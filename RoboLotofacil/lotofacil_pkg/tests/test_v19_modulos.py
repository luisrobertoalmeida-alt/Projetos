"""
tests/test_v19_modulos.py
--------------------------
Testes unitários para os módulos V19.1:
  v19_1_benchmark, v19_1_estabilidade, v19_1_telemetria,
  v19_1_cache_inteligente, v19_0_arquitetura_cientifica,
  v17_4_features
"""
import os
import sys
import time
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from lotofacil_pkg.v19_1_benchmark import (
    comparar_modelos,
    resumo_benchmark,
    filtrar_modelos_ativos,
)
from lotofacil_pkg.v19_1_estabilidade import (
    score_estabilidade,
    analisar_estabilidade,
    classificar_estabilidade,
)
from lotofacil_pkg.v19_1_telemetria import Telemetria
from lotofacil_pkg.v17_4_features import (
    split_temporal,
    redundancia_media,
    cobertura_pares,
    cobertura_trios,
)

import random
from lotofacil_pkg.config import NUMEROS


def _hist(n=60, seed=99):
    random.seed(seed)
    return [sorted(random.sample(NUMEROS, 15)) for _ in range(n)]


# ── Benchmark ─────────────────────────────────────────────────────────────────

class TestCompararModelos(unittest.TestCase):
    def _modelos(self):
        return [
            {"nome": "markov", "score": 0.72},
            {"nome": "bayesiano", "score": 0.85},
            {"nome": "neural", "score": 0.60},
        ]

    def test_primeiro_e_o_maior(self):
        ranking = comparar_modelos(self._modelos())
        self.assertEqual(ranking[0]["nome"], "bayesiano")

    def test_ultimo_e_o_menor(self):
        ranking = comparar_modelos(self._modelos())
        self.assertEqual(ranking[-1]["nome"], "neural")

    def test_preserva_todos(self):
        modelos = self._modelos()
        self.assertEqual(len(comparar_modelos(modelos)), len(modelos))

    def test_lista_vazia(self):
        self.assertEqual(comparar_modelos([]), [])

    def test_sem_chave_score_tratado_como_zero(self):
        modelos = [{"nome": "x"}, {"nome": "y", "score": 0.5}]
        ranking = comparar_modelos(modelos)
        self.assertEqual(ranking[0]["nome"], "y")


class TestResumoBenchmark(unittest.TestCase):
    def _modelos(self):
        return [
            {"nome": "a", "score": 0.8},
            {"nome": "b", "score": 0.6},
            {"nome": "c", "score": 0.4},
        ]

    def test_lider_correto(self):
        r = resumo_benchmark(self._modelos())
        self.assertEqual(r["lider"], "a")

    def test_media_correta(self):
        r = resumo_benchmark(self._modelos())
        self.assertAlmostEqual(r["media_score"], (0.8 + 0.6 + 0.4) / 3, places=5)

    def test_total_correto(self):
        self.assertEqual(resumo_benchmark(self._modelos())["total"], 3)

    def test_vazio(self):
        r = resumo_benchmark([])
        self.assertIsNone(r["lider"])
        self.assertEqual(r["total"], 0)

    def test_desvio_zero_com_um_modelo(self):
        r = resumo_benchmark([{"nome": "x", "score": 0.5}])
        self.assertEqual(r["desvio_score"], 0.0)


class TestFiltrarModelosAtivos(unittest.TestCase):
    def test_remove_abaixo_do_limiar(self):
        modelos = [
            {"nome": "a", "score": 0.5},
            {"nome": "b", "score": 0.05},
        ]
        ativos = filtrar_modelos_ativos(modelos, limiar=0.10)
        self.assertEqual(len(ativos), 1)
        self.assertEqual(ativos[0]["nome"], "a")

    def test_nenhum_passa_retorna_todos(self):
        modelos = [{"nome": "x", "score": 0.01}]
        ativos = filtrar_modelos_ativos(modelos, limiar=0.50)
        self.assertEqual(len(ativos), 1)

    def test_todos_passam(self):
        modelos = [{"nome": str(i), "score": 0.5} for i in range(5)]
        self.assertEqual(len(filtrar_modelos_ativos(modelos)), 5)


