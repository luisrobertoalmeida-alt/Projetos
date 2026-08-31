"""
lotofacil_pkg/tests/test_v21_0_auto_poda.py
-------------------------------------------------
Testes para v21_0_auto_poda.py (poda adaptativa por limiar dinâmico
SQLite), módulo confirmado como ATIVO (usado por ui.py via
calcular_limiares/relatorio_auto_poda e por analise.py via
decidir_poda_adaptativa -- não é código morto).

Isolamento: as funções db_limiar_dinamico/db_prob_recuperacao/get_db
tocam o SQLite real de produção (lotofacil_pkg/v21_0_sqlite.py não
respeita ROBOLOTOFACIL_DADOS_DIR -- lacuna conhecida, documentada em
ARQUITETURA.md). Por isso todos os testes aqui usam
unittest.mock.patch nos nomes importados dentro de v21_0_auto_poda,
sem nunca abrir uma conexão real.
"""
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg import v21_0_auto_poda as auto_poda


class TestCalcularLimiares(unittest.TestCase):
    def test_usa_limiar_do_banco_quando_disponivel(self):
        with patch.object(auto_poda, "db_limiar_dinamico", return_value=10.5):
            ativo, observacao = auto_poda.calcular_limiares([])
        # limiar_score = (10.5 - 9.0) / 4.0 = 0.375
        self.assertAlmostEqual(observacao, 0.375)
        self.assertAlmostEqual(ativo, 0.575)

    def test_limiar_do_banco_e_limitado_a_0_1(self):
        with patch.object(auto_poda, "db_limiar_dinamico", return_value=999.0):
            ativo, observacao = auto_poda.calcular_limiares([])
        self.assertEqual(observacao, 1.0)
        # ativo = limiar_score (clampado a 1.0) + 0.20, sem clamp adicional
        self.assertEqual(ativo, 1.2)

    def test_fallback_sem_banco_e_sem_scores(self):
        with patch.object(auto_poda, "db_limiar_dinamico", return_value=0.0):
            ativo, observacao = auto_poda.calcular_limiares([])
        self.assertEqual((ativo, observacao), (0.70, 0.50))

    def test_fallback_sem_banco_com_scores(self):
        with patch.object(auto_poda, "db_limiar_dinamico", return_value=0.0):
            ativo, observacao = auto_poda.calcular_limiares([0.5, 0.6])
        # media = 0.55 -> ativo = min(0.90, 0.65) = 0.65 ; observacao = max(0.30, 0.45) = 0.45
        self.assertAlmostEqual(ativo, 0.65)
        self.assertAlmostEqual(observacao, 0.45)


class TestCalcularLimiarPercentil(unittest.TestCase):
    def test_delega_para_db_limiar_dinamico_com_percentil(self):
        with patch.object(auto_poda, "db_limiar_dinamico", return_value=8.5) as mock_db:
            resultado = auto_poda.calcular_limiar_percentil(percentil=15.0)
        mock_db.assert_called_once_with(15.0)
        self.assertEqual(resultado, 8.5)


class TestSuavizarLimiar(unittest.TestCase):
    def test_formula_padrao(self):
        # alpha=0.30 -> 0.30*10 + 0.70*5 = 3 + 3.5 = 6.5
        self.assertAlmostEqual(auto_poda.suavizar_limiar(10.0, 5.0), 6.5)

    def test_alpha_customizado(self):
        self.assertAlmostEqual(auto_poda.suavizar_limiar(10.0, 5.0, alpha=1.0), 10.0)
        self.assertAlmostEqual(auto_poda.suavizar_limiar(10.0, 5.0, alpha=0.0), 5.0)


