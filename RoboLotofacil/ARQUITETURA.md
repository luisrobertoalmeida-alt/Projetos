# RoboLotofacilPro — Mapa Arquitetural V21.6

## 🟢 NÚCLEO ESTÁVEL (não mexer sem testes)
Estes módulos formam o pipeline principal. Qualquer alteração exige rodar
a suite de testes completa antes de liberar.

| Módulo | Responsabilidade |
|--------|-----------------|
| `config.py` | Constantes globais (NUMEROS, caminhos, limites) |
| `utils.py` | Funções puras utilitárias (sem efeitos colaterais) |
| `historico.py` | Leitura e análise do histórico CSV |
| `analise.py` | Modelos de IA (bayesiano, markov, neural_leve, etc.) |
| `genetico.py` | Algoritmo genético de otimização de jogos |
| `apostas.py` | Pipeline principal: gerar_apostas(), calcular_configuracao_assistida() |
| `aprendizado.py` | Memória adaptativa e aprendizado permanente |
| `backtest.py` | Calibração, backtest científico V11, laboratório histórico |
| `persistencia.py` | Leitura/escrita de arquivos CSV e JSON |

## 🔵 MÓDULOS ATIVOS (validados, em uso na UI)
| Módulo | Responsabilidade |
|--------|-----------------|
| `v20_5_validacao_cientifica.py` | Benchmark vs aleatório, estabilidade por janela |
| `v20_6_bootstrap.py` | IC bootstrap, p-valor, Cohen's d, inferência estatística |
| `v20_8_walkforward.py` | Walk-Forward com detecção de overfitting |
| `v21_0_sqlite.py` | Banco SQLite, ranking de modelos, desempenho recente |
| `v21_5_melhorias_cientificas.py` | Score de robustez V2, mapear_vale_gp(), significância |
| `v21_6_impopularidade.py` | Estratégia de impopularidade de dezenas |
| `ui.py` | Interface gráfica principal (Tkinter) |
| `fechamento.py` | Fechamento combinatório de garantia total (wheeling). Botão "🔒 Fechamento" na UI (linha "Operação principal"), campo "Pool Fecht." (16-20). Garantia matemática condicional — ver docstring do módulo e `VALIDACAO_ESCALA_REAL_2026-07-14.md`. |
| `auditoria_cientifica.py` | Auditoria científica contínua para scripts de validação (`auditoria_experimento`, `corrigir_multiplas_comparacoes`, `consolidar_rodada_experimentos`). Não tem botão de UI (é infraestrutura de validação, não feature de produto) — mesmo status de `v20_6_bootstrap.py`, do qual depende. Ver seção "Decisão de arquitetura" abaixo e `test_auditoria_cientifica.py`. |
| `execucao_paralela.py` | Execução paralela por PROCESSOS (não threads) do walk-forward para scripts de validação standalone — `ThreadPoolExecutor` não acelera o algoritmo genético (GIL, Python puro); `ProcessPoolExecutor` dá speedup real (medido: 3,77x com 4 processos). Uso restrito a scripts standalone, NÃO à UI. Requisito não-negociável (testado): mesma seed_base ⇒ resultado idêntico entre `modo="processos"` e `modo="sequencial"`. `fn_gerar` precisa ser função top-level (não closure) — ver docstring do módulo. Ver `test_execucao_paralela.py`. |

## 🟡 MÓDULOS EXPERIMENTAIS (usar com cuidado)
| Módulo | Status | Observação |
|--------|--------|------------|
| `v21_5_meta_competitivo.py` | Experimental | Não integrado à UI |
| `v21_5_montecarlo_cientifico.py` | Experimental | Não integrado à UI |
| `v21_5_walkforward_profissional.py` | Experimental | Substituído pelo v20_8 |
| `v21_5_auto_poda_full.py` | Experimental | Derivado do v21_0_auto_poda |
| `v21_3_1_dashboard_real.py` | Experimental | Dashboard alternativo |
| `v21_3_1_hall_fama_auto.py` | Experimental | Não integrado à UI |
| `v21_3_1_historico_combinacoes.py` | Experimental | Não integrado à UI |
| `v21_0_auto_poda.py` | Experimental | Substituído pelo v21_5_auto_poda_full |
| `v21_0_meta_aprendizado.py` | Experimental | Não integrado à UI |

