"""
lotofacil_pkg/v19_0_arquitetura_cientifica.py
----------------------------------------------
Pipeline V19 unificado.

Centraliza Meta Otimizador, IA Adaptativa, Meta-Ensemble, Monte Carlo
e Auditor Científico em uma única função de entrada — ``pipeline_v19``.

A partir da V19.1 o pipeline também integra telemetria e cache inteligente
de backtest, além de benchmark e score de estabilidade.

Imports explícitos (sem ``import *``) para rastreabilidade de símbolos.
"""

# ── V18: Meta Otimizador ──────────────────────────────────────────────────────
from .v18_meta_otimizador import (
    carregar_historico,
    salvar_historico,
    carregar_pesos_modelos,
    salvar_pesos_modelos,
    registrar_resultado_modelo,
    calcular_rating_modelo,
    recalcular_pesos_adaptativos,
    gerar_hall_da_fama,
)

# ── V18: IA Adaptativa (detecção de cenário) ──────────────────────────────────
from .v18_1b_ia_adaptativa import (
    detectar_cenario,
    selecionar_modelos,
    ajustar_pesos_por_cenario,
    registrar_performance_cenario,
)

# ── V18: Meta-Ensemble ────────────────────────────────────────────────────────
# Nota: v18_1c_meta_ensemble duplica detectar_cenario/selecionar_modelos/
# ajustar_pesos_por_cenario de v18_1b_ia_adaptativa. Importa apenas o que
# não foi importado acima para evitar colisão de nomes.
from .v18_1c_meta_ensemble import (
    registrar_performance_cenario as _registrar_performance_cenario_mc,  # alias
)

# ── V18: Monte Carlo ──────────────────────────────────────────────────────────
from .v18_2_montecarlo import (
    executar_monte_carlo,
    classificar_heatmap,
    calcular_consenso,
)

# ── V18: Auditor Científico ───────────────────────────────────────────────────
from .v18_2b_auditor_cientifico import (
    auditar_overfitting,
    auditar_recencia,
    auditar_modelos,
    auditar_pesos,
    gerar_relatorio_cientifico,
)

# ── V20: Backtest massivo, Poda inteligente, Ablação ─────────────────────────
from .v20_4_backtest_massivo import backtest_multijanela, gerar_relatorio_backtest
from .v20_2_poda_inteligente import (
    score_sobrevivencia,
    classificar_modelo,
    salvar_quarentena,
)
from .v20_3_ablation import (
    avaliar_contribuicao,
    ranking_contribuicao,
    gerar_relatorio_ablation,
)

# ── V19.1: Telemetria, Cache, Benchmark, Estabilidade ────────────────────────
from .v19_1_telemetria import Telemetria
from .v19_1_cache_inteligente import CacheBacktest
from .v19_1_benchmark import comparar_modelos, resumo_benchmark, filtrar_modelos_ativos
from .v19_1_estabilidade import (
    score_estabilidade,
    analisar_estabilidade,
    classificar_estabilidade,
)

# Instâncias compartilhadas do módulo (uma por processo)
_telemetria = Telemetria()
_cache = CacheBacktest()


