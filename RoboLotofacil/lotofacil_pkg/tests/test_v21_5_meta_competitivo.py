"""
lotofacil_pkg/tests/test_v21_5_meta_competitivo.py
-------------------------------------------------------
Testes para v21_5_meta_competitivo.py (ranking ELO dos modelos do
ensemble), usado por analise.py (fator_elo) e pela Hall da Fama
(corrigida em 2026-08-08 -- ver ARQUITETURA.md).

Isolamento: carregar_elo/salvar_elo tentam SQLite primeiro (get_db(),
que não respeita ROBOLOTOFACIL_DADOS_DIR -- lacuna conhecida) com
fallback silencioso (try/except Exception) para o JSON em _ARQ_ELO.
Por isso os testes que tocam persistência forçam o fallback JSON
patchando lotofacil_pkg.v21_0_sqlite.get_db para levantar exceção, e
redirecionam _ARQ_ELO para um arquivo temporário -- nunca tocam o
SQLite nem o JSON reais de produção.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg import v21_5_meta_competitivo as elo_mod


class TestProbEsperadaEClipar(unittest.TestCase):
    def test_prob_esperada_elos_iguais_e_50_50(self):
        self.assertAlmostEqual(elo_mod._prob_esperada_elo(1500, 1500), 0.5)

    def test_prob_esperada_favorece_elo_maior(self):
        self.assertGreater(elo_mod._prob_esperada_elo(1700, 1500), 0.5)
        self.assertLess(elo_mod._prob_esperada_elo(1300, 1500), 0.5)

    def test_clipar_dentro_do_intervalo(self):
        self.assertEqual(elo_mod._clipar(5, 0, 10), 5)

    def test_clipar_abaixo_do_minimo(self):
        self.assertEqual(elo_mod._clipar(-5, 0, 10), 0)

    def test_clipar_acima_do_maximo(self):
        self.assertEqual(elo_mod._clipar(15, 0, 10), 10)


class TestFatorElo(unittest.TestCase):
    def test_elo_neutro_da_fator_1(self):
        self.assertEqual(elo_mod.fator_elo("a", {"a": elo_mod.ELO_REFERENCIA}), 1.0)

    def test_elo_minimo_clampado_em_fator_min(self):
        self.assertEqual(elo_mod.fator_elo("a", {"a": elo_mod.ELO_MIN}), elo_mod.FATOR_MIN)

    def test_elo_maximo_clampado_em_fator_max(self):
        self.assertEqual(elo_mod.fator_elo("a", {"a": elo_mod.ELO_MAX}), elo_mod.FATOR_MAX)

    def test_elo_acima_do_neutro_da_fator_maior_que_1(self):
        self.assertGreater(elo_mod.fator_elo("a", {"a": 1700}), 1.0)

    def test_modelo_desconhecido_usa_elo_inicial(self):
        self.assertEqual(elo_mod.fator_elo("desconhecido", {"a": 1700}), 1.0)

    def test_fatores_elo_todos_cobre_todos_os_modelos(self):
        elos = {"a": 1500, "b": 1700}
        fatores = elo_mod.fatores_elo_todos(elos)
        self.assertEqual(set(fatores.keys()), {"a", "b"})
        self.assertEqual(fatores["a"], 1.0)


class TestAtualizarEloConcurso(unittest.TestCase):
    def test_acertos_por_modelo_vazio_retorna_vazio(self):
        self.assertEqual(elo_mod.atualizar_elo_concurso({}), {})

    def test_vencedor_e_o_de_mais_acertos(self):
        with patch.object(elo_mod, "carregar_elo", return_value={"a": 1500.0, "b": 1500.0}), \
             patch.object(elo_mod, "salvar_elo") as mock_salvar:
            resultado = elo_mod.atualizar_elo_concurso({"a": 12.0, "b": 8.0}, concurso=100)
        self.assertEqual(resultado["vencedor"], "a")
        self.assertEqual(resultado["concurso"], 100)
        mock_salvar.assert_called_once()

    def test_modelo_acima_da_media_ganha_elo_e_abaixo_perde(self):
        with patch.object(elo_mod, "carregar_elo", return_value={"a": 1500.0, "b": 1500.0}), \
             patch.object(elo_mod, "salvar_elo"):
            resultado = elo_mod.atualizar_elo_concurso({"a": 12.0, "b": 8.0})
        self.assertGreater(resultado["elos_novos"]["a"], resultado["elos_anteriores"]["a"])
        self.assertLess(resultado["elos_novos"]["b"], resultado["elos_anteriores"]["b"])

    def test_modelos_empatados_na_media_nao_mudam_elo_um_contra_outro(self):
        with patch.object(elo_mod, "carregar_elo", return_value={"a": 1500.0, "b": 1500.0}), \
             patch.object(elo_mod, "salvar_elo"):
            resultado = elo_mod.atualizar_elo_concurso({"a": 9.0, "b": 9.0})
        self.assertEqual(resultado["elos_novos"]["a"], resultado["elos_anteriores"]["a"])
        self.assertEqual(resultado["elos_novos"]["b"], resultado["elos_anteriores"]["b"])

    def test_modelo_novo_sem_elo_previo_comeca_no_inicial(self):
        with patch.object(elo_mod, "carregar_elo", return_value={"a": 1500.0}), \
             patch.object(elo_mod, "salvar_elo"):
            resultado = elo_mod.atualizar_elo_concurso({"a": 9.0, "novo": 9.0})
        self.assertEqual(resultado["elos_anteriores"]["novo"], elo_mod.ELO_INICIAL)

    def test_elo_nunca_sai_do_intervalo_min_max(self):
        with patch.object(elo_mod, "carregar_elo", return_value={"a": elo_mod.ELO_MAX, "b": elo_mod.ELO_MIN}), \
             patch.object(elo_mod, "salvar_elo"):
            resultado = elo_mod.atualizar_elo_concurso({"a": 15.0, "b": 5.0})
        self.assertLessEqual(resultado["elos_novos"]["a"], elo_mod.ELO_MAX)
        self.assertGreaterEqual(resultado["elos_novos"]["b"], elo_mod.ELO_MIN)


class TestGetRankingElo(unittest.TestCase):
    def test_ordenado_por_elo_decrescente(self):
        ranking = elo_mod.get_ranking_elo({"a": 1400, "b": 1600, "c": 1500})
        self.assertEqual([r["nome"] for r in ranking], ["b", "c", "a"])
        self.assertEqual([r["posicao"] for r in ranking], [1, 2, 3])

    def test_status_por_faixa_de_elo(self):
        ranking = elo_mod.get_ranking_elo({
            "destaque": 1650, "ativo": 1550, "observacao": 1400,
            "quarentena": 1250, "suspenso": 1100,
        })
        status_por_nome = {r["nome"]: r["status"] for r in ranking}
        self.assertIn("DESTAQUE", status_por_nome["destaque"])
        self.assertIn("ATIVO", status_por_nome["ativo"])
        self.assertIn("OBSERVAÇÃO", status_por_nome["observacao"])
        self.assertIn("QUARENTENA", status_por_nome["quarentena"])
        self.assertIn("SUSPENSO", status_por_nome["suspenso"])


class TestPersistenciaElo(unittest.TestCase):
    """Isola SQLite (força fallback) e redireciona _ARQ_ELO para arquivo temporário."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="robolotofacil_elo_")
        self._arq_original = elo_mod._ARQ_ELO
        elo_mod._ARQ_ELO = Path(self._tmpdir) / "elo_modelos.json"
        self._patch_sqlite = patch("lotofacil_pkg.v21_0_sqlite.get_db", side_effect=RuntimeError("sem sqlite nos testes"))
        self._patch_sqlite.start()

    def tearDown(self):
        self._patch_sqlite.stop()
        elo_mod._ARQ_ELO = self._arq_original

    def test_carregar_sem_arquivo_retorna_default_para_modelos_padrao(self):
        elos = elo_mod.carregar_elo()
        self.assertEqual(set(elos.keys()), set(elo_mod.MODELOS_PADRAO))
        self.assertTrue(all(v == elo_mod.ELO_INICIAL for v in elos.values()))

    def test_salvar_e_carregar_faz_round_trip(self):
        elo_mod.salvar_elo({"a": 1600.0, "b": 1400.0})
        elos = elo_mod.carregar_elo()
        self.assertEqual(elos, {"a": 1600.0, "b": 1400.0})

    def test_salvar_cria_arquivo_json_legivel(self):
        elo_mod.salvar_elo({"a": 1600.0})
        conteudo = json.loads(elo_mod._ARQ_ELO.read_text(encoding="utf-8"))
        self.assertEqual(conteudo, {"a": 1600.0})


