"""
mapa_diversidade_custom.py
----------------------------
Mapa de Diversidade -- primeiro passo concreto do "Nível 4" discutido com
o usuário em 2026-08-08 (ver ARQUITETURA.md): em vez de um "Meta-Cientista"
genérico testando vários hiperparâmetros de uma vez (risco de p-hacking
acumulado sem controle), testa UM parâmetro por vez -- aqui, `diversidade`
-- reaproveitando a mesma metodologia estatística já validada do Mapa G×P
(Cohen's d pareado, sign-flip, TOST, correção Holm para múltiplas
comparações -- ver v20_6_bootstrap.py, auditoria_cientifica.py e
mapear_vale_diversidade() em v21_5_melhorias_cientificas.py).

G/P ficam FIXOS na configuração real de produção (G=100/P=77, ver
ARQUITETURA.md 2026-07-31) -- só `diversidade` varia, isolando o efeito
desse parâmetro especificamente via `estrategia_override`.

DISCIPLINA EXPERIMENTAL (não pule esta parte): decida a grade de valores
ANTES de rodar e mantenha fixa entre rodadas. Não adicione pontos "pra
ver se acha algo" depois de observar um resultado promissor -- isso
reintroduz o problema de múltiplas comparações que a correção Holm desta
função só resolve *dentro* de uma rodada, não entre rodadas ao longo do
tempo. Qualquer "POSSIVEL_VALE" deve ser tratado como hipótese a
confirmar numa amostra nova (concursos ainda não usados em nenhuma
rodada anterior), não como conclusão definitiva.

Uso:
    python mapa_diversidade_custom.py <janela> <passos> <qtd_jogos> <d1,d2,d3,...>

Exemplo (grade padrão sugerida):
    python mapa_diversidade_custom.py 200 150 20 0.5,0.6,0.7,0.75,0.8,0.9
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lotofacil_pkg.historico import carregar_concursos_do_csv
from lotofacil_pkg.apostas import gerar_apostas
from lotofacil_pkg.v21_5_melhorias_cientificas import mapear_vale_diversidade

if len(sys.argv) != 5:
    print(__doc__)
    sys.exit(1)

JANELA = int(sys.argv[1])
PASSOS = int(sys.argv[2])
QTD_JOGOS = int(sys.argv[3])
PONTOS_DIVERSIDADE = [float(x) for x in sys.argv[4].split(",")]

# G/P fixos na configuração real de produção -- ver ARQUITETURA.md, 2026-07-31.
GERACOES_FIXO = 100
POP_SIZE_FIXO = 77

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE_DIR, "dados", "lotofacil_resultados_reais.csv")
concursos, _, total_csv = carregar_concursos_do_csv(CSV)
print(f"Histórico carregado: {total_csv} concursos.")
print(
    f"Parâmetros: janela={JANELA} | passos={PASSOS} | jogos={QTD_JOGOS} | "
    f"G={GERACOES_FIXO} (fixo) | P={POP_SIZE_FIXO} (fixo) | "
    f"pontos_diversidade={PONTOS_DIVERSIDADE}"
)


def fn_gerar(hist, diversidade, qtd_j):
    jogos, _, _ = gerar_apostas(
        hist, qtd_jogos=qtd_j, janela_analise=len(hist),
        geracoes=GERACOES_FIXO, pop_size=POP_SIZE_FIXO,
        estrategia_override={"diversidade": diversidade},
    )
    return jogos


def status_cb(msg: str) -> None:
    print(f"  {msg}", flush=True)


print("=" * 72)
print("MAPA DE DIVERSIDADE")
resultado = mapear_vale_diversidade(
    concursos,
    fn_gerar,
    janela=JANELA,
    passos=PASSOS,
    qtd_jogos=QTD_JOGOS,
    pontos_diversidade=PONTOS_DIVERSIDADE,
    status_cb=status_cb,
)

print("-" * 60)
print("Mapa de Diversidade concluído")

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
      f"diversidade={resultado.get('referencia_extremo')}:")
for c in resultado.get("comparacoes_pareadas", []):
    if c.get("veredito") == "INCONCLUSIVO" and "cohen_d_pareado" not in c:
        print(f"  diversidade={c['d']}: INCONCLUSIVO ({c.get('motivo')})")
        continue
    print(
        f"  diversidade={c['d']}: {c['veredito']} | d_z={c['cohen_d_pareado']:.3f} "
        f"({c['magnitude']}) | p={c['p_value']:.4f} | "
        f"p_ajustado={c.get('p_ajustado', c['p_value']):.4f} | "
        f"IC90%={c['ic_90']} | n={c['n']}"
    )

print("\nRanking completo (score heurístico — só triagem):")
for r in resultado.get("resultados", []):
    print(
        f"  {r['nome']:<16} | score={r['score']:.4f} | média={r['media_melhor']} "
        f"| 12+={r['pct_12_mais']}% | 13+={r['pct_13_mais']}% | vitórias={r['vit_robo']}/{r['passos_executados']}"
    )
