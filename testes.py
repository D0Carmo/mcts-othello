import random
import unittest
import agentes
import analise
import othello
from othello import PASS, PRETAS, BRANCAS


def jogar_ate(estado, rng, vazias_alvo):
    while True:
        p, b = othello.contagem(estado)
        acao = othello.jogada_aleatoria(estado, rng)
        if 64 - p - b <= vazias_alvo or acao is None:
            return estado
        estado = othello.aplicar_acao(estado, acao)


def partida(ag_pretas, ag_brancas):
    estado = othello.estado_inicial()
    seq = []
    while True:
        acoes = othello.acoes_legais(estado)
        if not acoes:
            return estado, seq
        ag = ag_pretas if estado.jogador == PRETAS else ag_brancas
        acao, _ = ag.decidir(estado)
        assert acao in acoes
        seq.append(othello.nome_casa(acao))
        estado = othello.aplicar_acao(estado, acao)


class TesteMotor(unittest.TestCase):

    def teste_acoes_iniciais(self):
        nomes = sorted(othello.nome_casa(a) for a in othello.acoes_legais(othello.estado_inicial()))
        self.assertEqual(nomes, ["c4", "d3", "e6", "f5"])

    def teste_captura_nas_oito_direcoes(self):
        estado = othello.de_texto(["........", "........", "..X.X.X.", "...OOO..",
                                   "..XO.OX.", "...OOO..", "..X.X.X.", "........"], PRETAS)
        novo = othello.aplicar_acao(estado, othello.casa_pelo_nome("e5"))
        self.assertEqual(othello.contagem(novo), (17, 0))
        self.assertEqual(othello.contagem(estado), (8, 8))

    def teste_jogada_ilegal(self):
        estado = othello.estado_inicial()
        with self.assertRaises(ValueError):
            othello.aplicar_acao(estado, othello.casa_pelo_nome("d4"))
        with self.assertRaises(ValueError):
            othello.aplicar_acao(estado, othello.casa_pelo_nome("a1"))

    def teste_passe(self):
        estado = othello.de_texto(["XOX.....", "........", "........", "........",
                                   "........", "........", "........", "........"], PRETAS)
        self.assertEqual(othello.acoes_legais(estado), [PASS])
        depois = othello.aplicar_acao(estado, PASS)
        self.assertEqual([othello.nome_casa(a) for a in othello.acoes_legais(depois)], ["d1"])

    def teste_fim_com_casas_vazias_e_empate(self):
        so_pretas = othello.de_texto(["XX......"] + ["........"] * 7, PRETAS)
        self.assertTrue(othello.eh_terminal(so_pretas))
        self.assertEqual(othello.recompensa(so_pretas, PRETAS), 1.0)
        empate = othello.de_texto(["XX......"] + ["........"] * 6 + ["......OO"], BRANCAS)
        self.assertTrue(othello.eh_terminal(empate))
        self.assertEqual(othello.recompensa(empate, PRETAS), 0.5)

    def teste_jogada_rapida_e_legal_e_uniforme(self):
        rng = random.Random(1)
        for _ in range(20):
            estado = othello.estado_inicial()
            while True:
                legais = othello.acoes_legais(estado)
                acao = othello.jogada_aleatoria_rapida(estado, rng)
                if not legais:
                    self.assertIsNone(acao)
                    break
                self.assertIn(acao, legais)
                estado = othello.aplicar_acao(estado, acao)
        cont = {}
        for _ in range(4000):
            a = othello.jogada_aleatoria_rapida(othello.estado_inicial(), rng)
            cont[a] = cont.get(a, 0) + 1
        for a in cont:
            self.assertTrue(850 < cont[a] < 1150)


