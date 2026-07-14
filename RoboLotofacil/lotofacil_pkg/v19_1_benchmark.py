"""
lotofacil_pkg/v19_1_benchmark.py
---------------------------------
Comparação e ranking de modelos por score de desempenho.

Funções exportadas:
  comparar_modelos      — ordena lista de modelos do melhor para o pior
  resumo_benchmark      — devolve dict com ranking, líder e estatísticas
  filtrar_modelos_ativos — remove modelos abaixo de um limiar mínimo de score
"""
from statistics import mean, stdev
from typing import Any


def comparar_modelos(modelos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Ordena uma lista de dicionários de modelos pelo campo ``score`` (desc).

    Cada dicionário deve conter ao menos a chave ``"score"`` (float).
    Modelos sem a chave são tratados como score=0 e ficam no final.

    Args:
        modelos: lista de dicts, ex. [{"nome": "markov", "score": 0.72}, ...]

    Returns:
        Nova lista ordenada do maior para o menor score.
    """
    return sorted(modelos, key=lambda x: float(x.get("score", 0.0)), reverse=True)


def resumo_benchmark(modelos: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Gera um resumo estatístico do benchmark de modelos.

    Args:
        modelos: lista de dicts com ao menos ``"nome"`` e ``"score"``.

    Returns:
        Dict com chaves:
          - ``ranking``: lista ordenada (mesmo resultado de comparar_modelos)
          - ``lider``: nome do modelo de maior score (ou None se lista vazia)
          - ``media_score``: média dos scores
          - ``desvio_score``: desvio padrão (0.0 se menos de 2 modelos)
          - ``total``: quantidade de modelos avaliados
    """
    if not modelos:
        return {
            "ranking": [],
            "lider": None,
            "media_score": 0.0,
            "desvio_score": 0.0,
            "total": 0,
        }

    ranking = comparar_modelos(modelos)
    scores = [float(m.get("score", 0.0)) for m in ranking]

    return {
        "ranking": ranking,
        "lider": ranking[0].get("nome") if ranking else None,
        "media_score": round(mean(scores), 6),
        "desvio_score": round(stdev(scores), 6) if len(scores) >= 2 else 0.0,
        "total": len(ranking),
    }


def filtrar_modelos_ativos(
    modelos: list[dict[str, Any]],
    limiar: float = 0.10,
) -> list[dict[str, Any]]:
    """
    Remove modelos cujo score esteja abaixo do limiar mínimo.

    Útil para desabilitar automaticamente modelos de baixo desempenho
    antes de alimentar o ensemble.

    Args:
        modelos: lista de dicts com ``"score"``.
        limiar:  score mínimo para o modelo ser mantido (padrão 0.10).

    Returns:
        Lista filtrada. Se nenhum modelo passar do limiar, devolve todos
        os modelos originais para evitar ensemble vazio.
    """
    ativos = [m for m in modelos if float(m.get("score", 0.0)) >= limiar]
    return ativos if ativos else list(modelos)


def podar_modelos_fracos(modelos, limiar=0.10):
    return [m for m in modelos if float(m.get('score',0)) >= limiar]

def contribuicao_individual(modelos):
    total = sum(float(m.get('score',0)) for m in modelos) or 1.0
    return {m.get('nome','modelo'): round(float(m.get('score',0))/total,4) for m in modelos}
