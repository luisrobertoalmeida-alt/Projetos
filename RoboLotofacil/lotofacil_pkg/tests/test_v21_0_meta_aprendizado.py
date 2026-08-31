"""
lotofacil_pkg/tests/test_v21_0_meta_aprendizado.py
-------------------------------------------------------
Testes para v21_0_meta_aprendizado.py, reduzido em 2026-07-23 (ver
ARQUITETURA.md, tarefa #28) a apenas `probabilidade_recuperacao()` --
a única função com chamador real (analise.py). As demais funções do
módulo original foram removidas por serem código morto.

Isolamento: db_prob_recuperacao toca o SQLite real (lacuna de
isolamento conhecida em v21_0_sqlite.py), então é sempre mockado aqui.
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg.v21_0_meta_aprendizado import MetaAprendizadoModelos


class TestProbabilidadeRecuperacao(unittest.TestCase):
    def setUp(self):
        self.meta = MetaAprendizadoModelos()

    def test_usa_valor_do_banco_quando_ha_historico_real(self):
        with patch("lotofacil_pkg.v21_0_meta_aprendizado.db_prob_recuperacao", return_value=0.8):
            resultado = self.meta.probabilidade_recuperacao([], model_id="modelo_x")
        self.assertEqual(resultado, 0.8)

    def test_banco_retornando_exatamente_0_5_cai_no_fallback(self):
        # 0.5 é o valor sentinela de "sem histórico" -> ignora e usa série temporal.
        historico = [0.6, 0.3, 0.6, 0.3, 0.6]
        with patch("lotofacil_pkg.v21_0_meta_aprendizado.db_prob_recuperacao", return_value=0.5):
            resultado = self.meta.probabilidade_recuperacao(historico, model_id="modelo_x")
        self.assertNotEqual(resultado, 0.5)  # deve ter calculado pela série temporal

    def test_erro_no_banco_cai_no_fallback_sem_quebrar(self):
        with patch("lotofacil_pkg.v21_0_meta_aprendizado.db_prob_recuperacao",
                   side_effect=RuntimeError("sem sqlite")):
            resultado = self.meta.probabilidade_recuperacao([], model_id="modelo_x")
        self.assertEqual(resultado, 0.50)  # fallback com histórico vazio

    def test_sem_model_id_usa_direto_a_serie_temporal(self):
        with patch("lotofacil_pkg.v21_0_meta_aprendizado.db_prob_recuperacao") as mock_db:
            resultado = self.meta.probabilidade_recuperacao([], model_id=None)
        mock_db.assert_not_called()
        self.assertEqual(resultado, 0.50)

    def test_fallback_com_menos_de_5_pontos_retorna_neutro(self):
        resultado = self.meta.probabilidade_recuperacao([0.3, 0.6, 0.3], model_id=None)
        self.assertEqual(resultado, 0.50)

    def test_fallback_calcula_taxa_de_recuperacao_apos_queda(self):
        # Quedas (valor anterior < 0.5): índices 1,3 (0.3 e 0.3).
        # Recuperação real (valor seguinte > valor anterior): ambas recuperam.
        historico = [0.6, 0.3, 0.6, 0.3, 0.6]
        resultado = self.meta.probabilidade_recuperacao(historico, model_id=None)
        self.assertEqual(resultado, 1.0)

    def test_fallback_sem_nenhuma_queda_nao_divide_por_zero(self):
        historico = [0.6, 0.7, 0.8, 0.9, 1.0]  # nunca cai abaixo de 0.5
        resultado = self.meta.probabilidade_recuperacao(historico, model_id=None)
        self.assertEqual(resultado, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