## 🔴 MÓDULOS LEGADOS (candidatos à remoção futura)

**Removidos em 2026-07-15** (confirmado por `grep` em todo o repositório
— zero referências reais fora de comentários/docstrings — e suíte
completa rodada depois, sem regressão): `analise_old.py`,
`v19_0_arquitetura_cientifica.py` (tinha ainda um bug latente: flags
`meta_otimizador`/`ia_adaptativa`/etc. hardcoded em `True` no dict de
retorno, nunca setadas para `False` nos `except` — mesma falha silenciosa
já corrigida em outros módulos; não importa mais, ficava sem efeito por
o módulo nunca ser chamado), `v18_3_parallel.py` (wrapper genérico de
`ProcessPoolExecutor`, também sem nenhum uso real — funcionalidade
superada por `execucao_paralela.py`, que tem garantia de reprodutibilidade
testada).

| Módulo | Motivo |
|--------|--------|
| `v17_4_features.py` | ⚠️ Ainda importado por `backtest.py` e `genetico.py` (núcleo) — viola a regra 1 abaixo, não remover sem primeiro migrar esses imports |
| `v18_1b_ia_adaptativa.py` | ⚠️ Ainda importado por `analise.py` (núcleo) e `backtest.py` — viola a regra 1 abaixo, não remover sem primeiro migrar esses imports |
| `v18_1c_meta_ensemble.py` | Substituído pelo ensemble do apostas.py |
| `v18_2_montecarlo.py` | Substituído pelo v21_5_montecarlo_cientifico |
| `v18_2b_auditor_cientifico.py` | Funcionalidade absorvida pelo backtest.py |
| `v18_meta_otimizador.py` | Substituído pelo genético atual |
| `v19_1_benchmark.py` | Substituído pelo v20_5_validacao_cientifica |
| `v19_1_cache_inteligente.py` | Cache não utilizado na V21 |
| `v19_1_estabilidade.py` | Absorvido pelo v20_5 |
| `v19_1_telemetria.py` | Telemetria não utilizada na V21 |
| `v20_2_poda_inteligente.py` | ⚠️ Ainda importado por `backtest.py` e `v21_0_sqlite.py` — viola a regra 1 abaixo, não remover sem primeiro migrar esses imports |
| `v20_3_ablation.py` | Ablation não integrado à UI |
| `v20_4_backtest_massivo.py` | Absorvido pelo backtest.py |

## 📋 Regras arquiteturais

1. **Nunca importar módulos 🔴 legados em código novo** — usar sempre o equivalente ativo
2. **Qualquer módulo novo começa como 🟡 experimental** — só promove para 🔵 após integração + testes
3. **Alterações no 🟢 núcleo** exigem rodar `python -m unittest discover` antes do commit
4. **Remoção de legados** só após confirmar que nenhum módulo ativo os importa

## 🧪 Rodar testes
```bash
cd RoboLotofacil
python -m unittest discover -s lotofacil_pkg/tests -p "test_*.py" -v
```

## 🧹 Auditoria estática (pyflakes) — 2026-07-15

Rodado `python -m pyflakes lotofacil_pkg/*.py`: 174 imports não usados
(a maioria debris de refatorações antigas, sem impacto funcional — não
recomendado limpar manualmente linha a linha agora) e 32 avisos de outra
natureza, todos verificados individualmente e confirmados **sem bug
funcional**: f-strings sem necessidade de interpolação (mensagens
corretas, só desnecessariamente prefixadas com `f`), variáveis locais
não usadas, e nomes de módulo re-importados localmente (redundante, não
quebra nada). Nenhum caso de variável sombreando um import de forma que
quebrasse o comportamento esperado.

