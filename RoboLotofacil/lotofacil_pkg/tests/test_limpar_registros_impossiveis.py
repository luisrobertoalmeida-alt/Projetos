"""
lotofacil_pkg/tests/test_limpar_registros_impossiveis.py
-------------------------------------------------------------
Testa a lógica de detecção do script limpar_registros_impossiveis.py
(raiz do projeto) -- não roda o script inteiro (que mexe no arquivo
real de produção), só a função pura de detecção.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import tempfile as _tempfile
os.environ.setdefault("ROBOLOTOFACIL_DADOS_DIR", _tempfile.mkdtemp(prefix="robolotofacil_testes_"))

# raiz do projeto (onde está limpar_registros_impossiveis.py), não lotofacil_pkg/
_RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.abspath(_RAIZ))

from limpar_registros_impossiveis import encontrar_registros_impossiveis, MINIMO_MATEMATICO_POSSIVEL


class TestEncontrarRegistrosImpossiveis(unittest.TestCase):
    def test_identifica_melhor_acerto_zero_como_impossivel(self):
        banco = {"registros": [{"melhor_acerto": 0}, {"melhor_acerto": 11}]}
        self.assertEqual(encontrar_registros_impossiveis(banco), [0])

    def test_minimo_matematico_e_5(self):
        # Nenhum jogo válido de Lotofácil (15+ dezenas) pode acertar menos que 5.
        self.assertEqual(MINIMO_MATEMATICO_POSSIVEL, 5)

    def test_melhor_acerto_igual_ao_minimo_nao_e_removido(self):
        banco = {"registros": [{"melhor_acerto": MINIMO_MATEMATICO_POSSIVEL}]}
        self.assertEqual(encontrar_registros_impossiveis(banco), [])

    def test_melhor_acerto_abaixo_do_minimo_e_removido(self):
        banco = {"registros": [{"melhor_acerto": MINIMO_MATEMATICO_POSSIVEL - 1}]}
        self.assertEqual(encontrar_registros_impossiveis(banco), [0])

    def test_banco_vazio_nao_quebra(self):
        self.assertEqual(encontrar_registros_impossiveis({"registros": []}), [])

    def test_registro_sem_melhor_acerto_e_ignorado_sem_erro(self):
        banco = {"registros": [{"outra_chave": 1}]}
        self.assertEqual(encontrar_registros_impossiveis(banco), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
