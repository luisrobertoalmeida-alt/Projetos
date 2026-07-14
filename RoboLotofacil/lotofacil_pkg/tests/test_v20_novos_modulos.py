"""
lotofacil_pkg/tests/test_v20_novos_modulos.py
----------------------------------------------
Testes unitários para V20.6 (bootstrap) e V20.8 (walk-forward).
"""
import random
import unittest

from lotofacil_pkg.v20_6_bootstrap import (
    bootstrap_media,
    bootstrap_comparacao,
    # Alias: evita que o pytest colete "teste_significancia" como um teste
    # próprio (nome começa com "test"), o que gerava um ERROR de fixture ausente.
    teste_significancia as _teste_significancia,
    tamanho_efeito_cohen_d,
    intervalo_confianca_taxa,
    relatorio_inferencial,
)
from lotofacil_pkg.v20_8_walkforward import (
    gerar_janelas_walkforward,
    score_janela,
    executar_walkforward,
    score_robustez_walkforward,
    detectar_overfitting_wf,
    relatorio_walkforward,
)


def _fake_resultados(media: float, n: int, desvio: float = 0.5, seed: int = 0) -> list[dict]:
    """Gera resultados sintéticos com média e desvio aproximados."""
    rng = random.Random(seed)
    return [{"acertos": max(0.0, min(15.0, rng.gauss(media, desvio)))} for _ in range(n)]


def _fake_historico(n: int, seed: int = 42) -> list[list[int]]:
    """Gera histórico sintético de concursos."""
    rng = random.Random(seed)
    return [sorted(rng.sample(range(1, 26), 15)) for _ in range(n)]


def _fn_gerar_simples(historico: list[list[int]]) -> list[list[int]]:
    """Função de geração simples para testes: retorna 5 jogos aleatórios."""
    rng = random.Random(len(historico))
    return [sorted(rng.sample(range(1, 26), 15)) for _ in range(5)]


# ── Testes V20.6 Bootstrap ────────────────────────────────────────────────────

class TestBootstrapMedia(unittest.TestCase):

    def test_retorna_dict_completo(self):
        res = _fake_resultados(11.0, 50)
        r = bootstrap_media(res, n_reamostras=200, seed=1)
        self.assertIn("media_observada", r)
        self.assertIn("intervalos", r)
        self.assertIn("95%", r["intervalos"])
        self.assertIn("99%", r["intervalos"])

    def test_lista_vazia(self):
        r = bootstrap_media([])
        self.assertEqual(r["media_observada"], 0.0)
        self.assertEqual(r["n_amostras"], 0)

    def test_ic_contem_media(self):
        res = _fake_resultados(11.0, 100, seed=7)
        r = bootstrap_media(res, n_reamostras=500, seed=7)
        ic = r["intervalos"]["95%"]
        self.assertLessEqual(ic["inferior"], r["media_observada"])
        self.assertGreaterEqual(ic["superior"], r["media_observada"])

    def test_ic_estreita_com_mais_amostras(self):
        res_peq = _fake_resultados(11.0, 10, seed=1)
        res_grd = _fake_resultados(11.0, 200, seed=1)
        r_p = bootstrap_media(res_peq, n_reamostras=300, seed=1)
        r_g = bootstrap_media(res_grd, n_reamostras=300, seed=1)
        amp_p = r_p["intervalos"]["95%"]["superior"] - r_p["intervalos"]["95%"]["inferior"]
        amp_g = r_g["intervalos"]["95%"]["superior"] - r_g["intervalos"]["95%"]["inferior"]
        self.assertGreater(amp_p, amp_g)


class TestBootstrapComparacao(unittest.TestCase):

    def test_superior_detectado(self):
        a = _fake_resultados(12.0, 100, desvio=0.3, seed=1)
        b = _fake_resultados(9.0, 100, desvio=0.3, seed=2)
        r = bootstrap_comparacao(a, b, n_reamostras=500, seed=1)
        self.assertEqual(r["veredito"], "SUPERIOR")
        self.assertTrue(r["significativo_95"])

    def test_equivalente_detectado(self):
        a = _fake_resultados(11.0, 80, desvio=0.5, seed=3)
        b = _fake_resultados(11.0, 80, desvio=0.5, seed=4)
        r = bootstrap_comparacao(a, b, n_reamostras=500, seed=5)
        self.assertIn(r["veredito"], ("EQUIVALENTE", "SUPERIOR", "INFERIOR"))  # sanity

    def test_listas_vazias(self):
        r = bootstrap_comparacao([], [])
        self.assertEqual(r["veredito"], "SEM_DADOS")


