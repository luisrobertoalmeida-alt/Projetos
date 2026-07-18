"""
lotofacil_pkg/apostas.py
-------------------------
Orquestração da geração de apostas:
  - gerar_apostas — pipeline completo (análise → ensemble → genético → cobertura)
  - Modo Laboratório Inteligente — gera com a configuração G/P validada (não
    testa mais variantes de G/P, ver montar_configuracoes_laboratorio)
  - Assistente de configuração, Simulador "e se", Pacote mínimo
  - Relatório de evolução do aprendizado
"""
from collections import Counter
from datetime import datetime
from statistics import mean

from .config import (
    NUMEROS, MIN_HIST, ARQUIVO_APRENDIZADO,
    ARQUIVO_PERFORMANCE_ESTRATEGIA, ARQUIVO_DESEMPENHO_HISTORICO,
    ARQUIVO_CONHECIMENTO_CIENTIFICO,
)
from .utils import (
    formatar_jogo, intersecao, limitar, contar_pares, soma_jogo,
    salvar_json, ler_json, tornar_json_seguro, garantir_estrutura_pastas,
    gerar_timestamp_arquivo, normalizar_scores,
)
from .aprendizado import (
    calcular_bonus_aprendizado, aplicar_aprendizado_na_estrategia,
    carregar_memoria_aprendizado, salvar_memoria_aprendizado,
    registrar_resultado_aprendizado, registrar_resultado_simulado_aprendizado,
    gerar_resumo_aprendizado,
)
from .historico import analisar_historico
from .analise import (
    calcular_motor_estrategico,
    calcular_ensemble_multi_ia,
)
from .genetico import (
    gerar_jogo_base, evoluir_populacao, mutacao,
    filtrar_candidatos_refinamento_agressivo,
    selecionar_jogos_cobertura_global,
    calcular_mapa_cobertura, analisar_estrutura_jogo_cached,
    resumo_estrutural_pacote, parametros_refinamento_agressivo,
    score_jogo, recortar_historico_para_analise,
)


def gerar_apostas(concursos_completos: list, qtd_jogos: int = 20, janela_analise: int = 120, geracoes: int = 35, pop_size: int = 70, refinamento_agressivo: bool = True, estrategia_override: dict | None = None) -> tuple[list, dict, dict]:
    concursos = recortar_historico_para_analise(concursos_completos, janela_analise)
    analise = analisar_historico(concursos, janela=min(janela_analise, len(concursos)))
    estrategia = calcular_motor_estrategico(analise, qtd_jogos=qtd_jogos, janela=janela_analise)
    estrategia["refinamento_agressivo"] = bool(refinamento_agressivo)
    estrategia["parametros_refinamento_agressivo"] = parametros_refinamento_agressivo(estrategia)
    aprendizado = calcular_bonus_aprendizado()
    estrategia = aplicar_aprendizado_na_estrategia(estrategia, aprendizado)
    # Aplica override de estratégia quando fornecido por rotinas internas.
    if estrategia_override:
        estrategia.update(estrategia_override)
    analise["estrategia"] = estrategia
    analise["aprendizado"] = aprendizado
    ensemble = calcular_ensemble_multi_ia(concursos, analise, estrategia=estrategia)
    analise["ensemble"] = ensemble
    pesos = ensemble["pesos_finais"]

    tentativas_base = 180 if estrategia["modo"] == "agressivo" else 240 if estrategia["modo"] == "equilibrado" else 300
    elite = max(8, int(pop_size * estrategia.get("elite_fracao", 0.20)))

    inicial = [gerar_jogo_base(pesos, analise, tentativas=tentativas_base, estrategia=estrategia) for _ in range(pop_size)]
    evoluidos = evoluir_populacao(
        inicial, pesos, analise, geracoes=geracoes, tamanho_pop=pop_size, elite=elite, estrategia=estrategia
    )
    candidatos = evoluidos[:]
    repeticoes_mutacao = 4 if estrategia["modo"] == "conservador" else 3
    taxa_extra = limitar(estrategia.get("taxa_mutacao", 0.35) + 0.12, 0.25, 0.70)
    for jogo in evoluidos[:30]:
        for _ in range(repeticoes_mutacao):
            candidatos.append(mutacao(jogo, pesos, taxa=taxa_extra))
    candidatos = sorted(candidatos, key=lambda j: score_jogo(j, pesos, analise, estrategia=estrategia), reverse=True)
    info_ref = {"ativo": False}
    if refinamento_agressivo:
        candidatos, info_ref = filtrar_candidatos_refinamento_agressivo(
            candidatos, estrategia=estrategia, minimo=max(60, qtd_jogos * 6)
        )
        candidatos = sorted(candidatos, key=lambda j: score_jogo(j, pesos, analise, estrategia=estrategia), reverse=True)

    jogos, cobertura = selecionar_jogos_cobertura_global(
        candidatos, pesos, analise, qtd=qtd_jogos, estrategia=estrategia
    )

    cobertura["refinamento_agressivo"] = info_ref
    analise["cobertura_global"] = cobertura
    return jogos, analise, pesos



