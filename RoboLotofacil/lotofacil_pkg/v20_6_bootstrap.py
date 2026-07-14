"""
lotofacil_pkg/v20_6_bootstrap.py
----------------------------------
Estatística Inferencial com Bootstrap — V20.6

Objetivo: substituir afirmações pontuais ("o robô acerta 11.3 em média") por
afirmações com margem de erro ("acerta 11.3 ± 0.4 com 95% de confiança"),
tornando qualquer comparação entre versões ou módulos estatisticamente honesta.

Por que Bootstrap?
  - Não assume distribuição normal dos acertos.
  - Funciona bem com amostras pequenas (característico de backtests de loteria).
  - É o método padrão quando não se conhece a distribuição subjacente.

Funções exportadas (amostras independentes):
  bootstrap_media             — IC da média de acertos por reamostragem
  bootstrap_comparacao        — IC da diferença entre dois conjuntos de resultados
  teste_significancia         — p-value bootstrap para H0: delta <= 0
  tamanho_efeito_cohen_d      — Cohen's d entre robô e baseline
  intervalo_confianca_taxa    — IC para taxas (ex.: taxa de 11+ acertos)
  relatorio_inferencial       — consolida todas as métricas em um único dict

Funções exportadas (dados PAREADOS — mesma unidade nos dois conjuntos,
ex.: mesmos sorteios reais testando duas configurações G/P):
  cohen_d_pareado             — Cohen's d pareado (d_z) das diferenças
  teste_significancia_pareado — p-value por permutação sign-flip
  bootstrap_pareado           — IC bootstrap da diferença pareada
  tost_equivalencia           — teste de equivalência (TOST) com margem a priori

Notas de design:
  - Todas as funções são puras (sem I/O, sem estado global).
  - O número de reamostras padrão é 2000 — suficiente para ICs de 95%/99%
    sem custo computacional proibitivo.
  - I/O fica em salvar_relatorio_inferencial(), separado da lógica.
"""
import json
import math
import random
from statistics import mean, stdev
from typing import Any


# ── helpers internos ──────────────────────────────────────────────────────────

def _extrair_acertos(resultados: list[dict]) -> list[float]:
    """Extrai valores de acertos/media_acertos de uma lista de dicts."""
    return [float(r.get("acertos", r.get("media_acertos", 0.0))) for r in resultados]


