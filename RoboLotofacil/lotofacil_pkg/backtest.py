from .v17_4_features import split_temporal
from .v21_5_melhorias_cientificas import teste_significancia_calibracao
from .v21_6_impopularidade import resumo_impopularidade_pacote
from .v20_2_poda_inteligente import (
    registrar_resultado_modelo_backtest,
    avaliar_e_podar_modelos,
    ESTADO_ATIVO, ESTADO_OBSERVACAO, ESTADO_SUSPENSO,
)
# V21.1-A: espelhamento automático no SQLite (falha silenciosa para não quebrar o fluxo)
try:
    from .v21_0_sqlite import (
        inicializar_banco_v21,
        db_registrar_desempenho,
        db_registrar_evento_poda,
        db_registrar_ranking_cientifico,
    )
    inicializar_banco_v21()
    _V21_SQLITE_OK = True
except Exception:
    _V21_SQLITE_OK = False
    def db_registrar_desempenho(_r): pass
    def db_registrar_evento_poda(_n, _e, _s, _p): pass
    def db_registrar_ranking_cientifico(_r): pass
"""
lotofacil_pkg/backtest.py
--------------------------
Backtesting, calibração vs. aleatório, laboratório histórico,
módulo científico V11, relatórios, dashboard e auditoria de pacotes.
"""
import os
import json
import math
import time
import random
from collections import Counter
from datetime import datetime
from statistics import mean

import pandas as pd

from . import config as _cfg
from .config import (
    NUMEROS, MIN_HIST, PASTA_EXPORT, PASTA_DADOS, TAMANHO_JOGO,
    ARQUIVO_DESEMPENHO_HISTORICO, ARQUIVO_CONHECIMENTO_CIENTIFICO,
    ARQUIVO_PERFORMANCE_ESTRATEGIA, ARQUIVO_APRENDIZADO,
    VERSAO_ROBO,
)
from .utils import (
    formatar_jogo, intersecao, contar_pares, soma_jogo,
    salvar_json, ler_json, tornar_json_seguro,
    garantir_estrutura_pastas, gerar_timestamp_arquivo, limitar,
    normalizar_scores, definir_rng_thread, limpar_rng_thread,
)
from .persistencia import salvar_csv_blindado
from .apostas import gerar_apostas
from .genetico import (
    analisar_estrutura_jogo_cached, analisar_estrutura_jogo,
    calcular_mapa_cobertura, resumo_estrutural_pacote,
    score_jogo, gerar_jogo_base, evoluir_populacao, mutacao,
    selecionar_jogos_cobertura_global, selecionar_jogos_diversos,
    recortar_historico_para_analise,
)
from .historico import analisar_historico
from .analise import calcular_motor_estrategico, calcular_ensemble_multi_ia
from .aprendizado import carregar_memoria_aprendizado, gerar_resumo_aprendizado


from .apostas import (
    carregar_performance_estrategias, salvar_performance_estrategias,
    registrar_performance_geracao,
    gerar_relatorio_evolucao_aprendizado,
)


def _seed_do_passo(i: int) -> int | None:
    """
    Deriva a seed de um passo de backtest a partir da seed global (config.SEED)
    e do índice do concurso testado.

    Necessário porque os passos rodam em paralelo (ThreadPoolExecutor) e todos
    compartilhavam o mesmo `random` global: threads concorrentes consumiam o
    mesmo fluxo pseudo-aleatório em ordem não determinística, e o backtest não
    era reprodutível mesmo com uma seed fixa. Cada passo agora recebe seu
    próprio gerador (thread-local, via definir_rng_thread), semeado de forma
    determinística — mesma seed + mesmo concurso => mesmo resultado, não
    importa em qual thread ou ordem o passo rodou.

    Se `config.SEED` for None ("aleatório verdadeiro"), retorna None: cada
    thread recebe um gerador independente semeado por entropia do SO, o que
    já evita a disputa pelo estado global sem exigir reprodutibilidade.
    """
    if _cfg.SEED is None:
        return None
    return (int(_cfg.SEED) * 1_000_003 + i) & 0xFFFFFFFF


def carregar_banco_desempenho(caminho: str = ARQUIVO_DESEMPENHO_HISTORICO) -> dict:
    dados = ler_json(caminho, default={"versao": "1.0", "registros": []})
    dados.setdefault("registros", [])
    return dados


def salvar_banco_desempenho(dados: dict, caminho: str = ARQUIVO_DESEMPENHO_HISTORICO) -> None:
    garantir_estrutura_pastas()
    dados["atualizado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    dados["total_registros"] = len(dados.get("registros", []))
    salvar_json(caminho, tornar_json_seguro(dados))


def resumir_configuracao_robo(configuracao: dict | None = None, analise: dict | None = None) -> dict:
    """Cria um resumo padronizado da configuração usada na geração."""
    configuracao = dict(configuracao or {})
    estrategia = (analise or {}).get("estrategia", {}) if isinstance(analise, dict) else {}
    return {
        "qtd_jogos": configuracao.get("qtd_jogos"),
        "janela_historica": configuracao.get("janela_historica"),
        "geracoes": configuracao.get("geracoes"),
        "populacao": configuracao.get("populacao"),
        "passos_backtest": configuracao.get("passos_backtest"),
        "modo_turbo": configuracao.get("modo_turbo"),
        "modo_estrategico": estrategia.get("modo"),
        "indice_confianca": estrategia.get("indice_confianca"),
        "ciclo_principal": estrategia.get("ciclo_principal"),
    }


def registrar_desempenho_historico_robo(jogos: list, resultado_real: list[int], analise: dict | None = None, pesos: dict | None = None, origem: str = "manual", concurso: int | None = None, configuracao: dict | None = None, caminho: str = ARQUIVO_DESEMPENHO_HISTORICO) -> dict:
    """
    Registra, em banco próprio, o desempenho do pacote gerado.
    Diferente da memória de IA, este banco é voltado para auditoria e comparação de configurações.
    """
    if not jogos:
        raise ValueError("Nenhum jogo informado para registrar desempenho.")
    resultado = sorted(set(int(n) for n in resultado_real))
    if len(resultado) != 15:
        raise ValueError("Resultado real inválido para registro de desempenho.")

    jogos_limpos = [sorted(set(int(n) for n in j)) for j in jogos if len(set(j)) == 15]
    acertos = [intersecao(j, resultado) for j in jogos_limpos]
    dist = dict(sorted(Counter(acertos).items()))
    melhor = max(acertos) if acertos else 0
    media_acertos = round(sum(acertos) / max(1, len(acertos)), 3)

    cfg = resumir_configuracao_robo(configuracao=configuracao, analise=analise)
    ensemble = (analise or {}).get("ensemble", {}) if isinstance(analise, dict) else {}
    consenso = ensemble.get("consenso", {}) if isinstance(ensemble, dict) else {}
    ranking = ensemble.get("ranking", []) if isinstance(ensemble, dict) else []
    top15 = [int(n) for n, _ in ranking[:15]] if ranking else []
    top10 = [int(n) for n, _ in ranking[:10]] if ranking else []
    top5 = [int(n) for n, _ in ranking[:5]] if ranking else []

    registro = {
        "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "origem": origem,
        "concurso": concurso,
        "resultado_real": resultado,
        "qtd_jogos": len(jogos_limpos),
        "melhor_acerto": melhor,
        "media_acertos": media_acertos,
        "distribuicao_acertos": dist,
        "qtd_11_mais": sum(1 for a in acertos if a >= 11),
        "qtd_12_mais": sum(1 for a in acertos if a >= 12),
        "qtd_13_mais": sum(1 for a in acertos if a >= 13),
        "taxa_11_mais": round(100 * sum(1 for a in acertos if a >= 11) / max(1, len(acertos)), 2),
        "taxa_12_mais": round(100 * sum(1 for a in acertos if a >= 12) / max(1, len(acertos)), 2),
        "taxa_13_mais": round(100 * sum(1 for a in acertos if a >= 13) / max(1, len(acertos)), 2),
        "configuracao": cfg,
        "top5_acertos": intersecao(top5, resultado) if top5 else None,
        "top10_acertos": intersecao(top10, resultado) if top10 else None,
        "top15_acertos": intersecao(top15, resultado) if top15 else None,
        "top_consenso": consenso.get("top_consenso", [])[:10] if isinstance(consenso, dict) else [],
    }

    banco = carregar_banco_desempenho(caminho)
    # Evita duplicar exatamente a mesma conferência do mesmo concurso com a mesma origem.
    chave = f"{origem}:{concurso}:{'-'.join(map(str, resultado))}:{len(jogos_limpos)}"
    existentes = {r.get("chave_registro") for r in banco.get("registros", [])}
    if chave in existentes:
        return registro, gerar_resumo_banco_desempenho(banco)
    registro["chave_registro"] = chave
    banco.setdefault("registros", []).append(registro)
    banco["registros"] = banco["registros"][-1000:]
    salvar_banco_desempenho(banco, caminho)
    # V21.1-A: espelha no SQLite (não bloqueia se falhar)
    db_registrar_desempenho(registro)
    return registro, gerar_resumo_banco_desempenho(banco)


def gerar_resumo_banco_desempenho(banco: dict | None = None, ultimos: int = 30) -> dict:
    banco = banco or carregar_banco_desempenho()
    registros = banco.get("registros", [])
    if not registros:
        return {"total_registros": 0, "texto": "Sem registros no banco histórico de desempenho."}

    amostra = registros[-ultimos:]
    melhores = [int(r.get("melhor_acerto", 0) or 0) for r in amostra]
    medias = [float(r.get("media_acertos", 0) or 0) for r in amostra]
    total = len(amostra)
    pct_11 = round(100 * sum(1 for m in melhores if m >= 11) / max(1, total), 1)
    pct_12 = round(100 * sum(1 for m in melhores if m >= 12) / max(1, total), 1)
    pct_13 = round(100 * sum(1 for m in melhores if m >= 13) / max(1, total), 1)

    por_config = {}
    for r in registros:
        cfg = r.get("configuracao", {}) or {}
        chave = f"J{cfg.get('qtd_jogos')}|G{cfg.get('geracoes')}|P{cfg.get('populacao')}|H{cfg.get('janela_historica')}|{cfg.get('modo_estrategico')}"
        por_config.setdefault(chave, []).append(int(r.get("melhor_acerto", 0) or 0))
    ranking_cfg = []
    for chave, vals in por_config.items():
        if len(vals) >= 2:
            ranking_cfg.append((chave, round(mean(vals), 3), max(vals), len(vals)))
    ranking_cfg.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)

    texto = []
    texto.append("BANCO HISTÓRICO DE DESEMPENHO DO ROBÔ")
    texto.append("-" * 72)
    texto.append(f"Registros totais: {len(registros)}")
    texto.append(f"Amostra analisada: últimos {total} registro(s)")
    texto.append(f"Média do melhor jogo: {mean(melhores):.2f}")
    texto.append(f"Média geral dos jogos: {mean(medias):.2f}")
    texto.append(f"Melhor marca na amostra: {max(melhores)} ponto(s)")
    texto.append(f"Taxa de pacotes com 11+: {pct_11}% | 12+: {pct_12}% | 13+: {pct_13}%")
    if ranking_cfg:
        texto.append("")
        texto.append("Configurações com melhor média histórica:")
        for chave, media_cfg, max_cfg, qtd in ranking_cfg[:5]:
            texto.append(f"- {chave} -> média melhor={media_cfg} | máximo={max_cfg} | usos={qtd}")

    return {
        "total_registros": len(registros),
        "media_melhor_ultimos": round(mean(melhores), 3),
        "media_geral_ultimos": round(mean(medias), 3),
        "melhor_ultimos": max(melhores),
        "pct_11_mais": pct_11,
        "pct_12_mais": pct_12,
        "pct_13_mais": pct_13,
        "ranking_configuracoes": ranking_cfg[:10],
        "texto": "\n".join(texto),
    }


def _ranking_modelos_historico() -> list[dict]:
    """Ranking de modelos do ensemble a partir de historico_modelos.json (Poda Inteligente V20.2)."""
    arq = os.path.join(PASTA_DADOS, "historico_modelos.json")
    if not os.path.exists(arq):
        return []
    try:
        with open(arq, "r", encoding="utf-8") as f:
            historico = json.load(f)
        ranking = []
        for modelo, dados in historico.items():
            ranking.append({
                "modelo": modelo,
                "media": round(dados.get("media", 0), 4),
                "concursos": dados.get("concursos", 0),
            })
        return sorted(ranking, key=lambda x: x["media"], reverse=True)
    except Exception:
        return []


