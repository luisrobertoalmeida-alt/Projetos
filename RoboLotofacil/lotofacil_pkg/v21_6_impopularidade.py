"""
lotofacil_pkg/v21_6_impopularidade.py
---------------------------------------
V21.6 — Módulo de Valor Esperado por Impopularidade

Estratégia: em loterias com prêmio rateado, não basta acertar —
é preciso acertar com menos gente. Jogadores humanos têm vieses
sistemáticos e documentados que tornam certas combinações cronicamente
sub-apostadas. Quando essas combinações saem, o prêmio é dividido
entre menos cotas — o valor esperado por aposta sobe.

Este módulo NÃO tenta prever o sorteio. Ele mede o quanto cada
jogo gerado é improvável de ser escolhido por um humano típico,
e transforma isso num bônus que o algoritmo genético pode usar.

Vieses humanos explorados (literatura de loterias):
  1. Preferência por datas (1–31): dezenas ≤ 31 são over-apostadas.
     Na Lotofácil, todas as 25 dezenas estão nessa faixa, mas as
     "datas" mais óbvias (1–12 meses, 1–31 dias) são mais escolhidas.
  2. Evitar sequências longas: humanos raramente escolhem 4+ consecutivos.
  3. Padrões geométricos no volante 5×5: linhas, colunas e diagonais
     completas são over-apostadas por parecerem "bonitas".
  4. Números redondos e terminações favoritas: 5, 10, 15, 20, 25 e
     terminações em 0 ou 5 atraem mais apostadores.
  5. Equilíbrio forçado: humanos tendem a distribuir manualmente
     os números "a olho", gerando distribuição linha/coluna muito
     regular — mais regular do que o aleatório real.
  6. Evitar repetição de concursos anteriores: apostadores mudam
     suas escolhas mesmo quando isso não tem base matemática.

Todas as funções são puras (sem I/O, sem estado global).
"""

from __future__ import annotations

import math
from collections import Counter
from statistics import mean, stdev
from typing import Sequence


# ── Constantes de viés ────────────────────────────────────────────────────────

# Dezenas "magnéticas" para humanos: datas de meses (1–12) e dias
# muito usados em aniversários + números redondos dentro de 1–25.
_DATAS_MAGNETICAS = frozenset([1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
                                11, 12, 13, 14, 15, 20, 25])

# Terminações "redondas" que atraem apostadores (0 e 5).
_TERMINACOES_REDONDAS = frozenset([5, 10, 15, 20, 25])

# Dezenas que aparecem na diagonal principal do volante 5×5
# (canto sup-esq → canto inf-dir: 1, 7, 13, 19, 25).
_DIAGONAL_PRINCIPAL = frozenset([1, 7, 13, 19, 25])

# Dezenas na diagonal secundária (canto sup-dir → canto inf-esq:
# 5, 9, 13, 17, 21).
_DIAGONAL_SECUNDARIA = frozenset([5, 9, 13, 17, 21])

# Linhas completas do volante (cada linha tem 5 dezenas).
_LINHAS_VOLANTE = [
    frozenset(range(1,  6)),   # linha 1: 01–05
    frozenset(range(6,  11)),  # linha 2: 06–10
    frozenset(range(11, 16)),  # linha 3: 11–15
    frozenset(range(16, 21)),  # linha 4: 16–20
    frozenset(range(21, 26)),  # linha 5: 21–25
]

# Colunas completas do volante.
_COLUNAS_VOLANTE = [
    frozenset([1, 6, 11, 16, 21]),
    frozenset([2, 7, 12, 17, 22]),
    frozenset([3, 8, 13, 18, 23]),
    frozenset([4, 9, 14, 19, 24]),
    frozenset([5, 10, 15, 20, 25]),
]


# ── Funções de detecção de viés ───────────────────────────────────────────────

def _clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def detectar_datas_magneticas(jogo: list[int]) -> float:
    """
    Retorna fração das dezenas do jogo que são 'datas magnéticas'.
    Quanto maior, mais o jogo se parece com escolhas humanas de datas.
    """
    return sum(1 for n in jogo if n in _DATAS_MAGNETICAS) / max(1, len(jogo))


def detectar_terminacoes_redondas(jogo: list[int]) -> float:
    """Fração de dezenas com terminação em 0 ou 5."""
    return sum(1 for n in jogo if n in _TERMINACOES_REDONDAS) / max(1, len(jogo))


