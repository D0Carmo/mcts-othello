import argparse
import csv
import json
import math
import os
import random
import statistics
import sys

import othello

DELTA = 0.05
REAMOSTRAGENS = 10000
SEMENTE_BOOTSTRAP = 20260930
Z_0975 = 1.959964
Z_090 = 1.281552
COMPARACAO_PRINCIPAL = (640, 1280)
MINIMO_BLOCOS = 10


def ler(caminho):
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---- validacao ----
def validar_partida(r):
    estado = othello.estado_inicial()
    for i, nome in enumerate(r["sequencia"].split()):
        acao = othello.casa_pelo_nome(nome)
        if acao not in othello.acoes_legais(estado):
            return "acao ilegal na jogada %d (%s)" % (i, nome)
        estado = othello.aplicar_acao(estado, acao)
    if not othello.eh_terminal(estado):
        return "sequencia nao termina o jogo"
    pretas, brancas = othello.contagem(estado)
    if (pretas, brancas) != (int(r["pretas"]), int(r["brancas"])):
        return "contagem final nao bate"
    jogador = othello.PRETAS if r["cor_avaliado"] == "pretas" else othello.BRANCAS
    if abs(othello.recompensa(estado, jogador) - float(r["pontos"])) > 1e-9:
        return "pontos nao batem"
    return None


# ---- taxa e bootstrap ----
def taxa_de_pontuacao(vitorias, empates, partidas):
    return (vitorias + 0.5 * empates) / partidas if partidas else None


def pontuacao_por_bloco(registros):
    pontos = {}
    for r in registros:
        pontos.setdefault(int(r["bloco"]), []).append(float(r["pontos"]))
    return {b: sum(v) / 2 for b, v in pontos.items() if len(v) == 2}


def percentil(ordenados, fracao):
    pos = fracao * (len(ordenados) - 1)
    i = int(pos)
    j = min(i + 1, len(ordenados) - 1)
    return ordenados[i] + (ordenados[j] - ordenados[i]) * (pos - i)


def intervalo_bootstrap(valores, reamostragens, rotulo):
    if not valores:
        return None, None
    rng = random.Random(SEMENTE_BOOTSTRAP + sum(ord(c) for c in rotulo))
    n = len(valores)
    medias = sorted(sum(rng.choices(valores, k=n)) / n for _ in range(reamostragens))
    return percentil(medias, 0.025), percentil(medias, 0.975)


def diferencas_pareadas(y_b, y_2b):
    return [y_2b[b] - y_b[b] for b in sorted(y_b) if b in y_2b]


def classificar(inf, sup, blocos, degenerado):
    if inf is None:
        return "sem dados"
    if blocos < MINIMO_BLOCOS:
        return "amostra insuficiente"
    if degenerado:
        return "intervalo degenerado"
    if inf > DELTA:
        return "ganho relevante"
    if sup < -DELTA:
        return "perda relevante"
    if inf >= -DELTA and sup <= DELTA:
        return "equivalente"
    return "inconclusivo"


def tamanho_de_amostra(sigma_plan):
    return max(200, math.ceil(((Z_0975 + Z_090) * sigma_plan / DELTA) ** 2))


# ---- custo ----
def custo(decisoes):
    com_busca = [d for d in decisoes if d["forcada"] != "True"]
    res = {"forcadas": len(decisoes) - len(com_busca),
           "contingencias": sum(d["contingencia"] == "True" for d in decisoes)}
    if not com_busca:
        return res
    tempos = sorted(float(d["tempo_efetivo_s"]) for d in com_busca)
    res["tempo_medio_s"] = sum(tempos) / len(tempos)
    res["tempo_mediana_s"] = percentil(tempos, 0.5)
    res["tempo_p95_s"] = percentil(tempos, 0.95)
    res["iteracoes_media"] = sum(int(d["iteracoes"]) for d in com_busca) / len(com_busca)
    excessos = [float(d["excesso_prazo_s"]) for d in com_busca]
    res["excesso_max_s"] = max(excessos)
    res["violacoes_prazo"] = sum(
        1 for d in com_busca
        if d["id_partida"].split("-")[1] == "tempo" and float(d["excesso_prazo_s"]) > 0.1 * float(d["orcamento_solicitado"]) / 1000)
    return res