class TestRelatorioMetaCompetitivo(unittest.TestCase):
    def test_estrutura_e_estatisticas(self):
        elos = {"a": 1600.0, "b": 1400.0}
        with patch.object(elo_mod, "carregar_elo", return_value=elos), \
             patch("lotofacil_pkg.v21_0_sqlite.get_db", side_effect=RuntimeError("sem sqlite nos testes")):
            rel = elo_mod.relatorio_meta_competitivo()
        for chave in ("ranking", "fatores", "campeao", "ultimo_colocado",
                      "historico_elo", "estatisticas", "versao", "timestamp"):
            self.assertIn(chave, rel)
        self.assertEqual(rel["campeao"]["nome"], "a")
        self.assertEqual(rel["estatisticas"]["max_elo"], 1600.0)
        self.assertEqual(rel["estatisticas"]["min_elo"], 1400.0)
        self.assertEqual(rel["estatisticas"]["media_elo"], 1500.0)

    def test_sem_modelos_nao_quebra(self):
        with patch.object(elo_mod, "carregar_elo", return_value={}), \
             patch("lotofacil_pkg.v21_0_sqlite.get_db", side_effect=RuntimeError("sem sqlite nos testes")):
            rel = elo_mod.relatorio_meta_competitivo()
        self.assertEqual(rel["ranking"], [])
        self.assertEqual(rel["campeao"], {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
