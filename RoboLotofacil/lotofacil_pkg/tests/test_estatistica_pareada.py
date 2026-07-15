"""
lotofacil_pkg/tests/test_estatistica_pareada.py
-------------------------------------------------
Testes para as funções de estatística PAREADA em v20_6_bootstrap.py
(cohen_d_pareado, teste_significancia_pareado, bootstrap_pareado,
tost_equivalencia) e para o mapear_vale_gp() reescrito para usá-las.
"""
import os
import sys
import random
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Isola v18_1b_ia_adaptativa/v20_2_poda_inteligente do dados/ real do
# repositorio durante os testes (ver lotofacil_pkg/tests/__init__.py e
# ARQUITETURA.md -- 'unittest discover' com caminho de arquivo nao
# executa esse __init__.py de forma confiavel, entao o isolamento
# tambem precisa estar aqui, no proprio arquivo de teste).
import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg.v20_6_bootstrap import (
    cohen_d_pareado,
    # Alias: evita que o pytest colete como teste proprio (nome comeca com "test").
    teste_significancia_pareado as _teste_significancia_pareado,
    bootstrap_pareado,
    tost_equivalencia,
)
from lotofacil_pkg.v21_5_melhorias_cientificas import mapear_vale_gp


def _dados(vals):
    return [{"acertos": v} for v in vals]


class TestCohenDPareado(unittest.TestCase):
    def test_diferenca_zero_da_d_zero(self):
        a = _dados([10, 11, 9, 12, 8] * 20)
        r = cohen_d_pareado(a, a)
        self.assertEqual(r["cohen_d_pareado"], 0.0)
        self.assertEqual(r["magnitude"], "DESPREZIVEL")

    def test_diferenca_grande_e_consistente_da_d_grande(self):
        a = _dados([12] * 50)
        b = _dados([9] * 50)
        r = cohen_d_pareado(a, b)
        # desvio da diferenca e zero (diferenca constante) -> d finito grande, nao NaN/inf
        self.assertGreater(r["cohen_d_pareado"], 0.8)
        self.assertEqual(r["magnitude"], "GRANDE")

    def test_tamanhos_diferentes_lanca_erro(self):
        with self.assertRaises(ValueError):
            cohen_d_pareado(_dados([1, 2, 3]), _dados([1, 2]))

    def test_lista_vazia(self):
        r = cohen_d_pareado([], [])
        self.assertEqual(r["magnitude"], "SEM_DADOS")


class TestTesteSignificanciaPareado(unittest.TestCase):
    def test_sem_diferenca_nao_significativo(self):
        random.seed(1)
        base = [random.randint(8, 12) for _ in range(200)]
        a = _dados(base)
        b = _dados(base)  # identico -> delta=0
        r = _teste_significancia_pareado(a, b, n_reamostras=500)
        self.assertFalse(r["rejeita_h0"])
        self.assertAlmostEqual(r["delta_obs"], 0.0)

    def test_diferenca_grande_e_consistente_e_significativo(self):
        a = _dados([15] * 100)
        b = _dados([9] * 100)
        r = _teste_significancia_pareado(a, b, n_reamostras=500)
        self.assertTrue(r["rejeita_h0"])
        self.assertLess(r["p_value"], 0.01)

    def test_lista_vazia(self):
        r = _teste_significancia_pareado([], [])
        self.assertEqual(r["nivel_significancia"], "SEM_DADOS")


class TestBootstrapPareado(unittest.TestCase):
    def test_ic_contem_delta_observado(self):
        random.seed(2)
        a = _dados([random.randint(8, 14) for _ in range(150)])
        b = _dados([random.randint(8, 14) for _ in range(150)])
        r = bootstrap_pareado(a, b, n_reamostras=500)
        ic95 = r["intervalos"]["95%"]
        self.assertLessEqual(ic95["inferior"], r["delta_observado"])
        self.assertGreaterEqual(ic95["superior"], r["delta_observado"])

    def test_diferenca_constante_ic_estreito_em_torno_do_valor(self):
        a = _dados([13] * 80)
        b = _dados([10] * 80)
        r = bootstrap_pareado(a, b, n_reamostras=500)
        ic95 = r["intervalos"]["95%"]
        self.assertAlmostEqual(ic95["inferior"], 3.0, delta=0.01)
        self.assertAlmostEqual(ic95["superior"], 3.0, delta=0.01)


class TestTostEquivalencia(unittest.TestCase):
    def test_diferenca_pequena_dentro_da_margem_e_equivalente(self):
        random.seed(3)
        base = [random.randint(8, 12) for _ in range(300)]
        a = _dados(base)
        b = _dados([v + random.choice([-1, 0, 1]) * 0.01 for v in base])
        r = tost_equivalencia(a, b, margem=0.5, n_reamostras=1000)
        self.assertTrue(r["equivalente"])

    def test_diferenca_grande_fora_da_margem_nao_e_equivalente(self):
        a = _dados([15] * 60)
        b = _dados([9] * 60)
        r = tost_equivalencia(a, b, margem=0.3, n_reamostras=500)
        self.assertFalse(r["equivalente"])

    def test_margem_maior_que_diferenca_confirma_equivalencia(self):
        a = _dados([10.0] * 60)
        b = _dados([10.2] * 60)
        r = tost_equivalencia(a, b, margem=1.0, n_reamostras=500)
        self.assertTrue(r["equivalente"])


class TestMapearValeGp(unittest.TestCase):
    def setUp(self):
        random.seed(42)
        numeros = list(range(1, 26))
        self.hist = [sorted(random.sample(numeros, 15)) for _ in range(200)]

    def test_estrutura_do_retorno_tem_campos_estatisticos(self):
        def fn_gerar(hist, g, p, qtd):
            return [sorted(random.sample(list(range(1, 26)), 15)) for _ in range(qtd)]

        r = mapear_vale_gp(self.hist, fn_gerar, janela=100, passos=20, qtd_jogos=10,
                            pontos_g=[20, 50, 100])
        self.assertIn("resultados", r)
        self.assertIn("vale_confirmado", r)
        self.assertIn("comparacoes_pareadas", r)
        self.assertIn("referencia_extremo", r)
        for comp in r["comparacoes_pareadas"]:
            self.assertIn("cohen_d_pareado", comp)
            self.assertIn("p_value", comp)
            self.assertIn("tost_equivalente", comp)
            self.assertIn("veredito", comp)
            self.assertIn(comp["veredito"], ("POSSIVEL_VALE", "EQUIVALENTE", "INCONCLUSIVO"))

    def test_sem_diferenca_real_nao_confirma_vale(self):
        """Todas as configs geram jogos igualmente aleatorios -- nao deve haver vale real."""
        def fn_gerar(hist, g, p, qtd):
            return [sorted(random.sample(list(range(1, 26)), 15)) for _ in range(qtd)]

        r = mapear_vale_gp(self.hist, fn_gerar, janela=100, passos=30, qtd_jogos=10,
                            pontos_g=[20, 50, 80, 100])
        self.assertFalse(r["vale_confirmado"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
