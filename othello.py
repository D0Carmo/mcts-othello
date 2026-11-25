VAZIA = 0
PRETAS = 1
BRANCAS = -1
BORDA = 2
PASS = "PASS"

DIRECOES = (-11, -10, -9, -1, 1, 9, 10, 11)


def indice(linha, coluna):
    return (linha + 1) * 10 + (coluna + 1)


def linha_coluna(ind):
    return ind // 10 - 1, ind % 10 - 1


CASAS = [indice(l, c) for l in range(8) for c in range(8)]

LETRAS = "abcdefgh"


def nome_casa(ind):
    if ind == PASS:
        return PASS
    linha, coluna = linha_coluna(ind)
    return LETRAS[coluna] + str(linha + 1)


def casa_pelo_nome(nome):
    if nome == PASS:
        return PASS
    return indice(int(nome[1]) - 1, LETRAS.index(nome[0]))


class Estado:
    def __init__(self, tabuleiro, jogador):
        self.tabuleiro = tabuleiro
        self.jogador = jogador


def tabuleiro_vazio():
    tab = [BORDA] * 100
    for casa in CASAS:
        tab[casa] = VAZIA
    return tab


def estado_inicial():
    tab = tabuleiro_vazio()
    tab[casa_pelo_nome("d4")] = BRANCAS
    tab[casa_pelo_nome("e5")] = BRANCAS
    tab[casa_pelo_nome("d5")] = PRETAS
    tab[casa_pelo_nome("e4")] = PRETAS
    return Estado(tab, PRETAS)


def capturas_na_direcao(tab, casa, direcao, jogador):
    viradas = []
    atual = casa + direcao
    while tab[atual] == -jogador:
        viradas.append(atual)
        atual += direcao
    if viradas and tab[atual] == jogador:
        return viradas
    return []


def eh_colocacao_legal(tab, casa, jogador):
    if tab[casa] != VAZIA:
        return False
    for direcao in DIRECOES:
        if capturas_na_direcao(tab, casa, direcao, jogador):
            return True
    return False


def colocacoes_legais(tab, jogador):
    legais = []
    for casa in CASAS:
        if tab[casa] == VAZIA and eh_colocacao_legal(tab, casa, jogador):
            legais.append(casa)
    return legais


def tem_colocacao_legal(tab, jogador):
    for casa in CASAS:
        if tab[casa] == VAZIA and eh_colocacao_legal(tab, casa, jogador):
            return True
    return False


def acoes_legais(estado):
    legais = colocacoes_legais(estado.tabuleiro, estado.jogador)
    if legais:
        return legais
    if tem_colocacao_legal(estado.tabuleiro, -estado.jogador):
        return [PASS]
    return []


def eh_terminal(estado):
    tab = estado.tabuleiro
    return not tem_colocacao_legal(tab, estado.jogador) and not tem_colocacao_legal(tab, -estado.jogador)


def aplicar_acao(estado, acao):
    jogador = estado.jogador
    if acao == PASS:
        return Estado(estado.tabuleiro[:], -jogador)
    tab = estado.tabuleiro[:]
    if tab[acao] != VAZIA:
        raise ValueError("casa ocupada " + nome_casa(acao))
    total = 0
    for direcao in DIRECOES:
        viradas = capturas_na_direcao(tab, acao, direcao, jogador)
        for casa in viradas:
            tab[casa] = jogador
        total += len(viradas)
    if total == 0:
        raise ValueError("jogada ilegal " + nome_casa(acao))
    tab[acao] = jogador
    return Estado(tab, -jogador)


def contagem(estado):
    pretas = 0
    brancas = 0
    for casa in CASAS:
        if estado.tabuleiro[casa] == PRETAS:
            pretas += 1
        elif estado.tabuleiro[casa] == BRANCAS:
            brancas += 1
    return pretas, brancas


def vencedor(estado):
    pretas, brancas = contagem(estado)
    if pretas > brancas:
        return PRETAS
    if brancas > pretas:
        return BRANCAS
    return 0


def recompensa(estado_final, jogador):
    quem = vencedor(estado_final)
    if quem == 0:
        return 0.5
    if quem == jogador:
        return 1.0
    return 0.0


def jogada_aleatoria(estado, rng):
    acoes = acoes_legais(estado)
    if not acoes:
        return None
    return rng.choice(acoes)


def jogada_aleatoria_rapida(estado, rng):
    tab = estado.tabuleiro
    vazias = [casa for casa in CASAS if tab[casa] == VAZIA]
    if not vazias:
        return None
    for _ in range(8):
        casa = rng.choice(vazias)
        if eh_colocacao_legal(tab, casa, estado.jogador):
            return casa
    return jogada_aleatoria(estado, rng)


# ---- usado so nos testes ----
def para_texto(estado):
    simbolos = {VAZIA: ".", PRETAS: "X", BRANCAS: "O"}
    linhas = ["  a b c d e f g h"]
    for l in range(8):
        linhas.append(str(l + 1) + " " + " ".join(simbolos[estado.tabuleiro[indice(l, c)]] for c in range(8)))
    return "\n".join(linhas)


def de_texto(linhas, jogador):
    tab = tabuleiro_vazio()
    for l in range(8):
        for c in range(8):
            if linhas[l][c] == "X":
                tab[indice(l, c)] = PRETAS
            elif linhas[l][c] == "O":
                tab[indice(l, c)] = BRANCAS
    return Estado(tab, jogador)
