"""
validacao_zona_morta.py
------------------------
Reavalia com estatistica PAREADA a alegacao de "zona morta" documentada em
montar_configuracoes_laboratorio() (apostas.py): calibracao de 25/06/2026
(antes da metodologia pareada/TOST criada neste projeto em 07/2026) afirmava
que ratio G/P ~1.64 com janela < 140 cai numa "zona morta" (52.3% robo),
enquanto ratio ~1.30 seria seguro em qualquer janela.

Testa diretamente essa alegacao: mesma janela pequena (120, < 140), mesmos
sorteios reais, comparando:
  A) ratio ~1.64 (a "zona morta" alegada): G=164 / P=100
  B) ratio ~1.30 (alegado seguro)        : G=130 / P=100

Usa a mesma metodologia do Mapa G x P (cohen_d_pareado, sign-flip,
TOST margem=0.3) para decidir se a alegacao se sustenta ou nao.

Paralelo por PROCESSOS (nao threads -- GIL nao acelera codigo Python puro,
ver execucao_paralela.py) e com checkpoint incremental em JSON: se o
processo for interrompido, rodar de novo retoma so os passos que faltam
em vez de recomecar do zero.

Uso:
    python validacao_zona_morta.py
"""
import os
import sys
import json
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lotofacil_pkg.historico import carregar_concursos_do_csv
from lotofacil_pkg.apostas import gerar_apostas
from lotofacil_pkg.utils import definir_rng_thread, limpar_rng_thread, intersecao
from lotofacil_pkg.v20_6_bootstrap import (
    cohen_d_pareado, teste_significancia_pareado, tost_equivalencia,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE_DIR, "dados", "lotofacil_resultados_reais.csv")
CHECKPOINT = os.path.join(BASE_DIR, "dados", "zona_morta_checkpoint.json")

JANELA = 120  # < 140, condicao da "zona morta" alegada
QTD_JOGOS = 20
PASSOS = 150
SEED_BASE = 2026

CONFIGS = {
    "A_ratio1.64_zona_morta": (164, 100),
    "B_ratio1.30_seguro":     (130, 100),
}


def seed_do_passo(i):
    return (SEED_BASE * 1_000_003 + i) & 0xFFFFFFFF


def tarefa(nome_cfg, geracoes, pop_size, i, concursos):
    """Top-level e picklable -- roda em processo separado (ProcessPoolExecutor)."""
    definir_rng_thread(seed_do_passo(i))
    try:
        base = concursos[:i]
        real = sorted(concursos[i])
        jogos, _, _ = gerar_apostas(
            base, qtd_jogos=QTD_JOGOS, janela_analise=min(JANELA, len(base)),
            geracoes=geracoes, pop_size=pop_size,
        )
        acertos = [intersecao(j, real) for j in jogos]
        melhor = max(acertos) if acertos else 0
    finally:
        limpar_rng_thread()
    return nome_cfg, i, melhor


def carregar_checkpoint():
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {}


def salvar_checkpoint(dados):
    with open(CHECKPOINT, "w") as f:
        json.dump(dados, f)


def main():
    concursos, _, total = carregar_concursos_do_csv(CSV)
    inicio = max(JANELA, total - PASSOS)
    indices = list(range(inicio, total))
    print(f"Histórico: {total} concursos | janela={JANELA} | passos={len(indices)}", flush=True)

    resultados = carregar_checkpoint()  # {nome_cfg: {str(i): melhor}}
    for nome in CONFIGS:
        resultados.setdefault(nome, {})

    pendentes = []
    for nome, (g, p) in CONFIGS.items():
        for i in indices:
            if str(i) not in resultados[nome]:
                pendentes.append((nome, g, p, i))

    ja_prontos = sum(len(v) for v in resultados.values())
    print(f"Checkpoint: {ja_prontos} passo(s) já concluído(s). Faltam {len(pendentes)}.", flush=True)

    if pendentes:
        concluidos = 0
        with ProcessPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(tarefa, nome, g, p, i, concursos) for nome, g, p, i in pendentes]
            for fut in as_completed(futures):
                nome_cfg, i, melhor = fut.result()
                resultados[nome_cfg][str(i)] = melhor
                concluidos += 1
                if concluidos % 10 == 0 or concluidos == len(pendentes):
                    salvar_checkpoint(resultados)
                    print(f"  {concluidos}/{len(pendentes)} passos concluídos (checkpoint salvo).", flush=True)
        salvar_checkpoint(resultados)

    nomes = list(CONFIGS.keys())
    a_dados = [{"acertos": resultados[nomes[0]][str(i)]} for i in indices]
    b_dados = [{"acertos": resultados[nomes[1]][str(i)]} for i in indices]

    cohen = cohen_d_pareado(a_dados, b_dados)
    sig = teste_significancia_pareado(a_dados, b_dados, n_reamostras=5000)
    tost = tost_equivalencia(a_dados, b_dados, margem=0.3, n_reamostras=5000)

    media_a = sum(d["acertos"] for d in a_dados) / len(a_dados)
    media_b = sum(d["acertos"] for d in b_dados) / len(b_dados)

    print("\n" + "=" * 72)
    print(f"ZONA MORTA — {nomes[0]} vs {nomes[1]} (janela={JANELA}, n={len(indices)})")
    print(f"  média melhor {nomes[0]}: {media_a:.4f}")
    print(f"  média melhor {nomes[1]}: {media_b:.4f}")
    print(f"  Cohen's d pareado: {cohen['cohen_d_pareado']:.4f} ({cohen['magnitude']})")
    print(f"  p-value (sign-flip): {sig['p_value']:.4f} | delta_obs={sig['delta_obs']:.4f}")
    print(f"  TOST (margem=±0.3): equivalente={tost['equivalente']} | IC90={tost['ic_90']}")
    if tost["equivalente"]:
        print("\n  VEREDITO: alegação de 'zona morta' NÃO se sustenta — equivalência confirmada.")
    elif sig["rejeita_h0"] and abs(cohen["cohen_d_pareado"]) >= 0.2:
        print("\n  VEREDITO: diferença real detectada — alegação pode ter fundamento (investigar mais).")
    else:
        print("\n  VEREDITO: INCONCLUSIVO — nem equivalência nem diferença real estabelecidas.")


if __name__ == "__main__":
    main()
