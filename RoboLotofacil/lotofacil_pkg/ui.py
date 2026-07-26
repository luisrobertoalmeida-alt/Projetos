"""
lotofacil_pkg/ui.py
--------------------
Interface gráfica tkinter — tema Neon Dark.
Separa completamente a camada de apresentação da lógica de negócio.
"""
import os
import re
import json
import time
import math
import random
import threading
import traceback
from datetime import datetime
from collections import Counter
from statistics import mean

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd

from . import config as _config_module
from .config import (
    TEMA, NUMEROS, TAMANHO_JOGO, MIN_HIST, VERSAO_ROBO, SEED,
    ARQUIVO_CSV_PADRAO, ARQUIVO_CACHE, ARQUIVO_APRENDIZADO,
    ARQUIVO_ULTIMOS_JOGOS, ARQUIVO_PERFORMANCE_ESTRATEGIA,
    ARQUIVO_DESEMPENHO_HISTORICO, ARQUIVO_CONHECIMENTO_CIENTIFICO,
    ARQUIVO_AUTO_AVALIACOES, ARQUIVO_AUTO_APRENDIZADO,
    PASTA_DADOS, PASTA_BACKUP, PASTA_EXPORT, PASTA_LOG,
    MODO_TURBO_PADRAO,
)
from .utils import (
    formatar_jogo, intersecao, contar_pares, soma_jogo,
    parse_data_br, gerar_timestamp_arquivo, limitar,
    salvar_json, ler_json, tornar_json_seguro,
    garantir_estrutura_pastas, normalizar_scores,
    seed_global,
)
from .persistencia import (
    baixar_e_exportar_historico_ultra, salvar_csv_blindado,
    exportar_excel_blindado,
)
from .historico import carregar_concursos_do_csv
from .aprendizado import (
    carregar_memoria_aprendizado, salvar_memoria_aprendizado,
    calcular_bonus_aprendizado, registrar_resultado_aprendizado,
    registrar_resultado_simulado_aprendizado,
    gerar_resumo_aprendizado,
)
from .historico import analisar_historico
from .analise import (
    calcular_motor_estrategico,
    calcular_ensemble_multi_ia, calcular_pesos_dinamicos,
)
from .genetico import (
    gerar_jogo_base, analisar_estrutura_jogo,
    analisar_estrutura_jogo_cached, calcular_mapa_cobertura,
    resumo_estrutural_pacote, score_jogo,
)
from .apostas import (
    gerar_apostas,
    gerar_apostas_dual_perfil, relatorio_dual_perfil,
    simular_jogos_em_concurso, calcular_pacote_minimo,
    gerar_relatorio_evolucao_aprendizado,
    carregar_performance_estrategias, registrar_performance_geracao,
)
from .backtest import (
    registrar_desempenho_historico_robo, gerar_resumo_banco_desempenho,
    gerar_dashboard_desempenho_historico, exportar_apostas_pdf,
    backtest_basico, backtest_ultra_massivo,
    executar_backtest_cientifico_massivo,
    executar_auto_diagnostico_lotofacil,
    calibrar_robo_vs_aleatorio,
    comparar_estrategias,
    gerar_dashboard_analitico, auditar_pacote_jogos,
    gerar_relatorio_simulador_pacote, avaliar_jogos, gerar_relatorio_texto,
    barra_ascii,
    carregar_conhecimento_cientifico,
    alimentar_poda_e_elo,
)
from .v20_8_walkforward import relatorio_walkforward, salvar_relatorio_walkforward
from .v20_6_bootstrap import relatorio_inferencial, salvar_relatorio_inferencial
# V22: Configuração central, Pipeline, Relatório, Otimizador
# (v22_plugins/PluginManager removido em 2026-07-19 — nunca era
# instanciado em lugar nenhum; ver ARQUITETURA.md)
try:
    from .v22_config import cfg as cfg_v22
    from .v22_pipeline import PipelineV22
    from .v22_relatorio import RelatorioV22
    from .v22_otimizador import otimizar_pacote as _otimizar_pacote
    _V22_OK = True
except Exception as _v22_err:
    _V22_OK = False
    print(f"⚠️ V22 não carregado: {_v22_err}")

from .v21_5_melhorias_cientificas import (
    teste_significancia_calibracao,
    score_robustez_walkforward_v2,
    estimar_referencia_melhor_aleatorio,
    relatorio_melhorias_cientificas,
    mapear_vale_gp,
)
from .v20_5_validacao_cientifica import benchmark_vs_aleatorio, ganho_estatistico
from .fechamento import (
    gerar_apostas_fechamento,
    qtd_jogos_fechamento,
    garantia_minima,
    TAMANHO_POOL_MINIMO,
    TAMANHO_POOL_MAXIMO,
)
# V21.1: SQLite + Meta-Aprendizado + Auto-Poda + Dashboard Científico
try:
    from .v21_0_sqlite import (
        inicializar_banco_v21, db_ranking_modelos,
        db_desempenho_recente, db_eventos_recentes,
        db_prob_recuperacao, db_limiar_dinamico,
    )
    from .v21_0_meta_aprendizado import MetaAprendizadoModelos
    from .v21_0_auto_poda import calcular_limiares, relatorio_auto_poda
    inicializar_banco_v21()
    _V21_OK = True
except Exception:
    _V21_OK = False

class _ToolTip:
    """Tooltip leve para widgets tkinter — aparece após 600ms de hover."""

    def __init__(self, widget: tk.Widget, texto: str) -> None:
        self.widget = widget
        self.texto = texto
        self._job: str | None = None
        self._top: tk.Toplevel | None = None
        widget.bind("<Enter>", self._agendar, add="+")
        widget.bind("<Leave>", self._cancelar, add="+")
        widget.bind("<ButtonPress>", self._cancelar, add="+")

    def _agendar(self, _event=None) -> None:
        self._cancelar()
        self._job = self.widget.after(600, self._mostrar)

    def _cancelar(self, _event=None) -> None:
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None
        if self._top:
            self._top.destroy()
            self._top = None

    def _mostrar(self) -> None:
        try:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            self._top = tk.Toplevel(self.widget)
            self._top.wm_overrideredirect(True)
            self._top.wm_geometry(f"+{x}+{y}")
            bg = TEMA.get("bg3", "#2d2d2d")
            fg = TEMA.get("fg", "#e0e0e0")
            tk.Label(
                self._top, text=self.texto, bg=bg, fg=fg,
                relief="flat", padx=8, pady=4,
                font=("Segoe UI", 8), wraplength=320, justify="left",
            ).pack()
        except Exception:
            pass


def tooltip(widget: tk.Widget, texto: str) -> None:
    """Registra um tooltip no widget. Uso: tooltip(btn, 'Descrição.')"""
    _ToolTip(widget, texto)


class RoboLotofacilUltraApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Robô Lotofácil Ultra — Interface Premium + Simulador")
        self.root.geometry("1380x900")
        self.root.configure(bg=TEMA["bg"])

        # ── Tema escuro no ttk ──────────────────────────────
        self._aplicar_tema_escuro()

        self.caminho_csv = tk.StringVar(value=ARQUIVO_CSV_PADRAO)
        self.qtd_jogos = tk.IntVar(value=20)
        self.janela_hist = tk.IntVar(value=120)
        # G=16/P=40: fixo desde 2026-07-18 -- Mapa G x P (n=300, TOST
        # margem=0.3) confirmou equivalencia estatistica na faixa G=16-300;
        # nao ha vale estrutural, entao nao faz sentido expor como ajuste
        # manual na tela principal (ver ARQUITETURA.md). Ainda pode ser
        # sobrescrito via estrategia_override/mapa_gp_custom.py para quem
        # quiser reabrir essa investigacao.
        self.geracoes = tk.IntVar(value=16)
        self.pop_size = tk.IntVar(value=40)
        self.passos_backtest = tk.IntVar(value=50)
        self.tamanho_jogo = tk.IntVar(value=TAMANHO_JOGO)
        # Fechamento combinatório (V22.1 experimental) — tamanho do pool (16-20)
        self.tamanho_pool_fechamento = tk.IntVar(value=TAMANHO_POOL_MINIMO)
        self.auto_update_on_open = tk.BooleanVar(value=True)
        self.modo_turbo = tk.BooleanVar(value=True)
        self.auto_aprender_on_open = tk.BooleanVar(value=True)
        self.usar_seed_fixo = tk.BooleanVar(value=False)
        self.seed_valor = tk.IntVar(value=42)
        # V21.6 — controle de impopularidade (0 = desligado, 100 = máximo)
        self.peso_impopularidade = tk.IntVar(value=30)

        # Restaura preferencia de Turbo salva na sessao anterior.
        # Feito antes de montar_ui para que o checkbox reflita o valor correto.
        try:
            _cache = ler_json(ARQUIVO_CACHE, default={})
            if "modo_turbo_usuario" in _cache:
                self.modo_turbo.set(bool(_cache["modo_turbo_usuario"]))
        except Exception:
            pass

        self.concursos = []
        self.df_csv = None
        self.jogos_gerados = []
        self.analise = None
        self.pesos = None
        self.info_backtest = None
        self.info_calibracao = None
        self.info_auto_diagnostico = None
        self.total_concursos_csv = 0
        self.calibracao_ativa = False
        self.auto_diagnostico_ativo = False
        self.thread_calibracao = None
        self.thread_auto_diagnostico = None
        self.aprendizado_continuo_ativo = False
        self.thread_aprendizado_continuo = None
        self.aprendizado_automatico_chave = None

        self.montar_ui()
        self.carregar_ultimos_jogos_gerados()
        self.root.protocol("WM_DELETE_WINDOW", self.encerrar_aplicativo)
        self.root.after(350, self.inicializacao_automatica)
        self.root.after(600, self._atualizar_grafico_acertos)
        self.root.after(650, self._atualizar_painel_info)

    # ── Tema escuro ──────────────────────────────────────────
    def _aplicar_tema_escuro(self) -> None:
        """Aplica tema escuro com proteção contra opções ttk não suportadas em algumas versões do Tcl/Tk."""
        try:
            style = ttk.Style(self.root)
            try:
                style.theme_use("clam")
            except Exception:
                pass

            bg, bg2, bg3 = TEMA["bg"], TEMA["bg2"], TEMA["bg3"]
            fg, fg2, acc = TEMA["fg"], TEMA["fg2"], TEMA["accent"]

            def cfg(nome, **kwargs):
                try:
                    style.configure(nome, **kwargs)
                except Exception:
                    seguros = {k: v for k, v in kwargs.items()
                               if k not in ("bordercolor", "insertcolor", "lightcolor", "darkcolor",
                                            "indicatorcolor", "indicatorrelief", "tabmargins")}
                    try:
                        style.configure(nome, **seguros)
                    except Exception:
                        pass

            def mp(nome, **kwargs):
                try:
                    style.map(nome, **kwargs)
                except Exception:
                    pass

            cfg(".", background=bg, foreground=fg, fieldbackground=bg2, troughcolor=bg3,
                selectbackground=acc, selectforeground=bg, font=("Segoe UI", 9))
            cfg("TFrame", background=bg)
            cfg("TLabel", background=bg, foreground=fg, font=("Segoe UI", 9))
            cfg("TLabelframe", background=bg, foreground=acc)
            cfg("TLabelframe.Label", background=bg, foreground=acc, font=("Segoe UI", 9, "bold"))
            cfg("TEntry", fieldbackground=bg2, foreground=fg, relief="flat")
            cfg("TCheckbutton", background=bg, foreground=fg2)
            mp("TCheckbutton", background=[("active", bg)], foreground=[("active", fg)])
            cfg("TNotebook", background=bg)
            cfg("TNotebook.Tab", background=bg2, foreground=fg2, padding=[12, 5], font=("Segoe UI", 9))
            mp("TNotebook.Tab", background=[("selected", bg3)], foreground=[("selected", acc)])
            cfg("Treeview", background=bg2, foreground=fg, fieldbackground=bg2, rowheight=22, font=("Consolas", 9))
            cfg("Treeview.Heading", background=bg3, foreground=acc, font=("Segoe UI", 9, "bold"), relief="flat")
            mp("Treeview", background=[("selected", acc)], foreground=[("selected", bg)])
            cfg("TScrollbar", background=bg3, troughcolor=bg, arrowcolor=fg2, relief="flat")
            cfg("TProgressbar", background=acc, troughcolor=bg3)
            cfg("Vermelho.TLabel", background=bg, foreground=TEMA["vermelho"])
            cfg("Verde.TLabel", background=bg, foreground=TEMA["verde"])
            cfg("Amarelo.TLabel", background=bg, foreground=TEMA["amarelo"])
            cfg("Accent.TLabel", background=bg, foreground=acc, font=("Segoe UI", 9, "bold"))
            cfg("Premium.TLabelframe", background=bg2, foreground=acc)
            cfg("Premium.TLabelframe.Label", background=bg2, foreground=acc, font=("Segoe UI", 9, "bold"))
        except Exception:
            pass

    def inicializacao_automatica(self) -> None:
        if not self.auto_update_on_open.get():
            return
        self.log("Iniciando autoatualização ao abrir...")
        try:
            self.atualizar_resultados_reais()
            self.carregar_historico()
        except Exception:
            # os próprios métodos já registram os detalhes no painel
            pass

    def criar_botao_colorido(self, master: tk.Widget, texto: str, comando, cor: str = "#2f80ed", largura: int | None = None) -> tk.Button:
        """Botão colorido com hover effect para o tema escuro."""
        btn = tk.Button(
            master,
            text=texto,
            command=comando,
            bg=cor,
            fg="white",
            activebackground=cor,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=13,
            pady=7,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            width=largura if largura else 0,
        )
        # Hover: clareia levemente
        def _on_enter(e, b=btn, c=cor):
            try:
                r = int(c[1:3], 16); g = int(c[3:5], 16); bv = int(c[5:7], 16)
                r2 = min(255, r + 30); g2 = min(255, g + 30); b2 = min(255, bv + 30)
                b.configure(bg=f"#{r2:02x}{g2:02x}{b2:02x}")
            except Exception:
                pass
        def _on_leave(e, b=btn, c=cor):
            try:
                b.configure(bg=c)
            except Exception:
                pass
        btn.bind("<Enter>", _on_enter)
        btn.bind("<Leave>", _on_leave)
        return btn

    def _criar_card_premium(self, master: tk.Widget, titulo: str, valor: str = "—", subtitulo: str = "", cor: str | None = None):
        """Cria um card visual para o dashboard superior."""
        bg2, bg3 = TEMA["bg2"], TEMA["bg3"]
        cor = cor or TEMA["accent"]
        card = tk.Frame(master, bg=bg2, highlightbackground=bg3, highlightthickness=1, padx=12, pady=8)
        tk.Label(card, text=titulo, bg=bg2, fg=TEMA["fg2"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        lbl_valor = tk.Label(card, text=valor, bg=bg2, fg=cor, font=("Segoe UI", 15, "bold"))
        lbl_valor.pack(anchor="w", pady=(2, 0))
        lbl_sub = tk.Label(card, text=subtitulo, bg=bg2, fg=TEMA["fg2"], font=("Segoe UI", 8))
        lbl_sub.pack(anchor="w")
        return card, lbl_valor, lbl_sub

    def montar_ui(self) -> None:
        """Orquestra a construção completa da interface gráfica."""
        self._montar_header()
        self._montar_dashboard()
        self._montar_controles()
        self._montar_notebook()
        self._registrar_atalhos()

    # ── Submétodos de construção da UI ────────────────────────────────────────

    def _montar_header(self) -> None:
        """Cabeçalho com título e painel de info rápida."""
        bg2, fg2, acc = TEMA["bg2"], TEMA["fg2"], TEMA["accent"]
        bg3 = TEMA["bg3"]

        header = tk.Frame(self.root, bg=bg2, pady=8)
        header.pack(fill="x")
        tk.Label(header, text="🎲  Robô Lotofácil Ultra",
                 bg=bg2, fg=acc, font=("Segoe UI", 17, "bold")).pack(side="left", padx=(18, 10))
        tk.Label(header, text="Interface Premium • IA Adaptativa • Simulador de Qualidade",
                 bg=bg2, fg=fg2, font=("Segoe UI", 10)).pack(side="left")

        self._frame_info = tk.Frame(header, bg=bg2)
        self._frame_info.pack(side="right", padx=16)
        self._lbl_concursos = tk.Label(self._frame_info, text="Concursos: —", bg=bg2, fg=fg2, font=("Segoe UI", 9))
        self._lbl_concursos.grid(row=0, column=0, padx=10)
        self._lbl_ultimo = tk.Label(self._frame_info, text="Último: —", bg=bg2, fg=fg2, font=("Segoe UI", 9))
        self._lbl_ultimo.grid(row=0, column=1, padx=10)
        self._lbl_memoria = tk.Label(self._frame_info, text="Memória IA: —", bg=bg2, fg=fg2, font=("Segoe UI", 9))
        self._lbl_memoria.grid(row=0, column=2, padx=10)

        tk.Frame(self.root, bg=bg3, height=1).pack(fill="x")

    def _montar_dashboard(self) -> None:
        """Cards de métricas rápidas na faixa superior."""
        bg = TEMA["bg"]

        dash = tk.Frame(self.root, bg=bg, padx=12, pady=10)
        dash.pack(fill="x")
        cards = [
            ("📚 Base",       "—", "concursos carregados",         TEMA["verde"]),
            ("🧠 Memória IA", "—", "registros de aprendizado",     TEMA["accent"]),
            ("🎲 Jogos",      "—", "último pacote gerado",         TEMA["amarelo"]),
            ("🏆 Melhor",     "—", "último desempenho registrado", TEMA["roxo"]),
            ("🧪 Simulador",  "ativo", "auditoria do pacote",      TEMA["ciano"]),
        ]
        self._cards_dashboard = {}
        for chave, valor, sub, cor in cards:
            card, lbl_valor, lbl_sub = self._criar_card_premium(dash, chave, valor, sub, cor)
            card.pack(side="left", fill="x", expand=True, padx=4)
            self._cards_dashboard[chave] = (lbl_valor, lbl_sub)

    def _montar_controles(self) -> None:
        """Painel de configurações, campos numéricos, checkboxes e botões."""
        bg, bg2, bg3 = TEMA["bg"], TEMA["bg2"], TEMA["bg3"]
        fg, fg2, acc = TEMA["fg"], TEMA["fg2"], TEMA["accent"]

        topo = tk.LabelFrame(self.root, text="  ⚙️ Central de Controle  ", bg=bg, fg=acc,
                             padx=12, pady=8, font=("Segoe UI", 9, "bold"),
                             highlightbackground=bg3, highlightthickness=1, bd=0)
        topo.pack(fill="x", padx=12, pady=(4, 8))

        # ── Linha 0: CSV ──────────────────────────────────────
        linha0 = tk.Frame(topo, bg=bg)
        linha0.pack(fill="x", pady=(0, 4))
        tk.Label(linha0, text="CSV:", bg=bg, fg=fg2, font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(linha0, textvariable=self.caminho_csv,
                 bg=bg2, fg=fg, insertbackground=fg,
                 relief="flat", font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=6)
        self.criar_botao_colorido(linha0, "📂 Selecionar", self.selecionar_csv,
                                  cor=TEMA["btn_csv"]).pack(side="left")

        # ── Linha 1: parâmetros numéricos ─────────────────────
        linha1 = tk.Frame(topo, bg=bg)
        linha1.pack(fill="x", pady=4)

        def campo(parent, label, var, w=7):
            tk.Label(parent, text=label, bg=bg, fg=fg2, font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))
            tk.Entry(parent, textvariable=var, width=w,
                     bg=bg2, fg=fg, insertbackground=fg,
                     relief="flat", font=("Segoe UI", 9)).pack(side="left")

        campo(linha1, "Qtd. jogos",       self.qtd_jogos)
        campo(linha1, "Janela histórica", self.janela_hist)
        campo(linha1, "Passos BT",    self.passos_backtest)
        campo(linha1, "  Pool Fecht.", self.tamanho_pool_fechamento, w=3)
        # ── Campo Dezenas destacado ───────────────────────────
        _acc = TEMA["accent"]
        _dez_frame = tk.Frame(linha1, bg=_acc, padx=1, pady=1)
        _dez_frame.pack(side="left", padx=(10, 2))
        _dez_inner = tk.Frame(_dez_frame, bg=bg)
        _dez_inner.pack()
        tk.Label(_dez_inner, text="✦ Dezenas", bg=bg, fg=_acc,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 2))
        tk.Entry(_dez_inner, textvariable=self.tamanho_jogo, width=4,
                 bg=bg2, fg=_acc, insertbackground=_acc,
                 relief="flat", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))

        # ── Impopularidade (mesma linha, logo após Dezenas) ───
        tk.Label(linha1, text="  📊 Impopularidade:", bg=bg, fg=TEMA["ciano"],
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(12, 2))
        _imp_val_lbl = tk.Label(linha1, text="30%", bg=bg, fg=TEMA["ciano"],
                                font=("Segoe UI", 9, "bold"), width=4)
        _imp_val_lbl.pack(side="left")

        def _atualizar_lbl_imp(val):
            _imp_val_lbl.config(text=f"{int(float(val))}%")

        tk.Scale(
            linha1,
            from_=0, to=100,
            orient="horizontal",
            variable=self.peso_impopularidade,
            command=_atualizar_lbl_imp,
            bg=bg, fg=TEMA["ciano"], troughcolor=bg3,
            highlightthickness=0, showvalue=False,
            length=110, width=10,
        ).pack(side="left", padx=(2, 6))

        # ── Linha 2: checkboxes ───────────────────────────────
        linha2 = tk.Frame(topo, bg=bg)
        linha2.pack(fill="x", pady=2)

        def chk(parent, label, var):
            tk.Checkbutton(parent, text=label, variable=var,
                           bg=bg, fg=fg2, activebackground=bg,
                           selectcolor=bg3, font=("Segoe UI", 9)).pack(side="left", padx=6)

        chk(linha2, "Autoatualizar ao abrir",       self.auto_update_on_open)
        chk(linha2, "Modo Turbo",                   self.modo_turbo)
        chk(linha2, "Auto Aprender ao carregar",    self.auto_aprender_on_open)
        tk.Checkbutton(linha2, text="Seed fixo", variable=self.usar_seed_fixo,
                       bg=bg, fg=fg2, activebackground=bg, selectcolor=bg3,
                       font=("Segoe UI", 9)).pack(side="left", padx=(6, 2))
        tk.Entry(linha2, textvariable=self.seed_valor, width=5,
                 bg=bg2, fg=fg, insertbackground=fg, relief="flat",
                 font=("Segoe UI", 9)).pack(side="left")

        # ── Linha 3: operação principal ───────────────────────
        tk.Label(topo, text="▶ Operação principal", bg=bg, fg=acc, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 0))
        linha3 = tk.Frame(topo, bg=bg)
        linha3.pack(fill="x", pady=(4, 2))
        _tips_linha3 = {
            "⬆ Atualizar":      "Baixa os últimos resultados da API da CAIXA e atualiza o CSV.",
            "📂 Carregar":       "Lê o CSV do disco e carrega o histórico em memória.",
            "🎲 Gerar Jogos":    "Gera o pacote de apostas usando ensemble multi-IA + algoritmo genético, já na configuração G/P validada (16/40). (F5)",
            "🧪 Simulador":      "Audita a qualidade estrutural do pacote com simulações artificiais.",
            "✅ Conferir Jogos": "Confere os jogos gerados contra o último sorteio real.",
            "🎯 Dual-Perfil":   "Gera pacote misto: 70% otimizado para 11+/12+ e 30% exploração para 13+ (Pares/Trios + Cobertura).",
            "🔒 Fechamento":    "Fechamento combinatório: escolhe um pool de dezenas (campo 'Pool Fecht.', 16-20) pelo ranking do "
                                "ensemble e joga TODAS as combinações de 15 dentro dele. Garantia matemática (não estatística) "
                                "condicionada às 15 sorteadas estarem dentro do pool escolhido — ver VALIDACAO_ESCALA_REAL "
                                "e docstring de fechamento.py.",
            "⚡ Otimizador": "Gera pacotes candidatos com a mesma configuração até atingir 95% de 11+ na simulação "
                                "(ou esgotar as tentativas); entre os candidatos, escolhe o melhor priorizando 12+/13+ "
                                "e média do melhor jogo (mais raros e discriminantes que 11+) — investigação, não "
                                "muda a config validada.",
        }
        for txt, cmd, cor in [
            ("⬆ Atualizar",      self.iniciar_atualizar_resultados, TEMA["btn_atualizar"]),
            ("📂 Carregar",       self.iniciar_carregar_historico,   TEMA["btn_carregar"]),
            ("🎲 Gerar Jogos",    self.iniciar_gerar_jogos,          TEMA["btn_gerar"]),
            ("🧪 Simulador",     self.rodar_simulador_pacote,                TEMA["btn_simulador"]),
            ("✅ Conferir Jogos",self.conferir_jogos_gerados,                TEMA["btn_conferir"]),
            ("🎯 Dual-Perfil",    self.gerar_jogos_dual_perfil,      TEMA["btn_gerar"]),
            ("🔒 Fechamento",     self.iniciar_fechamento,           TEMA["btn_pacote"]),
            ("⚡ Otimizador", self.iniciar_otimizador_v22,          TEMA["btn_aprender"]),
        ]:
            btn = self.criar_botao_colorido(linha3, txt, cmd, cor=cor)
            btn.pack(side="left", padx=3)
            tooltip(btn, _tips_linha3.get(txt, ""))

        # ── Linha 4: inteligência e calibração ───────────────
        tk.Label(topo, text="🧠 Inteligência, diagnóstico e calibração", bg=bg, fg=acc, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 0))
        linha4 = tk.Frame(topo, bg=bg)
        linha4.pack(fill="x", pady=(4, 2))
        _tips_linha4 = {
            "⚡ Aprender":             "Executa um ciclo de aprendizado contínuo com os dados disponíveis.",
            "🩺 Auto Diagnóstico":     "Analisa automaticamente a qualidade do histórico e do robô.",
            "🎯 Calibrar IA":          "Compara o robô contra pacotes aleatórios em concursos passados.",
            "📊 Backtest":       "Testa o robô em concursos passados e mede a taxa de acertos. (F6)",
            "🤖 BT Automático": "Walk-forward detalhado: gera e confere jogos concurso a concurso, salva relatório.",
            "🧪 Backtest Científico": "Backtest científico massivo (configuração validada vs. diversidade ampliada) e "
                                "campeonato de modelos do ensemble — alimenta poda/ELO com o resultado.",
            "🔀 Walk-Forward":         "Validação walk-forward deslizante: avalia robustez em múltiplas janelas e detecta overfitting.",
            "📐 Bootstrap IC":         "IC 95%/99% e erro padrão (bootstrap) sobre a série de acertos do último backtest. "
                                "Não compara contra aleatório (sem p-value/Cohen's d aqui) — para isso use 🎯 Calibrar IA ou 🗺️ Mapa G×P.",
            "🔬 Análise Científica":    "Teste binomial de significância + Walk-Forward com métrica corrigida (melhor do pacote). Rode Calibrar IA e Walk-Forward antes.",
        }
        for txt, cmd, cor in [
            ("⚡ Aprender",            self.forcar_aprendizado_continuo_seguro, TEMA["btn_aprender"]),
            ("🩺 Auto Diagnóstico",    self.iniciar_auto_diagnostico,           TEMA["btn_comparar"]),
            ("🎯 Calibrar IA",         self.iniciar_calibracao_vs_aleatorio,    TEMA["btn_backtest"]),
            ("📊 Backtest",       self.iniciar_rodar_backtest,       TEMA["btn_backtest"]),
            ("🤖 BT Automático", self.iniciar_backtest_automatico,   TEMA["btn_backauto"]),
            ("🧪 Backtest Científico", self.iniciar_backtest_cientifico_v11, TEMA["btn_relatorio"]),
            ("🔀 Walk-Forward",        self.iniciar_walkforward,                TEMA["btn_backauto"]),
            ("📐 Bootstrap IC",        self.iniciar_bootstrap_ic,               TEMA["btn_relatorio"]),
            ("🔬 Análise Científica",   self.iniciar_analise_cientifica_v2,      TEMA["btn_relatorio"]),
        ]:
            btn = self.criar_botao_colorido(linha4, txt, cmd, cor=cor)
            btn.pack(side="left", padx=3)
            tooltip(btn, _tips_linha4.get(txt, ""))

        # ── Linha 5: conferência, relatórios e arquivos ───────
        tk.Label(topo, text="📊 Conferência, relatórios e arquivos", bg=bg, fg=acc, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 0))
        linha5 = tk.Frame(topo, bg=bg)
        linha5.pack(fill="x", pady=(4, 6))
        _tips_linha5 = {
            "📈 Dashboard":      "Abre o painel analítico completo com análise do pacote e relatório.",
            "📊 Desempenho":     "Exibe o banco histórico de acertos reais registrados e o ranking de modelos do ensemble.",
            "💾 Salvar TXT":     "Salva só os números dos jogos gerados em TXT (sem relatório, score ou logs).",
            "🖨️ Exportar PDF":   "Exporta os jogos gerados em PDF com o volante da Lotofácil marcado visualmente.",
            "📋 Excel":          "Exporta o histórico de resultados para planilha Excel.",
            "🎰 Probabilidades": "Calculadora de probabilidades reais baseada em combinatória.",
            "🗑 Limpar":         "Limpa o painel de log. (Ctrl+L)",
        }
        for txt, cmd, cor in [
            ("📈 Dashboard",     self.abrir_dashboard,                       TEMA["btn_dash"]),
            ("📊 Desempenho",    self.abrir_dashboard_desempenho,            TEMA["btn_relatorio"]),
            ("⚗️ Painel Científico", self.abrir_dashboard_cientifico_v21,       TEMA["btn_backauto"]),
            ("💾 Salvar TXT",    self.salvar_txt,                            TEMA["btn_salvar"]),
            ("🖨️ Exportar PDF",  self.exportar_pdf,                          TEMA["btn_pdf"]),
            ("📋 Excel",         self.exportar_excel,                        TEMA["btn_excel"]),
            ("🎰 Probabilidades",self.abrir_calculadora_probabilidades,      TEMA["btn_comparar"]),
            ("🗑 Limpar",        self.limpar,                                TEMA["btn_limpar"]),
        ]:
            btn = self.criar_botao_colorido(linha5, txt, cmd, cor=cor)
            btn.pack(side="left", padx=3)
            tooltip(btn, _tips_linha5.get(txt, ""))

        # Encerrar no canto direito da mesma linha de relatórios
        self.criar_botao_colorido(
            linha5, "✖ Encerrar",
            self.encerrar_aplicativo, cor=TEMA["btn_encerrar"],
        ).pack(side="right", padx=3)

        # ── Barra de progresso ────────────────────────────────
        barra_frame = tk.Frame(topo, bg=bg)
        barra_frame.pack(fill="x", pady=(0, 2))
        self._progresso = ttk.Progressbar(
            barra_frame, mode="determinate", maximum=100, style="TProgressbar"
        )
        self._progresso.pack(fill="x")
        self._progresso_visivel = False
        self._progresso_valor = tk.DoubleVar(value=0)

        self.lbl_status = ttk.Label(topo, text="Pronto.", style="Accent.TLabel")
        self.lbl_status.pack(anchor="w", pady=(0, 2))

        tk.Frame(self.root, bg=bg3, height=1).pack(fill="x")

    def _montar_notebook(self) -> None:
        """Notebook inferior com abas: Log, Jogos Gerados, Histórico de Acertos, Comparador, Mapa G×P."""
        bg, bg2, fg = TEMA["bg"], TEMA["bg2"], TEMA["fg"]

        self._notebook_corpo = ttk.Notebook(self.root)
        self._notebook_corpo.pack(fill="both", expand=True)

        # Aba Log
        aba_log = ttk.Frame(self._notebook_corpo)
        self._notebook_corpo.add(aba_log, text="  📋 Log  ")
        txt_frame = tk.Frame(aba_log, bg=bg)
        txt_frame.pack(fill="both", expand=True)
        self.txt_saida = tk.Text(
            txt_frame, wrap="word", bg=bg2, fg=fg, insertbackground=fg,
            font=("Consolas", 10), relief="flat",
            selectbackground=TEMA["accent"], selectforeground=bg,
            pady=6, padx=8,
        )
        self.txt_saida.pack(side="left", fill="both", expand=True)
        scroll_log = ttk.Scrollbar(txt_frame, orient="vertical", command=self.txt_saida.yview)
        scroll_log.pack(side="right", fill="y")
        self.txt_saida.config(yscrollcommand=scroll_log.set)
        for tag, cor, extra in [
            ("ok",     TEMA["verde"],    {}),
            ("erro",   TEMA["vermelho"], {}),
            ("aviso",  TEMA["amarelo"],  {}),
            ("titulo", TEMA["accent"],   {"font": ("Consolas", 10, "bold")}),
            ("normal", fg,               {}),
        ]:
            self.txt_saida.tag_configure(tag, foreground=cor, **extra)

        # Aba Jogos
        aba_jogos = ttk.Frame(self._notebook_corpo)
        self._notebook_corpo.add(aba_jogos, text="  🎲 Jogos Gerados  ")
        self._montar_aba_jogos(aba_jogos)

        # Aba Acertos
        aba_acertos = ttk.Frame(self._notebook_corpo)
        self._notebook_corpo.add(aba_acertos, text="  📈 Histórico de Acertos  ")
        self._montar_aba_acertos(aba_acertos)

        # Aba Comparador
        aba_comp = ttk.Frame(self._notebook_corpo)
        self._notebook_corpo.add(aba_comp, text="  ⚖️ Comparador  ")
        self._montar_aba_comparador(aba_comp)

        # Aba Mapa G×P — uso pontual, tirada da barra de botões principal
        # para não competir em destaque com a operação do dia a dia.
        aba_mapa_gp = ttk.Frame(self._notebook_corpo)
        self._notebook_corpo.add(aba_mapa_gp, text="  🗺️ Mapa G×P  ")
        self._montar_aba_mapa_gp(aba_mapa_gp)

    def _registrar_atalhos(self) -> None:
        """Registra todos os atalhos de teclado globais."""
        self.root.bind("<F5>",        lambda e: self.iniciar_gerar_jogos())
        self.root.bind("<F6>",        lambda e: self.iniciar_rodar_backtest())
        self.root.bind("<F9>",        lambda e: self.atualizar_resultados_reais())
        self.root.bind("<F10>",       lambda e: self.carregar_historico())
        self.root.bind("<Control-l>", lambda e: self.limpar())


    def _montar_aba_jogos(self, parent: ttk.Frame) -> None:
        """Tabela de jogos gerados com colunas estruturadas."""
        bg, bg2 = TEMA["bg"], TEMA["bg2"]
        cols = ("jogo", "dezenas", "pares", "impares", "soma", "perfil", "estrutura", "score")
        self._tree_jogos = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")
        cab = {
            "jogo":     ("Jogo",      55),
            "dezenas":  ("Dezenas",   340),
            "pares":    ("Pares",     55),
            "impares":  ("Ímpares",   60),
            "soma":     ("Soma",      55),
            "perfil":   ("Perfil",    160),
            "estrutura":("Estrutura", 130),
            "score":    ("Score",     75),
        }
        for c, (h, w) in cab.items():
            self._tree_jogos.heading(c, text=h)
            self._tree_jogos.column(c, width=w, anchor="center" if c != "dezenas" and c != "perfil" else "w")

        sb_v = ttk.Scrollbar(parent, orient="vertical",   command=self._tree_jogos.yview)
        sb_h = ttk.Scrollbar(parent, orient="horizontal", command=self._tree_jogos.xview)
        self._tree_jogos.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        self._tree_jogos.pack(side="left", fill="both", expand=True)
        sb_v.pack(side="right", fill="y")

        # Rodapé com resumo
        self._lbl_jogos_resumo = tk.Label(parent, text="Nenhum jogo gerado ainda.",
                                           bg=TEMA["bg"], fg=TEMA["fg2"], font=("Segoe UI", 9))
        self._lbl_jogos_resumo.pack(side="bottom", anchor="w", padx=8, pady=4)

    def _montar_aba_acertos(self, parent: ttk.Frame) -> None:
        """Canvas com gráfico de barras do histórico de acertos da memória IA."""
        bg = TEMA["bg"]
        self._canvas_acertos = tk.Canvas(parent, bg=bg, highlightthickness=0)
        self._canvas_acertos.pack(fill="both", expand=True)
        # Redesenha quando o canvas ganha seu tamanho real: logo após a criação
        # (ou ao trocar de aba, quando o notebook mapeia o frame pela primeira
        # vez) winfo_width()/height() retornam 1, não 0 — o fallback "or 900"
        # não entra em ação e o gráfico é desenhado numa área de 1x1 (invisível).
        # <Configure> dispara assim que o canvas recebe as dimensões reais.
        self._canvas_acertos.bind("<Configure>", lambda e: self._atualizar_grafico_acertos())
        self._lbl_acertos_vazio = tk.Label(parent,
            text="Registre resultados usando 'Conferir Jogos' para ver o histórico aqui.",
            bg=bg, fg=TEMA["fg2"], font=("Segoe UI", 10))
        self._lbl_acertos_vazio.place(relx=0.5, rely=0.5, anchor="center")

    def _montar_aba_comparador(self, parent: ttk.Frame) -> None:
        """Aba completa do Comparador de Estratégias."""
        bg, bg2, bg3 = TEMA["bg"], TEMA["bg2"], TEMA["bg3"]
        fg, fg2, acc = TEMA["fg"], TEMA["fg2"], TEMA["accent"]

        # ── Painel de configuração ──────────────────────────
        cfg = tk.Frame(parent, bg=bg2, padx=12, pady=10)
        cfg.pack(fill="x")

        tk.Label(cfg, text="⚖️  Comparador de Estratégias",
                 bg=bg2, fg=acc, font=("Segoe UI", 12, "bold")).grid(
                     row=0, column=0, columnspan=8, sticky="w", pady=(0, 8))

        def lbl(text): return tk.Label(cfg, text=text, bg=bg2, fg=fg2, font=("Segoe UI", 9))
        def ent(var, w=6): return tk.Entry(cfg, textvariable=var, width=w,
                                           bg=bg3, fg=fg, insertbackground=fg, relief="flat",
                                           font=("Segoe UI", 9))

        self._comp_passos   = tk.IntVar(value=30)
        self._comp_qtd      = tk.IntVar(value=10)
        self._comp_janela   = tk.IntVar(value=120)

        lbl("Passos BT").grid(row=1, column=0, sticky="w", padx=(0, 4))
        ent(self._comp_passos).grid(row=1, column=1, sticky="w", padx=(0, 16))
        lbl("Qtd. jogos").grid(row=1, column=2, sticky="w", padx=(0, 4))
        ent(self._comp_qtd).grid(row=1, column=3, sticky="w", padx=(0, 16))
        lbl("Janela histórica").grid(row=1, column=4, sticky="w", padx=(0, 4))
        ent(self._comp_janela, w=7).grid(row=1, column=5, sticky="w", padx=(0, 16))

        self._btn_rodar_comp = self.criar_botao_colorido(
            cfg, "▶  Rodar Comparação", self._rodar_comparador,
            cor=TEMA["btn_comparar"])
        self._btn_rodar_comp.grid(row=1, column=6, padx=(0, 8))

        self._btn_salvar_comp = self.criar_botao_colorido(
            cfg, "💾 Exportar CSV", self._exportar_comparador,
            cor=TEMA["btn_salvar"])
        self._btn_salvar_comp.grid(row=1, column=7)

        tk.Label(cfg,
                 text="Cada estratégia roda backtest independente. Avaliação: score ponderado prioriza acertos ≥11 e ≥13.",
                 bg=bg2, fg=fg2, font=("Segoe UI", 8)).grid(
                     row=2, column=0, columnspan=8, sticky="w", pady=(6, 0))

        # ── Tabela de resultados ───────────────────────────
        tk.Frame(parent, bg=bg3, height=1).pack(fill="x")
        tab_frame = tk.Frame(parent, bg=bg)
        tab_frame.pack(fill="both", expand=True)

        cols = ("pos", "nome", "score", "med_melhor", "max", "pct11", "pct13",
                "med_geral", "geracoes", "pop", "mutacao", "janela_pct", "tempo")
        self._tree_comp = ttk.Treeview(tab_frame, columns=cols, show="headings",
                                       selectmode="browse", height=8)
        cab_comp = {
            "pos":        ("🏆", 40),
            "nome":       ("Estratégia",       160),
            "score":      ("Score ⭐",          80),
            "med_melhor": ("Méd. Melhor",       90),
            "max":        ("Máx.",              55),
            "pct11":      ("≥11 (%)",           70),
            "pct13":      ("≥13 (%)",           70),
            "med_geral":  ("Méd. Geral",        80),
            "geracoes":   ("Gerações",          70),
            "pop":        ("Pop.",              55),
            "mutacao":    ("Mutação",           70),
            "janela_pct": ("Janela %",          70),
            "tempo":      ("Tempo(s)",          70),
        }
        for c, (h, w) in cab_comp.items():
            self._tree_comp.heading(c, text=h,
                command=lambda col=c: self._ordenar_tabela_comp(col))
            self._tree_comp.column(c, width=w,
                anchor="center" if c not in ("nome",) else "w")

        sb_cv = ttk.Scrollbar(tab_frame, orient="vertical",   command=self._tree_comp.yview)
        sb_ch = ttk.Scrollbar(tab_frame, orient="horizontal", command=self._tree_comp.xview)
        self._tree_comp.configure(yscrollcommand=sb_cv.set, xscrollcommand=sb_ch.set)
        self._tree_comp.pack(side="left", fill="both", expand=True)
        sb_cv.pack(side="right", fill="y")

        # ── Canvas do gráfico de barras ────────────────────
        tk.Frame(parent, bg=bg3, height=1).pack(fill="x")
        self._canvas_comp = tk.Canvas(parent, bg=bg, highlightthickness=0, height=220)
        self._canvas_comp.pack(fill="x", padx=0, pady=0)
        # Mesmo bug (agora corrigido) do gráfico de Acertos: sem <Configure>,
        # o primeiro desenho pode acontecer com o canvas ainda em 1x1 (antes
        # do notebook mapear a aba), ficando invisível até algum redesenho
        # acidental. Redesenha com o último resultado assim que o canvas
        # recebe suas dimensões reais.
        self._canvas_comp.bind(
            "<Configure>",
            lambda e: self._desenhar_grafico_comp(self._resultados_comp) if getattr(self, "_resultados_comp", None) else None,
        )

        # ── Status do comparador ───────────────────────────
        self._lbl_comp_status = tk.Label(parent, text="Configure e clique em 'Rodar Comparação'.",
                                          bg=bg, fg=fg2, font=("Segoe UI", 9))
        self._lbl_comp_status.pack(anchor="w", padx=10, pady=4)

        self._resultados_comp = []   # cache dos últimos resultados
        self._comp_sort_col   = None
        self._comp_sort_asc   = False

    def _montar_aba_mapa_gp(self, parent: ttk.Frame) -> None:
        """
        Aba do Mapa G×P — investigação pontual (não é operação do dia a dia),
        por isso fica numa aba própria em vez de um botão na barra principal.
        """
        bg, bg2, bg3 = TEMA["bg"], TEMA["bg2"], TEMA["bg3"]
        fg, fg2, acc = TEMA["fg"], TEMA["fg2"], TEMA["accent"]

        painel = tk.Frame(parent, bg=bg2, padx=16, pady=14)
        painel.pack(fill="x")

        tk.Label(painel, text="🗺️  Mapa G×P",
                 bg=bg2, fg=acc, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))

        tk.Label(
            painel,
            text="Mapeia o espaço de Gerações×População e testa os extremos contra os intermediários com "
                 "estatística PAREADA (Cohen's d pareado, sign-flip, TOST) — mesma metodologia de "
                 "reanalise_pareada.py. Já confirmado equivalente de G=16 a G=300 (ver ARQUITETURA.md); use só "
                 "para reabrir a investigação, não é necessário no uso normal.",
            bg=bg2, fg=fg2, font=("Segoe UI", 9), justify="left", wraplength=760,
        ).pack(anchor="w", pady=(0, 12))

        self._lbl_mapa_gp_status = tk.Label(
            painel, text="Usa Janela histórica, Passos BT e Qtd. jogos configurados no topo da tela.",
            bg=bg2, fg=fg2, font=("Segoe UI", 9),
        )
        self._lbl_mapa_gp_status.pack(anchor="w", pady=(0, 10))

        def _rodar():
            self._lbl_mapa_gp_status.config(
                text="⏳ Rodando... acompanhe o progresso na aba 📋 Log.", fg=TEMA["amarelo"]
            )
            self.iniciar_mapa_gp()

        self.criar_botao_colorido(
            painel, "🗺️ Rodar Mapa G×P", _rodar, cor=TEMA["btn_neon_verde"],
        ).pack(anchor="w")

    def _atualizar_tabela_jogos(self, mudar_aba: bool = True) -> None:
        """
        Preenche a tabela de jogos com os dados da última geração.

        `mudar_aba=False` popula a tabela sem forçar a troca pra aba
        "Jogos Gerados" — usado na restauração do pacote ao abrir o app
        (`carregar_ultimos_jogos_gerados`), pra não roubar o foco da tela
        logo na inicialização (antes, essa restauração simplesmente não
        chamava este método, então a tabela ficava vazia até a próxima
        geração real, mesmo com um pacote válido já em memória — ver
        2026-07-23 no ARQUITETURA.md).
        """
        for row in self._tree_jogos.get_children():
            self._tree_jogos.delete(row)
        if not self.jogos_gerados or self.analise is None or self.pesos is None:
            self._lbl_jogos_resumo.config(text="Nenhum jogo gerado ainda.")
            return
        avaliados = avaliar_jogos(self.jogos_gerados, self.analise, self.pesos)
        cores = {
            "estrutura forte": TEMA["verde"],
            "estrutura boa":   TEMA["accent"],
            "estrutura aceitável": TEMA["amarelo"],
            "estrutura fraca": TEMA["vermelho"],
        }
        for r in avaliados:
            tag = r.get("Estrutura", "").lower().replace("á","a")
            self._tree_jogos.insert("", "end", values=(
                f"{r['Jogo']:02d}",
                r["Dezenas"],
                r["Pares"],
                r["Ímpares"],
                r["Soma"],
                r.get("Perfil", ""),
                r.get("Estrutura", ""),
                r["Score"],
            ), tags=(tag,))
        for cls, cor in cores.items():
            chave = cls.lower().replace("á","a")
            self._tree_jogos.tag_configure(chave, foreground=cor)
        cob = (self.analise.get("cobertura_global") or {})
        self._lbl_jogos_resumo.config(
            text=f"Total: {len(self.jogos_gerados)} jogos  |  "
                 f"Sobrep. média: {cob.get('media_sobreposicao', '—')}  |  "
                 f"Soma média: {cob.get('media_soma', '—')}  |  "
                 f"Pares médios: {cob.get('media_pares', '—')}   "
                 f"[F5=Gerar  F6=Backtest  F9=Atualizar  F10=Carregar  Ctrl+L=Limpar]"
        )
        self._atualizar_painel_info()
        if mudar_aba:
            # Vai para a aba de jogos automaticamente
            self._notebook_corpo.select(1)

    def _atualizar_grafico_acertos(self) -> None:
        """Desenha gráfico de barras dos últimos acertos registrados."""
        memoria = carregar_memoria_aprendizado()
        registros = memoria.get("registros", [])
        c = self._canvas_acertos
        c.delete("all")
        if not registros:
            self._lbl_acertos_vazio.place(relx=0.5, rely=0.5, anchor="center")
            return
        self._lbl_acertos_vazio.place_forget()

        bg, fg, acc = TEMA["bg"], TEMA["fg"], TEMA["accent"]
        verde, amarelo, vermelho = TEMA["verde"], TEMA["amarelo"], TEMA["vermelho"]

        ultimos = registros[-60:]
        melhores = [int(r.get("melhor_acerto", 0)) for r in ultimos]
        medias   = [float(r.get("media_acertos", 0)) for r in ultimos]
        n = len(melhores)

        # Dimensões
        W = c.winfo_width()  or 900
        H = c.winfo_height() or 400
        mg_l, mg_r, mg_t, mg_b = 55, 20, 30, 60
        w_area = W - mg_l - mg_r
        h_area = H - mg_t - mg_b
        mx = max(melhores) if melhores else 15
        escala = h_area / max(mx, 15)

        # Fundo do gráfico
        c.create_rectangle(mg_l, mg_t, W - mg_r, H - mg_b,
                            fill=TEMA["bg2"], outline=TEMA["bg3"])

        # Linhas de grade horizontais
        for v in range(10, 16):
            y = H - mg_b - int(v * escala)
            cor_grade = vermelho if v == 11 else (amarelo if v == 13 else TEMA["bg3"])
            c.create_line(mg_l, y, W - mg_r, y, fill=cor_grade, dash=(4, 4) if v not in (11, 13) else ())
            c.create_text(mg_l - 6, y, text=str(v), fill=fg, font=("Segoe UI", 8), anchor="e")

        # Barras
        bw = max(4, min(28, int(w_area / max(n, 1)) - 2))
        for i, (m, med) in enumerate(zip(melhores, medias)):
            x = mg_l + int(i * w_area / max(n, 1)) + (int(w_area / max(n, 1)) - bw) // 2
            y_top = H - mg_b - int(m * escala)
            cor = verde if m >= 13 else (acc if m >= 11 else TEMA["fg2"])
            c.create_rectangle(x, y_top, x + bw, H - mg_b, fill=cor, outline="")
            # Linha de média
            y_med = H - mg_b - int(med * escala)
            c.create_oval(x + bw//2 - 2, y_med - 2, x + bw//2 + 2, y_med + 2,
                          fill=amarelo, outline="")

        # Rótulo do eixo X
        c.create_text(W // 2, H - 12,
                      text=f"Últimos {n} registros   •   ■ melhor acerto   • média",
                      fill=TEMA["fg2"], font=("Segoe UI", 8))

        # Estatísticas no topo
        media_geral = sum(melhores) / len(melhores) if melhores else 0
        c.create_text(mg_l + 4, mg_t + 10,
                      text=f"Melhor: {max(melhores)}   Média: {media_geral:.1f}   Total registros: {len(registros)}",
                      fill=acc, font=("Segoe UI", 9, "bold"), anchor="w")

    def _aplicar_seed_configurada(self, log_async: bool = False) -> None:
        """
        Aplica a seed (fixa ou aleatória) conforme o checkbox "Seed fixo".

        Chamado no início de toda operação que gera jogos/simula concursos
        (Gerar Jogos, Backtest, BT Automático, Walk-Forward, Calibrar IA, Lab
        Histórico, Auto Diagnóstico, Científico V11, Dual-Perfil, Otimizador,
        Mapa G×P) para que o mesmo seed valha para todas elas — antes, só
        "Gerar Jogos" aplicava `seed_global`, e mesmo essa chamada não
        alcançava `config.SEED` (ver `seed_global` em utils.py), então as
        demais sempre rodavam com entropia real, mesmo com o checkbox
        marcado.
        """
        registrar = self.log_async if log_async else self.log
        if self.usar_seed_fixo.get():
            seed_global(int(self.seed_valor.get()))
            registrar(f"Seed fixo ativado: {self.seed_valor.get()} (resultados reproduzíveis)")
        else:
            seed_global(None)
            registrar("Seed aleatório (resultados diferentes a cada execução)")

    def _obter_resultados_backtest_reais_para_montecarlo(self) -> list[dict] | None:
        """
        Extrai os resultados reais da última vitória do Backtest Científico
        (conhecimento_cientifico.json) para alimentar o Monte Carlo
        Científico com dados reais do robô.

        Antes, `executar_montecarlo_cientifico()` era sempre chamado sem
        `resultados_backtest`, então sempre caía no fallback sintético
        (`rng.gauss(0.3, 0.25)`) — mesmo quando já existia um Backtest
        Científico real rodado — e o painel mostrava P(Robô > Aleatório),
        IC 95%, Cohen's d e p-value calculados sobre números fabricados,
        contradizendo o próprio docstring do módulo (ver 2026-07-19 no
        ARQUITETURA.md). Retorna None se ainda não há nenhuma execução
        científica registrada — nesse caso o Monte Carlo cai no fallback
        sintético mesmo, mas agora isso é sinalizado na tela.
        """
        try:
            conhecimento = carregar_conhecimento_cientifico()
            ranking = conhecimento.get("ranking_configuracoes") or []
            if not ranking:
                return None
            ultimos = ranking[0].get("ultimos") or []
            resultados = [
                {"acertos": r.get("media_acertos", 0.0)}
                for r in ultimos if "media_acertos" in r
            ]
            return resultados or None
        except Exception:
            return None

    def _iniciar_progresso(self) -> None:
        if not self._progresso_visivel:
            self._progresso_visivel = True
            self._progresso.start(12)

    def _parar_progresso(self) -> None:
        if self._progresso_visivel:
            self._progresso_visivel = False
            self._progresso.stop()

    def _atualizar_painel_info(self) -> None:
        """Atualiza o mini painel de info no header e os cards premium."""
        try:
            n = self.total_concursos_csv or len(self.concursos)
            if n:
                self._lbl_concursos.config(text=f"Concursos: {n}", fg=TEMA["verde"])
            ult = self.obter_id_ultimo_concurso()
            if ult:
                self._lbl_ultimo.config(text=f"Último: #{ult}", fg=TEMA["accent"])
            mem = carregar_memoria_aprendizado()
            regs = mem.get("registros", [])
            nreg = len(regs)
            cor = TEMA["verde"] if nreg > 0 else TEMA["fg2"]
            self._lbl_memoria.config(text=f"Memória IA: {nreg} reg.", fg=cor)

            cards = getattr(self, "_cards_dashboard", {})
            def set_card(nome, valor, sub=None):
                if nome in cards:
                    lbl, lbl_sub = cards[nome]
                    lbl.config(text=str(valor))
                    if sub is not None:
                        lbl_sub.config(text=str(sub))

            set_card("📚 Base", n if n else "—", f"último #{ult}" if ult else "concursos carregados")
            set_card("🧠 Memória IA", nreg, "registro(s) salvos")
            set_card("🎲 Jogos", len(self.jogos_gerados) if self.jogos_gerados else "—", "último pacote gerado")
            if regs:
                ult_reg = regs[-1]
                set_card("🏆 Melhor", ult_reg.get("melhor_acerto", "—"), f"média {ult_reg.get('media_acertos', '—')}")
            else:
                set_card("🏆 Melhor", "—", "sem conferência ainda")
            set_card("🧪 Simulador", "ativo", "auditoria do pacote")
        except Exception:
            pass

    def log(self, texto: str = "") -> None:
        tag = "normal"
        t = texto.strip()
        if t.startswith("✅") or t.startswith("💾") or t.startswith("🧠"):
            tag = "ok"
        elif t.startswith("❌"):
            tag = "erro"
        elif t.startswith("⚠️") or t.startswith("⚠"):
            tag = "aviso"
        elif t.startswith("===") or t.startswith("GERAÇÃO") or t.startswith("BACKTEST") or t.startswith("CARREGAMENTO") or t.startswith("ATUALIZAÇÃO"):
            tag = "titulo"
        self.txt_saida.insert("end", texto + "\n", tag)
        self.txt_saida.see("end")
        self.root.update_idletasks()

    def set_status(self, texto: str, cor: str = "blue") -> None:
        self.lbl_status.config(text=texto, foreground=cor)
        self.root.update_idletasks()

    def log_async(self, texto: str = "") -> None:
        """Atualiza o campo de log com segurança quando chamado por uma thread."""
        try:
            self.root.after(0, lambda: self.log(texto))
        except Exception:
            try:
                self.log(texto)
            except Exception:
                pass

    def set_status_async(self, texto: str, cor: str = "blue") -> None:
        """Atualiza o status com segurança quando chamado por uma thread."""
        try:
            self.root.after(0, lambda: self.set_status(texto, cor))
        except Exception:
            try:
                self.set_status(texto, cor)
            except Exception:
                pass

    def calcular_limite_turbo(self) -> int | None:
        janela = max(MIN_HIST, int(self.janela_hist.get()))
        passos = max(10, int(self.passos_backtest.get()))
        margem = 20
        return max(janela + passos + margem, MIN_HIST)

    def selecionar_csv(self) -> None:
        # Usa a caixa de "salvar" (não "abrir") de propósito: este campo é
        # compartilhado por Carregar E por Atualizar (que pode criar um CSV
        # novo num caminho que ainda não existe) — askopenfilename exigiria
        # um arquivo já existente. `confirmoverwrite=False` evita o aviso
        # de "sobrescrever?" ao reselecionar o CSV atual, que não faz
        # sentido aqui já que nada está sendo salvo neste momento (achado
        # de auditoria, ver 2026-07-23 no ARQUITETURA.md).
        caminho = filedialog.asksaveasfilename(
            title="Escolha o CSV de resultados",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos os arquivos", "*.*")],
            initialfile=os.path.basename(self.caminho_csv.get() or ARQUIVO_CSV_PADRAO),
            confirmoverwrite=False,
        )
        if caminho:
            self.caminho_csv.set(caminho)

    def iniciar_atualizar_resultados(self) -> None:
        """Lança atualizar_resultados_reais em thread para não travar a UI."""
        if getattr(self, "_atualizando", False):
            self.log("⚠️ Atualização já em andamento.")
            return
        self._atualizando = True
        threading.Thread(target=self._executar_atualizar_resultados, daemon=True).start()

    def _executar_atualizar_resultados(self) -> None:
        """Executa download e atualização em thread separada."""
        try:
            self.atualizar_resultados_reais()
        finally:
            self._atualizando = False

    def atualizar_resultados_reais(self) -> None:
        # Roda em thread de fundo (iniciar_atualizar_resultados) — usa apenas
        # chamadas thread-safe (_async / root.after), como os demais handlers
        # threaded do arquivo (ver 2026-07-19 no ARQUITETURA.md).
        try:
            self.set_status_async("Atualizando resultados reais...", "blue")
            self.log_async("=" * 72)
            self.log_async("ATUALIZAÇÃO AUTOMÁTICA")
            self.log_async(f"Arquivo de saída: {self.caminho_csv.get().strip()}")

            caminho, total, origem, novos, info_salvamento = baixar_e_exportar_historico_ultra(
                caminho_saida=self.caminho_csv.get().strip(),
                caminho_cache=ARQUIVO_CACHE,
                status_cb=self.log_async,
            )
            self.log_async(f"✅ Atualização concluída. Origem: {origem}")
            self.log_async(f"Total de concursos no CSV: {total}")
            self.log_async(f"Concursos novos adicionados nesta execução: {novos}")
            self.log_async(f"Arquivo salvo em: {caminho}")
            if info_salvamento.get('backup'):
                self.log_async(f"Backup criado em: {info_salvamento['backup']}")
            if info_salvamento.get('alternativo'):
                self.log_async("⚠️ O arquivo principal estava bloqueado. Os dados foram salvos em arquivo alternativo.")
                self.log_async(f"Motivo: {info_salvamento.get('erro_principal', 'arquivo em uso')}")
                self.root.after(0, lambda: self.caminho_csv.set(caminho))
                self.set_status_async("Atualizado em arquivo alternativo por bloqueio do principal.", "orange")
            else:
                self.set_status_async("Resultados reais atualizados com sucesso.", "green")
        except PermissionError as e:
            self.set_status_async("Erro de permissão ao salvar CSV.", "red")
            self.log_async("❌ Arquivo CSV está bloqueado ou sem permissão de escrita.")
            self.log_async(str(e))
            self.log_async("Feche o Excel/LibreOffice se o CSV estiver aberto e tente novamente.")
        except Exception as e:
            self.set_status_async("Erro ao atualizar resultados reais.", "red")
            self.log_async("❌ Erro ao atualizar resultados reais:")
            self.log_async(str(e))
            self.log_async(traceback.format_exc())

    def iniciar_carregar_historico(self) -> None:
        """Lança carregar_historico em thread para não travar a UI."""
        if getattr(self, "_carregando", False):
            self.log("⚠️ Carregamento já em andamento.")
            return
        self._carregando = True
        threading.Thread(target=self._executar_carregar_historico, daemon=True).start()

    def _executar_carregar_historico(self) -> None:
        """Executa leitura do CSV em thread separada."""
        try:
            self.carregar_historico()
        finally:
            self._carregando = False

    def carregar_historico(self) -> None:
        # Roda em thread de fundo (iniciar_carregar_historico) — mesma
        # observação de thread-safety de atualizar_resultados_reais.
        try:
            self.root.after(0, self._iniciar_progresso)
            self.set_status_async("Carregando histórico...", "blue")
            self.log_async("=" * 72)
            self.log_async("CARREGAMENTO DE HISTÓRICO")
            limite = self.calcular_limite_turbo() if self.modo_turbo.get() else None
            self.concursos, self.df_csv, self.total_concursos_csv = carregar_concursos_do_csv(self.caminho_csv.get().strip(), limite=limite)
            self.log_async(f"CSV carregado: {self.caminho_csv.get().strip()}")
            self.log_async(f"Base completa no disco: {self.total_concursos_csv} concursos")
            if self.modo_turbo.get():
                self.log_async(f"Modo turbo ativo: memória carregada com os últimos {len(self.concursos)} concursos")
                self.log_async(f"Janela atual de análise: últimos {min(int(self.janela_hist.get()), len(self.concursos))} concursos")
            else:
                self.log_async(f"Concursos válidos em memória: {len(self.concursos)}")
            self.log_async(f"Primeiro concurso: {formatar_jogo(self.concursos[0])}")
            self.log_async(f"Último concurso:   {formatar_jogo(self.concursos[-1])}")
            self.avaliar_ultimo_sorteio_automatico()
            self.iniciar_aprendizado_automatico_pos_carga()
            self.root.after(0, self._parar_progresso)
            self.root.after(0, self._atualizar_painel_info)
            self.set_status_async("Histórico carregado com sucesso.", "green")
        except Exception as e:
            self.root.after(0, self._parar_progresso)
            self.set_status_async("Erro ao carregar histórico.", "red")
            self.log_async("❌ Erro ao carregar histórico:")
            self.log_async(str(e))
            self.log_async(traceback.format_exc())


    def iniciar_gerar_jogos(self) -> None:
        """Lança gerar_jogos em thread separada para não travar a UI."""
        if getattr(self, "_geracao_ativa", False):
            self.log("⚠️ Geração já em andamento. Aguarde.")
            self.set_status("Geração em andamento...", "blue")
            return
        self._geracao_ativa = True
        th = threading.Thread(target=self._executar_gerar_jogos, daemon=True)
        th.start()

    def _atualizar_progresso(self, valor: float, texto: str = "") -> None:
        """Atualiza a barra de progresso de forma thread-safe (0–100)."""
        def _update():
            try:
                self._progresso["value"] = max(0, min(100, valor))
                if texto:
                    self.set_status(texto, "blue")
            except Exception:
                pass
        self.root.after(0, _update)

    def gerar_jogos(self) -> None:
        """Atalho de compatibilidade — redireciona para iniciar_gerar_jogos."""
        self.iniciar_gerar_jogos()

    def _executar_gerar_jogos(self) -> None:
        """Executa a geração de jogos em thread separada com progresso determinado."""
        try:
            if not self.concursos:
                limite = self.calcular_limite_turbo() if self.modo_turbo.get() else None
                self.concursos, self.df_csv, self.total_concursos_csv = carregar_concursos_do_csv(self.caminho_csv.get().strip(), limite=limite)

            # Atualiza TAMANHO_JOGO globalmente conforme campo da UI (15–18)
            _config_module.TAMANHO_JOGO = min(max(15, int(self.tamanho_jogo.get())), 18)

            qtd = min(max(1, int(self.qtd_jogos.get())), 100)
            janela = min(max(MIN_HIST, int(self.janela_hist.get())), len(self.concursos))
            ger = min(max(5, int(self.geracoes.get())), 2000)
            pop = min(max(20, int(self.pop_size.get())), 1000)

            self.root.after(0, self._iniciar_progresso)
            self._atualizar_progresso(5, "Analisando histórico...")
            self.log("=" * 72)
            self.log("GERAÇÃO DE JOGOS")
            self._aplicar_seed_configurada()
            aprendizado_previo = calcular_bonus_aprendizado()
            self.log("Memória IA: " + aprendizado_previo.get("resumo", "Sem registros anteriores."))
            base_total = getattr(self, "total_concursos_csv", len(self.concursos))
            self.log(f"Base completa no disco: {base_total} concursos")
            self.log(f"Concursos carregados em memória: {len(self.concursos)}")
            self.log(f"Analisando apenas os últimos: {janela} concursos")
            self.log(f"Jogos={qtd} | Gerações={ger} | População={pop}")

            # V21.6 — injeta peso_impopularidade na estratégia via override
            peso_imp_ui = round(self.peso_impopularidade.get() / 100.0, 2)
            _override_imp = {"peso_impopularidade": peso_imp_ui}
            if peso_imp_ui > 0:
                self.log(f"📊 Impopularidade ativa: {self.peso_impopularidade.get()}% — favorecendo combinações sub-apostadas por humanos.")
            else:
                self.log("📊 Impopularidade desligada (slider em 0%).")

            self._atualizar_progresso(30, "Rodando ensemble multi-IA...")
            self.jogos_gerados, self.analise, self.pesos = gerar_apostas(
                self.concursos,
                qtd_jogos=qtd,
                janela_analise=janela,
                geracoes=ger,
                pop_size=pop,
                estrategia_override=_override_imp,
            )

            self._atualizar_progresso(70, "Selecionando pacote final...")
            self.info_backtest = None
            estrategia = self.analise.get("estrategia", {}) if self.analise else {}
            if estrategia:
                self.log("MOTOR ESTRATÉGICO INTELIGENTE")
                self.log(f"Modo escolhido: {estrategia.get('modo', 'equilibrado').upper()}")
                self.log(f"Índice de confiança: {estrategia.get('indice_confianca', 0):.3f}")
                self.log(f"Estabilidade={estrategia.get('estabilidade', 0):.3f} | Concentração={estrategia.get('concentracao', 0):.3f} | Diversidade={estrategia.get('diversidade', 0):.3f}")
                self.log(f"Taxa de mutação={estrategia.get('taxa_mutacao', 0):.3f} | Limite de interseção={estrategia.get('limite_intersecao', 12)}")
            ensemble = self.analise.get("ensemble", {}) if self.analise else {}
            if ensemble:
                self.log("-" * 72)
                self.log("ENSEMBLE MULTI-IA ADAPTATIVO")
                conf = ensemble.get("confianca_modelos", {})
                self.log(", ".join(f"{nome}={peso:.2f}" for nome, peso in conf.items()))
                top_ens = sorted(self.pesos.items(), key=lambda x: x[1], reverse=True)[:10]
                self.log("Top 10 pesos finais: " + ", ".join(f"{n:02d} ({p:.4f})" for n, p in top_ens))
            cobertura = self.analise.get("cobertura_global", {}) if self.analise else {}
            perf_reg = registrar_performance_geracao(self.jogos_gerados, self.analise, ger, pop, janela, qtd)
            if perf_reg:
                self.log("💾 Performance técnica registrada no banco interno de estratégias.")
            if cobertura:
                self.log("-" * 72)
                self.log("COBERTURA INTELIGENTE GLOBAL")
                self.log(f"Sobreposição média entre jogos: {cobertura.get('media_sobreposicao', 0)}")
                self.log(f"Sobreposição mínima/máxima: {cobertura.get('min_sobreposicao', 0)} / {cobertura.get('max_sobreposicao', 0)}")
                self.log(f"Média de soma do pacote: {cobertura.get('media_soma', 0)} | Média de pares: {cobertura.get('media_pares', 0)}")
                mais = cobertura.get('dezenas_mais_cobertas', [])
                menos = cobertura.get('dezenas_menos_cobertas', [])
                if mais:
                    self.log("Mais cobertas: " + ", ".join(f"{n:02d}({q})" for n, q in mais))
                if menos:
                    self.log("Menos cobertas: " + ", ".join(f"{n:02d}({q})" for n, q in menos))
                ref = cobertura.get("refinamento_matematico") or {}
                if ref:
                    self.log("REFINAMENTO MATEMÁTICO ESTRUTURAL")
                    self.log(f"Score estrutural médio: {ref.get('score_estrutural_medio')} | Entropia média: {ref.get('entropia_media')}")
                    self.log(f"Estruturas fortes/boas: {ref.get('jogos_estrutura_forte_ou_boa')} | Fracas: {ref.get('jogos_estrutura_fraca')}")
                ref_ag = cobertura.get("refinamento_agressivo") or {}
                if ref_ag.get("ativo"):
                    self.log("REFINAMENTO MATEMÁTICO AGRESSIVO")
                    self.log(
                        f"Filtro pré-seleção: aprovados={ref_ag.get('aprovados')} | rejeitados={ref_ag.get('rejeitados')} | "
                        f"score mínimo={ref_ag.get('score_minimo')} | fallback={ref_ag.get('fallback_usado')}"
                    )
            aprendizado = self.analise.get("aprendizado", {}) if self.analise else {}
            if aprendizado:
                self.log("-" * 72)
                self.log("APRENDIZADO PERMANENTE")
                self.log(aprendizado.get("resumo", "Sem memória de desempenho."))
                if aprendizado.get("tem_memoria"):
                    self.log(f"Ajustes: diversidade={aprendizado.get('ajuste_diversidade', 0):+.3f} | mutação={aprendizado.get('ajuste_mutacao', 0):+.3f} | elite={aprendizado.get('ajuste_elite', 0):+.3f}")
            lab = self.analise.get("laboratorio_inteligente", {}) if self.analise else {}
            if lab.get("ativo"):
                self.log("-" * 72)
                self.log("RESULTADO DO MODO LABORATÓRIO INTELIGENTE")
                vencedor = lab.get("configuracao_vencedora", {})
                self.log(
                    f"Vencedor: {vencedor.get('nome', '')} | "
                    f"Gerações={vencedor.get('geracoes', '')} | "
                    f"População={vencedor.get('pop_size', '')} | "
                    f"Score laboratório={vencedor.get('score_laboratorio', '')}"
                )
                self.log("Configurações testadas:")
                for r in lab.get("resultados_testados", []):
                    self.log(
                        f"- {r.get('nome')}: G={r.get('geracoes')} | P={r.get('pop_size')} | "
                        f"Score={r.get('score_laboratorio')} | Sobrep. média={r.get('media_sobreposicao')} | Tempo={r.get('tempo_segundos')}s"
                    )
            self.log("✅ Jogos gerados com sucesso.")
            for row in avaliar_jogos(self.jogos_gerados, self.analise, self.pesos):
                self.log(
                    f"Jogo {row['Jogo']:02d}: {row['Dezenas']} | "
                    f"Pares={row['Pares']} | Ímpares={row['Ímpares']} | "
                    f"Soma={row['Soma']} | Perfil={row.get('Perfil', '')} | Score={row['Score']}"
                )
            self.salvar_ultimos_jogos_gerados()
            self._atualizar_progresso(100, "Concluído!")
            self.root.after(0, self._parar_progresso)
            self.root.after(0, self._atualizar_tabela_jogos)
            self.root.after(0, self._atualizar_painel_info)
            self.set_status_async("Jogos gerados com sucesso.", "green")
        except Exception as e:
            self.root.after(0, self._parar_progresso)
            self.set_status_async("Erro ao gerar jogos.", "red")
            self.log_async("❌ Erro ao gerar jogos:")
            self.log_async(str(e))
            self.log_async(traceback.format_exc())
        finally:
            self._geracao_ativa = False
            self.root.after(0, lambda: self._progresso.configure(value=0))

    # ── Fechamento combinatório (V22.1 experimental) ──────────────────────
    def iniciar_fechamento(self) -> None:
        """Lança o fechamento combinatório em thread separada."""
        if getattr(self, "_fechamento_ativo", False):
            self.log("⚠️ Fechamento já em andamento. Aguarde.")
            self.set_status("Fechamento em andamento...", "blue")
            return
        if not self.concursos:
            self.log("⚠️ Carregue o histórico antes de gerar o fechamento.")
            messagebox.showwarning("Fechamento", "Carregue o histórico (📂 Carregar) antes de gerar o fechamento.")
            return

        try:
            tamanho_pool = int(self.tamanho_pool_fechamento.get())
        except Exception:
            tamanho_pool = TAMANHO_POOL_MINIMO
        if not (TAMANHO_POOL_MINIMO <= tamanho_pool <= TAMANHO_POOL_MAXIMO):
            messagebox.showerror(
                "Fechamento",
                f"Pool Fecht. precisa estar entre {TAMANHO_POOL_MINIMO} e {TAMANHO_POOL_MAXIMO} "
                f"(recebido: {tamanho_pool})."
            )
            return

        qtd = qtd_jogos_fechamento(tamanho_pool)
        if tamanho_pool > TAMANHO_POOL_MINIMO:
            # Pools acima de 16 geram muitos jogos (136 a 15.504) — confirma
            # antes de gerar/exibir, já que cada jogo tem custo real se apostado.
            confirmado = messagebox.askyesno(
                "Fechamento — confirmar quantidade de jogos",
                f"Pool de {tamanho_pool} dezenas gera {qtd:,} jogos "
                f"(garantia mínima de {garantia_minima(tamanho_pool)} pontos SE as 15 dezenas "
                f"sorteadas estiverem todas dentro do pool escolhido).\n\n"
                f"Isso é MUITO mais que os 20 jogos do seu uso normal. Deseja continuar?"
            )
            if not confirmado:
                self.log("Fechamento cancelado pelo usuário (pool grande demais para o orçamento pretendido).")
                return

        self._fechamento_ativo = True
        self.set_status("Gerando fechamento combinatório...", "blue")
        self.log("=" * 72)
        self.log("🔒 FECHAMENTO COMBINATÓRIO — GARANTIA TOTAL")
        th = threading.Thread(target=self._executar_fechamento, args=(tamanho_pool,), daemon=True)
        th.start()

    def _executar_fechamento(self, tamanho_pool: int) -> None:
        try:
            janela = min(max(MIN_HIST, int(self.janela_hist.get())), len(self.concursos))
            self.root.after(0, self._iniciar_progresso)
            self._atualizar_progresso(20, "Escolhendo pool pelo ranking do ensemble...")

            resultado = gerar_apostas_fechamento(self.concursos, tamanho_pool=tamanho_pool, janela_analise=janela)

            self._atualizar_progresso(80, "Montando jogos do fechamento...")
            self.jogos_gerados = resultado["jogos"]
            self.analise = resultado["analise"]
            self.pesos = (self.analise.get("ensemble") or {}).get("pesos_finais", {})
            self.info_backtest = None

            self.log(f"Pool escolhido ({tamanho_pool} dezenas): {' '.join(f'{n:02d}' for n in resultado['pool'])}")
            self.log(f"Jogos no fechamento: {resultado['qtd_jogos']:,}")
            self.log(f"Garantia mínima SE as 15 sorteadas estiverem no pool: {resultado['garantia_minima']} pontos")
            self.log(
                "⚠️ A garantia é condicional: escolher quais dezenas entram no pool continua sendo uma "
                "aposta. O fechamento redistribui o resultado entre vários jogos, não muda a chance de "
                "acertar quais dezenas saem — ver VALIDACAO_ESCALA_REAL_2026-07-14.md."
            )
            self.log("-" * 72)
            limite_exibicao = 30
            for idx, jogo in enumerate(resultado["jogos"][:limite_exibicao], start=1):
                self.log(f"Jogo {idx:02d}: {formatar_jogo(jogo)}")
            if resultado["qtd_jogos"] > limite_exibicao:
                self.log(f"... e mais {resultado['qtd_jogos'] - limite_exibicao} jogos (todos em self.jogos_gerados / tabela de jogos).")

            self.salvar_ultimos_jogos_gerados()
            self._atualizar_progresso(100, "Concluído!")
            self.root.after(0, self._parar_progresso)
            self.root.after(0, self._atualizar_tabela_jogos)
            self.root.after(0, self._atualizar_painel_info)
            self.set_status_async("Fechamento gerado com sucesso.", "green")
        except Exception as e:
            self.root.after(0, self._parar_progresso)
            self.set_status_async("Erro ao gerar fechamento.", "red")
            self.log_async("❌ Erro ao gerar fechamento:")
            self.log_async(str(e))
            self.log_async(traceback.format_exc())
        finally:
            self._fechamento_ativo = False
            self.root.after(0, lambda: self._progresso.configure(value=0))


    def rodar_simulador_pacote(self) -> None:
        """Audita os jogos já gerados usando simulações artificiais e critérios estruturais."""
        try:
            if not self.jogos_gerados:
                messagebox.showwarning("Simulador", "Gere os jogos primeiro para depois rodar o simulador.")
                return

            self.set_status("Rodando simulador do pacote...", "blue")
            self.log("=" * 72)
            self.log("🧪 SIMULADOR / AUDITOR DE QUALIDADE DO PACOTE")
            self.log("Analisando estrutura, cobertura, diversidade e simulação artificial curta...")

            qtd_sim = 1000
            resultado = auditar_pacote_jogos(self.jogos_gerados, self.analise, qtd_simulacoes=qtd_sim)
            self.info_simulador = resultado
            relatorio = gerar_relatorio_simulador_pacote(resultado)

            self.log(relatorio)

            garantir_estrutura_pastas()
            caminho = os.path.join(PASTA_EXPORT, f"simulador_pacote_{gerar_timestamp_arquivo()}.txt")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(relatorio)

            self.log(f"💾 Relatório do simulador salvo em: {caminho}")
            self.set_status(f"Simulador concluído: {resultado.get('classificacao')} | Nota {resultado.get('nota_final')}/10", "green")
            messagebox.showinfo(
                "Simulador concluído",
                f"Classificação: {resultado.get('classificacao')}\n"
                f"Nota final: {resultado.get('nota_final')}/10\n\n"
                f"{resultado.get('recomendacao')}"
            )
        except Exception as e:
            self.set_status("Erro no simulador.", "red")
            self.log("❌ Erro no simulador:")
            self.log(str(e))
            self.log(traceback.format_exc())
            messagebox.showerror("Erro no simulador", str(e))

    def gerar_jogos_dual_perfil(self) -> None:
        """
        V21.5-FULL — Geração Dual-Perfil.
        Gera pacote misto automático: 70% consistência (11+/12+) + 30% exploração (13+).
        Executa em thread separada para não travar a UI.
        """
        if getattr(self, "_geracao_ativa", False):
            self.log("⚠️ Geração já em andamento. Aguarde.")
            self.set_status("Geração em andamento...", "blue")
            return
        self._geracao_ativa = True
        th = threading.Thread(target=self._executar_dual_perfil, daemon=True)
        th.start()

    def _executar_dual_perfil(self) -> None:
        """Thread do Dual-Perfil."""
        try:
            if not self.concursos:
                limite = self.calcular_limite_turbo() if self.modo_turbo.get() else None
                self.concursos, self.df_csv, self.total_concursos_csv = carregar_concursos_do_csv(
                    self.caminho_csv.get().strip(), limite=limite
                )

            qtd    = min(max(1, int(self.qtd_jogos.get())), 100)
            janela = min(max(MIN_HIST, int(self.janela_hist.get())), len(self.concursos))
            # Item 4: lê G e P (self.geracoes/self.pop_size, fixos em 16/40) em
            # vez de valores hardcoded, para que o Dual-Perfil honre a configuração validada.
            ger_ui = max(5,  int(self.geracoes.get()))
            pop_ui = max(20, int(self.pop_size.get()))

            # V21.6 — impopularidade também no Dual-Perfil
            peso_imp_ui = round(self.peso_impopularidade.get() / 100.0, 2)
            _override_imp = {"peso_impopularidade": peso_imp_ui}

            self.root.after(0, self._iniciar_progresso)
            self.log("=" * 72)
            self.log("🎯 GERAÇÃO DUAL-PERFIL V21.5-FULL")
            self._aplicar_seed_configurada()
            self.log(f"Total de jogos: {qtd} | Janela: {janela}")
            self.log(f"Perfil Consistência: {round(qtd * 0.70)} jogos — G={ger_ui} P={pop_ui} · otimizado para 11+/12+")
            self.log(f"Perfil Exploração:   {round(qtd * 0.30)} jogos — G=40 P=40 · Pares/Trios+Cobertura → 13+")
            if peso_imp_ui > 0:
                self.log(f"📊 Impopularidade: {self.peso_impopularidade.get()}% ativo em ambos os perfis.")
            else:
                self.log("📊 Impopularidade desligada (slider em 0%).")
            self.log("-" * 72)

            self._atualizar_progresso(15, "Gerando perfil consistência...")

            self.jogos_gerados, self.analise, self.pesos = gerar_apostas_dual_perfil(
                self.concursos,
                qtd_jogos=qtd,
                janela_analise=janela,
                geracoes_consistencia=ger_ui,
                pop_consistencia=pop_ui,
                fracao_exploracao=0.30,
                status_cb=self.log,
                estrategia_override=_override_imp,
            )

            self._atualizar_progresso(80, "Finalizando pacote dual...")
            self.info_backtest = None

            # Exibe resumo dual-perfil
            rel_dp = relatorio_dual_perfil(self.analise)
            if rel_dp:
                self.log(rel_dp)

            # Exibe ensemble e cobertura normalmente
            ensemble = self.analise.get("ensemble", {}) if self.analise else {}
            if ensemble:
                self.log("-" * 72)
                self.log("ENSEMBLE MULTI-IA (Perfil Consistência)")
                conf = ensemble.get("confianca_modelos", {})
                self.log(", ".join(f"{nome}={peso:.2f}" for nome, peso in conf.items()))

            cobertura = self.analise.get("cobertura_global", {}) if self.analise else {}
            if cobertura:
                self.log("-" * 72)
                self.log(f"COBERTURA FINAL — Sobrep. média: {cobertura.get('media_sobreposicao', 0)}"
                         f" | mín/máx: {cobertura.get('min_sobreposicao', 0)}"
                         f"/{cobertura.get('max_sobreposicao', 0)}")

            self.salvar_ultimos_jogos_gerados()
            self._atualizar_progresso(95, "Exibindo jogos...")
            self.root.after(0, self._atualizar_tabela_jogos)
            self.root.after(0, self._atualizar_painel_info)
            self._atualizar_progresso(100, "✅ Dual-Perfil concluído.")
            self.log("✅ Pacote Dual-Perfil gerado com sucesso.")
            self.set_status("✅ Dual-Perfil concluído.", "green")

        except Exception as e:
            self.log(f"❌ Erro no Dual-Perfil: {e}")
            self.set_status("Erro no Dual-Perfil.", "red")
            import traceback
            self.log(traceback.format_exc())
        finally:
            self._geracao_ativa = False
            self.root.after(0, self._parar_progresso)

    def iniciar_calibracao_vs_aleatorio(self) -> None:
        """Compara o robo contra pacotes aleatorios em concursos passados."""
        try:
            if getattr(self, "calibracao_ativa", False):
                self.log("⚠️ A calibração já está em execução.")
                self.set_status("Calibração já em execução.", "blue")
                return
            self.calibracao_ativa = True
            self.set_status("Iniciando calibração...", "blue")
            self.log("=" * 72)
            self.log("CALIBRAÇÃO ROBO VS ALEATÓRIO INICIADA")
            self.log("O robô será comparado com pacotes aleatórios usando concursos passados.")
            th = threading.Thread(target=self.executar_calibracao_vs_aleatorio, daemon=True)
            self.thread_calibracao = th
            th.start()
        except Exception as e:
            self.calibracao_ativa = False
            self.set_status("Erro ao iniciar calibração.", "red")
            self.log(f"❌ Erro ao iniciar calibração: {e}")

    def executar_calibracao_vs_aleatorio(self) -> None:
        try:
            # FIX V11: calibração também usa Passos Backtest; por isso recarrega
            # a base conforme a configuração atual do Modo Turbo.
            limite = self.calcular_limite_turbo() if self.modo_turbo.get() else None
            self.concursos, self.df_csv, self.total_concursos_csv = carregar_concursos_do_csv(
                self.caminho_csv.get().strip(), limite=limite
            )

            janela = int(self.janela_hist.get())
            passos = int(self.passos_backtest.get())
            qtd = min(max(5, int(self.qtd_jogos.get())), 100)
            ger = max(5, int(self.geracoes.get()))
            pop = max(20, int(self.pop_size.get()))

            self.root.after(0, self._iniciar_progresso)
            self._aplicar_seed_configurada(log_async=True)
            self.log_async(f"Configuração calibração: passos={passos} | janela={janela} | jogos={qtd} | G={ger} | P={pop}")
            resultado = calibrar_robo_vs_aleatorio(
                self.concursos,
                janela=janela,
                qtd_jogos=qtd,
                passos=passos,
                geracoes=ger,
                pop_size=pop,
                status_cb=self.log_async,
            )
            self.info_calibracao = resultado

            robo = resultado.get("resumo_robo", {})
            aleatorio = resultado.get("resumo_aleatorio", {})
            self.log_async("✅ Calibração concluída.")
            self.log_async(
                f"Robô: pacotes 11+={robo.get('pct_pacotes_11_mais', 0)}% | "
                f"12+={robo.get('pct_pacotes_12_mais', 0)}% | média melhor={robo.get('media_melhor', 0)}"
            )
            self.log_async(
                f"Aleatório: pacotes 11+={aleatorio.get('pct_pacotes_11_mais', 0)}% | "
                f"12+={aleatorio.get('pct_pacotes_12_mais', 0)}% | média melhor={aleatorio.get('media_melhor', 0)}"
            )
            self.log_async(
                f"Vitórias por score: robô={resultado.get('robo_venceu_score', 0)} | "
                f"aleatório={resultado.get('aleatorio_venceu_score', 0)} | "
                f"empates={resultado.get('empates_score', 0)}"
            )
            self.log_async(f"Relatório TXT salvo em: {resultado.get('arquivo_txt', '')}")
            if resultado.get("arquivo_csv"):
                self.log_async(f"Planilha CSV salva em: {resultado.get('arquivo_csv')}")
            # V21.5: armazena resultado para Análise Científica V2
            self._ultimo_resultado_calibracao = resultado
            self.set_status_async("Calibração concluída com sucesso.", "green")
        except Exception as e:
            self.set_status_async("Erro na calibração.", "red")
            self.log_async("❌ Erro na calibração:")
            self.log_async(str(e))
            self.log_async(traceback.format_exc())
        finally:
            self.calibracao_ativa = False
            try:
                self.root.after(0, self._parar_progresso)
            except Exception:
                pass

    def iniciar_backtest_cientifico_v11(self) -> None:
        """Executa a camada científica V11 em thread para não travar a interface."""
        try:
            if getattr(self, "backtest_cientifico_ativo", False):
                self.log("⚠️ O Backtest Científico já está em execução.")
                self.set_status("Backtest Científico já em execução.", "blue")
                return
            self.backtest_cientifico_ativo = True
            self.set_status("Iniciando Backtest Científico...", "blue")
            self.log("=" * 72)
            self.log("🧪 BACKTEST CIENTÍFICO INICIADO")
            self.log("Inclui: backtest massivo, competição de modelos, autocalibração e banco de conhecimento.")
            th = threading.Thread(target=self.executar_backtest_cientifico_v11, daemon=True)
            self.thread_backtest_cientifico = th
            th.start()
        except Exception as e:
            self.backtest_cientifico_ativo = False
            self.set_status("Erro ao iniciar Backtest Científico.", "red")
            self.log(f"❌ Erro ao iniciar Backtest Científico: {e}")

    def executar_backtest_cientifico_v11(self) -> None:
        try:
            # Sempre recarrega o CSV para o V11 — garante que o estado atual
            # do Modo Turbo seja respeitado, mesmo que concursos ja estivessem
            # em memoria de uma execucao anterior com outra configuracao.
            limite = self.calcular_limite_turbo() if self.modo_turbo.get() else None
            self.concursos, self.df_csv, self.total_concursos_csv = carregar_concursos_do_csv(
                self.caminho_csv.get().strip(), limite=limite
            )
            self.log_async(
                f"[V11] CSV recarregado: {len(self.concursos)} concursos | "
                f"Turbo={'sim' if self.modo_turbo.get() else 'NAO'}"
            )
            janela = int(self.janela_hist.get())
            passos = int(self.passos_backtest.get())
            qtd = min(max(5, int(self.qtd_jogos.get())), 100)
            ger = max(10, int(self.geracoes.get()))
            pop = max(30, int(self.pop_size.get()))
            self.root.after(0, self._iniciar_progresso)
            self._aplicar_seed_configurada(log_async=True)
            self.log_async(f"Configuração Científica: passos={passos} | janela={janela} | jogos={qtd} | G={ger} | P={pop}")
            resultado = executar_backtest_cientifico_massivo(
                self.concursos,
                janela=janela,
                qtd_jogos=qtd,
                passos=passos,
                geracoes=ger,
                pop_size=pop,
                status_cb=self.log_async,
            )
            self.info_backtest_cientifico = resultado
            rec = resultado.get("recomendacao") or {}
            self.log_async("✅ Backtest Científico concluído.")
            self.log_async(f"Configuração campeã: {rec.get('estrategia_base')} | G={rec.get('geracoes')} | P={rec.get('pop_size')}")
            self.log_async(f"Modelo campeão: {rec.get('modelo_campeao')}")
            self.log_async(f"Relatório TXT salvo em: {resultado.get('arquivo_relatorio', '')}")
            self.log_async(f"Conhecimento salvo em: {resultado.get('arquivo_conhecimento', '')}")
            self.set_status_async("Backtest Científico concluído.", "green")
            try:
                messagebox.showinfo(
                    "Backtest Científico",
                    "Backtest Científico concluído!\n\n"
                    f"Configuração campeã: {rec.get('estrategia_base')}\n"
                    f"G={rec.get('geracoes')} | P={rec.get('pop_size')}\n\n"
                    f"Relatório:\n{resultado.get('arquivo_relatorio', '')}"
                )
            except Exception:
                pass
        except Exception as e:
            self.set_status_async("Erro no Backtest Científico.", "red")
            self.log_async("❌ Erro no Backtest Científico:")
            self.log_async(str(e))
            self.log_async(traceback.format_exc())
        finally:
            self.backtest_cientifico_ativo = False
            try:
                self.root.after(0, self._parar_progresso)
            except Exception:
                pass

    def iniciar_auto_diagnostico(self) -> None:
        """Roda calibracao e comparador em sequencia."""
        try:
            if getattr(self, "auto_diagnostico_ativo", False):
                self.log("⚠️ O Auto Diagnóstico já está em execução.")
                self.set_status("Auto Diagnóstico já em execução.", "blue")
                return
            self.auto_diagnostico_ativo = True
            self.set_status("Iniciando Auto Diagnóstico...", "blue")
            self.log("=" * 72)
            self.log("AUTO DIAGNÓSTICO INICIADO")
            self.log("Será executado: Calibrar IA e Comparador de Estratégias.")
            th = threading.Thread(target=self.executar_auto_diagnostico, daemon=True)
            self.thread_auto_diagnostico = th
            th.start()
        except Exception as e:
            self.auto_diagnostico_ativo = False
            self.set_status("Erro ao iniciar Auto Diagnóstico.", "red")
            self.log(f"❌ Erro ao iniciar Auto Diagnóstico: {e}")

    def executar_auto_diagnostico(self) -> None:
        try:
            if not self.concursos:
                limite = self.calcular_limite_turbo() if self.modo_turbo.get() else None
                self.concursos, self.df_csv, self.total_concursos_csv = carregar_concursos_do_csv(
                    self.caminho_csv.get().strip(), limite=limite
                )

            janela = int(self.janela_hist.get())
            passos = int(self.passos_backtest.get())
            qtd = min(max(5, int(self.qtd_jogos.get())), 30)
            ger = max(5, int(self.geracoes.get()))
            pop = max(20, int(self.pop_size.get()))

            self.root.after(0, self._iniciar_progresso)
            self._aplicar_seed_configurada(log_async=True)
            self.log_async(f"Configuração Auto Diagnóstico: passos={passos} | janela={janela} | jogos={qtd} | G={ger} | P={pop}")
            resultado = executar_auto_diagnostico_lotofacil(
                self.concursos,
                janela=janela,
                qtd_jogos=qtd,
                passos=passos,
                geracoes=ger,
                pop_size=pop,
                status_cb=self.log_async,
            )
            self.info_auto_diagnostico = resultado

            calibracao = resultado.get("calibracao") or {}
            comparador = resultado.get("comparador") or []
            robo = calibracao.get("resumo_robo", {})
            vencedor_comp = comparador[0] if comparador else {}

            self.log_async("✅ Auto Diagnóstico concluído.")
            self.log_async(
                f"Calibração: robô pacotes 11+={robo.get('pct_pacotes_11_mais', 0)}% | "
                f"12+={robo.get('pct_pacotes_12_mais', 0)}% | vantagem score={calibracao.get('vantagem_media_score', 0)}"
            )
            if vencedor_comp:
                self.log_async(
                    f"Comparador vencedor: {vencedor_comp.get('nome', '')} | "
                    f"score={vencedor_comp.get('score_ponderado', 0)} | "
                    f">=11={vencedor_comp.get('pct_11_mais', 0)}%"
                )
            self.log_async(f"Resumo final salvo em: {resultado.get('arquivo_txt', '')}")
            self.set_status_async("Auto Diagnóstico concluído com sucesso.", "green")
        except Exception as e:
            self.set_status_async("Erro no Auto Diagnóstico.", "red")
            self.log_async("❌ Erro no Auto Diagnóstico:")
            self.log_async(str(e))
            self.log_async(traceback.format_exc())
        finally:
            self.auto_diagnostico_ativo = False
            try:
                self.root.after(0, self._parar_progresso)
            except Exception:
                pass

    def iniciar_backtest_automatico(self) -> None:
        """Executa o backtest automático em thread para não travar a tela."""
        try:
            if getattr(self, "backtest_automatico_ativo", False):
                self.log("⚠️ O Backtest Automático já está em execução.")
                self.set_status("Backtest Automático já em execução.", "blue")
                return
            self.backtest_automatico_ativo = True
            self.set_status("Iniciando Backtest Automático...", "blue")
            self.log("=" * 72)
            self.log("🤖 BACKTEST AUTOMÁTICO INICIADO")
            self.log("O robô vai gerar jogos usando concursos anteriores e comparar com o resultado real seguinte.")
            th = threading.Thread(target=self.executar_backtest_automatico, daemon=True)
            self.thread_backtest_automatico = th
            th.start()
        except Exception as e:
            self.backtest_automatico_ativo = False
            self.set_status("Erro ao iniciar Backtest Automático.", "red")
            self.log(f"❌ Erro ao iniciar Backtest Automático: {e}")

    def executar_backtest_automatico(self) -> None:
        """
        Backtest automático detalhado.
        Usa somente concursos anteriores como base de treino, gera os jogos, confere contra
        o concurso real seguinte e salva relatório TXT + CSV em exportações.
        """
        try:
            # FIX V11: recarrega sempre o histórico antes do backtest automático.
            # Assim alterações em Passos Backtest / Janela Histórica / Modo Turbo
            # passam a valer imediatamente, sem ficar preso ao histórico antigo em memória.
            limite = self.calcular_limite_turbo() if self.modo_turbo.get() else None
            self.concursos, self.df_csv, self.total_concursos_csv = carregar_concursos_do_csv(
                self.caminho_csv.get().strip(), limite=limite
            )

            total = len(self.concursos or [])
            if total < MIN_HIST + 10:
                raise ValueError(
                    f"Histórico insuficiente para Backtest Automático: {total} concursos. "
                    f"Use ao menos {MIN_HIST + 10} concursos ou desligue o modo turbo."
                )

            janela_digitada = int(self.janela_hist.get())
            passos_digitados = int(self.passos_backtest.get())
            qtd = min(max(5, int(self.qtd_jogos.get())), 100)
            ger = max(5, int(self.geracoes.get()))
            pop = max(20, int(self.pop_size.get()))
            self._aplicar_seed_configurada(log_async=True)

            janela_maxima_segura = max(MIN_HIST, total - 5)
            janela = min(max(MIN_HIST, janela_digitada), janela_maxima_segura)
            passos_maximos = max(1, total - janela)
            passos = min(max(1, passos_digitados), passos_maximos)
            inicio = max(janela, total - passos)
            total_testes = total - inicio

            resumo = Counter()
            melhores = []
            medias = []
            linhas_txt = []
            linhas_csv = []
            # V21.5-FULL/V20.2 (2026-07-23): BT Automático nunca alimentava a
            # poda inteligente/ELO, diferente de "📊 Backtest" que faz o
            # mesmo tipo de trabalho (gera jogos a partir de histórico
            # passado e confere contra o resultado real seguinte) — ver
            # ARQUITETURA.md. `registros_poda` acumula os acertos por modelo
            # de cada passo pra alimentar alimentar_poda_e_elo() no final.
            registros_poda = []

            base_total = getattr(self, "total_concursos_csv", total)
            linhas_txt.append("===== BACKTEST AUTOMÁTICO LOTOFÁCIL =====")
            linhas_txt.append(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            linhas_txt.append(f"Base completa no disco: {base_total} concursos")
            linhas_txt.append(f"Concursos carregados em memória: {total}")
            linhas_txt.append(f"Concursos testados: {total_testes}")
            linhas_txt.append(f"Janela histórica: {janela}")
            linhas_txt.append(f"Jogos por concurso: {qtd}")
            linhas_txt.append(f"Gerações: {ger}")
            linhas_txt.append(f"População: {pop}")
            linhas_txt.append(f"Seed: {'fixa (' + str(_config_module.SEED) + ')' if _config_module.SEED is not None else 'aleatória'}")
            linhas_txt.append("")

            self.log_async(f"Configuração: testes={total_testes} | janela={janela} | jogos={qtd} | G={ger} | P={pop}")

            for pos, i in enumerate(range(inicio, total), start=1):
                base_passada = self.concursos[:i]
                resultado_real = sorted(self.concursos[i])
                concurso_id = i + 1
                try:
                    if self.df_csv is not None and not self.df_csv.empty and "concurso" in self.df_csv.columns:
                        concurso_id = int(self.df_csv["concurso"].iloc[i])
                except Exception:
                    concurso_id = i + 1

                jogos, analise, pesos = gerar_apostas(
                    base_passada,
                    qtd_jogos=qtd,
                    janela_analise=min(janela, len(base_passada)),
                    geracoes=ger,
                    pop_size=pop,
                )

                acertos = [intersecao(j, resultado_real) for j in jogos]
                melhor = max(acertos) if acertos else 0
                media = round(sum(acertos) / len(acertos), 3) if acertos else 0
                melhores.append(melhor)
                medias.append(media)
                for a in acertos:
                    if a >= 11:
                        resumo[a] += 1

                # Mesmo cálculo de acertos por modelo que backtest_basico usa
                # (ver alimentar_poda_e_elo em backtest.py).
                acertos_modelo: dict[str, float] = {}
                try:
                    modelos_scores = ((analise or {}).get("ensemble") or {}).get("modelos") or {}
                    for nome, scores_dez in modelos_scores.items():
                        if not scores_dez:
                            continue
                        top15 = sorted(scores_dez, key=lambda n: scores_dez[n], reverse=True)[:15]
                        acertos_modelo[nome] = float(intersecao(top15, resultado_real))
                except Exception:
                    pass
                registros_poda.append({
                    "concurso_idx": concurso_id,
                    "acertos_modelo": acertos_modelo,
                })

                linhas_txt.append("-" * 72)
                linhas_txt.append(f"Concurso real: {concurso_id} | Teste {pos}/{total_testes}")
                linhas_txt.append(f"Resultado real: {formatar_jogo(resultado_real)}")
                linhas_txt.append(f"Melhor acerto: {melhor} | Média dos jogos: {media}")
                for n, (jogo, acerto) in enumerate(zip(jogos, acertos), start=1):
                    linhas_txt.append(f"Jogo {n:02d}: {formatar_jogo(jogo)} -> {acerto} pontos")
                    linhas_csv.append({
                        "teste": pos,
                        "concurso": concurso_id,
                        "jogo": n,
                        "dezenas": formatar_jogo(jogo),
                        "resultado_real": formatar_jogo(resultado_real),
                        "acertos": int(acerto),
                        "melhor_do_concurso": int(melhor),
                        "media_do_concurso": media,
                    })

                if pos == 1 or pos % 5 == 0 or pos == total_testes:
                    self.log_async(
                        f"Backtest Automático {pos}/{total_testes} | melhor passo={melhor} | "
                        f"melhor geral={max(melhores)} | média geral={sum(medias)/max(1, len(medias)):.2f}"
                    )

            _poda_resultado_auto, _erro_elo_auto = alimentar_poda_e_elo(registros_poda)
            if _erro_elo_auto:
                self.log_async(f"⚠️ ELO/4-fases não pôde ser atualizado: {_erro_elo_auto}")
            else:
                self.log_async("🔪 Poda inteligente e ELO/4-fases atualizados com este Backtest Automático.")

            garantir_estrutura_pastas()
            timestamp = gerar_timestamp_arquivo()
            caminho_txt = os.path.join(PASTA_EXPORT, f"backtest_automatico_lotofacil_{timestamp}.txt")
            caminho_csv = os.path.join(PASTA_EXPORT, f"backtest_automatico_lotofacil_{timestamp}.csv")

            resumo_final = []
            resumo_final.append("===== RESUMO FINAL =====")
            resumo_final.append(f"Concursos testados: {total_testes}")
            resumo_final.append(f"Total de jogos simulados: {len(linhas_csv)}")
            resumo_final.append(f"Média do melhor jogo por concurso: {round(sum(melhores)/len(melhores), 3) if melhores else 0}")
            resumo_final.append(f"Média geral de acertos: {round(sum(medias)/len(medias), 3) if medias else 0}")
            resumo_final.append(f"Melhor pontuação atingida: {max(melhores) if melhores else 0}")
            resumo_final.append(f"11 pontos: {resumo.get(11, 0)}")
            resumo_final.append(f"12 pontos: {resumo.get(12, 0)}")
            resumo_final.append(f"13 pontos: {resumo.get(13, 0)}")
            resumo_final.append(f"14 pontos: {resumo.get(14, 0)}")
            resumo_final.append(f"15 pontos: {resumo.get(15, 0)}")
            resumo_final.append("")

            with open(caminho_txt, "w", encoding="utf-8") as f:
                f.write("\n".join(resumo_final + linhas_txt))

            try:
                pd.DataFrame(linhas_csv).to_csv(caminho_csv, index=False, encoding="utf-8-sig")
            except Exception:
                caminho_csv = ""

            self.info_backtest_automatico = {
                "concursos_testados": total_testes,
                "total_jogos": len(linhas_csv),
                "media_melhor": round(sum(melhores)/len(melhores), 3) if melhores else 0,
                "media_geral": round(sum(medias)/len(medias), 3) if medias else 0,
                "melhor": max(melhores) if melhores else 0,
                "distribuicao_11_15": dict(sorted((k, v) for k, v in resumo.items() if k >= 11)),
                "arquivo_txt": caminho_txt,
                "arquivo_csv": caminho_csv,
            }

            self.log_async("✅ Backtest Automático concluído.")
            self.log_async(f"Concursos testados: {total_testes} | Jogos simulados: {len(linhas_csv)}")
            self.log_async(f"Média do melhor jogo: {self.info_backtest_automatico['media_melhor']}")
            self.log_async(f"Melhor acerto observado: {self.info_backtest_automatico['melhor']}")
            self.log_async(f"11 pontos: {resumo.get(11, 0)} | 12 pontos: {resumo.get(12, 0)} | 13 pontos: {resumo.get(13, 0)} | 14 pontos: {resumo.get(14, 0)} | 15 pontos: {resumo.get(15, 0)}")
            self.log_async(f"Relatório TXT salvo em: {caminho_txt}")
            if caminho_csv:
                self.log_async(f"Planilha CSV salva em: {caminho_csv}")
            self.set_status_async("Backtest Automático concluído com sucesso.", "green")
            try:
                messagebox.showinfo(
                    "Backtest Automático",
                    "Backtest Automático concluído!\n\n"
                    f"Melhor resultado: {self.info_backtest_automatico['melhor']} pontos\n"
                    f"Relatório salvo em:\n{caminho_txt}"
                )
            except Exception:
                pass

        except Exception as e:
            self.set_status_async("Erro no Backtest Automático.", "red")
            self.log_async("❌ Erro no Backtest Automático:")
            self.log_async(str(e))
            self.log_async(traceback.format_exc())
        finally:
            self.backtest_automatico_ativo = False

    def iniciar_rodar_backtest(self) -> None:
        """Lança rodar_backtest em thread para não travar a UI."""
        if getattr(self, "_backtest_simples_ativo", False):
            self.log("⚠️ Backtest já em andamento.")
            return
        self._backtest_simples_ativo = True
        self.set_status("Iniciando backtest...", "blue")
        threading.Thread(target=self._executar_rodar_backtest, daemon=True).start()

    def _executar_rodar_backtest(self) -> None:
        """Executa backtest em thread separada."""
        try:
            self.rodar_backtest()
        finally:
            self._backtest_simples_ativo = False

    def rodar_backtest(self) -> None:
        try:
            # FIX V11: recarrega sempre o histórico antes do backtest.
            # Corrige o caso em que o usuário altera Passos Backtest, mas o robô
            # continuava usando uma base antiga já carregada em memória.
            limite = self.calcular_limite_turbo() if self.modo_turbo.get() else None
            self.concursos, self.df_csv, self.total_concursos_csv = carregar_concursos_do_csv(
                self.caminho_csv.get().strip(), limite=limite
            )

            total = len(self.concursos)
            if total < MIN_HIST + 5:
                raise ValueError(
                    f"Histórico insuficiente para backtest: {total} concursos carregados. "
                    f"Carregue ao menos {MIN_HIST + 5} concursos ou desligue o modo turbo."
                )

            janela_digitada = int(self.janela_hist.get())
            passos_digitados = int(self.passos_backtest.get())
            qtd = min(max(5, int(self.qtd_jogos.get())), 30)
            ger = max(5, int(self.geracoes.get()))
            pop = max(20, int(self.pop_size.get()))

            # Correção principal: a janela não pode consumir todo o histórico.
            janela_maxima_segura = max(MIN_HIST, total - 5)
            janela = min(max(MIN_HIST, janela_digitada), janela_maxima_segura)

            passos_maximos = max(1, total - janela)
            passos = min(max(1, passos_digitados), passos_maximos)

            self.set_status("Rodando backtest...", "blue")
            self.log("=" * 72)
            self.log("BACKTEST")
            self._aplicar_seed_configurada()
            base_total = getattr(self, "total_concursos_csv", total)
            self.log(f"Base completa no disco: {base_total} concursos")
            self.log(f"Concursos carregados em memória: {total}")
            if janela != janela_digitada:
                self.log(f"⚠️ Janela ajustada automaticamente de {janela_digitada} para {janela} para evitar erro de histórico insuficiente.")
            if passos != passos_digitados:
                self.log(f"⚠️ Passos ajustados automaticamente de {passos_digitados} para {passos} conforme histórico disponível.")
            self.log(f"Passos={passos} | Janela={janela} | Jogos por rodada={qtd} | G={ger} | P={pop}")

            if passos >= 120:
                self.log("Modo Ultra Massivo ativado automaticamente pelo número alto de passos.")

                def status_ultra(msg):
                    self.log(msg)
                    try:
                        self.root.update_idletasks()
                    except Exception:
                        pass

                self.info_backtest = backtest_ultra_massivo(
                    self.concursos, janela=janela, qtd_jogos=qtd, passos=passos, status_cb=status_ultra,
                    geracoes=ger, pop_size=pop,
                )
                self.log("✅ Backtest Ultra Massivo concluído.")
                self.log(f"Configuração testada: {self.info_backtest.get('configuracao_vencedora', {}).get('nome', '')}")
                self.log(f"Média do melhor jogo: {self.info_backtest['media_melhor']}")
                self.log(f"Melhor acerto observado: {self.info_backtest['max_melhor']}")
                self.log(f"Distribuição dos melhores acertos: {self.info_backtest['distribuicao']}")
                self.log("Campeonato entre modelos:")
                for pos, item in enumerate(self.info_backtest.get('ranking_modelos', []), start=1):
                    self.log(f"{pos}. {item.get('modelo')} | peso médio={item.get('peso_medio')}")
                self.log(f"Relatório salvo em: {self.info_backtest.get('arquivo_relatorio', '')}")
                self.set_status("Backtest Ultra Massivo concluído com sucesso.", "green")
            else:
                self.info_backtest = backtest_basico(
                    self.concursos, janela=janela, qtd_jogos=qtd, passos=passos,
                    geracoes=ger, pop_size=pop,
                )
                self.log(f"✅ Backtest concluído. Passos: {self.info_backtest['passos']}")
                self.log(f"Média do melhor jogo: {self.info_backtest['media_melhor']}")
                self.log(f"Melhor acerto observado: {self.info_backtest['max_melhor']}")
                self.log(f"Distribuição dos melhores acertos: {self.info_backtest['distribuicao']}")
                # ── V20.5: validação científica automática ──
                try:
                    resultados_bt = [
                        {"acertos": v}
                        for v in self.info_backtest.get("acertos_por_passo", [])
                        if isinstance(v, (int, float))
                    ]
                    if not resultados_bt:
                        resultados_bt = [{"acertos": self.info_backtest["media_melhor"]}]
                    bm = benchmark_vs_aleatorio(resultados_bt)
                    gs = ganho_estatistico(resultados_bt)
                    self.log(
                        f"📊 V20.5 | vs aleatório: {bm['veredito']} "
                        f"(robô={bm['media_robo']:.3f} | aleat.={bm['media_aleatorio']:.3f} | Δ={bm['delta']:+.3f}) "
                        f"| z-score={gs['z_score']:.3f} [{gs['interpretacao']}]"
                    )
                except Exception:
                    pass
                # ── V20.2: resultado da poda inteligente ──
                try:
                    poda = self.info_backtest.get("poda_modelos") or []
                    if poda:
                        icones = {"ATIVO": "✅", "OBSERVACAO": "⚠️", "SUSPENSO": "🔴"}
                        self.log("🔪 V20.2 Poda Inteligente — estado dos modelos após backtest:")
                        for m in sorted(poda, key=lambda x: x.get("score_sobrevivencia", 0), reverse=True):
                            ic = icones.get(m.get("estado", ""), "❓")
                            obs = m.get("obs", "")
                            if obs == "dados_insuficientes":
                                self.log(
                                    f"   {ic} {m['nome']:<14} | dados insuficientes — sem penalidade"
                                )
                            else:
                                self.log(
                                    f"   {ic} {m['nome']:<14} | "
                                    f"sv={m.get('score_sobrevivencia', 0):.4f} | "
                                    f"estado={m.get('estado')} | "
                                    f"média={m.get('media_global', 0):.2f} | "
                                    f"recente={m.get('media_recente', 0):.2f} | "
                                    f"peso_novo={m.get('peso_novo', 0):.4f}"
                                )
                        n_sus = sum(1 for m in poda if m.get("estado") == "SUSPENSO")
                        n_obs = sum(1 for m in poda if m.get("estado") == "OBSERVACAO")
                        if n_sus or n_obs:
                            self.log(
                                f"   → {n_sus} suspenso(s), {n_obs} em observação. "
                                f"Pesos ajustados em pesos_modelos.json — próxima geração já aplica."
                            )
                        else:
                            self.log("   → Todos os modelos ATIVOS. Nenhum peso penalizado.")
                except Exception:
                    pass
                self.set_status("Backtest concluído com sucesso.", "green")
        except Exception as e:
            self.set_status("Erro no backtest.", "red")
            self.log("❌ Erro no backtest:")
            self.log(str(e))
            self.log(traceback.format_exc())

    def obter_id_ultimo_concurso(self) -> int:
        try:
            if self.df_csv is not None and not self.df_csv.empty and "concurso" in self.df_csv.columns:
                return int(self.df_csv["concurso"].iloc[-1])
        except Exception:
            pass
        return len(self.concursos) if self.concursos else 0

    def obter_configuracao_atual(self) -> dict:
        """Captura os principais parâmetros visíveis da interface para auditoria histórica."""
        def get_int(var, default=0):
            try:
                return int(var.get())
            except Exception:
                return default
        def get_bool(var):
            try:
                return bool(var.get())
            except Exception:
                return False
        return {
            "qtd_jogos": get_int(self.qtd_jogos, 20),
            "janela_historica": get_int(self.janela_hist, 120),
            "geracoes": get_int(self.geracoes, 100),
            "populacao": get_int(self.pop_size, 150),
            "passos_backtest": get_int(self.passos_backtest, 20),
            "modo_turbo": get_bool(self.modo_turbo),
            "seed_fixo": get_bool(self.usar_seed_fixo),
            "seed_valor": get_int(self.seed_valor, 42),
        }

    def salvar_ultimos_jogos_gerados(self) -> None:
        """Salva o último pacote para avaliação automática quando sair concurso novo."""
        try:
            if not self.jogos_gerados or self.analise is None or self.pesos is None or not self.concursos:
                return
            garantir_estrutura_pastas()
            _ensemble_atual = self.analise.get("ensemble", {}) or {}
            analise_min = tornar_json_seguro({
                "estrategia": self.analise.get("estrategia", {}),
                "ensemble": {
                    "confianca_modelos": _ensemble_atual.get("confianca_modelos", {}),
                    # ranking/consenso são exigidos por registrar_desempenho_historico_robo()
                    # (backtest.py) pra calcular top5/10/15_acertos e top_consenso — antes
                    # ficavam de fora deste "analise_min" e qualquer "Conferir Jogos" feito
                    # num pacote restaurado do disco (ex.: reabrir o app no dia seguinte)
                    # registrava esses campos como vazios silenciosamente (ver 2026-07-23
                    # no ARQUITETURA.md).
                    "ranking": _ensemble_atual.get("ranking", []),
                    "consenso": _ensemble_atual.get("consenso", {}),
                },
                "cobertura_global": self.analise.get("cobertura_global", {}),
                # soma_media/hist_usado são exigidos por score_jogo() (genetico.py),
                # chamado por avaliar_jogos() sempre que a aba "Jogos Gerados" é
                # atualizada — sem eles, restaurar um pacote ao abrir o app e ter
                # a tabela populada automaticamente (correção anterior) quebrava
                # com KeyError: 'soma_media' assim que a tela tentava desenhar a
                # tabela (ver 2026-07-26 no ARQUITETURA.md). hist_usado é cortado
                # pros últimos 30 concursos — score_repeticao_recente só olha os
                # últimos 10, e isso evita persistir a janela histórica inteira.
                "soma_media": self.analise.get("soma_media", 195.0),
                "hist_usado": (self.analise.get("hist_usado") or [])[-30:],
            })
            dados = tornar_json_seguro({
                "salvo_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "concurso_referencia": self.obter_id_ultimo_concurso(),
                "resultado_referencia": self.concursos[-1],
                "jogos": self.jogos_gerados,
                "analise": analise_min,
                "pesos": self.pesos,
                "configuracao": self.obter_configuracao_atual(),
            })
            salvar_json(ARQUIVO_ULTIMOS_JOGOS, dados)
            self.log(f"💾 Pacote salvo para avaliação automática futura: {ARQUIVO_ULTIMOS_JOGOS}")
        except Exception as e:
            self.log(f"⚠️ Não foi possível salvar pacote para avaliação automática: {e}")

    def carregar_ultimos_jogos_gerados(self) -> None:
        """Carrega pacote anterior sem substituir a geração atual quando o arquivo não existir."""
        try:
            dados = ler_json(ARQUIVO_ULTIMOS_JOGOS, default={})
            if dados.get("jogos"):
                self.jogos_gerados = dados.get("jogos", [])
                self.analise = dados.get("analise", {})
                self.pesos = {int(k): float(v) for k, v in (dados.get("pesos") or {}).items()}
                # Popula a aba "Jogos Gerados" com o pacote restaurado sem
                # trocar de aba na inicialização (5ª instância do mesmo bug
                # já corrigido em outros 4 handlers — ver 2026-07-23 no
                # ARQUITETURA.md).
                self.root.after(0, lambda: self._atualizar_tabela_jogos(mudar_aba=False))
        except Exception:
            pass

    def avaliar_ultimo_sorteio_automatico(self) -> None:
        """
        Se houver jogos salvos de uma geração anterior e o histórico já estiver em concurso novo,
        avalia automaticamente contra o último resultado carregado da Caixa/CSV.
        """
        try:
            dados = ler_json(ARQUIVO_ULTIMOS_JOGOS, default={})
            if not dados.get("jogos") or not self.concursos:
                return

            concurso_atual = self.obter_id_ultimo_concurso()
            concurso_ref = int(dados.get("concurso_referencia", 0) or 0)
            resultado_atual = sorted(self.concursos[-1])
            resultado_ref = sorted(int(n) for n in dados.get("resultado_referencia", []) if str(n).isdigit())

            # Evita avaliar o mesmo pacote contra o mesmo concurso várias vezes.
            chave = f"{concurso_ref}->{concurso_atual}:{'-'.join(map(str, resultado_atual))}"
            avaliacoes = ler_json(ARQUIVO_AUTO_AVALIACOES, default={"avaliados": []})
            avaliados = set(avaliacoes.get("avaliados", []))

            if chave in avaliados:
                return
            if concurso_atual <= concurso_ref and resultado_atual == resultado_ref:
                return

            jogos = dados.get("jogos", [])
            analise = dados.get("analise", {}) or {}
            pesos_raw = dados.get("pesos", {}) or {}
            pesos = {int(k): float(v) for k, v in pesos_raw.items()}

            registro, ajustes = registrar_resultado_aprendizado(jogos, analise, pesos, resultado_atual)
            try:
                reg_hist, resumo_hist = registrar_desempenho_historico_robo(
                    jogos, resultado_atual, analise, pesos,
                    origem="automatico",
                    concurso=concurso_atual,
                    configuracao=dados.get("configuracao", {}),
                )
                self.log_async(f"📊 Desempenho histórico atualizado: melhor={reg_hist.get('melhor_acerto')} | média={reg_hist.get('media_acertos')}")
            except Exception as e:
                self.log_async(f"⚠️ Avaliação feita, mas não foi possível atualizar banco histórico: {e}")
            avaliados.add(chave)
            avaliacoes["avaliados"] = list(avaliados)[-200:]
            avaliacoes["ultima_avaliacao"] = {
                "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "chave": chave,
                "melhor_acerto": registro.get("melhor_acerto"),
                "media_acertos": registro.get("media_acertos"),
            }
            salvar_json(ARQUIVO_AUTO_AVALIACOES, avaliacoes)

            self.log_async("=" * 72)
            self.log_async("🤖 AVALIAÇÃO AUTOMÁTICA DO ÚLTIMO SORTEIO")
            self.log_async(f"Pacote gerado na referência: concurso {concurso_ref}")
            self.log_async(f"Último concurso carregado: {concurso_atual}")
            self.log_async(f"Resultado avaliado: {formatar_jogo(resultado_atual)}")
            self.log_async(f"Melhor acerto: {registro['melhor_acerto']} | Média: {registro['media_acertos']}")
            self.log_async(f"Distribuição: {registro['distribuicao_acertos']}")
            self.log_async(ajustes.get("resumo", "Memória atualizada automaticamente."))
        except Exception as e:
            self.log_async("⚠️ Falha na avaliação automática do último sorteio:")
            self.log_async(str(e))

    def forcar_aprendizado_continuo_seguro(self) -> None:
        """
        Botão manual seguro: não abre nova janela e não cria outro Tk().
        Apenas força o mesmo aprendizado contínuo a rodar em segundo plano dentro da tela atual.
        """
        try:
            if self.aprendizado_continuo_ativo:
                self.log("⚠️ O Aprendizado Contínuo já está rodando nesta mesma janela.")
                self.set_status("Aprendizado já em execução.", "blue")
                return
            self.log("🧠 Aprendizado manual iniciado dentro da mesma janela.")
            self.set_status("Iniciando aprendizado contínuo...", "blue")
            self.iniciar_aprendizado_continuo(automatico=False)
        except Exception as e:
            self.log(f"❌ Erro ao iniciar aprendizado manual: {e}")
            self.set_status("Erro ao iniciar aprendizado.", "red")

    def iniciar_aprendizado_automatico_pos_carga(self) -> None:
        """
        Dispara o Aprendizado Contínuo automaticamente após carregar/atualizar o histórico.
        Para evitar repetição pesada, roda uma vez por último concurso carregado.
        """
        try:
            if not self.auto_aprender_on_open.get():
                return
            if self.aprendizado_continuo_ativo:
                return
            if not self.concursos or len(self.concursos) < MIN_HIST + 10:
                return

            concurso_atual = self.obter_id_ultimo_concurso()
            if concurso_atual <= 0:
                return

            estado = ler_json(ARQUIVO_AUTO_APRENDIZADO, default={})
            ultimo_treinado = int(estado.get("ultimo_concurso_treinado", 0) or 0)

            if ultimo_treinado == concurso_atual:
                self.log_async(f"🧠 Aprendizado automático já executado para o concurso {concurso_atual}.")
                return

            self.aprendizado_automatico_chave = str(concurso_atual)
            self.log_async("🤖 Auto Aprender ativado: iniciando aprendizado contínuo em segundo plano.")
            self.root.after(800, lambda: self.iniciar_aprendizado_continuo(automatico=True))
        except Exception as e:
            self.log_async(f"⚠️ Não foi possível iniciar o aprendizado automático: {e}")

    def iniciar_aprendizado_continuo(self, automatico: bool = False) -> None:
        if self.aprendizado_continuo_ativo:
            self.log("⚠️ O Aprendizado Contínuo já está rodando.")
            return
        try:
            # FIX V11: recarrega sempre antes do aprendizado contínuo para respeitar
            # os novos valores de janela/passos definidos na interface.
            limite = self.calcular_limite_turbo() if self.modo_turbo.get() else None
            self.concursos, self.df_csv, self.total_concursos_csv = carregar_concursos_do_csv(self.caminho_csv.get().strip(), limite=limite)
        except Exception as e:
            self.log(f"❌ Não foi possível iniciar o aprendizado: {e}")
            return
        if len(self.concursos) < MIN_HIST + 10:
            self.log(f"❌ Histórico insuficiente para aprendizado contínuo. Use pelo menos {MIN_HIST + 10} concursos.")
            return
        self.aprendizado_continuo_ativo = True
        if not automatico:
            self.aprendizado_automatico_chave = None
        self.thread_aprendizado_continuo = threading.Thread(target=self.executar_aprendizado_continuo, daemon=True)
        self.thread_aprendizado_continuo.start()

    def parar_aprendizado_continuo(self) -> None:
        self.aprendizado_continuo_ativo = False
        self.log("⏹ Solicitação enviada: parar Aprendizado Contínuo.")

    def executar_aprendizado_continuo(self) -> None:
        """
        Treina em segundo plano usando concursos reais anteriores.
        Para cada passo, o robô gera jogos usando somente o passado e confere no concurso seguinte.
        """
        try:
            passos = min(max(10, int(self.passos_backtest.get())), max(10, len(self.concursos) - MIN_HIST))
            janela = min(max(MIN_HIST, int(self.janela_hist.get())), len(self.concursos) - 1)
            qtd = min(max(5, int(self.qtd_jogos.get())), 30)
            # Mantém o treino mais leve para não travar nem demorar demais.
            ger = min(max(5, int(self.geracoes.get())), 90)
            pop = min(max(25, int(self.pop_size.get())), 160)

            inicio = max(janela, len(self.concursos) - passos)
            total = len(self.concursos) - inicio
            self.set_status_async("Aprendizado Contínuo em execução...", "blue")
            self.log_async("=" * 72)
            self.log_async("🧠 APRENDIZADO CONTÍNUO POR SIMULAÇÃO")
            self.log_async(f"Passos={total} | Janela={janela} | Jogos={qtd} | Gerações={ger} | População={pop}")
            self.log_async("O robô vai gerar jogos usando concursos anteriores e comparar com o concurso real seguinte.")

            melhor_global = 0
            soma_medias = 0.0
            executados = 0
            for pos, i in enumerate(range(inicio, len(self.concursos)), start=1):
                if not self.aprendizado_continuo_ativo:
                    break
                base_passada = self.concursos[:i]
                resultado_real = self.concursos[i]
                jogos, analise, pesos = gerar_apostas(
                    base_passada,
                    qtd_jogos=qtd,
                    janela_analise=min(janela, len(base_passada)),
                    geracoes=ger,
                    pop_size=pop,
                )
                registro, ajustes = registrar_resultado_simulado_aprendizado(
                    jogos, analise, pesos, resultado_real, origem="aprendizado_continuo"
                )
                melhor_global = max(melhor_global, int(registro.get("melhor_acerto", 0)))
                soma_medias += float(registro.get("media_acertos", 0) or 0)
                executados += 1

                if pos == 1 or pos % 5 == 0 or pos == total:
                    media_geral = soma_medias / max(1, executados)
                    self.log_async(
                        f"🧪 Treino {pos}/{total} | melhor passo={registro.get('melhor_acerto')} | "
                        f"média passo={registro.get('media_acertos')} | melhor geral={melhor_global} | "
                        f"média geral={media_geral:.2f}"
                    )
                    self.log_async(ajustes.get("resumo", "Memória recalibrada."))

            self.aprendizado_continuo_ativo = False
            self.set_status_async("Aprendizado Contínuo concluído.", "green")
            self.log_async("✅ Aprendizado Contínuo finalizado.")
            self.log_async(gerar_resumo_aprendizado())
            if getattr(self, "aprendizado_automatico_chave", None):
                try:
                    salvar_json(ARQUIVO_AUTO_APRENDIZADO, {
                        "ultimo_concurso_treinado": int(self.aprendizado_automatico_chave),
                        "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    })
                    self.log_async(f"💾 Aprendizado automático marcado como concluído para o concurso {self.aprendizado_automatico_chave}.")
                except Exception as e:
                    self.log_async(f"⚠️ Não foi possível salvar o controle do aprendizado automático: {e}")
                finally:
                    self.aprendizado_automatico_chave = None
        except Exception as e:
            self.aprendizado_continuo_ativo = False
            self.set_status_async("Erro no Aprendizado Contínuo.", "red")
            self.log_async("❌ Erro no Aprendizado Contínuo:")
            self.log_async(str(e))
            self.log_async(traceback.format_exc())
            self.aprendizado_automatico_chave = None

    def _obter_resultado_para_conferencia(self) -> list[int] | None:
        """Obtém o último resultado carregado; se necessário tenta carregar o CSV atual."""
        if not self.concursos:
            limite = self.calcular_limite_turbo() if self.modo_turbo.get() else None
            self.concursos, self.df_csv, self.total_concursos_csv = carregar_concursos_do_csv(
                self.caminho_csv.get().strip(), limite=limite
            )
        if not self.concursos:
            raise ValueError("Nenhum resultado carregado para conferência.")
        return sorted(int(n) for n in self.concursos[-1])

    def conferir_jogos_gerados(self) -> None:
        """
        Confere jogo por jogo contra o último resultado carregado no histórico.
        Mostra 11, 12, 13, 14 e 15 pontos e grava um relatório em TXT.
        """
        try:
            # Se a tela acabou de abrir e ainda não gerou jogos nesta sessão,
            # usa automaticamente o último pacote salvo.
            if not self.jogos_gerados:
                self.carregar_ultimos_jogos_gerados()

            if not self.jogos_gerados:
                messagebox.showwarning("Aviso", "Nenhum jogo gerado/salvo foi encontrado para conferir.")
                return

            resultado = self._obter_resultado_para_conferencia()
            concurso = self.obter_id_ultimo_concurso()
            resultado_set = set(resultado)

            linhas = []
            distribuicao = Counter()
            melhor_acerto = -1
            melhor_jogo = None
            melhor_idx = None

            linhas.append("=" * 72)
            linhas.append("CONFERÊNCIA DOS JOGOS GERADOS")
            linhas.append("=" * 72)
            linhas.append(f"Data da conferência: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            linhas.append(f"Concurso conferido: {concurso}")
            linhas.append(f"Resultado oficial usado: {formatar_jogo(resultado)}")
            linhas.append("")

            for idx, jogo in enumerate(self.jogos_gerados, start=1):
                jogo_limpo = sorted(set(int(n) for n in jogo))
                acertadas = sorted(set(jogo_limpo) & resultado_set)
                acertos = len(acertadas)
                distribuicao[acertos] += 1
                if acertos > melhor_acerto:
                    melhor_acerto = acertos
                    melhor_jogo = jogo_limpo
                    melhor_idx = idx

                destaque = ""
                if acertos >= 15:
                    destaque = "  <<< 15 PONTOS"
                elif acertos >= 14:
                    destaque = "  <<< 14 PONTOS"
                elif acertos >= 13:
                    destaque = "  <<< 13 PONTOS"
                elif acertos >= 12:
                    destaque = "  <<< 12 PONTOS"
                elif acertos >= 11:
                    destaque = "  <<< 11 PONTOS"

                linhas.append(
                    f"Jogo {idx:02d}: {formatar_jogo(jogo_limpo)}  |  "
                    f"Acertos: {acertos:02d}{destaque}"
                )
                linhas.append(f"         Dezenas acertadas: {formatar_jogo(acertadas) if acertadas else '-'}")

            linhas.append("")
            linhas.append("RESUMO DA CONFERÊNCIA")
            linhas.append("-" * 72)
            for pontos in range(11, 16):
                linhas.append(f"{pontos} pontos: {distribuicao.get(pontos, 0)} jogo(s)")
            linhas.append("")
            if melhor_jogo is not None:
                linhas.append(f"Melhor jogo: Jogo {melhor_idx:02d} com {melhor_acerto} ponto(s)")
                linhas.append(f"Dezenas do melhor jogo: {formatar_jogo(melhor_jogo)}")

            texto_relatorio = "\n".join(linhas)
            self.log(texto_relatorio)

            garantir_estrutura_pastas()
            caminho = os.path.join(PASTA_EXPORT, f"conferencia_jogos_{gerar_timestamp_arquivo()}.txt")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(texto_relatorio)

            self.set_status(f"Conferência concluída. Melhor: {melhor_acerto} ponto(s).", "green")
            self.log(f"💾 Relatório da conferência salvo em: {caminho}")

            # Também registra no aprendizado permanente, se a análise/pesos estiverem disponíveis.
            if self.analise is not None and self.pesos is not None:
                try:
                    registro, ajustes = registrar_resultado_aprendizado(
                        self.jogos_gerados, self.analise, self.pesos, resultado
                    )
                    self.log("🧠 Conferência registrada no aprendizado permanente.")
                    self.log(f"Distribuição registrada: {registro.get('distribuicao_acertos', {})}")
                    self.log(ajustes.get("resumo", "Memória atualizada."))
                    try:
                        reg_hist, resumo_hist = registrar_desempenho_historico_robo(
                            self.jogos_gerados, resultado, self.analise, self.pesos,
                            origem="conferencia",
                            concurso=concurso,
                            configuracao=self.obter_configuracao_atual(),
                        )
                        self.log("📊 Banco histórico de desempenho atualizado.")
                        self.log(f"Resumo histórico: média melhor={resumo_hist.get('media_melhor_ultimos', 0)} | 11+={resumo_hist.get('pct_11_mais', 0)}% | 12+={resumo_hist.get('pct_12_mais', 0)}%")
                    except Exception as e:
                        self.log(f"⚠️ Não foi possível atualizar banco histórico de desempenho: {e}")
                    self._atualizar_grafico_acertos()
                    self._atualizar_painel_info()
                except Exception as e:
                    self.log(f"⚠️ Conferência feita, mas não foi possível registrar no aprendizado: {e}")

            messagebox.showinfo(
                "Conferência concluída",
                f"Jogos conferidos contra o concurso {concurso}.\n"
                f"Melhor jogo: {melhor_acerto} ponto(s).\n\n"
                f"Relatório salvo em:\n{caminho}"
            )
        except Exception as e:
            self.set_status("Erro ao conferir jogos.", "red")
            self.log("❌ Erro ao conferir jogos gerados:")
            self.log(str(e))
            self.log(traceback.format_exc())
            messagebox.showerror("Erro", f"Não foi possível conferir os jogos:\n{e}")

    def registrar_resultado(self) -> None:
        try:
            if not self.jogos_gerados or self.analise is None or self.pesos is None:
                messagebox.showwarning("Aviso", "Gere os jogos antes de registrar o resultado.")
                return
            janela = tk.Toplevel(self.root)
            janela.title("Avaliar sorteio e aprender")
            janela.geometry("520x180")
            ttk.Label(janela, text="Digite as 15 dezenas sorteadas, separadas por espaço ou vírgula:").pack(padx=12, pady=10, anchor="w")
            entrada = tk.StringVar()
            campo = ttk.Entry(janela, textvariable=entrada, width=70)
            campo.pack(padx=12, pady=5, fill="x")
            campo.focus_set()

            def confirmar():
                texto = entrada.get().strip()
                dezenas = [int(x) for x in re.findall(r"\d+", texto)]
                registro, ajustes = registrar_resultado_aprendizado(self.jogos_gerados, self.analise, self.pesos, dezenas)
                try:
                    reg_hist, resumo_hist = registrar_desempenho_historico_robo(
                        self.jogos_gerados, dezenas, self.analise, self.pesos,
                        origem="manual",
                        concurso=self.obter_id_ultimo_concurso(),
                        configuracao=self.obter_configuracao_atual(),
                    )
                except Exception as e:
                    reg_hist, resumo_hist = None, None
                    self.log(f"⚠️ Não foi possível atualizar banco histórico de desempenho: {e}")
                self.log("=" * 72)
                self.log("RESULTADO AVALIADO E REGISTRADO NO APRENDIZADO PERMANENTE")
                self.log(f"Melhor acerto: {registro['melhor_acerto']} | Média: {registro['media_acertos']}")
                self.log(f"Distribuição: {registro['distribuicao_acertos']}")
                self.log(ajustes.get("resumo", "Memória atualizada."))
                if resumo_hist:
                    self.log("📊 Banco histórico de desempenho atualizado.")
                    self.log(f"Resumo histórico: média melhor={resumo_hist.get('media_melhor_ultimos', 0)} | 11+={resumo_hist.get('pct_11_mais', 0)}% | 12+={resumo_hist.get('pct_12_mais', 0)}%")
                self._atualizar_grafico_acertos()
                self._atualizar_painel_info()
                self.set_status("Resultado registrado no aprendizado permanente.", "green")
                janela.destroy()

            self.criar_botao_colorido(janela, "Avaliar e Aprender", confirmar, cor="#455a64").pack(pady=12)
        except Exception as e:
            self.set_status("Erro ao registrar resultado.", "red")
            self.log("❌ Erro ao registrar resultado:")
            self.log(str(e))
            self.log(traceback.format_exc())

    def ver_aprendizado(self) -> None:
        try:
            memoria = carregar_memoria_aprendizado()
            resumo = gerar_resumo_aprendizado(memoria)
            self.log("=" * 72)
            self.log(resumo)
            self._atualizar_grafico_acertos()
            self._atualizar_painel_info()
            self.set_status("Resumo do aprendizado exibido.", "green")
        except Exception as e:
            self.set_status("Erro ao ler aprendizado.", "red")
            self.log("❌ Erro ao ler aprendizado:")
            self.log(str(e))
            self.log(traceback.format_exc())


    def abrir_dashboard_cientifico_v21(self) -> None:
        """
        V21.5-FULL — Dashboard Científico Completo.
        Abas: Campeão · Hall da Fama · ELO · Poda 4-fases · Monte Carlo · Walk-Forward · Eventos · SQLite
        """
        if not _V21_OK:
            messagebox.showwarning(
                "V21 não disponível",
                "Os módulos V21.1 não foram inicializados corretamente.\n"
                "Verifique se o banco SQLite foi criado (inicializar_banco_v21)."
            )
            return

        janela = tk.Toplevel(self.root)
        janela.title("⚗️ Dashboard Científico V21.5-FULL")
        janela.geometry("1150x760")
        janela.configure(bg=TEMA["bg"])

        notebook = ttk.Notebook(janela)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        def _txt(parent):
            t = tk.Text(parent, wrap="none", font=("Consolas", 10),
                        bg=TEMA["bg2"], fg=TEMA["fg"])
            s = ttk.Scrollbar(parent, command=t.yview)
            t.config(yscrollcommand=s.set)
            s.pack(side="right", fill="y")
            t.pack(fill="both", expand=True)
            return t

        # ── Aba 1: MODELO CAMPEÃO (painel de destaque) ────────────────────────
        aba_camp = ttk.Frame(notebook)
        notebook.add(aba_camp, text="🥇 Campeão")
        txt_camp = _txt(aba_camp)

        try:
            from .v21_5_meta_competitivo import relatorio_meta_competitivo
            from .v21_5_montecarlo_cientifico import executar_montecarlo_cientifico, resumo_montecarlo
            from .v21_5_walkforward_profissional import get_indicadores_permanentes

            rel_mc  = relatorio_meta_competitivo()
            camp    = rel_mc.get("campeao", {})
            stats   = rel_mc.get("estatisticas", {})
            ind_wf  = get_indicadores_permanentes()
            rob_wf  = ind_wf.get("robustez_media")
            est_wf  = ind_wf.get("estabilidade_media")
            # Nível de overfitting da execução mais recente (histórico está em
            # ordem crescente de id, então o último item é o mais recente).
            hist_wf = ind_wf.get("historico") or []
            overfit_wf = hist_wf[-1].get("overfitting_nivel", "—") if hist_wf else "—"

            # Monte Carlo rápido com histórico existente (sem backtest novo)
            resultados_reais = self._obter_resultados_backtest_reais_para_montecarlo()
            mc = executar_montecarlo_cientifico(
                resultados_backtest=resultados_reais, n_simulacoes=500, qtd_jogos=10
            )
            fonte_mc = f"dados reais ({len(resultados_reais)} execuções)" if resultados_reais else "sintético — rode o Backtest Científico para dados reais"

            sep = "═" * 50
            linhas_c = [
                sep,
                "  MODELO CAMPEÃO",
                "",
                f"  {camp.get('nome','—').upper()}",
                "",
                f"  ELO            {camp.get('elo', 0):>8.0f}",
                f"  Status         {camp.get('status','—')}",
                f"  Fator peso     {camp.get('fator', 1.0):>8.4f}",
                sep,
                "",
                "  INDICADORES DO SISTEMA",
                "",
                f"  Robustez Temporal    {(rob_wf or 0)*100:>6.1f}%",
                f"  Estabilidade         {(est_wf or 0)*100:>6.1f}%",
                f"  Overfitting          {overfit_wf}",
                "",
                f"  MONTE CARLO (500 simulações — {fonte_mc})",
                "",
                f"  P(Robô > Aleatório)  {mc.get('prob_pct', 0):>6.1f}%",
                f"  IC 95%  {mc.get('ic_95',{}).get('inferior',0):.4f} → {mc.get('ic_95',{}).get('superior',0):.4f}",
                f"  Desvio Padrão        {mc.get('desvio_padrao',0):>8.4f}",
                f"  Veredito             {mc.get('veredito','')}",
                sep,
                "",
                "  RANKING ELO COMPLETO",
                "",
            ]
            ranking_elo = rel_mc.get("ranking", [])
            linhas_c.append(f"  {'Pos':<4} {'Modelo':<14} {'ELO':>6}  {'Fator':>6}  Status")
            linhas_c.append("  " + "-" * 55)
            for e in ranking_elo:
                linhas_c.append(
                    f"  {e['posicao']:<4} {e['nome']:<14} {e['elo']:>6.0f}  "
                    f"{e['fator']:>6.4f}  {e['status']}"
                )
            linhas_c += ["", f"  ELO médio: {stats.get('media_elo',0):.0f}  "
                         f"Max: {stats.get('max_elo',0):.0f}  "
                         f"Min: {stats.get('min_elo',0):.0f}"]
        except Exception as ex:
            linhas_c = [f"  (dados indisponíveis — rode o Backtest Científico primeiro)\n  {ex}"]

        txt_camp.insert("end", "\n".join(linhas_c))
        txt_camp.config(state="disabled")

        # ── Aba 2: Hall da Fama ───────────────────────────────────────────────
        aba_hf = ttk.Frame(notebook)
        notebook.add(aba_hf, text="🏆 Hall da Fama")
        txt_hf = _txt(aba_hf)

        try:
            from .v21_3_1_hall_fama_auto import relatorio_hall_fama
            linhas_hf = [
                relatorio_hall_fama("geral"),
                "",
                "─" * 60,
                "",
            ]
        except Exception as ex:
            linhas_hf = [f"  (sem dados — rode o Backtest Científico)\n  {ex}"]

        txt_hf.insert("end", "\n".join(linhas_hf))
        txt_hf.config(state="disabled")

        # ── Aba 3: Poda 4-Fases ──────────────────────────────────────────────
        aba_poda = ttk.Frame(notebook)
        notebook.add(aba_poda, text="✂️ Poda 4-Fases")
        txt_poda = _txt(aba_poda)

        try:
            from .v21_5_auto_poda_full import relatorio_poda_full
            rel_poda = relatorio_poda_full()
            linhas_p = [
                "AUTO-PODA 4-ESTADOS — V21.5-FULL",
                "=" * 65,
                "",
                "  Avaliação relativa à média do grupo (7 modelos) em cada passo do backtest",
                f"  (correção 2026-07-21 — ver ARQUITETURA.md): abaixo de {rel_poda['limiares']['observacao']:+.2f} "
                f"do grupo → degrada | abaixo de {rel_poda['limiares']['suspenso']:+.2f} → pode suspender | "
                f"acima de {rel_poda['limiares']['recuperacao']:+.2f} → recupera",
                f"  Precisa de 2 rodadas consecutivas na mesma direção pra avançar de estado",
                "",
                f"  {'Modelo':<14} {'Estado':<12} {'Fator':>6} {'Média':>7} {'Tend.':<10} {'Hist.':>5}",
                "  " + "-" * 65,
            ]
            for m in rel_poda.get("modelos", []):
                ico = {"ATIVO":"✅","OBSERVAÇÃO":"👁","QUARENTENA":"⚠️","SUSPENSO":"🚫"}.get(m["estado"], "")
                linhas_p.append(
                    f"  {m['nome']:<14} {ico} {m['estado']:<10} "
                    f"{m['fator_peso']:>6.2f} "
                    f"{m['media_historico']:>7.3f} "
                    f"{m['tendencia']:<10} "
                    f"{m['historico_tam']:>5}"
                )
            cnt = rel_poda.get("contagem", {})
            linhas_p += [
                "",
                f"  Resumo: ATIVO={cnt.get('ATIVO',0)}  OBSERVAÇÃO={cnt.get('OBSERVAÇÃO',0)}  "
                f"QUARENTENA={cnt.get('QUARENTENA',0)}  SUSPENSO={cnt.get('SUSPENSO',0)}",
            ]
        except Exception as ex:
            limiar_din = db_limiar_dinamico(percentil=20.0)
            poda_rel = relatorio_auto_poda()
            linhas_p = ["AUTO-PODA ADAPTATIVA — V21.1-C (fallback)", "=" * 80, ""]
            linhas_p.append(f"  Limiar dinâmico (P20): {limiar_din:.4f}")
            if poda_rel:
                linhas_p.append(f"  {'Modelo':<40} {'Score':>8} {'P(Rec)':>8} {'Decisão':<10}")
                for r in poda_rel:
                    ico2 = "🔴" if r["decisao"] == "PODAR" else "🟢"
                    linhas_p.append(
                        f"  {r['nome']:<40} {r['score_global']:>8.4f} "
                        f"{r['prob_recuperacao']:>8.4f} {ico2} {r['decisao']}"
                    )
            else:
                linhas_p.append("  Sem histórico de poda ainda.")

        txt_poda.insert("end", "\n".join(linhas_p))
        txt_poda.config(state="disabled")

        # ── Aba 4: Monte Carlo Científico ────────────────────────────────────
        aba_mc = ttk.Frame(notebook)
        notebook.add(aba_mc, text="🎲 Monte Carlo")
        txt_mc = _txt(aba_mc)

        try:
            from .v21_5_montecarlo_cientifico import executar_montecarlo_cientifico, resumo_montecarlo
            resultados_reais_mc1000 = self._obter_resultados_backtest_reais_para_montecarlo()
            mc1000 = executar_montecarlo_cientifico(
                resultados_backtest=resultados_reais_mc1000, n_simulacoes=1000, qtd_jogos=10
            )
            fonte_mc1000 = (
                f"dados reais ({len(resultados_reais_mc1000)} execuções do Backtest Científico)"
                if resultados_reais_mc1000 else
                "sintético — rode o Backtest Científico para dados reais"
            )
            linhas_mc = [
                "MONTE CARLO CIENTÍFICO — V21.5-FULL",
                "=" * 60,
                "",
                f"  Fonte dos dados: {fonte_mc1000}",
                "",
                resumo_montecarlo(mc1000),
                "",
                "─" * 60,
                "",
                f"  Simulações usadas:    {mc1000.get('n_simulacoes_usadas', 0)}",
                f"  Baseline aleatório:   {mc1000.get('n_baseline', 0)} simulações",
                f"  Cohen's d:            {mc1000.get('cohen_d',0):.4f} [{mc1000.get('cohen_magnitude','')}]",
                f"  p-value:              {mc1000.get('p_value',1.0):.4f}",
                f"  IC 99%:  {mc1000.get('ic_99',{}).get('inferior',0):.4f} → {mc1000.get('ic_99',{}).get('superior',0):.4f}",
                "",
                "  Interpretação:",
                "    IC 95% = intervalo onde a média real do robô está com 95% de confiança",
                "    p-value < 0.05 = diferença estatisticamente significativa vs aleatório",
                "    Cohen's d > 0.2 = efeito pequeno mas mensurável",
            ]
        except Exception as ex:
            linhas_mc = [f"  (erro ao executar Monte Carlo: {ex})"]

        txt_mc.insert("end", "\n".join(linhas_mc))
        txt_mc.config(state="disabled")

        # ── Aba 5: Walk-Forward Profissional ─────────────────────────────────
        aba_wf = ttk.Frame(notebook)
        notebook.add(aba_wf, text="🔀 Walk-Forward")
        txt_wf = _txt(aba_wf)

        try:
            from .v21_5_walkforward_profissional import (
                relatorio_walkforward_profissional, get_indicadores_permanentes
            )
            ind = get_indicadores_permanentes()
            linhas_wf = [
                "WALK-FORWARD PROFISSIONAL — V21.5-FULL",
                "=" * 60,
                "",
                relatorio_walkforward_profissional(),
                "",
                "─" * 60,
                "",
                "  INDICADORES PERMANENTES ACUMULADOS",
                "",
            ]
            if ind.get("n_execucoes", 0) > 0:
                linhas_wf += [
                    f"  Robustez média:       {(ind.get('robustez_media') or 0)*100:.1f}%",
                    f"  Robustez máxima:      {(ind.get('robustez_max') or 0)*100:.1f}%",
                    f"  Robustez mínima:      {(ind.get('robustez_min') or 0)*100:.1f}%",
                    f"  Estabilidade média:   {(ind.get('estabilidade_media') or 0)*100:.1f}%",
                    f"  Tendência histórica:  {ind.get('trend_atual','—')}",
                    f"  Execuções acumuladas: {ind.get('n_execucoes', 0)}",
                ]
            else:
                linhas_wf.append("  (sem execuções acumuladas — rode Walk-Forward para gerar histórico)")
        except Exception as ex:
            linhas_wf = [f"  (erro ao carregar Walk-Forward: {ex})"]

        txt_wf.insert("end", "\n".join(linhas_wf))
        txt_wf.config(state="disabled")

        # ── Aba 6: Eventos ────────────────────────────────────────────────────
        aba_ev = ttk.Frame(notebook)
        notebook.add(aba_ev, text="🔔 Eventos")
        txt_ev = _txt(aba_ev)

        eventos = db_eventos_recentes(limit=80)
        linhas4 = ["HISTÓRICO DE EVENTOS — SQLite", "=" * 80, ""]
        if eventos:
            linhas4.append(f"  {'Data':<28} {'Evento':<30} {'Modelo':<20}")
            linhas4.append("  " + "-" * 82)
            for e in eventos:
                ev_str = str(e.get("evento",""))
                ico = (
                    "⚠️ " if "suspens" in ev_str else
                    "🔴 " if "PODAR" in ev_str else
                    "✅ " if ev_str == "ativo" else
                    "🟡 " if ev_str == "observacao" else
                    "🏆 " if "ELO" in ev_str else
                    "🔄 " if "transicao" in ev_str else "📌 "
                )
                linhas4.append(
                    f"  {str(e.get('criado_em',''))[:25]:<28} "
                    f"{ico}{ev_str[:27]:<28} "
                    f"{str(e.get('model_id','') or '—'):<20}"
                )
        else:
            linhas4.append("  (sem eventos ainda — rode o backtest para gerar histórico)")
        txt_ev.insert("end", "\n".join(linhas4))
        txt_ev.config(state="disabled")

        # ── Aba 7: Status SQLite ──────────────────────────────────────────────
        aba_db = ttk.Frame(notebook)
        notebook.add(aba_db, text="🗄️ Banco")
        txt_db = _txt(aba_db)

        try:
            from .v21_0_sqlite import get_db as _gdb
            conn_db = _gdb()
            tabelas = [
                "modelos", "desempenho", "ranking_modelos", "historico_eventos",
                "geracoes_performance", "aprendizado_registros", "pesos_modelos",
                "elo_modelos", "walkforward_indicadores", "hall_fama",
            ]
            linhas5 = ["STATUS DO BANCO SQLite V21.5-FULL", "=" * 60, "", "  Arquivo: lotofacil_v21.db", ""]
            linhas5.append(f"  {'Tabela':<35} {'Registros':>12}")
            linhas5.append("  " + "-" * 50)
            for t in tabelas:
                try:
                    n = conn_db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    linhas5.append(f"  {t:<35} {n:>12,}")
                except Exception:
                    linhas5.append(f"  {t:<35} {'(não existe)':>12}")
            linhas5 += ["", "  ✅ Banco V21.5-FULL ativo e funcionando"]
        except Exception as ex:
            linhas5 = [f"Erro ao consultar banco: {ex}"]
        txt_db.insert("end", "\n".join(linhas5))
        txt_db.config(state="disabled")

        # Rodapé
        rodape = tk.Frame(janela, bg=TEMA["bg3"], pady=6)
        rodape.pack(fill="x", side="bottom")
        tk.Label(
            rodape,
            text="⚗️ V21.5-FULL · ELO Competitivo · Poda 4-Fases · Monte Carlo · Walk-Forward · Hall da Fama",
            bg=TEMA["bg3"], fg=TEMA["fg2"], font=("Segoe UI", 9)
        ).pack()


    def abrir_dashboard_desempenho(self) -> None:
        """Abre o painel do banco histórico de desempenho real do robô."""
        try:
            texto = gerar_dashboard_desempenho_historico()
            janela = tk.Toplevel(self.root)
            janela.title("Dashboard de Desempenho Histórico")
            janela.geometry("980x640")
            janela.configure(bg=TEMA["bg"])
            txt = tk.Text(
                janela,
                wrap="word",
                bg=TEMA["bg2"],
                fg=TEMA["fg"],
                insertbackground=TEMA["fg"],
                font=("Consolas", 10),
                relief="flat",
            )
            txt.pack(fill="both", expand=True, padx=12, pady=12)
            txt.insert("end", texto)
            txt.configure(state="disabled")

            rodape = tk.Frame(janela, bg=TEMA["bg"])
            rodape.pack(fill="x", padx=12, pady=(0, 12))

            def salvar_txt_desempenho():
                caminho = filedialog.asksaveasfilename(
                    title="Salvar dashboard de desempenho",
                    defaultextension=".txt",
                    initialfile=f"dashboard_desempenho_lotofacil_{gerar_timestamp_arquivo()}.txt",
                    filetypes=[("Arquivo TXT", "*.txt")],
                )
                if caminho:
                    with open(caminho, "w", encoding="utf-8") as f:
                        f.write(texto)
                    messagebox.showinfo("Salvo", f"Dashboard salvo em:\n{caminho}")

            self.criar_botao_colorido(rodape, "Salvar Dashboard TXT", salvar_txt_desempenho, cor=TEMA["btn_salvar"]).pack(side="left", padx=5)
            self.criar_botao_colorido(rodape, "Fechar", janela.destroy, cor=TEMA["btn_limpar"]).pack(side="right", padx=5)
            self.set_status("Dashboard de desempenho exibido.", "green")
        except Exception as e:
            self.set_status("Erro ao abrir desempenho histórico.", "red")
            self.log("❌ Erro ao abrir dashboard de desempenho:")
            self.log(str(e))
            self.log(traceback.format_exc())

    def abrir_dashboard(self) -> None:
        try:
            if not self.jogos_gerados or self.analise is None or self.pesos is None:
                messagebox.showwarning("Aviso", "Gere os jogos antes de abrir o dashboard.")
                return
            memoria = carregar_memoria_aprendizado()
            texto_dashboard = gerar_dashboard_analitico(
                self.jogos_gerados,
                self.analise,
                self.pesos,
                memoria=memoria,
                info_backtest=self.info_backtest,
            )

            janela = tk.Toplevel(self.root)
            janela.title("Dashboard Analítico Profissional")
            janela.geometry("1180x780")

            notebook = ttk.Notebook(janela)
            notebook.pack(fill="both", expand=True, padx=8, pady=8)

            aba_resumo   = ttk.Frame(notebook)
            aba_dezenas  = ttk.Frame(notebook)
            aba_modelos  = ttk.Frame(notebook)
            aba_texto    = ttk.Frame(notebook)
            notebook.add(aba_resumo,  text="Resumo")
            notebook.add(aba_dezenas, text="Mapa 5x5")
            notebook.add(aba_modelos, text="Modelos")
            notebook.add(aba_texto,   text="Relatório")

            estrategia = self.analise.get("estrategia", {})
            cobertura  = self.analise.get("cobertura_global", {})
            ensemble   = self.analise.get("ensemble", {})

            # ── Paleta de cores do tema ───────────────────────────────────
            BG   = TEMA["bg2"]
            FG   = TEMA["fg"]
            ACC  = TEMA["accent"]
            VRD  = TEMA["verde"]
            AMR  = TEMA["amarelo"]
            VRM  = TEMA["vermelho"]
            CYN  = TEMA["ciano"]
            ROX  = TEMA["roxo"]
            LRN  = TEMA["laranja"]
            FG2  = TEMA["fg2"]

            def _txt(parent, **kw):
                """Cria Text widget com fundo do tema e tags de cor pré-configuradas."""
                t = tk.Text(
                    parent, wrap="word",
                    bg=BG, fg=FG, insertbackground=FG,
                    selectbackground=ACC, selectforeground=BG,
                    relief="flat", **kw
                )
                # Tags semânticas — usadas em todas as abas
                t.tag_configure("titulo",   foreground=ACC,  font=("Consolas", 11, "bold"))
                t.tag_configure("secao",    foreground=CYN,  font=("Consolas", 10, "bold"))
                t.tag_configure("ok",       foreground=VRD)
                t.tag_configure("aviso",    foreground=AMR)
                t.tag_configure("erro",     foreground=VRM)
                t.tag_configure("destaque", foreground=ROX,  font=("Consolas", 10, "bold"))
                t.tag_configure("label",    foreground=FG2)
                t.tag_configure("valor",    foreground=FG)
                t.tag_configure("barra_hi", foreground=VRD)
                t.tag_configure("barra_md", foreground=AMR)
                t.tag_configure("barra_lo", foreground=VRM)
                t.tag_configure("laranja",  foreground=LRN)
                return t

            def _inserir_barra_colorida(txt_widget, valor, maximo, largura=26):
                """Insere barra ASCII com cor proporcional ao valor (verde→amarelo→vermelho)."""
                maximo = float(maximo) if maximo else 1.0
                ratio  = max(0.0, min(1.0, float(valor) / maximo)) if maximo > 0 else 0.0
                qtd    = int(round(ratio * largura))
                bar    = "█" * qtd + " " * (largura - qtd)
                tag    = "barra_hi" if ratio >= 0.65 else ("barra_md" if ratio >= 0.35 else "barra_lo")
                txt_widget.insert("end", f"|{bar}|", tag)

            # ── Aba Resumo ────────────────────────────────────────────────
            cards = ttk.Frame(aba_resumo, padding=12)
            cards.pack(fill="x")
            dados_cards = [
                ("Modo",             estrategia.get("modo", "n/d").upper()),
                ("Confiança",        f"{estrategia.get('indice_confianca', 0):.3f}"),
                ("Diversidade",      f"{estrategia.get('diversidade', 0):.3f}"),
                ("Mutação",          f"{estrategia.get('taxa_mutacao', 0):.3f}"),
                ("Sobreposição média", str(cobertura.get("media_sobreposicao", 0))),
                ("Média de soma",    str(cobertura.get("media_soma", 0))),
            ]
            for i, (titulo, valor) in enumerate(dados_cards):
                frame = ttk.LabelFrame(cards, text=titulo, padding=10)
                frame.grid(row=i // 3, column=i % 3, padx=8, pady=8, sticky="nsew")
                ttk.Label(frame, text=valor, font=("Segoe UI", 16, "bold")).pack()
            for i in range(3):
                cards.columnconfigure(i, weight=1)

            txt_resumo = _txt(aba_resumo, font=("Consolas", 10), height=20)
            txt_resumo.pack(fill="both", expand=True, padx=12, pady=8)

            txt_resumo.insert("end", "PERFIS TÁTICOS\n", "secao")
            txt_resumo.insert("end", "─" * 60 + "\n", "label")
            for p in cobertura.get("perfis_taticos", []):
                txt_resumo.insert("end", f"Jogo {p.get('jogo', 0):02d}: ", "label")
                txt_resumo.insert("end", f"{p.get('perfil', '')}\n", "destaque")
            txt_resumo.insert("end", "\n")
            txt_resumo.insert("end", "APRENDIZADO\n", "secao")
            txt_resumo.insert("end", "─" * 60 + "\n", "label")
            txt_resumo.insert("end",
                (self.analise.get("aprendizado") or {}).get("resumo", gerar_resumo_aprendizado(memoria)) + "\n",
                "valor"
            )
            txt_resumo.config(state="disabled")

            # ── Aba Dezenas — mapa em grade colorido + ranking ────────────
            painel_dezenas = ttk.Frame(aba_dezenas, padding=12)
            painel_dezenas.pack(fill="both", expand=True)
            contagem = cobertura.get("contagem_dezenas", {}) or dict(Counter(n for j in self.jogos_gerados for n in j))
            max_c = max(contagem.values()) if contagem else 1
            min_c = min(contagem.values()) if contagem else 0

            grade = ttk.LabelFrame(painel_dezenas, text="Mapa 5x5 de exposição", padding=10)
            grade.pack(side="left", fill="both", expand=True, padx=8, pady=8)

            for lin in range(5):
                for col in range(5):
                    n = lin * 5 + col + 1
                    q = int(contagem.get(n, 0))
                    # Cor da célula: quente (laranja/vermelho) = alta cobertura,
                    # fria (verde/azul) = baixa cobertura — leitura intuitiva.
                    ratio = (q - min_c) / max(1, max_c - min_c)
                    if ratio >= 0.75:
                        bg_cel, fg_cel = TEMA["vermelho"], "#ffffff"
                    elif ratio >= 0.50:
                        bg_cel, fg_cel = TEMA["laranja"],  "#000000"
                    elif ratio >= 0.25:
                        bg_cel, fg_cel = TEMA["amarelo"],  "#000000"
                    else:
                        bg_cel, fg_cel = TEMA["verde"],    "#000000"

                    tk.Label(
                        grade,
                        text=f"{n:02d}\n{q}x",
                        font=("Segoe UI", 13, "bold"),
                        anchor="center",
                        relief="groove",
                        padx=12, pady=8,
                        bg=bg_cel,
                        fg=fg_cel,
                        width=5,
                    ).grid(row=lin, column=col, sticky="nsew", padx=4, pady=4)

            for i in range(5):
                grade.columnconfigure(i, weight=1)
                grade.rowconfigure(i, weight=1)

            ranking_frame = ttk.LabelFrame(painel_dezenas, text="Ranking", padding=10)
            ranking_frame.pack(side="right", fill="both", expand=True, padx=8, pady=8)

            txt_rank = _txt(ranking_frame, font=("Consolas", 10))
            txt_rank.pack(fill="both", expand=True)

            txt_rank.insert("end", f"{'Dez':>4}  {'Cob':>4}  Exposição\n", "secao")
            txt_rank.insert("end", "─" * 44 + "\n", "label")
            for n, q in sorted(((int(k), int(v)) for k, v in contagem.items()), key=lambda x: (-x[1], x[0])):
                ratio = (q - min_c) / max(1, max_c - min_c)
                tag_b = "barra_hi" if ratio >= 0.65 else ("barra_md" if ratio >= 0.35 else "barra_lo")
                txt_rank.insert("end", f" {n:02d}  ", "label")
                txt_rank.insert("end", f"{q:>4}  ", "valor")
                _inserir_barra_colorida(txt_rank, q, max_c, 22)
                txt_rank.insert("end", "\n")
            txt_rank.config(state="disabled")

            legenda = tk.Frame(grade, bg=TEMA["bg2"])
            legenda.grid(row=5, column=0, columnspan=5, sticky="ew", pady=(8, 0))
            for cor, texto in [
                (TEMA["verde"],    "Baixa"),
                (TEMA["amarelo"],  "Média"),
                (TEMA["laranja"],  "Alta"),
                (TEMA["vermelho"], "Máxima"),
            ]:
                tk.Label(legenda, text=f"  {texto}", bg=cor, fg="#000000",
                         font=("Segoe UI", 9, "bold"), relief="flat", padx=6, pady=2
                         ).pack(side="left", padx=3)

            # ── Aba Modelos ───────────────────────────────────────────────
            txt_modelos = _txt(aba_modelos, font=("Consolas", 11))
            txt_modelos.pack(fill="both", expand=True, padx=10, pady=10)

            txt_modelos.insert("end", "CONFIANÇA DOS MODELOS\n", "titulo")
            txt_modelos.insert("end", "─" * 70 + "\n", "label")
            conf    = ensemble.get("confianca_modelos", {})
            max_conf = max(conf.values()) if conf else 1
            for nome_m, valor in sorted(conf.items(), key=lambda x: x[1], reverse=True):
                txt_modelos.insert("end", f"{nome_m:<18} ", "label")
                _inserir_barra_colorida(txt_modelos, valor, max_conf, 28)
                txt_modelos.insert("end", f"  {valor:.3f}\n", "valor")

            txt_modelos.insert("end", "\n")
            txt_modelos.insert("end", "TOP 15 DEZENAS PELO ENSEMBLE\n", "titulo")
            txt_modelos.insert("end", "─" * 70 + "\n", "label")
            max_p = max(self.pesos.values()) if self.pesos else 1
            for n, p in sorted(self.pesos.items(), key=lambda x: x[1], reverse=True)[:15]:
                txt_modelos.insert("end", f"{n:02d}  ", "label")
                _inserir_barra_colorida(txt_modelos, p, max_p, 28)
                txt_modelos.insert("end", f"  {p:.5f}\n", "valor")
            txt_modelos.config(state="disabled")

            # ── Aba Relatório — texto completo com cores semânticas ───────
            txt_frame_rel = ttk.Frame(aba_texto)
            txt_frame_rel.pack(fill="both", expand=True)
            txt = _txt(txt_frame_rel, font=("Consolas", 10))
            txt.pack(side="left", fill="both", expand=True)
            scroll = ttk.Scrollbar(txt_frame_rel, orient="vertical", command=txt.yview)
            scroll.pack(side="right", fill="y")
            txt.config(yscrollcommand=scroll.set)

            # Insere o relatório linha a linha com tags semânticas
            for linha in texto_dashboard.split("\n"):
                stripped = linha.strip()
                if stripped.startswith("="):
                    txt.insert("end", linha + "\n", "titulo")
                elif stripped.startswith("-") and len(stripped) > 4:
                    txt.insert("end", linha + "\n", "label")
                elif any(stripped.startswith(f"{i})") for i in range(1, 10)):
                    txt.insert("end", linha + "\n", "secao")
                elif "█" in linha:
                    # Divide label | barra | valor e colore a barra
                    partes = linha.split("|", 2)
                    if len(partes) == 3:
                        txt.insert("end", partes[0], "label")
                        txt.insert("end", "|", "label")
                        barra_s = partes[1]
                        preenchidos = barra_s.count("█")
                        total_chars = len(barra_s)
                        ratio_b = preenchidos / max(1, total_chars)
                        tag_b = "barra_hi" if ratio_b >= 0.65 else ("barra_md" if ratio_b >= 0.35 else "barra_lo")
                        txt.insert("end", barra_s, tag_b)
                        txt.insert("end", "|" + partes[2] + "\n", "valor")
                    else:
                        txt.insert("end", linha + "\n", "valor")
                elif stripped.startswith("✅") or "SIGNIFICATIV" in stripped:
                    txt.insert("end", linha + "\n", "ok")
                elif stripped.startswith("⚠️") or "não significativ" in stripped.lower():
                    txt.insert("end", linha + "\n", "aviso")
                elif stripped.startswith("❌"):
                    txt.insert("end", linha + "\n", "erro")
                elif "Jogo" in stripped and ":" in stripped:
                    txt.insert("end", linha + "\n", "destaque")
                else:
                    txt.insert("end", linha + "\n", "valor")
            txt.config(state="disabled")

            # ── Rodapé ────────────────────────────────────────────────────
            rodape = ttk.Frame(janela, padding=8)
            rodape.pack(fill="x")

            def salvar_dashboard_txt():
                caminho = filedialog.asksaveasfilename(
                    title="Salvar dashboard em TXT",
                    defaultextension=".txt",
                    filetypes=[("Texto", "*.txt")],
                    initialfile=f"dashboard_lotofacil_{gerar_timestamp_arquivo()}.txt",
                )
                if caminho:
                    with open(caminho, "w", encoding="utf-8") as f:
                        f.write(texto_dashboard)
                    self.log(f"✅ Dashboard salvo em: {caminho}")

            self.criar_botao_colorido(rodape, "Salvar Dashboard TXT", salvar_dashboard_txt, cor="#558b2f").pack(side="left", padx=5)
            self.criar_botao_colorido(rodape, "Fechar", janela.destroy, cor="#c62828").pack(side="right", padx=5)
            self.set_status("Dashboard aberto com sucesso.", "green")
        except Exception as e:
            self.set_status("Erro ao abrir dashboard.", "red")
            self.log("❌ Erro ao abrir dashboard:")
            self.log(str(e))
            self.log(traceback.format_exc())

    def salvar_txt(self) -> None:
        """
        Salva apenas os números dos jogos gerados em TXT.
        Não inclui cabeçalho, relatório, score, métricas ou logs.
        """
        try:
            if not self.jogos_gerados:
                messagebox.showwarning("Aviso", "Gere os jogos antes de salvar.")
                return

            caminho = filedialog.asksaveasfilename(
                title="Salvar jogos em TXT",
                defaultextension=".txt",
                filetypes=[("Texto", "*.txt")],
                initialfile=f"jogos_lotofacil_{gerar_timestamp_arquivo()}.txt",
            )

            if not caminho:
                return

            with open(caminho, "w", encoding="utf-8") as f:
                for idx, jogo in enumerate(self.jogos_gerados, start=1):
                    linha = " ".join(f"{int(n):02d}" for n in sorted(jogo))
                    f.write(f"Jogo {idx}: {linha}" + chr(10))

            self.log(f"✅ Jogos salvos em TXT limpo: {caminho}")
            self.set_status("TXT limpo salvo com sucesso.", "green")

        except Exception as e:
            self.set_status("Erro ao salvar TXT.", "red")
            self.log("❌ Erro ao salvar TXT:")
            self.log(str(e))
            self.log(traceback.format_exc())

    def exportar_pdf(self) -> None:
        """
        Exporta os jogos gerados em PDF com volante visual da Lotofácil
        (`exportar_apostas_pdf`, backtest.py). Função já existia
        implementada mas não tinha nenhum botão na tela (achado de
        auditoria, ver 2026-07-23 no ARQUITETURA.md).
        """
        try:
            if not self.jogos_gerados:
                messagebox.showwarning("Aviso", "Gere os jogos antes de exportar.")
                return

            caminho = filedialog.asksaveasfilename(
                title="Exportar jogos em PDF",
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
                initialfile=f"apostas_{gerar_timestamp_arquivo()}.pdf",
            )
            if not caminho:
                return

            resultado = exportar_apostas_pdf(self.jogos_gerados, caminho_saida=caminho)
            if resultado.get("formato") == "txt_fallback":
                self.log(f"⚠️ {resultado.get('aviso', '')}")
                self.log(f"✅ Jogos exportados em TXT (fallback): {resultado.get('arquivo')}")
                self.set_status("PDF indisponível — exportado como TXT.", "orange")
            else:
                self.log(f"✅ Jogos exportados em PDF: {resultado.get('arquivo')}")
                self.set_status("PDF exportado com sucesso.", "green")

        except Exception as e:
            self.set_status("Erro ao exportar PDF.", "red")
            self.log("❌ Erro ao exportar PDF:")
            self.log(str(e))
            self.log(traceback.format_exc())


    def exportar_excel(self) -> None:
        try:
            caminho_csv = self.caminho_csv.get().strip()
            if not os.path.exists(caminho_csv):
                raise FileNotFoundError("Atualize ou carregue o CSV antes de exportar para Excel.")
            df = pd.read_csv(caminho_csv)
            caminho = exportar_excel_blindado(df, nome_base="lotofacil_resultados_reais")
            if not caminho:
                raise ValueError("Não foi possível gerar o Excel. Instale openpyxl com: pip install openpyxl")
            self.log(f"✅ Excel exportado em: {caminho}")
            self.set_status("Excel exportado com sucesso.", "green")
        except Exception as e:
            self.set_status("Erro ao exportar Excel.", "red")
            self.log("❌ Erro ao exportar Excel:")
            self.log(str(e))
            self.log(traceback.format_exc())

    # ── Comparador de Estratégias ─────────────────────────────

    def abrir_comparador_estrategias(self) -> None:
        """Vai direto para a aba do Comparador."""
        self._notebook_corpo.select(3)

    def _rodar_comparador(self) -> None:
        if not self.concursos:
            messagebox.showwarning("Atenção", "Carregue o histórico antes de comparar.")
            return
        if len(self.concursos) < MIN_HIST + 10:
            messagebox.showwarning("Atenção", f"Histórico insuficiente ({len(self.concursos)} concursos).")
            return

        passos  = max(5,  min(200, int(self._comp_passos.get())))
        qtd     = max(5,  min(30,  int(self._comp_qtd.get())))
        janela  = max(MIN_HIST, min(500, int(self._comp_janela.get())))

        self._lbl_comp_status.config(text="⏳ Rodando comparação… aguarde.", fg=TEMA["amarelo"])
        self._btn_rodar_comp.config(state="disabled")
        self._iniciar_progresso()
        self._notebook_corpo.select(3)
        self._aplicar_seed_configurada()

        def tarefa():
            try:
                resultados = comparar_estrategias(
                    self.concursos, janela, passos, qtd,
                    status_cb=self.log_async,
                )
                self.root.after(0, lambda: self._exibir_resultados_comp(resultados))
            except Exception as e:
                msg = f"❌ Erro no comparador: {e}"
                self.root.after(0, lambda: self._comp_erro(msg))

        threading.Thread(target=tarefa, daemon=True).start()

    def _comp_erro(self, msg: str) -> None:
        self._parar_progresso()
        self._btn_rodar_comp.config(state="normal")
        self._lbl_comp_status.config(text=msg, fg=TEMA["vermelho"])
        self.log(msg)

    def _exibir_resultados_comp(self, resultados: list) -> None:
        """Preenche tabela + gráfico com os resultados do comparador."""
        self._parar_progresso()
        self._btn_rodar_comp.config(state="normal")
        self._resultados_comp = resultados

        # Preenche tabela
        for row in self._tree_comp.get_children():
            self._tree_comp.delete(row)

        medalhas = {0: "🥇", 1: "🥈", 2: "🥉"}
        for i, r in enumerate(resultados):
            pos = medalhas.get(i, str(i + 1))
            self._tree_comp.insert("", "end", iid=str(i), values=(
                pos,
                r["nome"],
                r["score_ponderado"],
                r["media_melhor"],
                r["max_melhor"],
                f"{r['pct_11_mais']}%",
                f"{r['pct_13_mais']}%",
                r["media_geral"],
                r["params"]["geracoes"],
                r["params"]["pop_size"],
                r["params"]["taxa_mutacao"],
                f"{int(r['params']['janela_pct']*100)}%",
                f"{r['tempo_s']}s",
            ), tags=(r["nome"],))
            self._tree_comp.tag_configure(r["nome"], foreground=r["cor"])

        # Destacar campeão
        if resultados:
            self._tree_comp.selection_set("0")

        self._desenhar_grafico_comp(resultados)

        vencedor = resultados[0] if resultados else {}
        self._lbl_comp_status.config(
            text=(f"✅ Comparação concluída! Melhor estratégia: {vencedor.get('nome', '—')} "
                  f"(score {vencedor.get('score_ponderado', '—')} | "
                  f"méd. melhor {vencedor.get('media_melhor', '—')} | "
                  f"≥11: {vencedor.get('pct_11_mais', '—')}%)"),
            fg=TEMA["verde"],
        )
        self.log("=" * 72)
        self.log("COMPARADOR DE ESTRATÉGIAS — RESULTADO")
        for i, r in enumerate(resultados):
            self.log(
                f"#{i+1} {r['nome']:22s} | score={r['score_ponderado']:.3f} | "
                f"méd={r['media_melhor']} | max={r['max_melhor']} | "
                f"≥11={r['pct_11_mais']}% | ≥13={r['pct_13_mais']}% | {r['tempo_s']}s"
            )

    def _desenhar_grafico_comp(self, resultados: list) -> None:
        """Gráfico de barras agrupadas: score ponderado + média do melhor por estratégia."""
        c = self._canvas_comp
        c.delete("all")
        if not resultados:
            return

        c.update_idletasks()
        W = c.winfo_width()  or 900
        H = c.winfo_height() or 220
        mg_l, mg_r, mg_t, mg_b = 55, 20, 30, 55
        w_area = W - mg_l - mg_r
        h_area = H - mg_t - mg_b

        # Escala: max entre score*2 (para caber) e media_melhor*1.1
        max_val = max(
            max(r["score_ponderado"] * 1.1 for r in resultados),
            max(r["media_melhor"]         for r in resultados),
            12,
        )
        escala = h_area / max_val

        n = len(resultados)
        grupo_w = w_area / n
        bw = max(12, min(40, int(grupo_w * 0.3)))
        gap = max(4,  min(12, int(grupo_w * 0.08)))

        bg3, fg, fg2 = TEMA["bg3"], TEMA["fg"], TEMA["fg2"]

        # Fundo
        c.create_rectangle(mg_l, mg_t, W - mg_r, H - mg_b,
                            fill=TEMA["bg2"], outline=bg3)

        # Linhas de grade
        for v in range(0, int(max_val) + 2, 2):
            y = H - mg_b - int(v * escala)
            if y < mg_t:
                break
            c.create_line(mg_l, y, W - mg_r, y, fill=bg3, dash=(3, 4))
            c.create_text(mg_l - 6, y, text=str(v), fill=fg2,
                          font=("Segoe UI", 7), anchor="e")

        # Referência: 11 pontos
        y11 = H - mg_b - int(11 * escala)
        if mg_t <= y11 <= H - mg_b:
            c.create_line(mg_l, y11, W - mg_r, y11,
                          fill=TEMA["amarelo"], dash=(6, 3))
            c.create_text(mg_l - 6, y11, text="11", fill=TEMA["amarelo"],
                          font=("Segoe UI", 7, "bold"), anchor="e")

        for i, r in enumerate(resultados):
            cx = mg_l + int((i + 0.5) * grupo_w)
            cor = r["cor"]

            # Barra score ponderado (esquerda)
            x1s = cx - bw - gap // 2
            y_s = H - mg_b - int(r["score_ponderado"] * escala)
            c.create_rectangle(x1s, y_s, x1s + bw, H - mg_b,
                                fill=cor, outline="", stipple="gray50")
            c.create_text(x1s + bw // 2, y_s - 4,
                          text=f"{r['score_ponderado']:.2f}",
                          fill=cor, font=("Segoe UI", 7), anchor="s")

            # Barra média melhor (direita)
            x1m = cx + gap // 2
            y_m = H - mg_b - int(r["media_melhor"] * escala)
            c.create_rectangle(x1m, y_m, x1m + bw, H - mg_b,
                                fill=cor, outline="")
            c.create_text(x1m + bw // 2, y_m - 4,
                          text=f"{r['media_melhor']}",
                          fill=cor, font=("Segoe UI", 7), anchor="s")

            # Nome (rotacionado simulado — linha vertical + texto)
            nome_curto = r["nome"][:14]
            c.create_text(cx, H - mg_b + 6, text=nome_curto,
                          fill=fg2 if i > 0 else fg,
                          font=("Segoe UI", 8, "bold" if i == 0 else "normal"),
                          anchor="n")

        # Legenda
        lx = mg_l + 4
        ly = mg_t + 4
        c.create_rectangle(lx, ly, lx + 12, ly + 10, fill=TEMA["fg2"], stipple="gray50", outline="")
        c.create_text(lx + 16, ly + 5, text="Score ponderado", fill=fg2,
                      font=("Segoe UI", 7), anchor="w")
        c.create_rectangle(lx + 120, ly, lx + 132, ly + 10, fill=TEMA["fg2"], outline="")
        c.create_text(lx + 136, ly + 5, text="Média do melhor jogo", fill=fg2,
                      font=("Segoe UI", 7), anchor="w")

    def _ordenar_tabela_comp(self, col: str) -> None:
        """Ordena a tabela do comparador ao clicar no cabeçalho."""
        if not self._resultados_comp:
            return
        reverso = (self._comp_sort_col == col) and (not self._comp_sort_asc)
        self._comp_sort_col = col
        self._comp_sort_asc = reverso

        mapa_col = {
            "pos": lambda r: self._resultados_comp.index(r),
            "nome": lambda r: r["nome"],
            "score": lambda r: r["score_ponderado"],
            "med_melhor": lambda r: r["media_melhor"],
            "max": lambda r: r["max_melhor"],
            "pct11": lambda r: r["pct_11_mais"],
            "pct13": lambda r: r["pct_13_mais"],
            "med_geral": lambda r: r["media_geral"],
            "geracoes": lambda r: r["params"]["geracoes"],
            "pop": lambda r: r["params"]["pop_size"],
            "mutacao": lambda r: r["params"]["taxa_mutacao"],
            "janela_pct": lambda r: r["params"]["janela_pct"],
            "tempo": lambda r: r["tempo_s"],
        }
        key_fn = mapa_col.get(col, lambda r: r["score_ponderado"])
        ordenado = sorted(self._resultados_comp, key=key_fn, reverse=not reverso)
        self._exibir_resultados_comp(ordenado)

    def _exportar_comparador(self) -> None:
        """Exporta resultados do comparador para CSV."""
        if not self._resultados_comp:
            messagebox.showwarning("Comparador", "Rode a comparação antes de exportar.")
            return
        caminho = filedialog.asksaveasfilename(
            title="Salvar comparação como CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"comparador_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not caminho:
            return
        try:
            linhas = []
            for i, r in enumerate(self._resultados_comp, 1):
                params = r.get("params", {})
                linhas.append({
                    "Posição": i,
                    "Estratégia": r.get("nome", ""),
                    "Score": r.get("score_ponderado", 0),
                    "Méd.Melhor": r.get("media_melhor", 0),
                    "Máx": r.get("max_melhor", 0),
                    ">=11%": r.get("pct_11_mais", 0),
                    ">=13%": r.get("pct_13_mais", 0),
                    "Méd.Geral": r.get("media_geral", 0),
                    "Gerações": params.get("geracoes", 0),
                    "Pop": params.get("pop_size", 0),
                    "Mutação": params.get("taxa_mutacao", 0),
                    "Janela%": params.get("janela_pct", 0),
                    "Tempo(s)": r.get("tempo_s", 0),
                })
            info = salvar_csv_blindado(pd.DataFrame(linhas), caminho)
            caminho_salvo = info.get("salvo_em", caminho)
            self.log(f"✅ Comparação exportada: {caminho_salvo}")
            messagebox.showinfo("Exportado", f"Arquivo salvo em:\n{caminho_salvo}")
        except Exception as e:
            self.log(f"❌ Erro ao exportar: {e}")

    def abrir_calculadora_probabilidades(self) -> None:
        """Abre janela com calculadora de probabilidades reais da Lotofácil."""
        import math

        bg, bg2, bg3 = TEMA["bg"], TEMA["bg2"], TEMA["bg3"]
        fg, fg2, acc = TEMA["fg"], TEMA["fg2"], TEMA["accent"]

        jan = tk.Toplevel(self.root)
        jan.title("🎰 Calculadora de Probabilidades Reais")
        jan.configure(bg=bg)
        jan.geometry("620x560")
        jan.resizable(False, False)

        # ── Funções de cálculo ────────────────────────────────
        def c(n: int, k: int) -> int:
            return math.comb(n, k)

        def prob_acertar_exatamente(dezenas_jogo: int, acertos: int) -> float:
            """P(acertar exatamente `acertos` em um jogo de `dezenas_jogo` dezenas)."""
            if acertos > dezenas_jogo or acertos > 15:
                return 0.0
            try:
                num = c(15, acertos) * c(25 - 15, dezenas_jogo - acertos)
                den = c(25, dezenas_jogo)
                return num / den if den else 0.0
            except Exception:
                return 0.0

        def prob_pelo_menos_um_acerto(dezenas_jogo: int, acertos: int, n_jogos: int, n_concursos: int) -> float:
            """P(pelo menos um jogo acertar >= acertos em N jogos × M concursos)."""
            p_jogo = sum(prob_acertar_exatamente(dezenas_jogo, k) for k in range(acertos, dezenas_jogo + 1))
            tentativas = n_jogos * n_concursos
            return 1 - (1 - p_jogo) ** tentativas

        def calcular() -> None:
            try:
                dez = int(var_dezenas.get())
                alvo = int(var_alvo.get())
                jogos = int(var_jogos.get())
                conc = int(var_concursos.get())
                custo_jogo = float(var_custo.get())

                if not (15 <= dez <= 20):
                    raise ValueError("Dezenas por jogo: entre 15 e 20")
                if not (11 <= alvo <= 15):
                    raise ValueError("Meta de acertos: entre 11 e 15")
                if jogos < 1 or conc < 1:
                    raise ValueError("Jogos e concursos devem ser ≥ 1")

                p_jogo = sum(prob_acertar_exatamente(dez, k) for k in range(alvo, dez + 1))
                p_pelo_menos_1 = prob_pelo_menos_um_acerto(dez, alvo, jogos, conc)
                custo_total = jogos * conc * custo_jogo
                tentativas = jogos * conc

                # Número esperado de sorteios para acertar ao menos uma vez
                esperado_sorteios = (1 / p_jogo / jogos) if p_jogo > 0 else float("inf")

                linhas = [
                    f"{'─'*52}",
                    f"  Jogo de {dez} dezenas  |  Meta: {alvo}+ acertos",
                    f"{'─'*52}",
                    f"  P(acertar ≥{alvo} em 1 jogo):     1 em {1/p_jogo:,.0f}" if p_jogo > 0 else "  P(acertar): impossível",
                    f"  P(acertar ≥{alvo} ao menos 1x):  {p_pelo_menos_1*100:.4f}%",
                    f"  com {jogos} jogos × {conc} concursos = {tentativas} tentativas",
                    f"",
                    f"  Sorteios esperados p/ acertar 1x: {esperado_sorteios:,.0f}",
                    f"  (com {jogos} jogos/sorteio)",
                    f"",
                    f"  Custo total ({jogos}j × {conc}c × R${custo_jogo:.2f}): R$ {custo_total:,.2f}",
                    f"{'─'*52}",
                    f"  Distribuição de probabilidade:",
                ]
                for k in range(max(11, alvo - 1), dez + 1):
                    p = prob_acertar_exatamente(dez, k)
                    if p > 0:
                        linhas.append(f"    {k} acertos: 1 em {1/p:>14,.0f}  ({p*100:.6f}%)")

                txt_result.config(state="normal")
                txt_result.delete("1.0", "end")
                txt_result.insert("end", "\n".join(linhas))
                txt_result.config(state="disabled")

            except ValueError as e:
                txt_result.config(state="normal")
                txt_result.delete("1.0", "end")
                txt_result.insert("end", f"⚠️ Erro: {e}")
                txt_result.config(state="disabled")

        # ── Layout ────────────────────────────────────────────
        tk.Label(jan, text="🎰  Calculadora de Probabilidades Reais",
                 bg=bg, fg=acc, font=("Segoe UI", 13, "bold")).pack(pady=(16, 4))
        tk.Label(jan, text="Mostra as chances reais com base em combinatória — sem estimativas.",
                 bg=bg, fg=fg2, font=("Segoe UI", 9)).pack(pady=(0, 12))

        form = tk.Frame(jan, bg=bg)
        form.pack(padx=24, fill="x")

        def linha_campo(label: str, var, valor_default, dica: str = ""):
            f = tk.Frame(form, bg=bg)
            f.pack(fill="x", pady=3)
            tk.Label(f, text=label, bg=bg, fg=fg2, font=("Segoe UI", 9), width=26, anchor="w").pack(side="left")
            tk.Entry(f, textvariable=var, width=10, bg=bg2, fg=fg,
                     insertbackground=fg, relief="flat", font=("Segoe UI", 9)).pack(side="left")
            if dica:
                tk.Label(f, text=dica, bg=bg, fg=fg2, font=("Segoe UI", 8)).pack(side="left", padx=8)
            var.set(valor_default)

        var_dezenas   = tk.StringVar()
        var_alvo      = tk.StringVar()
        var_jogos     = tk.StringVar()
        var_concursos = tk.StringVar()
        var_custo     = tk.StringVar()

        linha_campo("Dezenas por jogo:",       var_dezenas,   "15", "(15 a 20)")
        linha_campo("Meta de acertos (mín):",  var_alvo,      "14", "(11 a 15)")
        linha_campo("Jogos por concurso:",      var_jogos,     "30", "")
        linha_campo("Quantidade de concursos:", var_concursos, "52", "(1 ano = ~104)")
        linha_campo("Custo por jogo (R$):",     var_custo,     "3.00", "jogo de 15 dezenas")

        btn_calc = tk.Button(
            jan, text="  Calcular  ", command=calcular,
            bg=acc, fg=bg, activebackground=acc, relief="flat",
            font=("Segoe UI", 10, "bold"), padx=16, pady=6, cursor="hand2",
        )
        btn_calc.pack(pady=12)

        txt_result = tk.Text(
            jan, bg=bg2, fg=fg, font=("Consolas", 10), relief="flat",
            state="disabled", height=14, padx=12, pady=8,
        )
        txt_result.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Calcula imediatamente com os valores padrão
        jan.after(100, calcular)

    def encerrar_aplicativo(self) -> None:
        """Encerra o aplicativo salvando estado e verificando threads ativas."""
        # Verifica se há operações em andamento
        threads_ativas = []
        if getattr(self, "_geracao_ativa", False):
            threads_ativas.append("Geração de jogos")
        if getattr(self, "_backtest_simples_ativo", False):
            threads_ativas.append("Backtest")
        if getattr(self, "calibracao_ativa", False):
            threads_ativas.append("Calibração IA")
        if getattr(self, "auto_diagnostico_ativo", False):
            threads_ativas.append("Auto Diagnóstico")
        if getattr(self, "aprendizado_continuo_ativo", False):
            threads_ativas.append("Aprendizado Contínuo")
        if getattr(self, "backtest_automatico_ativo", False):
            threads_ativas.append("BT Automático")

        aviso = ""
        if threads_ativas:
            aviso = f"\n\n⚠️ Em andamento: {', '.join(threads_ativas)}\nAo encerrar essas operações serão interrompidas."

        try:
            if messagebox.askyesno("Encerrar", f"Deseja encerrar o aplicativo?{aviso}"):
                # Para todas as threads
                self.aprendizado_continuo_ativo = False
                self.calibracao_ativa = False
                self.auto_diagnostico_ativo = False
                self._geracao_ativa = False
                self._backtest_simples_ativo = False
                # Salva estado atual
                try:
                    self.salvar_ultimos_jogos_gerados()
                except Exception:
                    pass
                # Persiste preferencia do Turbo para a proxima sessao
                try:
                    _cache = ler_json(ARQUIVO_CACHE, default={})
                    _cache["modo_turbo_usuario"] = bool(self.modo_turbo.get())
                    salvar_json(ARQUIVO_CACHE, _cache)
                except Exception:
                    pass
                self.root.destroy()
        except Exception:
            self.root.destroy()

    # ─────────────────────────────────────────────────────────────────────────
    # V20.8 — Walk-Forward Validation
    # ─────────────────────────────────────────────────────────────────────────

    def iniciar_walkforward(self) -> None:
        """Dispara a validação Walk-Forward em thread separada."""
        if getattr(self, "_walkforward_ativo", False):
            self.log("⚠️ Walk-Forward já está em execução.")
            return
        if not self.concursos:
            self.log("⚠️ Carregue o histórico antes de executar o Walk-Forward.")
            return
        self._walkforward_ativo = True
        self.set_status("Iniciando Walk-Forward...", "blue")
        self.log("=" * 72)
        self.log("🔀 WALK-FORWARD VALIDATION V20.8 INICIADO")
        self.log("Avalia robustez em múltiplas janelas deslizantes e detecta overfitting.")
        th = threading.Thread(target=self._executar_walkforward, daemon=True)
        th.start()

    def _executar_walkforward(self) -> None:
        try:
            concursos = list(self.concursos)
            janela_treino = min(int(self.janela_hist.get()), len(concursos) - 40)
            janela_treino = max(50, janela_treino)
            janela_teste  = max(10, min(20, len(concursos) // 20))
            passo         = max(10, janela_teste)
            qtd = min(max(5, int(self.qtd_jogos.get())), 20)
            ger = max(10, int(self.geracoes.get()))
            pop = max(30, int(self.pop_size.get()))
            self._aplicar_seed_configurada(log_async=True)

            self.log_async(
                f"Parâmetros: treino={janela_treino} | teste={janela_teste} "
                f"| passo={passo} | jogos={qtd} | G={ger} | P={pop}"
            )
            self.root.after(0, self._iniciar_progresso)

            def fn_gerar(hist):
                jogos, _, _ = gerar_apostas(
                    hist, qtd_jogos=qtd, janela_analise=len(hist),
                    geracoes=ger, pop_size=pop,
                )
                return jogos

            rel = relatorio_walkforward(
                concursos,
                fn_gerar,
                tamanho_treino=janela_treino,
                tamanho_teste=janela_teste,
                passo=passo,
            )

            resumo = rel["resumo"]
            wf     = rel["walkforward"]
            ovf    = rel["overfitting"]

            self.log_async("─" * 60)
            self.log_async(f"✅ Walk-Forward concluído — {wf['n_janelas']} janelas avaliadas")
            self.log_async(f"   Média geral de acertos : {wf['media_geral']:.4f}")
            self.log_async(f"   Desvio entre janelas   : {wf['desvio_geral']:.4f}")
            self.log_async(f"   Score de robustez      : {rel['robustez']:.4f}")
            self.log_async(
                f"   Overfitting            : {'⚠️ DETECTADO' if ovf['overfitting_detectado'] else '✅ NORMAL'} "
                f"[{ovf['severidade']}]  razão={ovf['razao']:.4f}"
            )
            self.log_async(f"   Veredito               : {resumo['veredito']}")

            # V21.5: armazena resultado para Análise Científica V2.
            # Guarda também o qtd_jogos usado nesta rodada: a Análise
            # Científica V2 precisa recalcular a referência aleatória com o
            # MESMO tamanho de pacote usado aqui — o campo "Qtd. jogos" da UI
            # é compartilhado por todas as abas e pode ter mudado até lá.
            rel["qtd_jogos_usado"] = qtd
            self._ultimo_resultado_walkforward = rel

            # V21.5-FULL: alimenta os indicadores permanentes do Walk-Forward
            # Profissional (SQLite) — a aba "Walk-Forward Profissional" do
            # Painel Científico lia esse histórico, mas nada nunca escrevia
            # nele. Usa registrar_walkforward_profissional() (reaproveita
            # as janelas/scores do robô já calculados por `rel` acima) em
            # vez de executar_walkforward_profissional() (que rodaria
            # fn_gerar — o algoritmo genético — de novo em cada janela e
            # dobraria o tempo do botão sem aviso — achado de uso real,
            # ver 2026-07-21 no ARQUITETURA.md).
            try:
                from .v21_5_walkforward_profissional import registrar_walkforward_profissional
                ind_prof = registrar_walkforward_profissional(concursos, rel, qtd_jogos=qtd)
                self.log_async(
                    f"   Walk-Forward Profissional: robustez={ind_prof.get('robustez_pct', 0)}% "
                    f"| estabilidade={ind_prof.get('estabilidade_pct', 0)}% "
                    f"| tendência={ind_prof.get('trend_robustez', '')}"
                )
            except Exception as e_prof:
                self.log_async(f"   (aviso: Walk-Forward Profissional não pôde ser atualizado — {e_prof})")

            # Salva JSON
            try:
                garantir_estrutura_pastas()
                ts = gerar_timestamp_arquivo()
                arq = os.path.join(PASTA_EXPORT, f"walkforward_{ts}.json")
                salvar_relatorio_walkforward(rel, arquivo=arq)
                self.log_async(f"   Relatório JSON salvo em: {arq}")
            except Exception as e_salva:
                self.log_async(f"   (aviso: não foi possível salvar JSON — {e_salva})")

            cor_verd = "green" if resumo["veredito"] == "ROBUSTO" else (
                "red" if resumo["veredito"] == "INSTAVEL" else "blue"
            )
            self.set_status_async(f"Walk-Forward: {resumo['veredito']}", cor_verd)

            try:
                mensagem = (
                    f"Walk-Forward V20.8 concluído!\n\n"
                    f"Janelas avaliadas : {wf['n_janelas']}\n"
                    f"Média de acertos  : {wf['media_geral']:.4f}\n"
                    f"Score de robustez : {rel['robustez']:.4f}\n"
                    f"Overfitting       : {ovf['severidade']}\n\n"
                    f"Veredito: {resumo['veredito']}"
                )
                messagebox.showinfo("Walk-Forward V20.8", mensagem)
            except Exception:
                pass

        except Exception as e:
            self.set_status_async("Erro no Walk-Forward.", "red")
            self.log_async(f"❌ Erro no Walk-Forward: {e}")
            self.log_async(traceback.format_exc())
        finally:
            self._walkforward_ativo = False
            try:
                self.root.after(0, self._parar_progresso)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # V21.6 — Mapa G×P (mapear_vale_gp)
    # ─────────────────────────────────────────────────────────────────────────

    def iniciar_mapa_gp(self) -> None:
        """Dispara o mapeamento G×P em thread separada."""
        if getattr(self, "_mapa_gp_ativo", False):
            self.log("⚠️ Mapa G×P já está em execução.")
            return
        if not self.concursos:
            self.log("⚠️ Carregue o histórico antes de executar o Mapa G×P.")
            return
        self._mapa_gp_ativo = True
        self.set_status("Iniciando Mapa G×P...", "blue")
        self.log("=" * 72)
        self.log("🗺️ MAPA G×P INICIADO")
        self.log("Mapeia o espaço de gerações/população para identificar vale estrutural.")
        th = threading.Thread(target=self._executar_mapa_gp, daemon=True)
        th.start()

    def _executar_mapa_gp(self) -> None:
        try:
            concursos = list(self.concursos)
            janela  = min(int(self.janela_hist.get()), len(concursos) - 40)
            janela  = max(50, janela)
            passos  = max(10, int(self.passos_backtest.get()))
            qtd     = min(max(5, int(self.qtd_jogos.get())), 20)

            self._aplicar_seed_configurada(log_async=True)
            self.log_async(f"Parâmetros: janela={janela} | passos={passos} | jogos={qtd}")
            self.root.after(0, self._iniciar_progresso)

            def fn_gerar(hist, ger, pop, qtd_j):
                jogos, _, _ = gerar_apostas(
                    hist, qtd_jogos=qtd_j, janela_analise=len(hist),
                    geracoes=ger, pop_size=pop,
                )
                return jogos

            def status_cb(msg: str) -> None:
                self.log_async(f"  {msg}")

            resultado = mapear_vale_gp(
                concursos,
                fn_gerar,
                janela=janela,
                passos=passos,
                qtd_jogos=qtd,
                status_cb=status_cb,
            )

            self.log_async("─" * 60)
            self.log_async("✅ Mapa G×P concluído")

            melhor = resultado.get("melhor_config", {})
            if melhor:
                self.log_async(
                    f"   🏆 Melhor config : {melhor.get('nome')} | "
                    f"score={melhor.get('score')} | "
                    f"12+={melhor.get('pct_12_mais')}% | "
                    f"vantagem={melhor.get('vantagem_pct')}%"
                )

            self.log_async(f"   Vale confirmado : {'✅ SIM' if resultado.get('vale_confirmado') else '❌ NÃO'} (teste estatístico pareado, não heurística)")
            self.log_async(f"   Análise         : {resultado.get('analise', '')}")

            comparacoes = resultado.get("comparacoes_pareadas") or []
            if comparacoes:
                self.log_async("")
                self.log_async(f"🔬 Comparações pareadas vs. referência G={resultado.get('referencia_extremo')}:")
                for c in comparacoes:
                    if c.get("veredito") == "INCONCLUSIVO" and "cohen_d_pareado" not in c:
                        self.log_async(f"   G={c['g']}: INCONCLUSIVO ({c.get('motivo', '')})")
                        continue
                    self.log_async(
                        f"   G={c['g']}: {c['veredito']} | d_z={c['cohen_d_pareado']:.3f} ({c.get('magnitude','')}) | "
                        f"p={c['p_value']:.4f} | IC90%={c['ic_90']} | n={c['n']}"
                    )

            self.log_async("")
            self.log_async("📊 Ranking completo (score heurístico — só triagem, ver Vale confirmado acima para o veredito estatístico):")
            for r in resultado.get("resultados", []):
                self.log_async(
                    f"   {r['nome']:12s} | score={r['score']:.4f} | "
                    f"média={r['media_melhor']} | 12+={r['pct_12_mais']}% | "
                    f"13+={r['pct_13_mais']}% | vitórias={r['vit_robo']}/{r['passos_executados']}"
                )

            self.set_status_async("Mapa G×P concluído.", "green")

        except Exception as e:
            self.set_status_async("Erro no Mapa G×P.", "red")
            self.log_async(f"❌ Erro no Mapa G×P: {e}")
            self.log_async(traceback.format_exc())
        finally:
            self._mapa_gp_ativo = False
            try:
                self.root.after(0, self._parar_progresso)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # V22 — Otimizador de Pacotes por Simulação
    # ─────────────────────────────────────────────────────────────────────────

    def iniciar_otimizador_v22(self) -> None:
        """Dispara o Otimizador V22 em thread separada."""
        if not _V22_OK:
            self.log("❌ Módulos V22 não disponíveis.")
            return
        if getattr(self, "_otimizador_v22_ativo", False):
            self.log("⚠️ Otimizador já está em execução.")
            return
        if not self.concursos:
            self.log("⚠️ Carregue o histórico antes de usar o Otimizador.")
            return
        self._otimizador_v22_ativo = True
        self.set_status("Otimizador iniciado...", "blue")
        th = threading.Thread(target=self._executar_otimizador_v22, daemon=True)
        th.start()

    def _executar_otimizador_v22(self) -> None:
        try:
            concursos  = list(self.concursos)
            janela     = min(int(self.janela_hist.get()), len(concursos) - 40)
            janela     = max(50, janela)
            ger        = int(self.geracoes.get())
            pop        = int(self.pop_size.get())
            qtd        = min(max(5, int(self.qtd_jogos.get())), 40)
            tentativas = 10

            self.log("=" * 72)
            self.log("⚡ OTIMIZADOR INICIADO")
            self._aplicar_seed_configurada()
            self.log(f"Parâmetros: janela={janela} | G={ger} | P={pop} | jogos={qtd} | tentativas={tentativas}")
            self.root.after(0, self._iniciar_progresso)

            def fn_gerar(hist):
                jogos, analise, pesos = gerar_apostas(
                    hist,
                    qtd_jogos=qtd,
                    janela_analise=janela,
                    geracoes=ger,
                    pop_size=pop,
                )
                return jogos, analise, pesos

            jogos_otimizados, analise_otim, pesos_otim, relatorio = _otimizar_pacote(
                concursos,
                fn_gerar,
                limiar_11=95.0,
                limiar_media=11.20,
                max_tentativas=tentativas,
                n_simulacoes=1000,
                status_cb=self.log_async,
            )

            if jogos_otimizados:
                self.jogos_gerados = jogos_otimizados
                self.analise = analise_otim
                self.pesos = pesos_otim
                self.info_backtest = None
                met = relatorio.get("metricas", {})
                self.log_async("=" * 72)
                self.log_async("✅ Otimizador concluído")
                self.log_async(f"   Tentativas realizadas : {relatorio.get('tentativas_realizadas')}")
                self.log_async(f"   Limiar atingido       : {'✅ SIM' if relatorio.get('limiar_atingido') else '⚠️ NÃO — melhor encontrado'}")
                self.log_async(f"   11+%                  : {met.get('pct_11_mais')}%")
                self.log_async(f"   12+%                  : {met.get('pct_12_mais')}%")
                self.log_async(f"   Média do melhor       : {met.get('media_melhor')}")
                self.log_async("")
                self.log_async("📋 Jogos otimizados:")
                for i, jogo in enumerate(jogos_otimizados, 1):
                    self.log_async(f"   Jogo {i:02d}: {' '.join(f'{d:02d}' for d in sorted(jogo))}")
                self.salvar_ultimos_jogos_gerados()
                self.root.after(0, self._atualizar_tabela_jogos)
                self.root.after(0, self._atualizar_painel_info)
                self.set_status_async("Otimizador concluído.", "green")
            else:
                self.log_async("❌ Otimizador não gerou jogos válidos.")
                self.set_status_async("Erro no Otimizador.", "red")

        except Exception as e:
            self.set_status_async("Erro no Otimizador.", "red")
            self.log_async(f"❌ Erro no Otimizador: {e}")
            self.log_async(traceback.format_exc())
        finally:
            self._otimizador_v22_ativo = False
            try:
                self.root.after(0, self._parar_progresso)
            except Exception:
                pass

    # V22 — Pipeline Automático
    # ─────────────────────────────────────────────────────────────────────────

    def iniciar_pipeline_v22(self) -> None:
        """Dispara o Pipeline Automático V22 em thread separada."""
        if not _V22_OK:
            self.log("❌ Módulos V22 não disponíveis.")
            return
        if getattr(self, "_pipeline_v22_ativo", False):
            self.log("⚠️ Pipeline V22 já está em execução.")
            return
        if not self.concursos:
            self.log("⚠️ Carregue o histórico antes de rodar o Pipeline V22.")
            return
        self._pipeline_v22_ativo = True
        self.set_status("Pipeline V22 iniciado...", "blue")
        try:
            pipeline = PipelineV22(
                app=self,
                log_cb=self.log_async,
                status_cb=lambda m: self.set_status_async(m, "blue"),
            )
            pipeline.executar(em_thread=True)
        except Exception as e:
            self.log(f"❌ Erro ao iniciar Pipeline V22: {e}")
            self.set_status("Erro no Pipeline V22.", "red")
        finally:
            self._pipeline_v22_ativo = False

    # ─────────────────────────────────────────────────────────────────────────
    # V20.6 — Bootstrap IC (Inferência Estatística)
    # ─────────────────────────────────────────────────────────────────────────

    def iniciar_bootstrap_ic(self) -> None:
        """Calcula IC bootstrap e abre janela de resultados."""
        info = getattr(self, "info_backtest", None)
        if info is None:
            self.log("⚠️ Execute um Backtest primeiro para ter resultados disponíveis.")
            messagebox.showwarning(
                "Bootstrap IC",
                "Nenhum resultado de backtest encontrado.\nExecute o Backtest antes de usar esta função."
            )
            return

        if getattr(self, "_bootstrap_ativo", False):
            self.log("⚠️ Bootstrap IC já está em execução.")
            return

        self._bootstrap_ativo = True
        self.set_status("Calculando Bootstrap IC...", "blue")
        self.log("=" * 72)
        self.log("📐 BOOTSTRAP IC V20.6 INICIADO")
        th = threading.Thread(target=self._executar_bootstrap_ic, daemon=True)
        th.start()

    def _executar_bootstrap_ic(self) -> None:
        try:
            info = getattr(self, "info_backtest", {})

            # Monta lista de resultados a partir da serie real por passo do backtest.
            # NAO usar fallback de media_melhor replicada: isso produz uma amostra
            # sem variancia (erro padrao sempre 0, IC degenerado no ponto observado)
            # -- resultado estatisticamente sem sentido, mesmo "parecendo" valido
            # num JSON (achado de auditoria, 2026-07-18: bootstrap_ic_20260718_103521.json
            # tinha erro_padrao_bootstrap=0.0 porque backtest_ultra_massivo() nao
            # devolvia "acertos_por_passo" -- corrigido em backtest.py).
            resultados = [
                {"acertos": float(v)}
                for v in info.get("acertos_por_passo", [])
                if isinstance(v, (int, float))
            ]
            if len(resultados) < 2:
                # Bootstrap IC lê especificamente self.info_backtest — só
                # "📊 Backtest" preenche esse atributo. "🤖 BT Automático"
                # guarda seu resultado em self.info_backtest_automatico (sem
                # "acertos_por_passo"), então recomendá-lo aqui não resolvia
                # nada (achado de auditoria, ver 2026-07-23 no ARQUITETURA.md).
                self.log_async(
                    "⚠️ Bootstrap IC: nenhuma série de acertos por passo disponível "
                    "no último backtest (ou com menos de 2 pontos) — não é possível "
                    "calcular variância real. Execute 📊 Backtest novamente antes de "
                    "tentar de novo."
                )
                self.set_status_async("Bootstrap IC: dados insuficientes.", "red")
                return

            self.log_async(f"Amostra para inferência: {len(resultados)} observações")
            self.log_async(
                "Nota: este relatório mede IC/erro padrão da série do backtest — "
                "não compara contra aleatório (sem p-value/Cohen's d aqui; use "
                "🎯 Calibrar IA ou 🗺️ Mapa G×P para isso)."
            )
            self.root.after(0, self._iniciar_progresso)

            rel = relatorio_inferencial(resultados, n_reamostras=2000, seed=42)

            ic    = rel["ic_media"]
            resum = rel["resumo"]
            ic95  = ic["intervalos"].get("95%", {})
            ic99  = ic["intervalos"].get("99%", {})

            self.log_async("─" * 60)
            self.log_async("✅ Bootstrap IC V20.6 concluído")
            self.log_async(f"   Média observada : {ic['media_observada']:.4f}")
            self.log_async(f"   IC 95%          : [{ic95.get('inferior','?')} – {ic95.get('superior','?')}]")
            self.log_async(f"   IC 99%          : [{ic99.get('inferior','?')} – {ic99.get('superior','?')}]")
            self.log_async(f"   Erro padrão     : {ic['erro_padrao_bootstrap']:.4f}")
            self.log_async(f"   Mediana (boot.) : {ic['mediana_bootstrap']:.4f}")
            self.log_async(f"   Amostras usadas : {ic['n_amostras']}")
            if resum.get("veredito_comparacao", "N/A") != "N/A":
                self.log_async(f"   Veredito        : {resum.get('veredito_comparacao')}")
                self.log_async(f"   p-value         : {resum.get('p_value')}")
                self.log_async(f"   Cohen's d       : {resum.get('cohen_d')} ({resum.get('magnitude_efeito')})")

            # Salva JSON
            try:
                garantir_estrutura_pastas()
                ts = gerar_timestamp_arquivo()
                arq = os.path.join(PASTA_EXPORT, f"bootstrap_ic_{ts}.json")
                salvar_relatorio_inferencial(rel, arquivo=arq)
                self.log_async(f"   Relatório JSON salvo em: {arq}")
            except Exception as e_salva:
                self.log_async(f"   (aviso: não foi possível salvar JSON — {e_salva})")

            self.set_status_async("Bootstrap IC concluído.", "green")

            # Pop-up com resultado
            try:
                linhas = [
                    "Bootstrap IC V20.6\n",
                    f"Média observada : {ic['media_observada']:.4f}",
                    f"IC 95%          : [{ic95.get('inferior','?')} – {ic95.get('superior','?')}]",
                    f"IC 99%          : [{ic99.get('inferior','?')} – {ic99.get('superior','?')}]",
                    f"Erro padrão     : {ic['erro_padrao_bootstrap']:.4f}",
                    f"Mediana (boot.) : {ic['mediana_bootstrap']:.4f}",
                    f"Amostras        : {ic['n_amostras']}",
                ]
                texto_resultado = "\n".join(linhas)
                self.root.after(0, lambda t=texto_resultado: self._abrir_janela_resultado_bootstrap(t))
            except Exception:
                pass

        except Exception as e:
            self.set_status_async("Erro no Bootstrap IC.", "red")
            self.log_async(f"❌ Erro no Bootstrap IC: {e}")
            self.log_async(traceback.format_exc())
        finally:
            self._bootstrap_ativo = False
            try:
                self.root.after(0, self._parar_progresso)
            except Exception:
                pass

    # ── V21.5 — Análise Científica V2 ────────────────────────────────────────

    def iniciar_analise_cientifica_v2(self) -> None:
        """
        Executa as melhorias científicas V21.5:
          1. Teste binomial de significância sobre a última calibração.
          2. Score de robustez walk-forward V2 (métrica corrigida).

        Usa os dados já calculados em memória (_ultimo_resultado_calibracao
        e _ultimo_resultado_walkforward). Se não houver dados, instrui o
        usuário a rodar Calibrar IA e Walk-Forward primeiro.
        """
        if getattr(self, "_analise_cient_v2_ativa", False):
            self.log("⚠️ Análise Científica V2 já está em execução.")
            return

        # Verificar dados disponíveis
        calib = getattr(self, "_ultimo_resultado_calibracao", None)
        wf    = getattr(self, "_ultimo_resultado_walkforward", None)

        if calib is None and wf is None:
            self.log("⚠️ Análise Científica V2: rode 'Calibrar IA' e 'Walk-Forward' primeiro.")
            self.log("   → Os resultados serão armazenados automaticamente para esta análise.")
            return

        self._analise_cient_v2_ativa = True
        self.set_status("Análise Científica V2...", "blue")
        import threading
        th = threading.Thread(target=self._executar_analise_cientifica_v2, daemon=True)
        th.start()

    def _executar_analise_cientifica_v2(self) -> None:
        """Thread principal da Análise Científica V2."""
        import traceback as _tb
        try:
            self.log_async("=" * 72)
            self.log_async("🔬 ANÁLISE CIENTÍFICA V2 — INICIADA")
            self.log_async("Teste binomial + Walk-Forward com métrica corrigida.")
            self.log_async("─" * 60)

            calib = getattr(self, "_ultimo_resultado_calibracao", None)
            wf    = getattr(self, "_ultimo_resultado_walkforward", None)
            # Usa o qtd_jogos que gerou os dados do Walk-Forward armazenado
            # (não o valor atual do campo "Qtd. jogos" da UI, que pode ter
            # mudado desde então — ver iniciar_walkforward/qtd_jogos_usado).
            # Isso garante que a referência aleatória estimada corresponda
            # ao mesmo tamanho de pacote realmente testado no Walk-Forward.
            if wf is not None and wf.get("qtd_jogos_usado"):
                qtd = int(wf["qtd_jogos_usado"])
            else:
                qtd = int(self.qtd_jogos.get()) if hasattr(self, "qtd_jogos") else 20

            # ── 1. TESTE BINOMIAL ─────────────────────────────────────────
            if calib is not None:
                vr  = int(calib.get("robo_venceu_score", 0))
                va  = int(calib.get("aleatorio_venceu_score", 0))
                emp = int(calib.get("empates_score", 0))

                self.log_async("📊 1. TESTE DE SIGNIFICÂNCIA BINOMIAL")
                self.log_async(f"   Vitórias robô={vr} | Aleatório={va} | Empates={emp}")

                sig = teste_significancia_calibracao(vr, va, emp)

                self.log_async(f"   N efetivo        : {sig['n_efetivo']}")
                self.log_async(f"   Proporção robô   : {sig['proporcao_robo']:.1%}")
                self.log_async(f"   p-value          : {sig['p_value']:.4f}")
                self.log_async(f"   Significativo    : {'✅ SIM' if sig['significativo'] else '⚠️ NÃO'} (α=5%)")
                self.log_async(f"   IC 95%           : [{sig['ic_95_inferior']:.1%}, {sig['ic_95_superior']:.1%}]")
                if sig.get("passos_extras_para_significancia"):
                    self.log_async(
                        f"   Para significância: ~{sig['passos_extras_para_significancia']} "
                        f"passos adicionais mantendo proporção atual."
                    )
                self.log_async(f"   → {sig['interpretacao']}")
            else:
                self.log_async("⚠️ 1. Sem dados de calibração — rode 'Calibrar IA' primeiro.")
                sig = None

            self.log_async("─" * 60)

            # ── 2. WALK-FORWARD V2 ────────────────────────────────────────
            if wf is not None:
                wf_data    = wf.get("walkforward", {})
                janelas    = wf_data.get("janelas", [])
                medias     = wf_data.get("medias_por_janela", [])
                melhores   = [j.get("melhor_acerto", 0) for j in janelas]

                self.log_async("📊 2. WALK-FORWARD V2 — MÉTRICA CORRIGIDA")
                self.log_async(f"   Janelas disponíveis: {len(janelas)}")

                if melhores:
                    self.log_async("   Estimando referência do aleatório...")
                    ref = estimar_referencia_melhor_aleatorio(qtd_jogos=qtd, n_simulacoes=5_000)
                    self.log_async(f"   Referência melhor aleatório ({qtd} jogos): {ref:.2f}")

                    wf_v2 = score_robustez_walkforward_v2(
                        [float(m) for m in melhores],
                        [float(m) for m in medias],
                        referencia_melhor_aleatorio=ref,
                    )

                    self.log_async(f"   Score V1 (legado)  : {wf_v2['score_v1_legado']:.4f}")
                    self.log_async(f"   Score V2 (correto) : {wf_v2['score_v2']:.4f}  [{wf_v2['veredito_v2']}]")
                    self.log_async(f"   Δ Score (V2−V1)    : {wf_v2['delta_score']:+.4f}")
                    self.log_async(f"   Média melhor/janela: {wf_v2['media_melhor_por_janela']:.4f}")
                    self.log_async(f"   Ganho V2           : {wf_v2['componente_ganho_v2']:.4f}")
                    self.log_async(f"   Ganho V1           : {wf_v2['componente_ganho_v1']:.4f}")
                    self.log_async(f"   Consistência       : {wf_v2['componente_consistencia']:.4f}")
                    self.log_async(f"   → {wf_v2['interpretacao']}")
                else:
                    self.log_async("   ⚠️ Sem dados de janelas individuais no walk-forward.")
                    wf_v2 = None
            else:
                self.log_async("⚠️ 2. Sem dados de Walk-Forward — rode 'Walk-Forward' primeiro.")
                wf_v2 = None

            self.log_async("─" * 60)
            self.log_async("✅ Análise Científica V2 concluída.")

            # Cor do status baseada nos resultados
            if sig and sig["significativo"] and wf_v2 and wf_v2["score_v2"] >= 0.6:
                cor = "green"
                veredito_geral = "ROBUSTEZ CONFIRMADA"
            elif sig and not sig["significativo"]:
                cor = "orange"
                veredito_geral = "MAIS PASSOS NECESSÁRIOS"
            else:
                cor = "blue"
                veredito_geral = "ACEITÁVEL"

            self.set_status_async(f"Análise V2: {veredito_geral}", cor)

        except Exception as e:
            self.set_status_async("Erro na Análise Científica V2.", "red")
            self.log_async(f"❌ Erro na Análise Científica V2: {e}")
            self.log_async(_tb.format_exc())
        finally:
            self._analise_cient_v2_ativa = False
            try:
                self.root.after(0, self._parar_progresso)
            except Exception:
                pass

    def _abrir_janela_resultado_bootstrap(self, texto: str) -> None:
        """Abre janela pop-up estilizada com os resultados do Bootstrap IC."""
        bg  = TEMA["bg"]
        bg2 = TEMA["bg2"]
        fg  = TEMA["fg"]
        acc = TEMA["accent"]

        janela = tk.Toplevel(self.root)
        janela.title("📐 Bootstrap IC — V20.6")
        janela.configure(bg=bg)
        janela.resizable(False, False)

        tk.Label(
            janela, text="📐  Inferência Estatística Bootstrap — V20.6",
            bg=bg, fg=acc, font=("Segoe UI", 11, "bold")
        ).pack(padx=20, pady=(16, 4))

        tk.Label(
            janela,
            text="Intervalo de confiança da média de acertos por reamostragem bootstrap (2000 iterações).",
            bg=bg, fg=TEMA["fg2"], font=("Segoe UI", 8),
        ).pack(padx=20, pady=(0, 10))

        frame_txt = tk.Frame(janela, bg=bg2, bd=0)
        frame_txt.pack(padx=20, pady=(0, 10), fill="both")

        txt = tk.Text(
            frame_txt, bg=bg2, fg=fg, font=("Consolas", 10),
            relief="flat", bd=0, width=52, height=texto.count("\n") + 2,
            state="normal", wrap="none",
        )
        txt.insert("end", texto)
        txt.config(state="disabled")
        txt.pack(padx=8, pady=8)

        self.criar_botao_colorido(
            janela, "Fechar", janela.destroy, cor=TEMA["btn_limpar"]
        ).pack(pady=(0, 14))

    def limpar(self) -> None:
        self.txt_saida.delete("1.0", "end")
        self.set_status("Pronto.", "blue")


# =========================================================
# MAIN
# =========================================================
def main():
    garantir_estrutura_pastas()
    seed_global(SEED)
    root = tk.Tk()
    app = RoboLotofacilUltraApp(root)
    root.mainloop()




if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        import os
        from datetime import datetime

        erro = traceback.format_exc()
        pasta = os.path.join(os.path.expanduser("~"), "Documents", "RoboLotofacilPro", "logs")
        os.makedirs(pasta, exist_ok=True)
        caminho_log = os.path.join(pasta, "erro_inicializacao_interface_premium.txt")

        with open(caminho_log, "w", encoding="utf-8") as f:
            f.write("ERRO AO INICIAR O ROBÔ LOTOFÁCIL\n")
            f.write("=" * 80 + "\n")
            f.write(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + "\n\n")
            f.write(erro)

        try:
            import tkinter as tk
            from tkinter import messagebox
            root_erro = tk.Tk()
            root_erro.withdraw()
            messagebox.showerror(
                "Erro ao iniciar o robô",
                "O programa encontrou um erro na inicialização.\n\n"
                f"O relatório foi salvo em:\n{caminho_log}\n\n"
                "Copie a mensagem desse arquivo e me envie."
            )
            root_erro.destroy()
        except Exception:
            print(erro)
            print("\nRelatório salvo em:", caminho_log)
            input("\nPressione ENTER para fechar...")
