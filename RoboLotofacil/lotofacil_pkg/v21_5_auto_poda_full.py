"""
lotofacil_pkg/v21_5_auto_poda_full.py
---------------------------------------
V21.5-FULL — Auto-Poda com 4 Estados Reais.

Expande a V20.2 (3 estados: ATIVO/OBSERVACAO/SUSPENSO) para um ciclo
completo de 4 estados com transições graduais e recuperação automática:

  ATIVO       — modelo contribui com peso integral
  OBSERVAÇÃO  — modelo contribui com 70% do peso (1 rodada abaixo do limiar)
  QUARENTENA  — modelo contribui com 30% do peso (2+ rodadas abaixo do limiar)
  SUSPENSO    — modelo contribui com 10% do peso (nunca zerado)

Recuperação automática:
  SUSPENSO    → QUARENTENA  (se desempenho recente melhora)
  QUARENTENA  → OBSERVAÇÃO  (se sustenta melhora por 2 rodadas)
  OBSERVAÇÃO  → ATIVO       (se sustenta melhora por 2 rodadas)

Integração com ELO:
  O estado também leva em conta o ELO do modelo, não só a média de acertos.

Funções exportadas:
  avaliar_estados_modelos   — avalia e atualiza estados de todos os modelos
  fator_peso_por_estado     — retorna o fator multiplicativo pelo estado atual
  get_estados_modelos       — retorna {nome: estado_dict} atual
  relatorio_poda_full       — relatório para o dashboard
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev

from .config import PASTA_DADOS

# ── Estados e fatores ────────────────────────────────────────────────────────
ESTADO_ATIVO      = "ATIVO"
ESTADO_OBSERVACAO = "OBSERVAÇÃO"
ESTADO_QUARENTENA = "QUARENTENA"
ESTADO_SUSPENSO   = "SUSPENSO"

FATORES_ESTADO = {
    ESTADO_ATIVO:      1.00,
    ESTADO_OBSERVACAO: 0.70,
    ESTADO_QUARENTENA: 0.30,
    ESTADO_SUSPENSO:   0.10,
}

# Limiares RELATIVOS à média do grupo (dos 7 modelos) no mesmo passo do
# backtest — não a um valor absoluto fixo.
#
# Até 2026-07-19 os limiares eram absolutos (observação<9.10, suspenso<8.90,
# recuperação>=9.20) numa escala onde "9 = aleatório" (o próprio comentário
# original já admitia isso). Como a média real de QUALQUER modelo em
# Lotofácil gira em torno de 9.0 (empatada com o acaso — confirmado por
# Calibrar IA vs. Aleatório), quase todo passo de backtest ficava abaixo de
# 9.10 e quase nunca acima de 9.20: o contador "abaixo" subia em praticamente
# todo passo e o "acima" quase nunca compensava, então TODO modelo descia
# ATIVO→OBSERVAÇÃO→QUARENTENA→SUSPENSO com passos suficientes e ficava
# preso lá (recuperação nunca disparava). O sistema não estava avaliando
# desempenho relativo entre modelos — estava avaliando "supera o acaso de
# forma absoluta", coisa que nenhum modelo consegue de forma sustentada
# neste domínio. Corrigido comparando cada modelo à média do PRÓPRIO GRUPO
# naquele passo — só modelos consistentemente piores que os outros 6
# degradam; só os consistentemente melhores recuperam (ver 2026-07-21 no
# ARQUITETURA.md).
DELTA_OBSERVACAO  = -0.05   # abaixo da média do grupo → conta como "abaixo"
DELTA_SUSPENSO    = -0.15   # abaixo da média do grupo por margem maior → pode suspender
DELTA_RECUPERACAO = 0.05    # acima da média do grupo → conta como "acima"/recuperação

# Rodadas consecutivas necessárias para degradar / recuperar.
#
# Até 2026-08-09 eram 2 -- achado do usuário (log de "Eventos" mostrando
# os 7 modelos trocando de estado dezenas de vezes em poucos segundos,
# durante um Backtest/BT Automático processando muitos passos rápido):
# como nenhum modelo tem vantagem real sobre os outros neste domínio
# (todos giram em torno da mesma média, diferença é ruído -- ver
# comentário de DELTA_OBSERVACAO acima), o delta "modelo vs. média do
# grupo" a cada passo é essencialmente ruído oscilando em torno de zero.
# Com só 2 rodadas seguidas na mesma direção pra transicionar, esse ruído
# already produz falsas transições com frequência alta o suficiente pra
# tornar o estado final mais reflexo de "onde o ruído parou" do que de
# desempenho persistente real. Subir pra 3 reduz a taxa de transições
# espúrias por ruído (a probabilidade de 3 rodadas seguidas na mesma
# direção só por acaso é menor que a de 2), sem exigir tantas rodadas que
# a recuperação real fique impraticável.
RODADAS_DEGRADAR   = 3
RODADAS_RECUPERAR  = 3

_ARQ_ESTADOS = Path(PASTA_DADOS) / "estados_modelos_v21.json"
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Persistência ─────────────────────────────────────────────────────────────

def _carregar_estados() -> dict:
    """
    Estrutura interna:
    {
      "estatistico": {
        "estado": "ATIVO",
        "rodadas_abaixo": 0,
        "rodadas_acima":  0,
        "historico": [9.2, 9.1, 9.3],   # últimas 30 médias
        "atualizado_em": "..."
      }, ...
    }
    """
    with _LOCK:
        if _ARQ_ESTADOS.exists():
            try:
                return json.loads(_ARQ_ESTADOS.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def _salvar_estados(estados: dict) -> None:
    with _LOCK:
        _ARQ_ESTADOS.parent.mkdir(parents=True, exist_ok=True)
        _ARQ_ESTADOS.write_text(
            json.dumps(estados, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def _estado_inicial() -> dict:
    return {
        "estado":          ESTADO_ATIVO,
        "rodadas_abaixo":  0,
        "rodadas_acima":   0,
        "historico":       [],
        "atualizado_em":   _now(),
    }


# ── Lógica de transição ───────────────────────────────────────────────────────

def _transicao(info: dict, media_recente: float, media_grupo: float, elo: float | None = None) -> dict:
    """
    Aplica a lógica de transição entre estados para UM modelo.
    Retorna o info atualizado.

    `media_grupo` é a média dos 7 modelos NESSE MESMO passo — a avaliação
    é sempre relativa ao grupo, não a um valor absoluto (ver comentário de
    DELTA_OBSERVACAO acima).
    """
    estado_atual = info.get("estado", ESTADO_ATIVO)
    rodadas_abaixo = info.get("rodadas_abaixo", 0)
    rodadas_acima  = info.get("rodadas_acima",  0)

    # Histórico acumulado (últimas 30 médias)
    hist = info.get("historico", [])
    hist.append(round(media_recente, 4))
    hist = hist[-30:]

    # Ajuste ELO: se ELO muito abaixo da média (<1350), contabiliza como "abaixo"
    penalidade_elo = elo is not None and elo < 1350

    delta = media_recente - media_grupo

    # ── Avalia tendência (relativa ao grupo) ────────────────────────────────
    if delta < DELTA_OBSERVACAO or penalidade_elo:
        rodadas_abaixo += 1
        rodadas_acima   = 0
    elif delta >= DELTA_RECUPERACAO:
        rodadas_acima  += 1
        rodadas_abaixo  = 0
    else:
        # Zona neutra: não muda contadores
        pass

    # ── Transições de degradação ────────────────────────────────────────────
    novo_estado = estado_atual
    if estado_atual == ESTADO_ATIVO:
        if rodadas_abaixo >= RODADAS_DEGRADAR:
            novo_estado = ESTADO_OBSERVACAO
    elif estado_atual == ESTADO_OBSERVACAO:
        if rodadas_abaixo >= RODADAS_DEGRADAR + 1:
            novo_estado = ESTADO_QUARENTENA
        elif rodadas_acima >= RODADAS_RECUPERAR:
            novo_estado = ESTADO_ATIVO
            rodadas_acima = 0
    elif estado_atual == ESTADO_QUARENTENA:
        if delta < DELTA_SUSPENSO and rodadas_abaixo >= RODADAS_DEGRADAR + 2:
            novo_estado = ESTADO_SUSPENSO
        elif rodadas_acima >= RODADAS_RECUPERAR:
            novo_estado = ESTADO_OBSERVACAO
            rodadas_acima = 0
    elif estado_atual == ESTADO_SUSPENSO:
        if rodadas_acima >= RODADAS_RECUPERAR:
            novo_estado = ESTADO_QUARENTENA
            rodadas_acima = 0

    return {
        "estado":          novo_estado,
        "rodadas_abaixo":  min(rodadas_abaixo, 10),
        "rodadas_acima":   min(rodadas_acima,  10),
        "historico":       hist,
        "media_historico": round(mean(hist), 4) if hist else 0.0,
        "tendencia":       "melhora" if rodadas_acima > 0 else (
                           "piora"   if rodadas_abaixo > 0 else "estavel"),
        "atualizado_em":   _now(),
        "houve_transicao": novo_estado != estado_atual,
        "estado_anterior": estado_atual if novo_estado != estado_atual else None,
    }


# ── Funções públicas ──────────────────────────────────────────────────────────

def avaliar_estados_modelos(
    acertos_por_modelo: dict[str, float],
    elos: dict | None = None,
    concurso: int | None = None,
) -> dict:
    """
    Avalia e atualiza o estado de cada modelo após um passo do backtest.

    Args:
        acertos_por_modelo: {nome: media_acertos_neste_passo}
        elos: {nome: elo_atual} — opcional, melhora precisão da poda
        concurso: número do concurso para rastreabilidade

    Returns:
        {nome: info_estado_atualizado}
    """
    estados = _carregar_estados()

    # Avaliação sempre relativa à média do PRÓPRIO GRUPO nesse passo (ver
    # comentário de DELTA_OBSERVACAO) — não a um valor absoluto fixo.
    media_grupo = mean(acertos_por_modelo.values()) if acertos_por_modelo else 0.0

    resultado = {}
    for nome, media in acertos_por_modelo.items():
        info = estados.get(nome, _estado_inicial())
        elo = (elos or {}).get(nome)
        info_novo = _transicao(info, media, media_grupo, elo=elo)
        info_novo["nome"] = nome
        info_novo["media_recente"] = round(media, 4)
        info_novo["fator_peso"] = FATORES_ESTADO[info_novo["estado"]]
        estados[nome] = info_novo
        resultado[nome] = info_novo

        # Espelha transições no SQLite
        if info_novo.get("houve_transicao"):
            try:
                from .v21_0_sqlite import get_db
                conn = get_db()
                with conn:
                    conn.execute(
                        "INSERT INTO historico_eventos (evento, model_id, payload, criado_em)"
                        " VALUES (?,?,?,?)",
                        (
                            f"transicao:{info_novo['estado_anterior']}→{info_novo['estado']}",
                            nome,
                            json.dumps({
                                "estado_anterior": info_novo["estado_anterior"],
                                "estado_novo":     info_novo["estado"],
                                "media":           media,
                                "elo":             elo,
                                "concurso":        concurso,
                            }),
                            _now(),
                        )
                    )
            except Exception:
                pass

    _salvar_estados(estados)
    return resultado


def fator_peso_por_estado(nome: str, estados: dict | None = None) -> float:
    """
    Retorna o fator multiplicativo para o peso base de um modelo.
    ATIVO=1.0, OBSERVAÇÃO=0.7, QUARENTENA=0.3, SUSPENSO=0.1
    """
    if estados is None:
        estados = _carregar_estados()
    info = estados.get(nome, _estado_inicial())
    return FATORES_ESTADO.get(info.get("estado", ESTADO_ATIVO), 1.0)


def get_estados_modelos() -> dict:
    """Retorna o dict completo de estados de todos os modelos."""
    return _carregar_estados()


def fatores_poda_todos(elos: dict | None = None) -> dict:
    """
    Retorna {nome: fator_combinado} = fator_estado × fator_elo.
    Pronto para multiplicar diretamente nos pesos do ensemble.
    """
    estados = _carregar_estados()
    resultado = {}
    for nome, info in estados.items():
        fator_est = FATORES_ESTADO.get(info.get("estado", ESTADO_ATIVO), 1.0)
        # ELO complementa: se não disponível, usa 1.0
        if elos and nome in elos:
            from .v21_5_meta_competitivo import fator_elo
            fator_e = fator_elo(nome, elos)
        else:
            fator_e = 1.0
        # Combina: 60% estado, 40% ELO
        resultado[nome] = round(0.60 * fator_est + 0.40 * fator_e, 4)
    return resultado


def relatorio_poda_full() -> dict:
    """Relatório completo dos estados de poda para o dashboard."""
    estados = _carregar_estados()
    linhas = []
    contagem = {ESTADO_ATIVO: 0, ESTADO_OBSERVACAO: 0,
                ESTADO_QUARENTENA: 0, ESTADO_SUSPENSO: 0}

    for nome, info in sorted(estados.items(), key=lambda x: x[0]):
        est = info.get("estado", ESTADO_ATIVO)
        contagem[est] = contagem.get(est, 0) + 1
        linhas.append({
            "nome":            nome,
            "estado":          est,
            "fator_peso":      FATORES_ESTADO.get(est, 1.0),
            "media_historico": info.get("media_historico", 0.0),
            "tendencia":       info.get("tendencia", "estavel"),
            "rodadas_abaixo":  info.get("rodadas_abaixo", 0),
            "rodadas_acima":   info.get("rodadas_acima",  0),
            "historico_tam":   len(info.get("historico", [])),
        })

    return {
        "modelos":    linhas,
        "contagem":   contagem,
        "total":      len(linhas),
        # Deltas relativos à média do grupo no mesmo passo (não valores
        # absolutos — ver comentário de DELTA_OBSERVACAO). Não existe um
        # "delta_quarentena" próprio: QUARENTENA é alcançada por rodadas
        # acumuladas abaixo do delta de observação, não por um limiar extra.
        "limiares": {
            "observacao":  DELTA_OBSERVACAO,
            "suspenso":    DELTA_SUSPENSO,
            "recuperacao": DELTA_RECUPERACAO,
        },
        "fatores": FATORES_ESTADO,
        "versao":  "V21.5-FULL",
    }
