"""
tests/test_v21_5_walkforward_profissional.py
------------------------------------------------
Testes para v21_5_walkforward_profissional.

Cobre a correção de 2026-07-21 (ver ARQUITETURA.md): a versão anterior
só tinha `executar_walkforward_profissional()`, que roda `fn_gerar` (o
algoritmo genético) do zero em cada janela — quando conectada ao botão
"🔀 Walk-Forward" da UI, isso dobrava o tempo de execução, já que o
Walk-Forward V20.8 (`relatorio_walkforward`) já tinha acabado de rodar
exatamente as mesmas janelas. `registrar_walkforward_profissional()`
reaproveita esse resultado (sem chamar `fn_gerar` de novo) e produz os
mesmos indicadores.
"""
import os
import sys
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg.v20_8_walkforward import relatorio_walkforward
from lotofacil_pkg.v21_5_walkforward_profissional import (
    executar_walkforward_profissional,
    registrar_walkforward_profissional,
    get_indicadores_permanentes,
)
import lotofacil_pkg.v21_5_walkforward_profissional as wf_prof
from lotofacil_pkg.config import NUMEROS


def _hist(n=260, seed=7):
    rng = random.Random(seed)
    return [sorted(rng.sample(NUMEROS, 15)) for _ in range(n)]


def _fn_gerar_estavel(historico_treino):
    """Gerador determinístico simples, só para exercitar o pipeline."""
    rng = random.Random(len(historico_treino))
    return [sorted(rng.sample(NUMEROS, 15)) for _ in range(10)]


class TestRegistrarWalkforwardProfissionalReaproveitaV20_8(unittest.TestCase):
    """A função leve não deve chamar fn_gerar de novo — só reaproveitar `rel`."""

    def setUp(self):
        self._tmpdb = tempfile.mkdtemp(prefix="robolotofacil_wf_prof_")

    def test_reaproveita_medias_ja_calculadas_sem_chamar_fn_gerar(self):
        concursos = _hist(260)
        rel = relatorio_walkforward(
            concursos, _fn_gerar_estavel,
            tamanho_treino=200, tamanho_teste=20, passo=20,
        )
        self.assertGreater(rel["walkforward"]["n_janelas"], 0)

        chamadas = {"n": 0}

        def fn_gerar_nao_deveria_ser_chamado(hist):
            chamadas["n"] += 1
            return _fn_gerar_estavel(hist)

        with patch("lotofacil_pkg.v21_5_walkforward_profissional._salvar_indicadores_sqlite"):
            ind = registrar_walkforward_profissional(concursos, rel, qtd_jogos=10)

        self.assertEqual(chamadas["n"], 0, "registrar_walkforward_profissional não deve rodar fn_gerar")
        self.assertEqual(ind["n_janelas"], rel["walkforward"]["n_janelas"])
        self.assertIn("robustez_temporal", ind)
        self.assertIn("estabilidade", ind)
        self.assertIn("veredito", ind)

    def test_sem_janelas_retorna_erro_sem_lancar_excecao(self):
        rel_vazio = {"walkforward": {"janelas": []}}
        ind = registrar_walkforward_profissional([], rel_vazio, qtd_jogos=10)
        self.assertEqual(ind["n_janelas"], 0)
        self.assertIn("erro", ind)


class TestExecutarWalkforwardProfissionalAindaFunciona(unittest.TestCase):
    """Garante que o refactor (extração de _montar_indicadores) não quebrou a via antiga."""

    def test_executa_do_zero_com_fn_gerar(self):
        concursos = _hist(260)
        with patch("lotofacil_pkg.v21_5_walkforward_profissional._salvar_indicadores_sqlite"):
            ind = executar_walkforward_profissional(
                concursos, _fn_gerar_estavel,
                tamanho_treino=200, tamanho_teste=20, passo=20, qtd_jogos=10,
            )
        self.assertGreater(ind["n_janelas"], 0)
        self.assertIn("robustez_temporal", ind)
        self.assertIn("veredito", ind)

    def test_historico_insuficiente_retorna_erro(self):
        ind = executar_walkforward_profissional(
            _hist(10), _fn_gerar_estavel,
            tamanho_treino=200, tamanho_teste=20, passo=20,
        )
        self.assertEqual(ind["n_janelas"], 0)
        self.assertIn("erro", ind)


class TestGetIndicadoresPermanentes(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="robolotofacil_wf_prof_get_")
        self._db_path_original = None

    def test_sem_historico_retorna_vazio(self):
        with patch("lotofacil_pkg.v21_5_walkforward_profissional._carregar_historico_walkforward", return_value=[]):
            ind = get_indicadores_permanentes()
        self.assertEqual(ind["n_execucoes"], 0)
        self.assertEqual(ind["historico"], [])


if __name__ == "__main__":
    unittest.main()