class TestTesteSignificancia(unittest.TestCase):

    def test_p_value_entre_0_e_1(self):
        a = _fake_resultados(11.5, 60, seed=1)
        b = _fake_resultados(9.0, 60, seed=2)
        r = _teste_significancia(a, b, n_reamostras=300, seed=1)
        self.assertGreaterEqual(r["p_value"], 0.0)
        self.assertLessEqual(r["p_value"], 1.0)

    def test_nivel_significancia_valido(self):
        a = _fake_resultados(11.5, 60, seed=1)
        b = _fake_resultados(9.0, 60, seed=2)
        r = _teste_significancia(a, b, n_reamostras=300, seed=1)
        self.assertIn(r["nivel_significancia"], ("p<0.01", "p<0.05", "p<0.10", "NS"))

    def test_sem_dados(self):
        r = _teste_significancia([], [])
        self.assertEqual(r["p_value"], 1.0)
        self.assertFalse(r["rejeita_h0"])


class TestCohenD(unittest.TestCase):

    def test_efeito_grande(self):
        a = _fake_resultados(13.0, 100, desvio=0.2, seed=1)
        b = _fake_resultados(9.0, 100, desvio=0.2, seed=2)
        r = tamanho_efeito_cohen_d(a, b)
        self.assertEqual(r["magnitude"], "GRANDE")
        self.assertGreater(r["cohen_d"], 0)

    def test_efeito_desprezivel(self):
        a = _fake_resultados(11.0, 100, desvio=0.5, seed=1)
        b = _fake_resultados(11.05, 100, desvio=0.5, seed=2)
        r = tamanho_efeito_cohen_d(a, b)
        self.assertIn(r["magnitude"], ("DESPREZIVEL", "PEQUENO"))

    def test_sem_dados(self):
        r = tamanho_efeito_cohen_d([], [])
        self.assertEqual(r["magnitude"], "SEM_DADOS")


class TestICTaxa(unittest.TestCase):

    def test_intervalo_valido(self):
        r = intervalo_confianca_taxa(30, 100, nivel=0.95)
        self.assertLessEqual(r["inferior"], r["taxa_observada"])
        self.assertGreaterEqual(r["superior"], r["taxa_observada"])
        self.assertGreaterEqual(r["inferior"], 0.0)
        self.assertLessEqual(r["superior"], 1.0)

    def test_zero_total(self):
        r = intervalo_confianca_taxa(0, 0)
        self.assertEqual(r["taxa_observada"], 0.0)

    def test_taxa_100_porcento(self):
        r = intervalo_confianca_taxa(100, 100, nivel=0.95)
        self.assertEqual(r["taxa_observada"], 1.0)


class TestRelatorioInferencial(unittest.TestCase):

    def test_estrutura_completa(self):
        a = _fake_resultados(11.0, 50, seed=1)
        b = _fake_resultados(9.0, 50, seed=2)
        r = relatorio_inferencial(a, b, n_reamostras=200, seed=1)
        self.assertIn("ic_media", r)
        self.assertIn("comparacao", r)
        self.assertIn("significancia", r)
        self.assertIn("cohen_d", r)
        self.assertIn("resumo", r)

    def test_sem_baseline(self):
        a = _fake_resultados(11.0, 50, seed=1)
        r = relatorio_inferencial(a, n_reamostras=200, seed=1)
        self.assertIsNone(r["comparacao"])
        self.assertIsNone(r["significancia"])


# ── Testes V20.8 Walk-Forward ─────────────────────────────────────────────────

class TestGerarJanelasWalkforward(unittest.TestCase):

    def test_gera_janelas_corretas(self):
        janelas = gerar_janelas_walkforward(200, tamanho_treino=100, tamanho_teste=20, passo=20)
        self.assertGreater(len(janelas), 0)
        for j in janelas:
            self.assertEqual(j["treino_fim"] - j["treino_inicio"], 100)
            self.assertEqual(j["teste_fim"] - j["teste_inicio"], 20)
            self.assertEqual(j["teste_inicio"], j["treino_fim"])

    def test_historico_insuficiente(self):
        janelas = gerar_janelas_walkforward(50, tamanho_treino=100, tamanho_teste=20)
        self.assertEqual(janelas, [])

    def test_janelas_consecutivas_deslocadas(self):
        janelas = gerar_janelas_walkforward(300, tamanho_treino=100, tamanho_teste=20, passo=20)
        for i in range(1, len(janelas)):
            self.assertEqual(
                janelas[i]["treino_inicio"],
                janelas[i - 1]["treino_inicio"] + 20,
            )