def _percentil(dados: list[float], p: float) -> float:
    """Percentil p (0–100) de uma lista ordenada."""
    if not dados:
        return 0.0
    s = sorted(dados)
    idx = (p / 100.0) * (len(s) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
    frac = idx - lo
    return s[lo] + frac * (s[hi] - s[lo])


# ── funções públicas ──────────────────────────────────────────────────────────

def bootstrap_media(
    resultados: list[dict],
    n_reamostras: int = 2000,
    niveis_confianca: tuple[float, ...] = (0.95, 0.99),
    seed: int | None = 42,
) -> dict[str, Any]:
    """
    Estima o intervalo de confiança da média de acertos por Bootstrap.

    Args:
        resultados:        lista de dicts com 'acertos' ou 'media_acertos'.
        n_reamostras:      número de reamostras bootstrap.
        niveis_confianca:  tupla de níveis (ex.: (0.95, 0.99)).
        seed:              semente para reprodutibilidade.

    Returns:
        Dict com:
          - media_observada: média pontual dos dados originais
          - mediana_bootstrap: mediana das médias reamostradas
          - intervalos: dict {nivel_str: {"inferior": float, "superior": float}}
          - erro_padrao_bootstrap: desvio padrão das médias reamostradas
          - n_amostras: tamanho da amostra original
    """
    vals = _extrair_acertos(resultados)
    n = len(vals)
    if n == 0:
        return {
            "media_observada": 0.0,
            "mediana_bootstrap": 0.0,
            "intervalos": {},
            "erro_padrao_bootstrap": 0.0,
            "n_amostras": 0,
        }

    rng = random.Random(seed)
    medias_boot = []
    for _ in range(n_reamostras):
        amostra = [rng.choice(vals) for _ in range(n)]
        medias_boot.append(mean(amostra))

    intervalos = {}
    for nivel in niveis_confianca:
        alfa = 1.0 - nivel
        p_inf = (alfa / 2.0) * 100
        p_sup = (1.0 - alfa / 2.0) * 100
        intervalos[f"{int(nivel * 100)}%"] = {
            "inferior": round(_percentil(medias_boot, p_inf), 4),
            "superior": round(_percentil(medias_boot, p_sup), 4),
        }

    ep = stdev(medias_boot) if len(medias_boot) >= 2 else 0.0

    return {
        "media_observada": round(mean(vals), 4),
        "mediana_bootstrap": round(_percentil(medias_boot, 50), 4),
        "intervalos": intervalos,
        "erro_padrao_bootstrap": round(ep, 4),
        "n_amostras": n,
    }


def bootstrap_comparacao(
    resultados_a: list[dict],
    resultados_b: list[dict],
    n_reamostras: int = 2000,
    niveis_confianca: tuple[float, ...] = (0.95, 0.99),
    seed: int | None = 42,
) -> dict[str, Any]:
    """
    Estima o IC da diferença (A - B) de médias de acertos por Bootstrap.

    Permite dizer: "A é melhor que B em X acertos, com IC de 95% entre [lo, hi]."
    Se o intervalo não incluir zero, a diferença é estatisticamente significativa.

    Args:
        resultados_a: lista de dicts do conjunto A (ex.: robô).
        resultados_b: lista de dicts do conjunto B (ex.: baseline aleatório).
        n_reamostras: reamostras bootstrap.
        niveis_confianca: níveis de confiança desejados.
        seed: semente.

    Returns:
        Dict com:
          - delta_observado:    média_A - média_B pontual
          - intervalos:         IC da diferença por nível
          - significativo_95:   bool — IC 95% não inclui zero
          - significativo_99:   bool — IC 99% não inclui zero
          - veredito:           "SUPERIOR", "EQUIVALENTE" ou "INFERIOR"
    """
    vals_a = _extrair_acertos(resultados_a)
    vals_b = _extrair_acertos(resultados_b)

    if not vals_a or not vals_b:
        return {
            "delta_observado": 0.0,
            "intervalos": {},
            "significativo_95": False,
            "significativo_99": False,
            "veredito": "SEM_DADOS",
        }

    rng = random.Random(seed)
    deltas_boot = []
    for _ in range(n_reamostras):
        am_a = [rng.choice(vals_a) for _ in range(len(vals_a))]
        am_b = [rng.choice(vals_b) for _ in range(len(vals_b))]
        deltas_boot.append(mean(am_a) - mean(am_b))

    intervalos = {}
    for nivel in niveis_confianca:
        alfa = 1.0 - nivel
        p_inf = (alfa / 2.0) * 100
        p_sup = (1.0 - alfa / 2.0) * 100
        intervalos[f"{int(nivel * 100)}%"] = {
            "inferior": round(_percentil(deltas_boot, p_inf), 4),
            "superior": round(_percentil(deltas_boot, p_sup), 4),
        }

    delta_obs = round(mean(vals_a) - mean(vals_b), 4)

    sig95 = False
    sig99 = False
    if "95%" in intervalos:
        ic = intervalos["95%"]
        sig95 = ic["inferior"] > 0 or ic["superior"] < 0
    if "99%" in intervalos:
        ic = intervalos["99%"]
        sig99 = ic["inferior"] > 0 or ic["superior"] < 0

    if sig95 and delta_obs > 0:
        veredito = "SUPERIOR"
    elif sig95 and delta_obs < 0:
        veredito = "INFERIOR"
    else:
        veredito = "EQUIVALENTE"

    return {
        "delta_observado": delta_obs,
        "intervalos": intervalos,
        "significativo_95": sig95,
        "significativo_99": sig99,
        "veredito": veredito,
    }


def teste_significancia(
    resultados_robo: list[dict],
    resultados_baseline: list[dict],
    n_reamostras: int = 2000,
    seed: int | None = 42,
) -> dict[str, Any]:
    """
    Teste de permutação/bootstrap para H0: média_robo <= média_baseline.

    Calcula o p-value como a proporção de reamostras onde o delta bootstrap
    é tão extremo quanto o delta observado, assumindo H0 verdadeira.

    Args:
        resultados_robo:     resultados do robô.
        resultados_baseline: resultados do baseline (aleatório ou estratégia-base).
        n_reamostras:        número de permutações.
        seed:                semente.

    Returns:
        Dict com:
          - p_value:      probabilidade de observar delta >= delta_obs por acaso
          - delta_obs:    diferença pontual observada
          - rejeita_h0:   bool (p_value < 0.05)
          - nivel_significancia: "p<0.01", "p<0.05", "p<0.10" ou "NS"
    """
    vals_r = _extrair_acertos(resultados_robo)
    vals_b = _extrair_acertos(resultados_baseline)

    if not vals_r or not vals_b:
        return {
            "p_value": 1.0,
            "delta_obs": 0.0,
            "rejeita_h0": False,
            "nivel_significancia": "SEM_DADOS",
        }

    delta_obs = mean(vals_r) - mean(vals_b)
    combinado = vals_r + vals_b
    n_r = len(vals_r)

    rng = random.Random(seed)
    contagem_extremos = 0
    for _ in range(n_reamostras):
        perm = combinado[:]
        rng.shuffle(perm)
        delta_perm = mean(perm[:n_r]) - mean(perm[n_r:])
        if delta_perm >= delta_obs:
            contagem_extremos += 1

    p_value = round(contagem_extremos / n_reamostras, 4)
    rejeita = p_value < 0.05

    if p_value < 0.01:
        nivel = "p<0.01"
    elif p_value < 0.05:
        nivel = "p<0.05"
    elif p_value < 0.10:
        nivel = "p<0.10"
    else:
        nivel = "NS"

    return {
        "p_value": p_value,
        "delta_obs": round(delta_obs, 4),
        "rejeita_h0": rejeita,
        "nivel_significancia": nivel,
    }


def tamanho_efeito_cohen_d(
    resultados_a: list[dict],
    resultados_b: list[dict],
) -> dict[str, Any]:
    """
    Calcula o tamanho de efeito de Cohen's d entre dois conjuntos.

    d = (média_A - média_B) / desvio_padrão_pooled

    Interpretação padrão:
      |d| < 0.2  → efeito desprezível
      |d| < 0.5  → efeito pequeno
      |d| < 0.8  → efeito médio
      |d| >= 0.8 → efeito grande

    Args:
        resultados_a: lista de dicts do grupo A.
        resultados_b: lista de dicts do grupo B.

    Returns:
        Dict com:
          - cohen_d:      valor de d (pode ser negativo)
          - magnitude:    "DESPREZIVEL", "PEQUENO", "MEDIO" ou "GRANDE"
          - media_a, media_b, dp_pooled: parâmetros intermediários
    """
    vals_a = _extrair_acertos(resultados_a)
    vals_b = _extrair_acertos(resultados_b)

    if not vals_a or not vals_b:
        return {
            "cohen_d": 0.0,
            "magnitude": "SEM_DADOS",
            "media_a": 0.0,
            "media_b": 0.0,
            "dp_pooled": 0.0,
        }

    ma = mean(vals_a)
    mb = mean(vals_b)
    na, nb = len(vals_a), len(vals_b)

    dp_a = stdev(vals_a) if na >= 2 else 0.0
    dp_b = stdev(vals_b) if nb >= 2 else 0.0

    # desvio padrão pooled (Hedges)
    if na + nb - 2 <= 0:
        dp_pool = (dp_a + dp_b) / 2 if (dp_a + dp_b) > 0 else 1.0
    else:
        dp_pool = math.sqrt(
            ((na - 1) * dp_a ** 2 + (nb - 1) * dp_b ** 2) / (na + nb - 2)
        )

    if dp_pool > 0:
        d = round((ma - mb) / dp_pool, 4)
    else:
        # Desvio pooled zero: sem variância nos dados. Se as médias também
        # forem iguais, não há efeito (d=0). Se diferirem, é uma separação
        # perfeita entre os grupos — o maior efeito possível, não "zero".
        # Usa um valor finito grande (em vez de infinito) para não gerar
        # "Infinity" em relatórios/JSON persistidos.
        d = 0.0 if ma == mb else math.copysign(99.0, ma - mb)
    abs_d = abs(d)

    if abs_d < 0.2:
        magnitude = "DESPREZIVEL"
    elif abs_d < 0.5:
        magnitude = "PEQUENO"
    elif abs_d < 0.8:
        magnitude = "MEDIO"
    else:
        magnitude = "GRANDE"

    return {
        "cohen_d": d,
        "magnitude": magnitude,
        "media_a": round(ma, 4),
        "media_b": round(mb, 4),
        "dp_pooled": round(dp_pool, 4),
    }


def intervalo_confianca_taxa(
    n_sucessos: int,
    n_total: int,
    nivel: float = 0.95,
) -> dict[str, Any]:
    """
    Calcula o IC de Wilson para uma taxa binomial (ex.: taxa de 11+ acertos).

    O IC de Wilson é superior ao IC normal para proporções próximas de 0 ou 1
    e amostras pequenas.

    Args:
        n_sucessos: número de eventos positivos (ex.: jogos com 11+ acertos).
        n_total:    total de tentativas.
        nivel:      nível de confiança (padrão 0.95).

    Returns:
        Dict com:
          - taxa_observada: n_sucessos / n_total
          - inferior:       limite inferior do IC de Wilson
          - superior:       limite superior do IC de Wilson
          - nivel:          nível usado
    """
    if n_total == 0:
        return {"taxa_observada": 0.0, "inferior": 0.0, "superior": 0.0, "nivel": nivel}

    p = n_sucessos / n_total
    # z para nível de confiança (aproximação comum)
    z_map = {0.90: 1.645, 0.95: 1.960, 0.99: 2.576}
    z = z_map.get(nivel, 1.960)

    z2 = z * z
    n = n_total
    centro = (p + z2 / (2 * n)) / (1 + z2 / n)
    margem = (z / (1 + z2 / n)) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))

    return {
        "taxa_observada": round(p, 4),
        "inferior": round(max(0.0, centro - margem), 4),
        "superior": round(min(1.0, centro + margem), 4),
        "nivel": nivel,
    }


