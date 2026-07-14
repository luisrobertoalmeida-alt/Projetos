"""
lotofacil_pkg/auditoria_cientifica.py — MÓDULO EXPERIMENTAL (V22.1)
----------------------------------------------------------------------
Auditoria científica contínua: um único ponto de entrada para produzir o
pacote estatístico completo de qualquer experimento (validação de config,
comparação G/P, teste de feature nova) — sempre com estatística pareada,
TOST quando a pergunta é de equivalência, correção para múltiplas
comparações quando há mais de um teste na mesma rodada, e poder
estatístico sempre reportado.

Por que isto existe: a validação G×P de 14/07/2026 só ficou correta
depois de revisão externa apontar dois erros — dados pareados tratados
como amostras independentes, e "não rejeitamos H0" tratado como
equivalência comprovada (ver VALIDACAO_MAPA_GP_2026-07-14.md). O
objetivo deste módulo é tornar o caminho certo mais fácil de seguir do
que reimplementar a análise na mão em cada script novo. Optamos por uma
função de uso explícito, não uma classe base/decorator que os scripts
de validação "herdariam" — ver ARQUITETURA.md para a justificativa
dessa escolha.

REGRA INEGOCIÁVEL: `dados_a`/`dados_b` devem vir de concursos REAIS do
histórico (dados/lotofacil_resultados_reais.csv), nunca sintéticos, para
qualquer conclusão de mérito sobre desempenho. Sorteios sintéticos são
aceitáveis só para testar mecânica (ex.: "execução paralela dá o mesmo
resultado que sequencial?"). `auditoria_experimento` exige
`metadados["fonte_dados"] == "real"` e emite aviso (não bloqueia — a
função não tem como verificar de onde os números realmente vieram) caso
contrário.

Uso típico (uma rodada com múltiplas comparações contra a mesma referência):

    aud_g88 = auditoria_experimento(
        "G88/P79 vs G35/P70", dados_g88, dados_g35,
        nome_a="G88/P79", nome_b="G35/P70",
        metadados={"n_concursos": 300, "range_concursos": "3410-3709",
                   "fonte_dados": "real", "walkforward_sem_vazamento": True},
    )
    aud_g16 = auditoria_experimento("G16/P40 vs G35/P70", dados_g16, dados_g35, ...)

    relatorio = consolidar_rodada_experimentos(
        "Mapa G x P — 2026-08-01", [aud_g88, aud_g16],
        metodo_correcao="holm", salvar_em="dados/auditoria_mapa_gp_20260801",
    )
    print(relatorio["comparacoes"][0]["veredito_final"])
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .v20_6_bootstrap import (
    cohen_d_pareado,
    teste_significancia_pareado,
    bootstrap_pareado,
    tost_equivalencia,
    poder_observado_pareado,
)

METADADOS_OBRIGATORIOS = ("n_concursos", "range_concursos", "fonte_dados", "walkforward_sem_vazamento")


def auditoria_experimento(
    nome: str,
    dados_a: list[dict],
    dados_b: list[dict],
    nome_a: str = "A",
    nome_b: str = "B",
    metadados: dict[str, Any] | None = None,
    margem_equivalencia: float = 0.3,
    n_reamostras: int = 3000,
    seed: int | None = 42,
) -> dict[str, Any]:
    """
    Pacote estatístico PAREADO completo para uma comparação A vs. B.

    Args:
        nome: identificação do experimento (aparece no relatório).
        dados_a, dados_b: listas de dicts com 'acertos', na MESMA ordem —
            dados_a[i] e dados_b[i] precisam se referir ao mesmo sorteio
            real/passo (mesmo índice), não a unidades diferentes.
        nome_a, nome_b: rótulos legíveis para o relatório.
        metadados: recomenda-se incluir pelo menos "n_concursos",
            "range_concursos" (ex.: "3410-3709"), "fonte_dados" ("real"
            ou "sintetico"), "walkforward_sem_vazamento" (bool). Ausência
            gera avisos, não bloqueia a execução.
        margem_equivalencia: margem do TOST, definida a priori.
        n_reamostras: reamostras para os testes de permutação/bootstrap.
        seed: semente para reprodutibilidade dos testes.

    Returns:
        Dict com cohen_d_pareado, p_value_bruto (sign-flip, ainda SEM
        correção para múltiplas comparações — ver
        consolidar_rodada_experimentos), delta_observado, ic_95,
        tost_equivalente, poder_observado, avisos e metadados.
    """
    metadados = dict(metadados or {})
    avisos: list[str] = []

    faltando = [k for k in METADADOS_OBRIGATORIOS if k not in metadados]
    if faltando:
        avisos.append(
            f"⚠️ metadados incompletos, faltando: {faltando}. Preencha para que o "
            f"relatório seja auditável (de onde vieram os dados, quantos concursos, "
            f"se houve vazamento)."
        )
    if metadados.get("fonte_dados") not in ("real",):
        avisos.append(
            "⚠️ metadados['fonte_dados'] não é 'real' — este experimento NÃO deve "
            "ser usado para conclusões de mérito sobre desempenho, apenas para "
            "testar mecânica (ex.: paralelo vs. sequencial dão o mesmo resultado?)."
        )
    if metadados.get("walkforward_sem_vazamento") is not True:
        avisos.append(
            "⚠️ metadados não confirma explicitamente 'walkforward_sem_vazamento': True "
            "— verifique se cada passo usou apenas histórico anterior ao sorteio testado."
        )

    cohen = cohen_d_pareado(dados_a, dados_b)
    sig = teste_significancia_pareado(dados_a, dados_b, n_reamostras=n_reamostras, seed=seed)
    ic = bootstrap_pareado(dados_a, dados_b, n_reamostras=n_reamostras, seed=seed)
    tost = tost_equivalencia(dados_a, dados_b, margem=margem_equivalencia, n_reamostras=n_reamostras, seed=seed)
    poder = poder_observado_pareado(dados_a, dados_b)

    if poder.get("aviso"):
        avisos.append(poder["aviso"])

    return {
        "nome": nome,
        "nome_a": nome_a,
        "nome_b": nome_b,
        "n": cohen["n"],
        "cohen_d_pareado": cohen["cohen_d_pareado"],
        "magnitude": cohen["magnitude"],
        "p_value_bruto": sig["p_value"],
        "delta_observado": ic["delta_observado"],
        "ic_95": ic["intervalos"].get("95%"),
        "tost_equivalente": tost["equivalente"],
        "tost_margem": margem_equivalencia,
        "tost_ic_90": tost["ic_90"],
        "poder_observado": poder["poder"],
        "metadados": metadados,
        "avisos": avisos,
    }


def corrigir_multiplas_comparacoes(
    p_values: list[float],
    metodo: str = "holm",
    alpha: float = 0.05,
) -> list[dict[str, Any]]:
    """
    Corrige uma lista de p-values (de comparações feitas na mesma rodada,
    ex.: 3 configurações testadas contra o mesmo baseline) para múltiplas
    comparações.

    Args:
        p_values: p-values brutos, na ordem em que serão retornados.
        metodo: "bonferroni" (simples, mais conservador) ou "holm"
            (step-down, menos conservador, controla a mesma FWER).
        alpha: nível de significância desejado após correção.

    Returns:
        Lista alinhada com `p_values`, cada item com p_original,
        p_ajustado e significativo_corrigido.
    """
    m = len(p_values)
    if m == 0:
        return []

    if metodo == "bonferroni":
        ajustados = [min(1.0, p * m) for p in p_values]
    elif metodo == "holm":
        ordem = sorted(range(m), key=lambda i: p_values[i])
        ajustados = [0.0] * m
        maior_ate_agora = 0.0
        for rank, idx in enumerate(ordem):
            fator = m - rank
            p_ajust = min(1.0, p_values[idx] * fator)
            # monotonia: cada p ajustado precisa ser >= o anterior na ordem (step-down)
            maior_ate_agora = max(maior_ate_agora, p_ajust)
            ajustados[idx] = maior_ate_agora
    else:
        raise ValueError(f"Método de correção desconhecido: {metodo!r}. Use 'bonferroni' ou 'holm'.")

    return [
        {
            "p_original": round(p_values[i], 4),
            "p_ajustado": round(ajustados[i], 4),
            "significativo_corrigido": ajustados[i] < alpha,
        }
        for i in range(m)
    ]


def consolidar_rodada_experimentos(
    nome_rodada: str,
    auditorias: list[dict[str, Any]],
    metodo_correcao: str = "holm",
    alpha: float = 0.05,
    salvar_em: str | None = None,
) -> dict[str, Any]:
    """
    Consolida uma rodada de auditorias (`auditoria_experimento`) numa
    conclusão final, aplicando correção para múltiplas comparações e
    decidindo um veredito por comparação:

      - "SUPERIOR": significativo após correção, TOST não confirma
        equivalência, e efeito >= "pequeno" (|d_z|>=0.2) na direção A>B.
      - "EQUIVALENTE": TOST confirma equivalência dentro da margem.
      - "INCONCLUSIVO": nem uma coisa nem outra — amostra insuficiente
        para concluir nessa escala (aumentar n, não forçar conclusão).

    Args:
        nome_rodada: identificação da rodada (aparece no relatório salvo).
        auditorias: lista de dicts retornados por auditoria_experimento().
        metodo_correcao: "bonferroni" ou "holm".
        alpha: nível de significância desejado.
        salvar_em: caminho base (sem extensão) para salvar `{salvar_em}.md`
            e `{salvar_em}.json`. Se None, não salva (só retorna o dict).

    Returns:
        Dict com nome_rodada, metodo_correcao, comparacoes (cada uma com
        o veredito_final) e avisos consolidados.
    """
    if not auditorias:
        return {"nome_rodada": nome_rodada, "comparacoes": [], "erro": "Nenhuma auditoria fornecida."}

    p_values = [a["p_value_bruto"] for a in auditorias]
    corrigidos = corrigir_multiplas_comparacoes(p_values, metodo=metodo_correcao, alpha=alpha)

    comparacoes = []
    avisos_consolidados: list[str] = []
    for auditoria, corr in zip(auditorias, corrigidos):
        if auditoria["tost_equivalente"]:
            veredito = "EQUIVALENTE"
        elif (
            corr["significativo_corrigido"]
            and abs(auditoria["cohen_d_pareado"]) >= 0.2
            and auditoria["delta_observado"] > 0
        ):
            veredito = "SUPERIOR"
        else:
            veredito = "INCONCLUSIVO"

        comparacoes.append({**auditoria, **corr, "veredito_final": veredito})
        avisos_consolidados.extend(auditoria.get("avisos", []))

    resultado = {
        "nome_rodada": nome_rodada,
        "metodo_correcao": metodo_correcao,
        "alpha": alpha,
        "n_comparacoes": len(auditorias),
        "comparacoes": comparacoes,
        "avisos": sorted(set(avisos_consolidados)),
        "gerado_em": datetime.now(timezone.utc).isoformat(),
    }

    if salvar_em:
        _salvar_relatorio(resultado, salvar_em)

    return resultado


def _gerar_markdown(resultado: dict[str, Any]) -> str:
    linhas = [
        f"# Auditoria Científica — {resultado['nome_rodada']}",
        "",
        f"Gerado em: {resultado['gerado_em']}",
        f"Correção para múltiplas comparações: {resultado['metodo_correcao']} "
        f"(α={resultado['alpha']}, {resultado['n_comparacoes']} comparações)",
        "",
    ]
    if resultado.get("avisos"):
        linhas.append("## ⚠️ Avisos")
        for a in resultado["avisos"]:
            linhas.append(f"- {a}")
        linhas.append("")

    linhas.append("## Comparações")
    linhas.append("")
    linhas.append(
        "| Comparação | n | d_z | p (bruto) | p (ajustado) | IC 95% | TOST equiv.? | Poder | Veredito |"
    )
    linhas.append("|---|---:|---:|---:|---:|---|---|---:|---|")
    for c in resultado["comparacoes"]:
        ic95 = c.get("ic_95") or {}
        linhas.append(
            f"| {c['nome']} | {c['n']} | {c['cohen_d_pareado']:.4f} | "
            f"{c['p_original']:.4f} | {c['p_ajustado']:.4f} | "
            f"[{ic95.get('inferior', '?')};{ic95.get('superior', '?')}] | "
            f"{'Sim' if c['tost_equivalente'] else 'Não'} | "
            f"{c['poder_observado']:.0%} | **{c['veredito_final']}** |"
        )
    linhas.append("")
    return "\n".join(linhas)


def _salvar_relatorio(resultado: dict[str, Any], caminho_base: str) -> None:
    """Salva o relatório em `{caminho_base}.json` (bruto) e `{caminho_base}.md` (legível)."""
    with open(f"{caminho_base}.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    with open(f"{caminho_base}.md", "w", encoding="utf-8") as f:
        f.write(_gerar_markdown(resultado))