# ---- tabelas ----
def chave(r):
    return (r["experimento"], r["adversario"], int(r["orcamento"]), r["orcamento_adversario"])


def tabela_taxas(grupos, decisoes_avaliado, reamostragens):
    linhas = []
    for k in sorted(grupos):
        regs = grupos[k]
        v = sum(r["resultado"] == "vitoria" for r in regs)
        e = sum(r["resultado"] == "empate" for r in regs)
        y = pontuacao_por_bloco(regs)
        valores = [y[b] for b in sorted(y)]
        inf, sup = intervalo_bootstrap(valores, reamostragens, "taxa%s" % (k,))
        decs = [d for r in regs for d in decisoes_avaliado.get(r["id_partida"], [])]
        linha = {"experimento": k[0], "adversario": k[1], "orcamento": k[2], "orcamento_adversario": k[3],
                 "partidas": len(regs), "blocos": len(valores), "vitorias": v, "empates": e,
                 "derrotas": len(regs) - v - e, "taxa": taxa_de_pontuacao(v, e, len(regs)),
                 "ic_inferior": inf, "ic_superior": sup}
        linha.update(custo(decs))
        linhas.append(linha)
    return linhas


def tabela_ganhos(grupos, taxas, reamostragens):
    tempo = {(t["experimento"], t["adversario"], t["orcamento"], t["orcamento_adversario"]): t.get("tempo_medio_s")
             for t in taxas}
    ganhos = []
    for k in sorted(grupos):
        exp, adv, orc, orc_adv = k
        k2 = (exp, adv, 2 * orc, orc_adv)
        if adv == "mcts" or k2 not in grupos:
            continue
        d = diferencas_pareadas(pontuacao_por_bloco(grupos[k]), pontuacao_por_bloco(grupos[k2]))
        inf, sup = intervalo_bootstrap(d, reamostragens, "ganho%s" % (k,))
        delta = sum(d) / len(d) if d else None
        eta = None
        t_b, t_2b = tempo.get(k), tempo.get(k2)
        if delta is not None and t_b and t_2b and t_2b - t_b > 0.1 * t_b:
            eta = delta / (t_2b - t_b)
        ganhos.append({"experimento": exp, "adversario": adv, "orcamento_B": orc, "orcamento_2B": 2 * orc,
                       "blocos": len(d), "delta": delta, "ic_inferior": inf, "ic_superior": sup,
                       "classificacao": classificar(inf, sup, len(d), len(set(d)) <= 1),
                       "tempo_B_s": t_b, "tempo_2B_s": t_2b, "eta_por_s": eta})
    return ganhos


def planejamento(grupos, reamostragens):
    kb = ("tempo", "minimax", COMPARACAO_PRINCIPAL[0], "")
    k2 = ("tempo", "minimax", COMPARACAO_PRINCIPAL[1], "")
    if kb not in grupos or k2 not in grupos:
        return {"disponivel": False, "motivo": "faltam partidas de 640/1280 ms vs minimax (experimento tempo)"}
    d = diferencas_pareadas(pontuacao_por_bloco(grupos[kb]), pontuacao_por_bloco(grupos[k2]))
    if len(d) < 3:
        return {"disponivel": False, "motivo": "menos de 3 blocos pareados"}
    rng = random.Random(SEMENTE_BOOTSTRAP)
    desvios = []
    for _ in range(reamostragens):
        amostra = rng.choices(d, k=len(d))
        desvios.append(statistics.stdev(amostra) if len(set(amostra)) > 1 else 0.0)
    limite = percentil(sorted(desvios), 0.90)
    sigma = max(0.5, limite)
    return {"disponivel": True, "blocos_pareados": len(d), "media_D": sum(d) / len(d),
            "desvio_D": statistics.stdev(d), "limite_90_desvio": limite, "sigma_plan": sigma,
            "m_estrela_pares": tamanho_de_amostra(sigma), "partidas_por_ponto": 2 * tamanho_de_amostra(sigma)}


# ---- graficos ----
CORES = {"aleatorio": "#2a78d6", "guloso": "#eb6834", "minimax": "#1baf7a", "mcts": "#eda100"}


