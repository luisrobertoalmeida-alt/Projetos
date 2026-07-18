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
significância).

**Mapa G×P ampliado (2026-07-16, janela=194, passos=300):** grade
estendida de G=16 a G=300 (`mapa_gp_custom.py`, ver seção própria abaixo)
confirma o mesmo padrão em toda a faixa — `média_melhor` varia só entre
11.24 e 11.35 (spread de ~0.11), bem dentro da margem de equivalência do
TOST (±0.3). Não há vale estrutural em nenhum ponto testado.

**Decisão: G=16/P=40 fixo, removido da tela principal.** Como G/P não
tem efeito prático mensurável nessa faixa, expor como parâmetro manual só
cria a falsa impressão de que vale a pena ajustar. `ui.py` fixa
`self.geracoes`/`self.pop_size` em 16/40 (`config_v22.yaml` atualizado com
os mesmos valores) e não exibe mais os campos na tela. Continua ajustável
por quem quiser reabrir a investigação, via `estrategia_override` ou
rodando `mapa_gp_custom.py` diretamente.

*Atualizado em 2026-07-18: valor fixo trocado de G=35/P=27 para G=16/P=40
— ambos já confirmados estatisticamente equivalentes acima (linha 144),
sem mudança de racional, só o ponto escolhido dentro da faixa validada.*

## 🗺️ Mapa G×P com grade customizada — `mapa_gp_custom.py`

A tela principal sempre chamava `mapear_vale_gp()` sem passar `pontos_g`,
então a grade ficava presa no default hardcoded da função (G=80 a G=300)
— não havia como testar valores de G menores pela UI. `mapa_gp_custom.py`
(raiz do projeto) chama a mesma função com `pontos_g` livre via linha de
comando:

```
python mapa_gp_custom.py <janela> <passos> <qtd_jogos> <g1,g2,g3,...>
```

Mesmos dados reais, mesma metodologia pareada de `mapear_vale_gp()`
(`v20_6_bootstrap.py`). Foi assim que a faixa G=16-65 foi testada e usada
na decisão acima.

## 🧹 Limpeza pós Mapa G×P — 2026-07-17

Auditoria dos botões/telas da UI encontrou mecanismos que ainda
reajustavam G/P silenciosamente ou testavam configurações já provadas
equivalentes, desfazendo o benefício do fix de G=35/P=27:

- **`calcular_configuracao_assistida()`** (`apostas.py`) não recalcula
  mais gerações/população a partir de quantidade de jogos, desempenho
  recente ou banco técnico — repassa os valores fixos. Consequência: o
  checkbox **"🧭 Assistente Auto Config"** (desligado por padrão desde
  2026-07-18 — antes ligado) e o botão
  **"🧭 Auto Ajuste"** pararam de sobrescrever `self.geracoes`/
  `self.pop_size` a cada geração de jogos.
- **`aplicar_conhecimento_cientifico_na_configuracao()`** (`backtest.py`)
  removida — ficou órfã (só existia para blendar a recomendação do
  Científico V11 na configuração do assistente).
- **`montar_configuracoes_cientificas()`** (Científico V11) reduzida de
  5 para 2 configurações: as 3 que só variavam escala de G/P foram
  removidas; mantida a comparação G/P fixo vs. diversidade ampliada
  (parâmetro ainda não validado).
- **Alegação de "zona morta"** (`montar_configuracoes_laboratorio()`,
  calibração de 25/06/2026, anterior à metodologia pareada do projeto):
  reavaliada com `validacao_zona_morta.py` (n=150, janela=120, ratio
  G/P 1.64 vs. 1.30 — a condição exata da alegação). Resultado: Cohen's
  d pareado = -0.042 (desprezível), TOST (margem=±0.3) confirma
  equivalência. **A alegação não se sustentou** — mesmo padrão do
  "G=88 validado com 5 rodadas" já derrubado. A guarda de ratio foi
  removida.
- **`montar_configuracoes_laboratorio()`/`gerar_apostas_laboratorio_inteligente()`**
  simplificadas em 2026-07-17, **removidas por completo em 2026-07-18**
  (ver seção "Segunda limpeza" abaixo) — geravam exatamente o mesmo
  resultado que "🎲 Gerar Jogos" já entrega.
- `config_v22.yaml`: removida a chave duplicada e nunca lida por
  nenhum código, `genetico.passos_calibracao`.

## 🧹 Segunda limpeza — 2026-07-18 (pós fix de G=16/P=40)

Levantada pelo usuário durante uma sessão de revisão da tela: com G/P
fixo, vários mecanismos que existiam para *decidir* ou *testar* G/P
tinham virado casca vazia — rodavam, mas sempre chegavam na mesma
configuração fixa, sem gerar informação nova. Removidos/simplificados:

- **Botão "🔬 Laboratório"** (`gerar_jogos_laboratorio`) e
  `gerar_apostas_laboratorio_inteligente()`/`montar_configuracoes_laboratorio()`
  (`apostas.py`) — geravam o pacote com o mesmo G/P fixo que "🎲 Gerar
  Jogos" já usa, só que **sem** a injeção de impopularidade
  (`estrategia_override`). Ou seja, virou um subconjunto pior do botão
  principal, não uma alternativa. Removido; "🎲 Gerar Jogos" cobre o caso.
- **Checkbox "Modo Laboratório Inteligente"** (`self.modo_laboratorio`) —
  a variável nunca era lida em lugar nenhum (`.get()` não aparecia em
  nenhum condicional); só existia o `.set()`. Marcar ou desmarcar não
  tinha efeito algum. Removida.