def pipeline_v19(
    ranking_dezenas: dict | None = None,
    metricas: dict | None = None,
    usar_cache: bool = True,
    chave_cache: str = "pipeline_padrao",
    janelas_backtest: dict | None = None,
    pesos_modelos: list | None = None,
    contribuicoes_ablacao: dict | None = None,
) -> dict:
    """
    Executa o pipeline científico V19 completo.

    Etapas:
      1. Consulta cache — retorna resultado anterior se existir e ``usar_cache=True``.
      2. Detecção de cenário a partir das ``metricas`` fornecidas.
      3. Simulação Monte Carlo sobre ``ranking_dezenas``.
      4. Geração do relatório científico (auditoria de overfitting/pesos).
      5. Recalcula pesos adaptativos dos modelos.
      6. Persiste resultado no cache.

    Args:
        ranking_dezenas:      dict ``{dezena: peso}`` vindo do ensemble (opcional).
        metricas:             dict com ``"repeticao"``, ``"pares"``, ``"dispersao"``
                              para detecção de cenário (opcional).
        usar_cache:           se True, tenta reaproveitar resultado em cache.
        chave_cache:          chave de identificação no CacheBacktest.
        janelas_backtest:     dict ``{nome_janela: [scores]}`` para backtest
                              massivo multi-janela (V20.4, opcional).
        pesos_modelos:        lista de dicts ``{nome, score_global,
                              desempenho_recente, estabilidade}`` para poda
                              inteligente (V20.2, opcional).
        contribuicoes_ablacao: dict ``{nome_modelo: contribuicao_marginal}``
                              para análise de ablação (V20.3, opcional).

    Returns:
        Dict com chaves: ``cenario``, ``montecarlo``, ``relatorio_cientifico``,
        ``pesos_adaptativos``, ``meta_otimizador``, ``ia_adaptativa``,
        ``meta_ensemble``, ``monte_carlo``, ``auditor``,
        ``backtest_massivo`` (V20.4), ``poda_modelos`` (V20.2),
        ``ablacao`` (V20.3).
    """
    _telemetria.iniciar("pipeline_v19")

    # 1. Cache
    if usar_cache:
        cached = _cache.carregar(chave_cache)
        if cached is not None:
            _telemetria.finalizar("pipeline_v19")
            cached["_fonte"] = "cache"
            return cached

    resultado: dict = {
        "meta_otimizador": True,
        "ia_adaptativa": True,
        "meta_ensemble": True,
        "monte_carlo": True,
        "auditor": True,
        "_fonte": "calculado",
    }

    # 2. Detecção de cenário
    try:
        cenario_info = detectar_cenario(metricas or {})
        resultado["cenario"] = cenario_info
    except Exception as exc:
        resultado["cenario"] = {"cenario": "desconhecido", "_erro": str(exc)}

    # 3. Monte Carlo
    try:
        if ranking_dezenas:
            resultado["montecarlo"] = executar_monte_carlo(ranking_dezenas)
        else:
            resultado["montecarlo"] = {}
    except Exception as exc:
        resultado["montecarlo"] = {"_erro": str(exc)}

    # 4. Relatório científico
    try:
        resultado["relatorio_cientifico"] = gerar_relatorio_cientifico()
    except Exception as exc:
        resultado["relatorio_cientifico"] = {"_erro": str(exc)}

    # 5. Pesos adaptativos
    try:
        resultado["pesos_adaptativos"] = recalcular_pesos_adaptativos()
    except Exception as exc:
        resultado["pesos_adaptativos"] = {"_erro": str(exc)}

    # 6. Backtest massivo multi-janela (V20.4)
    try:
        if janelas_backtest:
            resultado["backtest_massivo"] = backtest_multijanela(janelas_backtest)
        else:
            resultado["backtest_massivo"] = []
    except Exception as exc:
        resultado["backtest_massivo"] = {"_erro": str(exc)}

    # 7. Poda inteligente de modelos (V20.2)
    try:
        if pesos_modelos:
            modelos_classificados = []
            for m in pesos_modelos:
                s = score_sobrevivencia(
                    m.get("score_global", 0.0),
                    m.get("desempenho_recente", 0.0),
                    m.get("estabilidade", 0.0),
                )
                modelos_classificados.append({**m, "score_sobrevivencia": s, "estado": classificar_modelo(s)})
            resultado["poda_modelos"] = modelos_classificados
        else:
            resultado["poda_modelos"] = []
    except Exception as exc:
        resultado["poda_modelos"] = {"_erro": str(exc)}

    # 8. Análise de ablação (V20.3)
    try:
        if contribuicoes_ablacao:
            resultado["ablacao"] = {
                "ranking": ranking_contribuicao(contribuicoes_ablacao),
                "modelos_negativos": [m for m, v in contribuicoes_ablacao.items() if v < 0],
            }
        else:
            resultado["ablacao"] = {}
    except Exception as exc:
        resultado["ablacao"] = {"_erro": str(exc)}

    # 9. Persiste no cache
    if usar_cache:
        try:
            _cache.salvar(chave_cache, resultado)
        except Exception:
            pass

    _telemetria.finalizar("pipeline_v19")
    return resultado
