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

# Isola v18_1b_ia_adaptativa/v20_2_poda_inteligente do dados/ real do
# repositorio durante os testes (ver lotofacil_pkg/tests/__init__.py e
# ARQUITETURA.md -- 'unittest discover' com caminho de arquivo nao
# executa esse __init__.py de forma confiavel, entao o isolamento
# tambem precisa estar aqui, no proprio arquivo de teste).
import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg.fechamento import (
    qtd_jogos_fechamento,
    garantia_minima,
    gerar_fechamento_garantia_total,
    escolher_pool_por_ranking,
    gerar_apostas_fechamento,
    tamanho_pool_minimo,
    gerar_fechamento_reduzido,
    gerar_apostas_fechamento_reduzido,
    _verificar_garantia_reduzida,
    TAMANHO_POOL_MINIMO,
    TAMANHO_POOL_MAXIMO,
    TAMANHO_POOL_MAXIMO_REDUZIDO,
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


class TestTamanhoJogoDiferenteDe15(unittest.TestCase):
    """
    Regressão do achado do usuário (2026-08-03): o Fechamento sempre gerava
    jogos de 15 dezenas mesmo com o campo "Dezenas por jogo" em 16/17/18,
    porque tamanho_jogo nunca era repassado até gerar_fechamento_garantia_total().
    Também cobre a correção da fórmula de garantia_minima() para
    tamanho_jogo != 15 (a fórmula antiga confundia tamanho do jogo com
    tamanho do sorteio real, que são conceitos diferentes).
    """

    def test_tamanho_pool_minimo(self):
        self.assertEqual(tamanho_pool_minimo(15), 16)
        self.assertEqual(tamanho_pool_minimo(16), 17)
        self.assertEqual(tamanho_pool_minimo(18), 19)

    def test_garantia_minima_com_tamanho_jogo_15_igual_ao_antigo(self):
        # tamanho_jogo=15 tem que continuar batendo com os valores conhecidos.
        for m, esperado in [(16, 14), (17, 13), (18, 12), (19, 11), (20, 10)]:
            self.assertEqual(garantia_minima(m, tamanho_jogo=15), esperado)

    def test_garantia_minima_com_tamanho_jogo_maior_que_15(self):
        # formula geral: tamanho_jogo + 15 - tamanho_pool
        self.assertEqual(garantia_minima(17, tamanho_jogo=16), 16 + 15 - 17)
        self.assertEqual(garantia_minima(20, tamanho_jogo=18), 18 + 15 - 20)
        # no pool minimo (tamanho_jogo+1), a garantia eh sempre 14,
        # independente de tamanho_jogo (propriedade matematica do fechamento).
        for k in (15, 16, 17, 18):
            self.assertEqual(garantia_minima(tamanho_pool_minimo(k), tamanho_jogo=k), 14)

    def test_gerar_fechamento_garantia_total_com_tamanho_jogo_16(self):
        pool = list(range(1, 18))  # 17 dezenas
        jogos = gerar_fechamento_garantia_total(pool, tamanho_jogo=16)
        self.assertEqual(len(jogos), comb(17, 16))
        for j in jogos:
            self.assertEqual(len(set(j)), 16)
            self.assertTrue(set(j) <= set(pool))

    def test_garantia_matematica_com_tamanho_jogo_maior_que_15(self):
        """
        Mesma propriedade central do fechamento (ver
        TestGerarFechamentoGarantiaTotal), mas com tamanho_jogo=16/17 --
        precisa continuar valendo com a formula corrigida.
        """
        rng = random.Random(23)
        universo = list(range(1, 26))
        for tamanho_jogo in (16, 17):
            for m in (tamanho_jogo + 1, tamanho_jogo + 2):
                pool = sorted(rng.sample(universo, m))
                sorteio = set(rng.sample(pool, 15))  # sorteio real: sempre 15, 100% no pool
                jogos = gerar_fechamento_garantia_total(pool, tamanho_jogo=tamanho_jogo)
                acertos = [len(set(j) & sorteio) for j in jogos]
                self.assertGreaterEqual(min(acertos), garantia_minima(m, tamanho_jogo))
                self.assertEqual(max(acertos), 15)

    def test_gerar_apostas_fechamento_repassa_tamanho_jogo(self):
        r = gerar_apostas_fechamento(self.hist_padrao(), tamanho_pool=17, tamanho_jogo=16)
        self.assertEqual(r["tamanho_jogo"], 16)
        self.assertEqual(r["qtd_jogos"], comb(17, 16))
        self.assertEqual(r["garantia_minima"], 16 + 15 - 17)
        for j in r["jogos"]:
            self.assertEqual(len(j), 16)

    def test_gerar_apostas_fechamento_valida_pool_pelo_minimo_dinamico(self):
        # pool=17 eh valido para tamanho_jogo=15 (minimo 16) mas invalido
        # para tamanho_jogo=17 (minimo 18) -- a validacao tem que refletir isso.
        gerar_apostas_fechamento(self.hist_padrao(), tamanho_pool=17, tamanho_jogo=15)  # nao levanta
        with self.assertRaises(ValueError):
            gerar_apostas_fechamento(self.hist_padrao(), tamanho_pool=17, tamanho_jogo=17)

    @staticmethod
    def hist_padrao():
        random.seed(29)
        numeros = list(range(1, 26))
        return [sorted(random.sample(numeros, 15)) for _ in range(200)]


class TestVerificarGarantiaReduzida(unittest.TestCase):
    """
    Testa a verificação por força bruta isoladamente -- ela é a única
    coisa que separa uma garantia real de uma alegação falsa, então
    precisa ser correta tanto pra aceitar um sistema válido quanto pra
    rejeitar um inválido.
    """

    def test_aceita_fechamento_completo_como_caso_trivial(self):
        # Com t=k=tamanho do jogo e g=k, jogar TODAS as combinações de k
        # sempre cobre qualquer alvo de tamanho k (ele PRÓPRIO é um jogo).
        m, k = 6, 4
        jogos_idx = list(combinations(range(m), k))
        self.assertTrue(_verificar_garantia_reduzida(m, jogos_idx, t_garantia=k, g_garantia=k))

    def test_rejeita_sistema_insuficiente(self):
        # Só um jogo não pode garantir cobertura de TODOS os alvos de t=5
        # dezenas com g=4 num pool de 7 -- existem alvos que não intersectam
        # esse jogo o suficiente.
        m = 7
        jogos_idx = [tuple(range(5))]  # um único jogo de 5 dezenas (posições 0-4)
        self.assertFalse(_verificar_garantia_reduzida(m, jogos_idx, t_garantia=5, g_garantia=4))

    def test_sistema_vazio_nunca_cobre_nada(self):
        self.assertFalse(_verificar_garantia_reduzida(6, [], t_garantia=3, g_garantia=2))


class TestGerarFechamentoReduzido(unittest.TestCase):
    def test_caso_pequeno_exaustivamente_verificavel(self):
        """
        Pool pequeno (7 dezenas) onde dá pra confirmar manualmente, além
        da verificação interna, que a garantia é real: para TODO
        subconjunto de 6 dezenas do pool, pelo menos um jogo (de 5
        dezenas) do fechamento acerta pelo menos 4 delas.
        """
        pool = [1, 2, 3, 4, 5, 6, 7]
        resultado = gerar_fechamento_reduzido(pool, tamanho_jogo=5, t_garantia=6, g_garantia=4)
        self.assertTrue(resultado["garantia_verificada"])
        jogos = resultado["jogos"]
        self.assertGreater(len(jogos), 0)
        # Confirma a garantia de novo, de fora, sem depender da função interna.
        for alvo in combinations(pool, 6):
            alvo_set = set(alvo)
            self.assertTrue(
                any(len(set(j) & alvo_set) >= 4 for j in jogos),
                f"Nenhum jogo cobre o alvo {alvo} com pelo menos 4 acertos.",
            )

    def test_wheel_18_15_13_11_conhecido_na_literatura(self):
        """
        m=18,k=15,t=13,g=11 é um fechamento reduzido clássico e publicado
        na literatura de loteria -- usa muito menos que os 816 jogos da
        garantia total do mesmo pool.
        """
        pool = list(range(1, 19))  # 18 dezenas
        resultado = gerar_fechamento_reduzido(pool, tamanho_jogo=15, t_garantia=13, g_garantia=11)
        self.assertTrue(resultado["garantia_verificada"])
        self.assertLess(resultado["qtd_jogos"], comb(18, 15))  # bem menos que 816
        for j in resultado["jogos"]:
            self.assertEqual(len(j), 15)
            self.assertTrue(set(j) <= set(pool))

    def test_rejeita_pool_maior_que_limite_reduzido(self):
        pool = list(range(1, 22))  # 21 dezenas
        with self.assertRaises(ValueError):
            gerar_fechamento_reduzido(pool, tamanho_jogo=15, t_garantia=13, g_garantia=11)

    def test_rejeita_g_maior_que_t(self):
        pool = list(range(1, 19))
        with self.assertRaises(ValueError):
            gerar_fechamento_reduzido(pool, tamanho_jogo=15, t_garantia=11, g_garantia=13)

    def test_rejeita_t_maior_que_pool(self):
        pool = list(range(1, 8))
        with self.assertRaises(ValueError):
            gerar_fechamento_reduzido(pool, tamanho_jogo=5, t_garantia=10, g_garantia=4)

    def test_max_jogos_insuficiente_levanta_erro_em_vez_de_garantia_incompleta(self):
        pool = list(range(1, 19))
        with self.assertRaises(ValueError):
            gerar_fechamento_reduzido(pool, tamanho_jogo=15, t_garantia=13, g_garantia=11, max_jogos=1)


class TestGerarApostasFechamentoReduzido(unittest.TestCase):
    def setUp(self):
        random.seed(31)
        numeros = list(range(1, 26))
        self.hist = [sorted(random.sample(numeros, 15)) for _ in range(200)]

    def test_estrutura_do_resultado(self):
        r = gerar_apostas_fechamento_reduzido(
            self.hist, tamanho_pool=18, tamanho_jogo=15, t_garantia=13, g_garantia=11
        )
        self.assertTrue(r["garantia_verificada"])
        self.assertEqual(r["tamanho_pool"], 18)
        self.assertEqual(len(r["pool"]), 18)
        self.assertLess(r["qtd_jogos"], comb(18, 15))
        self.assertEqual(set(r["pool"]), set(n for j in r["jogos"] for n in j))

    def test_rejeita_tamanho_pool_acima_do_limite_reduzido(self):
        with self.assertRaises(ValueError):
            gerar_apostas_fechamento_reduzido(self.hist, tamanho_pool=TAMANHO_POOL_MAXIMO_REDUZIDO + 1)


if __name__ == "__main__":
    unittest.main()
