"""
lotofacil_pkg/aprendizado.py
-----------------------------
Memória adaptativa permanente: registra resultados reais/simulados,
calcula ajustes de diversidade/mutação/elite e bônus por modelo.
"""
import threading
from collections import Counter
from datetime import datetime
from statistics import mean

from .config import ARQUIVO_APRENDIZADO, NUMEROS
from .utils import (ler_json, salvar_json, normalizar_scores, limitar, garantir_estrutura_pastas,
    intersecao, contar_pares, soma_jogo, formatar_jogo, gerar_timestamp_arquivo,
)
# V21.1-A: espelhamento no SQLite (falha silenciosa)
try:
    from .v21_0_sqlite import db_registrar_aprendizado as _db_reg_apr
except Exception:
    def _db_reg_apr(_r): pass

# Protege o ciclo load -> append -> save da memória de aprendizado
# (ARQUIVO_APRENDIZADO). Sem isso, duas chamadas concorrentes (ex.: a
# thread do Aprendizado Contínuo registrando um passo enquanto o usuário
# clica "Registrar resultado real" na mesma janela) liam o arquivo antes
# uma da outra salvar, e a última a salvar sobrescrevia a lista inteira
# com sua versão desatualizada -- perdendo o registro da outra em
# silêncio (lost update).
# RLock (não Lock simples) porque registrar_resultado_simulado_aprendizado()
# chama registrar_resultado_aprendizado() por dentro -- ambas precisam do
# mesmo lock cobrindo a operação inteira como uma unidade atômica, e um
# Lock comum causaria deadlock nessa chamada aninhada pela mesma thread.
_LOCK_MEMORIA_APRENDIZADO = threading.RLock()


def carregar_memoria_aprendizado(caminho: str = ARQUIVO_APRENDIZADO) -> dict:
    memoria = ler_json(caminho, default={
        "versao": "1.0",
        "registros": [],
        "modelos": {},
        "estrategias": {},
        "ajustes": {},
    })
    memoria.setdefault("registros", [])
    memoria.setdefault("modelos", {})
    memoria.setdefault("estrategias", {})
    memoria.setdefault("ajustes", {})
    return memoria


