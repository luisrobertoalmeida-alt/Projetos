"""
tests/test_analise_genetico.py — unittest version
"""
import os, sys, random, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Isola v18_1b_ia_adaptativa/v20_2_poda_inteligente do dados/ real do
# repositorio durante os testes (ver lotofacil_pkg/tests/__init__.py e
# ARQUITETURA.md -- 'unittest discover' com caminho de arquivo nao
# executa esse __init__.py de forma confiavel, entao o isolamento
# tambem precisa estar aqui, no proprio arquivo de teste).
import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg.config import NUMEROS
from lotofacil_pkg.utils import intersecao, normalizar_scores
from lotofacil_pkg.historico import analisar_historico, detectar_ciclo_historico
from lotofacil_pkg.analise import (
    calcular_motor_estrategico, calcular_ensemble_multi_ia,
    calcular_scores_markov, calcular_scores_bayesiano,
    calcular_scores_tendencia, calcular_scores_neural_leve,
    calcular_scores_estatistico, calcular_scores_pares_trios,
    calcular_scores_cobertura,
)
from lotofacil_pkg.genetico import (
    analisar_estrutura_jogo, score_jogo, gerar_jogo_base,
    crossover, mutacao, evoluir_populacao,
    calcular_mapa_cobertura, selecionar_jogos_cobertura_global,
    resumo_estrutural_pacote, sample_ponderado_sem_reposicao,
)

SEED = 42

def jogo_rand(seed=None):
    if seed is not None: random.seed(seed)
    return sorted(random.sample(NUMEROS, 15))

def hist_sintetico(n=100, seed=42):
    random.seed(seed)
    return [sorted(random.sample(NUMEROS, 15)) for _ in range(n)]

HIST = hist_sintetico(100, SEED)
ANALISE = analisar_historico(HIST)
PESOS_UNI = {n: 1.0/25 for n in NUMEROS}


class TestCiclo(unittest.TestCase):
    def test_ciclo_principal_valido(self):
        c = detectar_ciclo_historico(HIST)
        self.assertIn(c["ciclo_principal"],
            ("alta_repeticao","alta_dispersao","soma_alta","soma_baixa","estavel","indefinido"))
    def test_historico_curto_indefinido(self):
        c = detectar_ciclo_historico([jogo_rand(i) for i in range(5)])
        self.assertEqual(c["ciclo_principal"], "indefinido")
    def test_vazio_indefinido(self):
        self.assertEqual(detectar_ciclo_historico([])["ciclo_principal"], "indefinido")


class TestAnalisarHistorico(unittest.TestCase):
    def test_chaves(self):
        for k in ("freq","recentes","atrasos","soma_media","pares_media","hist_usado"):
            self.assertIn(k, ANALISE)
    def test_25_atrasos(self):
        self.assertEqual(len(ANALISE["atrasos"]), 25)
    def test_soma_media_razoavel(self):
        self.assertGreaterEqual(ANALISE["soma_media"], 120)
        self.assertLessEqual(ANALISE["soma_media"], 315)
    def test_janela_limita(self):
        a = analisar_historico(HIST, janela=30)
        self.assertLessEqual(len(a["hist_usado"]), 30)


class TestMotorEstrategico(unittest.TestCase):
    def setUp(self):
        self.e = calcular_motor_estrategico(ANALISE)
    def test_modo(self):
        self.assertIn(self.e["modo"], ("agressivo","equilibrado","conservador"))
    def test_confianca(self):
        self.assertGreaterEqual(self.e["indice_confianca"], 0.0)
        self.assertLessEqual(self.e["indice_confianca"], 1.0)
    def test_pesos_somam_1(self):
        s = self.e["peso_freq"] + self.e["peso_recente"] + self.e["peso_atraso"]
        self.assertAlmostEqual(s, 1.0, places=9)
    def test_diversidade_range(self):
        self.assertGreaterEqual(self.e["diversidade"], 0.0)
        self.assertLessEqual(self.e["diversidade"], 1.0)


class TestModelos(unittest.TestCase):
    def _ok(self, scores):
        self.assertEqual(set(scores.keys()), set(NUMEROS))
        self.assertTrue(all(v >= 0 for v in scores.values()))
        self.assertAlmostEqual(sum(scores.values()), 1.0, places=6)
    def test_markov(self): self._ok(calcular_scores_markov(HIST))
    def test_bayesiano(self): self._ok(calcular_scores_bayesiano(ANALISE))
    def test_tendencia(self): self._ok(calcular_scores_tendencia(ANALISE))
    def test_neural(self): self._ok(calcular_scores_neural_leve(ANALISE))
    def test_estatistico(self): self._ok(calcular_scores_estatistico(ANALISE))
    def test_pares_trios(self): self._ok(calcular_scores_pares_trios(ANALISE))
    def test_cobertura(self): self._ok(calcular_scores_cobertura(ANALISE))