def relatorio_inferencial(
    resultados_robo: list[dict],
    resultados_baseline: list[dict] | None = None,
    n_reamostras: int = 2000,
    seed: int | None = 42,
) -> dict[str, Any]:
    """
    Consolida todas as métricas inferenciais em um único relatório.

    Args:
        resultados_robo:     histórico de resultados do robô.
        resultados_baseline: resultados do baseline (opcional; se None,
                             usa aleatório simulado com média ≈ 9.0).
        n_reamostras:        reamostras bootstrap.
        seed:                semente.

    Returns:
        Dict com seções:
          - ic_media:      bootstrap_media() do robô
          - comparacao:    bootstrap_comparacao() robô vs baseline (ou None)
          - significancia: teste_significancia() (ou None)
          - cohen_d:       tamanho_efeito_cohen_d() (ou None)
          - resumo:        dict de alto nível
    """
    ic = bootstrap_media(resultados_robo, n_reamostras=n_reamostras, seed=seed)

    comp = None
    sig = None
    cohen = None

    if resultados_baseline:
        comp = bootstrap_comparacao(
            resultados_robo, resultados_baseline,
            n_reamostras=n_reamostras, seed=seed,
        )
        sig = teste_significancia(
            resultados_robo, resultados_baseline,
            n_reamostras=n_reamostras, seed=seed,
        )
        cohen = tamanho_efeito_cohen_d(resultados_robo, resultados_baseline)

    ic_95 = ic["intervalos"].get("95%", {})
    resumo = {
        "media_com_ic95": (
            f"{ic['media_observada']} "
            f"[{ic_95.get('inferior', '?')} – {ic_95.get('superior', '?')}]"
        ),
        "erro_padrao": ic["erro_padrao_bootstrap"],
        "n_amostras": ic["n_amostras"],
        "veredito_comparacao": comp["veredito"] if comp else "N/A",
        "significativo_95": comp["significativo_95"] if comp else False,
        "p_value": sig["p_value"] if sig else None,
        "cohen_d": cohen["cohen_d"] if cohen else None,
        "magnitude_efeito": cohen["magnitude"] if cohen else "N/A",
    }

    return {
        "ic_media": ic,
        "comparacao": comp,
        "significancia": sig,
        "cohen_d": cohen,
        "resumo": resumo,
    }


