"""
plugins/frequencia.py
----------------------
Plugin de frequência: filtra jogos priorizando dezenas
que aparecem com frequência acima da média no histórico recente.

Interface obrigatória:
    NOME, DESCRICAO, aplicar(jogos, historico, config) -> list
"""

from collections import Counter

NOME = "frequencia"
DESCRICAO = "Filtra jogos priorizando dezenas frequentes no histórico recente"


def aplicar(jogos: list, historico: list, config: dict) -> list:
    """
    Pontua cada jogo pela soma das frequências das dezenas.
    Retorna os jogos ordenados por maior pontuação (sem descartar nenhum).
    """
    if not historico or not jogos:
        return jogos

    janela = config.get("janela", 60)
    recente = historico[-janela:]

    # Contar frequência de cada dezena
    contador: Counter = Counter()
    for concurso in recente:
        if isinstance(concurso, (list, tuple)):
            for d in concurso:
                contador[int(d)] += 1

    if not contador:
        return jogos

    # Pontuar cada jogo
    def pontuacao(jogo: list) -> float:
        return sum(contador.get(int(d), 0) for d in jogo)

    return sorted(jogos, key=pontuacao, reverse=True)
