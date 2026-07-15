"""
tests/test_utils.py — unittest version
"""
import json, os, sys, tempfile, unittest, random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Isola v18_1b_ia_adaptativa/v20_2_poda_inteligente do dados/ real do
# repositorio durante os testes (ver lotofacil_pkg/tests/__init__.py e
# ARQUITETURA.md -- 'unittest discover' com caminho de arquivo nao
# executa esse __init__.py de forma confiavel, entao o isolamento
# tambem precisa estar aqui, no proprio arquivo de teste).
import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg.utils import (
    contar_pares, distancia_jogos, formatar_jogo, gerar_timestamp_arquivo,
    intersecao, ler_json, limitar, normalizar_scores, parse_data_br,
    salvar_json, soma_jogo, tornar_json_seguro,
)
from lotofacil_pkg.config import NUMEROS


class TestFormatarJogo(unittest.TestCase):
    def test_ordenado_zeropaded(self):
        self.assertEqual(formatar_jogo([3, 1, 25, 10]), "01 03 10 25")
    def test_retorna_string(self):
        self.assertIsInstance(formatar_jogo([5, 10, 15]), str)
    def test_jogo_ja_ordenado(self):
        jogo = list(range(1, 16))
        partes = formatar_jogo(jogo).split()
        self.assertEqual(partes, [f"{n:02d}" for n in range(1, 16)])


class TestContarPares(unittest.TestCase):
    def test_todos_impares(self): self.assertEqual(contar_pares([1,3,5,7,9]), 0)
    def test_todos_pares(self): self.assertEqual(contar_pares([2,4,6,8,10]), 5)
    def test_misturado(self): self.assertEqual(contar_pares([1,2,3,4,5]), 2)
    def test_jogo_15(self):
        self.assertEqual(contar_pares(list(range(1,16))), 7)


class TestSomaJogo(unittest.TestCase):
    def test_basico(self): self.assertEqual(soma_jogo([1,2,3]), 6)
    def test_identidade(self):
        jogo = [1,5,9,12,15,17,20,22,24,3,8,11,19,23,25]
        self.assertEqual(soma_jogo(jogo), sum(jogo))


class TestIntersecaoDistancia(unittest.TestCase):
    def test_intersecao_total(self): self.assertEqual(intersecao([1,2,3],[1,2,3]), 3)
    def test_intersecao_zero(self): self.assertEqual(intersecao([1,3,5],[2,4,6]), 0)
    def test_intersecao_parcial(self): self.assertEqual(intersecao([1,2,3],[2,3,4]), 2)
    def test_distancia_identicos(self): self.assertEqual(distancia_jogos([1,2,3],[1,2,3]), 0)
    def test_distancia_complementares(self): self.assertEqual(distancia_jogos([1,2,3],[4,5,6]), 6)
    def test_distancia_parcial(self): self.assertEqual(distancia_jogos([1,2,3],[2,3,4]), 2)


class TestLimitar(unittest.TestCase):
    def test_dentro(self): self.assertEqual(limitar(5.0, 0.0, 10.0), 5.0)
    def test_abaixo(self): self.assertEqual(limitar(-1.0, 0.0, 10.0), 0.0)
    def test_acima(self): self.assertEqual(limitar(15.0, 0.0, 10.0), 10.0)
    def test_limite_inf(self): self.assertEqual(limitar(0.0, 0.0, 10.0), 0.0)
    def test_limite_sup(self): self.assertEqual(limitar(10.0, 0.0, 10.0), 10.0)
    def test_negativo(self): self.assertEqual(limitar(-5.0, -10.0, -1.0), -5.0)


class TestParseDataBr(unittest.TestCase):
    def test_br(self): self.assertEqual(parse_data_br("25/12/2023"), "25/12/2023")
    def test_iso(self): self.assertEqual(parse_data_br("2023-12-25"), "25/12/2023")
    def test_hifen(self): self.assertEqual(parse_data_br("25-12-2023"), "25/12/2023")
    def test_none(self): self.assertEqual(parse_data_br(None), "")
    def test_vazio(self): self.assertEqual(parse_data_br(""), "")
    def test_com_hora(self): self.assertEqual(parse_data_br("2023-12-25 10:30:00"), "25/12/2023")
    def test_desconhecido_retorna_str(self):
        self.assertIsInstance(parse_data_br("abc"), str)


class TestNormalizarScores(unittest.TestCase):
    def test_soma_1(self):
        scores = {n: float(n) for n in NUMEROS}
        norm = normalizar_scores(scores)
        self.assertAlmostEqual(sum(norm.values()), 1.0, places=9)

    def test_todos_numeros(self):
        norm = normalizar_scores({n: 1.0 for n in NUMEROS})
        self.assertEqual(set(norm.keys()), set(NUMEROS))

    def test_uniforme_com_dict_vazio(self):
        norm = normalizar_scores({}, piso=0.001)
        self.assertEqual(len(norm), 25)
        self.assertAlmostEqual(sum(norm.values()), 1.0, places=9)

    def test_sem_negativos(self):
        norm = normalizar_scores({n: -float(n) for n in NUMEROS})
        self.assertTrue(all(v >= 0 for v in norm.values()))

    def test_maior_score_tem_maior_peso(self):
        scores = {1: 100.0, **{n: 1.0 for n in range(2, 26)}}
        norm = normalizar_scores(scores)
        self.assertGreater(norm[1], norm[2])


class TestTornarJsonSeguro(unittest.TestCase):
    def test_chave_tupla(self):
        safe = tornar_json_seguro({(1,2): 3.0})
        self.assertIsInstance(list(safe.keys())[0], str)

    def test_set_vira_lista(self):
        safe = tornar_json_seguro({1,2,3})
        self.assertIsInstance(safe, list)

    def test_serializavel(self):
        obj = {"x": {(1,2): [1, {3,4}]}}
        self.assertIsInstance(json.dumps(tornar_json_seguro(obj)), str)


class TestJsonIO(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _path(self, name):
        return os.path.join(self.tmp, name)

    def test_roundtrip(self):
        dados = {"chave": [1,2,3]}
        p = self._path("rt.json")
        salvar_json(p, dados)
        self.assertEqual(ler_json(p), dados)

    def test_inexistente_retorna_default(self):
        self.assertEqual(ler_json(self._path("nope.json"), {"x":1}), {"x":1})

    def test_corrompido_retorna_default(self):
        p = self._path("bad.json")
        with open(p,"w") as f: f.write("{ não é json !!!")
        self.assertEqual(ler_json(p, {"fb":True}), {"fb":True})

    def test_salvar_cria_pasta(self):
        p = self._path("sub/novo/arquivo.json")
        salvar_json(p, {"ok":True})
        self.assertTrue(os.path.exists(p))

    def test_default_vazio(self):
        self.assertEqual(ler_json(self._path("nada.json")), {})


class TestTimestamp(unittest.TestCase):
    def test_formato(self):
        ts = gerar_timestamp_arquivo()
        self.assertEqual(len(ts), 15)
        self.assertEqual(ts[8], "_")
    def test_chars(self):
        ts = gerar_timestamp_arquivo()
        self.assertTrue(all(c.isdigit() or c == "_" for c in ts))


if __name__ == "__main__":
    unittest.main()
