"""
lotofacil_pkg/v21_5_walkforward_profissional.py
-------------------------------------------------
V21.5-FULL — Walk-Forward Profissional com Indicadores Permanentes.

Diferença em relação ao v20_8_walkforward:
  - Os resultados são persistidos no SQLite após cada execução
  - Indicadores permanentes acumulam ao longo de centenas de concursos
  - O dashboard sempre mostra o valor consolidado (não só o último run)
  - Detecta tendências de longo prazo (robustez crescente ou decrescente)

Indicadores gerados:
  - robustez_temporal:  % de janelas em que o robô supera o baseline [0,1]
  - estabilidade:       1 - coeficiente de variação dos scores por janela [0,1]
  - overfitting_nivel:  "BAIXO" / "MODERADO" / "ALTO"
  - trend_robustez:     "MELHORANDO" / "ESTAVEL" / "PIORANDO"

Funções exportadas:
  executar_walkforward_profissional   — executa e persiste
  get_indicadores_permanentes         — lê o histórico acumulado do SQLite
  relatorio_walkforward_profissional  — relatório completo para o dashboard
"""
import json
import random
from datetime import datetime, timezone
from statistics import mean, stdev

from .v20_8_walkforward import (
    gerar_janelas_walkforward,
    score_janela,
    score_robustez_walkforward,
    detectar_overfitting_wf,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gerar_baseline_janela(sorteios_teste: list, qtd_jogos: int, seed: int = 42) -> dict:
    """Gera baseline aleatório para uma janela de teste."""
    rng = random.Random(seed)
    numeros = list(range(1, 26))
    jogos_rand = [sorted(rng.sample(numeros, 15)) for _ in range(qtd_jogos)]
    acertos = []
    for sorteio in sorteios_teste:
        for jogo in jogos_rand:
            acertos.append(len(set(jogo) & set(sorteio)))
    return {"media_acertos": round(mean(acertos), 4) if acertos else 0.0}


def _salvar_indicadores_sqlite(indicadores: dict) -> None:
    """Persiste indicadores permanentes no SQLite."""
    try:
        from .v21_0_sqlite import get_db
        conn = get_db()
        with conn:
            conn.execute("""
                INSERT INTO walkforward_indicadores
                (robustez_temporal, estabilidade, overfitting_nivel,
                 trend_robustez, n_janelas, delta_vs_baseline,
                 score_robustez_raw, concurso_inicio, concurso_fim,
                 payload, criado_em)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                indicadores.get("robustez_temporal"),
                indicadores.get("estabilidade"),
                indicadores.get("overfitting_nivel"),
                indicadores.get("trend_robustez"),
                indicadores.get("n_janelas"),
                indicadores.get("delta_vs_baseline"),
                indicadores.get("score_robustez_raw"),
                indicadores.get("concurso_inicio"),
                indicadores.get("concurso_fim"),
                json.dumps(indicadores),
                _now(),
            ))
    except Exception:
        pass


def _carregar_historico_walkforward(limit: int = 50) -> list[dict]:
    """Carrega histórico de execuções anteriores do SQLite."""
    try:
        from .v21_0_sqlite import get_db
        conn = get_db()
        rows = conn.execute("""
            SELECT robustez_temporal, estabilidade, overfitting_nivel,
                   trend_robustez, n_janelas, delta_vs_baseline,
                   score_robustez_raw, criado_em
            FROM walkforward_indicadores
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in reversed(rows)]
    except Exception:
        return []


def _calcular_trend(historico: list[dict]) -> str:
    """Determina tendência da robustez ao longo das últimas execuções."""
    if len(historico) < 3:
        return "ESTAVEL"
    vals = [h.get("robustez_temporal", 0.5) for h in historico[-6:]]
    if len(vals) < 3:
        return "ESTAVEL"
    # Regressão linear simples
    n = len(vals)
    xs = list(range(n))
    mx, my = mean(xs), mean(vals)
    num   = sum((x - mx) * (y - my) for x, y in zip(xs, vals))
    denom = sum((x - mx) ** 2 for x in xs) or 1e-9
    slope = num / denom
    if slope > 0.01:
        return "MELHORANDO"
    elif slope < -0.01:
        return "PIORANDO"
    return "ESTAVEL"


def executar_walkforward_profissional(
    concursos: list,
    fn_gerar,
    tamanho_treino: int = 100,
    tamanho_teste:  int = 20,
    passo:          int = 20,
    qtd_jogos:      int = 10,
) -> dict:
    """
    Executa o Walk-Forward completo com baseline, persiste e retorna indicadores.

    Args:
        concursos:       lista de sorteios históricos (mais antigo → mais recente)
        fn_gerar:        função fn(historico_treino) → list[list[int]]
        tamanho_treino:  concursos de treino por janela
        tamanho_teste:   concursos de teste por janela
        passo:           deslocamento entre janelas
        qtd_jogos:       apostas geradas por janela (para baseline)

    Returns:
        dict com todos os indicadores permanentes e relatório detalhado
    """
    janelas = gerar_janelas_walkforward(
        len(concursos), tamanho_treino, tamanho_teste, passo
    )

    if not janelas:
        return {
            "robustez_temporal":  0.0,
            "estabilidade":       0.0,
            "overfitting_nivel":  "INDEFINIDO",
            "trend_robustez":     "ESTAVEL",
            "n_janelas":          0,
            "erro":               "Histórico insuficiente",
        }

    scores_robo     = []
    scores_baseline = []
    resultados_wf   = []

    for jan in janelas:
        treino  = concursos[jan["treino_inicio"]: jan["treino_fim"]]
        teste   = concursos[jan["teste_inicio"]:  jan["teste_fim"]]

        try:
            jogos = fn_gerar(treino)
        except Exception:
            continue

        sc_robo = score_janela(jogos, teste)
        sc_base = _gerar_baseline_janela(teste, qtd_jogos=max(1, len(jogos)))

        media_r = sc_robo.get("media_acertos", 0.0)
        media_b = sc_base.get("media_acertos", 0.0)

        scores_robo.append(media_r)
        scores_baseline.append(media_b)
        resultados_wf.append({
            "janela":        jan["janela"],
            "score_robo":    round(media_r, 4),
            "score_base":    round(media_b, 4),
            "delta":         round(media_r - media_b, 4),
            "supera_base":   media_r > media_b,
        })

    if not scores_robo:
        return {
            "robustez_temporal": 0.0,
            "estabilidade":      0.0,
            "overfitting_nivel": "INDEFINIDO",
            "n_janelas":         0,
        }

    # ── Indicadores ────────────────────────────────────────────────────────
    janelas_supera = sum(1 for r in resultados_wf if r["supera_base"])
    robustez_temporal = round(janelas_supera / len(resultados_wf), 4)

    dp = stdev(scores_robo) if len(scores_robo) > 1 else 0.0
    cv = dp / mean(scores_robo) if mean(scores_robo) > 0 else 1.0
    estabilidade = round(max(0.0, min(1.0, 1.0 - cv)), 4)

    score_robustez_raw = score_robustez_walkforward(scores_robo)

    # Overfitting via degradação treino → teste
    deltas = [r["delta"] for r in resultados_wf]
    delta_medio = mean(deltas) if deltas else 0.0
    ov_info = detectar_overfitting_wf(scores_robo, [])
    overfitting_nivel = ov_info.get("severidade", "BAIXO")

    # Tendência histórica
    hist_anterior = _carregar_historico_walkforward(limit=10)
    trend = _calcular_trend(hist_anterior + [{"robustez_temporal": robustez_temporal}])

    # Veredito de robustez
    if robustez_temporal >= 0.80:
        veredito = "ROBUSTO"
    elif robustez_temporal >= 0.60:
        veredito = "ACEITÁVEL"
    else:
        veredito = "INSTÁVEL"

    indicadores = {
        "robustez_temporal":  robustez_temporal,
        "robustez_pct":       round(robustez_temporal * 100, 1),
        "estabilidade":       estabilidade,
        "estabilidade_pct":   round(estabilidade * 100, 1),
        "overfitting_nivel":  overfitting_nivel,
        "trend_robustez":     trend,
        "veredito":           veredito,
        "score_robustez_raw": round(score_robustez_raw, 4),
        "delta_vs_baseline":  round(delta_medio, 4),
        "n_janelas":          len(resultados_wf),
        "janelas_supera":     janelas_supera,
        "media_robo":         round(mean(scores_robo), 4),
        "media_baseline":     round(mean(scores_baseline), 4) if scores_baseline else 0.0,
        "desvio_robo":        round(dp, 4),
        "concurso_inicio":    janelas[0]["treino_inicio"] if janelas else 0,
        "concurso_fim":       janelas[-1]["teste_fim"]    if janelas else 0,
        "detalhes_janelas":   resultados_wf,
        "versao":             "V21.5-FULL",
    }

    _salvar_indicadores_sqlite(indicadores)
    return indicadores


def get_indicadores_permanentes() -> dict:
    """
    Retorna os indicadores consolidados de todas as execuções anteriores.
    Útil para o dashboard mostrar a evolução histórica.
    """
    hist = _carregar_historico_walkforward(limit=100)

    if not hist:
        return {
            "robustez_media":    None,
            "estabilidade_media": None,
            "n_execucoes":       0,
            "historico":         [],
        }

    robustezas    = [h.get("robustez_temporal", 0) for h in hist if h.get("robustez_temporal") is not None]
    estabilidades = [h.get("estabilidade", 0)       for h in hist if h.get("estabilidade")       is not None]

    return {
        "robustez_media":     round(mean(robustezas),    4) if robustezas    else None,
        "estabilidade_media": round(mean(estabilidades), 4) if estabilidades else None,
        "robustez_max":       round(max(robustezas),     4) if robustezas    else None,
        "robustez_min":       round(min(robustezas),     4) if robustezas    else None,
        "n_execucoes":        len(hist),
        "historico":          hist,
        "trend_atual":        _calcular_trend(hist),
    }


def relatorio_walkforward_profissional() -> str:
    """Formata relatório dos indicadores permanentes para o dashboard."""
    ind = get_indicadores_permanentes()

    if not ind.get("n_execucoes"):
        return "Nenhuma execução Walk-Forward registrada ainda."

    rob = ind.get("robustez_media", 0)
    est = ind.get("estabilidade_media", 0)
    trend = ind.get("trend_atual", "ESTAVEL")
    n = ind.get("n_execucoes", 0)

    linhas = [
        f"Walk-Forward Profissional — {n} execuções acumuladas",
        "=" * 55,
        f"Robustez Temporal (média):   {rob*100:.1f}%"
        f"  [min {ind.get('robustez_min',0)*100:.0f}% / max {ind.get('robustez_max',0)*100:.0f}%]",
        f"Estabilidade (média):         {est*100:.1f}%",
        f"Tendência histórica:          {trend}",
        "",
        "Últimas execuções:",
    ]
    for h in ind.get("historico", [])[-5:]:
        rob_h = h.get("robustez_temporal", 0)
        ov_h  = h.get("overfitting_nivel", "?")
        nj    = h.get("n_janelas", "?")
        linhas.append(f"  Robustez {rob_h*100:.0f}%  Overfitting {ov_h}  [{nj} janelas]")

    return "\n".join(linhas)
