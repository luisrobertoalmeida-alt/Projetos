"""
lotofacil_pkg.tests
-------------------
Suite de testes unitários e de integração do RoboLotofacilPro V21.6.

Arquivos:
  test_utils.py                      — funções puras (utils, config)
  test_analise_genetico.py           — modelos IA, motor estratégico, algoritmo genético
  test_apostas_pipeline.py           — pipeline completo e memória adaptativa
  test_backtest.py                   — backtesting, laboratório e relatórios
  test_v17_4_features.py             — split temporal, redundância, cobertura de pares/trios
  test_v20_2_poda_inteligente.py     — poda inteligente de modelos (score/estado/quarentena)
  test_v21_5_auto_poda_full.py       — poda 4-estados (transições relativas ao grupo)
  test_v21_5_walkforward_profissional.py — indicadores permanentes (reaproveita V20.8)
  test_v20_novos_modulos.py          — V20.6 bootstrap e V20.8 walk-forward
  test_v20_5_validacao_cientifica.py — validação científica V20.5
  test_calibracao_estatistica.py     — V21.6: p-valor, IC95%, Cohen's d, critério aprovação
  test_fechamento.py                 — fechamento combinatório de garantia total e reduzido
  test_estatistica_pareada.py        — Cohen's d pareado, sign-flip, TOST, mapear_vale_gp/diversidade()
  test_auditoria_cientifica.py       — auditoria científica contínua
  test_hall_fama.py                  — Hall da Fama (normalização de nome p/ ELO, score composto)
  test_persistencia.py               — persistencia.py (funções puras, sem I/O real)
  test_limpar_registros_impossiveis.py — detecção de registros impossíveis no Banco Histórico
  test_v21_0_auto_poda.py            — poda adaptativa por limiar dinâmico SQLite
  test_v21_5_meta_competitivo.py     — ranking ELO dos modelos
  test_v21_6_impopularidade.py       — score de valor esperado por impopularidade
  test_v21_0_meta_aprendizado.py     — probabilidade de recuperação por modelo

  Nota (2026-07-19): test_v19_modulos.py, test_v20_modulos.py e
  test_execucao_paralela.py foram removidos junto com os módulos órfãos
  que testavam (ver ARQUITETURA.md).

Rodar tudo:
  python -m unittest discover -s lotofacil_pkg/tests -p "test_*.py" -v

Rodar apenas o novo:
  python -m unittest lotofacil_pkg/tests/test_calibracao_estatistica -v

ISOLAMENTO DE DADOS (achado de auditoria, 2026-07-15): v18_1b_ia_adaptativa.py
e v20_2_poda_inteligente.py calculam seus próprios caminhos de arquivo
(`ARQ_PESOS`/`ARQ_HIST`, `_ARQ_PESOS`/`_ARQ_HIST`) relativos ao próprio
pacote — `dados/pesos_modelos.json` e `dados/historico_modelos.json` —
em vez de usar `config.PASTA_DADOS` como o resto do projeto. Sem
isolamento, qualquer teste que exercite o ensemble/aprendizado (mesmo
indiretamente, via apostas.py/backtest.py -- ex.: setUpClass de
test_backtest.py chamando backtest_basico()) SOBRESCREVE esses dois
arquivos reais do repositório com valores calculados a partir do
histórico sintético dos próprios testes — silenciosamente, sem erro.

A correção definitiva é a variável de ambiente ROBOLOTOFACIL_DADOS_DIR,
checada por esses dois módulos no momento do import (não por monkeypatch
de atributo depois — essa abordagem se mostrou frágil quando algum teste
importa esses módulos antes do patch rodar).

IMPORTANTE — por que a variável é setada AQUI *e também* em cada arquivo
de teste: o comando oficial deste projeto,
    python -m unittest discover -s lotofacil_pkg/tests -p "test_*.py"
carrega os arquivos de teste diretamente por caminho de arquivo e, na
prática, NÃO garante a execução deste __init__.py antes de importar os
módulos de teste (confirmado empiricamente: logo após
`unittest.TestLoader().discover(...)`, 'lotofacil_pkg.tests' está
ausente de sys.modules). Ou seja, depender só deste arquivo para setar
a variável de ambiente não protege o `discover` oficial.

Por isso a correção que de fato funciona sob `discover` está inline em
cada um dos 12 arquivos de teste relevantes (logo após o
`sys.path.insert(...)` de cada um): cada arquivo seta
ROBOLOTOFACIL_DADOS_DIR (via `setdefault`, então não sobrescreve se já
setado) antes de importar qualquer módulo do pacote. Essa é a proteção
primária, validada rodando o comando oficial acima com instrumentação
de escrita de arquivo e comparando hashes de
dados/pesos_modelos.json e dados/historico_modelos.json antes/depois
(idênticos) com os 412 testes passando.

O que este __init__.py faz aqui embaixo permanece como rede de segurança
secundária, relevante apenas para invocações por nome pontilhado (ex.:
`python -m unittest lotofacil_pkg.tests.test_backtest`), onde o pacote
É importado normalmente e este arquivo roda antes de tudo.
"""
import atexit
import os
import shutil
import tempfile

_DIR_TEMP_TESTES = tempfile.mkdtemp(prefix="robolotofacil_testes_")
os.environ["ROBOLOTOFACIL_DADOS_DIR"] = _DIR_TEMP_TESTES
atexit.register(shutil.rmtree, _DIR_TEMP_TESTES, True)
