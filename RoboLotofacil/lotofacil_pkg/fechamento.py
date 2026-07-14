"""
lotofacil_pkg/fechamento.py — MÓDULO EXPERIMENTAL (v1)
--------------------------------------------------------
Fechamento combinatório (wheeling system) de garantia total.

Diferente do ensemble genético (`genetico.py`/`apostas.py`), que otimiza
heuristicamente a diversidade/cobertura de um pacote de jogos independentes,
o fechamento de garantia total é uma técnica puramente combinatória, com
garantia MATEMÁTICA (não estatística, não aproximada):

    Escolha um grupo ("pool") de `m` dezenas (m > 15). Jogue TODAS as
    C(m, 15) combinações possíveis de 15 dezenas dentro desse grupo.

    SE as 15 dezenas sorteadas estiverem TODAS dentro do seu grupo de `m`
    escolhidas, então, garantidamente:
        - o jogo que exclui exatamente as (m-15) dezenas do grupo que NÃO
          saíram acerta os 15 pontos (o pacote inteiro contém a aposta
          vencedora);
        - todos os demais jogos do fechamento acertam pelo menos
          `30 - m` pontos.

Números de jogos e garantia mínima por tamanho de grupo (m):

    m=16 ->    16 jogos  | garantia mínima: 14 pontos
    m=17 ->   136 jogos  | garantia mínima: 13 pontos
    m=18 ->   816 jogos  | garantia mínima: 12 pontos
    m=19 -> 3.876 jogos  | garantia mínima: 11 pontos
    m=20 -> 15.504 jogos | garantia mínima: 10 pontos

IMPORTANTE — o que essa garantia NÃO significa:
    A garantia é condicional: só vale SE as 15 dezenas sorteadas estiverem
    todas dentro do grupo de `m` escolhidas. Escolher esse grupo continua
    sendo uma aposta — o fechamento não aumenta a chance de acertar quais
    dezenas vão sair, apenas redistribui o resultado: em vez de uma chance
    pequena de acertar muito em UM jogo, você tem a mesma chance de acertar
    o grupo, mas premiada em VÁRIOS jogos simultaneamente (ou em nenhum).
    Isto é matematicamente neutro em valor esperado — é a natureza de
    qualquer sistema de fechamento, aqui ou em qualquer outro lugar.

Este módulo cobre apenas o fechamento de GARANTIA TOTAL (todas as
combinações do grupo). Fechamentos "reduzidos" (menos jogos, garantia
condicionada a menos dezenas acertadas dentro do grupo) são desenhos
combinatórios conhecidos na literatura de loteria, mas não estão
implementados aqui — ver ARQUITETURA.md.
"""
from __future__ import annotations

from itertools import combinations
from math import comb

from .config import NUMEROS, TAMANHO_JOGO
from .historico import analisar_historico
from .analise import calcular_motor_estrategico, calcular_ensemble_multi_ia
from .genetico import recortar_historico_para_analise


TAMANHO_POOL_MINIMO = TAMANHO_JOGO + 1   # 16
TAMANHO_POOL_MAXIMO = 20                  # C(20,15) = 15.504 jogos — já é um limite prático alto


def qtd_jogos_fechamento(tamanho_pool: int, tamanho_jogo: int = TAMANHO_JOGO) -> int:
    """Quantidade exata de jogos de um fechamento de garantia total: C(tamanho_pool, tamanho_jogo)."""
    return comb(tamanho_pool, tamanho_jogo)


def garantia_minima(tamanho_pool: int, tamanho_jogo: int = TAMANHO_JOGO) -> int:
    """
    Pontuação mínima garantida SE as `tamanho_jogo` dezenas sorteadas
    estiverem todas dentro do pool. Fórmula: tamanho_jogo - (tamanho_pool - tamanho_jogo),
    ou seja, 2*tamanho_jogo - tamanho_pool (para Lotofácil: 30 - tamanho_pool).
    """
    return 2 * tamanho_jogo - tamanho_pool


