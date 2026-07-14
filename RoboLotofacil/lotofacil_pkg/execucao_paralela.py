"""
lotofacil_pkg/execucao_paralela.py — MÓDULO EXPERIMENTAL (V22.1)
--------------------------------------------------------------------
Execução paralela POR PROCESSOS (não threads) do walk-forward usado nos
scripts de validação standalone (validacao_gp.py, reanalise_pareada.py,
futuras rodadas de auditoria científica contínua).

Por que processos, não threads: o algoritmo genético (`genetico.py`) é
Python puro — threads concorrentes disputam o GIL e não dão paralelismo
real para esse tipo de trabalho. Isso foi comprovado empiricamente neste
projeto: rodar duas validações G×P como dois processos separados (dois
`nohup python3 validacao_gp.py ...`) deu paralelismo de verdade, mas o
`ThreadPoolExecutor` usado em `backtest.py` não acelera o algoritmo
genético em si (só corrigiu reprodutibilidade — ver
VALIDACAO_ESCALA_REAL_2026-07-14.md). Processos têm interpretador e GIL
próprios: paralelismo real, escalando com núcleos disponíveis.

REQUISITO NÃO-NEGOCIÁVEL: com a mesma seed_base, execução paralela
(`modo="processos"`) e sequencial (`modo="sequencial"`) devem produzir
resultado IDÊNTICO. Cada processo/passo semeia seu próprio `random`
global (`random.seed`) a partir de `seed_base` + índice do passo — mais
simples que o RNG thread-local de `utils.py` (aquilo resolve threads
concorrentes DENTRO do mesmo processo; aqui cada processo já nasce
isolado, com seu próprio `random`, então `random.seed()` simples basta).
Ver `test_execucao_paralela.py` para o teste de regressão obrigatório.

ESCOPO: uso restrito a scripts standalone de validação. NÃO usar a
partir da UI — a UI já usa ThreadPoolExecutor (adequado para uso
interativo; o ganho de paralelismo de processos não compensa a
complexidade de gerenciar um pool de processos a partir de callbacks
Tkinter).

LIMITAÇÃO DE PICKLING: `fn_gerar` precisa ser uma função de nível de
módulo (top-level) para `modo="processos"` — closures/funções locais
(como as usadas em ui.py e nos scripts antigos) não são serializáveis
entre processos. Use `gerar_apostas_padrao` (o padrão) ou defina sua
própria função no nível do módulo.
"""
from __future__ import annotations

import random
from concurrent.futures import ProcessPoolExecutor
from typing import Callable

# Estado por processo-worker, populado uma vez por processo via
# `initializer` -- evita serializar `concursos` (grande) a cada tarefa.
_ESTADO_WORKER: dict = {}


def gerar_apostas_padrao(hist: list[list[int]], geracoes: int, pop_size: int, qtd_jogos: int) -> list[list[int]]:
    """
    fn_gerar padrão: chama gerar_apostas() com janela_analise=len(hist).
    Definida no nível do módulo de propósito (precisa ser picklável).
    """
    from .apostas import gerar_apostas
    jogos, _, _ = gerar_apostas(
        hist, qtd_jogos=qtd_jogos, janela_analise=len(hist),
        geracoes=geracoes, pop_size=pop_size,
    )
    return jogos


def seed_do_passo(seed_base: int, i: int) -> int:
    """Deriva uma seed determinística por passo a partir de uma seed base e do índice do passo."""
    return (int(seed_base) * 1_000_003 + i) & 0xFFFFFFFF


def _inicializar_worker(concursos, fn_gerar, geracoes, pop_size, qtd_jogos) -> None:
    """Roda uma vez por processo-worker (ProcessPoolExecutor initializer)."""
    _ESTADO_WORKER["concursos"] = concursos
    _ESTADO_WORKER["fn_gerar"] = fn_gerar
    _ESTADO_WORKER["geracoes"] = geracoes
    _ESTADO_WORKER["pop_size"] = pop_size
    _ESTADO_WORKER["qtd_jogos"] = qtd_jogos


def _tarefa_passo(args: tuple[int, int]) -> dict:
    i, seed_base = args
    random.seed(seed_do_passo(seed_base, i))

    concursos = _ESTADO_WORKER["concursos"]
    fn_gerar = _ESTADO_WORKER["fn_gerar"]
    base = concursos[:i]
    real = concursos[i]

    jogos = fn_gerar(base, _ESTADO_WORKER["geracoes"], _ESTADO_WORKER["pop_size"], _ESTADO_WORKER["qtd_jogos"])
    real_set = set(real)
    acertos = [len(set(j) & real_set) for j in jogos]
    melhor = max(acertos) if acertos else 0
    media = sum(acertos) / len(acertos) if acertos else 0.0
    return {"concurso_idx": i + 1, "melhor_robo": melhor, "media_robo": media}


def _e_funcao_local(fn: Callable) -> bool:
    qualname = getattr(fn, "__qualname__", "")
    return "<locals>" in qualname


def rodar_walkforward(
    concursos: list[list[int]],
    indices: list[int],
    geracoes: int,
    pop_size: int,
    qtd_jogos: int,
    seed_base: int,
    fn_gerar: Callable = gerar_apostas_padrao,
    modo: str = "processos",
    n_workers: int | None = None,
) -> list[dict]:
    """
    Roda `fn_gerar` (por padrão, gerar_apostas()) sobre `indices` do
    histórico, walk-forward sem vazamento (base=concursos[:i],
    real=concursos[i]).

    Args:
        indices: índices (posições em `concursos`) a testar. O chamador
            garante que cada `i` tem histórico suficiente antes dele.
        seed_base: com a mesma seed_base, modo="processos" e
            modo="sequencial" retornam EXATAMENTE o mesmo resultado —
            ver test_execucao_paralela.py.
        fn_gerar: função(hist, geracoes, pop_size, qtd_jogos) -> jogos.
            Precisa ser definida no nível do módulo (não uma closure)
            para modo="processos" — ver LIMITAÇÃO DE PICKLING no
            docstring do módulo.
        modo: "processos" (ProcessPoolExecutor, paralelo de verdade) ou
            "sequencial" (for loop simples — usado no teste de
            regressão e útil para depuração, já que erros em processos
            filhos são mais difíceis de depurar).
        n_workers: processos simultâneos (padrão: os.cpu_count()).

    Returns:
        Lista de dicts {concurso_idx, melhor_robo, media_robo}, na
        mesma ordem de `indices`.
    """
    if modo not in ("processos", "sequencial"):
        raise ValueError(f"modo deve ser 'processos' ou 'sequencial' (recebido: {modo!r})")

    if modo == "processos" and _e_funcao_local(fn_gerar):
        raise ValueError(
            f"fn_gerar={fn_gerar!r} é uma função local (closure) — não é serializável "
            f"entre processos. Defina fn_gerar no nível do módulo (top-level) ou use "
            f"modo='sequencial'."
        )

    if modo == "sequencial":
        _inicializar_worker(concursos, fn_gerar, geracoes, pop_size, qtd_jogos)
        return [_tarefa_passo((i, seed_base)) for i in indices]

    tarefas = [(i, seed_base) for i in indices]
    with ProcessPoolExecutor(
        max_workers=n_workers,
        initializer=_inicializar_worker,
        initargs=(concursos, fn_gerar, geracoes, pop_size, qtd_jogos),
    ) as ex:
        return list(ex.map(_tarefa_passo, tarefas))