def detectar_sequencias_longas_humanas(jogo: list[int]) -> float:
    """
    Humanos evitam sequências de 4+ consecutivos. Score alto = jogo
    com muitas sequências longas = menos popular = mais valioso.
    Retorna razão de dezenas participando de sequências ≥ 4.
    """
    jogo_s = sorted(set(jogo))
    em_seq_longa = 0
    i = 0
    while i < len(jogo_s):
        comprimento = 1
        while i + comprimento < len(jogo_s) and jogo_s[i + comprimento] == jogo_s[i] + comprimento:
            comprimento += 1
        if comprimento >= 4:
            em_seq_longa += comprimento
        i += comprimento
    return em_seq_longa / max(1, len(jogo_s))


def detectar_padrao_geometrico(jogo: list[int]) -> float:
    """
    Detecta se o jogo coincide fortemente com padrões geométricos
    humanos no volante 5×5: linhas, colunas e diagonais completas.
    Retorna fração de cobertura do padrão mais completo encontrado.
    """
    jogo_set = set(jogo)
    max_sobreposicao = 0.0

    # Linha ou coluna quase completa (4+ de 5): over-apostada.
    for padrao in _LINHAS_VOLANTE + _COLUNAS_VOLANTE:
        intersecao = len(jogo_set & padrao)
        max_sobreposicao = max(max_sobreposicao, intersecao / 5.0)

    # Diagonal principal ou secundária quase completa.
    for diag in (_DIAGONAL_PRINCIPAL, _DIAGONAL_SECUNDARIA):
        intersecao = len(jogo_set & diag)
        max_sobreposicao = max(max_sobreposicao, intersecao / 5.0)

    return max_sobreposicao


