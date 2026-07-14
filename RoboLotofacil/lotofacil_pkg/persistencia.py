"""
lotofacil_pkg/persistencia.py
------------------------------
I/O de dados: download da API CAIXA, leitura/escrita de CSV,
backup blindado e exportação Excel.
"""
import os
import time
import json
from datetime import datetime

import pandas as pd
import requests
from requests.adapters import HTTPAdapter

from .config import (
    API_BASE, HTTP_TIMEOUT, HTTP_MAX_RETRIES, HTTP_BACKOFF_FACTOR,
    USER_AGENT, MIN_HIST, PASTA_DADOS, PASTA_BACKUP, PASTA_EXPORT,
    ARQUIVO_CSV_PADRAO, ARQUIVO_CACHE, _PASTAS_APP,
)
from .utils import (
    parse_data_br, gerar_timestamp_arquivo, salvar_json, ler_json,
    garantir_estrutura_pastas, garantir_pasta_escrita,
)


def garantir_estrutura_pastas() -> None:
    """Cria todas as pastas necessárias para o robô (idempotente)."""
    for pasta in _PASTAS_APP:
        os.makedirs(pasta, exist_ok=True)


def limpar_cache_estrutura() -> None:
    """Libera o cache LRU de estrutura de jogos; útil ao trocar histórico ou iniciar novos testes."""
    try:
        from .genetico import analisar_estrutura_jogo_cached
        analisar_estrutura_jogo_cached.cache_clear()
    except Exception:
        pass


def gerar_timestamp_arquivo() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def criar_backup_do_arquivo(caminho_origem: str) -> str | None:
    if not os.path.exists(caminho_origem):
        return None
    import shutil
    nome = os.path.splitext(os.path.basename(caminho_origem))[0]
    destino = os.path.join(PASTA_BACKUP, f"{nome}_backup_{gerar_timestamp_arquivo()}.csv")
    shutil.copy2(caminho_origem, destino)
    return destino


def salvar_csv_blindado(df, caminho_saida: str) -> bool:
    garantir_estrutura_pastas()
    garantir_pasta_escrita(caminho_saida)

    nome_base = os.path.splitext(os.path.basename(caminho_saida))[0]
    caminho_tmp = os.path.join(PASTA_DADOS, f"{nome_base}_{gerar_timestamp_arquivo()}.tmp.csv")
    caminho_alternativo = os.path.join(PASTA_BACKUP, f"{nome_base}_alternativo_{gerar_timestamp_arquivo()}.csv")

    ultimo_erro = None
    for _ in range(5):
        try:
            df.to_csv(caminho_tmp, index=False, encoding="utf-8-sig")
            try:
                backup = criar_backup_do_arquivo(caminho_saida)
            except Exception:
                backup = None
            os.replace(caminho_tmp, caminho_saida)
            return {"salvo_em": caminho_saida, "backup": backup, "alternativo": False}
        except PermissionError as e:
            ultimo_erro = e
            time.sleep(1.0)
        except Exception as e:
            ultimo_erro = e
            break
        finally:
            if os.path.exists(caminho_tmp):
                try:
                    os.remove(caminho_tmp)
                except Exception:
                    pass

    df.to_csv(caminho_alternativo, index=False, encoding="utf-8-sig")
    return {
        "salvo_em": caminho_alternativo,
        "backup": None,
        "alternativo": True,
        "erro_principal": str(ultimo_erro) if ultimo_erro else "",
    }


def exportar_excel_blindado(df, nome_base: str = "lotofacil_resultados_reais") -> str | None:
    garantir_estrutura_pastas()
    caminho_xlsx = os.path.join(PASTA_EXPORT, f"{nome_base}_{gerar_timestamp_arquivo()}.xlsx")
    try:
        df.to_excel(caminho_xlsx, index=False)
        return caminho_xlsx
    except Exception:
        return None


# =========================================================
# DOWNLOAD OFICIAL CAIXA COM CACHE INCREMENTAL
# =========================================================


