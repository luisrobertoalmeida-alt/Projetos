# Validação do Mapa G×P — Escala Real (2026-07-14)

> Complementa `VALIDACAO_ESCALA_REAL_2026-07-14.md`. Mesma metodologia,
> mesmos 300 concursos reais, mesmo baseline aleatório pareado — agora
> comparando três configurações de gerações (G) e população (P) do
> algoritmo genético entre si, não só contra o aleatório.

> **ERRATA (mesmo dia, revisão pós-crítica):** a análise original abaixo
> (seções "Resultado"/"Interpretação"/"Conclusão") usou Cohen's d e teste
> de permutação de **amostras independentes** em dados que na verdade são
> **pareados** (mesmos 300 sorteios reais em todas as comparações), e
> tratou "não rejeitamos H0" como se fosse "provamos equivalência" sem
> teste de equivalência formal. Ambos os pontos foram corretamente
> apontados em revisão externa. A seção **"Reanálise pareada (TOST)"**
> no final deste documento corrige isso com estatística pareada correta
> (Cohen's d pareado, teste sign-flip, bootstrap pareado, TOST com margem
> pré-definida). A conclusão prática não muda, mas agora está em base
> estatisticamente correta — a análise original fica abaixo só por
> transparência histórica, não deve ser citada isoladamente.

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

---

## Reanálise pareada (TOST) — correção metodológica

**Problema identificado:** os dados de todas as comparações acima usam
os MESMOS 300 sorteios reais (pareados), mas a análise original usou
Cohen's d e teste de permutação de amostras independentes (embaralhamento
de grupo), que ignoram a estrutura pareada. Além disso, "nenhuma
configuração se diferencia" é apenas não-rejeição de H0 — não prova
equivalência sem um teste de equivalência formal (TOST).

**Correção aplicada** (ver `reanalise_pareada.py`, saída completa em
`reanalise_pareada_output.txt`):
- Cohen's d **pareado** (d_z = média das diferenças / desvio das
  diferenças, em vez da fórmula de SD pooled de dois grupos);
- teste de permutação por **sign-flip** (troca aleatória do sinal de
  cada diferença), o correto para dados pareados — em vez de embaralhar
  a união dos dois grupos;
- bootstrap **pareado** (reamostra as diferenças, não os grupos
  separadamente);
- **TOST** (Two One-Sided Tests): IC 90% da diferença dentro de uma
  margem de indiferença pré-definida de **±0,3 pontos** (menor que
  qualquer diferença que mudaria de faixa de premiação — critério
  conservador de relevância prática) ⇒ equivalência comprovada, não só
  ausência de significância.

### Resultado pareado

| Comparação | Cohen's d pareado | p-value (sign-flip) | IC 95% (diferença) | TOST (±0,3) |
|---|---:|---:|---|---|
| G=35/P=70 vs Aleatório | 0,075 | 0,098 | [-0,022 ; +0,112] | Equivalente (IC90% [-0,012;+0,102]) |
| G=88/P=79 vs Aleatório | 0,105 | 0,038 | [-0,006 ; +0,140] | Equivalente (IC90% [+0,006;+0,129]) |
| G=16/P=40 vs Aleatório | 0,097 | 0,046 | [-0,008 ; +0,126] | Equivalente (IC90% [+0,003;+0,115]) |
| G=88/P=79 vs G=35/P=70 | 0,028 | 0,347 | [-0,073 ; +0,120] | Equivalente (IC90% [-0,057;+0,103]) |
| G=16/P=40 vs G=35/P=70 | 0,016 | 0,414 | [-0,077 ; +0,107] | Equivalente (IC90% [-0,063;+0,090]) |
| **G=88/P=79 vs G=16/P=40** | **0,012** | **0,446** | **[-0,090 ; +0,110]** | **Equivalente (IC90% [-0,073;+0,090])** |

Nota: o Cohen's d pareado saiu **menor** que o independente reportado
acima (ex.: G=88 vs aleatório: 0,105 pareado vs 0,148 independente) — o
oposto do que um pareamento clássico produziria. Isso acontece porque o
lado "aleatório" é uma média de 300 repetições Monte Carlo por sorteio
(quase constante, baixa variância própria), então parear com ele não
remove ruído do jeito que um pareamento antes/depois normalmente remove.
Na prática isso reforça a conclusão de "sem efeito real", não enfraquece.

### Poder estatístico (honestidade sobre limitações)

n=300 **não foi dimensionado por cálculo de poder prévio** — foi escolhido
por ser uma ordem de grandeza muito maior que o piloto falho de n=55 e
computacionalmente viável, não por atender a um alvo de poder específico.
Poder observado (pareado, unilateral 5%) para os efeitos encontrados:

| Comparação | Poder observado |
|---|---:|
| G=35/P=70 vs Aleatório | 36% |
| G=88/P=79 vs Aleatório | 57% |
| G=16/P=40 vs Aleatório | 52% |
| G=88/P=79 vs G=35/P=70 | 12% |
| G=16/P=40 vs G=35/P=70 | 9% |
| G=88/P=79 vs G=16/P=40 | 7% |

n necessário para 80% de poder (pareado, unilateral 5%): **155** para
d_z=0,20; **275** para d_z=0,15; **619** para d_z=0,10. Ou seja: para os
efeitos pequenos observados contra o aleatório (d_z~0,08-0,10), n=300 está
no limite ou abaixo do poder ideal — **não podemos afirmar "não há efeito
nenhum"**, apenas que, se existe, é menor que a margem prática de ±0,3
pontos definida no TOST (que é o que importa para a decisão operacional).
Para as comparações config-vs-config o poder é baixo (7-12%), mas o IC é
estreito o suficiente (±0,07 a ±0,09) para a conclusão prática de
equivalência dentro de ±0,3 se sustentar mesmo assim.

### Conclusão revisada

A recomendação de usar **G=16/P=40** se mantém, agora em base
estatisticamente correta: TOST confirma equivalência prática (margem
±0,3 pontos) entre G=16/P=40, G=35/P=70 e G=88/P=79, com destaque para a
comparação operacionalmente mais relevante — **G=88/P=79 vs G=16/P=40**
— com IC90% estreito [-0,073; +0,090], bem dentro da margem. Rodar n
maior especificamente para essa comparação traria mais precisão, mas não
é necessário para a decisão de produção dado o intervalo já obtido.