class TestEnsemble(unittest.TestCase):
    def setUp(self):
        e = calcular_motor_estrategico(ANALISE)
        self.ens = calcular_ensemble_multi_ia(HIST, ANALISE, estrategia=e)
    def test_pesos_normalizados(self):
        pesos = self.ens["pesos_finais"]
        self.assertEqual(set(pesos.keys()), set(NUMEROS))
        self.assertAlmostEqual(sum(pesos.values()), 1.0, places=6)
    def test_ranking_25(self):
        self.assertEqual(len(self.ens["ranking"]), 25)
    def test_ranking_ordenado(self):
        pesos = [p for _,p in self.ens["ranking"]]
        self.assertEqual(pesos, sorted(pesos, reverse=True))
    def test_7_modelos(self):
        self.assertEqual(len(self.ens["modelos"]), 7)


class TestEstruturaJogo(unittest.TestCase):
    def test_valido_retorna_float(self):
        e = analisar_estrutura_jogo(jogo_rand(1))
        self.assertIsInstance(e["score_estrutural"], float)
    def test_invalido_negativo_extremo(self):
        e = analisar_estrutura_jogo([1,2,3])
        self.assertLessEqual(e["score_estrutural"], -1e8)
    def test_classificacao_valida(self):
        e = analisar_estrutura_jogo(jogo_rand(2))
        self.assertIn(e["classificacao"],
            ("estrutura forte","estrutura boa","estrutura aceitável","estrutura fraca"))
    def test_linhas_somam_15(self):
        self.assertEqual(sum(analisar_estrutura_jogo(jogo_rand(3))["linhas"]), 15)
    def test_colunas_somam_15(self):
        self.assertEqual(sum(analisar_estrutura_jogo(jogo_rand(4))["colunas"]), 15)
    def test_entropia_range(self):
        e = analisar_estrutura_jogo(jogo_rand(5))
        self.assertGreaterEqual(e["entropia"], 0.0)
        self.assertLessEqual(e["entropia"], 1.0)


class TestScoreJogo(unittest.TestCase):
    def test_invalido(self):
        self.assertLessEqual(score_jogo([1,2,3], PESOS_UNI, ANALISE), -1e8)
    def test_valido_float(self):
        self.assertIsInstance(score_jogo(jogo_rand(10), PESOS_UNI, ANALISE), float)


class TestSamplePonderado(unittest.TestCase):
    def test_15_dezenas(self):
        s = sample_ponderado_sem_reposicao(NUMEROS, PESOS_UNI, 15)
        self.assertEqual(len(s), 15)
    def test_sem_repeticao(self):
        s = sample_ponderado_sem_reposicao(NUMEROS, PESOS_UNI, 15)
        self.assertEqual(len(set(s)), 15)
    def test_validos(self):
        s = sample_ponderado_sem_reposicao(NUMEROS, PESOS_UNI, 15)
        self.assertTrue(all(1 <= n <= 25 for n in s))


class TestGerarJogoBase(unittest.TestCase):
    def _jogo(self, seed=1):
        random.seed(seed)
        return gerar_jogo_base(PESOS_UNI, ANALISE, tentativas=5)
    def test_15_dezenas(self): self.assertEqual(len(self._jogo()), 15)
    def test_validas(self): self.assertTrue(all(1 <= n <= 25 for n in self._jogo(2)))
    def test_sem_rep(self): self.assertEqual(len(set(self._jogo(3))), 15)
    def test_ordenado(self): j = self._jogo(4); self.assertEqual(j, sorted(j))


class TestCrossover(unittest.TestCase):
    def test_15_dezenas(self): self.assertEqual(len(crossover(jogo_rand(1), jogo_rand(2))), 15)
    def test_sem_rep(self): self.assertEqual(len(set(crossover(jogo_rand(3), jogo_rand(4)))), 15)
    def test_validas(self): self.assertTrue(all(1 <= n <= 25 for n in crossover(jogo_rand(5), jogo_rand(6))))
    def test_ordenado(self): f = crossover(jogo_rand(7), jogo_rand(8)); self.assertEqual(f, sorted(f))


class TestMutacao(unittest.TestCase):
    def test_15(self): self.assertEqual(len(mutacao(jogo_rand(10), PESOS_UNI, taxa=1.0)), 15)
    def test_sem_rep(self): self.assertEqual(len(set(mutacao(jogo_rand(11), PESOS_UNI, taxa=1.0))), 15)
    def test_validas(self): self.assertTrue(all(1 <= n <= 25 for n in mutacao(jogo_rand(12), PESOS_UNI, taxa=1.0)))
    def test_taxa_zero(self):
        random.seed(99)
        j = jogo_rand(13)
        self.assertEqual(mutacao(j, PESOS_UNI, taxa=0.0), sorted(j))