**Sugestão para não acumular mais isso**: adicionar `pyflakes` (ou
`vulture`) como check de CI/pre-commit.

## 🔬 Auditoria científica contínua — decisão de arquitetura

`auditoria_cientifica.py` existe para que qualquer validação nova (config,
comparação G/P, feature nova) gere automaticamente o pacote estatístico
completo — pareado, TOST, correção para múltiplas comparações, poder —
sem depender de alguém lembrar de pedir revisão manual (foi assim que os
dois erros do Mapa G×P original passaram despercebidos).

**Decisão: função de uso explícito (`auditoria_experimento` +
`consolidar_rodada_experimentos`), não classe base/decorator herdado por
padrão.** Este é um projeto de desenvolvimento solo, orientado a scripts,
não uma base de código com múltiplos contribuidores e pontos de entrada —
uma classe base ou decorator não impede ninguém de escrever a análise na
mão por fora (nada força o uso em Python). O que evita o erro de fato é
uma função pronta ser mais rápida de chamar do que reimplementar a
análise — foi a ausência dessa função, não a ausência de "enforcement",
que causou o erro original.

**Regra:** `dados_a`/`dados_b` de `auditoria_experimento` devem vir de
concursos reais (`dados/lotofacil_resultados_reais.csv`) para qualquer
conclusão de mérito — `metadados["fonte_dados"]` deve ser `"real"`;
sintéticos só para testar mecânica (ex.: paralelo vs. sequencial).

## 📊 Validação de desempenho vs. aleatório — referência oficial

Ver `VALIDACAO_ESCALA_REAL_2026-07-14.md`. Testado contra 300 concursos
reais (walk-forward, sem vazamento): **nenhuma vantagem estatisticamente
defensável do robô sobre pacotes aleatórios** na configuração padrão
(G=35, P=70, janela=120, 20 jogos). Um teste piloto anterior com apenas
55 sorteios havia sugerido um efeito pequeno (Cohen's d=0,46), que não se
sustentou com amostra maior (Cohen's d=0,11, não significativo) — amostra
pequena demais, efeito era ruído.

Qualquer alegação futura de "vantagem do robô" (nova versão, novo modelo,
novo modo de geração) deve ser validada com o mesmo rigor: dados reais,
walk-forward sem vazamento, amostra grande o suficiente (n≥300), e as
funções estatísticas de `v20_6_bootstrap.py`/`v21_5_melhorias_cientificas.py`.

Ver também `VALIDACAO_MAPA_GP_2026-07-14.md`: a alegação "G=88 validado
(57,1% em 5 rodadas)" do `config_v22.yaml` **também não se sustentou** em
n=300 — G=16/P=40, G=35/P=70 e G=88/P=79 são estatisticamente
equivalentes entre si (confirmado com TOST pareado, não só ausência de
significância). Recomendação: usar G=16/P=40 (mais barato, sem perda de
qualidade esperada).

**✅ CORRIGIDO (2026-07-14): `mapear_vale_gp()` agora faz teste estatístico
pareado de verdade** — `vale_confirmado` é decidido por Cohen's d pareado,
teste de permutação sign-flip e TOST (`v20_6_bootstrap.py`: `cohen_d_pareado`,
`teste_significancia_pareado`, `tost_equivalencia`), comparando o extremo de
melhor média contra cada configuração intermediária nos mesmos sorteios reais.
O "score" heurístico antigo continua existindo só para ranking/triagem rápida
entre configurações, não decide mais `vale_confirmado`. Vereditos possíveis
por comparação: `POSSIVEL_VALE` (diferença real, TOST rejeita equivalência),
`EQUIVALENTE` (TOST confirma equivalência) ou `INCONCLUSIVO` (nem uma coisa
nem outra — amostra insuficiente, aumentar `passos`). Testes em
`test_estatistica_pareada.py`.

Reexecutar `validacao_escala_real.py` reproduz este resultado.
