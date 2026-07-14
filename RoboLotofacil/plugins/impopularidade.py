"""
plugins/impopularidade.py
--------------------------
Plugin de impopularidade: prioriza dezenas menos frequentes
para reduzir chances de rateio em caso de acerto alto.

Interface obrigatória:
    NOME, DESCRICAO, aplicar(jogos, historico, config) -> list
"""

from collections import Counter

NOME = "impopularidade"
DESCRICAO = "Prioriza dezenas menos frequentes para reduzir rateio"


def aplicar(jogos: list, historico: list, config: dict) -> list:
    if not historico or not jogos:
        return jogos

    janela = config.get("janela", 60)
    recente = historico[-janela:]

    contador: Counter = Counter()
    for concurso in recente:
        if isinstance(concurso, (list, tuple)):
            for d in concurso:
                contador[int(d)] += 1

    if not contador:
        return jogos

    # Quanto menos frequente, maior a pontuação de impopularidade
    max_freq = max(contador.values()) if contador else 1

    def pontuacao_impopularidade(jogo: list) -> float:
        return sum(max_freq - contador.get(int(d), 0) for d in jogo)

    return sorted(jogos, key=pontuacao_impopularidade, reverse=True)