def gerar_dashboard_desempenho_historico() -> str:
    resumo = gerar_resumo_banco_desempenho()
    banco = carregar_banco_desempenho()
    registros = banco.get("registros", [])
    linhas = [resumo.get("texto", "Sem dados.")]
    if registros:
        linhas.append("")
        linhas.append("ÚLTIMOS REGISTROS")
        linhas.append("-" * 72)
        for r in registros[-12:][::-1]:
            cfg = r.get("configuracao", {}) or {}
            linhas.append(
                f"{r.get('data_registro')} | Concurso {r.get('concurso')} | "
                f"melhor={r.get('melhor_acerto')} | média={r.get('media_acertos')} | "
                f"11+={r.get('qtd_11_mais')} | 12+={r.get('qtd_12_mais')} | 13+={r.get('qtd_13_mais')} | "
                f"J={cfg.get('qtd_jogos')} G={cfg.get('geracoes')} P={cfg.get('populacao')} H={cfg.get('janela_historica')}"
            )
    ranking_modelos = _ranking_modelos_historico()
    if ranking_modelos:
        linhas.append("")
        linhas.append("RANKING DE MODELOS DO ENSEMBLE")
        linhas.append("-" * 72)
        for i, m in enumerate(ranking_modelos[:10], start=1):
            linhas.append(f"{i}. {m['modelo']}: média={m['media']} | concursos={m['concursos']}")
    return "\n".join(linhas)


