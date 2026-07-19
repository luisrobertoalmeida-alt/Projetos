"""
tests/test_v17_4_features.py
------------------------------
Testes unitários para v17_4_features (split temporal, redundância,
cobertura de pares/trios) — usado por backtest.py e genetico.py.

Antes vivia em test_v19_modulos.py junto com os testes de
v19_1_benchmark/v19_1_estabilidade/v19_1_telemetria; esses três módulos
eram código órfão (nunca chamados fora de si mesmos e de seus próprios
testes) e foram removidos em 2026-07-19 (ver ARQUITETURA.md). Este
arquivo mantém apenas os testes do que continua em uso real.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

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
