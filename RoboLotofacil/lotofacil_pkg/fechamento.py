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

FECHAMENTO REDUZIDO (desde 2026-08-08 — ver ARQUITETURA.md):

    Além da garantia total acima, este módulo também implementa
    fechamentos REDUZIDOS — o desenho combinatório clássico conhecido na
    literatura de loteria como wheel "m-k-t-g": em vez de jogar TODAS as
    C(m,k) combinações, joga-se um subconjunto bem menor, construído para
    garantir que:

        SE pelo menos `t` das dezenas sorteadas estiverem dentro do
        grupo de `m` escolhidas, então GARANTIDAMENTE pelo menos UM jogo
        do fechamento acerta pelo menos `g` dessas `t` dezenas.

    Repare a diferença para a garantia total: ali a condição e a garantia
    valem para TODOS os jogos do pacote; aqui a garantia vale pra PELO
    MENOS UM jogo, e a condição é sobre `t` dezenas (não as 15 todas).
    É uma garantia mais fraca e mais condicional, mas com uma fração
    pequena do custo (ex.: m=18,k=15,t=13,g=11 usa só 5 jogos, contra
    816 da garantia total do mesmo pool).

    Construção: heurística gulosa de cobertura de conjuntos (greedy set
    cover) — não é garantida ótima (pode não ser o menor número de jogos
    possível pra aquela garantia), mas TODA garantia retornada é
    verificada por força bruta antes de ser aceita (`_verificar_garantia_reduzida()`)
    — testando literalmente todo subconjunto de `t` dezenas do pool contra
    todos os jogos construídos. Nunca confia só na construção: uma
    garantia matemática falsa seria um bug grave, não um detalhe.

    Limite prático: pool até 19 dezenas (`TAMANHO_POOL_MAXIMO_REDUZIDO`).
    A verificação exaustiva por força bruta cresce rápido com o tamanho
    do pool (C(pool, t) subconjuntos-alvo × C(pool, k) jogos candidatos
    a cada passo da construção) — m=20 já passa de 1-2 minutos em Python
    puro para várias combinações de t/g testadas; não vale o custo agora.
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
TAMANHO_POOL_MAXIMO_REDUZIDO = 19         # ver docstring do módulo — custo da verificação exaustiva


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


def _popcount(x: int) -> int:
    """int.bit_count() (Python >=3.10) com fallback pra versões mais antigas."""
    try:
        return x.bit_count()
    except AttributeError:
        return bin(x).count("1")


def _verificar_garantia_reduzida(
    pool_size: int, jogos_idx: list[tuple[int, ...]], t_garantia: int, g_garantia: int
) -> bool:
    """
    Verifica por FORÇA BRUTA que todo subconjunto de `t_garantia` posições
    (0..pool_size-1) é coberto (interseção >= g_garantia) por pelo menos
    um dos `jogos_idx`.

    Nunca pule esta verificação: é a única coisa que separa uma garantia
    matemática real de uma alegação falsa vinda de uma heurística gulosa
    que pode ter parado cedo demais ou tem um bug.
    """
    jogos_bits = [sum(1 << p for p in j) for j in jogos_idx]
    for alvo in combinations(range(pool_size), t_garantia):
        alvo_bits = sum(1 << p for p in alvo)
        if not any(_popcount(jb & alvo_bits) >= g_garantia for jb in jogos_bits):
            return False
    return True