def score_pacote_laboratorio(jogos: list, analise: dict, pesos: dict) -> float:
    """
    Score interno para comparar configurações do Modo Laboratório.
    Não prevê sorteio; mede qualidade técnica do pacote: score médio,
    diversidade, cobertura, soma e equilíbrio par/ímpar.
    """
    if not jogos or not analise or not pesos:
        return -10**9

    # Import local: evita import circular (backtest.py já importa de apostas.py no topo do módulo).
    from .backtest import avaliar_jogos
    aval = avaliar_jogos(jogos, analise, pesos)
    media_score = mean([float(r.get("Score", 0)) for r in aval]) if aval else 0.0
    cobertura = analise.get("cobertura_global") or calcular_mapa_cobertura(jogos)
    media_sobre = float(cobertura.get("media_sobreposicao", 0) or 0)
    max_sobre = float(cobertura.get("max_sobreposicao", 0) or 0)
    media_soma = float(cobertura.get("media_soma", 0) or 0)
    media_pares = float(cobertura.get("media_pares", 0) or 0)

    # Quanto menor a sobreposição excessiva, melhor. Na Lotofácil é normal haver
    # alguma interseção, mas excesso deixa os jogos muito parecidos.
    bonus_diversidade = max(0.0, 12.0 - media_sobre) * 1.35
    penal_sobreposicao_maxima = max(0.0, max_sobre - 12.0) * 1.20

    # Mantém o pacote perto das faixas históricas típicas sem engessar demais.
    alvo_soma = float(analise.get("soma_media", 195.0) or 195.0)
    penal_soma = abs(media_soma - alvo_soma) / 16.0
    penal_pares = abs(media_pares - 7.5) / 1.8

    freq_dezenas = cobertura.get("freq_dezenas") or {}
    if freq_dezenas:
        valores = list(freq_dezenas.values())
        amplitude = max(valores) - min(valores)
    else:
        amplitude = 0
    penal_concentracao = amplitude * 0.10

    ref = cobertura.get("refinamento_matematico") or resumo_estrutural_pacote(jogos)
    bonus_refinamento = float(ref.get("score_estrutural_medio", 0) or 0) * 0.75
    penal_estrutura_fraca = float(ref.get("jogos_estrutura_fraca", 0) or 0) * 1.50

    return round(
        media_score
        + bonus_refinamento
        + bonus_diversidade
        - penal_sobreposicao_maxima
        - penal_soma
        - penal_pares
        - penal_concentracao
        - penal_estrutura_fraca,
        4,
    )


def montar_configuracoes_laboratorio(
    geracoes_max: int,
    pop_size_max: int,
    janela_analise: int = 150,
) -> list[dict]:
    """
    Até 2026-07-17 esta função montava uma bateria de até 5 configurações
    que só variavam gerações/população (com uma guarda de "zona morta"
    para ratio G/P alto + janela pequena, descoberta em calibração de
    25/06/2026 — antes da metodologia pareada/TOST deste projeto).

    Reavaliada com estatística pareada (`validacao_zona_morta.py`, n=150,
    janela=120, ratio 1.64 vs. 1.30): Cohen's d pareado = -0.04
    (desprezível), TOST (margem=±0.3) confirma equivalência. A "zona
    morta" não se sustentou — é o mesmo tipo de conclusão de amostra
    pequena já derrubada no Mapa G×P (ver ARQUITETURA.md). A guarda foi
    removida.

    `geracoes_max`/`pop_size_max`/`janela_analise` seguem aceitos por
    compatibilidade de assinatura, mas não influenciam mais o resultado:
    retorna sempre a configuração validada (G=16/P=40).
    """
    return [{
        "nome": "Configuração validada (G=16/P=40)",
        "geracoes": 16,
        "pop_size": 40,
        "ratio_gp": round(16 / 40, 2),
        "janela": max(30, int(janela_analise)),
    }]


