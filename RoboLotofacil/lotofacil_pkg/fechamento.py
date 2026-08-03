"""
lotofacil_pkg/fechamento.py — MÓDULO EXPERIMENTAL (v1)
--------------------------------------------------------
Fechamento combinatório (wheeling system) de garantia total.

Diferente do ensemble genético (`genetico.py`/`apostas.py`), que otimiza
heuristicamente a diversidade/cobertura de um pacote de jogos independentes,
o fechamento de garantia total é uma técnica puramente combinatória, com
garantia MATEMÁTICA (não estatística, não aproximada):

    Escolha um grupo ("pool") de `m` dezenas (m > k, onde k = tamanho de
    cada jogo, padrão 15). Jogue TODAS as C(m, k) combinações possíveis
    de `k` dezenas dentro desse grupo.

    SE as 15 dezenas sorteadas (o sorteio real da Lotofácil SEMPRE tem
    15 dezenas, independente de `k`) estiverem TODAS dentro do seu grupo
    de `m` escolhidas, então, garantidamente:
        - pelo menos um jogo do pacote acerta os 15 pontos (o pacote
          inteiro contém a aposta vencedora);
        - todos os demais jogos do fechamento acertam pelo menos
          `k + 15 - m` pontos.

Números de jogos e garantia mínima por tamanho de grupo (m), para o caso
padrão k=15 (cada jogo com 15 dezenas — ver `garantia_minima()` para o
caso geral com `k` != 15, ex.: apostas "estendidas" de 16-18 dezenas):

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

from . import config as _cfg
from .config import NUMEROS
from .historico import analisar_historico
from .analise import calcular_motor_estrategico, calcular_ensemble_multi_ia
from .genetico import recortar_historico_para_analise


TAMANHO_POOL_MINIMO = _cfg.TAMANHO_JOGO + 1   # 16 (padrão) — ver tamanho_pool_minimo() para o valor dinâmico
TAMANHO_POOL_MAXIMO = 20                  # C(20,15) = 15.504 jogos — já é um limite prático alto


def tamanho_pool_minimo(tamanho_jogo: int | None = None) -> int:
    """Menor pool válido (tamanho_jogo + 1) para o `tamanho_jogo` efetivo (padrão: config.TAMANHO_JOGO atual)."""
    return (tamanho_jogo if tamanho_jogo is not None else _cfg.TAMANHO_JOGO) + 1


def qtd_jogos_fechamento(tamanho_pool: int, tamanho_jogo: int | None = None) -> int:
    """Quantidade exata de jogos de um fechamento de garantia total: C(tamanho_pool, tamanho_jogo)."""
    if tamanho_jogo is None:
        tamanho_jogo = _cfg.TAMANHO_JOGO
    return comb(tamanho_pool, tamanho_jogo)


def garantia_minima(tamanho_pool: int, tamanho_jogo: int | None = None) -> int:
    """
    Pontuação mínima garantida SE as `config.TAMANHO_SORTEIO` (15, fixo —
    a Lotofácil sempre sorteia 15 dezenas) dezenas sorteadas estiverem
    todas dentro do pool. Fórmula: tamanho_jogo - (tamanho_pool - TAMANHO_SORTEIO),
    ou seja, tamanho_jogo + TAMANHO_SORTEIO - tamanho_pool.

    Até 2026-08-03 essa fórmula era `2*tamanho_jogo - tamanho_pool` —
    coincide com a correta quando tamanho_jogo==15 (o único caso já usado
    de verdade, por causa do bug corrigido nesta mesma data que impedia
    tamanho_jogo != 15 de chegar até aqui), mas dava resultado ERRADO para
    tamanho_jogo != 15: confundia "tamanho de cada jogo apostado" com
    "tamanho do sorteio real", que são conceitos diferentes (ver
    ARQUITETURA.md).
    """
    if tamanho_jogo is None:
        tamanho_jogo = _cfg.TAMANHO_JOGO
    return max(0, tamanho_jogo + _cfg.TAMANHO_SORTEIO - tamanho_pool)


def gerar_fechamento_garantia_total(pool: list[int], tamanho_jogo: int | None = None) -> list[list[int]]:
    """
    Gera TODAS as combinações de `tamanho_jogo` dezenas dentro de `pool`.

    Levanta ValueError se o pool for pequeno demais (nenhuma garantia real,
    é só um jogo) ou grande demais (explosão combinatória impraticável).
    """
    if tamanho_jogo is None:
        tamanho_jogo = _cfg.TAMANHO_JOGO
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


def gerar_apostas_fechamento(concursos_completos: list, tamanho_pool: int = 16, janela_analise: int = 120, tamanho_jogo: int | None = None) -> dict:
    """
    Pipeline completo: escolhe o pool pelo ranking do ensemble multi-IA e
    gera o fechamento de garantia total sobre esse pool.

    `tamanho_jogo` (padrão: `config.TAMANHO_JOGO` atual, geralmente 15) é o
    tamanho de CADA jogo do fechamento — não confundir com `tamanho_pool`
    (o grupo maior do qual os jogos são formados). Até 2026-08-03 esse
    parâmetro nem existia aqui: `gerar_fechamento_garantia_total()` era
    chamada sem ele, então o fechamento sempre usava 15 dezenas por jogo
    mesmo quando o usuário configurava "Dezenas por jogo" para 16, 17 ou 18
    na tela — o campo era lido em `gerar_apostas()` (Gerar Jogos normal)
    mas nunca chegava até o Fechamento (achado de usuário, ver
    ARQUITETURA.md).

    Retorna um dict com jogos, pool, garantia mínima, quantidade de jogos,
    o tamanho_jogo efetivo e a análise/ensemble usados para escolher o
    pool (auditoria).
    """
    if tamanho_jogo is None:
        tamanho_jogo = _cfg.TAMANHO_JOGO
    minimo = tamanho_pool_minimo(tamanho_jogo)
    if not (minimo <= tamanho_pool <= TAMANHO_POOL_MAXIMO):
        raise ValueError(
            f"tamanho_pool deve estar entre {minimo} e {TAMANHO_POOL_MAXIMO} "
            f"para tamanho_jogo={tamanho_jogo} (recebido: {tamanho_pool})."
        )
    pool, analise = escolher_pool_por_ranking(concursos_completos, tamanho_pool=tamanho_pool, janela_analise=janela_analise)
    jogos = gerar_fechamento_garantia_total(pool, tamanho_jogo=tamanho_jogo)
    return {
        "pool": pool,
        "tamanho_pool": tamanho_pool,
        "tamanho_jogo": tamanho_jogo,
        "jogos": jogos,
        "qtd_jogos": len(jogos),
        "garantia_minima": garantia_minima(tamanho_pool, tamanho_jogo),
        "analise": analise,
    }