def graficos(taxas, ganhos, pasta):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("sem matplotlib: graficos pulados")
        return
    for exp in ("simulacoes", "tempo"):
        if not any(t["experimento"] == exp for t in taxas):
            continue
        unidade = "simulacoes por decisao" if exp == "simulacoes" else "ms por decisao"
        fig, ax = plt.subplots(figsize=(7, 4.2))
        for adv in ("aleatorio", "guloso", "minimax", "mcts"):
            ls = sorted((t for t in taxas if t["experimento"] == exp and t["adversario"] == adv),
                        key=lambda t: t["orcamento"])
            if not ls:
                continue
            x = [t["orcamento"] for t in ls]
            y = [t["taxa"] for t in ls]
            err = [[t["taxa"] - (t["ic_inferior"] or t["taxa"]) for t in ls],
                   [(t["ic_superior"] or t["taxa"]) - t["taxa"] for t in ls]]
            rotulo = "vs " + adv if adv != "mcts" else "vs mcts com o dobro"
            ax.errorbar(x, y, yerr=err, marker="o", capsize=3, color=CORES[adv], label=rotulo)
        ax.set_xscale("log", base=2)
        xs = sorted({t["orcamento"] for t in taxas if t["experimento"] == exp})
        ax.set_xticks(xs)
        ax.set_xticklabels([str(v) for v in xs])
        ax.minorticks_off()
        ax.set_ylim(-0.02, 1.02)
        ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8)
        ax.set_xlabel(unidade + " (escala log2)")
        ax.set_ylabel("taxa de pontuacao")
        ax.set_title("taxa de pontuacao do MCTS por orcamento (%s)" % exp)
        ax.grid(True, color="#e3e3e3")
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(pasta, "pontuacao_%s.png" % exp), dpi=160)
        plt.close(fig)
        gs = [g for g in ganhos if g["experimento"] == exp]
        if not gs:
            continue
        fig, ax = plt.subplots(figsize=(7, 4.2))
        ax.axhspan(-DELTA, DELTA, color="#f0f0f0", label="faixa +-%.2f" % DELTA)
        ax.axhline(0, color="gray", linewidth=0.8)
        for desloc, adv in ((0.93, "aleatorio"), (1.0, "guloso"), (1.07, "minimax")):
            ls = sorted((g for g in gs if g["adversario"] == adv), key=lambda g: g["orcamento_B"])
            if not ls:
                continue
            x = [g["orcamento_B"] * desloc for g in ls]
            y = [g["delta"] for g in ls]
            err = [[g["delta"] - (g["ic_inferior"] or g["delta"]) for g in ls],
                   [(g["ic_superior"] or g["delta"]) - g["delta"] for g in ls]]
            ax.errorbar(x, y, yerr=err, marker="o", linestyle="none", capsize=3, color=CORES[adv], label="vs " + adv)
        ax.set_xscale("log", base=2)
        xs = sorted({g["orcamento_B"] for g in gs})
        ax.set_xticks(xs)
        ax.set_xticklabels([str(v) for v in xs])
        ax.minorticks_off()
        ax.set_xlabel("orcamento B (duplicacao B -> 2B)")
        ax.set_ylabel("delta = S(2B) - S(B)")
        ax.set_title("ganho por duplicacao (%s)" % exp)
        ax.grid(True, color="#e3e3e3")
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(pasta, "ganhos_%s.png" % exp), dpi=160)
        plt.close(fig)


# ---- saida ----
def f(v, casas=3):
    if v is None:
        return "-"
    return ("%." + str(casas) + "f") % v if isinstance(v, float) else str(v)


def escrever_csv(caminho, linhas):
    if not linhas:
        return
    colunas = []
    for l in linhas:
        for c in l:
            if c not in colunas:
                colunas.append(c)
    with open(caminho, "w", encoding="utf-8", newline="") as arq:
        w = csv.DictWriter(arq, fieldnames=colunas)
        w.writeheader()
        w.writerows(linhas)


