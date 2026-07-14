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
| Módulo | Motivo |
|--------|--------|
| `analise_old.py` | Substituído pelo analise.py |
| `v17_4_features.py` | Features da V17, absorvidas pelo núcleo |
| `v18_1b_ia_adaptativa.py` | Substituído pelos modelos do analise.py |
| `v18_1c_meta_ensemble.py` | Substituído pelo ensemble do apostas.py |
| `v18_2_montecarlo.py` | Substituído pelo v21_5_montecarlo_cientifico |
| `v18_2b_auditor_cientifico.py` | Funcionalidade absorvida pelo backtest.py |
| `v18_3_parallel.py` | Paralelismo absorvido pelo backtest_massivo |
| `v18_meta_otimizador.py` | Substituído pelo genético atual |
| `v19_0_arquitetura_cientifica.py` | Base da V19, absorvida pelo núcleo V20+ |
| `v19_1_benchmark.py` | Substituído pelo v20_5_validacao_cientifica |
| `v19_1_cache_inteligente.py` | Cache não utilizado na V21 |
| `v19_1_estabilidade.py` | Absorvido pelo v20_5 |
| `v19_1_telemetria.py` | Telemetria não utilizada na V21 |
| `v20_2_poda_inteligente.py` | Substituído pelo v21_5_auto_poda_full |
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
equivalentes entre si. Recomendação: usar G=16/P=40 (mais barato, sem
perda de qualidade esperada).
Reexecutar `validacao_escala_real.py` reproduz este resultado.
