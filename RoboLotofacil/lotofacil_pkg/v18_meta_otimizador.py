
from itertools import product

def gerar_combinacoes_pesos():
    grades = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    resultados = []

    for freq, bayes, markov, atraso, cobertura in product(
        grades, grades, grades, grades, grades
    ):
        soma = freq + bayes + markov + atraso + cobertura
        if abs(soma - 1.0) < 0.001:
            resultados.append({
                "frequencia": freq,
                "bayes": bayes,
                "markov": markov,
                "atraso": atraso,
                "cobertura": cobertura
            })
    return resultados

def classificar_resultados(resultados):
    return sorted(
        resultados,
        key=lambda r: (
            r.get("media", 0),
            -r.get("desvio", 999),
            -r.get("overfitting", 999)
        ),
        reverse=True
    )
