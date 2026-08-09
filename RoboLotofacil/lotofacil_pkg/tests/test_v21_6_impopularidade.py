"""
lotofacil_pkg/tests/test_v21_6_impopularidade.py
-------------------------------------------------------
Testes para v21_6_impopularidade.py (score de valor esperado por
impopularidade). Módulo 100% puro (sem I/O, sem estado global,
conforme a própria docstring do arquivo) -- não há necessidade de
isolamento de dados aqui.
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from lotofacil_pkg import v21_6_impopularidade as impop


class TestDetectarDatasMagneticas(unittest.TestCase):
    def test_todas_magneticas(self):
        jogo = list(range(1, 16))  # 1-15, todas em _DATAS_MAGNETICAS
        self.assertEqual(impop.detectar_datas_magneticas(jogo), 1.0)

    def test_metade_magnetica(self):
        jogo = [1, 2, 16, 17]  # 1,2 magnéticas; 16,17 não
        self.assertEqual(impop.detectar_datas_magneticas(jogo), 0.5)

    def test_lista_vazia_nao_quebra(self):
        self.assertEqual(impop.detectar_datas_magneticas([]), 0.0)


class TestDetectarTerminacoesRedondas(unittest.TestCase):
    def test_fracao_correta(self):
        jogo = [5, 10, 15, 1, 2]  # 3 de 5 são terminações redondas
        self.assertAlmostEqual(impop.detectar_terminacoes_redondas(jogo), 0.6)

    def test_nenhuma_redonda(self):
        jogo = [1, 2, 3, 4]
        self.assertEqual(impop.detectar_terminacoes_redondas(jogo), 0.0)


class TestDetectarSequenciasLongasHumanas(unittest.TestCase):
    def test_sem_sequencias(self):
        self.assertEqual(impop.detectar_sequencias_longas_humanas([1, 3, 5, 7, 9]), 0.0)

    def test_sequencia_de_exatos_4_conta(self):
        # 1,2,3,4 formam sequência de 4 (limiar mínimo); 10 fica de fora.
        resultado = impop.detectar_sequencias_longas_humanas([1, 2, 3, 4, 10])
        self.assertAlmostEqual(resultado, 4 / 5)

    def test_sequencia_de_3_nao_conta(self):
        # Sequência de apenas 3 consecutivos não atinge o limiar (>=4).
        self.assertEqual(impop.detectar_sequencias_longas_humanas([1, 2, 3, 10, 20]), 0.0)

    def test_duplicatas_sao_ignoradas(self):
        # set() remove duplicatas antes de procurar sequências.
        resultado = impop.detectar_sequencias_longas_humanas([1, 1, 2, 3, 4])
        self.assertAlmostEqual(resultado, 4 / 4)


class TestDetectarPadraoGeometrico(unittest.TestCase):
    def test_linha_completa_da_sobreposicao_maxima(self):
        jogo = [1, 2, 3, 4, 5, 10, 15]  # linha 1 (1-5) inteira presente
        self.assertEqual(impop.detectar_padrao_geometrico(jogo), 1.0)

    def test_diagonal_principal_completa(self):
        jogo = [1, 7, 13, 19, 25]  # diagonal principal inteira
        self.assertEqual(impop.detectar_padrao_geometrico(jogo), 1.0)

    def test_sem_padrao_relevante(self):
        jogo = [1, 8, 14]  # não completa nenhuma linha/coluna/diagonal
        self.assertLess(impop.detectar_padrao_geometrico(jogo), 1.0)


class TestDetectarEquilibrioForcado(unittest.TestCase):
    def test_distribuicao_perfeitamente_uniforme_tem_irregularidade_zero(self):
        # Diagonal principal: 1 dezena por linha E por coluna.
        jogo = [1, 7, 13, 19, 25]
        self.assertEqual(impop.detectar_equilíbrio_forcado(jogo), 0.0)

    def test_distribuicao_concentrada_tem_irregularidade_maior_que_zero(self):
        jogo = [1, 2, 3, 4, 5]  # tudo na linha 1
        self.assertGreater(impop.detectar_equilíbrio_forcado(jogo), 0.0)


class TestScoreImpopularidade(unittest.TestCase):
    def test_jogo_vazio_retorna_zero(self):
        self.assertEqual(impop.score_impopularidade([]), 0.0)

    def test_peso_zero_ou_negativo_retorna_zero(self):
        jogo = list(range(1, 16))
        self.assertEqual(impop.score_impopularidade(jogo, peso=0.0), 0.0)
        self.assertEqual(impop.score_impopularidade(jogo, peso=-1.0), 0.0)

    def test_jogo_com_tamanho_diferente_de_15_retorna_zero(self):
        self.assertEqual(impop.score_impopularidade([1, 2, 3]), 0.0)

    def test_repetir_concurso_recente_reduz_o_score(self):
        jogo = sorted([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16])
        sem_repeticao = impop.score_impopularidade(jogo, hist_recente=None, peso=1.0)
        com_repeticao = impop.score_impopularidade(jogo, hist_recente=[jogo], peso=1.0)
        self.assertAlmostEqual(com_repeticao, round(sem_repeticao - 0.30, 5))

    def test_repeticao_fora_da_janela_de_5_nao_afeta(self):
        jogo = sorted([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16])
        outro = sorted([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17])
        hist_distante = [jogo] + [outro] * 5  # jogo cai fora dos últimos 5
        sem_repeticao = impop.score_impopularidade(jogo, hist_recente=None, peso=1.0)
        com_hist_distante = impop.score_impopularidade(jogo, hist_recente=hist_distante, peso=1.0)
        self.assertAlmostEqual(sem_repeticao, com_hist_distante)

    def test_peso_escala_linearmente_o_score(self):
        jogo = sorted([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16])
        score_total = impop.score_impopularidade(jogo, peso=1.0)
        score_metade = impop.score_impopularidade(jogo, peso=0.5)
        self.assertAlmostEqual(score_metade, round(score_total * 0.5, 5), places=3)


class TestResumoImpopularidadePacote(unittest.TestCase):
    def test_lista_vazia_retorna_estrutura_default(self):
        resumo = impop.resumo_impopularidade_pacote([])
        self.assertEqual(resumo["media_score"], 0.0)
        self.assertEqual(resumo["jogos_acima_zero"], 0)
        self.assertEqual(resumo["interpretacao"], "Sem jogos.")

    def test_estrutura_com_jogos_reais(self):
        jogos = [
            sorted([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16]),
            sorted([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17]),
        ]
        resumo = impop.resumo_impopularidade_pacote(jogos)
        for chave in ("media_score", "max_score", "min_score", "media_datas",
                      "media_redondas", "media_seq_longas", "media_padrao_geo",
                      "media_irregularidade", "jogos_acima_zero", "interpretacao",
                      "peso_ativo"):
            self.assertIn(chave, resumo)
        self.assertEqual(resumo["min_score"] <= resumo["media_score"] <= resumo["max_score"], True)

    def test_interpretacao_por_faixa_de_media(self):
        jogos = [[1], [2]]  # conteúdo irrelevante, score_impopularidade é mockado
        casos = [
            (0.50, "muito impopular"),
            (0.20, "moderadamente impopular"),
            (0.0, "neutro"),
            (-0.50, "popular"),
        ]
        for valor_medio, trecho_esperado in casos:
            with patch.object(impop, "score_impopularidade", return_value=valor_medio):
                resumo = impop.resumo_impopularidade_pacote(jogos)
            self.assertIn(trecho_esperado, resumo["interpretacao"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