class TestDecidirPodaAdaptativa(unittest.TestCase):
    def test_poda_quando_abaixo_do_limiar_e_baixa_recuperacao(self):
        with patch.object(auto_poda, "db_limiar_dinamico", return_value=10.0), \
             patch.object(auto_poda, "db_prob_recuperacao", return_value=0.1):
            resultado = auto_poda.decidir_poda_adaptativa("modelo_x", score_global=0.1)
        # score_acertos = 9.0 + 0.1*4 = 9.4 < 10.0 -> abaixo_limiar
        # prob=0.1 < limiar_prob padrão 0.30 -> baixa_recuperacao
        self.assertTrue(resultado["abaixo_limiar"])
        self.assertTrue(resultado["baixa_recuperacao"])
        self.assertEqual(resultado["decisao"], "PODAR")

    def test_mantem_quando_recuperacao_alta(self):
        with patch.object(auto_poda, "db_limiar_dinamico", return_value=10.0), \
             patch.object(auto_poda, "db_prob_recuperacao", return_value=0.9):
            resultado = auto_poda.decidir_poda_adaptativa("modelo_x", score_global=0.1)
        self.assertTrue(resultado["abaixo_limiar"])
        self.assertFalse(resultado["baixa_recuperacao"])
        self.assertEqual(resultado["decisao"], "MANTER")

    def test_mantem_quando_acima_do_limiar(self):
        with patch.object(auto_poda, "db_limiar_dinamico", return_value=9.0), \
             patch.object(auto_poda, "db_prob_recuperacao", return_value=0.1):
            resultado = auto_poda.decidir_poda_adaptativa("modelo_x", score_global=0.9)
        self.assertFalse(resultado["abaixo_limiar"])
        self.assertEqual(resultado["decisao"], "MANTER")

    def test_sem_historico_suficiente_nunca_poda(self):
        # limiar <= 0 (histórico insuficiente) -> abaixo_limiar sempre False
        with patch.object(auto_poda, "db_limiar_dinamico", return_value=0.0), \
             patch.object(auto_poda, "db_prob_recuperacao", return_value=0.0):
            resultado = auto_poda.decidir_poda_adaptativa("modelo_x", score_global=0.0)
        self.assertFalse(resultado["abaixo_limiar"])
        self.assertEqual(resultado["decisao"], "MANTER")


class TestRelatorioAutoPoda(unittest.TestCase):
    def _fake_conn(self, model_rows, payload_por_modelo):
        """Constrói uma conexão fake cujo .execute(...).fetchall() varia
        conforme a query (lista de model_ids vs. eventos de um model_id)."""
        conn = MagicMock()

        def _execute(sql, params=None):
            resultado = MagicMock()
            if "DISTINCT model_id" in sql:
                resultado.fetchall.return_value = model_rows
            else:
                mid = params[0]
                resultado.fetchall.return_value = payload_por_modelo.get(mid, [])
            return resultado

        conn.execute.side_effect = _execute
        return conn

    def test_calcula_score_medio_dos_eventos_do_modelo(self):
        model_rows = [{"model_id": "modelo_a"}]
        payload_por_modelo = {
            "modelo_a": [
                {"payload": json.dumps({"score": 0.4})},
                {"payload": json.dumps({"score": 0.6})},
            ]
        }
        conn = self._fake_conn(model_rows, payload_por_modelo)
        with patch.object(auto_poda, "get_db", return_value=conn), \
             patch.object(auto_poda, "db_limiar_dinamico", return_value=0.0), \
             patch.object(auto_poda, "db_prob_recuperacao", return_value=0.5):
            resultados = auto_poda.relatorio_auto_poda()
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["nome"], "modelo_a")
        self.assertAlmostEqual(resultados[0]["score_global"], 0.5)

    def test_modelo_sem_eventos_com_score_usa_default_0_5(self):
        model_rows = [{"model_id": "modelo_b"}]
        payload_por_modelo = {"modelo_b": [{"payload": "{}"}]}
        conn = self._fake_conn(model_rows, payload_por_modelo)
        with patch.object(auto_poda, "get_db", return_value=conn), \
             patch.object(auto_poda, "db_limiar_dinamico", return_value=0.0), \
             patch.object(auto_poda, "db_prob_recuperacao", return_value=0.5):
            resultados = auto_poda.relatorio_auto_poda()
        self.assertEqual(resultados[0]["score_global"], 0.5)

    def test_payload_invalido_e_ignorado_sem_quebrar(self):
        model_rows = [{"model_id": "modelo_c"}]
        payload_por_modelo = {"modelo_c": [{"payload": "não é json"}]}
        conn = self._fake_conn(model_rows, payload_por_modelo)
        with patch.object(auto_poda, "get_db", return_value=conn), \
             patch.object(auto_poda, "db_limiar_dinamico", return_value=0.0), \
             patch.object(auto_poda, "db_prob_recuperacao", return_value=0.5):
            resultados = auto_poda.relatorio_auto_poda()
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["score_global"], 0.5)

    def test_sem_modelos_retorna_lista_vazia(self):
        conn = self._fake_conn([], {})
        with patch.object(auto_poda, "get_db", return_value=conn):
            resultados = auto_poda.relatorio_auto_poda()
        self.assertEqual(resultados, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
