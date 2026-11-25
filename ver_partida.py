import argparse
import csv
import os
import random
import time
import tkinter as tk
from tkinter import ttk
import agentes
import othello
from othello import PRETAS, BRANCAS, PASS

CASA = 64
MARGEM = 30
FUNDO = "#16241c"
PAINEL = "#1f3328"
VERDE = "#2e7552"
LINHA = "#1d5238"
TEXTO = "#e6ece8"
TEXTO_FRACO = "#9fc2ae"
LARANJA = "#f0883e"
PRETA = "#141414"
BRANCA = "#f4f4ee"


def botao(pai, texto, comando, destaque=False):
    cor = LARANJA if destaque else PAINEL
    b = tk.Button(pai, text=texto, command=comando, font=("Segoe UI", 11, "bold"),
                  bg=cor, fg=FUNDO if destaque else TEXTO, activebackground=VERDE, activeforeground=TEXTO,
                  relief="flat", bd=0, highlightthickness=0, padx=14, pady=8, cursor="hand2")
    return b


class Tela:
    def __init__(self, janela, titulo):
        self.janela = janela
        self.estados = [othello.estado_inicial()]
        self.jogadas = []
        self.infos = []
        self.atual = 0
        self.rodando = False
        self.pausa_ms = 500
        self.proxima_jogada = None

        janela.configure(bg=FUNDO)
        self.titulo = tk.Label(janela, text=titulo, font=("Segoe UI", 14, "bold"), bg=FUNDO, fg=TEXTO)
        self.titulo.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(12, 4))
        self.topo = tk.Frame(janela, bg=FUNDO)
        self.topo.grid(row=1, column=0, columnspan=2, sticky="w", padx=16)

        lado = 8 * CASA + 2 * MARGEM
        self.canvas = tk.Canvas(janela, width=lado, height=lado, bg=FUNDO, highlightthickness=0)
        self.canvas.grid(row=2, column=0, padx=(12, 6), pady=8)

        painel = tk.Frame(janela, bg=PAINEL, padx=16, pady=14)
        painel.grid(row=2, column=1, sticky="ns", padx=(6, 16), pady=8)
        self.placar = tk.Canvas(painel, width=230, height=60, bg=PAINEL, highlightthickness=0)
        self.placar.pack(anchor="w")
        self.lance = tk.Label(painel, font=("Segoe UI", 12), bg=PAINEL, fg=TEXTO_FRACO, anchor="w")
        self.lance.pack(anchor="w", pady=(6, 10))
        self.ultima = tk.Label(painel, font=("Segoe UI", 12), bg=PAINEL, fg=TEXTO, justify="left",
                               anchor="nw", wraplength=230, width=26, height=4)
        self.ultima.pack(anchor="w")
        self.situacao = tk.Label(painel, font=("Segoe UI", 13, "bold"), bg=PAINEL, fg=LARANJA, justify="left",
                                 anchor="w", width=24)
        self.situacao.pack(anchor="w", pady=(14, 0))
        tk.Label(painel, text="anel laranja = última jogada\nponto laranja = peça que virou\nbolinha clara = jogada possível",
                 font=("Segoe UI", 9), bg=PAINEL, fg=TEXTO_FRACO, justify="left").pack(side="bottom", anchor="w")

        barra = tk.Frame(janela, bg=FUNDO)
        barra.grid(row=3, column=0, columnspan=2, pady=(4, 14))
        self.extra = tk.Frame(barra, bg=FUNDO)
        self.extra.pack(side="left", padx=(0, 12))
        botao(barra, "<< Início", lambda: self.parar_e_ir(0)).pack(side="left", padx=3)
        botao(barra, "< Voltar", lambda: self.parar_e_ir(self.atual - 1)).pack(side="left", padx=3)
        botao(barra, "Avançar >", self.avancar).pack(side="left", padx=3)
        self.botao_play = botao(barra, "Jogar até o fim", self.play, destaque=True)
        self.botao_play.pack(side="left", padx=3)
        botao(barra, "Fim >>", self.fim).pack(side="left", padx=3)

        janela.bind("<Left>", lambda e: self.parar_e_ir(self.atual - 1))
        janela.bind("<Right>", lambda e: self.avancar())
        janela.bind("<space>", lambda e: self.play())

    # ---- dados ----
    def limpar(self):
        self.estados = [othello.estado_inicial()]
        self.jogadas = []
        self.infos = []
        self.atual = 0

    def carregar_sequencia(self, sequencia, infos=None):
        self.parar()
        self.limpar()
        for i, nome in enumerate(sequencia):
            self.estados.append(othello.aplicar_acao(self.estados[-1], othello.casa_pelo_nome(nome)))
            self.jogadas.append(nome)
            self.infos.append(infos[i] if infos and i < len(infos) else "")
        self.ir(0)

    def acabou(self):
        if self.atual < len(self.estados) - 1:
            return False
        return self.proxima_jogada is None or othello.eh_terminal(self.estados[-1])

    # ---- botoes ----
    def ir(self, n):
        self.atual = max(0, min(n, len(self.estados) - 1))
        self.desenhar()

    def parar_e_ir(self, n):
        self.parar()
        self.ir(n)

    def avancar(self):
        if self.atual < len(self.estados) - 1:
            self.ir(self.atual + 1)
        elif self.proxima_jogada and not othello.eh_terminal(self.estados[-1]):
            vez = "pretas" if self.estados[-1].jogador == PRETAS else "brancas"
            self.situacao.config(text="%s pensando..." % vez)
            self.janela.update()
            self.proxima_jogada()
            self.ir(len(self.estados) - 1)

    def play(self):
        if self.rodando:
            self.parar()
            return
        if self.acabou():
            self.ir(0)
        self.rodando = True
        self.botao_play.config(text="Pausar")
        self.passo_automatico(self.pausa_ms)

    def fim(self):
        if self.proxima_jogada and not othello.eh_terminal(self.estados[-1]):
            self.rodando = True
            self.botao_play.config(text="Pausar")
            self.passo_automatico(1)
        else:
            self.parar_e_ir(len(self.estados) - 1)

    def passo_automatico(self, pausa):
        if not self.rodando:
            return
        if self.acabou():
            self.parar()
            return
        self.avancar()
        self.janela.after(pausa, lambda: self.passo_automatico(pausa))

    def parar(self):
        self.rodando = False
        self.botao_play.config(text="Jogar até o fim")

    # ---- desenho ----
    def desenhar(self):
        c = self.canvas
        c.delete("all")
        estado = self.estados[self.atual]
        ultima = None
        viradas = []
        if self.atual > 0:
            antes = self.estados[self.atual - 1].tabuleiro
            if self.jogadas[self.atual - 1] != PASS:
                ultima = othello.casa_pelo_nome(self.jogadas[self.atual - 1])
            viradas = [casa for casa in othello.CASAS
                       if antes[casa] != 0 and antes[casa] != estado.tabuleiro[casa]]

        c.create_rectangle(MARGEM - 4, MARGEM - 4, MARGEM + 8 * CASA + 4, MARGEM + 8 * CASA + 4, fill=LINHA, outline="")
        for i in range(8):
            c.create_text(MARGEM + i * CASA + CASA / 2, MARGEM / 2 - 2, text="abcdefgh"[i], fill=TEXTO_FRACO,
                          font=("Segoe UI", 11))
            c.create_text(MARGEM / 2 - 2, MARGEM + i * CASA + CASA / 2, text=str(i + 1), fill=TEXTO_FRACO,
                          font=("Segoe UI", 11))
        for linha in range(8):
            for coluna in range(8):
                x = MARGEM + coluna * CASA
                y = MARGEM + linha * CASA
                c.create_rectangle(x, y, x + CASA, y + CASA, fill=VERDE, outline=LINHA, width=2)
                casa = othello.indice(linha, coluna)
                valor = estado.tabuleiro[casa]
                if valor != 0:
                    c.create_oval(x + 9, y + 11, x + CASA - 7, y + CASA - 5, fill=LINHA, outline="")
                    cor = PRETA if valor == PRETAS else BRANCA
                    c.create_oval(x + 7, y + 7, x + CASA - 7, y + CASA - 7, fill=cor, outline="")
                if casa in viradas:
                    c.create_oval(x + CASA / 2 - 5, y + CASA / 2 - 5, x + CASA / 2 + 5, y + CASA / 2 + 5,
                                  fill=LARANJA, outline="")
                if casa == ultima:
                    c.create_oval(x + 4, y + 4, x + CASA - 4, y + CASA - 4, outline=LARANJA, width=4)

        for casa in othello.colocacoes_legais(estado.tabuleiro, estado.jogador):
            linha, coluna = othello.linha_coluna(casa)
            x = MARGEM + coluna * CASA + CASA / 2
            y = MARGEM + linha * CASA + CASA / 2
            c.create_oval(x - 6, y - 6, x + 6, y + 6, fill="#5c9a78", outline="")

        pretas, brancas = othello.contagem(estado)
        p = self.placar
        p.delete("all")
        p.create_oval(4, 10, 40, 46, fill=PRETA, outline=TEXTO_FRACO)
        p.create_text(50, 28, text=str(pretas), anchor="w", fill=TEXTO, font=("Segoe UI", 22, "bold"))
        p.create_oval(120, 10, 156, 46, fill=BRANCA, outline="")
        p.create_text(166, 28, text=str(brancas), anchor="w", fill=TEXTO, font=("Segoe UI", 22, "bold"))

        total = len(self.estados) - 1
        if self.atual == 0:
            self.lance.config(text="início da partida")
        else:
            self.lance.config(text="jogada %d de %d" % (self.atual, total))

        if self.atual > 0:
            quem = "Pretas" if self.estados[self.atual - 1].jogador == PRETAS else "Brancas"
            jogada = self.jogadas[self.atual - 1]
            texto = "%s %s" % (quem, "passaram a vez" if jogada == PASS else "jogaram em " + jogada)
            if self.infos[self.atual - 1]:
                texto += "\n" + self.infos[self.atual - 1]
            if viradas:
                texto += "\nviraram %d peça%s" % (len(viradas), "s" if len(viradas) > 1 else "")
            self.ultima.config(text=texto)
        else:
            self.ultima.config(text="Clique em Avançar para ver\numa jogada por vez, ou em\nJogar até o fim.")

        if othello.eh_terminal(estado):
            v = othello.vencedor(estado)
            self.situacao.config(text="FIM: " + ("empate" if v == 0 else ("pretas venceram" if v == PRETAS else "brancas venceram")))
        else:
            self.situacao.config(text="vez das " + ("pretas" if estado.jogador == PRETAS else "brancas"))


