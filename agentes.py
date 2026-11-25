import math
import random
import time

import othello
from othello import PASS, PRETAS, BRANCAS

C_UCT = math.sqrt(2)
PROFUNDIDADE_MINIMAX = 4
VALOR_TERMINAL = 1000

PESOS = [
    [100, -20, 10,  5,  5, 10, -20, 100],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [ 10,  -2,  3,  2,  2,  3,  -2,  10],
    [  5,  -2,  2,  1,  1,  2,  -2,   5],
    [  5,  -2,  2,  1,  1,  2,  -2,   5],
    [ 10,  -2,  3,  2,  2,  3,  -2,  10],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [100, -20, 10,  5,  5, 10, -20, 100],
]
PESO_DA_CASA = {}
for _l in range(8):
    for _c in range(8):
        PESO_DA_CASA[othello.indice(_l, _c)] = PESOS[_l][_c]
SOMA_ABS_PESOS = sum(abs(p) for p in PESO_DA_CASA.values())
CANTOS = [othello.casa_pelo_nome(n) for n in ("a1", "h1", "a8", "h8")]


def info(iteracoes=0, forcada=False, contingencia=False, excesso=0.0):
    return {"iteracoes": iteracoes, "forcada": forcada,
            "contingencia": contingencia, "excesso": excesso}


def acao_forcada(acoes):
    if len(acoes) == 1:
        return acoes[0]
    return None


# ---- aleatorio ----
class AgenteAleatorio:
    def __init__(self, semente):
        self.nome = "aleatorio"
        self.rng = random.Random(semente)

    def decidir(self, estado):
        acoes = othello.acoes_legais(estado)
        forcada = acao_forcada(acoes)
        if forcada is not None:
            return forcada, info(forcada=True)
        return self.rng.choice(acoes), info()


# ---- guloso ----
def pecas_de(estado, jogador):
    pretas, brancas = othello.contagem(estado)
    return pretas if jogador == PRETAS else brancas


class AgenteGuloso:
    def __init__(self, semente):
        self.nome = "guloso"
        self.rng = random.Random(semente)

    def decidir(self, estado):
        acoes = othello.acoes_legais(estado)
        forcada = acao_forcada(acoes)
        if forcada is not None:
            return forcada, info(forcada=True)
        melhores = []
        melhor = -1
        for acao in acoes:
            total = pecas_de(othello.aplicar_acao(estado, acao), estado.jogador)
            if total > melhor:
                melhor = total
                melhores = [acao]
            elif total == melhor:
                melhores.append(acao)
        return self.rng.choice(melhores), info()


# ---- minimax ----
def avaliar(estado, jogador):
    tab = estado.tabuleiro
    adv = -jogador

    cantos = 0
    for casa in CANTOS:
        if tab[casa] == jogador:
            cantos += 1
        elif tab[casa] == adv:
            cantos -= 1
    C = cantos / 4

    mob_p = len(othello.colocacoes_legais(tab, jogador))
    mob_a = len(othello.colocacoes_legais(tab, adv))
    M = (mob_p - mob_a) / (mob_p + mob_a if mob_p + mob_a else 1)

    posicional = 0
    pecas_p = 0
    pecas_a = 0
    for casa in othello.CASAS:
        if tab[casa] == jogador:
            posicional += PESO_DA_CASA[casa]
            pecas_p += 1
        elif tab[casa] == adv:
            posicional -= PESO_DA_CASA[casa]
            pecas_a += 1
    P = posicional / SOMA_ABS_PESOS
    D = (pecas_p - pecas_a) / (pecas_p + pecas_a if pecas_p + pecas_a else 1)

    return 40 * C + 30 * M + 20 * P + 10 * D


def valor_terminal(estado, jogador):
    quem = othello.vencedor(estado)
    if quem == 0:
        return 0
    return VALOR_TERMINAL if quem == jogador else -VALOR_TERMINAL


def ordenar_por_peso(acoes):
    return sorted(acoes, key=lambda casa: (-PESO_DA_CASA[casa], othello.linha_coluna(casa)))


def minimax(estado, profundidade, alfa, beta, jogador):
    acoes = othello.acoes_legais(estado)
    if not acoes:
        return valor_terminal(estado, jogador)
    if profundidade == 0:
        return avaliar(estado, jogador)
    if acoes == [PASS]:
        return minimax(othello.aplicar_acao(estado, PASS), profundidade, alfa, beta, jogador)

    if estado.jogador == jogador:
        melhor = -math.inf
        for acao in ordenar_por_peso(acoes):
            v = minimax(othello.aplicar_acao(estado, acao), profundidade - 1, alfa, beta, jogador)
            melhor = max(melhor, v)
            alfa = max(alfa, melhor)
            if alfa >= beta:
                break
        return melhor
    pior = math.inf
    for acao in ordenar_por_peso(acoes):
        v = minimax(othello.aplicar_acao(estado, acao), profundidade - 1, alfa, beta, jogador)
        pior = min(pior, v)
        beta = min(beta, pior)
        if alfa >= beta:
            break
    return pior