def detectar_equilíbrio_forcado(jogo: list[int]) -> float:
    """
    Humanos distribuem dezenas "a olho" de forma muito uniforme.
    Distribuição muito uniforme por linha/coluna = mais popular.
    Retorna medida de uniformidade: 1.0 = perfeitamente uniforme,
    0.0 = muito concentrado. Impopularidade = 1 - uniformidade.
    """
    jogo_s = sorted(set(jogo))
    linhas = [0] * 5
    colunas = [0] * 5
    for n in jogo_s:
        linhas[(n - 1) // 5] += 1
        colunas[(n - 1) % 5] += 1

    def coef_variacao(vals: list[int]) -> float:
        m = mean(vals) if vals else 1
        if m == 0:
            return 0.0
        try:
            s = stdev(vals)
        except Exception:
            s = 0.0
        return s / m

    cv_lin = coef_variacao(linhas)
    cv_col = coef_variacao(colunas)
    # CV alto = distribuição irregular = menos humano = mais impopular
    irregularidade = _clip((cv_lin + cv_col) / 2.0, 0.0, 1.0)
    return irregularidade


# ── Score principal de impopularidade ────────────────────────────────────────

def score_impopularidade(
    jogo: list[int],
    hist_recente: list | None = None,
    peso: float = 1.0,
) -> float:
    """
    Score de impopularidade do jogo: quanto mais alto, mais o jogo
    difere das escolhas típicas humanas e, portanto, menos apostadores
    esperados concorrem à mesma cota quando ele acerta.

    Range aproximado: -2.0 (muito popular / humano) a +2.0 (muito impopular).

    Args:
        jogo:         lista de dezenas do jogo (15 inteiros de 1–25).
        hist_recente: últimos concursos sorteados (para evitar repetições
                      óbvias que humanos também evitam).
        peso:         escalar global [0.0, 1.0] — controla quanto o
                      score_jogo vai valorizar a impopularidade.

    Returns:
        float: score de impopularidade ponderado por `peso`.
    """
    if not jogo or peso <= 0.0:
        return 0.0

    jogo = sorted(set(jogo))
    if len(jogo) != 15:
        return 0.0

    peso = _clip(peso, 0.0, 1.0)

    # 1. Datas magnéticas: penaliza jogos com muitas (mais populares).
    frac_datas = detectar_datas_magneticas(jogo)
    # Esperado aleatório: 17/25 = 0.68. Acima disso = mais popular.
    bonus_datas = _clip((0.68 - frac_datas) / 0.68, -1.0, 1.0) * 0.55

    # 2. Terminações redondas: penaliza excesso.
    frac_redondas = detectar_terminacoes_redondas(jogo)
    # Esperado aleatório: 5/25 = 0.20.
    bonus_redondas = _clip((0.20 - frac_redondas) / 0.20, -1.0, 1.0) * 0.35

    # 3. Sequências longas: bônus (humanos evitam, logo são raras entre apostadores).
    frac_seq = detectar_sequencias_longas_humanas(jogo)
    bonus_seq = _clip(frac_seq, 0.0, 1.0) * 0.40

    # 4. Padrão geométrico: penaliza coincidência com linha/coluna/diagonal.
    padrao = detectar_padrao_geometrico(jogo)
    # Sobreposição < 0.6 (3/5) é normal; acima é suspeito.
    bonus_geometrico = _clip((0.60 - padrao) / 0.60, -1.0, 1.0) * 0.45

    # 5. Irregularidade de distribuição: bônus para jogos menos uniformes.
    irregularidade = detectar_equilíbrio_forcado(jogo)
    bonus_irregularidade = _clip(irregularidade - 0.15, 0.0, 1.0) * 0.35

    # 6. Penalidade leve por repetir concurso recente inteiro
    #    (humanos que "não repetem" são muitos — logo repetir é impopular,
    #    mas o efeito é fraco e cobrimos apenas a repetição exata).
    bonus_repeticao = 0.0
    if hist_recente:
        for conc in (hist_recente[-5:] or []):
            if set(jogo) == set(conc):
                bonus_repeticao -= 0.30
                break

    score_raw = (
        bonus_datas
        + bonus_redondas
        + bonus_seq
        + bonus_geometrico
        + bonus_irregularidade
        + bonus_repeticao
    )

    return round(score_raw * peso, 5)


# ── Análise de impopularidade do pacote ──────────────────────────────────────

def resumo_impopularidade_pacote(
    jogos: list[list[int]],
    hist_recente: list | None = None,
    peso: float = 1.0,
) -> dict:
    """
    Calcula métricas de impopularidade para um pacote de jogos.
    Usado no dashboard e no relatório.
    """
    if not jogos:
        return {
            "media_score":        0.0,
            "max_score":          0.0,
            "min_score":          0.0,
            "media_datas":        0.0,
            "media_redondas":     0.0,
            "media_seq_longas":   0.0,
            "media_padrao_geo":   0.0,
            "media_irregularidade": 0.0,
            "jogos_acima_zero":   0,
            "interpretacao":      "Sem jogos.",
            "peso_ativo":         peso,
        }

    scores = [score_impopularidade(j, hist_recente, peso) for j in jogos]
    datas  = [detectar_datas_magneticas(j) for j in jogos]
    round_ = [detectar_terminacoes_redondas(j) for j in jogos]
    seqs   = [detectar_sequencias_longas_humanas(j) for j in jogos]
    geos   = [detectar_padrao_geometrico(j) for j in jogos]
    irregs = [detectar_equilíbrio_forcado(j) for j in jogos]

    acima = sum(1 for s in scores if s > 0)
    media = round(mean(scores), 4)

    if media >= 0.40:
        interp = "Pacote muito impopular — alto valor esperado por cota quando acertar."
    elif media >= 0.15:
        interp = "Pacote moderadamente impopular — boa diferenciação dos apostadores típicos."
    elif media >= -0.05:
        interp = "Pacote neutro — sem vantagem ou desvantagem de popularidade."
    else:
        interp = "Pacote popular — semelhante às escolhas humanas típicas."

    return {
        "media_score":          media,
        "max_score":            round(max(scores), 4),
        "min_score":            round(min(scores), 4),
        "media_datas":          round(mean(datas), 3),
        "media_redondas":       round(mean(round_), 3),
        "media_seq_longas":     round(mean(seqs), 3),
        "media_padrao_geo":     round(mean(geos), 3),
        "media_irregularidade": round(mean(irregs), 3),
        "jogos_acima_zero":     acima,
        "interpretacao":        interp,
        "peso_ativo":           peso,
    }


# ── Utilitário: peso padrão recomendado ──────────────────────────────────────

PESO_IMPOPULARIDADE_PADRAO = 0.30
"""
Peso padrão do score_impopularidade dentro do score_jogo.
Representa ~11% do score total (considerando que score_base pesa 8.0).
Escolhido para ser influente sem dominar — mantém a qualidade estrutural
como critério principal e a impopularidade como critério secundário.
Pode ser ajustado via UI (0.0 = desligado, 1.0 = máximo).
"""