def salvar_relatorio_inferencial(
    relatorio: dict[str, Any],
    arquivo: str = "inferencia_bootstrap.json",
) -> None:
    """
    Persiste o relatório inferencial em JSON. Única função com I/O neste módulo.
    """
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, indent=2, ensure_ascii=False)


# =========================================================
# ESTATÍSTICA PAREADA (V22.1)
# =========================================================
# As funções acima (bootstrap_comparacao, teste_significancia,
# tamanho_efeito_cohen_d) tratam os dois grupos como AMOSTRAS
# INDEPENDENTES. Use-as quando resultados_a e resultados_b vêm de
# unidades diferentes (ex.: dois grupos de usuários).
#
# Quando os dois conjuntos vêm da MESMA unidade medida duas vezes (ex.:
# mesmos 300 sorteios reais, testando duas configurações G/P), o desenho
# é PAREADO — usar as funções independentes acima nesse caso ignora a
# correlação entre os pares e é metodologicamente incorreto (foi
# exatamente o erro corrigido em VALIDACAO_MAPA_GP_2026-07-14.md).
#
# Use as funções desta seção sempre que resultados_a[i] e resultados_b[i]
# correspondem à MESMA unidade/sorteio (mesmo índice).

def _diferencas_pareadas(resultados_a: list[dict], resultados_b: list[dict]) -> list[float]:
    vals_a = _extrair_acertos(resultados_a)
    vals_b = _extrair_acertos(resultados_b)
    if len(vals_a) != len(vals_b):
        raise ValueError(
            f"resultados_a e resultados_b precisam ter o mesmo tamanho para "
            f"comparação pareada (recebido: {len(vals_a)} e {len(vals_b)})."
        )
    return [a - b for a, b in zip(vals_a, vals_b)]


