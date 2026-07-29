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
| `apostas.py` | Pipeline principal: gerar_apostas(), gerar_apostas_dual_perfil() |
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

**Removido em 2026-07-19**: `execucao_paralela.py` — apesar do próprio
docstring afirmar que era usado por `validacao_gp.py`/`reanalise_pareada.py`,
nenhum desses scripts (nem qualquer outro arquivo do repositório) de fato
o chamava; cada script standalone reimplementava sua própria lógica de
`ProcessPoolExecutor`. Ver auditoria completa mais abaixo.

## 🟡 MÓDULOS EXPERIMENTAIS (usar com cuidado)
| Módulo | Status | Observação |
|--------|--------|------------|
| `v21_5_meta_competitivo.py` | Ativo | ELO por concurso, integrado ao pipeline real de poda/ELO (`alimentar_poda_e_elo()` em backtest.py) e ao ranking do "⚗️ Painel Científico" (`analise.py`). Tabela corrigida em 2026-07-23 — estava listada como "não integrado", desatualizado. |
| `v21_5_montecarlo_cientifico.py` | Ativo (corrigido 2026-07-19) | Integrado ao "⚗️ Painel Científico"; agora usa dados reais do Backtest Científico quando disponíveis (antes sempre usava dados sintéticos) |
| `v21_5_walkforward_profissional.py` | Ativo (corrigido 2026-07-19/21) | Complementa (não substitui) o v20_8: agora alimentado a cada Walk-Forward real, sem recomputar o algoritmo genético (ver Sétima rodada) |
| `v21_5_auto_poda_full.py` | Ativo (corrigido 2026-07-21) | Poda 4-estados, integrada ao pipeline real de poda/ELO (`alimentar_poda_e_elo()`). Tabela corrigida em 2026-07-23 — estava listada como "Experimental", desatualizado (ver Sexta rodada). |
| `v21_3_1_hall_fama_auto.py` | Experimental | Não integrado à UI |
| `v21_0_auto_poda.py` | Experimental | Substituído pelo v21_5_auto_poda_full |
| `v21_0_meta_aprendizado.py` | Ativo (reduzido 2026-07-23) | Só `probabilidade_recuperacao()` restou — é chamada de verdade por `analise.py`; as outras 4 funções do módulo nunca tinham chamador real e foram removidas. |

**Removidos em 2026-07-19**: `v21_3_1_dashboard_real.py`,
`v21_3_1_historico_combinacoes.py` — nunca tinham nenhum chamador real
fora de si mesmos.

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

## 🧹 Terceira limpeza — 2026-07-18 (poda/ELO e reorganização de tela)