def analisar(pasta, reamostragens):
    saida = os.path.join(pasta, "analise")
    os.makedirs(saida, exist_ok=True)
    partidas = ler(os.path.join(pasta, "partidas.csv"))
    decisoes = ler(os.path.join(pasta, "decisoes.csv"))

    validas, invalidas = [], []
    for r in partidas:
        motivo = validar_partida(r)
        (validas if motivo is None else invalidas).append(r if motivo is None else (r["id_partida"], motivo))
    grupos = {}
    for r in validas:
        grupos.setdefault(chave(r), []).append(r)
    dec_av = {}
    for d in decisoes:
        if d["agente"] == "mcts" and d["eh_avaliado"] == "True":
            dec_av.setdefault(d["id_partida"], []).append(d)

    taxas = tabela_taxas(grupos, dec_av, reamostragens)
    ganhos = tabela_ganhos(grupos, taxas, reamostragens)
    plano = planejamento(grupos, reamostragens)
    principal = [g for g in ganhos if g["experimento"] == "tempo" and g["adversario"] == "minimax"
                 and g["orcamento_B"] == COMPARACAO_PRINCIPAL[0]]

    linhas = ["VALIDACAO: %d validas, %d invalidas" % (len(validas), len(invalidas))]
    linhas += ["  %s: %s" % par for par in invalidas]
    linhas.append("\nTAXA DE PONTUACAO (IC 95%% bootstrap por blocos, %d reamostragens)" % reamostragens)
    for t in taxas:
        linhas.append("%-10s %-9s orc=%5s %-5s P=%3d V=%3d E=%3d D=%3d taxa=%s [%s, %s] t_medio=%ss p95=%ss iter=%s forcadas=%s viol=%s" % (
            t["experimento"], t["adversario"], t["orcamento"], t["orcamento_adversario"], t["partidas"],
            t["vitorias"], t["empates"], t["derrotas"], f(t["taxa"]), f(t["ic_inferior"]), f(t["ic_superior"]),
            f(t.get("tempo_medio_s"), 4), f(t.get("tempo_p95_s"), 4), f(t.get("iteracoes_media"), 0),
            t.get("forcadas"), t.get("violacoes_prazo")))
    linhas.append("\nGANHO POR DUPLICACAO (delta = %.2f)" % DELTA)
    for g in ganhos:
        linhas.append("%-10s %-9s %5s -> %5s  delta=%s [%s, %s] eta=%s/s blocos=%d => %s" % (
            g["experimento"], g["adversario"], g["orcamento_B"], g["orcamento_2B"], f(g["delta"]),
            f(g["ic_inferior"]), f(g["ic_superior"]), f(g["eta_por_s"]), g["blocos"], g["classificacao"]))
    if principal:
        g = principal[0]
        linhas.append("\nCOMPARACAO PRINCIPAL 640 -> 1280 ms vs minimax: delta=%s [%s, %s] => %s" % (
            f(g["delta"]), f(g["ic_inferior"]), f(g["ic_superior"]), g["classificacao"]))
    else:
        linhas.append("\nCOMPARACAO PRINCIPAL: sem dados")
    if plano["disponivel"]:
        linhas.append("PLANEJAMENTO (tamanho de amostra): blocos=%d media_D=%s desvio_D=%s limite90=%s sigma_plan=%s => m*=%d pares (%d partidas por ponto)" % (
            plano["blocos_pareados"], f(plano["media_D"]), f(plano["desvio_D"]), f(plano["limite_90_desvio"]),
            f(plano["sigma_plan"]), plano["m_estrela_pares"], plano["partidas_por_ponto"]))
    else:
        linhas.append("PLANEJAMENTO (tamanho de amostra): " + plano["motivo"])

    resumo = "\n".join(linhas)
    with open(os.path.join(saida, "resumo.txt"), "w", encoding="utf-8") as arq:
        arq.write(resumo + "\n")
    escrever_csv(os.path.join(saida, "taxas.csv"), taxas)
    escrever_csv(os.path.join(saida, "ganhos.csv"), ganhos)
    with open(os.path.join(saida, "planejamento.json"), "w", encoding="utf-8") as arq:
        json.dump(plano, arq, indent=2)
    graficos(taxas, ganhos, saida)
    return resumo


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pasta")
    parser.add_argument("--reamostragens", type=int, default=REAMOSTRAGENS)
    args = parser.parse_args()
    print(analisar(args.pasta, args.reamostragens))