def cohen_d_pareado(resultados_a: list[dict], resultados_b: list[dict]) -> dict[str, Any]:
    """
    Cohen's d PAREADO (d_z) entre dois conjuntos medidos nas mesmas
    unidades: d_z = média(diferenças) / desvio(diferenças).

    Args:
        resultados_a, resultados_b: listas de dicts com 'acertos', na
            MESMA ordem/unidade (resultados_a[i] e resultados_b[i] devem
            se referir ao mesmo sorteio/passo).

    Returns:
        Dict com cohen_d_pareado, magnitude, média/desvio da diferença, n.
    """
    diffs = _diferencas_pareadas(resultados_a, resultados_b)
    if not diffs:
        return {"cohen_d_pareado": 0.0, "magnitude": "SEM_DADOS", "media_diferenca": 0.0, "desvio_diferenca": 0.0, "n": 0}
    media_diff = mean(diffs)
    dp_diff = stdev(diffs) if len(diffs) >= 2 else 0.0
    if dp_diff > 0:
        dz = media_diff / dp_diff
    else:
        dz = 0.0 if media_diff == 0 else math.copysign(99.0, media_diff)
    abs_dz = abs(dz)
    if abs_dz < 0.2:
        magnitude = "DESPREZIVEL"
    elif abs_dz < 0.5:
        magnitude = "PEQUENO"
    elif abs_dz < 0.8:
        magnitude = "MEDIO"
    else:
        magnitude = "GRANDE"
    return {
        "cohen_d_pareado": round(dz, 4),
        "magnitude": magnitude,
        "media_diferenca": round(media_diff, 4),
        "desvio_diferenca": round(dp_diff, 4),
        "n": len(diffs),
    }


