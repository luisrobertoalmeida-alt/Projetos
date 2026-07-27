"""
mapa_gp_custom.py
------------------
Mapa G x P com grade de valores de G customizavel via linha de comando.

A tela principal (ui.py -> _executar_mapa_gp) sempre chama mapear_vale_gp()
sem passar `pontos_g`, entao a grade fica presa no default hardcoded em
mapear_vale_gp() (v21_5_melhorias_cientificas.py): G=[80,100,120,140,160,
200,250,16] -- o ultimo ponto (antes G=300/P=230, o extremo teorico do
estudo original) foi trocado por G=16/P=40, a configuracao real e fixa
do sistema desde 2026-07-18 (ver ARQUITETURA.md, 2026-07-27). Nao ha
campo na UI para customizar a grade. Este script chama a mesma funcao,
mesmos dados reais e mesma metodologia (estatistica PAREADA: Cohen's d
pareado, sign-flip, TOST -- ver v20_6_bootstrap.py), mas com `pontos_g`
livre. Qualquer G=16 na lista sempre usa P=40 (o real), nao o P
proporcional da formula (que daria 12).

Uso:
    python mapa_gp_custom.py <janela> <passos> <qtd_jogos> <g1,g2,g3,...>

Exemplo (grade estendida para baixo, incluindo valores ja conhecidos por
outros testes -- G16, G35 -- e reduzindo o minimo da grade padrao):
    python mapa_gp_custom.py 194 300 20 16,35,50,80,100,120,140,160,200,250,300
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lotofacil_pkg.historico import carregar_concursos_do_csv
from lotofacil_pkg.apostas import gerar_apostas
from lotofacil_pkg.v21_5_melhorias_cientificas import mapear_vale_gp

if len(sys.argv) != 5:
    print(__doc__)
    sys.exit(1)

JANELA = int(sys.argv[1])
PASSOS = int(sys.argv[2])
QTD_JOGOS = int(sys.argv[3])
PONTOS_G = [int(x) for x in sys.argv[4].split(",")]

# CSV relativo ao próprio arquivo -- config.ARQUIVO_CSV_PADRAO usa um
# caminho fixo da máquina original do projeto (não portável), mesmo
# padrão adotado em validacao_gp.py.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE_DIR, "dados", "lotofacil_resultados_reais.csv")
concursos, _, total_csv = carregar_concursos_do_csv(CSV)
print(f"Histórico carregado: {total_csv} concursos.")
print(f"Parâmetros: janela={JANELA} | passos={PASSOS} | jogos={QTD_JOGOS} | pontos_g={PONTOS_G}")


def fn_gerar(hist, ger, pop, qtd_j):
    jogos, _, _ = gerar_apostas(
        hist, qtd_jogos=qtd_j, janela_analise=len(hist),
        geracoes=ger, pop_size=pop,
    )
    return jogos


def status_cb(msg: str) -> None:
    print(f"  {msg}", flush=True)


print("=" * 72)
print("MAPA G x P (grade customizada)")
resultado = mapear_vale_gp(
    concursos,
    fn_gerar,
    janela=JANELA,
    passos=PASSOS,
    qtd_jogos=QTD_JOGOS,
    pontos_g=PONTOS_G,
    status_cb=status_cb,
)

print("-" * 60)
print("Mapa G x P concluído")

melhor = resultado.get("melhor_config", {})
if melhor:
    print(
        f"  Melhor config : {melhor.get('nome')} | "
        f"score={melhor.get('score')} | "
        f"12+={melhor.get('pct_12_mais')}% | "
        f"vantagem={melhor.get('vantagem_pct')}%"
    )

print(f"  Vale confirmado : {'SIM' if resultado.get('vale_confirmado') else 'NAO'} (teste estatístico pareado, não heurística)")
print(f"  Análise         : {resultado.get('analise', '')}")

print("\nComparações pareadas vs. referência "
      f"G={resultado.get('referencia_extremo')}:")
for c in resultado.get("comparacoes_pareadas", []):
    if c.get("veredito") == "INCONCLUSIVO" and "cohen_d_pareado" not in c:
        print(f"  G={c['g']}: INCONCLUSIVO ({c.get('motivo')})")
        continue
    print(
        f"  G={c['g']}: {c['veredito']} | d_z={c['cohen_d_pareado']:.3f} "
        f"({c['magnitude']}) | p={c['p_value']:.4f} | "
        f"IC90%={c['ic_90']} | n={c['n']}"
    )

print("\nRanking completo (score heurístico — só triagem):")
for r in resultado.get("resultados", []):
    print(
        f"  {r['nome']:<14} | score={r['score']:.4f} | média={r['media_melhor']} "
        f"| 12+={r['pct_12_mais']}% | 13+={r['pct_13_mais']}% | vitórias={r['vit_robo']}/{r['passos_executados']}"
    )