def minimax_sem_poda(estado, profundidade, jogador):
    acoes = othello.acoes_legais(estado)
    if not acoes:
        return valor_terminal(estado, jogador)
    if profundidade == 0:
        return avaliar(estado, jogador)
    if acoes == [PASS]:
        return minimax_sem_poda(othello.aplicar_acao(estado, PASS), profundidade, jogador)
    valores = [minimax_sem_poda(othello.aplicar_acao(estado, a), profundidade - 1, jogador) for a in acoes]
    return max(valores) if estado.jogador == jogador else min(valores)


class AgenteMinimax:
    def __init__(self, semente, profundidade=PROFUNDIDADE_MINIMAX):
        self.nome = "minimax"
        self.rng = random.Random(semente)
        self.profundidade = profundidade

    def decidir(self, estado):
        acoes = othello.acoes_legais(estado)
        forcada = acao_forcada(acoes)
        if forcada is not None:
            return forcada, info(forcada=True)
        melhores = []
        melhor = -math.inf
        for acao in ordenar_por_peso(acoes):
            v = minimax(othello.aplicar_acao(estado, acao), self.profundidade - 1,
                        -math.inf, math.inf, estado.jogador)
            if v > melhor:
                melhor = v
                melhores = [acao]
            elif v == melhor:
                melhores.append(acao)
        return self.rng.choice(melhores), info()


# ---- MCTS ----
class No:
    def __init__(self, estado, pai, acao_entrada, jogador_entrada):
        self.estado = estado
        self.pai = pai
        self.acao_entrada = acao_entrada
        self.jogador_entrada = jogador_entrada
        self.filhos = []
        self.nao_expandidas = othello.acoes_legais(estado)
        self.terminal = len(self.nao_expandidas) == 0
        self.visitas = 0
        self.recompensas = 0.0


def uct(filho, visitas_pai, c):
    if filho.visitas == 0:
        return math.inf
    return filho.recompensas / filho.visitas + c * math.sqrt(math.log(visitas_pai) / filho.visitas)


def selecionar(no, c, rng):
    melhores = []
    melhor = -math.inf
    for filho in no.filhos:
        v = uct(filho, max(no.visitas, 1), c)
        if v > melhor:
            melhor = v
            melhores = [filho]
        elif v == melhor:
            melhores.append(filho)
    return rng.choice(melhores)


def expandir(no, rng):
    acao = no.nao_expandidas.pop(rng.randrange(len(no.nao_expandidas)))
    filho = No(othello.aplicar_acao(no.estado, acao), no, acao, no.estado.jogador)
    no.filhos.append(filho)
    return filho


def simular(estado, rng, prazo):
    while True:
        if prazo is not None and time.perf_counter() >= prazo:
            return None
        acao = othello.jogada_aleatoria_rapida(estado, rng)
        if acao is None:
            return estado
        estado = othello.aplicar_acao(estado, acao)


def retropropagar(caminho, estado_final):
    for no in caminho:
        no.visitas += 1
        no.recompensas += othello.recompensa(estado_final, no.jogador_entrada)


def mais_visitado(raiz, rng):
    melhores = []
    maior = -1
    for filho in raiz.filhos:
        if filho.visitas > maior:
            maior = filho.visitas
            melhores = [filho]
        elif filho.visitas == maior:
            melhores.append(filho)
    return rng.choice(melhores).acao_entrada


class AgenteMCTS:

    def __init__(self, semente, simulacoes=None, tempo_ms=None, c=C_UCT):
        if (simulacoes is None) == (tempo_ms is None):
            raise ValueError("informe simulacoes ou tempo_ms")
        self.nome = "mcts"
        self.rng = random.Random(semente)
        self.simulacoes = simulacoes
        self.tempo_ms = tempo_ms
        self.c = c
        self.raiz = None

    def tem_orcamento(self, k, prazo):
        if self.simulacoes is not None:
            return k < self.simulacoes
        return time.perf_counter() < prazo

    def decidir(self, estado):
        inicio = time.perf_counter()
        prazo = None if self.tempo_ms is None else inicio + self.tempo_ms / 1000

        acoes = othello.acoes_legais(estado)
        forcada = acao_forcada(acoes)
        if forcada is not None:
            return forcada, info(forcada=True)

        contingencia = self.rng.choice(acoes)
        raiz = No(estado, None, None, estado.jogador)
        self.raiz = raiz
        k = 0

        while self.tem_orcamento(k, prazo):
            no = raiz
            caminho = [raiz]
            # selecao
            estourou = False
            while not no.terminal and not no.nao_expandidas:
                if prazo is not None and time.perf_counter() >= prazo:
                    estourou = True
                    break
                no = selecionar(no, self.c, self.rng)
                caminho.append(no)
            if estourou:
                break
            # expansao
            if not no.terminal:
                no = expandir(no, self.rng)
                caminho.append(no)
            # simulacao
            if no.terminal:
                final = no.estado
            else:
                final = simular(no.estado, self.rng, prazo)
                if final is None:
                    break
            # retropropagacao
            retropropagar(caminho, final)
            k += 1

        if k == 0:
            acao = contingencia
        else:
            acao = mais_visitado(raiz, self.rng)
        excesso = 0.0 if prazo is None else max(0.0, time.perf_counter() - prazo)
        return acao, info(iteracoes=k, contingencia=(k == 0), excesso=excesso)