def criar_sessao() -> 'requests.Session':
    """Cria sessão HTTP com retry automático para erros transitórios (5xx, timeout, conexão)."""
    from requests.adapters import HTTPAdapter
    try:
        from urllib3.util.retry import Retry
        retry = Retry(
            total=HTTP_MAX_RETRIES,
            backoff_factor=HTTP_BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
    except Exception:
        adapter = HTTPAdapter()
    sess = requests.Session()
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    sess.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://loterias.caixa.gov.br/",
    })
    return sess


def resposta_parece_html(resp) -> bool:
    ctype = (resp.headers.get("Content-Type") or "").lower()
    texto = resp.text[:200].lower() if resp.text else ""
    return ("text/html" in ctype) or ("<!doctype html" in texto) or ("<html" in texto)


def obter_ultimo_concurso_api(sess=None) -> tuple[int, dict]:
    """Consulta o último concurso da Lotofácil via API oficial da CAIXA."""
    close_me = False
    if sess is None:
        sess = criar_sessao()
        close_me = True
    try:
        resp = sess.get(API_BASE, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        if resposta_parece_html(resp):
            raise ValueError(
                "A API da CAIXA retornou HTML em vez de JSON. "
                "Verifique sua conexão ou tente novamente em alguns minutos."
            )
        data = resp.json()
        numero = int(data["numero"])
        return numero, data
    except requests.exceptions.Timeout:
        raise TimeoutError(
            f"Timeout ao consultar a API da CAIXA ({HTTP_TIMEOUT}s). Verifique sua conexão."
        )
    except requests.exceptions.ConnectionError as exc:
        raise ConnectionError(f"Sem conexão com a API da CAIXA: {exc}") from exc
    finally:
        if close_me:
            sess.close()


def baixar_concurso_api(numero: int, sess=None) -> dict | None:
    close_me = False
    if sess is None:
        sess = criar_sessao()
        close_me = True
    try:
        url = f"{API_BASE}/{numero}"
        resp = sess.get(url, timeout=HTTP_TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        if resposta_parece_html(resp):
            raise ValueError(f"A API retornou HTML no concurso {numero}.")
        data = resp.json()
        dezenas = data.get("listaDezenas") or []
        if len(dezenas) != 15:
            raise ValueError(f"Concurso {numero} retornou {len(dezenas)} dezenas.")
        dezenas_int = sorted(int(x) for x in dezenas)
        registro = {
            "concurso": int(data.get("numero", numero)),
            "data": parse_data_br(data.get("dataApuracao", "")),
        }
        for i, dez in enumerate(dezenas_int, start=1):
            registro[f"d{i}"] = dez
        return registro
    finally:
        if close_me:
            sess.close()


def garantir_pasta_escrita(caminho_saida: str) -> None:
    garantir_estrutura_pastas()
    pasta = os.path.dirname(os.path.abspath(caminho_saida)) or os.getcwd()
    if not os.access(pasta, os.W_OK):
        raise PermissionError(f"Sem permissão de escrita na pasta: {pasta}")


def carregar_csv_resultados(caminho_csv: str):
    if not os.path.exists(caminho_csv):
        return pd.DataFrame(columns=["concurso", "data"] + [f"d{i}" for i in range(1, 16)])
    df = pd.read_csv(caminho_csv)
    cols = ["concurso", "data"] + [f"d{i}" for i in range(1, 16)]
    for c in cols:
        if c not in df.columns:
            raise ValueError(f"CSV existente inválido; coluna ausente: {c}")
    return df[cols].copy()


def normalizar_df_resultados(df: 'pd.DataFrame') -> 'pd.DataFrame':
    if df.empty:
        return df
    df = df.copy()
    df["concurso"] = pd.to_numeric(df["concurso"], errors="coerce").astype("Int64")
    df["data"] = df["data"].astype(str).map(parse_data_br)
    for i in range(1, 16):
        c = f"d{i}"
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    df = df.dropna(subset=["concurso"] + [f"d{i}" for i in range(1, 16)])
    for i in range(1, 16):
        df[f"d{i}"] = df[f"d{i}"].astype(int)
    df["concurso"] = df["concurso"].astype(int)
    df = df.drop_duplicates(subset=["concurso"]).sort_values("concurso").reset_index(drop=True)
    return df


def baixar_e_exportar_historico_ultra(caminho_saida: str = ARQUIVO_CSV_PADRAO, caminho_cache: str = ARQUIVO_CACHE, status_cb=None) -> dict:
    garantir_pasta_escrita(caminho_saida)

    sess = criar_sessao()
    estado = ler_json(caminho_cache, default={})

    ultimo_api, payload_ultimo = obter_ultimo_concurso_api(sess)
    ultimo_cache = int(estado.get("ultimo_concurso_baixado", 0) or 0)

    try:
        df_existente = carregar_csv_resultados(caminho_saida)
    except Exception:
        df_existente = pd.DataFrame(columns=["concurso", "data"] + [f"d{i}" for i in range(1, 16)])

    df_existente = normalizar_df_resultados(df_existente)
    ultimo_csv = int(df_existente["concurso"].max()) if not df_existente.empty else 0

    inicio = max(1, ultimo_cache, ultimo_csv) + 1
    novos = []

    # Se não existir base local, faz carga total.
    if df_existente.empty:
        inicio = 1

    def cb(msg: str) -> None:
        if status_cb:
            status_cb(msg)

    cb(f"Último concurso na API: {ultimo_api}")
    cb(f"Último concurso no cache/CSV: {max(ultimo_cache, ultimo_csv)}")

    # Se já está sincronizado, apenas garante que o último payload esteja presente.
    if inicio > ultimo_api:
        cb("Base já sincronizada. Validando último concurso...")
        registro = {
            "concurso": int(payload_ultimo.get("numero", ultimo_api)),
            "data": parse_data_br(payload_ultimo.get("dataApuracao", "")),
        }
        dezenas_int = sorted(int(x) for x in payload_ultimo.get("listaDezenas", []))
        if len(dezenas_int) == 15:
            for i, dez in enumerate(dezenas_int, start=1):
                registro[f"d{i}"] = dez
            novos.append(registro)
    else:
        total_alvo = ultimo_api - inicio + 1
        cb(f"Baixando {total_alvo} concurso(s) novo(s)...")
        for numero in range(inicio, ultimo_api + 1):
            registro = baixar_concurso_api(numero, sess)
            if registro is None:
                continue
            novos.append(registro)
            if len(novos) % 25 == 0 or numero == ultimo_api:
                cb(f"Concursos novos baixados: {len(novos)} / {total_alvo}")
            time.sleep(0.03)

    sess.close()

    df_novos = pd.DataFrame(novos)
    if df_novos.empty and not df_existente.empty:
        df_final = df_existente.copy()
    else:
        df_final = pd.concat([df_existente, df_novos], ignore_index=True)
        df_final = normalizar_df_resultados(df_final)

    if df_final.empty:
        raise ValueError("Nenhum resultado válido foi obtido da API oficial.")

    # Valida quinzenas
    for _, row in df_final.iterrows():
        jogo = [int(row[f"d{i}"]) for i in range(1, 16)]
        if len(set(jogo)) != 15 or any(n < 1 or n > 25 for n in jogo):
            raise ValueError("CSV final inválido: foi encontrada quinzena fora do padrão.")

    info_salvamento = salvar_csv_blindado(df_final, caminho_saida)
    caminho_real_salvo = info_salvamento["salvo_em"]

    estado.update({
        "ultimo_concurso_baixado": int(df_final["concurso"].max()),
        "atualizado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "api_base": API_BASE,
        "total_registros": int(len(df_final)),
        "arquivo_principal": caminho_saida,
        "arquivo_ultimo_salvo": caminho_real_salvo,
    })
    salvar_json(caminho_cache, estado)

    return caminho_real_salvo, int(len(df_final)), "API oficial CAIXA", int(len(df_novos)), info_salvamento


# =========================================================
# LEITURA DOS CONCURSOS PARA ANÁLISE
# =========================================================