# =========================================================
# EXPORTAÇÃO DE APOSTAS EM PDF
# =========================================================
def exportar_apostas_pdf(jogos: list, caminho_saida: str | None = None, titulo: str = "Robô Lotofácil Ultra") -> dict:
    """
    Gera PDF com os jogos marcados visualmente no volante da Lotofácil.
    Usa apenas a biblioteca reportlab se disponível; caso contrário, exporta TXT formatado.

    Retorna um dict `{"arquivo": caminho, "formato": "pdf"|"txt_fallback",
    "jogos": int, "aviso": str (só no fallback)}` — não uma string (o
    docstring/type hint antigos diziam "retorna caminho do arquivo",
    incoerente com o `return {...}` de ambos os ramos; corrigido em
    2026-07-23, ver ARQUITETURA.md, junto com o wiring do botão que
    faltava na UI).
    """
    garantir_estrutura_pastas()
    if caminho_saida is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_saida = os.path.join(PASTA_EXPORT, f"apostas_{ts}.pdf")

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm

        doc = SimpleDocTemplate(caminho_saida, pagesize=A4,
                                topMargin=1.5*cm, bottomMargin=1.5*cm,
                                leftMargin=1.5*cm, rightMargin=1.5*cm)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph(f"<b>{titulo}</b>", styles["Title"]))
        story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')} | {len(jogos)} jogos", styles["Normal"]))
        story.append(Spacer(1, 0.4*cm))

        for idx, jogo in enumerate(jogos, 1):
            jogo_set = set(jogo)
            story.append(Paragraph(f"<b>Jogo {idx:02d}</b>  —  {formatar_jogo(jogo)}", styles["Heading3"]))

            # Grade 5x5 do volante
            data = []
            for linha in range(5):
                row = []
                for col in range(5):
                    n = linha * 5 + col + 1
                    row.append(str(n).zfill(2))
                data.append(row)

            t = Table(data, colWidths=[1.1*cm]*5, rowHeights=[1.1*cm]*5)
            estilo = [
                ("ALIGN",    (0, 0), (-1, -1), "CENTER"),
                ("VALIGN",   (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("GRID",     (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROUNDEDCORNERS", [3]),
            ]
            for linha in range(5):
                for col in range(5):
                    n = linha * 5 + col + 1
                    if n in jogo_set:
                        estilo += [
                            ("BACKGROUND", (col, linha), (col, linha), colors.HexColor("#00c8ff")),
                            ("TEXTCOLOR",  (col, linha), (col, linha), colors.black),
                            ("FONTNAME",   (col, linha), (col, linha), "Helvetica-Bold"),
                        ]
                    else:
                        estilo += [("BACKGROUND", (col, linha), (col, linha), colors.HexColor("#1a1a2e"))]
                        estilo += [("TEXTCOLOR",  (col, linha), (col, linha), colors.HexColor("#4a7fa8"))]
            t.setStyle(TableStyle(estilo))
            story.append(t)
            story.append(Spacer(1, 0.5*cm))

        doc.build(story)
        return {"arquivo": caminho_saida, "formato": "pdf", "jogos": len(jogos)}

    except ImportError:
        # Fallback: exporta TXT formatado se reportlab não estiver instalado
        caminho_txt = caminho_saida.replace(".pdf", ".txt")
        linhas = [titulo, "=" * 50,
                  f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                  f"Total de jogos: {len(jogos)}", ""]
        for idx, jogo in enumerate(jogos, 1):
            jogo_set = set(jogo)
            linhas.append(f"Jogo {idx:02d}: {formatar_jogo(jogo)}")
            for linha in range(5):
                row_str = ""
                for col in range(5):
                    n = linha * 5 + col + 1
                    row_str += f"[{n:02d}]" if n in jogo_set else f" {n:02d} "
                linhas.append(row_str)
            linhas.append("")
        with open(caminho_txt, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas))
        return {"arquivo": caminho_txt, "formato": "txt_fallback", "jogos": len(jogos), "aviso": "reportlab não instalado; exportado como TXT. Instale com: pip install reportlab"}


# =========================================================
# COMPARADOR DE ESTRATÉGIAS
# =========================================================
ESTRATEGIAS_COMPARADOR = [
    {
        "nome": "Conservador",
        "cor":  "#89b4fa",
        "params": {"geracoes": 20, "pop_size": 40, "janela_pct": 1.0,
                   "diversidade": 0.3, "taxa_mutacao": 0.25},
    },
    {
        "nome": "Equilibrado",
        "cor":  "#a6e3a1",
        "params": {"geracoes": 35, "pop_size": 70, "janela_pct": 1.0,
                   "diversidade": 0.5, "taxa_mutacao": 0.35},
    },
    {
        "nome": "Agressivo",
        "cor":  "#fab387",
        "params": {"geracoes": 60, "pop_size": 100, "janela_pct": 1.0,
                   "diversidade": 0.7, "taxa_mutacao": 0.50},
    },
    {
        "nome": "Janela Curta (60)",
        "cor":  "#cba6f7",
        "params": {"geracoes": 30, "pop_size": 60, "janela_pct": 0.5,
                   "diversidade": 0.5, "taxa_mutacao": 0.35},
    },
    {
        "nome": "Alta Mutação",
        "cor":  "#f38ba8",
        "params": {"geracoes": 30, "pop_size": 60, "janela_pct": 1.0,
                   "diversidade": 0.6, "taxa_mutacao": 0.70},
    },
    {
        "nome": "Baixa Mutação",
        "cor":  "#89dceb",
        "params": {"geracoes": 30, "pop_size": 60, "janela_pct": 1.0,
                   "diversidade": 0.4, "taxa_mutacao": 0.15},
    },
]


def _backtest_estrategia_unica(concursos: list, janela_base: int, passos: int, qtd_jogos: int, estrategia_def: dict) -> dict:
    """Roda backtest para uma estratégia específica e retorna métricas."""
    from concurrent.futures import ThreadPoolExecutor
    params  = estrategia_def["params"]
    janela  = max(MIN_HIST, int(janela_base * params.get("janela_pct", 1.0)))
    total   = len(concursos)
    janela  = min(janela, total - 5)
    passos  = min(passos, total - janela)
    inicio  = max(janela, total - passos)
    indices = list(range(inicio, total))

    # Estratégia customizada injetada no motor
    estrategia_injetada = {
        "modo":        "equilibrado",
        "diversidade": params["diversidade"],
        "taxa_mutacao":params["taxa_mutacao"],
    }

    def simular(i: int) -> dict:
        definir_rng_thread(_seed_do_passo(i))
        base = concursos[:i]
        real = concursos[i]
        try:
            jogos, _, _ = gerar_apostas(
                base,
                qtd_jogos=qtd_jogos,
                janela_analise=min(janela, len(base)),
                geracoes=params["geracoes"],
                pop_size=params["pop_size"],
                estrategia_override=estrategia_injetada,
            )
            acertos = [intersecao(j, real) for j in jogos]
            melhor  = max(acertos) if acertos else 0
            media   = round(sum(acertos) / len(acertos), 2) if acertos else 0
        except Exception:
            melhor, media = 0, 0.0
        finally:
            limpar_rng_thread()
        return {"melhor": melhor, "media": media}

    n_workers = min(4, max(1, len(indices)))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        resultados = list(ex.map(simular, indices))
    tempo = round(time.time() - t0, 1)

    melhores = [r["melhor"] for r in resultados]
    medias   = [r["media"]  for r in resultados]
    dist     = dict(sorted(Counter(melhores).items()))
    score_ponderado = (
        sum(m * (1.5 if m >= 13 else 1.2 if m >= 12 else 1.0 if m >= 11 else 0.7)
            for m in melhores) / max(len(melhores), 1)
    )
    return {
        "nome":              estrategia_def["nome"],
        "cor":               estrategia_def["cor"],
        "params":            params,
        "passos":            len(resultados),
        "media_melhor":      round(sum(melhores) / max(len(melhores), 1), 2),
        "max_melhor":        max(melhores) if melhores else 0,
        "media_geral":       round(sum(medias)   / max(len(medias), 1), 2),
        "score_ponderado":   round(score_ponderado, 3),
        "pct_11_mais":       round(100 * sum(1 for m in melhores if m >= 11) / max(len(melhores), 1), 1),
        "pct_13_mais":       round(100 * sum(1 for m in melhores if m >= 13) / max(len(melhores), 1), 1),
        "distribuicao":      dist,
        "serie_melhores":    melhores,
        "tempo_s":           tempo,
    }


def comparar_estrategias(concursos: list, janela: int, passos: int, qtd_jogos: int,
                         estrategias=None, status_cb=None):
    """
    Roda backtest para cada estratégia em sequência e retorna lista de resultados
    ordenada pelo score ponderado (melhor primeiro).
    """
    if estrategias is None:
        estrategias = ESTRATEGIAS_COMPARADOR
    resultados = []
    for i, est in enumerate(estrategias):
        if status_cb:
            status_cb(f"[{i+1}/{len(estrategias)}] Testando: {est['nome']}...")
        r = _backtest_estrategia_unica(concursos, janela, passos, qtd_jogos, est)
        resultados.append(r)
        if status_cb:
            status_cb(
                f"  ✅ {est['nome']}: média_melhor={r['media_melhor']} | "
                f"max={r['max_melhor']} | ≥11: {r['pct_11_mais']}% | "
                f"score={r['score_ponderado']} | {r['tempo_s']}s"
            )
    return sorted(resultados, key=lambda x: x["score_ponderado"], reverse=True)


# =========================================================
# BACKTEST
# =========================================================
def alimentar_poda_e_elo(registros: list[dict]) -> tuple[list[dict], str | None]:
    """
    Alimenta a poda inteligente V20.2 (pesos_modelos.json) e o ELO/4-fases
    V21.5-FULL a partir de uma série de passos, cada um com pelo menos
    `concurso_idx` e `acertos_modelo` (dict modelo -> acertos nesse passo).

    Compartilhado por `backtest_basico`, `backtest_ultra_massivo`,
    `executar_backtest_cientifico_massivo` e (2026-07-23)
    `executar_backtest_automatico` (ui.py) — até 2026-07-18 só
    `backtest_basico` alimentava esses dois sistemas, e até 2026-07-23
    "🤖 BT Automático" não alimentava nenhum dos dois apesar de fazer o
    mesmo tipo de trabalho de `backtest_basico` (ver ARQUITETURA.md).

    Retorna `(poda_resultado, erro_elo)`: `poda_resultado` é a lista de
    resultados de poda (ou `[]`); `erro_elo` é `None` se o ELO atualizou
    normalmente, ou uma mensagem de erro se falhou — antes esse segundo
    bloco engolia a exceção silenciosamente (`except: pass`), então uma
    falha real no ELO (ex.: `salvar_elo` sem permissão de escrita) nunca
    aparecia pro usuário, mesmo com a poda tendo funcionado e sido
    logada como sucesso (ver 2026-07-23 no ARQUITETURA.md).
    """
    poda_resultado: list[dict] = []
    try:
        acum: dict[str, list[float]] = {}
        for r in registros:
            for nome, val in (r.get("acertos_modelo") or {}).items():
                acum.setdefault(nome, []).append(val)

        if acum:
            media_por_modelo = {
                nome: round(sum(vals) / len(vals), 4)
                for nome, vals in acum.items()
            }
            registrar_resultado_modelo_backtest(media_por_modelo)
            poda_resultado = avaliar_e_podar_modelos(
                modelos_ativos=list(media_por_modelo.keys())
            )
            if poda_resultado:
                for r in poda_resultado:
                    db_registrar_evento_poda(
                        r.get("nome", ""),
                        r.get("estado", "ATIVO"),
                        r.get("score_sobrevivencia", 0.0),
                        r.get("peso_novo", 1.0),
                    )
    except Exception:
        pass

    erro_elo: str | None = None
    try:
        from .v21_5_meta_competitivo import atualizar_elo_concurso
        from .v21_5_auto_poda_full import avaliar_estados_modelos

        for idx, r in enumerate(registros):
            acertos_passo = r.get("acertos_modelo")
            if not acertos_passo:
                continue
            concurso_num = r.get("concurso_idx", idx + 1)
            elo_result = atualizar_elo_concurso(acertos_passo, concurso=concurso_num)
            elos_atuais = elo_result.get("elos_novos", {})
            avaliar_estados_modelos(acertos_passo, elos=elos_atuais, concurso=concurso_num)
    except Exception as e:
        erro_elo = str(e)

    return poda_resultado, erro_elo


def backtest_basico(concursos: list, janela: int = 120, qtd_jogos: int = 20, passos: int = 50, geracoes: int = 16, pop_size: int = 40) -> dict:
    """
    Backtest basico blindado com execucao paralela para maior velocidade.
    Ao final, registra a media de acertos de cada modelo no historico e
    aciona a poda inteligente V20.2 para ajustar os pesos do ensemble.

    IMPORTANTE: `geracoes`/`pop_size` devem ser a configuração REAL do robô
    (self.geracoes/self.pop_size na UI). Até 2026-07-18 esta função ignorava
    esses parâmetros e usava G=20/P=40 fixo no código — ou seja, a poda
    inteligente estava sendo calibrada com o desempenho de modelos numa
    config diferente da que "Gerar Jogos" de fato usa, contaminando os
    pesos reais do ensemble com dados de uma simulação irrelevante.
    """
    treino, validacao, teste = split_temporal(concursos)
    total = len(concursos or [])
    if total < MIN_HIST + 5:
        raise ValueError(f"Historico insuficiente para backtest: {total} concursos carregados. Use ao menos {MIN_HIST + 5}.")

    janela = int(janela)
    passos = int(passos)
    qtd_jogos = int(qtd_jogos)
    geracoes = int(geracoes)
    pop_size = int(pop_size)

    janela_maxima_segura = max(MIN_HIST, total - 5)
    janela = min(max(MIN_HIST, janela), janela_maxima_segura)

    passos_maximos = max(1, total - janela)
    passos = min(max(1, passos), passos_maximos)
    qtd_jogos = min(max(5, qtd_jogos), 30)

    inicio = max(janela, total - passos)
    indices = list(range(inicio, total))

    def simular(i: int) -> dict:
        definir_rng_thread(_seed_do_passo(i))
        try:
            base = concursos[:i]
            real = concursos[i]
            jogos, analise, pesos_gen = gerar_apostas(
                base,
                qtd_jogos=qtd_jogos,
                janela_analise=min(janela, len(base)),
                geracoes=geracoes,
                pop_size=pop_size,
            )
            acertos = [intersecao(j, real) for j in jogos]
            melhor = max(acertos) if acertos else 0
            media_pac = round(sum(acertos) / len(acertos), 4) if acertos else 0.0

            # ── V20.2: coleta acertos individuais de cada modelo ──
            # Para cada modelo, simulamos qual seria seu jogo "puro" (top-15 do
            # modelo isolado) e medimos os acertos contra o sorteio real.
            acertos_modelo: dict[str, float] = {}
            try:
                ensemble = (analise or {}).get("ensemble") or {}
                modelos_scores = ensemble.get("modelos") or {}
                for nome, scores_dez in modelos_scores.items():
                    if not scores_dez:
                        continue
                    top15 = sorted(scores_dez, key=lambda n: scores_dez[n], reverse=True)[:15]
                    acertos_modelo[nome] = float(intersecao(top15, real))
            except Exception:
                pass

            return {
                "concurso_idx": i + 1,
                "melhor_acerto": melhor,
                "media_acertos": round(media_pac, 2),
                "acertos_modelo": acertos_modelo,
            }
        finally:
            limpar_rng_thread()

    from concurrent.futures import ThreadPoolExecutor
    n_workers = min(4, len(indices))
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        resumo = list(executor.map(simular, indices))

    melhores = [r["melhor_acerto"] for r in resumo]
    dist = Counter(melhores)

    # ── V20.2/V21.5-FULL: registra acertos por modelo, poda e ELO ──────────
    poda_resultado, erro_elo = alimentar_poda_e_elo(resumo)

    acertos_por_passo = [r["media_acertos"] for r in resumo]
    return {
        "tipo": "basico",
        "passos": len(resumo),
        "janela": janela,
        "qtd_jogos": qtd_jogos,
        "media_melhor": round(sum(melhores) / len(melhores), 2) if melhores else 0,
        "max_melhor": max(melhores) if melhores else 0,
        "distribuicao": dict(sorted(dist.items())),
        "ultimos": resumo[-10:],
        "acertos_por_passo": acertos_por_passo,
        "poda_modelos": poda_resultado,
        "erro_elo": erro_elo,
    }

def gerar_jogos_aleatorios(qtd_jogos: int = 10) -> list[list[int]]:
    qtd_jogos = min(max(1, int(qtd_jogos)), 100)
    return [sorted(random.sample(NUMEROS, TAMANHO_JOGO)) for _ in range(qtd_jogos)]


def resumir_acertos_pacote(acertos: list) -> dict:
    acertos = [int(a) for a in (acertos or [])]
    if not acertos:
        return {
            "melhor": 0,
            "media": 0,
            "qtd_11": 0,
            "qtd_12": 0,
            "qtd_13": 0,
            "qtd_14": 0,
            "qtd_15": 0,
            "qtd_11_mais": 0,
            "qtd_12_mais": 0,
            "qtd_13_mais": 0,
        }
    c = Counter(acertos)
    return {
        "melhor": max(acertos),
        "media": round(sum(acertos) / len(acertos), 3),
        "qtd_11": c.get(11, 0),
        "qtd_12": c.get(12, 0),
        "qtd_13": c.get(13, 0),
        "qtd_14": c.get(14, 0),
        "qtd_15": c.get(15, 0),
        "qtd_11_mais": sum(1 for a in acertos if a >= 11),
        "qtd_12_mais": sum(1 for a in acertos if a >= 12),
        "qtd_13_mais": sum(1 for a in acertos if a >= 13),
    }


def score_calibracao_pacote(resumo: dict) -> float:
    return round(
        float(resumo.get("melhor", 0)) * 2.0
        + float(resumo.get("media", 0)) * 0.5
        + int(resumo.get("qtd_11", 0)) * 1.0
        + int(resumo.get("qtd_12", 0)) * 3.0
        + int(resumo.get("qtd_13", 0)) * 8.0
        + int(resumo.get("qtd_14", 0)) * 30.0
        + int(resumo.get("qtd_15", 0)) * 100.0,
        3,
    )


def resumir_linhas_calibracao(linhas: list, prefixo: str) -> dict:
    total = len(linhas)
    if not total:
        return {}
    melhores = [int(r.get(f"melhor_{prefixo}", 0)) for r in linhas]
    medias = [float(r.get(f"media_{prefixo}", 0)) for r in linhas]
    scores = [float(r.get(f"score_{prefixo}", 0)) for r in linhas]
    return {
        "media_melhor": round(sum(melhores) / total, 3),
        "media_geral": round(sum(medias) / total, 3),
        "media_score": round(sum(scores) / total, 3),
        "max_melhor": max(melhores),
        "pct_pacotes_11_mais": round(100 * sum(1 for r in linhas if int(r.get(f"qtd_11_mais_{prefixo}", 0)) > 0) / total, 2),
        "pct_pacotes_12_mais": round(100 * sum(1 for r in linhas if int(r.get(f"qtd_12_mais_{prefixo}", 0)) > 0) / total, 2),
        "pct_pacotes_13_mais": round(100 * sum(1 for r in linhas if int(r.get(f"qtd_13_mais_{prefixo}", 0)) > 0) / total, 2),
        "total_11_mais": sum(int(r.get(f"qtd_11_mais_{prefixo}", 0)) for r in linhas),
        "total_12_mais": sum(int(r.get(f"qtd_12_mais_{prefixo}", 0)) for r in linhas),
        "total_13_mais": sum(int(r.get(f"qtd_13_mais_{prefixo}", 0)) for r in linhas),
    }


def _descricao_seed() -> str:
    """
    Descreve o estado da seed no momento da chamada, para registro nos
    relatórios (auditoria: permite saber depois se um resultado veio de
    seed fixa e reproduzível, ou de entropia real). Lê `config.SEED`,
    atualizado por `seed_global()`/`_aplicar_seed_configurada()` (ui.py)
    logo antes de cada operação.
    """
    return f"fixa ({_cfg.SEED})" if _cfg.SEED is not None else "aleatória"


def salvar_relatorio_calibracao(resultado: dict) -> str:
    garantir_estrutura_pastas()
    timestamp = gerar_timestamp_arquivo()
    caminho_txt = os.path.join(PASTA_EXPORT, f"calibracao_vs_aleatorio_{timestamp}.txt")
    caminho_csv = os.path.join(PASTA_EXPORT, f"calibracao_vs_aleatorio_{timestamp}.csv")

    robo = resultado.get("resumo_robo", {})
    aleatorio = resultado.get("resumo_aleatorio", {})
    linhas = [
        "===== CALIBRACAO ROBO VS ALEATORIO =====",
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"Concursos testados: {resultado.get('passos', 0)}",
        f"Janela historica: {resultado.get('janela', 0)}",
        f"Jogos por pacote: {resultado.get('qtd_jogos', 0)}",
        f"Geracoes: {resultado.get('geracoes', 0)}",
        f"Populacao: {resultado.get('pop_size', 0)}",
        f"Seed: {_descricao_seed()}",
        "",
        "ROBO",
        f"Media do melhor jogo: {robo.get('media_melhor', 0)}",
        f"Media geral de acertos: {robo.get('media_geral', 0)}",
        f"Pacotes com 11+: {robo.get('pct_pacotes_11_mais', 0)}%",
        f"Pacotes com 12+: {robo.get('pct_pacotes_12_mais', 0)}%",
        f"Pacotes com 13+: {robo.get('pct_pacotes_13_mais', 0)}%",
        f"Total de jogos 11+: {robo.get('total_11_mais', 0)}",
        f"Total de jogos 12+: {robo.get('total_12_mais', 0)}",
        f"Total de jogos 13+: {robo.get('total_13_mais', 0)}",
        "",
        "ALEATORIO",
        f"Media do melhor jogo: {aleatorio.get('media_melhor', 0)}",
        f"Media geral de acertos: {aleatorio.get('media_geral', 0)}",
        f"Pacotes com 11+: {aleatorio.get('pct_pacotes_11_mais', 0)}%",
        f"Pacotes com 12+: {aleatorio.get('pct_pacotes_12_mais', 0)}%",
        f"Pacotes com 13+: {aleatorio.get('pct_pacotes_13_mais', 0)}%",
        f"Total de jogos 11+: {aleatorio.get('total_11_mais', 0)}",
        f"Total de jogos 12+: {aleatorio.get('total_12_mais', 0)}",
        f"Total de jogos 13+: {aleatorio.get('total_13_mais', 0)}",
        "",
        "COMPARATIVO",
        f"Robo venceu em score: {resultado.get('robo_venceu_score', 0)} pacote(s)",
        f"Aleatorio venceu em score: {resultado.get('aleatorio_venceu_score', 0)} pacote(s)",
        f"Empates em score: {resultado.get('empates_score', 0)} pacote(s)",
        f"Vantagem media do score: {resultado.get('vantagem_media_score', 0)}",
        "",
        "── Validação Estatística ──────────────────────────────",
        f"p-valor (Wilcoxon/t-test): {resultado.get('estatistica', {}).get('p_valor', 'N/A')}  {'✅ significativo (p<0.05)' if resultado.get('estatistica', {}).get('significativo') else '⚠️ não significativo'}",
        f"IC 95%% vitórias: [{resultado.get('estatistica', {}).get('ic95_vitoria', ['?','?'])[0]:.1%} – {resultado.get('estatistica', {}).get('ic95_vitoria', ['?','?'])[1]:.1%}]" if resultado.get('estatistica', {}).get('ic95_vitoria') else "IC 95% vitórias: N/A",
        f"Tamanho do efeito (Cohen d): {resultado.get('estatistica', {}).get('cohen_d', 'N/A')} ({resultado.get('estatistica', {}).get('interpretacao', '')})",
        "",
        "Observacao: isto mede desempenho historico contra uma referencia aleatoria. Nao e previsao nem garantia de premio.",
    ]
    with open(caminho_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))

    try:
        pd.DataFrame(resultado.get("linhas", [])).to_csv(caminho_csv, index=False, encoding="utf-8-sig")
    except Exception:
        caminho_csv = ""

    resultado["arquivo_txt"] = caminho_txt
    resultado["arquivo_csv"] = caminho_csv
    return resultado


def calibrar_robo_vs_aleatorio(concursos: list, janela: int = 120, qtd_jogos: int = 10, passos: int = 50, geracoes: int = 20, pop_size: int = 40, status_cb=None) -> dict:
    treino, validacao, teste = split_temporal(concursos)
    total = len(concursos or [])
    if total < MIN_HIST + 10:
        raise ValueError(f"Historico insuficiente para calibracao: {total} concursos. Use ao menos {MIN_HIST + 10}.")

    janela = min(max(MIN_HIST, int(janela)), max(MIN_HIST, total - 5))
    passos = min(max(1, int(passos)), max(1, total - janela))
    qtd_jogos = min(max(5, int(qtd_jogos)), 50)
    geracoes = max(5, int(geracoes))
    pop_size = max(20, int(pop_size))
    inicio = max(janela, total - passos)

    linhas = []
    for pos, i in enumerate(range(inicio, total), start=1):
        base = concursos[:i]
        real = sorted(concursos[i])
        jogos_robo, analise, pesos = gerar_apostas(
            base,
            qtd_jogos=qtd_jogos,
            janela_analise=min(janela, len(base)),
            geracoes=geracoes,
            pop_size=pop_size,
        )
        jogos_aleatorios = gerar_jogos_aleatorios(qtd_jogos)

        acertos_robo = [intersecao(j, real) for j in jogos_robo]
        acertos_aleatorios = [intersecao(j, real) for j in jogos_aleatorios]
        resumo_robo = resumir_acertos_pacote(acertos_robo)
        resumo_aleatorio = resumir_acertos_pacote(acertos_aleatorios)
        score_robo = score_calibracao_pacote(resumo_robo)
        score_aleatorio = score_calibracao_pacote(resumo_aleatorio)

        linha = {
            "teste": pos,
            "concurso_idx": i + 1,
            "resultado_real": formatar_jogo(real),
            "melhor_robo": resumo_robo["melhor"],
            "media_robo": resumo_robo["media"],
            "qtd_11_robo": resumo_robo["qtd_11"],
            "qtd_12_robo": resumo_robo["qtd_12"],
            "qtd_13_robo": resumo_robo["qtd_13"],
            "qtd_14_robo": resumo_robo["qtd_14"],
            "qtd_15_robo": resumo_robo["qtd_15"],
            "qtd_11_mais_robo": resumo_robo["qtd_11_mais"],
            "qtd_12_mais_robo": resumo_robo["qtd_12_mais"],
            "qtd_13_mais_robo": resumo_robo["qtd_13_mais"],
            "score_robo": score_robo,
            "melhor_aleatorio": resumo_aleatorio["melhor"],
            "media_aleatorio": resumo_aleatorio["media"],
            "qtd_11_aleatorio": resumo_aleatorio["qtd_11"],
            "qtd_12_aleatorio": resumo_aleatorio["qtd_12"],
            "qtd_13_aleatorio": resumo_aleatorio["qtd_13"],
            "qtd_14_aleatorio": resumo_aleatorio["qtd_14"],
            "qtd_15_aleatorio": resumo_aleatorio["qtd_15"],
            "qtd_11_mais_aleatorio": resumo_aleatorio["qtd_11_mais"],
            "qtd_12_mais_aleatorio": resumo_aleatorio["qtd_12_mais"],
            "qtd_13_mais_aleatorio": resumo_aleatorio["qtd_13_mais"],
            "score_aleatorio": score_aleatorio,
            "vantagem_score_robo": round(score_robo - score_aleatorio, 3),
            "modo": (analise.get("estrategia") or {}).get("modo", ""),
        }
        linhas.append(linha)

        if status_cb and (pos == 1 or pos % 5 == 0 or pos == passos):
            status_cb(
                f"Calibracao {pos}/{passos} | robo melhor={resumo_robo['melhor']} "
                f"| aleatorio melhor={resumo_aleatorio['melhor']} | vantagem score={linha['vantagem_score_robo']}"
            )

    vantagens = [float(r["vantagem_score_robo"]) for r in linhas]
    resultado = {
        "tipo": "calibracao_vs_aleatorio",
        "passos": len(linhas),
        "janela": janela,
        "qtd_jogos": qtd_jogos,
        "geracoes": geracoes,
        "pop_size": pop_size,
        "resumo_robo": resumir_linhas_calibracao(linhas, "robo"),
        "resumo_aleatorio": resumir_linhas_calibracao(linhas, "aleatorio"),
        "robo_venceu_score": sum(1 for v in vantagens if v > 0),
        "aleatorio_venceu_score": sum(1 for v in vantagens if v < 0),
        "empates_score": sum(1 for v in vantagens if v == 0),
        "vantagem_media_score": round(sum(vantagens) / len(vantagens), 3) if vantagens else 0,
        "linhas": linhas,
    }

    # ── V21.6: Validação estatística da calibração ──────────────────────────
    try:
        from .v20_6_bootstrap import teste_significancia, intervalo_confianca_taxa, tamanho_efeito_cohen_d
        n = len(vantagens)
        vitorias = resultado["robo_venceu_score"]
        scores_robo = [float(r["score_robo"]) for r in linhas]
        scores_ale  = [float(r["score_aleatorio"]) for r in linhas]

        # Converter floats para dicts no formato esperado pelo v20_6_bootstrap
        dicts_robo = [{"acertos": v} for v in scores_robo]
        dicts_ale  = [{"acertos": v} for v in scores_ale]

        sig = teste_significancia(dicts_robo, dicts_ale)
        ic  = intervalo_confianca_taxa(vitorias, n)
        cohen = tamanho_efeito_cohen_d(dicts_robo, dicts_ale)

        # Projeção de quantos passos adicionais seriam necessários para
        # p<0.05, mantendo a proporção atual de vitórias. Reaproveita o
        # teste binomial de teste_significancia_calibracao() (já usado em
        # outros relatórios), que faz essa projeção por busca incremental
        # sobre a distribuição binomial real — a fórmula anterior aqui
        # dividia o numerador de uma margem de erro pelo p-value, duas
        # grandezas incompatíveis, produzindo um número sem significado
        # estatístico.
        sig_binomial = teste_significancia_calibracao(
            vitorias_robo=resultado["robo_venceu_score"],
            vitorias_aleatorio=resultado["aleatorio_venceu_score"],
            empates=resultado["empates_score"],
        )

        resultado["estatistica"] = {
            "p_valor":        round(sig.get("p_valor", 1.0), 4),
            "significativo":  sig.get("significativo", False),
            "ic95_vitoria":   [round(ic.get("inferior", 0), 3), round(ic.get("superior", 1), 3)],
            "cohen_d":        round(cohen.get("cohen_d", 0.0), 3),
            "interpretacao":  cohen.get("magnitude", ""),
            "passos_extra_p005": sig_binomial.get("passos_extras_para_significancia"),
        }
    except Exception:
        resultado["estatistica"] = {}

    return salvar_relatorio_calibracao(resultado)


def salvar_relatorio_auto_diagnostico(resultado: dict) -> str:
    garantir_estrutura_pastas()
    timestamp = gerar_timestamp_arquivo()
    caminho_txt = os.path.join(PASTA_EXPORT, f"auto_diagnostico_lotofacil_{timestamp}.txt")

    calibracao = resultado.get("calibracao") or {}
    comparador = resultado.get("comparador") or []
    robo = calibracao.get("resumo_robo", {})
    aleatorio = calibracao.get("resumo_aleatorio", {})
    vencedor_comp = comparador[0] if comparador else {}

    linhas = [
        "===== AUTO DIAGNOSTICO LOTOFACIL =====",
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"Concursos carregados: {resultado.get('total_concursos', 0)}",
        f"Janela historica: {resultado.get('janela', 0)}",
        f"Passos: {resultado.get('passos', 0)}",
        f"Jogos por pacote: {resultado.get('qtd_jogos', 0)}",
        f"Seed: {_descricao_seed()}",
        "",
        "1) CALIBRACAO ROBO VS ALEATORIO",
        f"Robo pacotes 11+: {robo.get('pct_pacotes_11_mais', 0)}%",
        f"Robo pacotes 12+: {robo.get('pct_pacotes_12_mais', 0)}%",
        f"Robo pacotes 13+: {robo.get('pct_pacotes_13_mais', 0)}%",
        f"Aleatorio pacotes 11+: {aleatorio.get('pct_pacotes_11_mais', 0)}%",
        f"Aleatorio pacotes 12+: {aleatorio.get('pct_pacotes_12_mais', 0)}%",
        f"Vantagem media de score: {calibracao.get('vantagem_media_score', 0)}",
        f"Arquivo calibracao: {calibracao.get('arquivo_txt', '')}",
        "",
        "2) COMPARADOR DE ESTRATEGIAS",
        f"Estrategia vencedora: {vencedor_comp.get('nome', '')}",
        f"Score: {vencedor_comp.get('score_ponderado', 0)}",
        f"Media do melhor jogo: {vencedor_comp.get('media_melhor', 0)}",
        f">=11: {vencedor_comp.get('pct_11_mais', 0)}%",
        f">=13: {vencedor_comp.get('pct_13_mais', 0)}%",
        "",
        "RECOMENDACAO PRATICA",
    ]

    recomendacao = []
    if vencedor_comp:
        recomendacao.append(f"No comparador, a estrategia mais forte foi '{vencedor_comp.get('nome', '')}'.")
    if float(calibracao.get("vantagem_media_score", 0) or 0) <= 0:
        recomendacao.append("A vantagem contra aleatorio ficou baixa ou negativa; aumente passos antes de confiar na calibracao.")
    else:
        recomendacao.append("A vantagem contra aleatorio ficou positiva; valide novamente com mais passos antes de usar como padrao.")
    linhas.extend(recomendacao)
    linhas.extend([
        "",
        "Observacao: diagnostico mede historico e comparativos. Nao e previsao nem garantia de premio.",
    ])

    with open(caminho_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))

    resultado["arquivo_txt"] = caminho_txt
    return resultado


def executar_auto_diagnostico_lotofacil(  # -> dict
    concursos,
    janela=120,
    qtd_jogos=10,
    passos=30,
    geracoes=35,
    pop_size=70,
    status_cb=None,
):
    treino, validacao, teste = split_temporal(concursos)
    total = len(concursos or [])
    if total < MIN_HIST + 10:
        raise ValueError(f"Historico insuficiente para auto diagnostico: {total} concursos. Use ao menos {MIN_HIST + 10}.")

    janela = min(max(MIN_HIST, int(janela)), max(MIN_HIST, total - 5))
    passos = min(max(1, int(passos)), max(1, total - janela))
    qtd_jogos = min(max(5, int(qtd_jogos)), 30)
    geracoes = max(5, int(geracoes))
    pop_size = max(20, int(pop_size))

    if status_cb:
        status_cb("Auto Diagnostico 1/2: calibrando robo vs aleatorio...")
    calibracao = calibrar_robo_vs_aleatorio(
        concursos,
        janela=janela,
        qtd_jogos=qtd_jogos,
        passos=passos,
        geracoes=geracoes,
        pop_size=pop_size,
        status_cb=status_cb,
    )

    if status_cb:
        status_cb("Auto Diagnostico 2/2: comparando estrategias...")
    comparador = comparar_estrategias(
        concursos,
        janela=janela,
        passos=passos,
        qtd_jogos=qtd_jogos,
        status_cb=status_cb,
    )

    return salvar_relatorio_auto_diagnostico({
        "tipo": "auto_diagnostico",
        "total_concursos": total,
        "janela": janela,
        "passos": passos,
        "qtd_jogos": qtd_jogos,
        "geracoes": geracoes,
        "pop_size": pop_size,
        "calibracao": calibracao,
        "comparador": comparador,
    })


def resumir_serie_backtest(registros: list) -> dict:
    melhores = [int(r.get("melhor_acerto", 0)) for r in registros]
    medias = [float(r.get("media_acertos", 0)) for r in registros]
    dist = Counter(melhores)
    passos = len(registros)
    if not passos:
        return {
            "passos": 0, "media_melhor": 0, "media_geral": 0, "max_melhor": 0,
            "distribuicao": {}, "taxa_11": 0, "taxa_12": 0, "taxa_13": 0, "score": 0,
        }
    taxa_11 = sum(1 for x in melhores if x >= 11) / passos
    taxa_12 = sum(1 for x in melhores if x >= 12) / passos
    taxa_13 = sum(1 for x in melhores if x >= 13) / passos
    score = (mean(melhores) * 1.00) + (taxa_11 * 1.20) + (taxa_12 * 2.20) + (taxa_13 * 4.50) + (max(melhores) * 0.15)
    return {
        "passos": passos,
        "media_melhor": round(mean(melhores), 3),
        "media_geral": round(mean(medias), 3) if medias else 0,
        "max_melhor": max(melhores),
        "distribuicao": dict(sorted(dist.items())),
        "taxa_11": round(taxa_11 * 100, 2),
        "taxa_12": round(taxa_12 * 100, 2),
        "taxa_13": round(taxa_13 * 100, 2),
        "score": round(score, 4),
    }


def salvar_relatorio_backtest_ultra(resultado: dict) -> str:
    garantir_estrutura_pastas()
    caminho = os.path.join(PASTA_EXPORT, f"backtest_ultra_massivo_{gerar_timestamp_arquivo()}.txt")
    linhas = []
    linhas.append("BACKTEST ULTRA MASSIVO - ROBÔ LOTOFÁCIL\n")
    linhas.append("=" * 78 + "\n")
    linhas.append(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
    linhas.append(f"Passos: {resultado.get('passos')} | Janela: {resultado.get('janela')} | Jogos por rodada: {resultado.get('qtd_jogos')}\n")
    linhas.append(f"Seed: {_descricao_seed()}\n")
    linhas.append(f"Configuração vencedora: {resultado.get('configuracao_vencedora', {}).get('nome', '')}\n\n")

    linhas.append("RANKING DAS CONFIGURAÇÕES\n")
    linhas.append("-" * 78 + "\n")
    for i, item in enumerate(resultado.get("ranking_configuracoes", []), start=1):
        linhas.append(
            f"{i}. {item.get('nome')} | score={item.get('score')} | média melhor={item.get('media_melhor')} | "
            f"máx={item.get('max_melhor')} | 11+={item.get('taxa_11')}% | 12+={item.get('taxa_12')}% | 13+={item.get('taxa_13')}%\n"
        )
        linhas.append(f"   distribuição: {item.get('distribuicao')}\n")

    linhas.append("\nCAMPEONATO ENTRE MODELOS DO ENSEMBLE\n")
    linhas.append("-" * 78 + "\n")
    for i, item in enumerate(resultado.get("ranking_modelos", []), start=1):
        linhas.append(f"{i}. {item.get('modelo')} | peso médio usado={item.get('peso_medio')} | presença={item.get('presenca')}\n")

    linhas.append("\nÚltimas rodadas simuladas da configuração vencedora:\n")
    for r in resultado.get("ultimos", [])[-15:]:
        linhas.append(f"Concurso idx {r.get('concurso_idx')}: melhor={r.get('melhor_acerto')} | média={r.get('media_acertos')} | modo={r.get('modo')}\n")

    linhas.append("\nObservação: o backtest mede robustez estatística em concursos passados. Não é previsão nem garantia de prêmio.\n")
    with open(caminho, "w", encoding="utf-8") as f:
        f.writelines(linhas)
    return caminho


def backtest_ultra_massivo(concursos: list, janela: int = 120, qtd_jogos: int = 20, passos: int = 200, status_cb=None, geracoes: int = 16, pop_size: int = 40) -> dict:
    """
    Backtest pesado blindado, com a configuração G/P real do robô.

    Até 2026-07-18 esta função comparava 3 variantes que só diferiam por
    escala de gerações/população ("Ultra Rápido" G=16/P=36, "Ultra
    Equilibrado" G=24/P=52, "Ultra Forte" G=34/P=70) — nenhuma delas era a
    configuração fixa de verdade (G=16/P=40), e o Mapa G×P já confirmou
    equivalência estatística nessa faixa toda, então a comparação só
    custava tempo (3x as simulações) para declarar um "vencedor" arbitrário
    entre configs que sabemos indistinguíveis. Pior: esse resultado
    (baseado em G/P que não é o do robô) não alimentava a poda de modelos
    — mas dava a falsa impressão de estar validando "o robô". Reduzido
    para uma única simulação com a configuração real (`geracoes`/`pop_size`,
    parâmetros repassados por quem chama — normalmente `self.geracoes`/
    `self.pop_size` da UI).
    """
    treino, validacao, teste = split_temporal(concursos)
    total = len(concursos or [])
    if total < MIN_HIST + 5:
        raise ValueError(f"Histórico insuficiente para backtest ultra: {total} concursos carregados. Use ao menos {MIN_HIST + 5}.")

    janela = int(janela)
    passos = int(passos)
    qtd_jogos = int(qtd_jogos)
    geracoes = int(geracoes)
    pop_size = int(pop_size)

    # A janela precisa deixar concursos posteriores para simulação.
    janela_maxima_segura = max(MIN_HIST, total - 5)
    janela = min(max(MIN_HIST, janela), janela_maxima_segura)

    passos_maximos = max(1, total - janela)
    passos = min(max(1, passos), passos_maximos)
    qtd_jogos = min(max(5, qtd_jogos), 30)
    inicio = max(janela, total - passos)

    def avisar(msg: str) -> None:
        if status_cb:
            status_cb(msg)

    acumulador_modelos = Counter()
    presenca_modelos = Counter()
    registros = []

    total_tarefas = total - inicio
    avisar(f"Backtest ultra massivo: G={geracoes} | P={pop_size} (configuração real do robô)")
    for tarefa, i in enumerate(range(inicio, total), start=1):
        base = concursos[:i]
        real = concursos[i]
        jogos, analise, pesos = gerar_apostas(
            base,
            qtd_jogos=qtd_jogos,
            janela_analise=min(janela, len(base)),
            geracoes=geracoes,
            pop_size=pop_size,
        )
        acertos = [intersecao(j, real) for j in jogos]
        melhor = max(acertos) if acertos else 0
        media_acertos = round(sum(acertos) / len(acertos), 3) if acertos else 0
        modo = (analise.get("estrategia") or {}).get("modo", "")
        confianca_modelos = ((analise.get("ensemble") or {}).get("confianca_modelos") or {})
        for modelo, peso in confianca_modelos.items():
            acumulador_modelos[modelo] += float(peso)
            presenca_modelos[modelo] += 1

        # Mesmo calculo de acertos por modelo que backtest_basico usa para
        # alimentar poda inteligente/ELO (ver alimentar_poda_e_elo) — antes
        # só o modo <120 passos fazia isso, deixando o robô real sem
        # atualização de pesos sempre que "Ultra Massivo" era acionado.
        acertos_modelo: dict[str, float] = {}
        try:
            modelos_scores = ((analise.get("ensemble") or {}).get("modelos") or {})
            for nome, scores_dez in modelos_scores.items():
                if not scores_dez:
                    continue
                top15 = sorted(scores_dez, key=lambda n: scores_dez[n], reverse=True)[:15]
                acertos_modelo[nome] = float(intersecao(top15, real))
        except Exception:
            pass

        registros.append({
            "concurso_idx": i + 1,
            "melhor_acerto": melhor,
            "media_acertos": media_acertos,
            "modo": modo,
            "acertos_modelo": acertos_modelo,
        })
        if tarefa % 10 == 0 or tarefa == total_tarefas:
            avisar(f"Backtest ultra: {tarefa}/{total_tarefas} simulações concluídas.")

    _poda_resultado_ultra, _erro_elo_ultra = alimentar_poda_e_elo(registros)
    if _erro_elo_ultra:
        avisar(f"⚠️ ELO/4-fases não pôde ser atualizado: {_erro_elo_ultra}")

    resumo = resumir_serie_backtest(registros)
    resumo.update({
        "nome": f"Configuração validada (G={geracoes}/P={pop_size})",
        "geracoes": geracoes,
        "pop_size": pop_size,
        "ultimos": registros[-20:],
        # Serie completa por passo (mesma convencao de backtest_basico) --
        # sem isso, Bootstrap IC nao tem como calcular variancia real e
        # cai num fallback degenerado (media replicada, erro padrao 0).
        "acertos_por_passo": [r["media_acertos"] for r in registros],
    })
    avisar(f"Resultado: score={resumo['score']} | média melhor={resumo['media_melhor']} | máx={resumo['max_melhor']}")

    ranking_modelos = []
    for modelo, total_peso in acumulador_modelos.items():
        pres = max(1, presenca_modelos[modelo])
        ranking_modelos.append({
            "modelo": modelo,
            "peso_medio": round(total_peso / pres, 4),
            "presenca": int(pres),
        })
    ranking_modelos = sorted(ranking_modelos, key=lambda x: x["peso_medio"], reverse=True)

    resultado = {
        "tipo": "ultra_massivo",
        "passos": total - inicio,
        "janela": janela,
        "qtd_jogos": qtd_jogos,
        "ranking_configuracoes": [resumo],
        "ranking_modelos": ranking_modelos,
        "configuracao_vencedora": resumo,
        "media_melhor": resumo.get("media_melhor", 0),
        "max_melhor": resumo.get("max_melhor", 0),
        "distribuicao": resumo.get("distribuicao", {}),
        "ultimos": resumo.get("ultimos", []),
        "acertos_por_passo": resumo.get("acertos_por_passo", []),
    }
    resultado["arquivo_relatorio"] = salvar_relatorio_backtest_ultra(resultado)
    return resultado


# =========================================================
# MÓDULO CIENTÍFICO V11 — BACKTEST, COMPETIÇÃO, AUTOCALIBRAÇÃO E CONHECIMENTO
# =========================================================
def carregar_conhecimento_cientifico(caminho: str = ARQUIVO_CONHECIMENTO_CIENTIFICO) -> dict:
    dados = ler_json(caminho, default={
        "versao": "11.0",
        "execucoes": [],
        "ranking_configuracoes": [],
        "ranking_modelos": [],
        "recomendacao_atual": {},
    })
    dados.setdefault("execucoes", [])
    dados.setdefault("ranking_configuracoes", [])
    dados.setdefault("ranking_modelos", [])
    dados.setdefault("recomendacao_atual", {})
    return dados


def salvar_conhecimento_cientifico(dados: dict, caminho: str = ARQUIVO_CONHECIMENTO_CIENTIFICO) -> None:
    garantir_estrutura_pastas()
    dados["atualizado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    dados["execucoes"] = dados.get("execucoes", [])[-40:]
    salvar_json(caminho, tornar_json_seguro(dados))


def _score_cientifico(melhores: dict, medias: dict) -> float:
    melhores = [int(x) for x in melhores]
    medias = [float(x) for x in medias]
    if not melhores:
        return 0.0
    qtd = len(melhores)
    taxa11 = sum(1 for x in melhores if x >= 11) / qtd
    taxa12 = sum(1 for x in melhores if x >= 12) / qtd
    taxa13 = sum(1 for x in melhores if x >= 13) / qtd
    taxa14 = sum(1 for x in melhores if x >= 14) / qtd
    return round(
        mean(melhores) * 1.20
        + (mean(medias) if medias else 0) * 0.35
        + taxa11 * 1.80
        + taxa12 * 3.60
        + taxa13 * 7.50
        + taxa14 * 18.00
        + max(melhores) * 0.25,
        5,
    )


def _resumo_cientifico(nome: str, tipo: str, registros: list, extra: dict | None = None) -> dict:
    extra = extra or {}
    melhores = [int(r.get("melhor_acerto", 0)) for r in registros]
    medias = [float(r.get("media_acertos", 0)) for r in registros]
    passos = len(registros)
    dist = Counter(melhores)
    return {
        "nome": nome,
        "tipo": tipo,
        "passos": passos,
        "media_melhor": round(mean(melhores), 3) if melhores else 0,
        "media_geral": round(mean(medias), 3) if medias else 0,
        "max_melhor": max(melhores) if melhores else 0,
        "pct_11_mais": round(100 * sum(1 for x in melhores if x >= 11) / max(1, passos), 2),
        "pct_12_mais": round(100 * sum(1 for x in melhores if x >= 12) / max(1, passos), 2),
        "pct_13_mais": round(100 * sum(1 for x in melhores if x >= 13) / max(1, passos), 2),
        "pct_14_mais": round(100 * sum(1 for x in melhores if x >= 14) / max(1, passos), 2),
        "distribuicao": dict(sorted(dist.items())),
        "score_cientifico": _score_cientifico(melhores, medias),
        "ultimos": registros[-12:],
        **extra,
    }


def montar_configuracoes_cientificas() -> list[dict]:
    """
    Configurações testadas pelo Backtest Científico V11.

    Até 2026-07-16 esta função testava 4 variantes que só diferiam por
    escala de gerações/população ("Rápida robusta", "Equilibrada
    científica", "Exploratória forte", além da base) — o Mapa G x P
    (n=300, TOST margem=0.3) confirmou equivalência estatística entre
    G=16 e G=300, então essa busca comparava configurações que já
    sabemos indistinguíveis, custando tempo à toa. A função não recebe
    mais `geracoes`/`pop_size` do chamador (2026-07-19): recebê-los sem
    usá-los para nada dava a falsa impressão de que o G/P configurado na
    tela influenciava as variantes testadas, quando na prática elas
    sempre foram G=16/P=40 fixo — que é, coincidentemente, a própria
    configuração real do robô.

    Mantém só a comparação que ainda faz sentido: G/P fixo (16/40) vs.
    a mesma config com diversidade ampliada (parâmetro não testado até
    agora).
    """
    candidatos = [
        {"nome": "Configuração validada (G=16/P=40)", "geracoes": 16, "pop_size": 40},
        {"nome": "Diversidade ampliada", "geracoes": 16, "pop_size": 40, "override": {"diversidade": 0.86, "limite_intersecao": 11}},
    ]
    return candidatos


def executar_backtest_cientifico_massivo(concursos: list, janela: int = 120, qtd_jogos: int = 20, passos: int = 80, geracoes=120, pop_size=120, status_cb=None):
    """
    Evolução 1, 2, 3 e 4:
    1) Backtest científico massivo por configurações.
    2) Campeonato entre modelos do ensemble.
    3) Autocalibração de gerações/população/diversidade.
    4) Banco de conhecimento histórico do próprio robô.

    Desde 2026-07-18, o campeonato de modelos (fase 2) também alimenta a
    poda inteligente (`pesos_modelos.json`) e o ELO/4-fases via
    `alimentar_poda_e_elo()` — a mesma infraestrutura que `backtest_basico`
    e `backtest_ultra_massivo` alimentam a cada rodada, só que aqui com uma
    medição mais rigorosa (pipeline completo por modelo isolado via
    `forcar_modelo`, não uma extração bruta de top-15). Funciona como
    correção periódica por cima da atualização contínua e barata do
    "📊 Backtest".

    `geracoes`/`pop_size` (parâmetros desta função) são validados/limitados
    mas não influenciam mais nenhuma fase: a fase 1
    (`montar_configuracoes_cientificas()`) sempre testa G=16/P=40 fixo, e a
    fase 2 (campeonato de modelos) sempre herda G/P do vencedor da fase 1
    (`vencedor_config`), que também já vem com "geracoes"/"pop_size"
    preenchidos — o fallback para os parâmetros do caller nunca dispara na
    prática. Mantidos na assinatura só por estabilidade de chamada externa
    (ver 2026-07-19 no ARQUITETURA.md).
    """
    treino, validacao, teste = split_temporal(concursos)
    total = len(concursos or [])
    if total < MIN_HIST + 10:
        raise ValueError(f"Histórico insuficiente para Backtest Científico: {total}. Use ao menos {MIN_HIST + 10} concursos.")

    janela = min(max(MIN_HIST, int(janela)), max(MIN_HIST, total - 5))
    passos = min(max(5, int(passos)), max(1, total - janela))
    qtd_jogos = min(max(5, int(qtd_jogos)), 50)
    geracoes = min(max(10, int(geracoes)), 600)
    pop_size = min(max(30, int(pop_size)), 400)
    inicio = max(janela, total - passos)
    indices = list(range(inicio, total))
    if status_cb:
        status_cb(f"[V11] total={total} | janela={janela} | passos_efetivos={len(indices)}")

    def avisar(msg: str) -> None:
        if status_cb:
            status_cb(msg)

    def rodar_variante(nome: str, tipo: str, ger: int, pop: int, override: dict | None = None) -> tuple[dict, list[dict]]:
        override = dict(override or {})
        registros = []
        t0 = time.time()
        for pos, i in enumerate(indices, start=1):
            base = concursos[:i]
            real = sorted(concursos[i])
            jogos, analise, pesos = gerar_apostas(
                base,
                qtd_jogos=qtd_jogos,
                janela_analise=min(janela, len(base)),
                geracoes=ger,
                pop_size=pop,
                estrategia_override=override,
            )
            acertos = [intersecao(j, real) for j in jogos]
            estrategia = analise.get("estrategia") or {}
            registros.append({
                "concurso_idx": i + 1,
                "melhor_acerto": max(acertos) if acertos else 0,
                "media_acertos": round(sum(acertos) / max(1, len(acertos)), 3) if acertos else 0,
                "modo": estrategia.get("modo", ""),
            })
            if pos == 1 or pos % 10 == 0 or pos == len(indices):
                avisar(f"{nome}: {pos}/{len(indices)} testes concluídos.")
        resumo = _resumo_cientifico(nome, tipo, registros, {
            "geracoes": int(ger),
            "pop_size": int(pop),
            "override": override,
            "tempo_s": round(time.time() - t0, 1),
        })
        return resumo, registros

    avisar("Fase 1/4: Backtest científico por configurações...")
    configs = montar_configuracoes_cientificas()
    resultados_config = []
    for cfg in configs:
        resumo_cfg, _ = rodar_variante(
            cfg["nome"], "configuracao", cfg["geracoes"], cfg["pop_size"], cfg.get("override")
        )
        resultados_config.append(resumo_cfg)
    ranking_config = sorted(resultados_config, key=lambda r: r.get("score_cientifico", 0), reverse=True)
    vencedor_config = ranking_config[0] if ranking_config else {}

    avisar("Fase 2/4: Campeonato entre modelos do ensemble...")
    modelos = ["estatistico", "markov", "bayesiano", "tendencia", "neural_leve", "cobertura", "pares_trios"]
    resultados_modelos = []
    registros_por_modelo: dict[str, list[dict]] = {}
    ger_v = int(vencedor_config.get("geracoes", geracoes) or geracoes)
    pop_v = int(vencedor_config.get("pop_size", pop_size) or pop_size)
    for modelo in modelos:
        resumo_modelo, registros_modelo = rodar_variante(
            f"Modelo isolado: {modelo}", "modelo", ger_v, pop_v, {"forcar_modelo": modelo}
        )
        resultados_modelos.append(resumo_modelo)
        registros_por_modelo[modelo] = registros_modelo
    ranking_modelos = sorted(resultados_modelos, key=lambda r: r.get("score_cientifico", 0), reverse=True)
    vencedor_modelo = ranking_modelos[0] if ranking_modelos else {}

    # Alimenta poda inteligente (pesos_modelos.json) e ELO/4-fases com o
    # campeonato de modelos isolados — metodologia mais rigorosa que a do
    # backtest_basico (roda o pipeline completo por modelo, não extrai um
    # top-15 bruto), usada aqui como correção periódica por cima da
    # atualização contínua e barata que o "📊 Backtest" já faz a cada rodada.
    try:
        por_passo: dict[int, dict] = {}
        for modelo, registros_modelo in registros_por_modelo.items():
            for r in registros_modelo:
                idx = r["concurso_idx"]
                entrada = por_passo.setdefault(idx, {"concurso_idx": idx, "acertos_modelo": {}})
                entrada["acertos_modelo"][modelo] = r["media_acertos"]
        _, _erro_elo_cientifico = alimentar_poda_e_elo(list(por_passo.values()))
        if _erro_elo_cientifico:
            avisar(f"⚠️ ELO/4-fases não pôde ser atualizado: {_erro_elo_cientifico}")
    except Exception:
        pass

    avisar("Fase 3/4: Gerando autocalibração...")
    recomendacao = {
        "janela": int(janela),
        "qtd_jogos": int(qtd_jogos),
        "geracoes": int(vencedor_config.get("geracoes", geracoes)),
        "pop_size": int(vencedor_config.get("pop_size", pop_size)),
        "estrategia_base": vencedor_config.get("nome", ""),
        "modelo_campeao": vencedor_modelo.get("nome", ""),
        "score_configuracao": vencedor_config.get("score_cientifico", 0),
        "score_modelo": vencedor_modelo.get("score_cientifico", 0),
        "observacao": "Use como sugestão técnica. Valide periodicamente porque sorteios são aleatórios.",
    }

    resultado = {
        "tipo": "backtest_cientifico_v11",
        "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "total_concursos": total,
        "janela": janela,
        "passos": len(indices),
        "qtd_jogos": qtd_jogos,
        "ranking_configuracoes": ranking_config,
        "ranking_modelos": ranking_modelos,
        "configuracao_vencedora": vencedor_config,
        "modelo_vencedor": vencedor_modelo,
        "recomendacao": recomendacao,
    }

    avisar("Fase 4/4: Atualizando banco de conhecimento histórico...")
    conhecimento = carregar_conhecimento_cientifico()
    conhecimento.setdefault("execucoes", []).append(resultado)
    conhecimento["ranking_configuracoes"] = ranking_config
    conhecimento["ranking_modelos"] = ranking_modelos
    conhecimento["recomendacao_atual"] = recomendacao
    salvar_conhecimento_cientifico(conhecimento)
    # V21.1-A: espelha ranking científico no SQLite
    db_registrar_ranking_cientifico(ranking_modelos)
    # V21.5-FULL: registra no Hall da Fama
    try:
        from .v21_3_1_hall_fama_auto import registrar_hall_fama
        registrar_hall_fama(ranking_modelos, janela="geral")
    except Exception:
        pass
    resultado["arquivo_conhecimento"] = ARQUIVO_CONHECIMENTO_CIENTIFICO
    resultado["arquivo_relatorio"] = salvar_relatorio_backtest_cientifico(resultado)
    return resultado


def salvar_relatorio_backtest_cientifico(resultado: dict) -> str:
    garantir_estrutura_pastas()
    caminho = os.path.join(PASTA_EXPORT, f"backtest_cientifico_v11_{gerar_timestamp_arquivo()}.txt")
    linhas = []
    linhas.append("BACKTEST CIENTÍFICO V11 - ROBÔ LOTOFÁCIL")
    linhas.append("=" * 82)
    linhas.append(f"Gerado em: {resultado.get('data')}")
    linhas.append(f"Concursos testados: {resultado.get('passos')} | Janela: {resultado.get('janela')} | Jogos: {resultado.get('qtd_jogos')}")
    linhas.append(f"Seed: {_descricao_seed()}")
    linhas.append("")
    linhas.append("1) RANKING CIENTÍFICO DE CONFIGURAÇÕES")
    linhas.append("-" * 82)
    for i, r in enumerate(resultado.get("ranking_configuracoes", []), start=1):
        linhas.append(
            f"{i}. {r.get('nome')} | G={r.get('geracoes')} | P={r.get('pop_size')} | "
            f"score={r.get('score_cientifico')} | média melhor={r.get('media_melhor')} | "
            f"máx={r.get('max_melhor')} | 11+={r.get('pct_11_mais')}% | 12+={r.get('pct_12_mais')}% | 13+={r.get('pct_13_mais')}%"
        )
        linhas.append(f"   distribuição: {r.get('distribuicao')}")
    linhas.append("")
    linhas.append("2) CAMPEONATO ENTRE MODELOS")
    linhas.append("-" * 82)
    for i, r in enumerate(resultado.get("ranking_modelos", []), start=1):
        linhas.append(
            f"{i}. {r.get('nome')} | score={r.get('score_cientifico')} | "
            f"média melhor={r.get('media_melhor')} | máx={r.get('max_melhor')} | "
            f"11+={r.get('pct_11_mais')}% | 12+={r.get('pct_12_mais')}% | 13+={r.get('pct_13_mais')}%"
        )
    rec = resultado.get("recomendacao") or {}
    linhas.append("")
    linhas.append("3) AUTOCALIBRAÇÃO RECOMENDADA")
    linhas.append("-" * 82)
    linhas.append(f"Estratégia base: {rec.get('estrategia_base')}")
    linhas.append(f"Gerações: {rec.get('geracoes')} | População: {rec.get('pop_size')} | Janela: {rec.get('janela')}")
    linhas.append(f"Modelo campeão: {rec.get('modelo_campeao')}")
    linhas.append("")
    linhas.append("4) BANCO DE CONHECIMENTO")
    linhas.append("-" * 82)
    linhas.append(f"Arquivo atualizado: {resultado.get('arquivo_conhecimento')}")
    linhas.append("")
    linhas.append("Observação: este relatório mede desempenho em concursos passados. Não é previsão nem garantia de prêmio.")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    return caminho


# =========================================================
# RELATÓRIOS
# =========================================================
def avaliar_jogos(jogos: list, analise: dict, pesos: dict) -> list[dict]:
    linhas = []
    for i, jogo in enumerate(jogos, start=1):
        cobertura = analise.get("cobertura_global") or {}
        perfis = {p.get("jogo"): p.get("perfil") for p in cobertura.get("perfis_taticos", [])}
        estrutura = analisar_estrutura_jogo(jogo)
        linhas.append({
            "Jogo": i,
            "Dezenas": formatar_jogo(jogo),
            "Pares": contar_pares(jogo),
            "Ímpares": 15 - contar_pares(jogo),
            "Soma": soma_jogo(jogo),
            "Perfil": perfis.get(i, ""),
            "Estrutura": estrutura.get("classificacao", ""),
            "Score Estrutural": estrutura.get("score_estrutural", 0),
            "Score": round(score_jogo(jogo, pesos, analise, [j for j in jogos if j != jogo], analise.get("estrategia")), 3),
        })
    return linhas


def gerar_relatorio_texto(jogos: list, analise: dict, pesos: dict, info_csv=None, info_backtest=None) -> str:
    linhas = []
    linhas.append("ROBÔ LOTOFÁCIL ULTRA")
    linhas.append("=" * 72)
    if info_csv:
        linhas.append(f"CSV: {info_csv}")
    linhas.append(f"Janela usada na análise: {len(analise['hist_usado'])} concursos")
    linhas.append(f"Média de pares: {analise['pares_media']:.2f}")
    linhas.append(f"Média de soma: {analise['soma_media']:.2f}")
    linhas.append(f"Média de interseção entre concursos consecutivos: {analise['intersecao_media']:.2f}")
    estrategia = analise.get("estrategia") or {}
    if estrategia:
        linhas.append("")
        linhas.append("MOTOR ESTRATÉGICO INTELIGENTE")
        linhas.append("-" * 72)
        linhas.append(f"Modo escolhido: {estrategia.get('modo', 'equilibrado').upper()}")
        linhas.append(f"Índice de confiança: {estrategia.get('indice_confianca', 0):.3f}")
        linhas.append(f"Estabilidade: {estrategia.get('estabilidade', 0):.3f} | Concentração: {estrategia.get('concentracao', 0):.3f}")
        linhas.append(f"Diversidade: {estrategia.get('diversidade', 0):.3f} | Mutação: {estrategia.get('taxa_mutacao', 0):.3f}")
        if estrategia.get('ciclo_principal'):
            linhas.append(f"Ciclo detectado: {estrategia.get('ciclo_principal', '').upper()} — {estrategia.get('ciclo_descricao', '')}")
    aprendizado = analise.get("aprendizado") or estrategia.get("aprendizado_permanente") or {}
    if aprendizado:
        linhas.append("")
        linhas.append("APRENDIZADO PERMANENTE")
        linhas.append("-" * 72)
        linhas.append(aprendizado.get("resumo", "Sem memória de desempenho."))
        if aprendizado.get("tem_memoria"):
            linhas.append(f"Ajuste diversidade: {aprendizado.get('ajuste_diversidade', 0):+.3f} | Mutação: {aprendizado.get('ajuste_mutacao', 0):+.3f} | Elite: {aprendizado.get('ajuste_elite', 0):+.3f}")
    linhas.append("")
    ensemble = analise.get("ensemble") or {}
    if ensemble:
        linhas.append("Ensemble Multi-IA Adaptativo:")
        conf = ensemble.get("confianca_modelos", {})
        linhas.append(", ".join(f"{nome}={peso:.2f}" for nome, peso in conf.items()))
        consenso = ensemble.get("consenso") or {}
        if consenso.get("top_consenso"):
            linhas.append("Top consenso dos modelos: " + ", ".join(f"{n:02d}({v:.2f})" for n, v in consenso.get("top_consenso", [])[:10]))
        if ensemble.get("memoria_ranking", {}).get("tem_ranking"):
            linhas.append("Memória do ranking: " + ensemble.get("memoria_ranking", {}).get("resumo", ""))
        linhas.append("")
    cobertura = analise.get("cobertura_global") or {}
    if cobertura:
        linhas.append("COBERTURA INTELIGENTE GLOBAL")
        linhas.append("-" * 72)
        linhas.append(f"Média de sobreposição entre jogos: {cobertura.get('media_sobreposicao', 0)}")
        linhas.append(f"Sobreposição mínima/máxima: {cobertura.get('min_sobreposicao', 0)} / {cobertura.get('max_sobreposicao', 0)}")
        linhas.append(f"Média de soma do pacote: {cobertura.get('media_soma', 0)} | Média de pares: {cobertura.get('media_pares', 0)}")
        mais = cobertura.get('dezenas_mais_cobertas', [])
        menos = cobertura.get('dezenas_menos_cobertas', [])
        if mais:
            linhas.append("Dezenas mais cobertas: " + ", ".join(f"{n:02d}({q})" for n, q in mais))
        if menos:
            linhas.append("Dezenas menos cobertas: " + ", ".join(f"{n:02d}({q})" for n, q in menos))
        ref = cobertura.get("refinamento_matematico") or resumo_estrutural_pacote(jogos)
        if ref:
            linhas.append("")
            linhas.append("REFINAMENTO MATEMÁTICO ESTRUTURAL")
            linhas.append("-" * 72)
            linhas.append(f"Score estrutural médio: {ref.get('score_estrutural_medio', 0)}")
            linhas.append(f"Entropia média 5x5: {ref.get('entropia_media', 0)}")
            linhas.append(f"Jogos com estrutura forte/boa: {ref.get('jogos_estrutura_forte_ou_boa', 0)}")
            linhas.append(f"Jogos com estrutura fraca: {ref.get('jogos_estrutura_fraca', 0)}")
            cls = ref.get('classificacoes', {})
            if cls:
                linhas.append("Classificações: " + ", ".join(f"{k}={v}" for k, v in cls.items()))
        linhas.append("")
    top = sorted(pesos.items(), key=lambda x: x[1], reverse=True)[:10]
    linhas.append("Top 10 dezenas por peso final do ensemble:")
    linhas.append(", ".join(f"{n:02d} ({p:.4f})" for n, p in top))
    linhas.append("")
    linhas.append("JOGOS GERADOS")
    linhas.append("-" * 72)
    for row in avaliar_jogos(jogos, analise, pesos):
        linhas.append(
            f"Jogo {row['Jogo']:02d}: {row['Dezenas']} | "
            f"Pares={row['Pares']} | Ímpares={row['Ímpares']} | "
            f"Soma={row['Soma']} | Perfil={row.get('Perfil', '')} | Score={row['Score']}"
        )
    if info_backtest:
        linhas.append("")
        linhas.append("BACKTEST")
        linhas.append("-" * 72)
        linhas.append(f"Passos: {info_backtest['passos']}")
        linhas.append(f"Média do melhor jogo: {info_backtest['media_melhor']}")
        linhas.append(f"Melhor acerto observado: {info_backtest['max_melhor']}")
        linhas.append(f"Distribuição: {info_backtest['distribuicao']}")
    linhas.append("")
    linhas.append("Aviso: o sistema faz análise estatística e combinatória. Não há garantia de premiação.")
    return "\n".join(linhas)




# =========================================================
# DASHBOARD ANALÍTICO PROFISSIONAL
# =========================================================
def barra_ascii(valor: float, maximo: float, largura: int = 28, simbolo: str = "█") -> str:
    try:
        valor = float(valor)
        maximo = float(maximo) if maximo else 1.0
        qtd = int(round((valor / maximo) * largura)) if maximo > 0 else 0
        qtd = max(0, min(largura, qtd))
        return simbolo * qtd + " " * (largura - qtd)
    except Exception:
        return " " * largura


def matriz_5x5_dezenas(valores_por_dezena: dict) -> str:
    linhas = []
    for lin in range(5):
        partes = []
        for col in range(5):
            n = lin * 5 + col + 1
            partes.append(f"{n:02d}:{valores_por_dezena.get(n, 0):>3}")
        linhas.append("   ".join(partes))
    return "\n".join(linhas)


def gerar_dashboard_analitico(jogos: list, analise: dict, pesos: dict, memoria: dict | None = None, info_backtest: dict | None = None) -> str:
    memoria = memoria if memoria is not None else carregar_memoria_aprendizado()
    estrategia = analise.get("estrategia", {}) if analise else {}
    ensemble = analise.get("ensemble", {}) if analise else {}
    cobertura = analise.get("cobertura_global", {}) if analise else {}
    aprendizado = analise.get("aprendizado", {}) if analise else {}

    linhas = []
    linhas.append("DASHBOARD ANALÍTICO PROFISSIONAL - ROBÔ LOTOFÁCIL")
    linhas.append("=" * 78)
    linhas.append(datetime.now().strftime("Gerado em: %d/%m/%Y %H:%M:%S"))
    linhas.append("")

    linhas.append("1) PAINEL EXECUTIVO")
    linhas.append("-" * 78)
    linhas.append(f"Jogos no pacote: {len(jogos) if jogos else 0}")
    linhas.append(f"Janela analisada: {len(analise.get('hist_usado', [])) if analise else 0} concursos")
    linhas.append(f"Modo estratégico: {estrategia.get('modo', 'n/d').upper()}")
    linhas.append(f"Índice de confiança: {estrategia.get('indice_confianca', 0):.3f}")
    linhas.append(f"Diversidade alvo: {estrategia.get('diversidade', 0):.3f}")
    linhas.append(f"Taxa de mutação: {estrategia.get('taxa_mutacao', 0):.3f}")
    linhas.append(f"Elite genética: {estrategia.get('elite_fracao', 0):.3f}")
    if estrategia.get("ciclo_principal"):
        linhas.append(f"Ciclo histórico: {estrategia.get('ciclo_principal', '').upper()} | {estrategia.get('ciclo_descricao', '')}")
    if ensemble.get("consenso", {}).get("top_consenso"):
        linhas.append("Top consenso IA: " + ", ".join(f"{n:02d}({v:.2f})" for n, v in ensemble.get("consenso", {}).get("top_consenso", [])[:10]))
    if ensemble.get("memoria_ranking", {}).get("tem_ranking"):
        linhas.append("Memória ranking: " + ensemble.get("memoria_ranking", {}).get("resumo", ""))
    linhas.append("")

    linhas.append("2) MAPA 5x5 DE COBERTURA DAS DEZENAS")
    linhas.append("-" * 78)
    contagem = cobertura.get("contagem_dezenas", {})
    if not contagem and jogos:
        contagem = dict(Counter(n for j in jogos for n in j))
    linhas.append(matriz_5x5_dezenas({int(k): int(v) for k, v in contagem.items()}))
    linhas.append("")
    if contagem:
        max_c = max(contagem.values()) if contagem else 1
        linhas.append("Ranking de exposição das dezenas:")
        for n, q in sorted(((int(k), int(v)) for k, v in contagem.items()), key=lambda x: (-x[1], x[0])):
            linhas.append(f"{n:02d} |{barra_ascii(q, max_c, 24)}| {q}")
    linhas.append("")

    linhas.append("3) PESOS FINAIS DO ENSEMBLE")
    linhas.append("-" * 78)
    if pesos:
        max_p = max(pesos.values()) if pesos else 1
        for n, p in sorted(pesos.items(), key=lambda x: x[1], reverse=True):
            linhas.append(f"{n:02d} |{barra_ascii(p, max_p, 24)}| {p:.5f}")
    linhas.append("")

    linhas.append("4) CONFIANÇA DOS MODELOS")
    linhas.append("-" * 78)
    conf = ensemble.get("confianca_modelos", {})
    if conf:
        max_conf = max(conf.values()) if conf else 1
        for nome, valor in sorted(conf.items(), key=lambda x: x[1], reverse=True):
            linhas.append(f"{nome:<16} |{barra_ascii(valor, max_conf, 24)}| {valor:.3f}")
    else:
        linhas.append("Sem dados do ensemble nesta geração.")
    linhas.append("")

    linhas.append("5) QUALIDADE DA COBERTURA GLOBAL")
    linhas.append("-" * 78)
    if cobertura:
        linhas.append(f"Sobreposição média: {cobertura.get('media_sobreposicao', 0)}")
        linhas.append(f"Sobreposição mínima/máxima: {cobertura.get('min_sobreposicao', 0)} / {cobertura.get('max_sobreposicao', 0)}")
        linhas.append(f"Média de soma: {cobertura.get('media_soma', 0)}")
        linhas.append(f"Média de pares: {cobertura.get('media_pares', 0)}")
        linhas.append("Mais cobertas: " + ", ".join(f"{n:02d}({q})" for n, q in cobertura.get('dezenas_mais_cobertas', [])))
        linhas.append("Menos cobertas: " + ", ".join(f"{n:02d}({q})" for n, q in cobertura.get('dezenas_menos_cobertas', [])))
    else:
        linhas.append("Gere jogos para calcular a cobertura global.")
    linhas.append("")

    linhas.append("6) PERFIS TÁTICOS DOS JOGOS")
    linhas.append("-" * 78)
    perfis = cobertura.get("perfis_taticos", []) if cobertura else []
    if perfis:
        for p in perfis:
            linhas.append(f"Jogo {p.get('jogo', 0):02d}: {p.get('perfil', '')} | {p.get('dezenas', '')}")
    elif jogos:
        for i, jogo in enumerate(jogos, 1):
            linhas.append(f"Jogo {i:02d}: {formatar_jogo(jogo)}")
    else:
        linhas.append("Nenhum jogo gerado ainda.")
    linhas.append("")

    linhas.append("7) APRENDIZADO PERMANENTE")
    linhas.append("-" * 78)
    linhas.append(aprendizado.get("resumo") or gerar_resumo_aprendizado(memoria))
    registros = memoria.get("registros", []) if isinstance(memoria, dict) else []
    if registros:
        ultimos = registros[-10:]
        linhas.append("")
        linhas.append("Últimos registros de desempenho:")
        for r in ultimos:
            linhas.append(
                f"{r.get('data', '')} | melhor={r.get('melhor_acerto', '')} | média={r.get('media_acertos', '')} | modo={r.get('modo', '')}"
            )
    linhas.append("")

    if info_backtest:
        linhas.append("8) BACKTEST")
        linhas.append("-" * 78)
        linhas.append(f"Passos: {info_backtest.get('passos', 0)}")
        linhas.append(f"Média do melhor jogo: {info_backtest.get('media_melhor', 0)}")
        linhas.append(f"Melhor acerto observado: {info_backtest.get('max_melhor', 0)}")
        linhas.append(f"Distribuição: {info_backtest.get('distribuicao', {})}")
        linhas.append("")

    linhas.append("Leitura técnica: este painel mede robustez, cobertura e adaptação. Não representa garantia de premiação.")

    # ── 9) VALOR ESPERADO — IMPOPULARIDADE ──────────────────────────────
    if jogos:
        linhas.append("")
        linhas.append("9) VALOR ESPERADO — IMPOPULARIDADE DO PACOTE")
        linhas.append("-" * 78)
        estrategia_imp = (analise or {}).get("estrategia", {})
        peso_imp = float((estrategia_imp or {}).get("peso_impopularidade", 0.30))
        hist_rec = (analise or {}).get("hist_usado", [])
        resumo_imp = resumo_impopularidade_pacote(jogos, hist_rec, peso=peso_imp)
        linhas.append(f"Peso impopularidade ativo: {peso_imp:.2f} {'(desligado)' if peso_imp == 0 else ''}")
        linhas.append(f"Score médio impopularidade: {resumo_imp['media_score']:+.4f}")
        linhas.append(f"  Min/Max: {resumo_imp['min_score']:+.4f} / {resumo_imp['max_score']:+.4f}")
        linhas.append(f"  Jogos com score positivo (impopulares): {resumo_imp['jogos_acima_zero']}/{len(jogos)}")
        linhas.append(f"  Fração média de datas magnéticas (1-12,15,20,25): {resumo_imp['media_datas']:.2%}  (esperado aleatório: 68%)")
        linhas.append(f"  Fração média terminações redondas (5,10,15,20,25): {resumo_imp['media_redondas']:.2%}  (esperado aleatório: 20%)")
        linhas.append(f"  Sequências longas (≥4 consecutivos): {resumo_imp['media_seq_longas']:.2%}  (humanos evitam: bônus)")
        linhas.append(f"  Padrão geométrico (linha/col/diag): {resumo_imp['media_padrao_geo']:.2%}  (≤60% é neutro)")
        linhas.append(f"  Irregularidade de distribuição: {resumo_imp['media_irregularidade']:.2%}  (humanos são uniformes demais)")
        linhas.append(f"→ {resumo_imp['interpretacao']}")

    return "\n".join(linhas)




# =========================================================
# SIMULADOR / AUDITOR DE QUALIDADE DO PACOTE (UPGRADE V10.1)
# =========================================================
def auditar_pacote_jogos(jogos: list, analise: dict | None = None, qtd_simulacoes: int = 1000) -> dict:
    """
    Auditor técnico do pacote gerado.
    Não prevê o próximo sorteio: simula sorteios artificiais para medir robustez,
    cobertura, diversidade e estrutura matemática dos jogos antes da conferência real.
    """
    jogos = [sorted(set(int(n) for n in jogo)) for jogo in (jogos or [])]
    jogos = [j for j in jogos if len(j) == _cfg.TAMANHO_JOGO and all(1 <= n <= 25 for n in j)]
    if not jogos:
        raise ValueError("Nenhum jogo válido disponível para simular.")

    qtd_simulacoes = int(limitar(int(qtd_simulacoes or 1000), 100, 10000))

    # 1) Cobertura das 25 dezenas
    cobertura = Counter(n for jogo in jogos for n in jogo)
    dezenas_cobertas = sum(1 for n in NUMEROS if cobertura.get(n, 0) > 0)
    min_cobertura = min(cobertura.get(n, 0) for n in NUMEROS)
    max_cobertura = max(cobertura.get(n, 0) for n in NUMEROS)
    media_cobertura = mean([cobertura.get(n, 0) for n in NUMEROS])
    desvio_cobertura = math.sqrt(mean([(cobertura.get(n, 0) - media_cobertura) ** 2 for n in NUMEROS]))

    # 2) Diversidade entre jogos
    inters = []
    for i in range(len(jogos)):
        for j in range(i + 1, len(jogos)):
            inters.append(intersecao(jogos[i], jogos[j]))
    media_inter = mean(inters) if inters else 15.0
    min_inter = min(inters) if inters else 15
    max_inter = max(inters) if inters else 15

    # 3) Estrutura matemática do pacote
    estrutura = resumo_estrutural_pacote(jogos)
    score_estrutural_medio = float(estrutura.get("score_estrutural_medio", 0) or 0)

    # 4) Simulação artificial curta
    dist_melhor = Counter()
    dist_total = Counter()
    melhores = []
    medias = []
    eventos_11_mais = 0
    eventos_12_mais = 0
    eventos_13_mais = 0

    for _ in range(qtd_simulacoes):
        sorteio = set(random.sample(NUMEROS, _cfg.TAMANHO_JOGO))
        acertos = [len(set(jogo) & sorteio) for jogo in jogos]
        melhor = max(acertos)
        melhores.append(melhor)
        medias.append(sum(acertos) / len(acertos))
        dist_melhor[melhor] += 1
        dist_total.update(acertos)
        if melhor >= 11:
            eventos_11_mais += 1
        if melhor >= 12:
            eventos_12_mais += 1
        if melhor >= 13:
            eventos_13_mais += 1

    media_melhor = mean(melhores) if melhores else 0.0
    media_geral = mean(medias) if medias else 0.0

    # 5) Notas técnicas — todas em escala 0..10
    nota_estrutura = limitar((score_estrutural_medio + 1.0) / 6.0 * 10.0, 0, 10)

    # Interseção média saudável para pacotes de Lotofácil: nem idênticos demais, nem dispersos sem critério.
    nota_diversidade = 10.0 - abs(media_inter - 9.7) * 1.35
    if max_inter >= 14:
        nota_diversidade -= 1.5
    if media_inter > 12.2:
        nota_diversidade -= 1.2
    nota_diversidade = limitar(nota_diversidade, 0, 10)

    nota_cobertura = 6.0 + (dezenas_cobertas - 22) * 0.8 - desvio_cobertura * 0.55
    if dezenas_cobertas == 25:
        nota_cobertura += 1.0
    if min_cobertura <= 1 and len(jogos) >= 20:
        nota_cobertura -= 0.8
    nota_cobertura = limitar(nota_cobertura, 0, 10)

    taxa_11 = eventos_11_mais / qtd_simulacoes
    taxa_12 = eventos_12_mais / qtd_simulacoes
    taxa_13 = eventos_13_mais / qtd_simulacoes
    nota_simulacao = limitar(4.0 + taxa_11 * 8.0 + taxa_12 * 10.0 + taxa_13 * 12.0 + (media_melhor - 10.0) * 1.4, 0, 10)

    nota_final = (
        0.28 * nota_estrutura
        + 0.27 * nota_diversidade
        + 0.22 * nota_cobertura
        + 0.23 * nota_simulacao
    )

    if nota_final >= 8.0:
        classificacao = "APROVADO FORTE"
        recomendacao = "Pacote bem estruturado. Pode ser mantido para conferência real."
    elif nota_final >= 6.7:
        classificacao = "APROVADO"
        recomendacao = "Pacote aceitável. Vale conferir, sem necessidade de regerar."
    elif nota_final >= 5.4:
        classificacao = "REGULAR"
        recomendacao = "Pacote mediano. Se quiser buscar mais qualidade, gere novamente em modo laboratório."
    else:
        classificacao = "REFINAR"
        recomendacao = "Pacote fraco para os critérios internos. Recomenda-se gerar novamente."

    return {
        "qtd_jogos": len(jogos),
        "qtd_simulacoes": qtd_simulacoes,
        "nota_final": round(nota_final, 2),
        "classificacao": classificacao,
        "recomendacao": recomendacao,
        "nota_estrutura": round(nota_estrutura, 2),
        "nota_diversidade": round(nota_diversidade, 2),
        "nota_cobertura": round(nota_cobertura, 2),
        "nota_simulacao": round(nota_simulacao, 2),
        "dezenas_cobertas": dezenas_cobertas,
        "min_cobertura": min_cobertura,
        "max_cobertura": max_cobertura,
        "desvio_cobertura": round(desvio_cobertura, 3),
        "media_intersecao": round(media_inter, 3),
        "min_intersecao": min_inter,
        "max_intersecao": max_inter,
        "estrutura": estrutura,
        "media_melhor_simulada": round(media_melhor, 3),
        "media_geral_simulada": round(media_geral, 3),
        "taxa_11_mais": round(taxa_11 * 100, 2),
        "taxa_12_mais": round(taxa_12 * 100, 2),
        "taxa_13_mais": round(taxa_13 * 100, 2),
        "distribuicao_melhor": dict(sorted(dist_melhor.items())),
        "distribuicao_total": dict(sorted(dist_total.items())),
        "dezenas_mais_cobertas": cobertura.most_common(8),
        "dezenas_menos_cobertas": sorted([(n, cobertura.get(n, 0)) for n in NUMEROS], key=lambda x: (x[1], x[0]))[:8],
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }


def gerar_relatorio_simulador_pacote(resultado: dict) -> str:
    linhas = []
    linhas.append("SIMULADOR / AUDITOR DE QUALIDADE DO PACOTE")
    linhas.append("=" * 78)
    linhas.append(f"Data: {resultado.get('gerado_em', '')}")
    linhas.append(f"Jogos analisados: {resultado.get('qtd_jogos', 0)}")
    linhas.append(f"Sorteios simulados: {resultado.get('qtd_simulacoes', 0)}")
    linhas.append("")
    linhas.append(f"NOTA FINAL: {resultado.get('nota_final', 0):.2f} / 10")
    linhas.append(f"CLASSIFICAÇÃO: {resultado.get('classificacao', '')}")
    linhas.append(f"RECOMENDAÇÃO: {resultado.get('recomendacao', '')}")
    linhas.append("")
    linhas.append("Notas por critério:")
    linhas.append(f"- Estrutura matemática: {resultado.get('nota_estrutura', 0):.2f}/10")
    linhas.append(f"- Diversidade entre jogos: {resultado.get('nota_diversidade', 0):.2f}/10")
    linhas.append(f"- Cobertura das 25 dezenas: {resultado.get('nota_cobertura', 0):.2f}/10")
    linhas.append(f"- Simulação artificial: {resultado.get('nota_simulacao', 0):.2f}/10")
    linhas.append("")
    linhas.append("Cobertura:")
    linhas.append(f"- Dezenas cobertas: {resultado.get('dezenas_cobertas', 0)} de 25")
    linhas.append(f"- Menor cobertura por dezena: {resultado.get('min_cobertura', 0)}")
    linhas.append(f"- Maior cobertura por dezena: {resultado.get('max_cobertura', 0)}")
    linhas.append(f"- Desvio de cobertura: {resultado.get('desvio_cobertura', 0)}")
    linhas.append("- Mais cobertas: " + ", ".join(f"{n:02d}({q})" for n, q in resultado.get('dezenas_mais_cobertas', [])))
    linhas.append("- Menos cobertas: " + ", ".join(f"{n:02d}({q})" for n, q in resultado.get('dezenas_menos_cobertas', [])))
    linhas.append("")
    linhas.append("Diversidade:")
    linhas.append(f"- Sobreposição média entre jogos: {resultado.get('media_intersecao', 0)}")
    linhas.append(f"- Sobreposição mínima/máxima: {resultado.get('min_intersecao', 0)} / {resultado.get('max_intersecao', 0)}")
    linhas.append("")
    linhas.append("Simulação artificial:")
    linhas.append(f"- Média do melhor jogo por simulação: {resultado.get('media_melhor_simulada', 0)}")
    linhas.append(f"- Média geral dos jogos: {resultado.get('media_geral_simulada', 0)}")
    linhas.append(f"- Pacotes com pelo menos 11 pontos: {resultado.get('taxa_11_mais', 0)}%")
    linhas.append(f"- Pacotes com pelo menos 12 pontos: {resultado.get('taxa_12_mais', 0)}%")
    linhas.append(f"- Pacotes com pelo menos 13 pontos: {resultado.get('taxa_13_mais', 0)}%")
    linhas.append(f"- Distribuição do melhor acerto: {resultado.get('distribuicao_melhor', {})}")
    linhas.append("")
    est = resultado.get("estrutura") or {}
    if est:
        linhas.append("Estrutura matemática:")
        linhas.append(f"- Score estrutural médio: {est.get('score_estrutural_medio', 0)}")
        linhas.append(f"- Entropia média: {est.get('entropia_media', 0)}")
        linhas.append(f"- Jogos fortes/boas: {est.get('jogos_estrutura_forte_ou_boa', 0)}")
        linhas.append(f"- Jogos fracos: {est.get('jogos_estrutura_fraca', 0)}")
        linhas.append(f"- Classificações: {est.get('classificacoes', {})}")
        linhas.append("")
    linhas.append("Observação: este simulador mede qualidade estrutural do pacote. Não é previsão nem garantia de acerto.")
    return "\n".join(linhas)


# =========================================================
# INTERFACE TKINTER
# =========================================================
