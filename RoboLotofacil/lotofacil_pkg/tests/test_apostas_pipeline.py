"""
tests/test_apostas_pipeline.py — unittest version (integration tests)
"""
import os, sys, random, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Isola v18_1b_ia_adaptativa/v20_2_poda_inteligente do dados/ real do
# repositorio durante os testes (ver lotofacil_pkg/tests/__init__.py e
# ARQUITETURA.md -- 'unittest discover' com caminho de arquivo nao
# executa esse __init__.py de forma confiavel, entao o isolamento
# tambem precisa estar aqui, no proprio arquivo de teste).
import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg.config import NUMEROS
from lotofacil_pkg.utils import intersecao
from lotofacil_pkg.apostas import (
    gerar_apostas, simular_jogos_em_concurso, calcular_pacote_minimo,
)
from lotofacil_pkg.aprendizado import (
    registrar_resultado_aprendizado, calcular_bonus_aprendizado,
    carregar_memoria_aprendizado,
)
from lotofacil_pkg.genetico import calcular_mapa_cobertura

def _hist(n=150, seed=7):
    random.seed(seed)
    return [sorted(random.sample(NUMEROS, 15)) for _ in range(n)]

# Shared fixture — generated once for the module
_HIST = _hist()
_JOGOS = _ANALISE = _PESOS = None

def _ensure_apostas():
    global _JOGOS, _ANALISE, _PESOS
    if _JOGOS is None:
        _JOGOS, _ANALISE, _PESOS = gerar_apostas(
            _HIST, qtd_jogos=10, janela_analise=80, geracoes=5, pop_size=20
        )

class TestPacoteBasico(unittest.TestCase):
    def setUp(self): _ensure_apostas()
    def test_quantidade(self): self.assertEqual(len(_JOGOS), 10)
    def test_15_dezenas(self):
        for j in _JOGOS: self.assertEqual(len(j), 15)
    def test_sem_repeticao(self):
        for j in _JOGOS: self.assertEqual(len(set(j)), 15)
    def test_range_valido(self):
        for j in _JOGOS: self.assertTrue(all(1 <= n <= 25 for n in j))
    def test_ordenado(self):
        for j in _JOGOS: self.assertEqual(j, sorted(j))
    def test_sem_duplicados(self):
        ts = [tuple(j) for j in _JOGOS]
        self.assertEqual(len(set(ts)), len(ts))


class TestAnaliseRetornada(unittest.TestCase):
    def setUp(self): _ensure_apostas()
    def test_tem_estrategia(self):
        self.assertIn("estrategia", _ANALISE)
        self.assertIn(_ANALISE["estrategia"]["modo"], ("agressivo","equilibrado","conservador"))
    def test_tem_ensemble(self):
        self.assertIn("ensemble", _ANALISE)
        self.assertIn("pesos_finais", _ANALISE["ensemble"])
    def test_tem_cobertura(self):
        self.assertIn("cobertura_global", _ANALISE)
    def test_pesos_normalizados(self):
        self.assertEqual(set(_PESOS.keys()), set(NUMEROS))
        self.assertAlmostEqual(sum(_PESOS.values()), 1.0, places=6)


class TestQualidadeMinima(unittest.TestCase):
    def setUp(self): _ensure_apostas()
    def test_nenhum_jogo_concentrado_linha(self):
        for j in _JOGOS:
            linhas = [0]*5
            for n in j: linhas[(n-1)//5] += 1
            self.assertLessEqual(max(linhas), 5)
    def test_sobreposicao_max_menor_15(self):
        for i in range(len(_JOGOS)):
            for k in range(i+1, len(_JOGOS)):
                self.assertLess(intersecao(_JOGOS[i], _JOGOS[k]), 15)
    def test_cobertura_minima_20_dezenas(self):
        cobertas = set(n for j in _JOGOS for n in j)
        self.assertGreaterEqual(len(cobertas), 20)


class TestSimulador(unittest.TestCase):
    def setUp(self): _ensure_apostas()
    def test_total_jogos(self):
        real = sorted(random.sample(NUMEROS, 15))
        r = simular_jogos_em_concurso(_JOGOS, real)
        self.assertEqual(r["total_jogos"], 10)
    def test_acertos_range(self):
        real = sorted(random.sample(NUMEROS, 15))
        for r in simular_jogos_em_concurso(_JOGOS, real)["resultados"]:
            self.assertGreaterEqual(r["acertos"], 0)
            self.assertLessEqual(r["acertos"], 15)
    def test_melhor_consistente(self):
        real = sorted(random.sample(NUMEROS, 15))
        res = simular_jogos_em_concurso(_JOGOS, real)
        acertos = [r["acertos"] for r in res["resultados"]]
        self.assertEqual(res["melhor_acerto"], max(acertos))


class TestAprendizado(unittest.TestCase):
    def setUp(self):
        _ensure_apostas()
        self.tmp = tempfile.mkdtemp()

    def _cam(self, nome):
        return os.path.join(self.tmp, nome)

    def test_registrar_nao_quebra(self):
        real = sorted(random.sample(NUMEROS, 15))
        reg, _ = registrar_resultado_aprendizado(_JOGOS, _ANALISE, _PESOS, real, caminho=self._cam("a.json"))
        self.assertIn("melhor_acerto", reg)
        self.assertGreaterEqual(reg["melhor_acerto"], 0)
        self.assertLessEqual(reg["melhor_acerto"], 15)

    def test_sem_historico_nao_tem_memoria(self):
        m = carregar_memoria_aprendizado(self._cam("b.json"))
        aj = calcular_bonus_aprendizado(m)
        self.assertFalse(aj["tem_memoria"])

    def test_roundtrip_registro(self):
        real = sorted(random.sample(NUMEROS, 15))
        cam = self._cam("c.json")
        registrar_resultado_aprendizado(_JOGOS, _ANALISE, _PESOS, real, caminho=cam)
        m = carregar_memoria_aprendizado(cam)
        self.assertEqual(len(m["registros"]), 1)

    def test_pipeline_apos_aprendizado(self):
        real = sorted(random.sample(NUMEROS, 15))
        cam = self._cam("d.json")
        registrar_resultado_aprendizado(_JOGOS, _ANALISE, _PESOS, real, caminho=cam)
        jogos2, _, _ = gerar_apostas(_HIST, qtd_jogos=5, janela_analise=80, geracoes=3, pop_size=15)
        self.assertEqual(len(jogos2), 5)
        for j in jogos2:
            self.assertEqual(len(j), 15)


if __name__ == "__main__":
    unittest.main()
