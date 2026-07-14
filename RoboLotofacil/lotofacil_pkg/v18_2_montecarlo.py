
import random
from collections import Counter

def executar_monte_carlo(ranking_dezenas, n_simulacoes=10000):
    contador = Counter()

    if not ranking_dezenas:
        return {}

    dezenas = list(ranking_dezenas.keys())
    pesos = [max(0.0001, float(v)) for v in ranking_dezenas.values()]

    for _ in range(n_simulacoes):
        sorteadas = random.choices(dezenas, weights=pesos, k=15)
        for d in set(sorteadas):
            contador[d] += 1

    total = max(1, n_simulacoes)

    return {
        dezena: round(contador[dezena] / total, 6)
        for dezena in dezenas
    }

def classificar_heatmap(scores):
    resultado = {}

    for dezena, score in scores.items():
        if score >= 0.80:
            resultado[dezena] = "ELITE"
        elif score >= 0.60:
            resultado[dezena] = "FORTE"
        elif score >= 0.40:
            resultado[dezena] = "NEUTRA"
        elif score >= 0.20:
            resultado[dezena] = "FRACA"
        else:
            resultado[dezena] = "EVITAR"

    return resultado

def calcular_consenso(modelos_por_dezena):
    return {
        dezena: len(modelos)
        for dezena, modelos in modelos_por_dezena.items()
    }
