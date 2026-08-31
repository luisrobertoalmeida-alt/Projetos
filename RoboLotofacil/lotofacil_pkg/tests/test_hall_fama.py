"""
lotofacil_pkg/tests/test_hall_fama.py
---------------------------------------
Testes para v21_3_1_hall_fama_auto.py.

Cobre 3 bugs encontrados pelo usuário em 2026-08-08 (ver ARQUITETURA.md):
1. _score_composto() tratava pct_11/12/13 (escala 0-100) como se já
   fossem fração 0-1, inflando taxa_premio em ~100x e dominando o score.
2. relatorio_hall_fama() multiplicava pct_11_mais/pct_12_mais por 100 de
   novo na exibição (já vinham em 0-100), produzindo "9200.0%".
3. registrar_hall_fama() buscava ELO por "Modelo isolado: {modelo}" (nome
   usado pelo campeonato de modelos isolados em backtest.py), mas o banco
   de ELO usa só o nome puro -- a busca nunca batia, ELO sempre 1500.

registrar_hall_fama()/get_hall_fama() persistem em SQLite real (get_db(),
sem isolamento de teste) -- os testes aqui evitam chamar essas duas
funções diretamente, testando a lógica pura (_score_composto,
_nome_para_elo) e relatorio_hall_fama() com get_hall_fama() mockado.
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg.v21_3_1_hall_fama_auto import (
    _score_composto,
    _nome_para_elo,
    relatorio_hall_fama,
)


class TestNomeParaElo(unittest.TestCase):
    def test_remove_prefixo_modelo_isolado(self):
        self.assertEqual(_nome_para_elo("Modelo isolado: bayesiano"), "bayesiano")
        self.assertEqual(_nome_para_elo("Modelo isolado: pares_trios"), "pares_trios")

    def test_nome_sem_prefixo_fica_igual(self):
        self.assertEqual(_nome_para_elo("bayesiano"), "bayesiano")

    def test_so_remove_ate_o_primeiro_separador(self):
        self.assertEqual(_nome_para_elo("Configuração validada (G=100/P=77)"), "Configuração validada (G=100/P=77)")


class TestScoreComposto(unittest.TestCase):
    def test_percentuais_em_escala_0_100_nao_dominam_o_score(self):
        """
        Com pct_11/12/13 em escala 0-100 (real), o score composto tem que
        ficar numa faixa pequena e plausivel (0-1-ish, ver docstring),
        nao ser dominado por um termo de ~10-15 so por causa da escala
        errada (bug ate 2026-08-08).
        """
        sc = _score_composto(elo=1500.0, media_acertos=9.0, pct_11=92.0, pct_12=36.67, pct_13=2.0)
        self.assertLess(sc, 2.0)
        self.assertGreater(sc, -2.0)

    def test_score_cresce_com_elo_maior(self):
        base = _score_composto(elo=1500.0, media_acertos=9.0, pct_11=90.0, pct_12=30.0, pct_13=2.0)
        maior = _score_composto(elo=1800.0, media_acertos=9.0, pct_11=90.0, pct_12=30.0, pct_13=2.0)
        self.assertGreater(maior, base)

    def test_score_cresce_com_media_acertos_maior(self):
        base = _score_composto(elo=1500.0, media_acertos=9.0, pct_11=90.0, pct_12=30.0, pct_13=2.0)
        maior = _score_composto(elo=1500.0, media_acertos=11.0, pct_11=90.0, pct_12=30.0, pct_13=2.0)
        self.assertGreater(maior, base)


class TestRelatorioHallFama(unittest.TestCase):
    def test_percentual_nao_e_multiplicado_de_novo(self):
        """
        pct_11_mais/pct_12_mais ja vem em escala 0-100 do que
        registrar_hall_fama() armazena -- o relatorio nao pode multiplicar
        por 100 de novo (bug ate 2026-08-08, produzia "9200.0%").
        """
        ranking_fake = [{
            "posicao": 1, "nome": "bayesiano", "elo": 1700.0,
            "media_acertos": 9.1, "pct_11_mais": 92.0, "pct_12_mais": 36.67,
            "pct_13_mais": 2.0, "score_composto": 0.55,
        }]
        with patch("lotofacil_pkg.v21_3_1_hall_fama_auto.get_hall_fama", return_value=ranking_fake):
            texto = relatorio_hall_fama("geral")
        self.assertIn("92.0%", texto)
        self.assertIn("36.7%", texto)
        self.assertNotIn("9200", texto)
        self.assertNotIn("3667", texto)


if __name__ == "__main__":
    unittest.main()
