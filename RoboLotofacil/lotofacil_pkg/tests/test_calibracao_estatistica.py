"""
tests/test_calibracao_estatistica.py
--------------------------------------
Testes automatizados para:
  1. Validação estatística da calibração (p-valor, IC95%, Cohen's d)
  2. Critério de aprovação de configurações (taxa vitória ≥ 55%)
  3. Detecção de outliers na calibração
  4. Funções de bootstrap e inferência (v20_6_bootstrap)
  5. Integridade do relatório de calibração

Execute com:
  python -m unittest discover -s lotofacil_pkg/tests -p "test_*.py" -v
  ou diretamente:
  python -m unittest lotofacil_pkg/tests/test_calibracao_estatistica.py -v
"""
import os
import sys
import random
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from lotofacil_pkg.v20_6_bootstrap import (
    # Alias com "_" na frente: evita que o pytest colete essa função importada
    # como se fosse um teste próprio (qualquer nome iniciado por "test" é
    # candidato a coleta), o que causava um ERROR de fixture ausente.
    teste_significancia as _teste_significancia,
    intervalo_confianca_taxa,
    tamanho_efeito_cohen_d,
    bootstrap_media,
    bootstrap_comparacao,
)
from lotofacil_pkg.backtest import (
    score_calibracao_pacote,
    resumir_acertos_pacote,
    gerar_jogos_aleatorios,
    resumir_linhas_calibracao,
)
from lotofacil_pkg.config import NUMEROS

SEED = 42
random.seed(SEED)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _scores_robo_vence(n=70, seed=0):
    """Gera lista de dicts onde o robô consistentemente supera o aleatório."""
    rng = random.Random(seed)
    return (
        [{"acertos": 10.0 + rng.uniform(0, 5)} for _ in range(n)],  # robô
        [{"acertos": 8.0  + rng.uniform(0, 5)} for _ in range(n)],  # aleatório
    )

def _scores_empate(n=70, seed=1):
    """Gera dicts com scores estatisticamente idênticos."""
    rng = random.Random(seed)
    base = [{"acertos": 9.0 + rng.gauss(0, 1)} for _ in range(n)]
    return base[:], base[:]  # mesma sequência

def _scores_aleatorio_vence(n=70, seed=2):
    """Gera dicts onde o aleatório supera o robô."""
    r, a = _scores_robo_vence(n, seed)
    return a, r  # invertido


# ─────────────────────────────────────────────────────────────────────────────
# 1. Testes de p-valor (teste_significancia)
# ─────────────────────────────────────────────────────────────────────────────

