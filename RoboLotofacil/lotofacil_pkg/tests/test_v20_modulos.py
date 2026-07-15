"""
tests/test_v20_modulos.py
--------------------------
Testes unitários para os módulos V20:
  - v20_4_backtest_massivo: backtest multi-janela, paralelo, relatório
  - v20_2_poda_inteligente: score de sobrevivência, classificação, quarentena
  - v20_3_ablation: contribuição marginal, ranking, modelos negativos

Execute com:  python -m unittest discover -s lotofacil_pkg/tests -p "test_*.py" -v
"""
import os
import sys
import json
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

from lotofacil_pkg.v20_4_backtest_massivo import (
    avaliar_janela,
    _avaliar_item,
    backtest_multijanela,
    backtest_paralelo,
    gerar_relatorio_backtest,
)
from lotofacil_pkg.v20_2_poda_inteligente import (
    score_sobrevivencia,
    classificar_modelo,
    salvar_quarentena,
    ESTADO_ATIVO,
    ESTADO_OBSERVACAO,
    ESTADO_SUSPENSO,
)
from lotofacil_pkg.v20_3_ablation import (
    avaliar_contribuicao,
    ranking_contribuicao,
    gerar_relatorio_ablation,
)


# ── v20_4_backtest_massivo ────────────────────────────────────────────────────

class TestAvaliarJanela(unittest.TestCase):

    def test_retorna_media_correta(self):
        r = avaliar_janela("j1", [0.5, 0.7, 0.8])
        self.assertEqual(r["janela"], "j1")
        self.assertAlmostEqual(r["media"], round((0.5 + 0.7 + 0.8) / 3, 4))

    def test_lista_vazia_retorna_zero(self):
        r = avaliar_janela("vazio", [])
        self.assertEqual(r["media"], 0)
        self.assertEqual(r["janela"], "vazio")

    def test_um_elemento(self):
        r = avaliar_janela("solo", [0.9])
        self.assertAlmostEqual(r["media"], 0.9)


class TestAvaliarItem(unittest.TestCase):
    """Garante que _avaliar_item (wrapper pickle-safe) é equivalente a avaliar_janela."""

    def test_equivalente_a_avaliar_janela(self):
        direto = avaliar_janela("x", [1.0, 2.0])
        via_wrapper = _avaliar_item(("x", [1.0, 2.0]))
        self.assertEqual(direto, via_wrapper)

    def test_serializavel_com_pickle(self):
        import pickle
        # Se isto não lançar exceção, a função é pickle-safe
        dados = pickle.dumps(_avaliar_item)
        fn = pickle.loads(dados)
        self.assertEqual(fn(("t", [0.5])), {"janela": "t", "media": 0.5})


class TestBacktestMultijanela(unittest.TestCase):

    def _janelas(self):
        return {
            "30d": [0.5, 0.6, 0.7],
            "60d": [0.4, 0.5],
            "90d": [],
        }

    def test_retorna_lista_com_todas_janelas(self):
        resultado = backtest_multijanela(self._janelas())
        self.assertEqual(len(resultado), 3)
        nomes = {r["janela"] for r in resultado}
        self.assertEqual(nomes, {"30d", "60d", "90d"})

    def test_janela_vazia_tem_media_zero(self):
        resultado = backtest_multijanela(self._janelas())
        vazia = next(r for r in resultado if r["janela"] == "90d")
        self.assertEqual(vazia["media"], 0)


class TestBacktestParalelo(unittest.TestCase):
    """Testa que backtest_paralelo retorna os mesmos resultados que o sequencial."""

    def test_resultados_equivalentes_ao_sequencial(self):
        janelas = {"a": [0.1, 0.2], "b": [0.9], "c": []}
        seq = sorted(backtest_multijanela(janelas), key=lambda x: x["janela"])
        par = sorted(backtest_paralelo(janelas), key=lambda x: x["janela"])
        self.assertEqual(seq, par)

    def test_nao_lanca_excecao_com_lambda(self):
        # Garante que o bug original (lambda não-serializável) está corrigido
        try:
            backtest_paralelo({"j": [0.5, 0.6]})
        except Exception as e:
            self.fail(f"backtest_paralelo lançou exceção inesperada: {e}")


class TestGerarRelatorioBacktest(unittest.TestCase):

    def test_cria_arquivo_json_valido(self):
        resultados = [{"janela": "30d", "media": 0.65}]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            caminho = f.name
        try:
            dados = gerar_relatorio_backtest(resultados, arquivo=caminho)
            self.assertIn("resultados", dados)
            with open(caminho, encoding="utf-8") as f:
                carregado = json.load(f)
            self.assertEqual(carregado["resultados"], resultados)
        finally:
            os.unlink(caminho)


# ── v20_2_poda_inteligente ────────────────────────────────────────────────────

