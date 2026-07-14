"""
lotofacil_pkg/v21_0_auto_poda.py
----------------------------------
V21.1-C — Auto-Poda Adaptativa integrada ao histórico SQLite.

Substitui limiares fixos por limiares calculados dinamicamente
a partir da distribuição histórica de acertos persistida no banco.
Compatível com a interface anterior (calcular_limiares).
"""

import json
from .v21_0_sqlite import get_db, db_limiar_dinamico, db_prob_recuperacao


# ── Interface legada (compatibilidade V20) ────────────────────────────────────

def calcular_limiares(scores: list) -> tuple[float, float]:
    """
    Interface original mantida para compatibilidade.
    Agora usa limiar dinâmico do SQLite quando há histórico suficiente;
    caso contrário, usa o cálculo original por média.
    """
    limiar_db = db_limiar_dinamico(percentil=20.0)

    if limiar_db > 0:
        # Converte de escala de acertos (9–13) para escala de score (0–1)
        # score = (media_acertos - 9) / 4
        limiar_score = max(0.0, min(1.0, (limiar_db - 9.0) / 4.0))
        ativo      = round(limiar_score + 0.20, 4)
        observacao = round(limiar_score, 4)
        return ativo, observacao

    # Fallback: cálculo original
    if not scores:
        return 0.70, 0.50
    media      = sum(scores) / len(scores)
    ativo      = min(0.90, media + 0.10)
    observacao = max(0.30, media - 0.10)
    return ativo, observacao


# ── API adaptativa nova ───────────────────────────────────────────────────────

def calcular_limiar_percentil(percentil: float = 20.0) -> float:
    """
    Limiar de poda baseado no percentil P20 do histórico de acertos.
    Retorna 0.0 se histórico insuficiente.
    """
    return db_limiar_dinamico(percentil)


def suavizar_limiar(limiar_novo: float, limiar_anterior: float,
                    alpha: float = 0.30) -> float:
    """
    Suavização exponencial para evitar oscilações bruscas.
    alpha = 0.30 → 30% novo, 70% histórico.
    """
    return round(alpha * limiar_novo + (1 - alpha) * limiar_anterior, 6)


def decidir_poda_adaptativa(nome: str, score_global: float,
                             limiar_prob: float = 0.30) -> dict:
    """
    Decide se um modelo deve ser podado usando:
      1. Limiar dinâmico calculado do histórico SQLite
      2. Probabilidade de recuperação do histórico de eventos SQLite

    Retorna dict com a decisão e os fatores utilizados.
    """
    limiar = calcular_limiar_percentil()
    prob   = db_prob_recuperacao(nome)

    # Converte score_global (0–1) para escala de acertos para comparar
    score_acertos = 9.0 + score_global * 4.0

    abaixo_limiar     = limiar > 0 and score_acertos < limiar
    baixa_recuperacao = prob < limiar_prob
    podar             = abaixo_limiar and baixa_recuperacao

    return {
        "nome":              nome,
        "score_global":      round(score_global, 4),
        "score_acertos":     round(score_acertos, 4),
        "limiar_dinamico":   round(limiar, 4),
        "prob_recuperacao":  round(prob, 4),
        "abaixo_limiar":     abaixo_limiar,
        "baixa_recuperacao": baixa_recuperacao,
        "decisao":           "PODAR" if podar else "MANTER",
    }


def relatorio_auto_poda() -> list[dict]:
    """
    Gera relatório completo de poda adaptativa para todos os modelos
    com histórico no banco de eventos.
    """
    conn = get_db()
    model_ids = conn.execute("""
        SELECT DISTINCT model_id FROM historico_eventos
        WHERE model_id IS NOT NULL
    """).fetchall()

    resultados = []
    for row in model_ids:
        mid = row["model_id"]
        # score aproximado via histórico de acertos do modelo
        rows_acertos = conn.execute("""
            SELECT payload FROM historico_eventos
            WHERE model_id = ? AND evento IN ('suspensão','observacao','ativo')
            ORDER BY criado_em DESC LIMIT 10
        """, (mid,)).fetchall()

        scores_raw = []
        for r in rows_acertos:
            try:
                p = json.loads(r["payload"] or "{}")
                if "score" in p:
                    scores_raw.append(float(p["score"]))
            except Exception:
                pass

        score_g = (sum(scores_raw) / len(scores_raw)) if scores_raw else 0.5
        resultados.append(decidir_poda_adaptativa(mid, score_g))

    return resultados