class TesteAgentes(unittest.TestCase):

    def teste_guloso_pega_mais_pecas(self):
        estado = othello.de_texto(["XOOO....", "........", "........", "...O....",
                                   "...X....", "........", "........", "........"], PRETAS)
        acao, _ = agentes.AgenteGuloso(1).decidir(estado)
        self.assertEqual(othello.nome_casa(acao), "e1")

    def teste_avaliacao_antissimetrica(self):
        rng = random.Random(2)
        estado = jogar_ate(othello.estado_inicial(), rng, 40)
        self.assertAlmostEqual(agentes.avaliar(estado, PRETAS), -agentes.avaliar(estado, BRANCAS))
        self.assertEqual(agentes.SOMA_ABS_PESOS, 944)

    def teste_poda_nao_muda_o_valor(self):
        for semente in range(3):
            estado = jogar_ate(othello.estado_inicial(), random.Random(semente), 24)
            com = agentes.minimax(estado, 3, -float("inf"), float("inf"), estado.jogador)
            sem = agentes.minimax_sem_poda(estado, 3, estado.jogador)
            self.assertAlmostEqual(com, sem)

    def teste_minimax_e_mcts_resolvem_finais_curtos(self):
        testados = 0
        for semente in range(30):
            estado = jogar_ate(othello.estado_inicial(), random.Random(semente), 3)
            acoes = othello.acoes_legais(estado)
            if len(acoes) < 2:
                continue
            valores = {a: agentes.minimax_sem_poda(othello.aplicar_acao(estado, a), 60, estado.jogador) for a in acoes}
            if len(set(valores.values())) == 1:
                continue
            melhor = max(valores.values())
            acao_mm, _ = agentes.AgenteMinimax(1).decidir(estado)
            acao_mcts, _ = agentes.AgenteMCTS(semente, simulacoes=400).decidir(estado)
            self.assertEqual(valores[acao_mm], melhor)
            self.assertEqual(valores[acao_mcts], melhor, othello.para_texto(estado))
            testados += 1
        self.assertGreater(testados, 5)

    def teste_mcts_visitas_e_prioridade(self):
        ag = agentes.AgenteMCTS(3, simulacoes=200)
        acao, inf = ag.decidir(othello.estado_inicial())
        self.assertEqual(inf["iteracoes"], 200)
        self.assertEqual(ag.raiz.visitas, 200)
        self.assertEqual(sum(f.visitas for f in ag.raiz.filhos), 200)
        ag = agentes.AgenteMCTS(3, simulacoes=4)
        ag.decidir(othello.estado_inicial())
        self.assertEqual([f.visitas for f in ag.raiz.filhos], [1, 1, 1, 1])

    def teste_mcts_perspectiva_da_recompensa(self):
        estado = othello.de_texto(["XO......"] + ["........"] * 6 + ["XO......"], PRETAS)
        ag = agentes.AgenteMCTS(5, simulacoes=20)
        ag.decidir(estado)
        self.assertEqual(ag.raiz.recompensas, ag.raiz.visitas)
        for filho in ag.raiz.filhos:
            self.assertEqual(filho.recompensas, filho.visitas)

    def teste_reprodutibilidade_e_acao_forcada(self):
        seqs = [partida(agentes.AgenteMCTS(11, simulacoes=40), agentes.AgenteGuloso(12))[1] for _ in range(2)]
        self.assertEqual(seqs[0], seqs[1])
        estado = othello.de_texto(["XOX....."] + ["........"] * 7, PRETAS)
        acao, inf = agentes.AgenteMCTS(1, simulacoes=50).decidir(estado)
        self.assertEqual((acao, inf["forcada"], inf["iteracoes"]), (PASS, True, 0))

    def teste_mcts_por_tempo(self):
        import time
        ag = agentes.AgenteMCTS(1, tempo_ms=60)
        t0 = time.perf_counter()
        acao, inf = ag.decidir(othello.estado_inicial())
        self.assertLess(time.perf_counter() - t0, 0.11)
        self.assertGreater(inf["iteracoes"], 5)
        acao, inf = agentes.AgenteMCTS(1, tempo_ms=0.0001).decidir(othello.estado_inicial())
        self.assertTrue(inf["contingencia"])


class TesteAnalise(unittest.TestCase):

    def teste_uma_vitoria_um_empate_uma_derrota(self):
        self.assertEqual(analise.taxa_de_pontuacao(1, 1, 3), 0.5)

    def teste_eq3(self):
        self.assertEqual(analise.tamanho_de_amostra(0.5), 1051)
        self.assertEqual(analise.tamanho_de_amostra(0.1), 200)

    def teste_classificacao(self):
        self.assertEqual(analise.classificar(0.06, 0.2, 50, False), "ganho relevante")
        self.assertEqual(analise.classificar(-0.2, -0.06, 50, False), "perda relevante")
        self.assertEqual(analise.classificar(-0.04, 0.04, 50, False), "equivalente")
        self.assertEqual(analise.classificar(-0.01, 0.08, 50, False), "inconclusivo")
        self.assertEqual(analise.classificar(0.0, 0.0, 3, False), "amostra insuficiente")

    def teste_validacao_pega_sequencia_adulterada(self):
        final, seq = partida(agentes.AgenteAleatorio(1), agentes.AgenteAleatorio(2))
        p, b = othello.contagem(final)
        r = {"sequencia": " ".join(seq), "pretas": p, "brancas": b, "cor_avaliado": "pretas",
             "pontos": othello.recompensa(final, PRETAS)}
        self.assertIsNone(analise.validar_partida(r))
        r["sequencia"] = "a1 " + r["sequencia"]
        self.assertIn("ilegal", analise.validar_partida(r))

    def teste_bootstrap(self):
        rng = random.Random(0)
        v = [rng.choice([0.0, 0.5, 1.0]) for _ in range(100)]
        inf, sup = analise.intervalo_bootstrap(v, 1000, "x")
        self.assertTrue(inf <= sum(v) / len(v) <= sup)
        self.assertEqual(analise.intervalo_bootstrap(v, 1000, "x"), (inf, sup))


if __name__ == "__main__":
    unittest.main()