# ── Estabilidade ──────────────────────────────────────────────────────────────

class TestScoreEstabilidade(unittest.TestCase):
    def test_range_valido(self):
        s = score_estabilidade(media=10.5, estabilidade=0.8, taxa11=0.6)
        self.assertGreaterEqual(s, 0.0)
        self.assertLessEqual(s, 1.0)

    def test_zeros_dao_zero(self):
        self.assertEqual(score_estabilidade(0.0, 0.0, 0.0), 0.0)

    def test_maximos_dao_um(self):
        # media=15 → norm=1, estabilidade=1, taxa11=1
        self.assertAlmostEqual(score_estabilidade(15.0, 1.0, 1.0), 1.0, places=5)

    def test_clipagem_superior(self):
        s = score_estabilidade(media=999.0, estabilidade=999.0, taxa11=999.0)
        self.assertLessEqual(s, 1.0)

    def test_clipagem_inferior(self):
        s = score_estabilidade(media=-1.0, estabilidade=-1.0, taxa11=-1.0)
        self.assertGreaterEqual(s, 0.0)


class TestAnalisarEstabilidade(unittest.TestCase):
    def _registros(self):
        return [
            {"media_acertos": 11.2, "melhor_acerto": 13},
            {"media_acertos": 10.8, "melhor_acerto": 12},
            {"media_acertos": 11.5, "melhor_acerto": 14},
            {"media_acertos": 10.5, "melhor_acerto": 11},
        ]

    def test_chaves_presentes(self):
        r = analisar_estabilidade(self._registros())
        for chave in ("media", "desvio", "indice_estabilidade",
                      "taxa_11_mais", "taxa_14_mais", "score", "total_registros"):
            self.assertIn(chave, r)

    def test_total_correto(self):
        self.assertEqual(analisar_estabilidade(self._registros())["total_registros"], 4)

    def test_taxa_11_correta(self):
        r = analisar_estabilidade(self._registros())
        # todos os 4 registros têm melhor_acerto >= 11
        self.assertAlmostEqual(r["taxa_11_mais"], 1.0, places=4)

    def test_taxa_14_correta(self):
        r = analisar_estabilidade(self._registros())
        # apenas 1 de 4 tem melhor_acerto >= 14
        self.assertAlmostEqual(r["taxa_14_mais"], 0.25, places=4)

    def test_vazio(self):
        r = analisar_estabilidade([])
        self.assertEqual(r["total_registros"], 0)
        self.assertEqual(r["score"], 0.0)

    def test_score_range(self):
        r = analisar_estabilidade(self._registros())
        self.assertGreaterEqual(r["score"], 0.0)
        self.assertLessEqual(r["score"], 1.0)


class TestClassificarEstabilidade(unittest.TestCase):
    def test_excelente(self):
        self.assertEqual(classificar_estabilidade(0.90), "EXCELENTE")

    def test_boa(self):
        self.assertEqual(classificar_estabilidade(0.65), "BOA")

    def test_regular(self):
        self.assertEqual(classificar_estabilidade(0.50), "REGULAR")

    def test_fraca(self):
        self.assertEqual(classificar_estabilidade(0.35), "FRACA")

    def test_insuficiente(self):
        self.assertEqual(classificar_estabilidade(0.10), "INSUFICIENTE")

    def test_limites_exatos(self):
        self.assertEqual(classificar_estabilidade(0.75), "EXCELENTE")
        self.assertEqual(classificar_estabilidade(0.60), "BOA")
        self.assertEqual(classificar_estabilidade(0.45), "REGULAR")
        self.assertEqual(classificar_estabilidade(0.30), "FRACA")


# ── Telemetria ────────────────────────────────────────────────────────────────

