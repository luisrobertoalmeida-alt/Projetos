"""
validacao_gp.py
----------------
Valida se a configuracao G/P "vencedora" do Mapa G x P (ex.: G=88/P=79,
"validado" com apenas ~5 rodadas no config_v22.yaml) realmente supera outras
configuracoes G/P, ou se essa conclusao tambem era ruido de amostra pequena
-- o mesmo problema ja encontrado na validacao robo vs aleatorio (n=55 vs
n=300).

Reaproveita o baseline aleatorio ja simulado em
dados/validacao_robo_vs_aleatorio_n300_20260714.json (mesmos 300 sorteios
reais, mesma seed por passo) para nao precisar re-simular 300*300 pacotes
aleatorios -- so roda o robo com a nova configuracao G/P nos mesmos passos.

Uso:
    python validacao_gp.py <geracoes> <pop_size> <sufixo_saida>

Exemplo:
    python validacao_gp.py 88 79 G88_P79
"""
import os
import sys
import json
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lotofacil_pkg.historico import carregar_concursos_do_csv
from lotofacil_pkg.apostas import gerar_apostas
from lotofacil_pkg.utils import definir_rng_thread, limpar_rng_thread, intersecao
from lotofacil_pkg.v20_6_bootstrap import teste_significancia, bootstrap_comparacao, tamanho_efeito_cohen_d

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE_DIR, "dados", "lotofacil_resultados_reais.csv")
JSON_BASELINE = os.path.join(BASE_DIR, "dados", "validacao_robo_vs_aleatorio_n300_20260714.json")

GERACOES = int(sys.argv[1])
POP_SIZE = int(sys.argv[2])
SUFIXO = sys.argv[3]
SAIDA = os.path.join(BASE_DIR, "dados", f"validacao_{SUFIXO}_n300_20260714.json")

SEED_BASE = 2026
JANELA = 120
QTD_JOGOS = 20

concursos, _, total_csv = carregar_concursos_do_csv(CSV)
with open(JSON_BASELINE) as f:
    baseline = {r["concurso_idx"]: r for r in json.load(f)}

indices = sorted(k - 1 for k in baseline.keys())  # concurso_idx = i+1
print(f"[{SUFIXO}] Reaproveitando baseline aleatorio de {len(indices)} passos "
      f"(concurso {indices[0]+1} ao {indices[-1]+1})", flush=True)
print(f"[{SUFIXO}] Config: G={GERACOES} P={POP_SIZE} qtd_jogos={QTD_JOGOS} janela={JANELA}", flush=True)


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
    return {"concurso_idx": i + 1, "melhor_robo": melhor_robo, "media_robo": media_robo}


t0 = time.time()
with ThreadPoolExecutor(max_workers=4) as ex:
    resultados = list(ex.map(simular, indices))
dt = time.time() - t0
print(f"[{SUFIXO}] Concluido em {dt:.1f}s ({dt/len(indices):.2f}s/passo)", flush=True)

with open(SAIDA, "w") as f:
    json.dump(resultados, f, indent=2)

n = len(resultados)
por_idx = {r["concurso_idx"]: r for r in resultados}

robo_melhor = [{"acertos": por_idx[k]["melhor_robo"]} for k in baseline]
ale_melhor  = [{"acertos": baseline[k]["melhor_ale"]}  for k in baseline]
robo_media  = [{"acertos": por_idx[k]["media_robo"]}   for k in baseline]
ale_media   = [{"acertos": baseline[k]["media_ale"]}   for k in baseline]

# robo(G,P) vs aleatorio
sig_m = teste_significancia(robo_melhor, ale_melhor, n_reamostras=5000, seed=7)
comp_m = bootstrap_comparacao(robo_melhor, ale_melhor, n_reamostras=5000, seed=7)
cohen_m = tamanho_efeito_cohen_d(robo_melhor, ale_melhor)

sig_a = teste_significancia(robo_media, ale_media, n_reamostras=5000, seed=7)
comp_a = bootstrap_comparacao(robo_media, ale_media, n_reamostras=5000, seed=7)
cohen_a = tamanho_efeito_cohen_d(robo_media, ale_media)

# robo(G,P) vs robo(G=35,P=70) -- baseline eh o proprio "robo" original salvo no JSON de referencia
robo35_melhor = [{"acertos": baseline[k]["melhor_robo"]} for k in baseline]
robo35_media  = [{"acertos": baseline[k]["media_robo"]}  for k in baseline]
sig_vs35_m = teste_significancia(robo_melhor, robo35_melhor, n_reamostras=5000, seed=7)
comp_vs35_m = bootstrap_comparacao(robo_melhor, robo35_melhor, n_reamostras=5000, seed=7)
cohen_vs35_m = tamanho_efeito_cohen_d(robo_melhor, robo35_melhor)

print(f"\n=== [{SUFIXO}] G={GERACOES} P={POP_SIZE} vs ALEATORIO — MELHOR DO PACOTE (n={n}) ===", flush=True)
print("media robo   :", round(sum(x["acertos"] for x in robo_melhor)/n, 4))
print("media aleat. :", round(sum(x["acertos"] for x in ale_melhor)/n, 4))
print("delta        :", comp_m["delta_observado"], "| IC95:", comp_m["intervalos"].get("95%"))
print("veredito     :", comp_m["veredito"], "| p-value:", sig_m["p_value"], sig_m["nivel_significancia"])
print("cohen_d      :", cohen_m["cohen_d"], cohen_m["magnitude"])

print(f"\n=== [{SUFIXO}] G={GERACOES} P={POP_SIZE} vs ALEATORIO — MEDIA DO PACOTE (n={n}) ===", flush=True)
print("media robo   :", round(sum(x["acertos"] for x in robo_media)/n, 4))
print("media aleat. :", round(sum(x["acertos"] for x in ale_media)/n, 4))
print("delta        :", comp_a["delta_observado"], "| IC95:", comp_a["intervalos"].get("95%"))
print("veredito     :", comp_a["veredito"], "| p-value:", sig_a["p_value"], sig_a["nivel_significancia"])
print("cohen_d      :", cohen_a["cohen_d"], cohen_a["magnitude"])

print(f"\n=== [{SUFIXO}] G={GERACOES} P={POP_SIZE} vs G=35/P=70 — MELHOR DO PACOTE (n={n}) ===", flush=True)
print(f"media G={GERACOES}/P={POP_SIZE} :", round(sum(x["acertos"] for x in robo_melhor)/n, 4))
print("media G=35/P=70    :", round(sum(x["acertos"] for x in robo35_melhor)/n, 4))
print("delta        :", comp_vs35_m["delta_observado"], "| IC95:", comp_vs35_m["intervalos"].get("95%"))
print("veredito     :", comp_vs35_m["veredito"], "| p-value:", sig_vs35_m["p_value"], sig_vs35_m["nivel_significancia"])
print("cohen_d      :", cohen_vs35_m["cohen_d"], cohen_vs35_m["magnitude"])

print(f"\n[{SUFIXO}] OK - validacao concluida", flush=True)
