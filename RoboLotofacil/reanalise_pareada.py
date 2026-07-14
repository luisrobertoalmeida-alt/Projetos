"""
Reanalise pareada da validacao G x P.

Critica recebida (correta): os dados sao PAREADOS (mesmos 300 sorteios
reais em todas as comparacoes), mas o relatorio original usou:
  - Cohen's d de amostras INDEPENDENTES (formula com SD pooled de dois
    grupos), que ignora a correlacao entre pares e SUBESTIMA o efeito
    quando os pares sao positivamente correlacionados (o que e o caso
    aqui: sorteios "faceis"/"dificeis" afetam robo e aleatorio igual).
  - teste de permutacao por embaralhamento de GRUPO (shuffle global),
    que assume trocabilidade entre unidades nao pareadas -- o correto
    para dados pareados e um teste de permutacao por TROCA DE SINAL
    (sign-flip) das diferencas.

Este script recalcula tudo com estatistica pareada correta:
  - d_z (Cohen's d pareado) = media(diff) / desvio(diff)
  - teste de permutacao por sign-flip (H1 unilateral: diff > 0)
  - bootstrap pareado (reamostra as DIFERENCAS, nao os grupos)
  - TOST (two one-sided tests) para equivalencia com margem pre-definida
  - calculo de poder observado e MDE (minimal detectable effect) a 80%
"""
import json
import math
import random
from statistics import mean, stdev

random.seed(7)
N_REAMOSTRAS = 10000

with open("/tmp/claude-0/-home-user-Projetos/605837cd-85d0-5357-a674-8511b314cbb3/scratchpad/robolotofacil/RoboLotofacil/dados/validacao_robo_vs_aleatorio_n300_20260714.json") as f:
    baseline = {r["concurso_idx"]: r for r in json.load(f)}
with open("/tmp/claude-0/-home-user-Projetos/605837cd-85d0-5357-a674-8511b314cbb3/scratchpad/robolotofacil/RoboLotofacil/dados/validacao_G88_P79_n300_20260714.json") as f:
    g88 = {r["concurso_idx"]: r for r in json.load(f)}
with open("/tmp/claude-0/-home-user-Projetos/605837cd-85d0-5357-a674-8511b314cbb3/scratchpad/robolotofacil/RoboLotofacil/dados/validacao_G16_P40_n300_20260714.json") as f:
    g16 = {r["concurso_idx"]: r for r in json.load(f)}

idx = sorted(baseline.keys())
n = len(idx)

series = {
    "G35/P70":    [baseline[i]["melhor_robo"] for i in idx],
    "G88/P79":    [g88[i]["melhor_robo"] for i in idx],
    "G16/P40":    [g16[i]["melhor_robo"] for i in idx],
    "Aleatorio":  [baseline[i]["melhor_ale"] for i in idx],
}


def cohen_d_pareado(diffs):
    dp = stdev(diffs)
    return mean(diffs) / dp if dp > 0 else float("nan")


def perm_test_sign_flip(diffs, n_reamostras=N_REAMOSTRAS, seed=7):
    """p-value unilateral (H1: media(diff) > 0) por troca aleatoria de sinal."""
    rng = random.Random(seed)
    obs = mean(diffs)
    contagem = 0
    for _ in range(n_reamostras):
        flipped = [d if rng.random() < 0.5 else -d for d in diffs]
        if mean(flipped) >= obs:
            contagem += 1
    return contagem / n_reamostras


def bootstrap_pareado_ic(diffs, n_reamostras=N_REAMOSTRAS, seed=7, nivel=0.95):
    rng = random.Random(seed)
    n = len(diffs)
    boots = [mean(rng.choice(diffs) for _ in range(n)) for _ in range(n_reamostras)]
    boots.sort()
    alfa = 1 - nivel
    lo = boots[int((alfa / 2) * n_reamostras)]
    hi = boots[int((1 - alfa / 2) * n_reamostras) - 1]
    return lo, hi