class TestTelemetria(unittest.TestCase):
    def test_finalizar_retorna_tempo_positivo(self):
        tel = Telemetria()
        tel.iniciar("etapa_x")
        time.sleep(0.01)
        elapsed = tel.finalizar("etapa_x")
        self.assertGreater(elapsed, 0.0)

    def test_multiplas_etapas_independentes(self):
        tel = Telemetria()
        tel.iniciar("a")
        tel.iniciar("b")
        time.sleep(0.01)
        tel.finalizar("a")
        tel.finalizar("b")
        self.assertIn("a", tel.dados)
        self.assertIn("b", tel.dados)

    def test_dados_inicialmente_vazio(self):
        self.assertEqual(Telemetria().dados, {})


# ── V17.4 Features ────────────────────────────────────────────────────────────

class TestSplitTemporal(unittest.TestCase):
    def setUp(self):
        self.hist = _hist(100)

    def test_tres_partes(self):
        treino, val, teste = split_temporal(self.hist)
        self.assertEqual(len(treino) + len(val) + len(teste), len(self.hist))

    def test_sem_sobreposicao(self):
        treino, val, teste = split_temporal(self.hist)
        ids_treino = {id(j) for j in treino}
        ids_val = {id(j) for j in val}
        ids_teste = {id(j) for j in teste}
        self.assertEqual(len(ids_treino & ids_val), 0)
        self.assertEqual(len(ids_val & ids_teste), 0)

    def test_proporcao_treino_dominante(self):
        treino, val, teste = split_temporal(self.hist)
        self.assertGreater(len(treino), len(val))
        self.assertGreater(len(treino), len(teste))

    def test_lista_vazia(self):
        self.assertEqual(split_temporal([]), ([], [], []))

    def test_lista_curta(self):
        hist = _hist(3)
        treino, val, teste = split_temporal(hist)
        self.assertEqual(len(treino) + len(val) + len(teste), 3)


class TestRedundanciaMedia(unittest.TestCase):
    def test_dois_jogos_identicos(self):
        jogo = sorted(random.sample(NUMEROS, 15))
        self.assertEqual(redundancia_media([jogo, jogo]), 15.0)

    def test_menos_de_dois_retorna_zero(self):
        self.assertEqual(redundancia_media([]), 0.0)
        self.assertEqual(redundancia_media([sorted(random.sample(NUMEROS, 15))]), 0.0)

    def test_valor_positivo(self):
        jogos = _hist(10)
        self.assertGreater(redundancia_media(jogos), 0.0)

    def test_range_razoavel(self):
        jogos = _hist(20)
        r = redundancia_media(jogos)
        self.assertGreaterEqual(r, 0.0)
        self.assertLessEqual(r, 15.0)


class TestCoberturaParesTrios(unittest.TestCase):
    def test_pares_positivos(self):
        jogos = _hist(5)
        self.assertGreater(cobertura_pares(jogos), 0)

    def test_trios_positivos(self):
        jogos = _hist(5)
        self.assertGreater(cobertura_trios(jogos), 0)

    def test_pares_cresce_com_mais_jogos(self):
        j5 = _hist(5)
        j20 = _hist(20)
        self.assertGreaterEqual(cobertura_pares(j20), cobertura_pares(j5))

    def test_trios_cresce_com_mais_jogos(self):
        j5 = _hist(5)
        j20 = _hist(20)
        self.assertGreaterEqual(cobertura_trios(j20), cobertura_trios(j5))

    def test_limite_maximo_pares(self):
        # C(25,2) = 300
        jogos = _hist(100)
        self.assertLessEqual(cobertura_pares(jogos), 300)

    def test_limite_maximo_trios(self):
        # C(25,3) = 2300
        jogos = _hist(100)
        self.assertLessEqual(cobertura_trios(jogos), 2300)

    def test_jogo_unico_pares(self):
        jogo = sorted(random.sample(NUMEROS, 15))
        from math import comb
        self.assertEqual(cobertura_pares([jogo]), comb(15, 2))

    def test_jogo_unico_trios(self):
        jogo = sorted(random.sample(NUMEROS, 15))
        from math import comb
        self.assertEqual(cobertura_trios([jogo]), comb(15, 3))


if __name__ == "__main__":
    unittest.main()
