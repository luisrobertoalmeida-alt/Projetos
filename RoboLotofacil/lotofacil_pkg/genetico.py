"""
lotofacil_pkg/genetico.py
--------------------------
Algoritmo genético para geração e refinamento de apostas:
  - Pontuação estrutural (entropia, linhas, colunas, sequências)
  - Geração base ponderada por pesos do ensemble
  - Crossover, mutação adaptativa, evolução de populações
  - Refinamento agressivo e seleção por cobertura global
"""
import math
import random
import bisect
from collections import Counter
from functools import lru_cache
from statistics import mean

from . import config as _cfg
from .config import NUMEROS
from .utils import (
    contar_pares, soma_jogo, intersecao, distancia_jogos,
    formatar_jogo, limitar, rng,
)
from .v17_4_features import redundancia_media, cobertura_pares, cobertura_trios
from .v21_6_impopularidade import (
    score_impopularidade,
    PESO_IMPOPULARIDADE_PADRAO,
)


def score_linhas(jogo: list[int]) -> float:
    linhas = [0] * 5
    for n in jogo:
        linhas[(n - 1) // 5] += 1
    s = 0.0
    for q in linhas:
        if 2 <= q <= 4:
            s += 0.5
        elif q in (1, 5):
            s += 0.1
        else:
            s -= 1.0
    return s


def score_repeticao_recente(jogo: list[int], hist: list) -> float:
    penal = 0.0
    for conc in hist[-10:]:
        inter = intersecao(jogo, conc)
        if inter >= 12:
            penal -= (inter - 11) * 1.25
    return penal


def score_diversidade(jogo: list[int], jogos_existentes: list, estrategia: dict | None = None) -> float:
    if not jogos_existentes:
        return 0.0
    limite = estrategia.get("limite_intersecao", 12) if estrategia else 12
    bonus_div = estrategia.get("diversidade", 0.70) if estrategia else 0.70
    s = 0.0
    for outro in jogos_existentes:
        inter = intersecao(jogo, outro)
        dist = distancia_jogos(jogo, outro)
        if inter >= limite:
            s -= (inter - limite + 1) * (1.15 + bonus_div)
        else:
            s += min(0.9, dist / 25.0) * bonus_div
    return s


# =========================================================
# REFINAMENTO MATEMÁTICO ESTRUTURAL
# =========================================================
def distribuicao_linhas_colunas(jogo: list[int]) -> tuple[list[int], list[int]]:
    linhas = [0] * 5
    colunas = [0] * 5
    for n in sorted(set(jogo)):
        linhas[(n - 1) // 5] += 1
        colunas[(n - 1) % 5] += 1
    return linhas, colunas


def contar_sequencias_consecutivas(jogo: list[int]) -> int:
    jogo = sorted(set(jogo))
    if not jogo:
        return []
    sequencias = []
    atual = [jogo[0]]
    for n in jogo[1:]:
        if n == atual[-1] + 1:
            atual.append(n)
        else:
            if len(atual) >= 2:
                sequencias.append(atual)
            atual = [n]
    if len(atual) >= 2:
        sequencias.append(atual)
    return sequencias


def entropia_distribuicao(valores: list[int]) -> float:
    total = sum(valores)
    if total <= 0:
        return 0.0
    h = 0.0
    for v in valores:
        if v > 0:
            p = v / total
            h -= p * math.log(p, 2)
    # normaliza para 0..1 considerando 5 grupos
    return h / math.log(5, 2)


def analisar_estrutura_jogo(jogo: list[int]) -> dict:
    jogo = sorted(set(jogo))
    if len(jogo) != _cfg.TAMANHO_JOGO:
        return {
            "score_estrutural": -10**9,
            "classificacao": "inválido",
            "entropia": 0,
            "linhas": [],
            "colunas": [],
            "sequencias": 0,
            "maior_sequencia": 0,
        }

    linhas, colunas = distribuicao_linhas_colunas(jogo)
    sequencias = contar_sequencias_consecutivas(jogo)
    maior_seq = max((len(s) for s in sequencias), default=1)
    qtd_seq = len(sequencias)
    pares = contar_pares(jogo)
    soma_ = soma_jogo(jogo)

    ent_linhas = entropia_distribuicao(linhas)
    ent_colunas = entropia_distribuicao(colunas)
    entropia = round((ent_linhas + ent_colunas) / 2, 4)

    # Distribuições muito comuns e saudáveis na grade 5x5: 3-3-3-3-3, 4-3-3-3-2 e variações próximas.
    linhas_ord = sorted(linhas, reverse=True)
    colunas_ord = sorted(colunas, reverse=True)
    padroes_bons = ([3, 3, 3, 3, 3], [4, 3, 3, 3, 2], [4, 4, 3, 2, 2], [5, 3, 3, 2, 2])

    bonus_linhas = 1.2 if linhas_ord in padroes_bons else 0.4 if max(linhas) <= 5 and min(linhas) >= 1 else -1.2
    bonus_colunas = 1.2 if colunas_ord in padroes_bons else 0.4 if max(colunas) <= 5 and min(colunas) >= 1 else -1.2

    penal_seq = 0.0
    if maior_seq >= 5:
        penal_seq += (maior_seq - 4) * 1.25
    if qtd_seq >= 5:
        penal_seq += (qtd_seq - 4) * 0.35

    # Evita jogos matematicamente muito concentrados em extremos.
    baixos = sum(1 for n in jogo if n <= 8)
    medios = sum(1 for n in jogo if 9 <= n <= 17)
    altos = sum(1 for n in jogo if n >= 18)
    dispersao_blocos = [baixos, medios, altos]
    penal_bloco = max(0, max(dispersao_blocos) - 7) * 0.45

    bonus_paridade = 0.8 if 6 <= pares <= 9 else 0.15 if 5 <= pares <= 10 else -1.0
    bonus_soma = max(-1.4, 1.0 - abs(soma_ - 195) / 32.0)

    score = (
        2.2 * entropia
        + bonus_linhas
        + bonus_colunas
        + bonus_paridade
        + bonus_soma
        - penal_seq
        - penal_bloco
    )

    if score >= 4.8:
        classificacao = "estrutura forte"
    elif score >= 3.2:
        classificacao = "estrutura boa"
    elif score >= 1.6:
        classificacao = "estrutura aceitável"
    else:
        classificacao = "estrutura fraca"

    return {
        "score_estrutural": round(score, 4),
        "classificacao": classificacao,
        "entropia": entropia,
        "linhas": linhas,
        "colunas": colunas,
        "sequencias": qtd_seq,
        "maior_sequencia": maior_seq,
        "blocos": dispersao_blocos,
    }


def score_matematico_estrutural(jogo: list[int], analise: dict | None = None) -> float:
    return analisar_estrutura_jogo(jogo).get("score_estrutural", -10**9)


# Cache LRU para análise estrutural (jogos idênticos não são recalculados).
# O maxsize limita memória em sessões longas e substitui o dict global manual.
@lru_cache(maxsize=4096)
def _analisar_estrutura_jogo_cached_por_chave(chave: tuple) -> dict:
    return analisar_estrutura_jogo(list(chave))


def analisar_estrutura_jogo_cached(jogo: list[int]) -> dict:
    """Versão cacheada de analisar_estrutura_jogo para evitar recálculos no refinamento."""
    chave = tuple(sorted(set(jogo)))
    return _analisar_estrutura_jogo_cached_por_chave(chave)


# Expõe cache_clear/cache_info no wrapper usado pelo restante do programa.
analisar_estrutura_jogo_cached.cache_clear = _analisar_estrutura_jogo_cached_por_chave.cache_clear
analisar_estrutura_jogo_cached.cache_info = _analisar_estrutura_jogo_cached_por_chave.cache_info


def resumo_estrutural_pacote(jogos: list) -> dict:
    if not jogos:
        return {}
    estruturas = [analisar_estrutura_jogo(j) for j in jogos]
    scores = [e["score_estrutural"] for e in estruturas]
    entropias = [e["entropia"] for e in estruturas]
    fracos = sum(1 for e in estruturas if e["classificacao"] == "estrutura fraca")
    fortes = sum(1 for e in estruturas if e["classificacao"] in ("estrutura forte", "estrutura boa"))
    return {
        "score_estrutural_medio": round(mean(scores), 3),
        "entropia_media": round(mean(entropias), 3),
        "jogos_estrutura_forte_ou_boa": fortes,
        "jogos_estrutura_fraca": fracos,
        "classificacoes": dict(Counter(e["classificacao"] for e in estruturas)),
    }


def parametros_refinamento_agressivo(estrategia: dict | None = None) -> dict:
    """Define filtros estruturais mínimos antes da seleção final."""
    modo = (estrategia or {}).get("modo", "equilibrado")
    diversidade = float((estrategia or {}).get("diversidade", 0.75) or 0.75)
    if modo == "agressivo":
        minimo = 2.15
    elif modo == "conservador":
        minimo = 1.70
    else:
        minimo = 1.95
    if diversidade >= 0.82:
        minimo -= 0.20
    return {
        "ativo": True,
        "score_minimo": round(minimo, 3),
        "aceitar_fracos_no_fallback": False,
    }


def jogo_aprovado_refinamento_agressivo(jogo: list[int], estrategia: dict | None = None) -> bool:
    """Filtro estrutural: elimina jogos ruins antes de disputar a vaga final."""
    params = parametros_refinamento_agressivo(estrategia)
    e = analisar_estrutura_jogo_cached(jogo)
    if e.get("classificacao") == "inválido":
        return False
    if e.get("classificacao") == "estrutura fraca":
        return False
    if float(e.get("score_estrutural", -999)) < params["score_minimo"]:
        return False
    if int(e.get("maior_sequencia", 0) or 0) >= 6:
        return False
    blocos = e.get("blocos") or []
    if blocos and max(blocos) >= 9:
        return False
    linhas = e.get("linhas") or []
    colunas = e.get("colunas") or []
    if linhas and (max(linhas) >= 6 or min(linhas) == 0):
        return False
    if colunas and (max(colunas) >= 6 or min(colunas) == 0):
        return False
    return True


def filtrar_candidatos_refinamento_agressivo(candidatos: list, estrategia: dict | None = None, minimo: int = 80) -> list:
    """Filtra candidatos mantendo fallback seguro para não travar a geração."""
    aprovados, rejeitados, vistos = [], 0, set()
    for jogo in candidatos:
        t = tuple(sorted(set(jogo)))
        if len(t) != _cfg.TAMANHO_JOGO or t in vistos:
            continue
        vistos.add(t)
        if jogo_aprovado_refinamento_agressivo(list(t), estrategia):
            aprovados.append(list(t))
        else:
            rejeitados += 1
    if len(aprovados) >= minimo:
        return aprovados, {
            "ativo": True,
            "aprovados": len(aprovados),
            "rejeitados": rejeitados,
            "fallback_usado": False,
            **parametros_refinamento_agressivo(estrategia),
        }
    # Fallback: se o filtro ficou severo demais, usa os melhores candidatos por score estrutural.
    unicos = []
    vistos = set()
    for jogo in candidatos:
        t = tuple(sorted(set(jogo)))
        if len(t) == _cfg.TAMANHO_JOGO and t not in vistos:
            vistos.add(t)
            unicos.append(list(t))
    unicos = sorted(unicos, key=lambda j: analisar_estrutura_jogo_cached(j).get("score_estrutural", -10**9), reverse=True)
    return unicos, {
        "ativo": True,
        "aprovados": len(aprovados),
        "rejeitados": rejeitados,
        "fallback_usado": True,
        **parametros_refinamento_agressivo(estrategia),
    }


def score_jogo(jogo: list[int], pesos: dict, analise: dict, jogos_existentes: list | None = None, estrategia: dict | None = None) -> float:
    jogos_existentes = jogos_existentes or []
    jogo = sorted(set(jogo))
    if len(jogo) != _cfg.TAMANHO_JOGO:
        return -10**9

    pares = contar_pares(jogo)
    soma_ = soma_jogo(jogo)
    score_base = sum(pesos.get(n, 0.0) for n in jogo)

    if 6 <= pares <= 9:
        s_par = 1.2
    elif 5 <= pares <= 10:
        s_par = 0.4
    else:
        s_par = -1.6

    # .get() com padrão em vez de indexação direta: um `analise` restaurado
    # de um pacote salvo em disco (self.analise após reabrir o app) pode
    # não ter esses campos se foi salvo antes de 2026-07-26 — sem o
    # fallback, isso derrubava a tela com KeyError ao popular a aba
    # "Jogos Gerados" (ver ARQUITETURA.md).
    dist_soma = abs(soma_ - analise.get("soma_media", 195.0))
    s_soma = max(-2.0, 1.5 - dist_soma / 18.0)

    estrutural = score_matematico_estrutural(jogo, analise)
    peso_estrutural = float((estrategia or {}).get("peso_refinamento_matematico", 0.55))

    # V21.6 — impopularidade: bônus para jogos sub-apostados por humanos.
    # peso_impopularidade=0.0 desliga completamente (comportamento anterior).
    peso_impop = float((estrategia or {}).get(
        "peso_impopularidade", PESO_IMPOPULARIDADE_PADRAO
    ))
    s_impop = score_impopularidade(
        jogo,
        hist_recente=analise.get("hist_usado"),
        peso=peso_impop,
    ) if peso_impop > 0.0 else 0.0

    return (
        8.0 * score_base
        + 1.5 * s_par
        + 1.6 * s_soma
        + 1.2 * score_linhas(jogo)
        + peso_estrutural * estrutural
        + score_repeticao_recente(jogo, analise.get("hist_usado") or [])
        + score_diversidade(jogo, jogos_existentes, estrategia)
        + s_impop
    )


def sample_ponderado_sem_reposicao(numeros: list[int], pesos: dict, k: int | None = None) -> list[int]:
    if k is None:
        k = _cfg.TAMANHO_JOGO
    """Amostragem ponderada sem reposicao usando bisect (mais rapido que roleta manual)."""
    disponiveis = numeros[:]
    escolhidos = []
    while len(escolhidos) < k and disponiveis:
        pesos_lista = [max(1e-9, pesos[n]) for n in disponiveis]
        total = sum(pesos_lista)
        # Monta CDF acumulada e usa bisect para O(log n) em vez de O(n)
        acumulada = []
        acc = 0.0
        for p in pesos_lista:
            acc += p / total
            acumulada.append(acc)
        r = rng().random()
        idx = bisect.bisect_left(acumulada, r)
        idx = min(idx, len(disponiveis) - 1)
        escolhidos.append(disponiveis.pop(idx))
    return sorted(escolhidos)


def gerar_jogo_base(pesos: dict, analise: dict, tentativas: int = 250, estrategia: dict | None = None) -> list[int]:
    melhor, melhor_score = None, -10**9
    for _ in range(tentativas):
        jogo = sample_ponderado_sem_reposicao(NUMEROS, pesos, _cfg.TAMANHO_JOGO)
        s = score_jogo(jogo, pesos, analise, estrategia=estrategia)
        if s > melhor_score:
            melhor, melhor_score = jogo, s
    return melhor


def crossover(j1: list[int], j2: list[int]) -> list[int]:
    """Combina dois jogos-pai por shuffle da união e complemento aleatório."""
    uniao = list(set(j1) | set(j2))
    rng().shuffle(uniao)
    filho = uniao[:15]
    # Completa se necessário (não deve ocorrer com jogos de 15 dezenas)
    extras = [n for n in NUMEROS if n not in filho]
    rng().shuffle(extras)
    while len(filho) < 15:
        filho.append(extras.pop())
    return sorted(filho)


def mutacao(jogo: list[int], pesos: dict, taxa: float = 0.35) -> list[int]:
    """Aplica mutação ponderada por pesos: substitui um gene por outro com maior probabilidade."""
    novo = jogo[:]
    if rng().random() < taxa:
        sair = rng().choice(novo)
        restantes = [n for n in NUMEROS if n not in novo]
        if restantes:
            pesos_lista = [max(1e-9, pesos.get(n, 0)) for n in restantes]
            # random.choices suporta pesos nativamente (evita sort + slice manual)
            entrar = rng().choices(restantes, weights=pesos_lista, k=1)[0]
            novo.remove(sair)
            novo.append(entrar)
            novo = sorted(set(novo))
    while len(novo) < 15:
        n = rng().choice(NUMEROS)
        if n not in novo:
            novo.append(n)
    return sorted(novo)


def evoluir_populacao(pop: list, pesos: dict, analise: dict, geracoes: int = 35, tamanho_pop: int = 70, elite: int = 14, estrategia: dict | None = None) -> list:
    taxa_mutacao = estrategia.get("taxa_mutacao", 0.35) if estrategia else 0.35
    pop = [sorted(set(j)) for j in pop if len(set(j)) == _cfg.TAMANHO_JOGO]
    while len(pop) < tamanho_pop:
        pop.append(gerar_jogo_base(pesos, analise, estrategia=estrategia))

    # Cache de scores: evita recalcular o mesmo jogo a cada geração.
    # Limitado a 8.000 entradas para não acumular memória em sessões longas.
    _CACHE_LIMITE = 8_000
    cache_scores: dict = {}

    def score_cached(j: list[int]) -> float:
        chave = tuple(j)
        if chave not in cache_scores:
            if len(cache_scores) >= _CACHE_LIMITE:
                # Descarta metade mais antiga (FIFO simples sem overhead de OrderedDict)
                chaves = list(cache_scores)
                for k in chaves[:_CACHE_LIMITE // 2]:
                    del cache_scores[k]
            cache_scores[chave] = score_jogo(j, pesos, analise, estrategia=estrategia)
        return cache_scores[chave]

    # Opção 2 — 24/06/2026: critério de convergência antecipada.
    # Interrompe o loop quando a população estagna por PACIENCIA gerações seguidas,
    # evitando iterações inúteis nos perfis com G/P ainda desequilibrado e
    # economizando tempo em todos os perfis que convergirem antes do limite.
    # PACIENCIA agora é proporcional a geracoes (≥10, ≤30) para escalar
    # corretamente: G=40→5ger, G=80→10ger, G=250→31ger — mas clampado em [10,30].
    # Pode ser sobrescrito via estrategia["paciencia"] para controle fino.
    PACIENCIA = int(
        (estrategia or {}).get("paciencia")
        or max(10, min(30, geracoes // 8))
    )
    melhor_score_anterior = -1.0
    geracoes_sem_melhora = 0

    for _ in range(geracoes):
        pop = sorted(pop, key=score_cached, reverse=True)

        # Verifica estagnação no melhor indivíduo da geração atual
        melhor_score_atual = score_cached(pop[0])
        if melhor_score_atual > melhor_score_anterior:
            melhor_score_anterior = melhor_score_atual
            geracoes_sem_melhora = 0
        else:
            geracoes_sem_melhora += 1
        if geracoes_sem_melhora >= PACIENCIA:
            break  # convergência antecipada — sem desperdício de gerações

        nova = pop[:elite]
        pais = pop[:min(20, len(pop))]
        while len(nova) < tamanho_pop:
            p1 = rng().choice(pais)
            p2 = rng().choice(pais)
            filho = mutacao(crossover(p1, p2), pesos, taxa=taxa_mutacao)
            nova.append(filho)
        pop = nova
    return sorted(pop, key=score_cached, reverse=True)


def selecionar_jogos_diversos(candidatos: list, pesos: dict, analise: dict, qtd: int = 20, estrategia: dict | None = None) -> list:
    escolhidos, vistos = [], set()
    limite_primario = estrategia.get("limite_intersecao", 12) if estrategia else 12
    limite_fallback = min(13, limite_primario + 1)
    for jogo in candidatos:
        t = tuple(sorted(jogo))
        if t in vistos:
            continue
        ok = True
        for ex in escolhidos:
            if intersecao(jogo, ex) >= limite_primario:
                ok = False
                break
        if ok:
            escolhidos.append(jogo)
            vistos.add(t)
        if len(escolhidos) >= qtd:
            return escolhidos
    tentativas = 0
    while len(escolhidos) < qtd and tentativas < 1500:
        tentativas += 1
        novo = gerar_jogo_base(pesos, analise, tentativas=120, estrategia=estrategia)
        t = tuple(novo)
        if t in vistos:
            continue
        ok = True
        for ex in escolhidos:
            if intersecao(novo, ex) >= limite_fallback:
                ok = False
                break
        if ok:
            escolhidos.append(novo)
            vistos.add(t)
    return escolhidos[:qtd]


# =========================================================
# COBERTURA INTELIGENTE GLOBAL
# =========================================================
def calcular_mapa_cobertura(jogos: list) -> dict:
    freq_dezenas = Counter()
    freq_linhas = Counter()
    freq_pares = Counter()
    somas = []
    pares_qtd = []

    for jogo in jogos:
        jogo = sorted(set(jogo))
        freq_dezenas.update(jogo)
        somas.append(soma_jogo(jogo))
        pares_qtd.append(contar_pares(jogo))
        for n in jogo:
            freq_linhas[(n - 1) // 5 + 1] += 1
        for i in range(len(jogo)):
            for j in range(i + 1, len(jogo)):
                freq_pares[(jogo[i], jogo[j])] += 1

    sobreposicoes = []
    for i in range(len(jogos)):
        for j in range(i + 1, len(jogos)):
            sobreposicoes.append(intersecao(jogos[i], jogos[j]))

    return {
        "freq_dezenas": dict(freq_dezenas),
        "freq_linhas": dict(freq_linhas),
        "freq_pares_top": dict(freq_pares.most_common(15)),
        "media_soma": round(mean(somas), 2) if somas else 0,
        "media_pares": round(mean(pares_qtd), 2) if pares_qtd else 0,
        "media_sobreposicao": round(mean(sobreposicoes), 2) if sobreposicoes else 0,
        "max_sobreposicao": max(sobreposicoes) if sobreposicoes else 0,
        "min_sobreposicao": min(sobreposicoes) if sobreposicoes else 0,
        "dezenas_mais_cobertas": sorted(freq_dezenas.items(), key=lambda x: (-x[1], x[0]))[:8],
        "dezenas_menos_cobertas": sorted(freq_dezenas.items(), key=lambda x: (x[1], x[0]))[:8],
    }


def perfil_tatico_jogo(jogo: list[int], analise: dict, pesos: dict, idx: int) -> dict:
    soma_ = soma_jogo(jogo)
    pares = contar_pares(jogo)
    peso_medio = sum(pesos.get(n, 0) for n in jogo) / 15
    soma_media = analise.get("soma_media", 195)

    if peso_medio >= mean(pesos.values()) * 1.04 and abs(soma_ - soma_media) <= 18:
        return "Agressivo estatístico"
    if abs(soma_ - soma_media) <= 10 and 6 <= pares <= 9:
        return "Equilibrado central"
    if soma_ < soma_media - 16:
        return "Proteção soma baixa"
    if soma_ > soma_media + 16:
        return "Proteção soma alta"
    if idx % 3 == 0:
        return "Alta dispersão"
    return "Cobertura complementar"


def score_incremental_cobertura(jogo: list[int], escolhidos: list, cobertura_dezenas: dict, cobertura_linhas: dict, cobertura_pares: dict, pesos: dict, analise: dict, estrategia: dict, qtd_alvo: int) -> float:
    jogo = sorted(set(jogo))
    if len(jogo) != _cfg.TAMANHO_JOGO:
        return -10**9

    alvo_medio = max(1.0, (qtd_alvo * _cfg.TAMANHO_JOGO) / 25)
    diversidade = estrategia.get("diversidade", 0.75) if estrategia else 0.75
    limite_inter = estrategia.get("limite_intersecao", 12) if estrategia else 12

    top_pesos = sorted(pesos, key=pesos.get, reverse=True)
    grupo_forte = set(top_pesos[:10])
    grupo_baixo = set(top_pesos[-8:])

    bonus_deficit = 0.0
    penal_excesso = 0.0
    for n in jogo:
        alvo_n = alvo_medio
        if n in grupo_forte:
            alvo_n *= 1.18
        elif n in grupo_baixo:
            alvo_n *= 0.90
        atual = cobertura_dezenas.get(n, 0)
        if atual < alvo_n:
            bonus_deficit += (alvo_n - atual) / alvo_n
        else:
            penal_excesso += (atual - alvo_n + 1) / alvo_n

    # equilíbrio de linhas no pacote completo
    alvo_linha = max(1.0, (qtd_alvo * _cfg.TAMANHO_JOGO) / 5)
    bonus_linhas = 0.0
    for linha in range(1, 6):
        qtd_linha_jogo = sum(1 for n in jogo if ((n - 1) // 5 + 1) == linha)
        if qtd_linha_jogo:
            atual = cobertura_linhas.get(linha, 0)
            if atual < alvo_linha:
                bonus_linhas += min(1.0, (alvo_linha - atual) / alvo_linha) * qtd_linha_jogo

    # evita que os mesmos pares apareçam demais no conjunto
    penal_pares = 0.0
    for i in range(len(jogo)):
        for j in range(i + 1, len(jogo)):
            par = (jogo[i], jogo[j])
            repet = cobertura_pares.get(par, 0)
            if repet >= max(2, qtd_alvo // 5):
                penal_pares += 0.08 * repet

    penal_sobreposicao = 0.0
    bonus_distancia = 0.0
    for outro in escolhidos:
        inter = intersecao(jogo, outro)
        if inter >= limite_inter:
            penal_sobreposicao += (inter - limite_inter + 1) * (1.2 + diversidade)
        else:
            bonus_distancia += (limite_inter - inter) * 0.08 * diversidade

    score_individual = score_jogo(jogo, pesos, analise, escolhidos, estrategia)
    estrutura = analisar_estrutura_jogo_cached(jogo)
    bonus_estrutura = 0.35 * estrutura.get("score_estrutural", 0)
    if estrutura.get("classificacao") == "estrutura fraca":
        bonus_estrutura -= 1.25

    return (
        0.55 * score_individual
        + bonus_estrutura
        + 1.35 * bonus_deficit
        + 0.30 * bonus_linhas
        + bonus_distancia
        - 1.15 * penal_excesso
        - penal_pares
        - penal_sobreposicao
    )


def selecionar_jogos_cobertura_global(candidatos: list, pesos: dict, analise: dict, qtd: int = 20, estrategia: dict | None = None) -> tuple[list, dict]:
    candidatos_limpos = []
    vistos = set()
    for jogo in candidatos:
        t = tuple(sorted(set(jogo)))
        if len(t) == _cfg.TAMANHO_JOGO and t not in vistos:
            candidatos_limpos.append(list(t))
            vistos.add(t)

    # Garante massa de candidatos suficiente para a seleção global.
    tentativas = 0
    while len(candidatos_limpos) < max(qtd * 12, 120) and tentativas < 1200:
        tentativas += 1
        novo = gerar_jogo_base(pesos, analise, tentativas=90, estrategia=estrategia)
        if rng().random() < 0.55:
            novo = mutacao(novo, pesos, taxa=(estrategia or {}).get("taxa_mutacao", 0.35) + 0.08)
        t = tuple(sorted(set(novo)))
        if len(t) == _cfg.TAMANHO_JOGO and t not in vistos:
            candidatos_limpos.append(list(t))
            vistos.add(t)

    candidatos_limpos = sorted(
        candidatos_limpos,
        key=lambda j: score_jogo(j, pesos, analise, estrategia=estrategia),
        reverse=True,
    )[:max(250, qtd * 20)]

    escolhidos = []
    cobertura_dezenas = Counter()
    cobertura_linhas = Counter()
    cobertura_pares = Counter()
    escolhidos_set = set()

    # ── Seleção greedy com heap de pontuação preguiçosa (lazy heap) ───────────
    # Complexidade: O(n·k·log n) em vez de O(n·k·n) do loop linear puro.
    #
    # Funcionamento:
    #   1. Pré-computa um score inicial para cada candidato (sem cobertura acumulada).
    #   2. Usa um max-heap (heapq com negativo) para extrair o melhor em O(log n).
    #   3. Ao retirar o topo, recomputa o score real com o estado atual de cobertura.
    #      Se o score ainda for o maior entre os candidatos restantes ("lazy evaluation"),
    #      aceita. Caso contrário, reinsere com o novo score e tenta o próximo.
    #   4. Isso evita recalcular TODOS os candidatos a cada iteração — na prática
    #      apenas O(k·log n) recálculos totais em vez de O(n·k).

    import heapq

    # Inicializa heap: (-score_inicial, id_único, jogo)
    # id_único garante desempate determinístico sem comparar listas.
    heap = []
    for uid, jogo in enumerate(candidatos_limpos):
        s0 = score_incremental_cobertura(
            jogo, [], cobertura_dezenas, cobertura_linhas, cobertura_pares,
            pesos, analise, estrategia, qtd
        )
        heapq.heappush(heap, (-s0, uid, jogo))

    removidos = set()

    while len(escolhidos) < qtd and heap:
        neg_score, uid, jogo = heapq.heappop(heap)

        if uid in removidos:
            continue

        chave = tuple(jogo)

        # Lazy re-evaluation: recompute score with current coverage state
        s_real = score_incremental_cobertura(
            jogo, escolhidos, cobertura_dezenas, cobertura_linhas, cobertura_pares,
            pesos, analise, estrategia, qtd
        )

        # Se o heap não está vazio, verificar se este jogo ainda é o melhor
        if heap:
            prox_neg, prox_uid, prox_jogo = heap[0]
            if prox_uid not in removidos and s_real < -prox_neg:
                # Não é o melhor agora — reinsere com score atualizado e continua
                heapq.heappush(heap, (-s_real, uid, jogo))
                continue

        if chave in escolhidos_set:
            continue

        escolhidos.append(jogo)
        escolhidos_set.add(chave)
        removidos.add(uid)

        cobertura_dezenas.update(jogo)
        for n in jogo:
            cobertura_linhas[(n - 1) // 5 + 1] += 1
        for i in range(len(jogo)):
            for j in range(i + 1, len(jogo)):
                cobertura_pares[(jogo[i], jogo[j])] += 1

    if len(escolhidos) < qtd:
        faltantes = selecionar_jogos_diversos(candidatos_limpos, pesos, analise, qtd=qtd - len(escolhidos), estrategia=estrategia)
        for jogo in faltantes:
            t = tuple(jogo)
            if t not in {tuple(x) for x in escolhidos}:
                escolhidos.append(jogo)
            if len(escolhidos) >= qtd:
                break

    mapa = calcular_mapa_cobertura(escolhidos)
    mapa["refinamento_matematico"] = resumo_estrutural_pacote(escolhidos)
    perfis = []
    for i, jogo in enumerate(escolhidos, start=1):
        perfis.append({
            "jogo": i,
            "perfil": perfil_tatico_jogo(jogo, analise, pesos, i),
            "dezenas": formatar_jogo(jogo),
        })
    mapa["perfis_taticos"] = perfis
    mapa["qtd_jogos"] = len(escolhidos)
    return escolhidos[:qtd], mapa


def recortar_historico_para_analise(concursos: list, n_ultimos: int = 120) -> list:
    if not concursos:
        raise ValueError("Histórico vazio.")
    n_ultimos = max(1, int(n_ultimos))
    return concursos[-n_ultimos:]