def gerar_fechamento_reduzido(
    pool: list[int],
    tamanho_jogo: int | None = None,
    t_garantia: int = 13,
    g_garantia: int = 11,
    max_jogos: int | None = None,
) -> dict:
    """
    Gera um fechamento REDUZIDO (wheel "m-k-t-g") sobre `pool`: um
    subconjunto de jogos de `tamanho_jogo` dezenas tal que, SE pelo menos
    `t_garantia` das dezenas sorteadas estiverem dentro do pool, então
    GARANTIDAMENTE pelo menos um jogo do fechamento acerta pelo menos
    `g_garantia` dessas `t_garantia` dezenas (ver docstring do módulo
    pra a diferença em relação à garantia total).

    Construção gulosa (greedy set cover): a cada passo, escolhe o jogo
    candidato (dentre todas as C(pool, tamanho_jogo) combinações) que
    cobre o maior número de alvos (subconjuntos de t_garantia dezenas)
    ainda não cobertos, até cobrir todos. Não é garantido ser o menor
    número de jogos possível — é uma heurística — mas o resultado é
    sempre verificado por força bruta antes de retornar
    (`_verificar_garantia_reduzida`); se a verificação falhar, levanta
    RuntimeError em vez de devolver uma garantia que não é real.

    Args:
        pool: dezenas do grupo (m > tamanho_jogo).
        tamanho_jogo: tamanho de cada jogo (k). Padrão: config.TAMANHO_JOGO.
        t_garantia: quantas dezenas sorteadas precisam estar no pool para
            a garantia valer (t <= m).
        g_garantia: quantas dessas t_garantia dezenas algum jogo garante
            acertar (g <= min(t_garantia, tamanho_jogo)).
        max_jogos: teto de jogos a tentar (padrão: sem teto, roda até
            cobrir tudo ou esgotar candidatos). Se o teto for atingido
            sem cobertura completa, levanta ValueError — não devolve um
            fechamento com garantia incompleta silenciosamente.

    Returns:
        Dict com "jogos", "qtd_jogos", "pool", "tamanho_jogo",
        "t_garantia", "g_garantia", "garantia_verificada" (sempre True
        se a função retornar sem erro).
    """
    if tamanho_jogo is None:
        tamanho_jogo = _cfg.TAMANHO_JOGO
    pool = sorted(set(int(n) for n in pool))
    m = len(pool)
    k = tamanho_jogo

    if not all(1 <= n <= 25 for n in pool):
        raise ValueError("Pool de fechamento contém dezena fora do intervalo 1–25.")
    if m <= k:
        raise ValueError(f"Pool precisa ter mais de {k} dezenas para formar um fechamento (recebido: {m}).")
    if m > TAMANHO_POOL_MAXIMO_REDUZIDO:
        raise ValueError(
            f"Pool de {m} dezenas acima do limite prático de fechamento reduzido "
            f"({TAMANHO_POOL_MAXIMO_REDUZIDO} — ver docstring do módulo)."
        )
    if not (1 <= t_garantia <= m):
        raise ValueError(f"t_garantia precisa estar entre 1 e {m} (recebido: {t_garantia}).")
    if not (1 <= g_garantia <= min(t_garantia, k)):
        raise ValueError(
            f"g_garantia precisa estar entre 1 e min(t_garantia, tamanho_jogo)="
            f"{min(t_garantia, k)} (recebido: {g_garantia})."
        )

    posicoes = list(range(m))
    alvos_idx = list(combinations(posicoes, t_garantia))
    alvos_bits = [sum(1 << p for p in a) for a in alvos_idx]
    candidatos_idx = list(combinations(posicoes, k))
    candidatos_bits = [sum(1 << p for p in c) for c in candidatos_idx]

    nao_cobertos = list(range(len(alvos_bits)))
    selecionados: list[tuple[int, ...]] = []
    limite = max_jogos if max_jogos is not None else len(candidatos_idx)

    while nao_cobertos and len(selecionados) < limite:
        melhor_i = -1
        melhor_cobertura = -1
        melhor_cobertos_agora: list[int] = []
        for ci, cbits in enumerate(candidatos_bits):
            cobertos_agora = [ai for ai in nao_cobertos if _popcount(cbits & alvos_bits[ai]) >= g_garantia]
            if len(cobertos_agora) > melhor_cobertura:
                melhor_cobertura = len(cobertos_agora)
                melhor_i = ci
                melhor_cobertos_agora = cobertos_agora
        if melhor_i < 0 or melhor_cobertura <= 0:
            break
        selecionados.append(candidatos_idx[melhor_i])
        cobertos_set = set(melhor_cobertos_agora)
        nao_cobertos = [a for a in nao_cobertos if a not in cobertos_set]

    if nao_cobertos:
        raise ValueError(
            f"Não foi possível atingir a garantia t={t_garantia}/g={g_garantia} para "
            f"pool={m}/jogo={k} dentro do limite de {limite} jogos "
            f"({len(nao_cobertos)} de {len(alvos_bits)} alvos ficaram descobertos)."
        )

    if not _verificar_garantia_reduzida(m, selecionados, t_garantia, g_garantia):
        raise RuntimeError(
            "Falha na verificação exaustiva da garantia do fechamento reduzido -- "
            "bug na construção, não confie neste resultado."
        )

    jogos = [sorted(pool[p] for p in c) for c in selecionados]
    return {
        "pool": pool,
        "jogos": jogos,
        "qtd_jogos": len(jogos),
        "tamanho_jogo": k,
        "t_garantia": t_garantia,
        "g_garantia": g_garantia,
        "garantia_verificada": True,
    }


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


def gerar_apostas_fechamento_reduzido(
    concursos_completos: list,
    tamanho_pool: int = 18,
    janela_analise: int = 120,
    tamanho_jogo: int | None = None,
    t_garantia: int = 13,
    g_garantia: int = 11,
    max_jogos: int | None = None,
) -> dict:
    """
    Pipeline completo do fechamento REDUZIDO: escolhe o pool pelo ranking
    do ensemble multi-IA (mesma lógica de `gerar_apostas_fechamento`) e
    gera um fechamento reduzido "m-k-t-g" sobre esse pool (ver docstring
    do módulo e de `gerar_fechamento_reduzido`).

    Retorna um dict com jogos, pool, t_garantia, g_garantia, quantidade
    de jogos, o tamanho_jogo efetivo e a análise/ensemble usados pra
    escolher o pool (auditoria) -- mesmo formato de
    `gerar_apostas_fechamento`, mais os campos específicos do reduzido.
    """
    if tamanho_jogo is None:
        tamanho_jogo = _cfg.TAMANHO_JOGO
    minimo = tamanho_pool_minimo(tamanho_jogo)
    if not (minimo <= tamanho_pool <= TAMANHO_POOL_MAXIMO_REDUZIDO):
        raise ValueError(
            f"tamanho_pool deve estar entre {minimo} e {TAMANHO_POOL_MAXIMO_REDUZIDO} "
            f"para fechamento reduzido com tamanho_jogo={tamanho_jogo} (recebido: {tamanho_pool})."
        )
    pool, analise = escolher_pool_por_ranking(concursos_completos, tamanho_pool=tamanho_pool, janela_analise=janela_analise)
    resultado_reduzido = gerar_fechamento_reduzido(
        pool, tamanho_jogo=tamanho_jogo, t_garantia=t_garantia, g_garantia=g_garantia, max_jogos=max_jogos
    )
    return {
        "pool": pool,
        "tamanho_pool": tamanho_pool,
        "tamanho_jogo": tamanho_jogo,
        "jogos": resultado_reduzido["jogos"],
        "qtd_jogos": resultado_reduzido["qtd_jogos"],
        "t_garantia": t_garantia,
        "g_garantia": g_garantia,
        "garantia_verificada": resultado_reduzido["garantia_verificada"],
        "analise": analise,
    }
