"""
validacao_escala_real.py
-------------------------
Validação em escala real: robô vs. aleatório, sobre os últimos N concursos
reais da Lotofácil (walk-forward, sem vazamento: cada passo usa apenas
concursos anteriores ao sorteio testado).

Usa o RNG thread-local corrigido (mesma técnica aplicada em backtest.py)
para que os passos paralelos sejam reprodutíveis, e as funções estatísticas
já corrigidas (v20_6_bootstrap) para a comparação pareada robô vs. aleatório.

Uso:
    python validacao_escala_real.py

Requer dados/lotofacil_resultados_reais.csv (histórico real de concursos).
Resultado consolidado: ver VALIDACAO_ESCALA_REAL_2026-07-14.md.
"""
import os
import sys
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lotofacil_pkg.historico import carregar_concursos_do_csv
from lotofacil_pkg.apostas import gerar_apostas
from lotofacil_pkg.config import NUMEROS
from lotofacil_pkg.utils import definir_rng_thread, limpar_rng_thread, intersecao
from lotofacil_pkg.v20_6_bootstrap import teste_significancia, bootstrap_comparacao, tamanho_efeito_cohen_d
from lotofacil_pkg.v21_5_melhorias_cientificas import teste_significancia_calibracao

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE_DIR, "dados", "lotofacil_resultados_reais.csv")
SAIDA_DADOS = os.path.join(BASE_DIR, "dados", "validacao_robo_vs_aleatorio_n300_20260714.json")

SEED_BASE = 2026
JANELA = 120
QTD_JOGOS = 20
GERACOES = 35
POP_SIZE = 70
PASSOS = 300
REPS_ALEATORIO = 300  # reps por passo p/ estimar expectativa aleatoria com baixa variancia

concursos, _, total_csv = carregar_concursos_do_csv(CSV)
print(f"Concursos reais carregados: {len(concursos)} (CSV tem {total_csv})", flush=True)

total = len(concursos)
inicio = max(JANELA, total - PASSOS)
indices = list(range(inicio, total))
print(f"Testando {len(indices)} concursos reais (concurso {indices[0]+1} ao {indices[-1]+1})", flush=True)


def seed_do_passo(i):
    return (SEED_BASE * 1_000_003 + i) & 0xFFFFFFFF


def simular(i):
    definir_rng_thread(seed_do_passo(i))
    try:
        base = concursos[:i]
        real = concursos[i]
        jogos, _, _ = gerar_apostas(
            base, qtd_jogos=QTD_JOGOS, janela_analise=min(JANELA, len(base)),
            geracoes=GERACOES, pop_size=POP_SIZE,
        )
        acertos_robo = [intersecao(j, real) for j in jogos]
        melhor_robo = max(acertos_robo)
        media_robo = sum(acertos_robo) / len(acertos_robo)
    finally:
        limpar_rng_thread()

    # Baseline aleatório pareado com o MESMO sorteio real (RNG local, seed derivada)
    rng_local = random.Random(seed_do_passo(i) ^ 0x5EED)
    real_set = set(real)
    melhores_ale, medias_ale = [], []
    for _ in range(REPS_ALEATORIO):
        pacote = [rng_local.sample(NUMEROS, 15) for _ in range(QTD_JOGOS)]
        acertos = [len(set(j) & real_set) for j in pacote]
        melhores_ale.append(max(acertos))
        medias_ale.append(sum(acertos) / len(acertos))
    melhor_ale = sum(melhores_ale) / len(melhores_ale)
    media_ale = sum(medias_ale) / len(medias_ale)

    return {
        "concurso_idx": i + 1,
        "melhor_robo": melhor_robo,
        "media_robo": media_robo,
        "melhor_ale": melhor_ale,
        "media_ale": media_ale,
    }


t0 = time.time()
with ThreadPoolExecutor(max_workers=4) as ex:
    resultados = list(ex.map(simular, indices))
dt = time.time() - t0
print(f"Concluído em {dt:.1f}s ({dt/len(indices):.2f}s/passo efetivo)", flush=True)

with open(SAIDA_DADOS, "w") as f:
    json.dump(resultados, f, indent=2)

n = len(resultados)
robo_melhor = [{"acertos": r["melhor_robo"]} for r in resultados]
ale_melhor = [{"acertos": r["melhor_ale"]} for r in resultados]
robo_media = [{"acertos": r["media_robo"]} for r in resultados]
ale_media = [{"acertos": r["media_ale"]} for r in resultados]

sig_m = teste_significancia(robo_melhor, ale_melhor, n_reamostras=5000, seed=7)
comp_m = bootstrap_comparacao(robo_melhor, ale_melhor, n_reamostras=5000, seed=7)
cohen_m = tamanho_efeito_cohen_d(robo_melhor, ale_melhor)

sig_a = teste_significancia(robo_media, ale_media, n_reamostras=5000, seed=7)
comp_a = bootstrap_comparacao(robo_media, ale_media, n_reamostras=5000, seed=7)
cohen_a = tamanho_efeito_cohen_d(robo_media, ale_media)

venceu = sum(1 for r in resultados if r["melhor_robo"] > r["melhor_ale"])
perdeu = sum(1 for r in resultados if r["melhor_robo"] < r["melhor_ale"])
empate = n - venceu - perdeu
sig_bin = teste_significancia_calibracao(vitorias_robo=venceu, vitorias_aleatorio=perdeu, empates=empate)

print("\n=== RESULTADO — MELHOR JOGO DO PACOTE (n=%d concursos reais) ===" % n, flush=True)
print("media robo   :", round(sum(x["acertos"] for x in robo_melhor)/n, 4))
print("media aleat. :", round(sum(x["acertos"] for x in ale_melhor)/n, 4))
print("delta        :", comp_m["delta_observado"])
print("IC95 delta   :", comp_m["intervalos"].get("95%"))
print("veredito     :", comp_m["veredito"])
print("p-value(perm):", sig_m["p_value"], "(", sig_m["nivel_significancia"], ")")
print("cohen_d      :", cohen_m["cohen_d"], cohen_m["magnitude"])
print(f"vitorias robo: {venceu}/{n} ({100*venceu/n:.1f}%) | p-value(binom): {sig_bin['p_value']:.4f}")

print("\n=== RESULTADO — MEDIA DE ACERTOS DO PACOTE (n=%d) ===" % n, flush=True)
print("media robo   :", round(sum(x["acertos"] for x in robo_media)/n, 4))
print("media aleat. :", round(sum(x["acertos"] for x in ale_media)/n, 4))
print("delta        :", comp_a["delta_observado"])
print("IC95 delta   :", comp_a["intervalos"].get("95%"))
print("veredito     :", comp_a["veredito"])
print("p-value(perm):", sig_a["p_value"], "(", sig_a["nivel_significancia"], ")")
print("cohen_d      :", cohen_a["cohen_d"], cohen_a["magnitude"])

print("\nOK - validacao concluida", flush=True)