def salvar_memoria_aprendizado(memoria: dict, caminho: str = ARQUIVO_APRENDIZADO) -> None:
    garantir_estrutura_pastas()
    memoria["atualizado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    salvar_json(caminho, memoria)



def calcular_memoria_ranking(registros: list) -> dict:
    """
    Mede se o ranking final da IA está realmente colocando dezenas sorteadas
    nas primeiras posições. Usa registros reais/simulados já gravados.
    """
    regs = [r for r in (registros or []) if r.get("ranking_ia") and r.get("resultado_real")]
    regs = regs[-250:]
    if not regs:
        return {
            "tem_ranking": False,
            "resumo": "Memória de ranking ainda sem registros suficientes.",
            "fator_concentracao_top": 0.0,
        }

    top5, top10, top15 = [], [], []
    pos_acertos = Counter()
    pos_total = Counter()
    for reg in regs:
        ranking = [int(n) for n in reg.get("ranking_ia", []) if str(n).strip().isdigit()]
        resultado = set(int(n) for n in reg.get("resultado_real", []))
        if not ranking or len(resultado) != 15:
            continue
        top5.append(len(set(ranking[:5]) & resultado))
        top10.append(len(set(ranking[:10]) & resultado))
        top15.append(len(set(ranking[:15]) & resultado))
        for pos, dezena in enumerate(ranking[:25], start=1):
            pos_total[pos] += 1
            if dezena in resultado:
                pos_acertos[pos] += 1

    if not top15:
        return {
            "tem_ranking": False,
            "resumo": "Memória de ranking ainda sem registros suficientes.",
            "fator_concentracao_top": 0.0,
        }

    media_top5 = mean(top5)
    media_top10 = mean(top10)
    media_top15 = mean(top15)

    # Em uma seleção aleatória, espera-se aprox. 3 acertos no top5, 6 no top10 e 9 no top15.
    eficiencia_top15 = (media_top15 - 9.0) / 3.0
    fator = limitar(eficiencia_top15 * 0.10, -0.08, 0.10)

    taxa_posicoes = {
        pos: round(pos_acertos[pos] / max(1, pos_total[pos]), 3)
        for pos in range(1, 26)
        if pos_total[pos] > 0
    }

    return {
        "tem_ranking": True,
        "total_registros_ranking": len(top15),
        "media_top5": round(media_top5, 3),
        "media_top10": round(media_top10, 3),
        "media_top15": round(media_top15, 3),
        "fator_concentracao_top": round(fator, 4),
        "taxa_posicoes": taxa_posicoes,
        "resumo": f"Ranking IA: Top5={media_top5:.2f}, Top10={media_top10:.2f}, Top15={media_top15:.2f} em {len(top15)} registro(s).",
    }


def aplicar_memoria_de_ranking_aos_pesos(pesos: dict, memoria_ranking: dict | None = None) -> dict:
    """
    Ajusta suavemente a concentração do ranking final.
    Se o Top15 vem performando bem, concentra um pouco mais nos primeiros colocados.
    Se vem performando mal, achata o ranking e preserva diversidade.
    """
    pesos = normalizar_scores(pesos, piso=0.002)
    if not memoria_ranking or not memoria_ranking.get("tem_ranking"):
        return pesos
    fator = float(memoria_ranking.get("fator_concentracao_top", 0.0) or 0.0)
    if abs(fator) < 0.001:
        return pesos
    ranking = sorted(pesos.items(), key=lambda x: x[1], reverse=True)
    ajustados = {}
    for pos, (n, p) in enumerate(ranking, start=1):
        if pos <= 5:
            mult = 1.0 + 1.8 * fator
        elif pos <= 10:
            mult = 1.0 + 1.2 * fator
        elif pos <= 15:
            mult = 1.0 + 0.7 * fator
        else:
            mult = 1.0 - 0.5 * fator
        ajustados[n] = max(0.001, p * mult)
    return normalizar_scores(ajustados, piso=0.002)

def calcular_bonus_aprendizado(memoria: dict | None = None, incluir_simulados: bool = False) -> dict:
    """
    Lê a memória do robô e devolve pequenos ajustes seguros.
    Esses ajustes não prometem previsão; apenas calibram diversidade, mutação e peso dos modelos
    conforme o desempenho registrado pelo próprio usuário.

    Por padrão (incluir_simulados=False) ignora registros marcados como
    `treino_historico` (gravados por registrar_resultado_simulado_aprendizado,
    usados pelo botão Aprender Contínuo) -- uma sessão de treino simulado
    percorre dezenas/centenas de concursos históricos numa tacada só e podia
    facilmente expulsar os registros REAIS do usuário da janela de 200 usada
    aqui, calibrando a geração real com base em simulação em vez de
    desempenho de fato registrado pelo usuário (achado de varredura de
    código, 2026-08-31).
    """
    memoria = memoria or carregar_memoria_aprendizado()
    todos_registros = memoria.get("registros", [])
    if not incluir_simulados:
        todos_registros = [r for r in todos_registros if not r.get("treino_historico")]
    registros = todos_registros[-200:]
    if not registros:
        return {
            "tem_memoria": False,
            "bonus_modelos": {},
            "ajuste_diversidade": 0.0,
            "ajuste_mutacao": 0.0,
            "ajuste_elite": 0.0,
            "resumo": "Sem registros suficientes de desempenho.",
        }

    # Desempenho por modelo, ponderado pelos pesos usados no ensemble no dia registrado.
    modelo_score = Counter()
    modelo_peso_total = Counter()
    estrategia_score = Counter()
    estrategia_qtd = Counter()
    melhores = []

    for reg in registros:
        melhor = float(reg.get("melhor_acerto", 0) or 0)
        media = float(reg.get("media_acertos", 0) or 0)
        eficiencia = limitar((0.70 * melhor + 0.30 * media - 10.0) / 4.0, -0.6, 1.0)
        melhores.append(melhor)
        modo = reg.get("modo", "equilibrado")
        estrategia_score[modo] += eficiencia
        estrategia_qtd[modo] += 1
        for nome, peso in (reg.get("confianca_modelos") or {}).items():
            try:
                p = float(peso)
            except Exception:
                p = 0.0
            modelo_score[nome] += eficiencia * p
            modelo_peso_total[nome] += abs(p)

    bonus_modelos = {}
    for nome in set(modelo_score) | set(modelo_peso_total):
        base = modelo_score[nome] / max(1e-9, modelo_peso_total[nome])
        bonus_modelos[nome] = limitar(base * 0.10, -0.06, 0.08)

    media_melhor = mean(melhores) if melhores else 0.0
    # Se o melhor acerto médio estiver baixo, abre mais diversidade; se estiver melhor, preserva elite.
    ajuste_div = limitar((12.0 - media_melhor) * 0.025, -0.04, 0.08)
    ajuste_mut = limitar((11.5 - media_melhor) * 0.020, -0.04, 0.07)
    ajuste_elite = limitar((media_melhor - 11.8) * 0.015, -0.03, 0.04)

    melhor_modo = None
    if estrategia_qtd:
        melhor_modo = max(estrategia_qtd, key=lambda m: estrategia_score[m] / max(1, estrategia_qtd[m]))

    memoria_ranking = calcular_memoria_ranking(registros)

    return {
        "tem_memoria": True,
        "bonus_modelos": bonus_modelos,
        "ajuste_diversidade": round(ajuste_div, 4),
        "ajuste_mutacao": round(ajuste_mut, 4),
        "ajuste_elite": round(ajuste_elite, 4),
        "memoria_ranking": memoria_ranking,
        "media_melhor_registrada": round(media_melhor, 3),
        "melhor_modo": melhor_modo,
        "total_registros": len(registros),
        "resumo": f"Memória ativa com {len(registros)} registro(s); média do melhor acerto: {media_melhor:.2f}. {memoria_ranking.get('resumo', '')}",
    }


def aplicar_aprendizado_na_estrategia(estrategia: dict, aprendizado: dict) -> dict:
    if not estrategia or not aprendizado or not aprendizado.get("tem_memoria"):
        return estrategia
    e = dict(estrategia)
    e["diversidade"] = round(limitar(float(e.get("diversidade", 0.75)) + aprendizado.get("ajuste_diversidade", 0.0), 0.56, 0.94), 3)
    e["taxa_mutacao"] = round(limitar(float(e.get("taxa_mutacao", 0.35)) + aprendizado.get("ajuste_mutacao", 0.0), 0.20, 0.68), 3)
    e["elite_fracao"] = round(limitar(float(e.get("elite_fracao", 0.20)) + aprendizado.get("ajuste_elite", 0.0), 0.12, 0.34), 3)
    if e["diversidade"] >= 0.80:
        e["limite_intersecao"] = min(int(e.get("limite_intersecao", 12)), 11)
    e["aprendizado_permanente"] = aprendizado
    return e


def aplicar_aprendizado_nos_modelos(confianca_modelos: dict, aprendizado: dict) -> dict:
    pesos = dict(confianca_modelos or {})
    if not aprendizado or not aprendizado.get("tem_memoria"):
        return pesos
    bonus = {k:min(float(v)*0.98,0.25) for k,v in (aprendizado.get("bonus_modelos") or {}).items()}
    for nome, b in bonus.items():
        if nome in pesos:
            pesos[nome] = max(0.02, pesos[nome] + float(b))
    total = sum(pesos.values()) or 1.0
    return {k: v / total for k, v in pesos.items()}


def registrar_resultado_aprendizado(jogos: list, analise: dict, pesos: dict, resultado_real: list, caminho: str = ARQUIVO_APRENDIZADO) -> tuple[dict, dict]:
    """Salva desempenho real dos jogos após o usuário informar o resultado do concurso."""
    if not jogos:
        raise ValueError("Nenhum jogo gerado para registrar.")
    resultado = sorted(set(int(n) for n in resultado_real))
    if len(resultado) != 15 or any(n < 1 or n > 25 for n in resultado):
        raise ValueError("Informe exatamente 15 dezenas válidas entre 1 e 25.")

    acertos = [intersecao(j, resultado) for j in jogos]
    estrategia = analise.get("estrategia") or {}
    ensemble = analise.get("ensemble") or {}
    cobertura = analise.get("cobertura_global") or {}
    pares_pacote = [contar_pares(j) for j in jogos]
    somas_pacote = [soma_jogo(j) for j in jogos]

    registro = {
        "data_registro": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "resultado_real": resultado,
        "qtd_jogos": len(jogos),
        "melhor_acerto": max(acertos) if acertos else 0,
        "media_acertos": round(sum(acertos) / len(acertos), 3) if acertos else 0,
        "distribuicao_acertos": dict(sorted(Counter(acertos).items())),
        # pares_medios/soma_media: padrão do pacote entregue ao usuário,
        # usados por analisar_padroes_vencedores() (analise.py) para
        # recalibrar pesos com base nos jogos que mais acertaram — antes
        # dessas duas chaves não existirem aqui, a função sempre lia o
        # valor-padrão e o auto-ajuste nunca disparava (ver 2026-07-19 no
        # ARQUITETURA.md).
        "pares_medios": round(mean(pares_pacote), 2) if pares_pacote else 7.0,
        "soma_media": round(mean(somas_pacote), 2) if somas_pacote else 195.0,
        "modo": estrategia.get("modo", "equilibrado"),
        "indice_confianca": estrategia.get("indice_confianca", 0),
        "diversidade": estrategia.get("diversidade", 0),
        "taxa_mutacao": estrategia.get("taxa_mutacao", 0),
        "elite_fracao": estrategia.get("elite_fracao", 0),
        "confianca_modelos": ensemble.get("confianca_modelos", {}),
        "top_dezenas": [n for n, _ in sorted((pesos or {}).items(), key=lambda x: x[1], reverse=True)[:10]],
        "ranking_ia": [n for n, _ in sorted((pesos or {}).items(), key=lambda x: x[1], reverse=True)],
        "ranking_top5_acertos": len(set([n for n, _ in sorted((pesos or {}).items(), key=lambda x: x[1], reverse=True)[:5]]) & set(resultado)),
        "ranking_top10_acertos": len(set([n for n, _ in sorted((pesos or {}).items(), key=lambda x: x[1], reverse=True)[:10]]) & set(resultado)),
        "ranking_top15_acertos": len(set([n for n, _ in sorted((pesos or {}).items(), key=lambda x: x[1], reverse=True)[:15]]) & set(resultado)),
        "ciclo_detectado": (analise.get("ciclo") or {}).get("ciclo_principal", ""),
        "media_sobreposicao": cobertura.get("media_sobreposicao", 0),
    }

    with _LOCK_MEMORIA_APRENDIZADO:
        memoria = carregar_memoria_aprendizado(caminho)
        memoria.setdefault("registros", []).append(registro)
        memoria["registros"] = memoria["registros"][-500:]
        memoria["ajustes"] = calcular_bonus_aprendizado(memoria)
        salvar_memoria_aprendizado(memoria, caminho)
    # V21.1-A: espelha no SQLite
    _db_reg_apr(registro)
    return registro, memoria["ajustes"]




def registrar_resultado_simulado_aprendizado(jogos: list, analise: dict, pesos: dict, resultado_real: list, origem: str = "simulacao_continua", caminho: str = ARQUIVO_APRENDIZADO) -> tuple[dict, dict]:
    """
    Registra um resultado de treino feito contra concursos reais anteriores.
    É usado pelo botão Aprender Contínuo. Mantém a mesma memória do robô,
    mas marca a origem como simulação para diferenciar de avaliação manual/real.
    """
    with _LOCK_MEMORIA_APRENDIZADO:
        registro, ajustes = registrar_resultado_aprendizado(jogos, analise, pesos, resultado_real, caminho=caminho)
        memoria = carregar_memoria_aprendizado(caminho)
        if memoria.get("registros"):
            memoria["registros"][-1]["origem"] = origem
            memoria["registros"][-1]["treino_historico"] = True
            memoria["ajustes"] = calcular_bonus_aprendizado(memoria)
            salvar_memoria_aprendizado(memoria, caminho)
            ajustes = memoria["ajustes"]
            # O `registro` devolvido ao chamador precisa refletir o que foi
            # de fato persistido (origem/treino_historico) -- antes ele
            # ficava com o dict original, sem esses dois campos, então
            # qualquer código que confiasse no retorno em vez de reler o
            # arquivo via `registro` recebia informação inconsistente.
            registro = dict(memoria["registros"][-1])
    return registro, ajustes

def gerar_resumo_aprendizado(memoria: dict | None = None) -> dict:
    memoria = memoria or carregar_memoria_aprendizado()
    ajustes = calcular_bonus_aprendizado(memoria)
    registros = memoria.get("registros", [])
    linhas = []
    linhas.append("APRENDIZADO PERMANENTE ADAPTATIVO")
    linhas.append("-" * 72)
    linhas.append(ajustes.get("resumo", "Sem dados."))
    if registros:
        ult = registros[-1]
        linhas.append(f"Último registro: melhor={ult.get('melhor_acerto', 0)} | média={ult.get('media_acertos', 0)} | modo={ult.get('modo', '')}")
        linhas.append(f"Ajustes atuais: diversidade={ajustes.get('ajuste_diversidade', 0):+.3f}, mutação={ajustes.get('ajuste_mutacao', 0):+.3f}, elite={ajustes.get('ajuste_elite', 0):+.3f}")
        bm = ajustes.get("bonus_modelos") or {}
        if bm:
            linhas.append("Bônus dos modelos: " + ", ".join(f"{k}={v:+.3f}" for k, v in sorted(bm.items())))
        mr = ajustes.get("memoria_ranking") or {}
        if mr.get("tem_ranking"):
            linhas.append("Memória por posição do ranking: " + mr.get("resumo", ""))
            linhas.append(f"Fator de concentração do Top15: {mr.get('fator_concentracao_top', 0):+.3f}")
    return "\n".join(linhas)