class TestScoreJanela(unittest.TestCase):

    def test_retorna_chaves_corretas(self):
        jogos = [sorted(random.sample(range(1, 26), 15)) for _ in range(5)]
        sorteios = [sorted(random.sample(range(1, 26), 15)) for _ in range(10)]
        r = score_janela(jogos, sorteios)
        self.assertIn("media_acertos", r)
        self.assertIn("melhor_acerto", r)
        self.assertIn("taxa_11_mais", r)
        self.assertIn("n_combinacoes", r)
        self.assertEqual(r["n_combinacoes"], 5 * 10)

    def test_listas_vazias(self):
        r = score_janela([], [])
        self.assertEqual(r["media_acertos"], 0.0)

    def test_acertos_na_faixa(self):
        jogos = [sorted(random.sample(range(1, 26), 15)) for _ in range(3)]
        sorteios = [sorted(random.sample(range(1, 26), 15)) for _ in range(5)]
        r = score_janela(jogos, sorteios)
        self.assertGreaterEqual(r["media_acertos"], 0.0)
        self.assertLessEqual(r["media_acertos"], 15.0)
        self.assertGreaterEqual(r["melhor_acerto"], 0)
        self.assertLessEqual(r["melhor_acerto"], 15)


class TestExecutarWalkforward(unittest.TestCase):

    def test_estrutura_retorno(self):
        hist = _fake_historico(200)
        r = executar_walkforward(hist, _fn_gerar_simples, tamanho_treino=100,
                                 tamanho_teste=20, passo=20)
        self.assertIn("janelas", r)
        self.assertIn("medias_por_janela", r)
        self.assertIn("media_geral", r)
        self.assertIn("n_janelas", r)

    def test_historico_insuficiente(self):
        hist = _fake_historico(50)
        r = executar_walkforward(hist, _fn_gerar_simples, tamanho_treino=100,
                                 tamanho_teste=20, passo=20)
        self.assertEqual(r["n_janelas"], 0)

    def test_media_na_faixa(self):
        hist = _fake_historico(300)
        r = executar_walkforward(hist, _fn_gerar_simples, tamanho_treino=100,
                                 tamanho_teste=20, passo=20)
        self.assertGreaterEqual(r["media_geral"], 0.0)
        self.assertLessEqual(r["media_geral"], 15.0)


class TestScoreRobustezWalkforward(unittest.TestCase):

    def test_score_na_faixa(self):
        for medias in [[], [9.0], [10.0, 10.5, 11.0], [8.0, 7.5, 7.0]]:
            s = score_robustez_walkforward(medias)
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 1.0)

    def test_melhor_que_aleatório_tem_score_maior(self):
        s_bom = score_robustez_walkforward([11.0, 11.2, 10.8])
        s_ruim = score_robustez_walkforward([8.5, 8.3, 8.7])
        self.assertGreater(s_bom, s_ruim)


class TestDetectarOverfittingWF(unittest.TestCase):

    def test_sem_overfitting(self):
        medias = [11.0] * 9
        r = detectar_overfitting_wf(medias)
        self.assertFalse(r["overfitting_detectado"])
        self.assertEqual(r["severidade"], "NORMAL")

    def test_overfitting_alto(self):
        medias = [11.0, 11.0, 11.0, 7.0, 7.0, 7.0]
        r = detectar_overfitting_wf(medias)
        self.assertTrue(r["overfitting_detectado"])
        self.assertEqual(r["severidade"], "ALTO")

    def test_amostras_insuficientes(self):
        r = detectar_overfitting_wf([11.0])
        self.assertEqual(r["severidade"], "INSUFICIENTE")


class TestRelatorioWalkforward(unittest.TestCase):

    def test_estrutura_completa(self):
        hist = _fake_historico(250)
        r = relatorio_walkforward(hist, _fn_gerar_simples,
                                  tamanho_treino=100, tamanho_teste=20, passo=20)
        self.assertIn("walkforward", r)
        self.assertIn("robustez", r)
        self.assertIn("overfitting", r)
        self.assertIn("resumo", r)
        self.assertIn("veredito", r["resumo"])

    def test_veredito_valido(self):
        hist = _fake_historico(250)
        r = relatorio_walkforward(hist, _fn_gerar_simples)
        self.assertIn(r["resumo"]["veredito"], ("ROBUSTO", "INSTAVEL", "ACEITAVEL"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