# ---- modo rever ----
def modo_rever(janela, pasta):
    partidas = list(csv.DictReader(open(os.path.join(pasta, "partidas.csv"), encoding="utf-8")))
    decisoes = {}
    caminho_dec = os.path.join(pasta, "decisoes.csv")
    if os.path.exists(caminho_dec):
        for d in csv.DictReader(open(caminho_dec, encoding="utf-8")):
            texto = d["agente"]
            if d["agente"] == "mcts" and d["forcada"] != "True":
                texto += ": %s simulações" % d["iteracoes"]
            texto += " (%.0f ms)" % (float(d["tempo_efetivo_s"]) * 1000)
            decisoes.setdefault(d["id_partida"], []).append(texto)

    partidas.sort(key=lambda r: (r["experimento"], r["adversario"], int(r["orcamento"]), int(r["bloco"]), r["cor_avaliado"]))
    nomes = ["%s | mcts %s vs %s | bloco %s | mcts de %s | %s" % (
        r["experimento"], r["orcamento"], r["adversario"] + (" " + r["orcamento_adversario"] if r["orcamento_adversario"] else ""),
        r["bloco"], r["cor_avaliado"], r["resultado"]) for r in partidas]

    tela = Tela(janela, "Rever partidas gravadas")
    escolha = ttk.Combobox(tela.topo, values=nomes, width=80, state="readonly")
    escolha.pack(anchor="w", pady=4)

    def abrir(evento=None):
        r = partidas[escolha.current()]
        tela.carregar_sequencia(r["sequencia"].split(), decisoes.get(r["id_partida"]))

    escolha.bind("<<ComboboxSelected>>", abrir)
    if partidas:
        escolha.current(0)
        abrir()