class TestScoreSobrevivencia(unittest.TestCase):

    def test_pesos_somam_um(self):
        # 0.5 + 0.3 + 0.2 = 1.0
        s = score_sobrevivencia(1.0, 1.0, 1.0)
        self.assertAlmostEqual(s, 1.0)

    def test_score_zero_quando_tudo_zero(self):
        s = score_sobrevivencia(0.0, 0.0, 0.0)
        self.assertAlmostEqual(s, 0.0)

    def test_pesos_individuais(self):
        # só score_global=1, resto 0 → deve retornar 0.5
        self.assertAlmostEqual(score_sobrevivencia(1.0, 0.0, 0.0), 0.5)
        # só desempenho_recente=1 → deve retornar 0.3
        self.assertAlmostEqual(score_sobrevivencia(0.0, 1.0, 0.0), 0.3)
        # só estabilidade=1 → deve retornar 0.2
        self.assertAlmostEqual(score_sobrevivencia(0.0, 0.0, 1.0), 0.2)


class TestClassificarModelo(unittest.TestCase):

    def test_ativo_acima_de_070(self):
        self.assertEqual(classificar_modelo(0.70), ESTADO_ATIVO)
        self.assertEqual(classificar_modelo(0.99), ESTADO_ATIVO)

    def test_observacao_entre_050_e_070(self):
        # Limiares reais: ATIVO >= 0.08, OBSERVACAO >= 0.03, SUSPENSO < 0.03
        self.assertEqual(classificar_modelo(0.05), ESTADO_OBSERVACAO)
        self.assertEqual(classificar_modelo(0.07), ESTADO_OBSERVACAO)

    def test_suspenso_abaixo_de_050(self):
        self.assertEqual(classificar_modelo(0.02), ESTADO_SUSPENSO)
        self.assertEqual(classificar_modelo(0.0), ESTADO_SUSPENSO)

    def test_fronteiras_exatas(self):
        self.assertEqual(classificar_modelo(0.08), ESTADO_ATIVO)
        self.assertEqual(classificar_modelo(0.03), ESTADO_OBSERVACAO)


class TestSalvarQuarentena(unittest.TestCase):

    def test_salva_apenas_suspensos(self):
        modelos = [
            {"nome": "A", "estado": ESTADO_ATIVO},
            {"nome": "B", "estado": ESTADO_SUSPENSO},
            {"nome": "C", "estado": ESTADO_OBSERVACAO},
            {"nome": "D", "estado": ESTADO_SUSPENSO},
        ]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            caminho = f.name
        try:
            suspensos = salvar_quarentena(modelos, arquivo=caminho)
            self.assertEqual(len(suspensos), 2)
            nomes = {m["nome"] for m in suspensos}
            self.assertEqual(nomes, {"B", "D"})
            with open(caminho, encoding="utf-8") as f:
                dados = json.load(f)
            self.assertEqual(len(dados), 2)
        finally:
            os.unlink(caminho)

    def test_nenhum_suspenso(self):
        modelos = [{"nome": "X", "estado": ESTADO_ATIVO}]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            caminho = f.name
        try:
            suspensos = salvar_quarentena(modelos, arquivo=caminho)
            self.assertEqual(suspensos, [])
        finally:
            os.unlink(caminho)


# ── v20_3_ablation ────────────────────────────────────────────────────────────

class TestAvaliarContribuicao(unittest.TestCase):

    def test_contribuicao_positiva(self):
        self.assertAlmostEqual(avaliar_contribuicao(0.80, 0.70), 0.10)

    def test_contribuicao_negativa(self):
        self.assertAlmostEqual(avaliar_contribuicao(0.70, 0.80), -0.10)

    def test_contribuicao_zero(self):
        self.assertAlmostEqual(avaliar_contribuicao(0.75, 0.75), 0.0)


class TestRankingContribuicao(unittest.TestCase):

    def test_ordenado_decrescente(self):
        contrib = {"A": 0.1, "B": 0.5, "C": -0.2, "D": 0.3}
        ranking = ranking_contribuicao(contrib)
        valores = [v for _, v in ranking]
        self.assertEqual(valores, sorted(valores, reverse=True))

    def test_todos_os_modelos_presentes(self):
        contrib = {"A": 0.1, "B": 0.2}
        ranking = ranking_contribuicao(contrib)
        self.assertEqual(len(ranking), 2)


class TestGerarRelatorioAblation(unittest.TestCase):

    def test_identifica_modelos_negativos(self):
        contrib = {"A": 0.3, "B": -0.1, "C": 0.0, "D": -0.05}
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            caminho = f.name
        try:
            dados = gerar_relatorio_ablation(contrib, arquivo=caminho)
            negativos = dados["modelos_negativos"]
            self.assertIn("B", negativos)
            self.assertIn("D", negativos)
            self.assertNotIn("A", negativos)
            self.assertNotIn("C", negativos)
        finally:
            os.unlink(caminho)

    def test_cria_arquivo_json_valido(self):
        contrib = {"X": 0.5, "Y": -0.1}
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            caminho = f.name
        try:
            gerar_relatorio_ablation(contrib, arquivo=caminho)
            with open(caminho, encoding="utf-8") as f:
                dados = json.load(f)
            self.assertIn("ranking", dados)
            self.assertIn("modelos_negativos", dados)
        finally:
            os.unlink(caminho)

    def test_sem_modelos_negativos(self):
        contrib = {"A": 0.5, "B": 0.3}
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            caminho = f.name
        try:
            dados = gerar_relatorio_ablation(contrib, arquivo=caminho)
            self.assertEqual(dados["modelos_negativos"], [])
        finally:
            os.unlink(caminho)


if __name__ == "__main__":
    unittest.main(verbosity=2)
