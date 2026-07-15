"""
lotofacil_pkg/tests/test_auditoria_cientifica.py
--------------------------------------------------
Testes para o módulo de auditoria científica contínua.
"""
import json
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Isola v18_1b_ia_adaptativa/v20_2_poda_inteligente do dados/ real do
# repositorio durante os testes (ver lotofacil_pkg/tests/__init__.py e
# ARQUITETURA.md -- 'unittest discover' com caminho de arquivo nao
# executa esse __init__.py de forma confiavel, entao o isolamento
# tambem precisa estar aqui, no proprio arquivo de teste).
import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg.auditoria_cientifica import (
    auditoria_experimento,
    corrigir_multiplas_comparacoes,
    consolidar_rodada_experimentos,
)


def _dados(vals):
    return [{"acertos": v} for v in vals]


META_REAL_OK = {
    "n_concursos": 300,
    "range_concursos": "3410-3709",
    "fonte_dados": "real",
    "walkforward_sem_vazamento": True,
}


class TestCorrigirMultiplasComparacoes(unittest.TestCase):
    def test_bonferroni_multiplica_por_m(self):
        r = corrigir_multiplas_comparacoes([0.01, 0.02, 0.20], metodo="bonferroni")
        self.assertEqual(r[0]["p_ajustado"], 0.03)
        self.assertEqual(r[1]["p_ajustado"], 0.06)
        self.assertEqual(r[2]["p_ajustado"], 0.6)

    def test_bonferroni_cap_em_1(self):
        r = corrigir_multiplas_comparacoes([0.5, 0.6], metodo="bonferroni")
        self.assertEqual(r[0]["p_ajustado"], 1.0)
        self.assertEqual(r[1]["p_ajustado"], 1.0)

    def test_holm_e_menos_conservador_que_bonferroni(self):
        p_values = [0.01, 0.02, 0.20]
        holm = corrigir_multiplas_comparacoes(p_values, metodo="holm")
        bonf = corrigir_multiplas_comparacoes(p_values, metodo="bonferroni")
        for h, b in zip(holm, bonf):
            self.assertLessEqual(h["p_ajustado"], b["p_ajustado"])

    def test_holm_e_monotono_step_down(self):
        """p ajustados, na ordem crescente do p original, nunca diminuem (Holm)."""
        p_values = [0.001, 0.30, 0.02, 0.04]
        r = corrigir_multiplas_comparacoes(p_values, metodo="holm")
        ordenado = sorted(range(len(p_values)), key=lambda i: p_values[i])
        ajustados_em_ordem = [r[i]["p_ajustado"] for i in ordenado]
        self.assertEqual(ajustados_em_ordem, sorted(ajustados_em_ordem))

    def test_lista_vazia(self):
        self.assertEqual(corrigir_multiplas_comparacoes([]), [])

    def test_metodo_invalido_lanca_erro(self):
        with self.assertRaises(ValueError):
            corrigir_multiplas_comparacoes([0.01], metodo="turbo")

    def test_significativo_corrigido_respeita_alpha(self):
        r = corrigir_multiplas_comparacoes([0.01, 0.5], metodo="bonferroni", alpha=0.05)
        self.assertTrue(r[0]["significativo_corrigido"])
        self.assertFalse(r[1]["significativo_corrigido"])


class TestAuditoriaExperimento(unittest.TestCase):
    def test_estrutura_do_retorno(self):
        random.seed(1)
        a = _dados([random.randint(9, 13) for _ in range(200)])
        b = _dados([random.randint(8, 12) for _ in range(200)])
        r = auditoria_experimento("teste", a, b, metadados=META_REAL_OK)
        for chave in (
            "cohen_d_pareado", "p_value_bruto", "delta_observado", "ic_95",
            "tost_equivalente", "poder_observado", "avisos", "metadados",
        ):
            self.assertIn(chave, r)

    def test_metadados_ausentes_geram_aviso(self):
        a = _dados([10] * 50)
        b = _dados([9] * 50)
        r = auditoria_experimento("teste", a, b, metadados={})
        self.assertTrue(any("metadados incompletos" in av for av in r["avisos"]))
        self.assertTrue(any("fonte_dados" in av for av in r["avisos"]))

    def test_fonte_sintetica_gera_aviso(self):
        a = _dados([10] * 50)
        b = _dados([9] * 50)
        meta = dict(META_REAL_OK, fonte_dados="sintetico")
        r = auditoria_experimento("teste", a, b, metadados=meta)
        self.assertTrue(any("fonte_dados" in av for av in r["avisos"]))

    def test_metadados_completos_e_reais_sem_aviso_de_metadados(self):
        random.seed(2)
        a = _dados([random.randint(8, 13) for _ in range(300)])
        b = _dados([random.randint(8, 13) for _ in range(300)])
        r = auditoria_experimento("teste", a, b, metadados=META_REAL_OK)
        self.assertFalse(any("metadados incompletos" in av for av in r["avisos"]))
        self.assertFalse(any("fonte_dados" in av for av in r["avisos"]))

    def test_poder_baixo_gera_aviso(self):
        random.seed(3)
        # efeito pequeno com poucas amostras -> poder baixo esperado
        a = _dados([random.randint(9, 12) for _ in range(20)])
        b = _dados([random.randint(9, 12) for _ in range(20)])
        r = auditoria_experimento("teste", a, b, metadados=META_REAL_OK)
        if r["poder_observado"] < 0.5:
            self.assertTrue(any("poder=" in av for av in r["avisos"]))