def gerar_apostas_laboratorio_inteligente(  # noqa: E501
    concursos_completos,
    qtd_jogos=20,
    janela_analise=120,
    geracoes_max=250,
    pop_size_max=180,
    status_cb=None,
):
    """
    Gera o pacote com a configuração G/P validada (16/40).

    Até 2026-07-17 esta função testava várias configurações de G/P numa
    amostra pequena e escolhia uma "vencedora" — desde que o Mapa G×P e a
    reavaliação da "zona morta" confirmaram equivalência estatística em
    toda a faixa de G/P testada, não há mais nada para comparar aqui, só
    overhead (rodar duas vezes: teste + geração final). Mantido só o
    passo de geração final.
    """
    def avisar(msg: str) -> None:
        if status_cb:
            status_cb(msg)

    cfg = montar_configuracoes_laboratorio(geracoes_max, pop_size_max, janela_analise)[0]
    avisar(
        "Modo Laboratório Inteligente: G/P já validado (Mapa G×P + reavaliação "
        "de zona morta) — gerando direto com a configuração fixa, sem testar variantes."
    )
    avisar(f"Configuração: G={cfg['geracoes']} P={cfg['pop_size']}")

    jogos, analise, pesos = gerar_apostas(
        concursos_completos,
        qtd_jogos=qtd_jogos,
        janela_analise=janela_analise,
        geracoes=cfg["geracoes"],
        pop_size=cfg["pop_size"],
    )
    analise["laboratorio_inteligente"] = {
        "ativo": False,
        "motivo": "G/P fixo e validado (Mapa G×P + zona morta reavaliada) — sem variantes para testar.",
        "configuracao_usada": cfg,
    }
    return jogos, analise, pesos


def carregar_performance_estrategias(caminho: str = ARQUIVO_PERFORMANCE_ESTRATEGIA) -> dict:
    dados = ler_json(caminho, default={"versao": "1.0", "geracoes": [], "backtests": []})
    dados.setdefault("geracoes", [])
    dados.setdefault("backtests", [])
    return dados