def tost_equivalencia(diffs, margem, n_reamostras=N_REAMOSTRAS, seed=7):
    """
    TOST via bootstrap: equivalente (dentro de +-margem) se o IC 90%
    (padrao para TOST, equivalente a 2x testes unilaterais a 5%) da
    diferenca estiver inteiramente contido em [-margem, +margem].
    """
    lo, hi = bootstrap_pareado_ic(diffs, n_reamostras=n_reamostras, seed=seed, nivel=0.90)
    equivalente = (lo > -margem) and (hi < margem)
    return equivalente, lo, hi


def poder_observado(diffs, alpha=0.05):
    """Poder aproximado (normal) do teste pareado, dado o efeito e n observados."""
    n = len(diffs)
    dz = cohen_d_pareado(diffs)
    z_alpha = 1.645  # unilateral, 5%
    ncp = dz * math.sqrt(n)  # parametro de nao-centralidade aproximado
    # Poder = P(Z > z_alpha - ncp) para teste unilateral normal
    z = z_alpha - ncp
    # aproximacao da CDF normal padrao via erf
    cdf = 0.5 * (1 + math.erf(-z / math.sqrt(2)))
    return cdf


def n_para_poder(dz_alvo, poder_alvo=0.80, alpha=0.05):
    """n necessario (pareado) para detectar d_z=dz_alvo com poder_alvo, unilateral 5%."""
    z_alpha = 1.645
    z_beta = 0.8416  # poder 80%
    if dz_alvo == 0:
        return float("inf")
    return math.ceil(((z_alpha + z_beta) / dz_alvo) ** 2)


print(f"n = {n} sorteios reais pareados (mesmos em todas as comparacoes)\n")

comparacoes = [
    ("G35/P70", "Aleatorio"),
    ("G88/P79", "Aleatorio"),
    ("G16/P40", "Aleatorio"),
    ("G88/P79", "G35/P70"),
    ("G16/P40", "G35/P70"),
    ("G88/P79", "G16/P40"),
]

MARGEM_EQUIVALENCIA = 0.3  # hits -- ver justificativa no relatorio

for a, b in comparacoes:
    diffs = [x - y for x, y in zip(series[a], series[b])]
    d_ind_note = ""  # so para lembrete
    dz = cohen_d_pareado(diffs)
    p_perm = perm_test_sign_flip(diffs)
    lo95, hi95 = bootstrap_pareado_ic(diffs, nivel=0.95)
    equiv, lo90, hi90 = tost_equivalencia(diffs, MARGEM_EQUIVALENCIA)
    poder = poder_observado(diffs)
    n_necessario_d02 = n_para_poder(0.2)

    print(f"=== {a} vs {b} (pareado, n={n}) ===")
    print(f"  media(diff)        : {mean(diffs):+.4f}")
    print(f"  desvio(diff)       : {stdev(diffs):.4f}")
    print(f"  Cohen's d PAREADO  : {dz:.4f}")
    print(f"  p-value (sign-flip, H1: {a}>{b}) : {p_perm:.4f}")
    print(f"  IC 95% (bootstrap pareado)       : [{lo95:+.4f} ; {hi95:+.4f}]")
    print(f"  TOST (margem=±{MARGEM_EQUIVALENCIA}): IC90%=[{lo90:+.4f};{hi90:+.4f}] -> "
          f"{'EQUIVALENTE dentro da margem' if equiv else 'NAO comprovadamente equivalente'}")
    print(f"  Poder observado (para detectar o d_z encontrado) : {poder:.3f}")
    print()

print(f"n necessario p/ 80% de poder detectar d_z=0.20 (pareado, unilateral 5%): {n_para_poder(0.20)}")
print(f"n necessario p/ 80% de poder detectar d_z=0.15 (pareado, unilateral 5%): {n_para_poder(0.15)}")
print(f"n necessario p/ 80% de poder detectar d_z=0.10 (pareado, unilateral 5%): {n_para_poder(0.10)}")
