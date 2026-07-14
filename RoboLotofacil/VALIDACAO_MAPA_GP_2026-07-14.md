# Validação do Mapa G×P — Escala Real (2026-07-14)

> Complementa `VALIDACAO_ESCALA_REAL_2026-07-14.md`. Mesma metodologia,
> mesmos 300 concursos reais, mesmo baseline aleatório pareado — agora
> comparando três configurações de gerações (G) e população (P) do
> algoritmo genético entre si, não só contra o aleatório.

## Motivação

`config_v22.yaml` alega "G validado: 88 (57,1% vitória em 5 rodadas)", e
`mapear_vale_gp()` (`v21_5_melhorias_cientificas.py`) roda por padrão
apenas 30 passos. Ambos sofrem do mesmo problema já identificado na
validação principal: amostra pequena demais para distinguir sinal de
ruído. Este teste repete a validação com n=300 para três configurações.

## Metodologia

Idêntica à de `VALIDACAO_ESCALA_REAL_2026-07-14.md` (mesmos 300 concursos
reais nº 3.410–3.709, walk-forward sem vazamento, mesma seed por passo).
O baseline aleatório foi **reaproveitado** do JSON já salvo
(`dados/validacao_robo_vs_aleatorio_n300_20260714.json`) — mesmos 300
sorteios reais, então a comparação entre configurações é pareada.
Ver `validacao_gp.py`.

Configurações testadas:
- **G=16 / P=40** — rápida
- **G=35 / P=70** — padrão de `gerar_apostas()` (já testada em
  `VALIDACAO_ESCALA_REAL_2026-07-14.md`)
- **G=88 / P=79** — "validada" no `config_v22.yaml`

## Resultado

### Cada configuração vs. aleatório (melhor jogo do pacote)

| Config | Tempo/passo | Delta vs. aleat. | IC 95% | p-value (permutação) | Cohen's d |
|---|---:|---:|---|---:|---|
| G=16/P=40 | 6,79s | +0,058 | [-0,008 ; 0,125] (cruza zero) | 0,045 | 0,138 (desprezível) |
| G=35/P=70 | 6,16s* | +0,044 | [-0,022 ; 0,112] (cruza zero) | 0,103 | 0,106 (desprezível) |
| G=88/P=79 | 9,76s | +0,068 | [-0,007 ; 0,141] (cruza zero) | 0,034 | 0,148 (desprezível) |

\*tempo efetivo da validação original, com ThreadPoolExecutor.

### Configuração vs. G=35/P=70 diretamente (melhor jogo do pacote)

| Comparação | Delta | IC 95% | p-value | Cohen's d |
|---|---:|---|---:|---|
| G=88/P=79 vs G=35/P=70 | +0,023 | [-0,077 ; 0,123] (cruza zero) | 0,347 (NS) | 0,038 (desprezível) |
| G=16/P=40 vs G=35/P=70 | +0,013 | [-0,080 ; 0,107] (cruza zero) | 0,413 (NS) | 0,023 (desprezível) |

## Interpretação

**Nenhuma das três configurações se diferencia das outras.** G=88/P=79 e
G=16/P=40 mostraram p<0,05 contra o aleatório isoladamente, mas:

1. O IC 95% do delta cruza zero nos dois casos — o teste de permutação e
   o bootstrap discordam na fronteira, sinal clássico de efeito instável,
   não robusto.
2. Foram feitas **3 comparações independentes contra o aleatório** (G=16,
   G=35, G=88). Com α=0,05 por teste, a chance de pelo menos um cruzar o
   limiar por acaso já é considerável. Aplicando correção de Bonferroni
   (α ajustado ≈ 0,017 para 3 testes), **nenhuma das três sobrevive**.
3. As comparações diretas entre configurações (G=88 vs G=35, G=16 vs
   G=35) não mostram diferença significativa nem efeito acima de
   "desprezível".

## Conclusão

A alegação "G=88 validado (57,1% em 5 rodadas)" **não se sustenta** em
amostra de 300 concursos reais — mesmo padrão do teste original (efeito
de amostra pequena que desaparece em escala). Não há evidência de que
G=88/P=79 seja superior a configurações mais baratas.

## Recomendação

Usar **G=16/P=40** no dia a dia: mesmo desempenho esperado (dentro do
ruído estatístico) que G=35/P=70 e G=88/P=79, porém ~30% mais rápido que
o padrão e ~43% mais rápido que o "validado" antigo. Não há custo de
qualidade em usar a configuração mais barata.

Qualquer novo "G validado" proposto no futuro deve passar pelo mesmo
teste (n≥300, comparação pareada contra outras configurações e correção
para múltiplas comparações) antes de virar recomendação — não bastam
poucas rodadas manuais.