- **Botão "🏆 Lab Histórico"** e `calibrar_laboratorio_historico_vs_aleatorio()`/
  `salvar_relatorio_laboratorio_historico()` (`backtest.py`) — desde que
  `montar_configuracoes_laboratorio()` passou a devolver sempre 1 config
  fixa, esse botão rodava a **mesma simulação** do "🎯 Calibrar IA" (mesmo
  G/P, mesma janela, mesmos passos, mesmos testes estatísticos), só
  embrulhada num formato de "ranking de 1 posição". Removido por completo.
- **Auto Diagnóstico** (`executar_auto_diagnostico_lotofacil`) rodava
  Calibração → Laboratório Histórico → Comparador — a etapa do meio era a
  duplicata acima, dobrando o tempo de execução para o mesmo resultado.
  Reduzido para 2 etapas (Calibração → Comparador); relatório renumerado.
- **Auto Ajuste / Assistente Auto Config** (`calcular_configuracao_assistida`,
  `apostas.py`) — calculava desempenho real (média do melhor acerto, taxa
  12+/13+, ajustes de memória) só para exibir como "motivo" no log; nada
  disso influenciava janela, passos ou G/P (que são fixos). Simplificada
  para só o que de fato é aplicado: janela (por tamanho do histórico) e
  passos de backtest (por quantidade de jogos). Tooltip do botão "🧭 Auto
  Ajuste" atualizado para não prometer mais do que isso.
- **Botão "📊 Dashboard Comparativo"** (`DashboardV22`/`v22_dashboard.py`) —
  auditado e tinha 3 problemas: (1) a seção "tendência de
  acertos"/"estabilidade" lia o mesmo arquivo
  (`lotofacil_desempenho_historico.json`) que o botão "📊 Desempenho" já
  mostra; (2) as seções "evolução por versão" e "histórico de
  calibrações" dependem de `historico_relatorios.json`, escrito só pelo
  Pipeline V22 (`RelatorioV22`) — e nenhum botão da tela dispara esse
  pipeline (`iniciar_pipeline_v22` existe mas está órfão), então essas
  seções sempre apareciam vazias; (3) só a seção "ranking de modelos"
  trazia algo que "📊 Desempenho" não tinha. Removido o botão e o módulo
  `v22_dashboard.py` (zero outros usos no projeto); a seção "ranking de
  modelos" foi incorporada em `gerar_dashboard_desempenho_historico()`
  (`backtest.py`), então nada de útil se perdeu.
- **Botão "🧠 Ver Aprendizado"** removido da tela a pedido do usuário
  (método `ver_aprendizado` mantido no código, sem botão vinculado).
- **Reorganização de botões** (a pedido do usuário): "📊 Backtest" e "🤖 BT
  Automático" moveram de "Operação principal" para "Inteligência,
  diagnóstico e calibração"; "🧪 Simulador" e "✅ Conferir Jogos" moveram
  de "Conferência, relatórios e arquivos" para "Operação principal",
  logo após "🎲 Gerar Jogos" — seguindo o fluxo de uso real (Atualizar →
  Carregar → Gerar Jogos → Simular → Conferir).
- **Bug corrigido de passagem**: `v22_pipeline.py` monitorava
  `laboratorio_historico_ativo` para saber se a etapa "calibracao" do
  Pipeline V22 tinha terminado — um flag que nunca era setado por
  `iniciar_calibracao_vs_aleatorio` (que usa `calibracao_ativa`). Como
  a remoção do Lab Histórico eliminaria esse atributo, o mapeamento foi
  corrigido para `calibracao_ativa`.
- **Bug real encontrado pelo usuário: "📊 Backtest" não testava o G/P do
  robô e contaminava os pesos do ensemble.** `backtest_basico()` tinha
  `geracoes=20, pop_size=40` **hardcoded** no código (não os 16/40 reais),
  e `backtest_ultra_massivo()` comparava 3 configs inventadas ("Ultra
  Rápido" G=16/P=36, "Ultra Equilibrado" G=24/P=52, "Ultra Forte"
  G=34/P=70) — nenhuma delas a config real. Mais grave: `backtest_basico()`
  alimenta a poda inteligente (`avaliar_e_podar_modelos`), que grava
  direto em `pesos_modelos.json` — os pesos que "🎲 Gerar Jogos" usa de
  verdade. Ou seja, cada "📊 Backtest" reajustava o ensemble real com base
  no desempenho de modelos sob uma config diferente da que o robô
  realmente usa. "🤖 BT Automático" nunca teve esse problema (já lia
  `self.geracoes`/`self.pop_size`). Corrigido: as duas funções agora
  recebem `geracoes`/`pop_size` como parâmetro e a UI passa os valores
  reais; `backtest_ultra_massivo()` parou de comparar 3 variantes de G/P
  (mesmo motivo do Mapa G×P — são estatisticamente equivalentes) e roda
  uma simulação só, com a config real.
- **Removido "🧭 Auto Ajuste" e "🧭 Assistente Auto Config"** — depois da
  simplificação acima, restava só ajustar janela e passos de backtest por
  2 regras fixas (tamanho do histórico e quantidade de jogos), sem
  nenhuma inteligência real por trás. O usuário considerou sem serventia
  suficiente para justificar dois pontos de entrada na tela; removidos
  o botão, o checkbox, `calcular_configuracao_assistida()`/
  `explicar_configuracao_assistida()` (`apostas.py`) e todos os call
  sites. Janela e passos de backtest continuam editáveis manualmente.

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
