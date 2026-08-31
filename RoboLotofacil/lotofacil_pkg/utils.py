"""
lotofacil_pkg/utils.py
----------------------
Funções utilitárias puras: matemática, strings, I/O JSON, seeds.
Única dependência interna: `config` (para ler/gravar a seed global).
"""
import os
import json
import math
import random
import threading
from datetime import datetime
from statistics import mean

from . import config as _config_module
from .config import NUMEROS, _PASTAS_APP


# ── Seed ──────────────────────────────────────────────────────────────────────

_SEED_NAO_INFORMADA = object()


def seed_global(seed=_SEED_NAO_INFORMADA) -> None:
    """
    Inicializa semente do gerador aleatório. None = entropia do sistema.

    Sem argumento, reaplica a seed atualmente configurada em
    `config.SEED` (lida em tempo real, não no momento do import -- um
    default `seed=SEED` aqui ficaria congelado em `None` para sempre,
    a mesma classe de bug já corrigida com TAMANHO_JOGO/TAMANHO_SORTEIO).

    Também grava em `config.SEED`: é esse atributo do módulo (não o valor
    importado aqui) que `backtest.py:_seed_do_passo` lê para derivar a seed
    de cada passo de backtest/walk-forward/calibração em paralelo. Sem essa
    gravação, "Seed fixo" só afetava a geração de jogos avulsa (`random.seed`
    local) e as ferramentas de validação continuavam usando entropia real,
    mesmo com o checkbox marcado.
    """
    if seed is _SEED_NAO_INFORMADA:
        seed = _config_module.SEED
    _config_module.SEED = seed
    if seed is not None:
        random.seed(seed)


# ── RNG thread-local ──────────────────────────────────────────────────────────
# O módulo `random` global é uma única instância compartilhada. Quando o
# backtest roda passos em paralelo (ThreadPoolExecutor), múltiplas threads
# consomem esse mesmo fluxo pseudo-aleatório ao mesmo tempo: a ordem de
# consumo passa a depender do escalonamento do SO, e os resultados deixam
# de ser reprodutíveis mesmo com uma seed fixa. `definir_rng_thread` dá a
# cada thread seu próprio gerador isolado; `rng()` o retorna (ou cai para o
# módulo `random` global fora de um contexto paralelo).
_rng_local = threading.local()


def definir_rng_thread(seed: int | None) -> None:
    """Define um gerador aleatório isolado para a thread atual."""
    _rng_local.instancia = random.Random(seed)


def limpar_rng_thread() -> None:
    """Remove o gerador isolado da thread atual, voltando ao fallback global."""
    if hasattr(_rng_local, "instancia"):
        del _rng_local.instancia


def rng():
    """Retorna o gerador aleatório da thread atual, ou `random` global."""
    return getattr(_rng_local, "instancia", random)


# ── Jogo helpers ──────────────────────────────────────────────────────────────

def formatar_jogo(jogo) -> str:
    """Retorna 'XX YY ZZ …' com os números do jogo ordenados e zero-padded."""
    return " ".join(f"{n:02d}" for n in sorted(jogo))


def contar_pares(jogo) -> int:
    """Conta quantas dezenas do jogo são pares."""
    return sum(1 for n in jogo if n % 2 == 0)


def soma_jogo(jogo) -> int:
    """Soma todas as dezenas do jogo."""
    return sum(jogo)


def intersecao(a, b) -> int:
    """Retorna a quantidade de dezenas em comum entre dois jogos."""
    return len(set(a) & set(b))


def distancia_jogos(a, b) -> int:
    """Retorna a distância simétrica (diferença) entre dois jogos."""
    return len(set(a) ^ set(b))


def limitar(valor: float, minimo: float, maximo: float) -> float:
    """Clipa `valor` no intervalo [minimo, maximo]."""
    return max(minimo, min(maximo, valor))


# ── Data / string ─────────────────────────────────────────────────────────────