class TestEvoluir(unittest.TestCase):
    def test_validos(self):
        random.seed(42)
        pop = [jogo_rand(i) for i in range(10)]
        res = evoluir_populacao(pop, PESOS_UNI, ANALISE, geracoes=2, tamanho_pop=10, elite=3)
        self.assertEqual(len(res), 10)
        for j in res:
            self.assertEqual(len(j), 15)
            self.assertEqual(len(set(j)), 15)

    def test_populacao_nao_fica_identica_entre_geracoes(self):
        """
        Regressão da auditoria de 2026-07-23: confirma que a evolução
        realmente muda a população (não fica "congelada" por elitismo
        excessivo ou mutação zerada) — achado verificado manualmente
        pela auditoria, nunca coberto por teste automatizado até então.
        """
        random.seed(7)
        pop0 = [jogo_rand(i) for i in range(20)]
        pop0_set = {tuple(j) for j in pop0}
        pop_evoluida = evoluir_populacao(
            list(pop0), PESOS_UNI, ANALISE,
            geracoes=8, tamanho_pop=20, elite=3,
            estrategia={"taxa_mutacao": 0.5},
        )
        pop_evoluida_set = {tuple(j) for j in pop_evoluida}
        # Elite=3 permite no máximo 3 sobreviventes idênticos; o resto da
        # população precisa ter mudado por crossover/mutação.
        self.assertLessEqual(len(pop0_set & pop_evoluida_set), 3)


class TestSensibilidadeAoPeso(unittest.TestCase):
    """
    Regressão da auditoria de 2026-07-23: confirma que `pesos_finais`
    (o resultado aprendido do ensemble/poda/ELO) realmente influencia o
    que o algoritmo genético produz — o usuário perguntou explicitamente
    se isso era verificável, e até então só tinha sido confirmado
    manualmente pela auditoria, sem nenhum teste automatizado.
    """

    def test_dobrar_peso_de_uma_dezena_aumenta_taxa_de_aparicao(self):
        random.seed(123)
        dezena_alvo = 7
        pesos_base = dict(PESOS_UNI)

        pesos_altos = dict(PESOS_UNI)
        pesos_altos[dezena_alvo] *= 3.0
        soma = sum(pesos_altos.values())
        pesos_altos = {n: v / soma for n, v in pesos_altos.items()}

        n_amostras = 150
        aparicoes_base = sum(
            1 for _ in range(n_amostras)
            if dezena_alvo in gerar_jogo_base(pesos_base, ANALISE, tentativas=20)
        )
        aparicoes_alto = sum(
            1 for _ in range(n_amostras)
            if dezena_alvo in gerar_jogo_base(pesos_altos, ANALISE, tentativas=20)
        )
        self.assertGreater(aparicoes_alto, aparicoes_base)


class TestMapaCobertura(unittest.TestCase):
    def setUp(self):
        self.mapa = calcular_mapa_cobertura([jogo_rand(i) for i in range(10)])
    def test_chaves(self):
        for k in ("freq_dezenas","media_soma","media_pares","media_sobreposicao"):
            self.assertIn(k, self.mapa)
    def test_soma_razoavel(self):
        self.assertGreaterEqual(self.mapa["media_soma"], 120)
        self.assertLessEqual(self.mapa["media_soma"], 315)
    def test_sobreposicao_max(self):
        self.assertLessEqual(self.mapa["max_sobreposicao"], 15)


class TestResumoEstruturalPacote(unittest.TestCase):
    def test_retorna_score(self):
        r = resumo_estrutural_pacote([jogo_rand(i) for i in range(10)])
        self.assertIn("score_estrutural_medio", r)
    def test_vazio(self):
        self.assertEqual(resumo_estrutural_pacote([]), {})


class TestSelecaoCobertura(unittest.TestCase):
    def test_qtd_correta(self):
        candidatos = [jogo_rand(i) for i in range(50)]
        jogos, _ = selecionar_jogos_cobertura_global(candidatos, PESOS_UNI, ANALISE, qtd=5)
        self.assertEqual(len(jogos), 5)
    def test_sem_duplicatas(self):
        candidatos = [jogo_rand(i) for i in range(50)]
        jogos, _ = selecionar_jogos_cobertura_global(candidatos, PESOS_UNI, ANALISE, qtd=5)
        ts = [tuple(j) for j in jogos]
        self.assertEqual(len(set(ts)), len(ts))
    def test_validos(self):
        candidatos = [jogo_rand(i) for i in range(50)]
        jogos, _ = selecionar_jogos_cobertura_global(candidatos, PESOS_UNI, ANALISE, qtd=5)
        for j in jogos:
            self.assertEqual(len(j), 15)
            self.assertEqual(len(set(j)), 15)


if __name__ == "__main__":
    unittest.main()