Discussão com o usuário sobre Backtest/BT Automático/Backtest Científico
revelou uma peça de infraestrutura que não estava documentada: "📊
Backtest" não é só diagnóstico — ele alimenta a poda inteligente V20.2
(`pesos_modelos.json`, pesos reais usados por "🎲 Gerar Jogos") e o
ELO/4-fases V21.5-FULL (exibido em "⚗️ Painel Científico" → aba "🥇
Campeão"). Isso levantou duas perguntas do usuário, respondidas assim:

- **"Não seria melhor o Científico alimentar a poda/ELO?"** — Sim,
  metodologicamente: o Científico V11 isola cada modelo rodando o
  pipeline completo com `forcar_modelo` (zera a confiança dos outros 6),
  medição mais fiel do que a aproximação barata do `backtest_basico`
  (extrai um top-15 bruto do score do modelo, sem passar pelo
  refinamento genético). Mas o Científico custa ~7x mais gerações só na
  fase de campeonato — não dá pra ser a única fonte sem deixar poda/ELO
  desatualizados na maior parte do tempo. Solução adotada: `_alimentar_poda_e_elo()`
  (`backtest.py`) virou uma função compartilhada; `backtest_basico`/
  `backtest_ultra_massivo` continuam alimentando a cada rodada (barato,
  frequente), e `executar_backtest_cientifico_massivo` (fase 2, campeonato
  de modelos) agora também alimenta com sua medição mais rigorosa — uma
  correção periódica por cima da atualização contínua.
- **"Inconsistência dos 120 passos"** — `backtest_ultra_massivo` (modo
  ativado automaticamente com ≥120 passos) não calculava `acertos_modelo`
  nem chamava a poda/ELO, diferente de `backtest_basico` (<120 passos).
  Ou seja, o mesmo botão "📊 Backtest" afetava o robô real ou não, só
  pela quantidade de passos digitada. Corrigido: `backtest_ultra_massivo`
  agora calcula `acertos_modelo` do mesmo jeito e chama
  `_alimentar_poda_e_elo()` também.

Reorganização de tela adicional (a pedido do usuário):
- "🧪 Backtest Científico" saiu de "Investigação avançada" para ficar em
  sequência com "📊 Backtest"/"🤖 BT Automático" (linha de inteligência/
  diagnóstico).
- "⚡ Otimizador" e "🗺️ Mapa G×P" saíram de "Investigação avançada" para
  "Operação principal" — linha "Investigação avançada" removida (ficou
  vazia).
- Otimizador: limiar de aceite de 11+ subiu de 93% para 95%
  (`limiar_11` em `iniciar_otimizador_v22`, `ui.py`).

## 🧹 Quarta rodada — 2026-07-19 (bugs reportados pelo usuário)

- **Registro da seed nos relatórios.** Usuário rodou o mesmo teste com
  "Seed fixo" ligado e desligado para comparar, e notou que os relatórios
  (calibração, auto diagnóstico, backtest ultra massivo, backtest
  científico, BT Automático) não registravam se a seed usada era fixa ou
  aleatória — dependia de lembrar o que estava marcado na tela.
  `_descricao_seed()` (`backtest.py`) lê `config.SEED` (atualizado por
  `seed_global()`/`_aplicar_seed_configurada()` logo antes de cada
  operação) e agora aparece como uma linha "Seed: fixa (N)" ou "Seed:
  aleatória" em todos esses relatórios.
- **Bug real: jogos do Otimizador não apareciam na aba "Jogos Gerados".**
  `_executar_otimizador_v22` setava `self.jogos_gerados` mas nunca chamava
  `_atualizar_tabela_jogos()` — e mesmo chamando, a tabela ficaria vazia,
  porque `otimizar_pacote()` (`v22_otimizador.py`) descartava a
  `analise`/`pesos` do pacote vencedor (só retornava a lista de jogos),
  e `_atualizar_tabela_jogos()`/`avaliar_jogos()` exigem os três.
  Consequência colateral: como "Conferir Jogos" só registra aprendizado
  quando `self.analise`/`self.pesos` não são `None` (ver próxima seção),
  conferir um pacote gerado pelo Otimizador também não estava alimentando
  o aprendizado permanente. Corrigido: `otimizar_pacote()` agora retorna
  `(jogos, analise, pesos, relatorio)` do candidato vencedor; a UI seta
  `self.analise`/`self.pesos` e atualiza a tabela e o painel de info,
  igual às outras rotinas de geração.

**Pergunta do usuário: "Conferir Jogos" alimenta o aprendizado?** Sim —
`conferir_jogos_gerados()` chama `registrar_resultado_aprendizado()`
(memória permanente, `lotofacil_aprendizado_permanente.json`, usada por
`calcular_bonus_aprendizado()` para ajustar diversidade/mutação/elite na
próxima geração) e `registrar_desempenho_historico_robo()` (banco de
auditoria, `lotofacil_desempenho_historico.json`, mostrado em "📊
Desempenho") — mas **só se `self.analise` e `self.pesos` não forem
`None`**. Isso só acontece depois de rodar alguma rotina de geração
(Gerar Jogos, Dual-Perfil, Otimizador, Laboratório...) na sessão atual;
se você reiniciar o app e for direto em "Conferir Jogos" sem gerar nada
antes, a conferência roda normalmente mas **não** registra aprendizado
(fica só o TXT da conferência).

**Critério de aceite do Otimizador (11+ vs. 12+/13+).** Usuário perguntou
se o filtro principal do Otimizador (`limiar_11`) deveria usar 12+ em vez
de 11+. Resposta implementada em `v22_otimizador.py`: manter 11+ como
gate de aceite (evento quase saturado no aleatório — ~85-98% com 20-30
jogos por pacote só por volume — serve bem como filtro de sanidade
grosseiro), mas rebalancear o *score* que compara candidatos entre si
para pesar mais 12+/13+ e a média do melhor jogo, que discriminam melhor
"candidato bom" de "mediano" por serem mais raros. Score antigo
(`pct_11*0.6 + media*3.0 + pct_12*0.4`, sem 13+) → novo
(`pct_11*0.2 + media*3.5 + pct_12*0.8 + pct_13*1.5`). Como pesar mais um
evento raro aumenta a sensibilidade a ruído da simulação Monte Carlo,
`n_simulacoes` subiu de 500 para 1000 (o próprio docstring do módulo já
prometia 1000 sem que o código cumprisse — inconsistência corrigida de
brinde).

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

## 🔍 Quinta rodada — Auditoria completa — 2026-07-19

Usuário pediu uma auditoria completa do robô ("não tem bug?"). Foram
lançados 7 agentes paralelos (read-only, em worktree isolado) cobrindo
todo `lotofacil_pkg/` — pipeline core, backtest/execução paralela/
fechamento, módulos legados v17–v20, módulos v21, módulos v22 + plugins,
e os dois grandes blocos de handlers de `ui.py` (geração/backtest e
relatórios/diversos). Cada um verificou achados via grep/rastreamento de
chamadas reais antes de reportar. Achados verificados e corrigidos:

**Bugs de comportamento real:**
- **Dual-Perfil ignorava o slider de Impopularidade em 0%**
  (`ui.py`, `_executar_dual_perfil`): só passava `estrategia_override`
  quando `peso_imp_ui > 0`; em 0% passava `None`, e como
  `analise.py` embute um padrão de 30% em todo `estrategia` dict, zerar
  o slider nesse modo não desligava nada. Corrigido para sempre passar o
  override (igual ao modo single-perfil), com log explícito de
  "desligada" quando 0%.
- **Dual-Perfil nunca salvava em "últimos jogos gerados"**: faltava a
  chamada a `self.salvar_ultimos_jogos_gerados()` que todo outro fluxo de
  geração faz — pacotes do Dual-Perfil nunca eram conferidos
  automaticamente contra o sorteio seguinte nem entravam como
  aprendizado. Corrigido.
- **Backtest Científico ainda ignorava o G/P real** — terceiro
  "irmão" do bug já corrigido em `backtest_basico`/`backtest_ultra_massivo`
  nesta mesma sessão: `montar_configuracoes_cientificas()` aceitava
  `geracoes_base`/`pop_base` mas nunca os usava (candidatos sempre
  G=16/P=40 fixo — decisão de 2026-07-16, documentada, e que hoje
  coincide com a config real fixa). Removidos os parâmetros mortos da
  assinatura para não sugerir que o G/P da tela influencia o teste.
- **Dual-Perfil "Exploração" usava só 2 de 7 modelos declarados**
  (`apostas.py`, `gerar_apostas_dual_perfil`): o `fn_map` buscava scores em
  `ensemble_exp["scores_modelos"]`/`analise_exp["scores_estatistico"]`,
  chaves que `calcular_ensemble_multi_ia()` nunca escreve (a chave real é
  `"modelos"`). Só cobertura/pares_trios (que chamavam a função direto,
  sem passar por essa busca) realmente contribuíam; os outros 5 pesos de
  `_PESOS_EXPLORACAO` sempre voltavam vazios. Corrigido: lookup direto em
  `ensemble_exp["modelos"][nome]`.
- **Auto-otimização por "padrões vencedores" nunca funcionou**
  (`analise.py`, `analisar_padroes_vencedores`): lia `pares_medios`/
  `soma_media` dos registros de aprendizado, chaves que
  `registrar_resultado_aprendizado()` (`aprendizado.py`) nunca gravava —
  sempre caía no valor-padrão (soma=195), então o gatilho de recalibração
  de `aplicar_auto_otimizacao()` (só dispara se média ≥198 ou ≤192) nunca
  ativava, silenciosamente, desde sempre. Corrigido: o registro agora
  calcula pares/soma médios reais do pacote conferido.
- **Monte Carlo Científico sempre usava dados sintéticos**, nunca o
  Backtest Científico real, apesar do próprio docstring do módulo e do
  comentário no `ui.py` afirmarem o contrário — os dois pontos de chamada
  nunca passavam `resultados_backtest`. P(Robô > Aleatório), IC 95%,
  Cohen's d e p-value no "⚗️ Painel Científico" eram sempre calculados
  sobre `rng.gauss(0.3, 0.25)`. Corrigido: novo helper
  `_obter_resultados_backtest_reais_para_montecarlo()` (`ui.py`) busca a
  última execução real do Backtest Científico em
  `conhecimento_cientifico.json`; a tela agora rotula explicitamente se
  os números são reais ou (na ausência de qualquer execução prévia)
  sintéticos.
- **Walk-Forward Profissional (V21.5) nunca era alimentado** —
  `executar_walkforward_profissional()` existia, tinha lógica sólida e
  persistia em SQLite (tabela `walkforward_indicadores`, já existente no
  schema), mas nenhum caller real chamava essa função em lugar nenhum do
  robô; o painel "Walk-Forward Profissional" sempre mostrava "nenhuma
  execução registrada". Em vez de remover o módulo, foi conectado ao
  fluxo real: `_executar_walkforward` (`ui.py`) agora também chama
  `executar_walkforward_profissional()` com o mesmo `fn_gerar`/janelas do
  Walk-Forward V20.8 já em uso, como camada extra de indicadores
  acumulados (não substitui o V20.8, complementa).
- **Thread-safety: "⬆ Atualizar" e "📂 Carregar"** — os dois botões mais
  usados chamavam `self.log`/`self.set_status`/`_iniciar_progresso`/
  `_parar_progresso` diretamente de dentro da thread de fundo, em vez das
  versões `_async`/`root.after` usadas no resto do arquivo. Corrigido em
  `atualizar_resultados_reais`, `carregar_historico`,
  `avaliar_ultimo_sorteio_automatico` e
  `iniciar_aprendizado_automatico_pos_carga`. **Nota honesta**: ao
  corrigir isso, foi constatado que o padrão "self.log direto dentro de
  thread" na verdade aparece também no corpo principal de praticamente
  todo outro handler threaded do arquivo (`_executar_gerar_jogos`,
  calibração, fechamento, etc.) — só os blocos de `except` usam
  consistentemente as versões `_async`. Converter tudo teria escopo e
  risco bem maiores que o corrigido aqui; fica registrado como
  característica arquitetural conhecida, não resolvida por completo.
- **Bootstrap IC criava uma janela (Toplevel) fora da thread principal**
  — `_executar_bootstrap_ic` chamava `_abrir_janela_resultado_bootstrap`
  direto, sem `root.after`. Corrigido.
- **"Conferir resultado" manual não atualizava gráfico/painel** —
  `registrar_resultado`'s `confirmar()` não chamava
  `_atualizar_grafico_acertos()`/`_atualizar_painel_info()` como
  `conferir_jogos_gerados`/`ver_aprendizado` fazem. Corrigido.
- **Gráfico do Comparador com o mesmo padrão do bug já corrigido no
  gráfico de Acertos** (canvas sem `<Configure>`, podendo desenhar em
  1x1 antes do notebook mapear a aba). Corrigido com o mesmo binding,
  redesenhando com `self._resultados_comp` (já armazenado).
- **Tooltip de "💾 Salvar TXT" enganoso** — prometia "o relatório atual",
  mas a função só salva os números nus dos jogos. Texto corrigido.

**Limpeza de código órfão** (confirmado por grep em todo o repositório —
zero chamadores reais fora de si mesmos e de seus próprios testes —
suíte completa rodada depois, sem regressão):
- Removidos por inteiro: `v18_meta_otimizador.py`, `v18_1c_meta_ensemble.py`,
  `v18_2_montecarlo.py`, `v18_2b_auditor_cientifico.py`,
  `v19_1_benchmark.py`, `v19_1_cache_inteligente.py`,
  `v19_1_estabilidade.py`, `v19_1_telemetria.py`, `v20_3_ablation.py`,
  `v20_4_backtest_massivo.py`, `execucao_paralela.py`,
  `v21_3_1_dashboard_real.py`, `v21_3_1_historico_combinacoes.py`.
- **Sistema de plugins V22 removido por inteiro**: `v22_plugins.py`
  (`PluginManager`) nunca era instanciado em lugar nenhum — `plugins/
  frequencia.py` e `plugins/impopularidade.py` nunca chegavam a rodar.
  Removidos os dois arquivos, o diretório `plugins/`, a seção `plugins:`
  de `config_v22.yaml` e os acessores `ConfigV22.plugins()`/
  `plugins_ativos` (mortos junto).
- `v18_1b_ia_adaptativa.py` reduzido a só `carregar_pesos_modelos()` (a
  única função de fato usada, por `analise.py`) — as outras 5 funções
  (`registrar_resultado_modelo`, `calcular_rating_modelo`,
  `recalcular_pesos_adaptativos`, `gerar_hall_da_fama`,
  `salvar_pesos_modelos`) nunca tinham chamador: quem de fato escreve
  `pesos_modelos.json`/`historico_modelos.json` é
  `v20_2_poda_inteligente.py`, que por coincidência usa os mesmos nomes
  de arquivo.
- `v21_0_sqlite.db_registrar_geracao()` — o docstring afirmava ser
  "chamado por `apostas.registrar_performance_geracao()`", mas isso nunca
  foi verdade. Em vez de remover, foi conectado de fato (espelhamento
  best-effort no SQLite, mesmo padrão já usado para aprendizado). Já
  `db_salvar_peso_modelo`/`db_ultimos_pesos` foram removidas — não tinham
  nenhum chamador real, nem mesmo o módulo experimental que as usava
  (também removido).
- Testes reorganizados para acompanhar: `test_v19_modulos.py` →
  `test_v17_4_features.py` (só o que sobrou de válido: `v17_4_features`,
  que é usado de verdade por `backtest.py`/`genetico.py`);
  `test_v20_modulos.py` → `test_v20_2_poda_inteligente.py` (idem, só
  `v20_2_poda_inteligente`, que é usado de verdade por `backtest.py`);
  `test_execucao_paralela.py` removido junto com o módulo.

**Confirmado limpo, sem achados**: `genetico.py`, `historico.py`,
`utils.py`, `config.py`, `persistencia.py`, `fechamento.py`,
`v17_4_features.py`, `v20_2_poda_inteligente.py`, `v20_6_bootstrap.py`,
`v20_8_walkforward.py`, `v22_otimizador.py` (rebalanceamento de score
desta sessão confirmado internamente consistente), `v22_pipeline.py`
(flags de conclusão, já corrigidas antes, continuam corretas).

**Identificado mas deliberadamente não alterado nesta rodada** (achado
real, mas de menor risco/impacto — documentado para decisão futura, não
uma pendência esquecida): `v20_5_validacao_cientifica.py` tem só 2 de 6
funções públicas realmente chamadas pela UI (`benchmark_vs_aleatorio`,
`ganho_estatistico`); o próprio consolidador do módulo
(`gerar_relatorio_validacao`) nunca é usado — a UI reimplementa uma
fatia mais simples do relatório. A maior parte de `config_v22.yaml`
(seções `validacao`, `dashboard`, `caminhos`) também nunca é lida por
código real, porque o único consumidor completo dessas seções
(`v22_relatorio.py`/`v22_pipeline.py`) só é alcançável pelo Pipeline V22,
que já está documentado como órfão desde a rodada anterior.

## 🐛 Sexta rodada — 2026-07-21 (bug real achado pelo usuário no uso diário)

**Poda 4-Estados (V21.5-FULL) suspendia TODOS os modelos, sempre, com
passos suficientes — bug de calibração de limiares, não um veredito real
sobre os modelos.**

Usuário rodou o Backtest Científico com 150 passos e viu o relatório de
Poda 4-Fases mostrar os 7 modelos em SUSPENSO (fator 0.10, o mínimo).
Investigação em `v21_5_auto_poda_full.py`:

- Os limiares eram **absolutos**: observação < 9.10, quarentena < 9.00,
  suspenso < 8.90, recuperação ≥ 9.20 — numa escala onde o próprio
  comentário do código já dizia "9 = aleatório".
- A média real de QUALQUER modelo em Lotofácil gira em torno de 9.0
  (estatisticamente empatada com o acaso — confirmado por "Calibrar IA
  vs. Aleatório": vantagem média de score de -0.086, p-valor=1.0, Cohen's
  d=-0.024/desprezível). Ou seja: **nenhum modelo, mesmo o melhor
  possível, consegue ficar de forma sustentada acima de 9.10**, e
  praticamente nenhum passo individual chega a 9.20.
- Resultado: `rodadas_abaixo` (contador de degradação) incrementava em
  quase todo passo do backtest; `rodadas_acima` (contador de
  recuperação) quase nunca incrementava. Com passos suficientes (150,
  no caso do usuário), **todo modelo** descia inevitavelmente
  ATIVO→OBSERVAÇÃO→QUARENTENA→SUSPENSO e ficava preso lá — a
  recuperação exigia 2 rodadas seguidas ≥9.20, que na prática nunca
  acontece. O sistema não estava medindo desempenho *relativo* entre os
  7 modelos (que é o único sinal que faz sentido nesse domínio) — estava
  medindo "supera o acaso de forma absoluta", uma barra que nenhum
  modelo consegue sustentar. Zero testes cobriam este módulo antes desta
  correção, o que explica por que passou despercebido até o usuário
  notar no uso real.

**Correção**: os limiares viraram deltas **relativos à média do grupo
(dos 7 modelos) naquele mesmo passo**, não valores absolutos:
`DELTA_OBSERVACAO=-0.05`, `DELTA_SUSPENSO=-0.15`, `DELTA_RECUPERACAO=+0.05`.
`avaliar_estados_modelos()` agora calcula a média do grupo a cada
chamada e `_transicao()` compara cada modelo a essa média, não a um
número fixo. Isso restaura o propósito real do sistema: só modelos
consistentemente piores que os outros 6 degradam; só os
consistentemente melhores recuperam. `LIMIAR_QUARENTENA` (que já era
morto — nunca era checado na lógica, só aparecia no relatório) foi
removido; o relatório de limiares (`relatorio_poda_full()`/aba "✂️ Poda
4-Fases" no `ui.py`) foi atualizado para refletir os deltas relativos.

Adicionados 8 testes em `test_v21_5_auto_poda_full.py` (módulo não tinha
nenhum teste antes) cobrindo o cenário exato do bug (modelo empatado com
o grupo não pode degradar para sempre) e o comportamento correto
(modelo consistentemente pior degrada sozinho, sem arrastar os outros).

**Nota para quem já rodou backtests antes desta correção**: o arquivo
`estados_modelos_v21.json` (na pasta `dados/` do usuário) pode ter
modelos presos em SUSPENSO pelo bug antigo. Não precisa apagar/resetar
manualmente — a partir da próxima rodada de backtest, a avaliação já
passa a ser relativa ao grupo, e qualquer modelo com desempenho
realmente acima da média dos outros 6 volta a acumular `rodadas_acima`
e se recupera normalmente em algumas rodadas (2 rodadas por nível:
SUSPENSO→QUARENTENA→OBSERVAÇÃO→ATIVO).

## 🐛 Sétima rodada — 2026-07-21 (regressão da própria correção anterior)

**A correção da "Quinta rodada" (wiring do Walk-Forward Profissional)
dobrava o tempo de execução do botão "🔀 Walk-Forward" — e escondia um
segundo bug pré-existente que só aparecia quando a função era chamada de
verdade.**

Usuário reportou que, depois de rodar Walk-Forward, o relatório
"Walk-Forward Profissional" continuava vazio, e o app parecia travado
("ainda tá rodando", sem nenhuma linha nova no log). Investigação:

1. **Computação duplicada.** `executar_walkforward_profissional()` (a
   função que eu tinha conectado na Quinta rodada) roda `fn_gerar` — o
   algoritmo genético completo (G=16/P=40) — de novo, do zero, em CADA
   janela. Só que o Walk-Forward V20.8 (`relatorio_walkforward`, chamado
   logo antes na mesma tela) já tinha acabado de rodar exatamente as
   mesmas ~180 janelas com o mesmo `fn_gerar`. Ou seja: meu wiring
   dobrava silenciosamente o tempo do botão, sem avisar o usuário, e sem
   nenhum log de progresso por janela nessa função — por isso parecia
   travado, mas só estava recalculando tudo de novo.
2. **Bug pré-existente escondido pelo módulo estar órfão.** Ao chegar ao
   fim do cálculo (depois de esperar o dobro do tempo), a função
   quebrava com `TypeError: '<' not supported between instances of
   'float' and 'list'` — `detectar_overfitting_wf(scores_robo, [])`
   passava `[]` como segundo argumento posicional
   (`limiar_degradacao`, que deveria ser um float, ex. 0.85), erro que
   existia desde que o módulo foi escrito, mas nunca tinha sido
   detectado porque a função nunca tinha sido chamada de verdade antes
   da Quinta rodada (módulo órfão).

**Correção**: `v21_5_walkforward_profissional.py` ganhou
`registrar_walkforward_profissional(concursos, resultado_v20_8,
qtd_jogos)` — versão leve que REAPROVEITA as janelas e os scores do
robô já calculados por `relatorio_walkforward()` (só gera o baseline
aleatório por janela, que é barato — sem rodar o algoritmo genético de
novo). A lógica de cálculo dos indicadores foi extraída para
`_montar_indicadores()`, compartilhada entre a função antiga
(`executar_walkforward_profissional`, mantida para uso em scripts
standalone sem um resultado V20.8 pronto) e a nova. `ui.py` passou a
chamar `registrar_walkforward_profissional()` em vez de
`executar_walkforward_profissional()`. O bug do `detectar_overfitting_wf(...,
[])` foi corrigido para `detectar_overfitting_wf(scores_robo)` (usa o
padrão `limiar_degradacao=0.85`).

Adicionados 5 testes em `test_v21_5_walkforward_profissional.py`
(módulo também não tinha nenhum teste antes), incluindo um teste que
confirma explicitamente que `registrar_walkforward_profissional` NÃO
chama `fn_gerar` — a regressão de performance exata que motivou a
correção.

## 🔍 Oitava rodada — 2026-07-23 (nova varredura completa)

Usuário pediu uma segunda auditoria completa, focada em três perguntas
específicas: (1) ainda há inconsistências no código? (2) todas as
etapas de calibração realmente alimentam o ensemble? (3) o algoritmo
genético realmente influencia o aprendizado do robô? Lançados 4 agentes
paralelos read-only: rastreamento completo do pipeline
calibração→ensemble, verificação do algoritmo genético,
re-auditoria dos arquivos remendados nesta sessão, e varredura de áreas
não cobertas antes.

**Pergunta 2 e 3 — respostas confirmadas:**
- O algoritmo genético **realmente usa** `pesos_finais`: confirmado por
  rastreamento de código E por execução real — dobrar (triplicar, no
  teste automatizado) o peso de uma dezena elevou sua taxa de aparição
  de ~55% para ~92% nos jogos finais. Mutação (sempre 20-68%) e elitismo
  (sempre 12-34%) nunca zeram a evolução. Nenhum atalho contorna isso.
  Antes só verificado manualmente pela auditoria; agora coberto por 2
  testes novos em `test_analise_genetico.py`
  (`TestSensibilidadeAoPeso`, `TestEvoluir.test_populacao_nao_fica_identica_entre_geracoes`).
- Das etapas de calibração: 📊 Backtest, 🧪 Backtest Científico e (a
  partir desta rodada) 🤖 BT Automático alimentam poda/ELO; ⚡ Aprender
  e Conferir Jogos/Registrar Resultado alimentam a memória de
  aprendizado permanente; 🎯 Calibrar IA, 🩺 Auto Diagnóstico, ⚖️
  Comparador e o Otimizador são, por desenho, só medição/seleção (não
  alimentam nada, e não fingem alimentar).

**Bugs reais corrigidos:**

1. **🤖 BT Automático nunca alimentava poda inteligente/ELO**, apesar
   de fazer exatamente o mesmo tipo de trabalho que "📊 Backtest" (gera
   jogos de histórico passado, confere contra o resultado real
   seguinte). `executar_backtest_automatico()` (`ui.py`) agora monta
   `acertos_modelo` por passo (mesmo cálculo de `backtest_basico`) e
   chama `alimentar_poda_e_elo()` no final.
2. **Falha silenciosa na atualização do ELO.** A função que alimenta
   poda+ELO (renomeada de `_alimentar_poda_e_elo` para
   `alimentar_poda_e_elo`, agora pública — passou a ser usada também
   por `ui.py`) envolvia a parte do ELO num `except Exception: pass`
   sem log nenhum, enquanto a poda (bloco separado) podia funcionar e
   ser logada como sucesso, mascarando uma falha real do ELO. Agora
   retorna `(poda_resultado, erro_elo)`; todo call site loga
   `erro_elo` quando não é `None`.
3. **Perda silenciosa de dados no banco de desempenho histórico.**
   `salvar_ultimos_jogos_gerados()` (`ui.py`) persistia um `analise_min`
   sem as chaves `ensemble.ranking`/`ensemble.consenso`, que
   `registrar_desempenho_historico_robo()` (`backtest.py`) precisa pra
   calcular `top5/10/15_acertos` e `top_consenso`. Resultado: toda vez
   que o usuário fechava o app e no dia seguinte conferia um pacote
   restaurado do disco (fluxo comum), esses campos ficavam vazios sem
   nenhum aviso. Corrigido incluindo as duas chaves no `analise_min`.
4. **Exportação em PDF implementada mas sem nenhum botão na tela.**
   `exportar_apostas_pdf()` (`backtest.py`) já existia pronta (volante
   visual da Lotofácil via reportlab, com fallback pra TXT se a
   biblioteca não estiver instalada), mas nunca tinha wiring na UI.
   Adicionado botão "🖨️ Exportar PDF" na linha de relatórios. De
   brinde: corrigido o docstring/type hint da função, que afirmavam
   "retorna caminho do arquivo" (`str | None`) quando na verdade sempre
   retorna um dict (`{"arquivo", "formato", "jogos", ...}`).
5. **Pacote restaurado ao abrir o app não aparecia na aba "Jogos
   Gerados"** — 5ª instância do mesmo bug já corrigido 4 vezes esta
   sessão (falta de chamar `_atualizar_tabela_jogos()` depois de setar
   `self.jogos_gerados`/`analise`/`pesos`). Causa raiz: esse método tem
   o efeito colateral de trocar de aba automaticamente
   (`self._notebook_corpo.select(1)`), o que provavelmente levou
   alguém a evitar chamá-lo na inicialização pra não roubar o foco da
   tela. Corrigido com um parâmetro `mudar_aba: bool = True` — a
   restauração inicial agora popula a tabela sem trocar de aba.

**Correções menores:**

6. `selecionar_csv()` usava a caixa de diálogo de "salvar" (necessário,
   já que o campo também é usado por "⬆ Atualizar" pra apontar um CSV
   que ainda não existe) mas sem suprimir o aviso de "sobrescrever?" —
   adicionado `confirmoverwrite=False`.
7. Mensagem de erro do Bootstrap IC recomendava rodar "🤖 BT Automático"
   pra resolver a falta de dados, mas essa função nunca preenche
   `self.info_backtest` (usa `self.info_backtest_automatico`, sem
   `acertos_por_passo`) — recomendação corrigida pra só "📊 Backtest".
8. `v21_0_meta_aprendizado.py` reduzido a só `probabilidade_recuperacao()`
   (a única função com chamador real, em `analise.py`) —
   `recomendar_status()`, `avaliar_todos()`, `score_estabilidade()` e
   `calcular_peso_contextual()` nunca tinham chamador fora do próprio
   arquivo.
9. Tabela de módulos experimentais corrigida: `v21_5_meta_competitivo.py`
   e `v21_5_auto_poda_full.py` estavam listados como "Experimental —
   não integrado" quando na verdade ambos alimentam o pipeline real de
   poda/ELO; `v21_0_meta_aprendizado.py` atualizado pra refletir a
   redução do item 8.

**Confirmado limpo nesta rodada**: `_atualizar_tabela_jogos`/
`_atualizar_grafico_acertos`/`_atualizar_painel_info` (sem dados
obsoletos), chaves do `TEMA` (todas existem), nenhum TODO/FIXME
esquecido, `v21_5_meta_competitivo.py` (fórmulas de ELO corretas),
callsites de todas as funções com assinatura alterada nesta sessão,
nenhuma referência viva a módulos/constantes já removidos.

## 🐛 Nona rodada — 2026-07-26 (crash real reportado pelo usuário)

**A correção da "Oitava rodada" (item 5 — restaurar o pacote na aba
"Jogos Gerados" ao abrir o app) tinha uma lacuna não coberta pelos
agentes de auditoria: crashava com `KeyError: 'soma_media'`.**

Usuário reportou o traceback completo do Tkinter. Causa raiz:
`salvar_ultimos_jogos_gerados()` (`ui.py`) persiste um `analise_min`
deliberadamente reduzido (só `estrategia`, `ensemble.*`,
`cobertura_global`) — mas `score_jogo()` (`genetico.py`), chamado por
`avaliar_jogos()` toda vez que a aba "Jogos Gerados" é desenhada,
precisa também de `analise["soma_media"]` (indexação direta, sem
`.get()`) e `analise["hist_usado"]` (idem). Enquanto
`_atualizar_tabela_jogos()` nunca era chamada na inicialização (bug já
corrigido), esse gap nunca era exercitado — a correção anterior expôs
um problema pré-existente que estava "adormecido" há mais tempo.

**Correção em duas camadas** (a segunda é a que resolve o problema pra
quem já tem um arquivo salvo do jeito antigo, sem precisar apagar nada):
1. `salvar_ultimos_jogos_gerados()` agora também persiste
   `soma_media` e os últimos 30 concursos de `hist_usado` (suficiente
   pra `score_repeticao_recente`, que só olha os últimos 10, e pra
   impopularidade — evita persistir a janela histórica inteira).
2. `score_jogo()` (`genetico.py`) trocou `analise["soma_media"]`/
   `analise["hist_usado"]` por `.get(..., padrão)` — defensivo contra
   qualquer `analise` incompleto, incluindo arquivos já salvos antes
   desta correção (o usuário não precisa apagar nada; assim que gerar
   um novo pacote, o arquivo passa a ter os campos completos).

Adicionados 2 testes em `test_analise_genetico.py`
(`TestScoreJogoComAnaliseRestaurada`) replicando exatamente o cenário
do crash — `analise` mínimo sem `soma_media`/`hist_usado`, tanto via
`score_jogo()` direto quanto via `avaliar_jogos()` (o caminho real
usado pela tela).

## 🗺️ Mapa G×P — grade padrão troca G=300 por G=16 (config real) — 2026-07-27

A pedido do usuário, o último ponto da grade padrão de
`mapear_vale_gp()` (`v21_5_melhorias_cientificas.py`), que era
G=300/P=230 (o extremo teórico do estudo original de 2026-07-14),
virou **G=16/P=40 — a configuração real e fixa do sistema desde
2026-07-18**. Grade padrão agora: `[80, 100, 120, 140, 160, 200, 250,
16]`. Objetivo: em vez de mapear um extremo puramente teórico que
ninguém roda de verdade, o Mapa passa a comparar diretamente a
configuração de produção contra a grade de valores mais altos.

Detalhe de implementação: o P de cada ponto é calculado
proporcionalmente ao G (`P ≈ G × 0.767`, ratio do estudo original) —
mas para G=16 isso daria P=12 (`round(16*0.767)`), um valor que o robô
nunca usa de verdade. Por isso G=16 tem um caso especial na função:
sempre usa P=40 (o real), não o proporcional. Isso vale tanto pra grade
padrão quanto pra qualquer `pontos_g` customizado passado via
`mapa_gp_custom.py` — um G=16 na lista sempre usa P=40.

Efeito colateral esperado (não é bug, é o objetivo da mudança): como a
comparação pareada usa o menor e o maior valor de G como "extremos" de
referência (`g_min`/`g_max` depois de ordenar `pontos_g`), G=16 agora
assume o papel de extremo inferior no lugar de G=80 — a análise passa a
comparar diretamente "config real (G=16)" vs. "config mais alta com
maior score", em vez de "extremo baixo (G=80)" vs. "extremo alto
(G=300)" como antes.

`mapa_gp_custom.py` (script standalone, sempre passa seu próprio
`pontos_g` via linha de comando) não é afetado pela mudança do default,
mas seu docstring foi atualizado para não descrever a grade antiga como
atual.

## 🔬 Auditoria matemática das fórmulas de cálculo — 2026-07-27

Todas as auditorias anteriores desta sessão verificaram arquitetura,
integração e fiação entre módulos — nenhuma tinha verificado se as
próprias **fórmulas matemáticas/estatísticas** batem com suas
definições padrão. A pedido do usuário, 4 agentes paralelos (em
worktrees isolados, só leitura) reconferiram, com exemplos numéricos
concretos (não só leitura de código): Cohen's d (independente e
pareado), bootstrap percentile CI, TOST, testes de permutação
sign-flip, ELO (fórmula logística + atualização por K-factor), os 7
modelos do ensemble em `analise.py`, entropia de Shannon/score
estrutural do genético, e a combinatória de fechamento. **Resultado:
~90% das fórmulas conferem exatamente com a literatura/definição
padrão.** Foram encontrados 2 bugs reais e 2 imprecisões de
documentação, todos corrigidos nesta rodada:

1. **Bug: p-valor de teste de permutação podia dar exatamente 0.0**
   (`v20_6_bootstrap.py`, `teste_significancia()` e
   `teste_significancia_pareado()`). A fórmula era
   `contagem_extremos / n_reamostras`, mas a estatística observada é
   sempre uma das `n_reamostras + 1` permutações possíveis (a original
   está incluída) — então p=0.0 é logicamente impossível (afirmaria
   certeza absoluta de que o efeito é real). Corrigido para a correção
   +1 padrão da literatura de testes de permutação/randomização
   (Davison & Hinkley, 1997; North et al., 2002):
   `p_value = (contagem_extremos + 1) / (n_reamostras + 1)`. Não
   quebra nenhum teste existente (só há uma asserção de `p_value==1.0`
   exata, no caminho separado de "sem_dados", não afetado).

2. **Bug: `calcular_scores_pares_trios()` (`analise.py`, Modelo 7)
   nunca calculava trios de verdade.** Apesar do nome da função, do
   docstring e do comentário interno, só existia `combinations(jogo,
   2)` — o "bônus de trio" era, na real, a contagem bruta de quantos
   pares cada dezena participava (sem checar se o par excedia a
   expectativa hipergeométrica), aplicado incondicionalmente. Corrigido
   para calcular `combinations(jogo_ordenado, 3)` de verdade, com sua
   própria probabilidade esperada hipergeométrica
   (`C(15,3)/C(25,3) = 455/2300 ≈ 0.1978`), e para os dois bônus (par e
   trio) só serem aplicados quando a frequência observada realmente
   excede a esperada (`excesso > 0.0`) — antes o bônus de par era
   aplicado mesmo com `excesso == 0`.

3. **Documentação: docstring de `fator_elo()` (`v21_5_meta_competitivo.py`)
   tinha exemplos numéricos errados.** Afirmava ELO 1700 → fator ≈1.38
   e ELO 1300 → fator ≈0.72; a fórmula real (`10^((elo-1500)/800)`) dá
   1.7783 e 0.5623 respectivamente. Corrigido, e adicionados os valores
   nos extremos do clamp (ELO 1000/2500) mostrando o valor que a
   fórmula pura daria antes do `_clipar` entrar em ação.

4. **Documentação: docstring de `calcular_scores_neural_leve()`
   (`analise.py`, Modelo 5) sugeria uma rede neural treinada.** Na
   real é um perceptron de um único neurônio com pesos e bias
   *fixos/hardcoded* (1.10, 0.85, 0.55, 0.25, bias -0.35) — não há
   treinamento nem ajuste a partir de dados. Docstring corrigido para
   descrever o modelo honestamente.

Suite completa (368+ testes) reexecutada após as 4 correções — nenhuma
regressão.

## 🔬 Correção para múltiplas comparações no Mapa G×P — 2026-07-29

A pedido do usuário, `mapear_vale_gp()` (`v21_5_melhorias_cientificas.py`)
agora corrige seus p-valores para múltiplas comparações antes de decidir
o veredito `POSSIVEL_VALE`.

**Problema**: cada rodada do Mapa testa vários pontos de G (hoje, 7) ao
mesmo tempo contra a mesma referência, cada comparação usando o limiar
de significância padrão (5%) isoladamente. Testar várias hipóteses
simultaneamente infla a chance de pelo menos um "POSSIVEL_VALE" aparecer
só por acaso — o clássico problema de múltiplas comparações. O projeto
já tinha essa lógica implementada e testada em
`corrigir_multiplas_comparacoes()`/`consolidar_rodada_experimentos()`
(`auditoria_cientifica.py`, usada por `reanalise_pareada.py`), mas
`mapear_vale_gp()` nunca a chamava.

**Correção**: depois de calcular cohen_d/sig/TOST pareados para cada
comparação da rodada, os p-valores brutos são passados juntos para
`corrigir_multiplas_comparacoes()` (método Holm por padrão, mesmo
método já usado em `consolidar_rodada_experimentos()`), e o veredito
`POSSIVEL_VALE` passa a exigir `p_ajustado<0.05` em vez de `p_value<0.05`
bruto. Novo parâmetro opcional `metodo_correcao` ("holm" ou
"bonferroni"). Cada comparação em `comparacoes_pareadas` agora expõe os
dois valores (`p_value` bruto e `p_ajustado`) para transparência —
atualizado em `ui.py` e `mapa_gp_custom.py`.

Sem efeito no comportamento em nenhum caso já observado até aqui: o
único ponto que já cruzou o limiar bruto (5%) num mapa real (G=250,
p=0.0117 vs. G=16) tinha efeito "desprezível" e já não gerava
`POSSIVEL_VALE`; a correção só reforça essa margem de segurança contra
falsos positivos daqui pra frente. Testes adicionados em
`test_estatistica_pareada.py` (`TestMapearValeGp`): verificam que
`p_ajustado>=p_value` sempre (propriedade matemática de Holm/Bonferroni)
e que `vale_confirmado` é consistente com os vereditos reportados
mesmo quando uma configuração é deliberadamente favorecida no teste.
