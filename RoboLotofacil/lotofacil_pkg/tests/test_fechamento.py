"""
tests/test_fechamento.py — unittest version
"""
import os
import sys
import random
import unittest
from itertools import combinations
from math import comb

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from lotofacil_pkg.fechamento import (
    qtd_jogos_fechamento,
    garantia_minima,
    gerar_fechamento_garantia_total,
    escolher_pool_por_ranking,
    gerar_apostas_fechamento,
    TAMANHO_POOL_MINIMO,
    TAMANHO_POOL_MAXIMO,
)


class TestQtdJogosFechamento(unittest.TestCase):
    def test_valores_conhecidos(self):
        self.assertEqual(qtd_jogos_fechamento(16), 16)
        self.assertEqual(qtd_jogos_fechamento(17), 136)
        self.assertEqual(qtd_jogos_fechamento(18), 816)
        self.assertEqual(qtd_jogos_fechamento(19), 3876)
        self.assertEqual(qtd_jogos_fechamento(20), 15504)

    def test_bate_com_math_comb(self):
        for m in range(16, 21):
            self.assertEqual(qtd_jogos_fechamento(m), comb(m, 15))


class TestGarantiaMinima(unittest.TestCase):
    def test_valores_conhecidos(self):
        self.assertEqual(garantia_minima(16), 14)
        self.assertEqual(garantia_minima(17), 13)
        self.assertEqual(garantia_minima(18), 12)
        self.assertEqual(garantia_minima(19), 11)
        self.assertEqual(garantia_minima(20), 10)


class TestGerarFechamentoGarantiaTotal(unittest.TestCase):
    def test_quantidade_e_conteudo_dos_jogos(self):
        pool = list(range(1, 17))  # 16 dezenas
        jogos = gerar_fechamento_garantia_total(pool)
        self.assertEqual(len(jogos), 16)
        # cada jogo tem 15 dezenas distintas, todas dentro do pool
        for j in jogos:
            self.assertEqual(len(set(j)), 15)
            self.assertTrue(set(j) <= set(pool))
        # nenhum jogo duplicado
        self.assertEqual(len({tuple(j) for j in jogos}), 16)
        # cobre exatamente todas as combinacoes possiveis
        esperado = {tuple(sorted(c)) for c in combinations(pool, 15)}
        obtido = {tuple(j) for j in jogos}
        self.assertEqual(obtido, esperado)

    def test_rejeita_pool_pequeno_demais(self):
        with self.assertRaises(ValueError):
            gerar_fechamento_garantia_total(list(range(1, 16)))  # 15 dezenas = 1 jogo so

    def test_rejeita_pool_grande_demais(self):
        with self.assertRaises(ValueError):
            gerar_fechamento_garantia_total(list(range(1, 23)))  # 22 dezenas

    def test_rejeita_dezena_fora_do_intervalo(self):
        with self.assertRaises(ValueError):
            gerar_fechamento_garantia_total(list(range(1, 16)) + [26])

    def test_garantia_matematica_todas_as_20_dezenas_sorteadas_no_pool(self):
        """
        Propriedade central do fechamento: se as 15 dezenas sorteadas
        estiverem TODAS dentro do pool de m dezenas, o pior jogo do
        fechamento acerta pelo menos `garantia_minima(m)` pontos, e pelo
        menos um jogo acerta os 15 pontos.
        """
        rng = random.Random(7)
        universo = list(range(1, 26))
        for m in (16, 17, 18):
            for _ in range(5):
                pool = sorted(rng.sample(universo, m))
                sorteio = set(rng.sample(pool, 15))  # sorteio 100% contido no pool
                jogos = gerar_fechamento_garantia_total(pool)
                acertos = [len(set(j) & sorteio) for j in jogos]
                self.assertGreaterEqual(min(acertos), garantia_minima(m))
                self.assertEqual(max(acertos), 15)
                self.assertEqual(len(jogos), qtd_jogos_fechamento(m))


class TestEscolherPoolPorRanking(unittest.TestCase):
    def setUp(self):
        random.seed(11)
        numeros = list(range(1, 26))
        self.hist = [sorted(random.sample(numeros, 15)) for _ in range(200)]

    def test_retorna_pool_do_tamanho_pedido_sem_repeticao(self):
        pool, analise = escolher_pool_por_ranking(self.hist, tamanho_pool=16)
        self.assertEqual(len(pool), 16)
        self.assertEqual(len(set(pool)), 16)
        self.assertTrue(all(1 <= n <= 25 for n in pool))
        self.assertIn("ensemble", analise)


class TestGerarApostasFechamento(unittest.TestCase):
    def setUp(self):
        random.seed(13)
        numeros = list(range(1, 26))
        self.hist = [sorted(random.sample(numeros, 15)) for _ in range(200)]

    def test_estrutura_do_resultado(self):
        r = gerar_apostas_fechamento(self.hist, tamanho_pool=16)
        self.assertEqual(r["tamanho_pool"], 16)
        self.assertEqual(r["qtd_jogos"], 16)
        self.assertEqual(r["garantia_minima"], 14)
        self.assertEqual(len(r["jogos"]), 16)
        self.assertEqual(set(r["pool"]), set(n for j in r["jogos"] for n in j))

    def test_rejeita_tamanho_pool_fora_do_intervalo(self):
        with self.assertRaises(ValueError):
            gerar_apostas_fechamento(self.hist, tamanho_pool=TAMANHO_POOL_MINIMO - 1)
        with self.assertRaises(ValueError):
            gerar_apostas_fechamento(self.hist, tamanho_pool=TAMANHO_POOL_MAXIMO + 1)


if __name__ == "__main__":
    unittest.main()
