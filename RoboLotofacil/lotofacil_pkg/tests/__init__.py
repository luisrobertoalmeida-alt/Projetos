"""
lotofacil_pkg.tests
-------------------
Suite de testes unitários e de integração do RoboLotofacilPro V21.6.

Arquivos:
  test_utils.py                      — funções puras (utils, config)
  test_analise_genetico.py           — modelos IA, motor estratégico, algoritmo genético
  test_apostas_pipeline.py           — pipeline completo e memória adaptativa
  test_backtest.py                   — backtesting, laboratório e relatórios
  test_v19_modulos.py                — módulos V19 (benchmark, estabilidade, telemetria)
  test_v20_modulos.py                — módulos V20 (backtest massivo, poda, ablation)
  test_v20_novos_modulos.py          — V20.6 bootstrap e V20.8 walk-forward
  test_v20_5_validacao_cientifica.py — validação científica V20.5
  test_calibracao_estatistica.py     — V21.6: p-valor, IC95%, Cohen's d, critério aprovação

Rodar tudo:
  python -m unittest discover -s lotofacil_pkg/tests -p "test_*.py" -v

Rodar apenas o novo:
  python -m unittest lotofacil_pkg/tests/test_calibracao_estatistica -v
"""