def teste_significancia_pareado(
    resultados_a: list[dict],
    resultados_b: list[dict],
    n_reamostras: int = 2000,
    seed: int | None = 42,
) -> dict[str, Any]:
    """
    Teste de permutação por TROCA DE SINAL (sign-flip) para dados
    pareados — o equivalente correto do teste de permutação por
    embaralhamento de grupo (teste_significancia) quando as unidades são
    as mesmas nos dois conjuntos.

    H0: média(a - b) <= 0.  H1 (unilateral): média(a - b) > 0.
    """
    diffs = _diferencas_pareadas(resultados_a, resultados_b)
    if not diffs:
        return {"p_value": 1.0, "delta_obs": 0.0, "rejeita_h0": False, "nivel_significancia": "SEM_DADOS"}

    obs = mean(diffs)
    rng = random.Random(seed)
    contagem_extremos = 0
    for _ in range(n_reamostras):
        invertidas = [d if rng.random() < 0.5 else -d for d in diffs]
        if mean(invertidas) >= obs:
            contagem_extremos += 1

    p_value = round(contagem_extremos / n_reamostras, 4)
    rejeita = p_value < 0.05
    if p_value < 0.01:
        nivel = "p<0.01"
    elif p_value < 0.05:
        nivel = "p<0.05"
    elif p_value < 0.10:
        nivel = "p<0.10"
    else:
        nivel = "NS"

    return {
        "p_value": p_value,
        "delta_obs": round(obs, 4),
        "rejeita_h0": rejeita,
        "nivel_significancia": nivel,
    }


def bootstrap_pareado(
    resultados_a: list[dict],
    resultados_b: list[dict],
    n_reamostras: int = 2000,
    niveis_confianca: tuple[float, ...] = (0.90, 0.95),
    seed: int | None = 42,
) -> dict[str, Any]:
    """
    IC bootstrap da diferença pareada (a - b): reamostra as DIFERENÇAS
    com reposição, não os dois grupos separadamente — o correto para
    dados pareados (ver bootstrap_comparacao() para amostras independentes).
    """
    diffs = _diferencas_pareadas(resultados_a, resultados_b)
    if not diffs:
        return {"delta_observado": 0.0, "intervalos": {}, "n": 0}

    n = len(diffs)
    rng = random.Random(seed)
    medias_boot = [mean(rng.choice(diffs) for _ in range(n)) for _ in range(n_reamostras)]

    intervalos = {}
    for nivel in niveis_confianca:
        alfa = 1.0 - nivel
        p_inf = (alfa / 2.0) * 100
        p_sup = (1.0 - alfa / 2.0) * 100
        intervalos[f"{int(nivel * 100)}%"] = {
            "inferior": round(_percentil(medias_boot, p_inf), 4),
            "superior": round(_percentil(medias_boot, p_sup), 4),
        }

    return {
        "delta_observado": round(mean(diffs), 4),
        "intervalos": intervalos,
        "n": n,
    }


def tost_equivalencia(
    resultados_a: list[dict],
    resultados_b: list[dict],
    margem: float,
    n_reamostras: int = 2000,
    seed: int | None = 42,
) -> dict[str, Any]:
    """
    TOST (Two One-Sided Tests) via bootstrap pareado: a e b são
    consideradas equivalentes dentro de ±margem se o IC 90% da diferença
    (a - b) estiver inteiramente contido em [-margem, +margem].

    Diferente de "não rejeitar H0" (ausência de evidência de diferença),
    isto é uma afirmação positiva de equivalência prática, condicionada
    à margem escolhida — a margem deve ser definida a priori, antes de
    ver os dados, como a menor diferença que teria relevância prática.

    Args:
        margem: margem de indiferença (mesma unidade dos dados, ex.:
            pontos de acerto). Não deve ser escolhida depois de ver o
            resultado.
    """
    boot = bootstrap_pareado(resultados_a, resultados_b, n_reamostras=n_reamostras, niveis_confianca=(0.90,), seed=seed)
    ic90 = boot["intervalos"].get("90%", {"inferior": 0.0, "superior": 0.0})
    lo, hi = ic90["inferior"], ic90["superior"]
    equivalente = (lo > -margem) and (hi < margem)
    return {
        "equivalente": equivalente,
        "margem": margem,
        "ic_90": [lo, hi],
        "delta_observado": boot["delta_observado"],
        "n": boot["n"],
    }