def salvar_performance_estrategias(dados: dict, caminho: str = ARQUIVO_PERFORMANCE_ESTRATEGIA) -> None:
    garantir_estrutura_pastas()
    dados["atualizado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    dados["geracoes"] = dados.get("geracoes", [])[-300:]
    dados["backtests"] = dados.get("backtests", [])[-120:]
    salvar_json(caminho, dados)


def registrar_performance_geracao(jogos: list, analise: dict, geracoes: int, pop_size: int, janela: int, qtd_jogos: int) -> None:
    """Registra qualidade técnica do pacote gerado para consulta futura."""
    try:
        cobertura = (analise or {}).get("cobertura_global") or calcular_mapa_cobertura(jogos)
        estrategia = (analise or {}).get("estrategia") or {}
        ref = cobertura.get("refinamento_matematico") or resumo_estrutural_pacote(jogos)
        registro = {
            "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "qtd_jogos": int(qtd_jogos),
            "janela": int(janela),
            "geracoes": int(geracoes),
            "pop_size": int(pop_size),
            "modo": estrategia.get("modo", "equilibrado"),
            "diversidade": estrategia.get("diversidade", 0),
            "taxa_mutacao": estrategia.get("taxa_mutacao", 0),
            "media_sobreposicao": cobertura.get("media_sobreposicao", 0),
            "max_sobreposicao": cobertura.get("max_sobreposicao", 0),
            "media_soma": cobertura.get("media_soma", 0),
            "media_pares": cobertura.get("media_pares", 0),
            "score_estrutural_medio": ref.get("score_estrutural_medio", 0),
            "estruturas_fracas": ref.get("jogos_estrutura_fraca", 0),
            "refinamento_agressivo": cobertura.get("refinamento_agressivo", {}),
        }
        dados = carregar_performance_estrategias()
        dados.setdefault("geracoes", []).append(registro)
        salvar_performance_estrategias(dados)
        return registro
    except Exception:
        return None


# =========================================================
# ASSISTENTE DE CONFIGURAÇÃO INTELIGENTE
# =========================================================
# =========================================================
# ASSISTENTE DE CONFIGURAÇÃO INTELIGENTE
# =========================================================
def calcular_configuracao_assistida(concursos: list | None = None, qtd_jogos: int = 20, janela_atual: int = 120, geracoes_atual: int = 35, pop_atual: int = 70, perfil: str = "auto") -> dict:
    """
    Sugere uma configuração técnica segura para reduzir tentativa manual.
    Ajusta janela e passos de backtest conforme tamanho do histórico. Gerações/
    população NÃO são mais ajustadas aqui (ver nota abaixo) — apenas repassadas
    fixas. Não promete previsão; apenas escolhe parâmetros coerentes.
    """
    total_hist = len(concursos or [])
    qtd_jogos = min(max(5, int(qtd_jogos or 20)), 100)
    janela_atual = int(janela_atual or 120)
    geracoes_atual = int(geracoes_atual or 35)
    pop_atual = int(pop_atual or 70)

    memoria = carregar_memoria_aprendizado()
    ajustes = calcular_bonus_aprendizado(memoria)
    registros_reais = memoria.get("registros", [])[-80:]

    # Janela: se houver histórico suficiente, prefere 120-200; se o desempenho real
    # estiver fraco, abre um pouco a janela para reduzir ruído recente.
    if total_hist >= 240:
        janela = 200
    elif total_hist >= 160:
        janela = 150
    elif total_hist >= 100:
        janela = 100
    else:
        janela = max(MIN_HIST, min(total_hist or janela_atual, 80))

    if registros_reais:
        media_melhor = mean([float(r.get("melhor_acerto", 0) or 0) for r in registros_reais])
        taxa_12 = sum(1 for r in registros_reais if float(r.get("melhor_acerto", 0) or 0) >= 12) / max(1, len(registros_reais))
        taxa_13 = sum(1 for r in registros_reais if float(r.get("melhor_acerto", 0) or 0) >= 13) / max(1, len(registros_reais))
        motivo_desempenho = "desempenho recente registrado (não influencia geração/população — ver nota abaixo)"
    else:
        media_melhor, taxa_12, taxa_13 = 0.0, 0.0, 0.0
        motivo_desempenho = "sem registros reais suficientes"

    # geracoes/pop_size: FIXOS em 16/40 desde 2026-07-18 (Mapa G x P, n=300,
    # TOST margem=0.3) confirmou equivalência estatística na faixa G=16-300 —
    # não há vale estrutural, então nem quantidade de jogos, nem desempenho
    # recente, nem histórico técnico anterior devem reajustar esses dois
    # parâmetros. `perfil` segue aceito por compatibilidade de assinatura,
    # mas não afeta mais G/P.
    geracoes = 16
    pop_size = 40

    janela = min(max(MIN_HIST, janela), max(MIN_HIST, total_hist or janela))
    passos_bt = 50 if qtd_jogos <= 20 else 35

    cfg = {
        "qtd_jogos": qtd_jogos,
        "janela": int(janela),
        "geracoes": int(geracoes),
        "pop_size": int(pop_size),
        "passos_backtest": int(passos_bt),
        "usar_laboratorio": False,
        # modo_turbo NAO e definido aqui — o assistente respeita a escolha do usuario.
        # A UI preserva o estado atual do checkbox ao aplicar esta configuracao.
        "motivo": motivo_desempenho,
        "media_melhor_real": round(media_melhor, 3),
        "taxa_12_mais": round(taxa_12 * 100, 2),
        "taxa_13_mais": round(taxa_13 * 100, 2),
        "registros_reais": len(registros_reais),
        "ajustes_memoria": ajustes,
    }
    return cfg


def explicar_configuracao_assistida(cfg: dict) -> str:
    linhas = []
    linhas.append("ASSISTENTE DE CONFIGURAÇÃO INTELIGENTE")
    linhas.append("-" * 72)
    linhas.append(f"Jogos: {cfg.get('qtd_jogos')} | Janela: {cfg.get('janela')} | Gerações: {cfg.get('geracoes')} | População: {cfg.get('pop_size')}")
    linhas.append(f"Backtest sugerido: {cfg.get('passos_backtest')} passos | Laboratório automático: desligado")
    linhas.append(f"Motivo: {cfg.get('motivo')}")
    if cfg.get('registros_reais'):
        linhas.append(f"Base real do robô: {cfg.get('registros_reais')} registro(s) | média do melhor acerto={cfg.get('media_melhor_real')} | 12+={cfg.get('taxa_12_mais')}% | 13+={cfg.get('taxa_13_mais')}%")
    else:
        linhas.append("Base real do robô: ainda sem registros suficientes; usando configuração técnica segura.")
    if cfg.get("conhecimento_cientifico"):
        cc = cfg.get("conhecimento_cientifico") or {}
        linhas.append(f"Conhecimento científico ativo: {cc.get('estrategia_base', '')} | G={cc.get('geracoes', 0)} | P={cc.get('pop_size', 0)} | modelo campeão={cc.get('modelo_campeao', '')}")
    return "\n".join(linhas)


# =========================================================
# SIMULADOR "E SE EU TIVESSE JOGADO?"
# =========================================================
def simular_jogos_em_concurso(jogos: list, concurso_real: list[int]) -> dict:
    """Retorna acertos de cada jogo contra um concurso histórico real."""
    resultados = []
    for i, jogo in enumerate(jogos, 1):
        acertos = intersecao(jogo, concurso_real)
        resultados.append({
            "jogo": i,
            "dezenas": formatar_jogo(jogo),
            "acertos": acertos,
            "premio": "🏆 15pts" if acertos == 15 else
                      "🥇 14pts" if acertos == 14 else
                      "🥈 13pts" if acertos == 13 else
                      "🥉 12pts" if acertos == 12 else
                      "✅ 11pts" if acertos == 11 else
                      f"❌ {acertos}pts",
        })
    resultados.sort(key=lambda r: r["acertos"], reverse=True)
    melhor = max(r["acertos"] for r in resultados)
    com_11_mais = sum(1 for r in resultados if r["acertos"] >= 11)
    return {
        "resultados": resultados,
        "melhor_acerto": melhor,
        "jogos_com_11_mais": com_11_mais,
        "total_jogos": len(jogos),
        "concurso_real": formatar_jogo(concurso_real),
    }


# =========================================================
# OTIMIZADOR DE PACOTE MÍNIMO
# =========================================================
def calcular_pacote_minimo(concursos: list, analise: dict, pesos: dict, cobertura_alvo: int = 20, max_jogos: int = 30) -> dict:
    """
    Calcula o menor pacote de jogos que cobre pelo menos `cobertura_alvo`
    dezenas distintas do espaço de 1-25, com boa diversidade estrutural.
    Retorna o pacote e métricas de cobertura.
    """
    candidatos = [
        gerar_jogo_base(pesos, analise, tentativas=80)
        for _ in range(max_jogos * 3)
    ]
    candidatos = sorted(
        candidatos,
        key=lambda j: analisar_estrutura_jogo_cached(j).get("score_estrutural", 0),
        reverse=True
    )

    pacote = []
    dezenas_cobertas = set()
    vistos = set()

    for jogo in candidatos:
        t = tuple(jogo)
        if t in vistos:
            continue
        vistos.add(t)
        novas = set(jogo) - dezenas_cobertas
        if not novas and len(pacote) > 0:
            continue
        # Verifica diversidade mínima
        if pacote:
            max_inter = max(intersecao(jogo, ex) for ex in pacote)
            if max_inter > 11:
                continue
        pacote.append(jogo)
        dezenas_cobertas.update(jogo)
        if len(dezenas_cobertas) >= cobertura_alvo and len(pacote) >= 3:
            break
        if len(pacote) >= max_jogos:
            break

    cobertura = calcular_mapa_cobertura(pacote)
    return {
        "pacote": pacote,
        "qtd_jogos": len(pacote),
        "dezenas_cobertas": sorted(dezenas_cobertas),
        "total_cobertas": len(dezenas_cobertas),
        "cobertura_alvo": cobertura_alvo,
        "custo_estimado_r": len(pacote) * 3.00,
        "cobertura_mapa": cobertura,
    }


# =========================================================
# RELATÓRIO DE EVOLUÇÃO DO APRENDIZADO
# =========================================================
def gerar_relatorio_evolucao_aprendizado() -> str:
    """
    Analisa a evolução dos acertos ao longo do tempo registrado na memória IA.
    Retorna métricas por período (semanas/meses) e tendência geral.
    """
    memoria = carregar_memoria_aprendizado()
    registros = memoria.get("registros", [])
    if len(registros) < 3:
        return {"erro": "Registros insuficientes (mínimo 3)."}

    melhores = [int(r.get("melhor_acerto", 0)) for r in registros]
    medias   = [float(r.get("media_acertos", 0)) for r in registros]
    n = len(melhores)

    # Tendência linear simples
    def tendencia_linear(vals: list[float]) -> float:
        n_ = len(vals)
        if n_ < 2:
            return 0.0
        xs = list(range(n_))
        mx = sum(xs) / n_; my = sum(vals) / n_
        num = sum((x - mx) * (y - my) for x, y in zip(xs, vals))
        den = sum((x - mx) ** 2 for x in xs) or 1
        return num / den

    slope = tendencia_linear(melhores)
    slope_med = tendencia_linear(medias)

    # Períodos: divide em 3 faixas (início, meio, fim)
    t3 = n // 3
    inicio  = melhores[:t3] or melhores
    meio    = melhores[t3:2*t3] or melhores
    fim     = melhores[2*t3:] or melhores

    media_inicio = round(mean(inicio), 2)
    media_meio   = round(mean(meio), 2)
    media_fim    = round(mean(fim), 2)

    dist = dict(sorted(Counter(melhores).items()))
    pct_11 = round(100 * sum(1 for m in melhores if m >= 11) / max(n, 1), 1)
    pct_12 = round(100 * sum(1 for m in melhores if m >= 12) / max(n, 1), 1)

    if slope > 0.01:
        tendencia_txt = "📈 Melhorando"
    elif slope < -0.01:
        tendencia_txt = "📉 Piorando"
    else:
        tendencia_txt = "➡️ Estável"

    return {
        "total_registros":  n,
        "media_geral_melhor": round(mean(melhores), 2),
        "media_geral_media":  round(mean(medias), 2),
        "melhor_historico":   max(melhores),
        "pct_11_mais":        pct_11,
        "pct_12_mais":        pct_12,
        "tendencia":          tendencia_txt,
        "slope":              round(slope, 4),
        "media_inicio":       media_inicio,
        "media_meio":         media_meio,
        "media_fim":          media_fim,
        "distribuicao":       dist,
        "serie_melhores":     melhores,
        "serie_medias":       medias,
    }


# =========================================================
# BANCO HISTÓRICO DE DESEMPENHO DO ROBÔ
# =========================================================

# =========================================================
# V21.5-FULL — GERAÇÃO DUAL-PERFIL
# =========================================================
"""
Dual-Perfil: gera automaticamente dois subpacotes com objetivos distintos
e os mescla num único pacote final entregue ao usuário.

  Perfil Consistência (70%): maximiza 11+/12+ com G=80/P=80
  Perfil Exploração   (30%): maximiza chance de 13+  com G=40/P=40,
                              pesos dominados por Pares/Trios e Cobertura

O usuário pede N jogos e recebe N jogos — transparente.
"""

# Pesos fixos do perfil de exploração (não adaptativo — alta variância intencional)
_PESOS_EXPLORACAO = {
    "pares_trios":  0.38,   # dominante: captura padrões raros
    "cobertura":    0.28,   # complementar: maximiza cobertura de dezenas
    "bayesiano":    0.14,   # suporte probabilístico
    "estatistico":  0.10,   # âncora leve para não perder consistência total
    "tendencia":    0.06,
    "neural_leve":  0.03,
    "markov":       0.01,
}

# Proporção do subpacote de exploração no total
_FRACAO_EXPLORACAO = 0.30


def gerar_apostas_dual_perfil(
    concursos_completos: list,
    qtd_jogos: int = 20,
    janela_analise: int = 120,
    geracoes_consistencia: int = 80,
    pop_consistencia: int = 80,
    fracao_exploracao: float = _FRACAO_EXPLORACAO,
    status_cb=None,
    estrategia_override: dict | None = None,
) -> tuple[list, dict, dict]:
    """
    Gera um pacote misto com dois perfis automáticos:
      - Consistência (70%): G=80/P=80, pesos adaptativos normais
      - Exploração   (30%): G=40/P=40, pesos fixos voltados para 13+

    Args:
        concursos_completos: histórico completo
        qtd_jogos:           total de jogos no pacote final
        janela_analise:      janela histórica para análise
        geracoes_consistencia: gerações do perfil principal (padrão 80)
        pop_consistencia:    população do perfil principal  (padrão 80)
        fracao_exploracao:   fração do pacote dedicada à exploração [0.0, 0.5]
        status_cb:           callback de status para a UI

    Returns:
        (jogos_final, analise, pesos)
        analise["dual_perfil"] contém métricas de ambos os subpacotes.
    """
    def avisar(msg: str) -> None:
        if status_cb:
            status_cb(msg)

    fracao_exploracao = max(0.0, min(0.50, fracao_exploracao))
    n_exploracao  = max(1, round(qtd_jogos * fracao_exploracao))
    n_consistencia = qtd_jogos - n_exploracao

    avisar(f"Dual-Perfil: {n_consistencia} jogos consistência + {n_exploracao} exploração (13+)")

    # ── Perfil Consistência ───────────────────────────────────────────────
    avisar(f"[1/2] Perfil Consistência — G={geracoes_consistencia} P={pop_consistencia}...")
    jogos_c, analise_c, pesos_c = gerar_apostas(
        concursos_completos,
        qtd_jogos=n_consistencia,
        janela_analise=janela_analise,
        geracoes=geracoes_consistencia,
        pop_size=pop_consistencia,
        refinamento_agressivo=True,
        estrategia_override=estrategia_override,
    )

    # ── Perfil Exploração ─────────────────────────────────────────────────
    avisar(f"[2/2] Perfil Exploração — G=40 P=40 (Pares/Trios + Cobertura dominantes)...")

    concursos_rec = recortar_historico_para_analise(concursos_completos, janela_analise)

    # Override de estratégia: modo exploratório com mutação alta
    estrategia_exp = analise_c.get("estrategia", {}).copy()
    estrategia_exp["modo"]            = "agressivo"
    estrategia_exp["taxa_mutacao"]    = 0.65   # alta variância intencional
    estrategia_exp["elite_fracao"]    = 0.10   # menos elitismo → mais diversidade
    estrategia_exp["diversidade"]     = 0.90
    # V21.6 — propaga overrides externos (ex: peso_impopularidade) ao perfil de exploração
    if estrategia_override:
        estrategia_exp.update(estrategia_override)

    # Recalcula ensemble forçando os pesos dos modelos de exploração
    # via estrategia_override — o ensemble normaliza e gera pesos por dezena
    from .analise import calcular_ensemble_multi_ia as _ensemble
    from .historico import analisar_historico as _analise_hist

    analise_exp = _analise_hist(concursos_rec, janela=min(janela_analise, len(concursos_rec)))
    analise_exp["estrategia"] = estrategia_exp

    # Injeta confiança dos modelos de exploração diretamente no ensemble
    ensemble_exp = _ensemble(
        concursos_rec, analise_exp, estrategia=estrategia_exp
    )
    # Substitui confiança pelos pesos fixos de exploração, re-normaliza
    total_exp = sum(_PESOS_EXPLORACAO.values())
    conf_exp = {k: v / total_exp for k, v in _PESOS_EXPLORACAO.items()}
    ensemble_exp["confianca_modelos"] = conf_exp
    # Recalcula pesos_finais por dezena com a nova confiança
    from .analise import calcular_scores_pares_trios, calcular_scores_cobertura
    from .utils import normalizar_scores as _norm
    scores_exp = {}
    for nome, peso in conf_exp.items():
        fn_map = {
            "estatistico":  lambda: analise_exp.get("scores_estatistico", {}),
            "markov":       lambda: ensemble_exp.get("scores_modelos", {}).get("markov", {}),
            "bayesiano":    lambda: ensemble_exp.get("scores_modelos", {}).get("bayesiano", {}),
            "tendencia":    lambda: ensemble_exp.get("scores_modelos", {}).get("tendencia", {}),
            "neural_leve":  lambda: ensemble_exp.get("scores_modelos", {}).get("neural_leve", {}),
            "cobertura":    lambda: calcular_scores_cobertura(analise_exp),
            "pares_trios":  lambda: calcular_scores_pares_trios(analise_exp),
        }
        sc = fn_map.get(nome, lambda: {})()
        for dezena, val in sc.items():
            scores_exp[dezena] = scores_exp.get(dezena, 0.0) + float(val) * peso
    pesos_exp = _norm(scores_exp) if scores_exp else ensemble_exp.get("pesos_finais", {})
    analise_exp["ensemble"] = ensemble_exp

    from .genetico import (
        gerar_jogo_base, evoluir_populacao, mutacao,
        selecionar_jogos_cobertura_global, score_jogo,
    )

    pop_exp = 40
    ger_exp = 40
    tentativas_exp = 120

    inicial_exp = [
        gerar_jogo_base(pesos_exp, analise_exp,
                        tentativas=tentativas_exp, estrategia=estrategia_exp)
        for _ in range(pop_exp)
    ]
    evoluidos_exp = evoluir_populacao(
        inicial_exp, pesos_exp, analise_exp,
        geracoes=ger_exp, tamanho_pop=pop_exp,
        elite=max(2, int(pop_exp * 0.10)),
        estrategia=estrategia_exp,
    )

    # Mutações extras para maximizar variância
    candidatos_exp = evoluidos_exp[:]
    for jogo in evoluidos_exp[:15]:
        for _ in range(5):
            candidatos_exp.append(
                mutacao(jogo, pesos_exp, taxa=0.70)
            )

    candidatos_exp = sorted(
        candidatos_exp,
        key=lambda j: score_jogo(j, pesos_exp, analise_exp,
                                  estrategia=estrategia_exp),
        reverse=True,
    )

    jogos_exp, cobertura_exp = selecionar_jogos_cobertura_global(
        candidatos_exp, pesos_exp, analise_exp,
        qtd=n_exploracao, estrategia=estrategia_exp,
    )

    # ── Mescla ────────────────────────────────────────────────────────────
    # Intercala jogos dos dois perfis para não agrupar no relatório
    jogos_final = []
    idx_c, idx_e = 0, 0
    turno = 0
    while len(jogos_final) < qtd_jogos:
        # Alterna: 2 consistência para 1 exploração (reflete proporção 70/30)
        if turno % 3 == 2 and idx_e < len(jogos_exp):
            jogos_final.append(jogos_exp[idx_e])
            idx_e += 1
        elif idx_c < len(jogos_c):
            jogos_final.append(jogos_c[idx_c])
            idx_c += 1
        elif idx_e < len(jogos_exp):
            jogos_final.append(jogos_exp[idx_e])
            idx_e += 1
        else:
            break
        turno += 1

    # ── Analise enriquecida ───────────────────────────────────────────────
    from .genetico import calcular_mapa_cobertura, resumo_estrutural_pacote
    cobertura_final = calcular_mapa_cobertura(jogos_final)
    analise_c["cobertura_global"] = cobertura_final

    analise_c["dual_perfil"] = {
        "ativo":             True,
        "n_consistencia":    len(jogos_c),
        "n_exploracao":      len(jogos_exp),
        "fracao_exploracao": fracao_exploracao,
        "geracoes_consistencia": geracoes_consistencia,
        "pop_consistencia":      pop_consistencia,
        "pesos_exploracao":      _PESOS_EXPLORACAO,
        "cobertura_exploracao":  cobertura_exp,
        "nota": (
            f"Pacote dual: {len(jogos_c)} jogos otimizados para 11+/12+ "
            f"+ {len(jogos_exp)} jogos de exploração para 13+ "
            f"(Pares/Trios + Cobertura dominantes, G=40/P=40)"
        ),
    }

    avisar(
        f"Dual-Perfil concluído: {len(jogos_c)} consistência + "
        f"{len(jogos_exp)} exploração = {len(jogos_final)} jogos totais"
    )

    return jogos_final, analise_c, pesos_c


def relatorio_dual_perfil(analise: dict) -> str:
    """Texto resumido do dual-perfil para exibir no dashboard/relatório."""
    dp = analise.get("dual_perfil")
    if not dp or not dp.get("ativo"):
        return ""

    linhas = [
        "═" * 55,
        "  PACOTE DUAL-PERFIL V21.5-FULL",
        "═" * 55,
        f"  Consistência (11+/12+):  {dp['n_consistencia']} jogos",
        f"    G={dp['geracoes_consistencia']} P={dp['pop_consistencia']} · pesos adaptativos",
        "",
        f"  Exploração (13+):        {dp['n_exploracao']} jogos",
        f"    G=40 P=40 · Pares/Trios {_PESOS_EXPLORACAO['pares_trios']*100:.0f}%"
        f" + Cobertura {_PESOS_EXPLORACAO['cobertura']*100:.0f}%",
        "",
        f"  Total:  {dp['n_consistencia'] + dp['n_exploracao']} jogos",
        "═" * 55,
    ]
    return "\n".join(linhas)