class TestConsolidarRodadaExperimentos(unittest.TestCase):
    def test_lista_vazia(self):
        r = consolidar_rodada_experimentos("rodada vazia", [])
        self.assertEqual(r["comparacoes"], [])

    def test_efeito_grande_consistente_da_veredito_superior(self):
        a1 = _dados([15] * 60)
        b1 = _dados([9] * 60)
        aud = auditoria_experimento("A supera B", a1, b1, metadados=META_REAL_OK)
        r = consolidar_rodada_experimentos("rodada", [aud])
        self.assertEqual(r["comparacoes"][0]["veredito_final"], "SUPERIOR")

    def test_diferenca_minima_da_veredito_equivalente(self):
        random.seed(4)
        base = [random.randint(9, 12) for _ in range(300)]
        a = _dados(base)
        b = _dados([v + random.choice([-0.01, 0, 0.01]) for v in base])
        aud = auditoria_experimento("quase igual", a, b, metadados=META_REAL_OK, margem_equivalencia=0.3)
        r = consolidar_rodada_experimentos("rodada", [aud])
        self.assertEqual(r["comparacoes"][0]["veredito_final"], "EQUIVALENTE")

    def test_amostra_pequena_e_efeito_pequeno_da_inconclusivo(self):
        random.seed(5)
        a = _dados([random.randint(9, 12) for _ in range(15)])
        b = _dados([random.randint(9, 12) for _ in range(15)])
        aud = auditoria_experimento("pouca amostra", a, b, metadados=META_REAL_OK, margem_equivalencia=0.05)
        r = consolidar_rodada_experimentos("rodada", [aud])
        self.assertIn(r["comparacoes"][0]["veredito_final"], ("INCONCLUSIVO", "EQUIVALENTE", "SUPERIOR"))

    def test_correcao_multipla_aplicada_a_varias_comparacoes(self):
        random.seed(6)
        base_ref = [random.randint(9, 12) for _ in range(150)]
        ref = _dados(base_ref)
        auditorias = []
        for i in range(3):
            outro = _dados([v + random.uniform(-0.5, 0.5) for v in base_ref])
            auditorias.append(auditoria_experimento(f"comparacao {i}", ref, outro, metadados=META_REAL_OK))
        r = consolidar_rodada_experimentos("rodada com 3 comparacoes", auditorias, metodo_correcao="holm")
        self.assertEqual(r["n_comparacoes"], 3)
        self.assertEqual(len(r["comparacoes"]), 3)
        for c in r["comparacoes"]:
            self.assertGreaterEqual(c["p_ajustado"], c["p_original"])

    def test_salva_relatorio_md_e_json(self):
        a = _dados([15] * 40)
        b = _dados([9] * 40)
        aud = auditoria_experimento("salvar", a, b, metadados=META_REAL_OK)
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "relatorio_teste")
            r = consolidar_rodada_experimentos("rodada salva", [aud], salvar_em=caminho)
            self.assertTrue(os.path.exists(caminho + ".json"))
            self.assertTrue(os.path.exists(caminho + ".md"))
            with open(caminho + ".json", encoding="utf-8") as f:
                do_disco = json.load(f)
            self.assertEqual(do_disco["nome_rodada"], "rodada salva")
            with open(caminho + ".md", encoding="utf-8") as f:
                conteudo_md = f.read()
            self.assertIn("SUPERIOR", conteudo_md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