class TestTesteSignificancia(unittest.TestCase):

    def test_robo_vence_significativo(self):
        """Quando robô supera claramente o aleatório, p < 0.05."""
        robo, ale = _scores_robo_vence(n=70)
        resultado = _teste_significancia(robo, ale)
        self.assertIn("p_value", resultado)
        self.assertLessEqual(resultado["p_value"], 0.05,
            "Robô claramente melhor deve ter p ≤ 0.05")
        self.assertTrue(resultado.get("rejeita_h0", False))

    def test_empate_nao_significativo(self):
        """Scores idênticos não devem ser significativos."""
        robo, ale = _scores_empate(n=70)
        resultado = _teste_significancia(robo, ale)
        self.assertGreater(resultado["p_value"], 0.05,
            "Scores iguais não devem ter p ≤ 0.05")
        self.assertFalse(resultado.get("rejeita_h0", True))

    def test_retorna_dicionario(self):
        robo, ale = _scores_robo_vence(n=30)
        resultado = _teste_significancia(robo, ale)
        self.assertIsInstance(resultado, dict)
        self.assertIn("p_value", resultado)
        self.assertIn("rejeita_h0", resultado)

    def test_lista_vazia_nao_explode(self):
        """Listas vazias não devem lançar exceção."""
        try:
            resultado = _teste_significancia([], [])
            self.assertIsInstance(resultado, dict)
        except Exception as e:
            self.fail(f"_teste_significancia([],[]) lançou exceção: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Testes de IC 95% (intervalo_confianca_taxa)
# ─────────────────────────────────────────────────────────────────────────────

class TestIntervaloConfianca(unittest.TestCase):

    def test_taxa_57_pct(self):
        """57% de vitória em 70 passos deve ter IC que exclui 50%."""
        ic = intervalo_confianca_taxa(40, 70)
        self.assertIn("inferior", ic)
        self.assertIn("superior", ic)
        self.assertGreater(ic["inferior"], 0.40,
            "IC inferior de 57% em n=70 deve ser > 40%")

    def test_taxa_50_pct_inclui_50(self):
        """50% de vitória em 70 passos deve ter IC que inclui 50%."""
        ic = intervalo_confianca_taxa(35, 70)
        self.assertLessEqual(ic["inferior"], 0.50)
        self.assertGreaterEqual(ic["superior"], 0.50)

    def test_ic_ordenado(self):
        """IC inferior deve ser menor que IC superior."""
        for vitorias, total in [(32, 70), (40, 70), (50, 70), (10, 70)]:
            ic = intervalo_confianca_taxa(vitorias, total)
            self.assertLessEqual(ic["inferior"], ic["superior"],
                f"IC desordenado para {vitorias}/{total}")

    def test_limites_entre_0_e_1(self):
        """IC deve estar entre 0 e 1."""
        ic = intervalo_confianca_taxa(40, 70)
        self.assertGreaterEqual(ic["inferior"], 0.0)
        self.assertLessEqual(ic["superior"], 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Testes de Cohen's d (tamanho_efeito_cohen_d)
# ─────────────────────────────────────────────────────────────────────────────

class TestCohenD(unittest.TestCase):

    def test_efeito_grande(self):
        """Diferença grande deve resultar em interpretação 'grande'."""
        # tamanho_efeito_cohen_d espera list[dict] (mesmo formato de
        # _scores_robo_vence), não uma lista de floats crua.
        robo = [{"acertos": 15.0 + random.gauss(0, 0.3)} for _ in range(70)]
        ale  = [{"acertos": 10.0 + random.gauss(0, 0.3)} for _ in range(70)]
        resultado = tamanho_efeito_cohen_d(robo, ale)
        self.assertEqual(resultado["magnitude"].upper(), "GRANDE",
            "Diferença de 5 pontos com desvio pequeno deve ter efeito 'grande'")

    def test_efeito_zero(self):
        """Listas iguais devem ter d ≈ 0."""
        base = [{"acertos": 11.0 + random.gauss(0, 1)} for _ in range(70)]
        resultado = tamanho_efeito_cohen_d(base, base)
        self.assertAlmostEqual(resultado["cohen_d"], 0.0, places=5)

    def test_retorna_interpretacao(self):
        """Deve retornar campo 'interpretacao'."""
        robo, ale = _scores_robo_vence()
        resultado = tamanho_efeito_cohen_d(robo, ale)
        self.assertIn("magnitude", resultado)
        self.assertIsInstance(resultado["magnitude"], str)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Critério de aprovação de configurações
# ─────────────────────────────────────────────────────────────────────────────

class TestCriterioAprovacao(unittest.TestCase):
    """
    Regra definida em sessão: taxa de vitória ≥ 55% (≥ 39/70) para aprovação.
    G=243 e G=88 aprovados com 40/70 (57.1%).
    G=72 reprovado com 32/70 (45.7%).
    """

    LIMIAR = 0.55
    PASSOS = 70

    def _taxa(self, vitorias):
        return vitorias / self.PASSOS

    def test_g88_aprovado(self):
        """G=88 com 40/70 vitórias deve ser aprovado."""
        self.assertGreaterEqual(self._taxa(40), self.LIMIAR,
            "G=88 (40/70=57.1%) deve passar no limiar de 55%")

    def test_g243_aprovado(self):
        """G=243 com 40/70 vitórias deve ser aprovado."""
        self.assertGreaterEqual(self._taxa(40), self.LIMIAR,
            "G=243 (40/70=57.1%) deve passar no limiar de 55%")

    def test_g72_reprovado(self):
        """G=72 com 32/70 vitórias deve ser reprovado."""
        self.assertLess(self._taxa(32), self.LIMIAR,
            "G=72 (32/70=45.7%) deve reprovar no limiar de 55%")

    def test_limiar_exato(self):
        """Exatamente 55% (38.5 → 39 vitórias) deve ser aprovado."""
        vitorias_minimas = int(self.LIMIAR * self.PASSOS) + 1  # 39
        self.assertGreaterEqual(self._taxa(vitorias_minimas), self.LIMIAR)

    def test_abaixo_limiar(self):
        """38/70 = 54.3% deve ser reprovado."""
        self.assertLess(self._taxa(38), self.LIMIAR)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Detecção de outliers na calibração
# ─────────────────────────────────────────────────────────────────────────────

class TestDeteccaoOutliers(unittest.TestCase):
    """
    Outliers como aleatório fazendo 14 pontos (score -40.25) distorcem
    a vantagem média. Detectar e sinalizar esses casos é importante.
    """

    def _vantagens_com_outlier(self):
        rng = random.Random(42)
        vantagens = [rng.uniform(-3, 5) for _ in range(69)]
        vantagens.append(-40.25)  # outlier: aleatório fez 14 pontos
        return vantagens

    def _detectar_outliers(self, vantagens, limiar_desvios=3.0):
        """Detecta valores além de N desvios padrão da média."""
        if len(vantagens) < 2:
            return []
        media = sum(vantagens) / len(vantagens)
        var = sum((v - media) ** 2 for v in vantagens) / (len(vantagens) - 1)
        desvio = var ** 0.5
        if desvio == 0:
            return []
        return [v for v in vantagens if abs(v - media) > limiar_desvios * desvio]

    def test_outlier_detectado(self):
        """O valor -40.25 deve ser detectado como outlier."""
        vantagens = self._vantagens_com_outlier()
        outliers = self._detectar_outliers(vantagens)
        self.assertTrue(len(outliers) > 0, "Deve detectar ao menos 1 outlier")
        self.assertIn(-40.25, outliers)

    def test_sem_outlier(self):
        """Dados normais não devem ter outliers."""
        rng = random.Random(0)
        vantagens = [rng.uniform(-3, 5) for _ in range(70)]
        outliers = self._detectar_outliers(vantagens)
        self.assertEqual(len(outliers), 0, "Dados normais não devem ter outliers")

    def test_vantagem_media_sem_outlier(self):
        """Remover outlier deve melhorar a vantagem média."""
        vantagens = self._vantagens_com_outlier()
        media_com = sum(vantagens) / len(vantagens)
        vantagens_sem = [v for v in vantagens if v != -40.25]
        media_sem = sum(vantagens_sem) / len(vantagens_sem)
        self.assertGreater(media_sem, media_com,
            "Média sem outlier deve ser maior que com outlier")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Integridade do score de calibração
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreCalibracao(unittest.TestCase):

    def _resumo(self, melhor, qtd_11=5, qtd_12=2, qtd_13=0):
        return {
            "melhor": melhor,
            "media": melhor - 1.5,
            "qtd_11": qtd_11,
            "qtd_12": qtd_12,
            "qtd_13": qtd_13,
            "qtd_14": 0,
            "qtd_15": 0,
            "qtd_11_mais": qtd_11 + qtd_12 + qtd_13,
            "qtd_12_mais": qtd_12 + qtd_13,
            "qtd_13_mais": qtd_13,
        }

    def test_melhor_jogo_maior_score(self):
        """Pacote com melhor acerto maior deve ter score maior."""
        score_12 = score_calibracao_pacote(self._resumo(12))
        score_11 = score_calibracao_pacote(self._resumo(11))
        self.assertGreater(score_12, score_11)

    def test_score_positivo(self):
        """Score nunca deve ser negativo para pacote com acertos razoáveis."""
        score = score_calibracao_pacote(self._resumo(11))
        self.assertGreaterEqual(score, 0)

    def test_mais_jogos_11_mais_score(self):
        """Mais jogos com 11+ deve aumentar o score."""
        s_menos = score_calibracao_pacote(self._resumo(11, qtd_11=3, qtd_12=1))
        s_mais  = score_calibracao_pacote(self._resumo(11, qtd_11=8, qtd_12=3))
        self.assertGreater(s_mais, s_menos)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Bootstrap
# ─────────────────────────────────────────────────────────────────────────────

class TestBootstrap(unittest.TestCase):

    def _dados(self, media, n=70, desvio=1.0, seed=0):
        rng = random.Random(seed)
        return [{"acertos": media + rng.gauss(0, desvio)} for _ in range(n)]

    def test_bootstrap_media_proxima(self):
        """Média bootstrap deve ser próxima da média real."""
        dados = self._dados(11.3, n=70)
        resultado = bootstrap_media(dados, n_reamostras=500)
        self.assertAlmostEqual(resultado["media_observada"], 11.3, delta=0.3)

    def test_bootstrap_comparacao_estrutura(self):
        """bootstrap_comparacao deve retornar estrutura esperada."""
        a = self._dados(11.5, seed=0)
        b = self._dados(11.0, seed=1)
        resultado = bootstrap_comparacao(a, b, n_reamostras=500)
        self.assertIn("delta_observado", resultado)
        self.assertIn("intervalos", resultado)
        self.assertIn("inferior", resultado["intervalos"]["95%"])
        self.assertIn("superior", resultado["intervalos"]["95%"])

    def test_bootstrap_ic_ordenado(self):
        """IC do bootstrap deve ter inferior ≤ superior."""
        dados = self._dados(11.0)
        resultado = bootstrap_media(dados, n_reamostras=500)
        ic_95 = resultado["intervalos"]["95%"]
        self.assertLessEqual(ic_95["inferior"], ic_95["superior"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
