"""
lotofacil_pkg/tests/test_persistencia.py
-------------------------------------------
persistencia.py mistura I/O real (download da API CAIXA, escrita em
PASTA_DADOS/PASTA_BACKUP -- caminhos fixos de produção, sem isolamento
via ROBOLOTOFACIL_DADOS_DIR) com algumas funções puras. Testar as
funções de I/O aqui escreveria arquivos de verdade na pasta de produção
do usuário (não isolado) -- fora de escopo por ora (ver ARQUITETURA.md,
2026-08-08, "quality pass"). Cobre só as funções puras (sem I/O de
arquivo/rede), que já dão valor real e são seguras de testar.
"""
import os
import sys
import unittest
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

from lotofacil_pkg.persistencia import resposta_parece_html, normalizar_df_resultados


class _RespostaFake:
    def __init__(self, content_type="application/json", texto=""):
        self.headers = {"Content-Type": content_type}
        self.text = texto


class TestRespostaPareceHtml(unittest.TestCase):
    def test_json_normal_nao_e_html(self):
        self.assertFalse(resposta_parece_html(_RespostaFake("application/json", '{"numero": 3700}')))

    def test_content_type_html_e_detectado(self):
        self.assertTrue(resposta_parece_html(_RespostaFake("text/html; charset=utf-8", "<html>...</html>")))

    def test_doctype_no_corpo_e_detectado_mesmo_com_content_type_json(self):
        self.assertTrue(resposta_parece_html(_RespostaFake("application/json", "<!DOCTYPE html><html>erro</html>")))

    def test_tag_html_no_corpo_e_detectada(self):
        self.assertTrue(resposta_parece_html(_RespostaFake("text/plain", "<html><body>Erro 503</body></html>")))

    def test_texto_vazio_nao_quebra(self):
        self.assertFalse(resposta_parece_html(_RespostaFake("application/json", "")))


class TestNormalizarDfResultados(unittest.TestCase):
    def _df_valido(self, n=3):
        linhas = []
        for i in range(n):
            linha = {"concurso": 3700 + i, "data": f"0{(i % 9) + 1}/01/2026"}
            for d in range(1, 16):
                linha[f"d{d}"] = d
            linhas.append(linha)
        return pd.DataFrame(linhas)

    def test_dataframe_vazio_retorna_vazio_sem_erro(self):
        vazio = pd.DataFrame(columns=["concurso", "data"] + [f"d{i}" for i in range(1, 16)])
        r = normalizar_df_resultados(vazio)
        self.assertTrue(r.empty)

    def test_ordena_por_concurso_e_remove_duplicatas(self):
        df = self._df_valido(3)
        df_embaralhado = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # duplica a primeira linha
        df_embaralhado = df_embaralhado.sample(frac=1, random_state=1).reset_index(drop=True)  # embaralha
        r = normalizar_df_resultados(df_embaralhado)
        self.assertEqual(list(r["concurso"]), sorted(df["concurso"].tolist()))
        self.assertEqual(len(r), 3)  # duplicata removida

    def test_linha_com_concurso_invalido_e_descartada(self):
        df = self._df_valido(2)
        df.loc[len(df)] = {"concurso": "não é número", "data": "01/01/2026", **{f"d{i}": i for i in range(1, 16)}}
        r = normalizar_df_resultados(df)
        self.assertEqual(len(r), 2)

    def test_colunas_de_dezena_viram_inteiros(self):
        df = self._df_valido(1)
        r = normalizar_df_resultados(df)
        for i in range(1, 16):
            # numpy.int64 (não int puro) -- mas precisa converter sem perda/erro.
            self.assertEqual(int(r.iloc[0][f"d{i}"]), i)


if __name__ == "__main__":
    unittest.main(verbosity=2)