def parse_data_br(valor) -> str:
    """Converte datas em vários formatos para o padrão brasileiro DD/MM/YYYY."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    if not texto:
        return ""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto[:10], fmt).strftime("%d/%m/%Y")
        except Exception:
            pass
    return texto


def gerar_timestamp_arquivo() -> str:
    """Retorna timestamp formatado para nomes de arquivo."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ── JSON helpers ──────────────────────────────────────────────────────────────

def ler_json(caminho: str, default=None):
    """Lê JSON com fallback seguro para arquivo ausente ou corrompido.

    Faz backup do arquivo (.corrompido) em QUALQUER falha de leitura, não
    só JSONDecodeError -- um UnicodeDecodeError (ex.: write truncado no
    meio de um caractere multibyte, o cenário que salvar_json() agora
    evita) ou um PermissionError transitório (outra thread escrevendo o
    mesmo arquivo) caindo direto no `default` sem backup apagava a memória
    de aprendizado acumulada (até 500 registros) sem deixar rastro.
    """
    default = default if default is not None else {}
    if not os.path.exists(caminho):
        return default
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        try:
            import shutil
            shutil.copy2(caminho, caminho + ".corrompido")
        except Exception:
            pass
        return default


def salvar_json(caminho: str, obj) -> None:
    """Persiste objeto como JSON garantindo que a pasta de destino exista.

    Escreve num arquivo temporário e só então troca pelo definitivo via
    os.replace() (atômico no SO) -- gravar direto em modo "w" trunca o
    arquivo antes de escrever; se o processo for interrompido no meio
    (queda, exceção em outra thread) ou duas threads gravarem o mesmo
    arquivo ao mesmo tempo (ex.: aprendizado contínuo + registro manual de
    resultado, ambos usando ARQUIVO_APRENDIZADO), o JSON ficava truncado/
    corrompido -- e ler_json() então descartava a memória acumulada sem
    aviso. os.replace() garante que quem lê o arquivo sempre vê a versão
    antiga completa ou a nova completa, nunca um meio-termo.
    """
    pasta = os.path.dirname(os.path.abspath(caminho))
    os.makedirs(pasta, exist_ok=True)
    caminho_tmp = f"{caminho}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(caminho_tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(caminho_tmp, caminho)
    finally:
        if os.path.exists(caminho_tmp):
            try:
                os.remove(caminho_tmp)
            except Exception:
                pass


def tornar_json_seguro(obj):
    """Converte estruturas internas (tuplas, sets, numpy) para tipos JSON-safe."""
    if isinstance(obj, dict):
        return {str(k): tornar_json_seguro(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [tornar_json_seguro(v) for v in obj]
    try:
        if hasattr(obj, "item") and callable(obj.item):
            return obj.item()
    except Exception:
        pass
    return obj


# ── Pastas ────────────────────────────────────────────────────────────────────

def garantir_estrutura_pastas() -> None:
    """Cria todas as pastas necessárias para o robô (idempotente)."""
    for pasta in _PASTAS_APP:
        os.makedirs(pasta, exist_ok=True)


def garantir_pasta_escrita(caminho_saida: str) -> None:
    """Lança PermissionError se a pasta de destino não tiver permissão de escrita."""
    garantir_estrutura_pastas()
    pasta = os.path.dirname(os.path.abspath(caminho_saida)) or os.getcwd()
    if not os.access(pasta, os.W_OK):
        raise PermissionError(f"Sem permissão de escrita na pasta: {pasta}")


def limpar_cache_estrutura() -> None:
    """Libera o cache LRU de estrutura de jogos."""
    try:
        from .genetico import analisar_estrutura_jogo_cached
        analisar_estrutura_jogo_cached.cache_clear()
    except Exception:
        pass


# ── Scores helper ─────────────────────────────────────────────────────────────

def normalizar_scores(scores: dict, piso: float = 0.001) -> dict:
    """Normaliza {dezena: score} para soma=1 com piso mínimo de segurança."""
    vals = {n: max(piso, float(scores.get(n, 0.0))) for n in NUMEROS}
    total = sum(vals.values()) or 1.0
    inv = 1.0 / total
    return {n: vals[n] * inv for n in NUMEROS}
