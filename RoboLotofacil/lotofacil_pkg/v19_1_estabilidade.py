"""
lotofacil_pkg/v19_1_estabilidade.py
-------------------------------------
Score composto de estabilidade do pacote de apostas.

Conceito
--------
"Estabilidade" mede a consistência do robô ao longo do tempo:
um robô estável acerta muitos concursos em faixas medianas (11-12 pontos)
sem depender de picos isolados para inflar a média.

Funções exportadas:
  score_estabilidade    — score escalar [0, 1] a partir de métricas resumidas
  analisar_estabilidade — análise detalhada a partir de lista de registros
  classificar_estabilidade — converte score em label legível
"""
from statistics import mean, stdev
from typing import Any


def score_estabilidade(
    media: float,
    estabilidade: float,
    taxa11: float,
) -> float:
    """
    Combina três métricas em um único score composto [0, 1].

    Args:
        media:        média de acertos por jogo (escala 0-15).
                      Normalizado internamente para [0, 1] dividindo por 15.
        estabilidade: índice de consistência [0, 1], onde 1 = sem variância.
                      Pode ser derivado de (1 - desvio_normalizado).
        taxa11:       fração de jogos com 11+ acertos no período [0, 1].

    Returns:
        Score composto: media*0.5 + estabilidade*0.3 + taxa11*0.2
        Resultado clipado para [0.0, 1.0].
    """
    media_norm = max(0.0, min(1.0, media / 15.0))
    estab_norm = max(0.0, min(1.0, float(estabilidade)))
    taxa_norm = max(0.0, min(1.0, float(taxa11)))
    raw = media_norm * 0.5 + estab_norm * 0.3 + taxa_norm * 0.2
    return round(max(0.0, min(1.0, raw)), 6)


def analisar_estabilidade(registros: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calcula métricas de estabilidade a partir de registros de desempenho.

    Cada registro deve conter ao menos ``"media_acertos"`` e/ou
    ``"melhor_acerto"`` (os mesmos campos gravados por
    ``registrar_resultado_aprendizado``).

    Args:
        registros: lista de dicts de desempenho (últimos N concursos).

    Returns:
        Dict com:
          - ``media``: média de acertos por jogo no período
          - ``desvio``: desvio padrão das médias (0.0 se menos de 2 registros)
          - ``indice_estabilidade``: 1 - desvio_normalizado ∈ [0, 1]
          - ``taxa_11_mais``: fração de jogos com melhor_acerto >= 11
          - ``taxa_14_mais``: fração de jogos com melhor_acerto >= 14
          - ``score``: score composto via score_estabilidade()
          - ``total_registros``: quantidade de registros analisados
    """
    if not registros:
        return {
            "media": 0.0,
            "desvio": 0.0,
            "indice_estabilidade": 0.0,
            "taxa_11_mais": 0.0,
            "taxa_14_mais": 0.0,
            "score": 0.0,
            "total_registros": 0,
        }

    medias = [float(r.get("media_acertos", 0.0)) for r in registros]
    melhores = [float(r.get("melhor_acerto", 0.0)) for r in registros]
    n = len(registros)

    media = mean(medias)
    desvio = stdev(medias) if n >= 2 else 0.0

    # Normaliza desvio pela escala máxima possível (15 acertos) para [0, 1]
    desvio_norm = min(1.0, desvio / 15.0)
    indice_estabilidade = round(1.0 - desvio_norm, 6)

    taxa_11 = sum(1 for m in melhores if m >= 11) / n
    taxa_14 = sum(1 for m in melhores if m >= 14) / n

    score = score_estabilidade(media, indice_estabilidade, taxa_11)

    return {
        "media": round(media, 4),
        "desvio": round(desvio, 4),
        "indice_estabilidade": indice_estabilidade,
        "taxa_11_mais": round(taxa_11, 4),
        "taxa_14_mais": round(taxa_14, 4),
        "score": score,
        "total_registros": n,
    }


def classificar_estabilidade(score: float) -> str:
    """
    Converte um score numérico em rótulo legível pelo usuário.

    Args:
        score: valor em [0, 1] retornado por score_estabilidade().

    Returns:
        Uma das strings: "EXCELENTE", "BOA", "REGULAR", "FRACA", "INSUFICIENTE"
    """
    if score >= 0.75:
        return "EXCELENTE"
    if score >= 0.60:
        return "BOA"
    if score >= 0.45:
        return "REGULAR"
    if score >= 0.30:
        return "FRACA"
    return "INSUFICIENTE"