# ---- modo ao vivo ----
def modo_ao_vivo(janela, args):
    if args.tempo_ms:
        desc = "MCTS com %d ms por jogada" % args.tempo_ms
    else:
        desc = "MCTS com %d simulações por jogada" % args.simulacoes
    if args.adversario == "minimax":
        desc_adv = "minimax (%d jogadas à frente)" % args.profundidade
    else:
        desc_adv = args.adversario
    jogador_mcts = PRETAS if args.mcts_de == "pretas" else BRANCAS

    tela = Tela(janela, "%s (%s)  x  %s" % (desc, args.mcts_de, desc_adv))
    tela.pausa_ms = args.pausa_ms
    jogo = {}

    def nova_partida():
        semente = random.randrange(10 ** 9)
        if args.tempo_ms:
            jogo["mcts"] = agentes.AgenteMCTS(semente, tempo_ms=args.tempo_ms)
        else:
            jogo["mcts"] = agentes.AgenteMCTS(semente, simulacoes=args.simulacoes)
        if args.adversario == "minimax":
            jogo["adv"] = agentes.AgenteMinimax(semente + 1, args.profundidade)
        elif args.adversario == "guloso":
            jogo["adv"] = agentes.AgenteGuloso(semente + 1)
        else:
            jogo["adv"] = agentes.AgenteAleatorio(semente + 1)
        tela.parar()
        tela.limpar()
        tela.ir(0)

    def proxima():
        estado = tela.estados[-1]
        agente = jogo["mcts"] if estado.jogador == jogador_mcts else jogo["adv"]
        t0 = time.perf_counter()
        acao, inf = agente.decidir(estado)
        ms = (time.perf_counter() - t0) * 1000
        if agente.nome == "mcts" and not inf["forcada"]:
            texto = "MCTS: %d simulações (%.0f ms)" % (inf["iteracoes"], ms)
        elif inf["forcada"]:
            texto = "%s: só tinha essa jogada" % agente.nome
        else:
            texto = "%s (%.0f ms)" % (agente.nome, ms)
        tela.estados.append(othello.aplicar_acao(estado, acao))
        tela.jogadas.append(othello.nome_casa(acao))
        tela.infos.append(texto)

    tela.proxima_jogada = proxima
    botao(tela.extra, "Nova partida", nova_partida).pack(side="left")
    nova_partida()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pasta", nargs="?", help="pasta com partidas.csv (modo rever)")
    parser.add_argument("--ao-vivo", action="store_true")
    parser.add_argument("--simulacoes", type=int, default=400)
    parser.add_argument("--tempo-ms", type=int, default=None)
    parser.add_argument("--adversario", choices=["aleatorio", "guloso", "minimax"], default="minimax")
    parser.add_argument("--profundidade", type=int, default=2)
    parser.add_argument("--mcts-de", choices=["pretas", "brancas"], default="pretas")
    parser.add_argument("--pausa-ms", type=int, default=500, help="pausa entre jogadas no jogar ate o fim")
    args = parser.parse_args()

    janela = tk.Tk()
    janela.title("Othello - MCTS")
    janela.resizable(False, False)
    if args.ao_vivo:
        modo_ao_vivo(janela, args)
    elif args.pasta:
        modo_rever(janela, args.pasta)
    else:
        parser.error("informe a pasta dos registros ou use --ao-vivo")
    janela.mainloop()