def gerar_fechamento_garantia_total(pool: list[int], tamanho_jogo: int = TAMANHO_JOGO) -> list[list[int]]:
    """
    Gera TODAS as combinações de `tamanho_jogo` dezenas dentro de `pool`.

    Levanta ValueError se o pool for pequeno demais (nenhuma garantia real,
    é só um jogo) ou grande demais (explosão combinatória impraticável).
    """
    pool = sorted(set(int(n) for n in pool))
    if not all(1 <= n <= 25 for n in pool):
        raise ValueError("Pool de fechamento contém dezena fora do intervalo 1–25.")
    if len(pool) <= tamanho_jogo:
        raise ValueError(
            f"Pool precisa ter mais de {tamanho_jogo} dezenas para formar um fechamento "
            f"(recebido: {len(pool)})."
        )
    if len(pool) > TAMANHO_POOL_MAXIMO:
        raise ValueError(
            f"Pool de {len(pool)} dezenas geraria {qtd_jogos_fechamento(len(pool), tamanho_jogo):,} "
            f"jogos — acima do limite prático de {TAMANHO_POOL_MAXIMO} dezenas "
            f"({qtd_jogos_fechamento(TAMANHO_POOL_MAXIMO, tamanho_jogo):,} jogos)."
        )
    return [sorted(c) for c in combinations(pool, tamanho_jogo)]


def escolher_pool_por_ranking(concursos_completos: list, tamanho_pool: int = 16, janela_analise: int = 120) -> tuple[list[int], dict]:
    """
    Escolhe o pool de `tamanho_pool` dezenas a partir do ranking do ensemble
    multi-IA já existente (mesma análise usada por `gerar_apostas`), em vez
    de um pool arbitrário/manual.

    Retorna (pool, analise) — `analise` inclui a análise completa e o
    ensemble, para transparência/auditoria de por que essas dezenas foram
    escolhidas.
    """
    concursos = recortar_historico_para_analise(concursos_completos, janela_analise)
    analise = analisar_historico(concursos, janela=min(janela_analise, len(concursos)))
    estrategia = calcular_motor_estrategico(analise, qtd_jogos=tamanho_pool, janela=janela_analise)
    analise["estrategia"] = estrategia
    ensemble = calcular_ensemble_multi_ia(concursos, analise, estrategia=estrategia)
    analise["ensemble"] = ensemble

    ranking = ensemble["ranking"]  # lista [(dezena, peso), ...] já ordenada desc.
    pool = sorted(int(n) for n, _ in ranking[:tamanho_pool])
    return pool, analise


def gerar_apostas_fechamento(concursos_completos: list, tamanho_pool: int = 16, janela_analise: int = 120) -> dict:
    """
    Pipeline completo: escolhe o pool pelo ranking do ensemble multi-IA e
    gera o fechamento de garantia total sobre esse pool.

    Retorna um dict com jogos, pool, garantia mínima, quantidade de jogos
    e a análise/ensemble usados para escolher o pool (auditoria).
    """
    if not (TAMANHO_POOL_MINIMO <= tamanho_pool <= TAMANHO_POOL_MAXIMO):
        raise ValueError(
            f"tamanho_pool deve estar entre {TAMANHO_POOL_MINIMO} e {TAMANHO_POOL_MAXIMO} "
            f"(recebido: {tamanho_pool})."
        )
    pool, analise = escolher_pool_por_ranking(concursos_completos, tamanho_pool=tamanho_pool, janela_analise=janela_analise)
    jogos = gerar_fechamento_garantia_total(pool)
    return {
        "pool": pool,
        "tamanho_pool": tamanho_pool,
        "jogos": jogos,
        "qtd_jogos": len(jogos),
        "garantia_minima": garantia_minima(tamanho_pool),
        "analise": analise,
    }
