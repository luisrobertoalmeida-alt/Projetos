"""
lotofacil_pkg/tests/test_execucao_paralela.py
------------------------------------------------
Teste de REGRESSÃO obrigatório: com a mesma seed_base, execução paralela
(processos) e sequencial devem produzir resultado idêntico.
"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Isola v18_1b_ia_adaptativa/v20_2_poda_inteligente do dados/ real do
# repositorio durante os testes (ver lotofacil_pkg/tests/__init__.py e
# ARQUITETURA.md -- 'unittest discover' com caminho de arquivo nao
# executa esse __init__.py de forma confiavel, entao o isolamento
# tambem precisa estar aqui, no proprio arquivo de teste).
import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg.execucao_paralela import rodar_walkforward, seed_do_passo, gerar_apostas_padrao


def _fn_gerar_teste_rapido(hist, geracoes, pop_size, qtd_jogos):
    """
    fn_gerar rápida para teste (não roda o algoritmo genético real) --
    top-level de propósito, para ser picklável entre processos. Usa
    random.sample, então depende do random.seed() já aplicado pelo
    worker antes de chamar fn_gerar -- exercita exatamente o mecanismo
    de reprodutibilidade que este módulo garante.
    """
    numeros = list(range(1, 26))
    return [sorted(random.sample(numeros, 15)) for _ in range(qtd_jogos)]


def _fn_gerar_local_invalida(hist, geracoes, pop_size, qtd_jogos):
    numeros = list(range(1, 26))
    return [sorted(random.sample(numeros, 15)) for _ in range(qtd_jogos)]


def _fabrica_com_closure():
    def fn_local(hist, geracoes, pop_size, qtd_jogos):
        return []
    return fn_local


class TestSeedDoPasso(unittest.TestCase):
    def test_determinístico(self):
        self.assertEqual(seed_do_passo(2026, 5), seed_do_passo(2026, 5))

    def test_seeds_diferentes_para_passos_diferentes(self):
        self.assertNotEqual(seed_do_passo(2026, 5), seed_do_passo(2026, 6))

    def test_seeds_diferentes_para_bases_diferentes(self):
        self.assertNotEqual(seed_do_passo(2026, 5), seed_do_passo(999, 5))


class TestRodarWalkforwardModoInvalido(unittest.TestCase):
    def setUp(self):
        random.seed(0)
        numeros = list(range(1, 26))
        self.concursos = [sorted(random.sample(numeros, 15)) for _ in range(60)]

    def test_modo_invalido_lanca_erro(self):
        with self.assertRaises(ValueError):
            rodar_walkforward(
                self.concursos, [50, 51], 10, 20, 5, seed_base=1,
                fn_gerar=_fn_gerar_teste_rapido, modo="turbo",
            )

    def test_funcao_local_em_modo_processos_lanca_erro_claro(self):
        fn_local = _fabrica_com_closure()
        with self.assertRaises(ValueError) as ctx:
            rodar_walkforward(
                self.concursos, [50, 51], 10, 20, 5, seed_base=1,
                fn_gerar=fn_local, modo="processos",
            )
        self.assertIn("closure", str(ctx.exception).lower())

    def test_funcao_local_em_modo_sequencial_funciona(self):
        fn_local = _fabrica_com_closure()
        r = rodar_walkforward(
            self.concursos, [50, 51], 10, 20, 5, seed_base=1,
            fn_gerar=fn_local, modo="sequencial",
        )
        self.assertEqual(len(r), 2)


class TestReproducibilidadeParaleloVsSequencial(unittest.TestCase):
    """O teste de regressão central pedido: mesma seed_base => resultado idêntico."""

    def setUp(self):
        random.seed(0)
        numeros = list(range(1, 26))
        self.concursos = [sorted(random.sample(numeros, 15)) for _ in range(80)]
        self.indices = list(range(50, 70))  # 20 passos

    def test_sequencial_e_processos_dao_resultado_identico(self):
        seed_base = 2026
        r_seq = rodar_walkforward(
            self.concursos, self.indices, geracoes=10, pop_size=20, qtd_jogos=8,
            seed_base=seed_base, fn_gerar=_fn_gerar_teste_rapido, modo="sequencial",
        )
        r_par = rodar_walkforward(
            self.concursos, self.indices, geracoes=10, pop_size=20, qtd_jogos=8,
            seed_base=seed_base, fn_gerar=_fn_gerar_teste_rapido, modo="processos", n_workers=4,
        )
        self.assertEqual(r_seq, r_par)

    def test_sequencial_e_processos_com_1_worker_dao_resultado_identico(self):
        seed_base = 42
        r_seq = rodar_walkforward(
            self.concursos, self.indices, geracoes=10, pop_size=20, qtd_jogos=8,
            seed_base=seed_base, fn_gerar=_fn_gerar_teste_rapido, modo="sequencial",
        )
        r_par = rodar_walkforward(
            self.concursos, self.indices, geracoes=10, pop_size=20, qtd_jogos=8,
            seed_base=seed_base, fn_gerar=_fn_gerar_teste_rapido, modo="processos", n_workers=1,
        )
        self.assertEqual(r_seq, r_par)

    def test_seeds_diferentes_dao_resultados_diferentes(self):
        """Sanity check: o teste acima nao passaria trivialmente por acaso (ex.: fn_gerar ignorando a seed)."""
        r_a = rodar_walkforward(
            self.concursos, self.indices, geracoes=10, pop_size=20, qtd_jogos=8,
            seed_base=1, fn_gerar=_fn_gerar_teste_rapido, modo="sequencial",
        )
        r_b = rodar_walkforward(
            self.concursos, self.indices, geracoes=10, pop_size=20, qtd_jogos=8,
            seed_base=2, fn_gerar=_fn_gerar_teste_rapido, modo="sequencial",
        )
        self.assertNotEqual(r_a, r_b)

    def test_ordem_dos_resultados_preservada(self):
        seed_base = 7
        r_par = rodar_walkforward(
            self.concursos, self.indices, geracoes=10, pop_size=20, qtd_jogos=8,
            seed_base=seed_base, fn_gerar=_fn_gerar_teste_rapido, modo="processos", n_workers=4,
        )
        self.assertEqual([r["concurso_idx"] for r in r_par], [i + 1 for i in self.indices])


class TestGerarApostasPadraoEhPicklavel(unittest.TestCase):
    def test_e_funcao_top_level(self):
        self.assertNotIn("<locals>", gerar_apostas_padrao.__qualname__)


if __name__ == "__main__":
    unittest.main(verbosity=2)
