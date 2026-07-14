# Validação Robô vs. Aleatório — Escala Real (2026-07-14)

> Referência oficial para qualquer alegação futura de "vantagem do robô
> sobre o acaso". Qualquer novo teste que reivindique uma vantagem deve
> ser cobrado com o mesmo rigor metodológico usado aqui: amostra real,
> walk-forward sem vazamento, comparação pareada, e — acima de tudo —
> **tamanho de amostra suficiente para não confundir ruído com sinal**.

## Motivação

Um teste inicial (ver seção "Histórico" abaixo) com apenas **55 sorteios
reais distintos** sugeriu uma vantagem pequena, porém estatisticamente
significativa, do robô sobre pacotes aleatórios no critério "melhor jogo
do pacote" (Cohen's d = 0,46, p = 0,0082). Como 55 é uma amostra pequena
e efeitos pequenos em amostras pequenas são notoriamente propensos a
"regressão à média" (o efeito observado encolhe conforme mais dados
chegam), esta validação repete o teste com uma amostra bem maior antes de
investir qualquer esforço de engenharia em amplificar esse mecanismo.

## Metodologia

- **Fonte de dados:** `dados/lotofacil_resultados_reais.csv` (fornecido
  pelo usuário) — 3.709 concursos oficiais reais da Lotofácil.
- **Janela testada:** últimos 300 concursos (nº 3.410 ao 3.709).
- **Walk-forward sem vazamento:** cada passo `i` usa apenas
  `concursos[:i]` como histórico de treino; o resultado real de `i` nunca
  entra na geração do pacote testado contra ele.
- **Parâmetros do robô:** `qtd_jogos=20`, `janela_analise=120`,
  `geracoes=35`, `pop_size=70` (valores padrão de `gerar_apostas`,
  equivalentes ao uso real relatado pelo usuário).
- **Baseline aleatório pareado:** para cada um dos 300 sorteios reais,
  300 repetições de pacotes de 20 jogos aleatórios (`random.sample`) foram
  simuladas contra o **mesmo** sorteio real, e a média das 300 repetições
  usada como expectativa aleatória para aquele sorteio — isso reduz o
  ruído do lado aleatório da comparação sem alterar o robô.
- **Reprodutibilidade:** RNG thread-local (seed derivada de
  `SEED_BASE=2026` + índice do passo) — mesmo mecanismo usado para
  corrigir o bug de reprodutibilidade dos backtests paralelos em
  `backtest.py`. Rodar este script novamente com os mesmos parâmetros
  reproduz os mesmos 300 pacotes do robô.
- **Testes estatísticos:** `teste_significancia` (permutação),
  `bootstrap_comparacao` (IC 95% via bootstrap) e `tamanho_efeito_cohen_d`,
  de `lotofacil_pkg/v20_6_bootstrap.py`.
- **Script:** ver `validacao_escala_real.py` (raiz do repositório de
  desenvolvimento) — dados brutos por passo salvos em
  `dados/validacao_robo_vs_aleatorio_n300_20260714.json`.

## Resultado

### Melhor jogo do pacote (métrica que mais importa para premiação)

| | Robô | Aleatório |
|---|---:|---:|
| Média | 11,277 | 11,232 |

- Delta observado: **+0,044**
- IC 95% do delta (bootstrap): **[-0,022 ; +0,112]** — cruza zero
- p-value (teste de permutação): **0,103** — não significativo (α=0,05)
- Cohen's d: **0,106 — efeito desprezível**
- Vitórias do robô: 89/300 (29,7%)

### Média de acertos do pacote

| | Robô | Aleatório |
|---|---:|---:|
| Média | 8,996 | 9,000 |

- Delta observado: -0,004
- IC 95%: [-0,020 ; +0,012] — cruza zero
- p-value: 0,710 — não significativo
- Cohen's d: -0,045 — efeito desprezível

## Comparação com o teste piloto (n=55)

| | n=55 (piloto) | n=300 (esta validação) |
|---|---:|---:|
| Delta (melhor do pacote) | +0,11 | +0,04 |
| p-value | 0,0082 | 0,103 |
| Cohen's d | 0,46 (pequeno) | 0,11 (desprezível) |

O efeito encolheu e deixou de ser estatisticamente significativo com a
amostra maior — o padrão clássico de um efeito inflado por ruído em
amostra pequena, não um efeito real.

## Conclusão

Com a configuração testada (G=35, P=70, janela=120, 20 jogos), **não há
vantagem estatisticamente defensável do robô sobre pacotes aleatórios**,
nem no melhor jogo do pacote nem na média de acertos, contra 300 sorteios
reais e distintos da Lotofácil. Isso é consistente com a natureza de um
sorteio oficial auditado (sem estrutura sequencial explorável) e com o
próprio aviso do `README.md`: o robô otimiza métricas estruturais do
pacote (cobertura, entropia, diversidade), não previsão de dezenas.

## Recomendação

- **Não investir** em otimizar o algoritmo genético para maximizar
  diretamente o "melhor do pacote" (ex.: fitness por Monte Carlo) — não
  há sinal comprovado para amplificar.
- **Fechamento combinatório** (`lotofacil_pkg/fechamento.py`) continua
  válido como abordagem complementar: sua garantia é matemática, não
  depende de o ensemble ter sinal preditivo real.
- **Repetir esta validação periodicamente** (a cada N concursos novos, ou
  antes de qualquer alegação de "vantagem" em uma nova versão) usando o
  mesmo script e metodologia, para não repetir o erro do teste piloto de
  concluir a partir de amostra pequena demais.
