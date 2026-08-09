"""
limpar_registros_impossiveis.py
---------------------------------
Remove do Banco Histórico de Desempenho (dados/lotofacil_desempenho_historico.json)
registros matematicamente impossíveis, causados pelo bug corrigido em
2026-08-08 (ver ARQUITETURA.md): quando o campo "Dezenas por jogo" estava
configurado com valor != 15 no momento do registro,
`registrar_desempenho_historico_robo()` descartava silenciosamente TODOS
os jogos do pacote e registrava `melhor_acerto=0` / `media_acertos=0.0`
como se fosse um resultado real.

Critério de detecção (conservador, sempre correto): a Lotofácil sempre
sorteia 15 dezenas de um total de 25 -- então QUALQUER jogo válido, do
menor tamanho possível (15 dezenas) em diante, acerta NO MÍNIMO
`15 - (25 - 15) = 5` pontos, pelo princípio da casa dos pombos (só
existem 10 dezenas "erradas" no total, um jogo de 15 não consegue
evitar todas). Um registro com `melhor_acerto < 5` é logicamente
impossível de ter sido um resultado real, não importa a configuração
usada -- só pode ser esse bug.

Uso:
    python limpar_registros_impossiveis.py           # mostra o que seria removido (dry-run)
    python limpar_registros_impossiveis.py --aplicar  # cria backup e remove de fato

Sempre cria um backup do arquivo original antes de qualquer alteração
(dados/lotofacil_desempenho_historico_backup_<timestamp>.json).
"""
import os
import sys
import json
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lotofacil_pkg.config import ARQUIVO_DESEMPENHO_HISTORICO
from lotofacil_pkg.backtest import carregar_banco_desempenho, salvar_banco_desempenho

MINIMO_MATEMATICO_POSSIVEL = 5  # ver docstring acima


def encontrar_registros_impossiveis(banco: dict) -> list[int]:
    """Retorna os índices (na lista banco['registros']) dos registros impossíveis."""
    indices = []
    for i, r in enumerate(banco.get("registros", [])):
        melhor = r.get("melhor_acerto")
        if melhor is not None and melhor < MINIMO_MATEMATICO_POSSIVEL:
            indices.append(i)
    return indices


def main() -> None:
    aplicar = "--aplicar" in sys.argv

    if not os.path.exists(ARQUIVO_DESEMPENHO_HISTORICO):
        print(f"Arquivo não encontrado: {ARQUIVO_DESEMPENHO_HISTORICO}")
        print("Nada para limpar.")
        return

    banco = carregar_banco_desempenho(ARQUIVO_DESEMPENHO_HISTORICO)
    registros = banco.get("registros", [])
    indices_ruins = encontrar_registros_impossiveis(banco)

    print(f"Arquivo: {ARQUIVO_DESEMPENHO_HISTORICO}")
    print(f"Registros totais: {len(registros)}")
    print(f"Registros impossíveis encontrados (melhor_acerto < {MINIMO_MATEMATICO_POSSIVEL}): {len(indices_ruins)}")

    if not indices_ruins:
        print("Nada para remover -- o arquivo já está limpo.")
        return

    print("\nRegistros que serão removidos:")
    for i in indices_ruins:
        r = registros[i]
        print(
            f"  - data={r.get('data_registro')} | concurso={r.get('concurso')} | "
            f"origem={r.get('origem')} | melhor_acerto={r.get('melhor_acerto')} | "
            f"media_acertos={r.get('media_acertos')}"
        )

    if not aplicar:
        print("\nModo dry-run (nada foi alterado). Rode com --aplicar para remover de verdade.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_backup = ARQUIVO_DESEMPENHO_HISTORICO.replace(".json", f"_backup_{timestamp}.json")
    shutil.copy2(ARQUIVO_DESEMPENHO_HISTORICO, caminho_backup)
    print(f"\nBackup criado em: {caminho_backup}")

    indices_ruins_set = set(indices_ruins)
    banco["registros"] = [r for i, r in enumerate(registros) if i not in indices_ruins_set]
    salvar_banco_desempenho(banco, ARQUIVO_DESEMPENHO_HISTORICO)
    print(f"Removidos {len(indices_ruins)} registro(s). Registros restantes: {len(banco['registros'])}.")


if __name__ == "__main__":
    main()
