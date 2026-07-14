
from collections import Counter

def detectar_cenario(metricas=None):
    metricas = metricas or {}

    repeticao = metricas.get("repeticao", 0)
    pares = metricas.get("pares", 0)
    dispersao = metricas.get("dispersao", 0)

    if repeticao >= 9:
        return {"cenario": "alta_repeticao"}

    if pares >= 10:
        return {"cenario": "tendencia_pares"}

    if dispersao > 0.75:
        return {"cenario": "caotico"}

    return {"cenario": "estavel"}


def selecionar_modelos(cenario):
    mapa = {
        "estavel": ["estatistico", "bayesiano", "neural_leve"],
        "caotico": ["cobertura", "genetico", "markov"],
        "tendencia_pares": ["markov", "tendencia", "estatistico"],
        "alta_repeticao": ["markov", "bayesiano", "tendencia"],
    }
    return mapa.get(cenario, ["estatistico", "bayesiano"])


def ajustar_pesos_por_cenario(pesos, cenario):
    ativos = selecionar_modelos(cenario)

    novos = {}
    for nome, peso in pesos.items():
        novos[nome] = peso * (1.25 if nome in ativos else 0.75)

    soma = sum(novos.values()) or 1.0
    return {k: v/soma for k, v in novos.items()}


def registrar_performance_cenario(cenario, resultado):
    return {
        "cenario": cenario,
        "resultado": resultado
    }
