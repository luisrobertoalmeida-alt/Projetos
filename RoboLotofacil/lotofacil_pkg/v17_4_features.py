"""
lotofacil_pkg/v17_4_features.py
---------------------------------
Engenharia de características introduzidas na V17.4.

Funções exportadas:
  split_temporal    — divide o histórico em treino / validação / teste
  redundancia_media — sobreposição média entre os jogos de um pacote
  cobertura_pares   — quantidade de pares distintos cobertos pelo pacote
  cobertura_trios   — quantidade de trios distintos cobertos pelo pacote
"""
from itertools import combinations


def split_temporal(
    concursos: list[list[int]],
) -> tuple[list[list[int]], list[list[int]], list[list[int]]]:
    """
    Divide o histórico em três faixas temporais sem sobreposição.

    Proporções fixas:
      - treino:    70 % dos concursos mais antigos
      - validação: 15 % seguintes
      - teste:     15 % mais recentes

    Args:
        concursos: lista de jogos ordenados do mais antigo para o mais recente.

    Returns:
        Tripla ``(treino, validacao, teste)``.
    """
    n = len(concursos)
    corte_treino = int(n * 0.70)
    corte_validacao = int(n * 0.85)
    treino = concursos[:corte_treino]
    validacao = concursos[corte_treino:corte_validacao]
    teste = concursos[corte_validacao:]
    return treino, validacao, teste


def redundancia_media(jogos: list[list[int]]) -> float:
    """
    Calcula a sobreposição média (intersecção) entre todos os pares de jogos.

    Valores altos indicam pacotes redundantes; valores baixos indicam boa
    diversidade. Para a Lotofácil, um pacote saudável costuma ter
    redundância média entre 8 e 11.

    Args:
        jogos: lista de jogos (cada jogo é uma lista de 15 dezenas).

    Returns:
        Média das intersecções entre todos os pares, ou 0.0 se menos de
        dois jogos forem fornecidos.
    """
    if len(jogos) < 2:
        return 0.0

    interseccoes = []
    for i, jogo_a in enumerate(jogos):
        set_a = set(jogo_a)
        for jogo_b in jogos[i + 1:]:
            interseccoes.append(len(set_a & set(jogo_b)))

    return sum(interseccoes) / len(interseccoes) if interseccoes else 0.0


def cobertura_pares(jogos: list[list[int]]) -> int:
    """
    Conta quantos pares distintos de dezenas são cobertos pelo pacote.

    O máximo teórico para a Lotofácil (25 dezenas) é C(25,2) = 300 pares.

    Args:
        jogos: lista de jogos.

    Returns:
        Número de pares (d_i, d_j) com d_i < d_j presentes em ao menos
        um jogo do pacote.
    """
    pares_cobertos: set[tuple[int, int]] = set()
    for jogo in jogos:
        for par in combinations(sorted(jogo), 2):
            pares_cobertos.add(par)
    return len(pares_cobertos)


def cobertura_trios(jogos: list[list[int]]) -> int:
    """
    Conta quantos trios distintos de dezenas são cobertos pelo pacote.

    O máximo teórico para a Lotofácil é C(25,3) = 2.300 trios.

    Args:
        jogos: lista de jogos.

    Returns:
        Número de trios (d_i, d_j, d_k) com d_i < d_j < d_k presentes
        em ao menos um jogo do pacote.
    """
    trios_cobertos: set[tuple[int, int, int]] = set()
    for jogo in jogos:
        for trio in combinations(sorted(jogo), 3):
            trios_cobertos.add(trio)
    return len(trios_cobertos)
