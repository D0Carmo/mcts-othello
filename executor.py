import argparse
import csv
import datetime
import gc
import hashlib
import json
import multiprocessing
import os
import platform
import random
import sys
import time

import agentes
import othello
from othello import PRETAS, BRANCAS

# ---- parametros do experimento ----
GRADE_SIMULACOES = [25, 50, 100, 200, 400, 800, 1600]
GRADE_TEMPO_MS = [20, 40, 80, 160, 320, 640, 1280]
COMPARACAO_PRINCIPAL_MS = (640, 1280)
SEMENTE_MESTRA = 20260930
PARES_PILOTO = 50
PARES_MINIMAX = 200
PARES_OUTROS = 100
BASELINES = ["aleatorio", "guloso", "minimax"]

COLUNAS_PARTIDA = ["id_partida", "fase", "experimento", "adversario", "orcamento",
                   "orcamento_adversario", "bloco", "cor_avaliado", "semente_avaliado",
                   "semente_adversario", "profundidade_minimax", "resultado", "pontos",
                   "pretas", "brancas", "numero_jogadas", "sequencia", "tempo_partida_s", "data_hora"]
COLUNAS_DECISAO = ["id_partida", "numero_jogada", "jogador", "agente", "eh_avaliado", "acao",
                   "numero_acoes_legais", "orcamento_solicitado", "tempo_efetivo_s", "iteracoes",
                   "forcada", "contingencia", "excesso_prazo_s"]


def semente_derivada(*partes):
    texto = "|".join(str(p) for p in partes)
    return int(hashlib.sha256(texto.encode()).hexdigest()[:16], 16)


def criar_agente(nome, semente, experimento, orcamento, profundidade):
    if nome == "mcts":
        if experimento == "simulacoes":
            return agentes.AgenteMCTS(semente, simulacoes=orcamento)
        return agentes.AgenteMCTS(semente, tempo_ms=orcamento)
    if nome == "aleatorio":
        return agentes.AgenteAleatorio(semente)
    if nome == "guloso":
        return agentes.AgenteGuloso(semente)
    if nome == "minimax":
        return agentes.AgenteMinimax(semente, profundidade)
    raise ValueError(nome)


def montar_partidas(fase, experimento, grade, adversarios, com_adjacentes, pares_fixo,
                    pares_principal, profundidade):
    confrontos = []
    for orcamento in grade:
        for adv in adversarios:
            if pares_fixo:
                pares = pares_fixo
            elif fase == "piloto":
                pares = PARES_PILOTO
            else:
                pares = PARES_MINIMAX if adv == "minimax" else PARES_OUTROS
            confrontos.append((adv, orcamento, "", adv, 1, pares))
    if com_adjacentes:
        for i in range(len(grade) - 1):
            pares = pares_fixo or (PARES_PILOTO if fase == "piloto" else PARES_OUTROS)
            confrontos.append(("mcts", grade[i], grade[i + 1], "mcts_adjacente", 1, pares))
    if fase == "final" and experimento == "tempo" and pares_principal and pares_principal > PARES_MINIMAX:
        for orcamento in COMPARACAO_PRINCIPAL_MS:
            if orcamento in grade and "minimax" in adversarios:
                confrontos.append(("minimax", orcamento, "", "minimax", PARES_MINIMAX + 1, pares_principal))

    partidas = []
    for adv, orcamento, orc_adv, chave, ini, fim in confrontos:
        for bloco in range(ini, fim + 1):
            for cor in ("pretas", "brancas"):
                partidas.append({
                    "id_partida": "-".join([fase, experimento, adv, str(orcamento), str(orc_adv), "b" + str(bloco), cor]),
                    "fase": fase, "experimento": experimento, "adversario": adv,
                    "orcamento": orcamento, "orcamento_adversario": orc_adv,
                    "chave_semente": chave, "bloco": bloco, "cor_avaliado": cor,
                    "profundidade_minimax": profundidade,
                })
    return partidas


def jogar_partida(p):
    sem_av = semente_derivada(SEMENTE_MESTRA, p["fase"], p["chave_semente"], p["bloco"], p["cor_avaliado"], "avaliado")
    sem_adv = semente_derivada(SEMENTE_MESTRA, p["fase"], p["chave_semente"], p["bloco"], p["cor_avaliado"], "adversario")
    avaliado = criar_agente("mcts", sem_av, p["experimento"], p["orcamento"], p["profundidade_minimax"])
    adversario = criar_agente(p["adversario"], sem_adv, p["experimento"], p["orcamento_adversario"],
                              p["profundidade_minimax"])
    jogador_avaliado = PRETAS if p["cor_avaliado"] == "pretas" else BRANCAS
    quem_joga = {jogador_avaliado: avaliado, -jogador_avaliado: adversario}

    estado = othello.estado_inicial()
    sequencia = []
    decisoes = []
    inicio_partida = time.perf_counter()
    while True:
        acoes = othello.acoes_legais(estado)
        if not acoes:
            break
        agente = quem_joga[estado.jogador]
        gc.disable()
        t0 = time.perf_counter()
        acao, inf = agente.decidir(estado)
        tempo = time.perf_counter() - t0
        gc.enable()
        gc.collect()
        if acao not in acoes:
            raise RuntimeError("acao ilegal do agente " + agente.nome)
        eh_avaliado = estado.jogador == jogador_avaliado
        orc = ""
        if agente.nome == "mcts":
            orc = p["orcamento"] if eh_avaliado else p["orcamento_adversario"]
        decisoes.append({
            "id_partida": p["id_partida"], "numero_jogada": len(sequencia),
            "jogador": "pretas" if estado.jogador == PRETAS else "brancas",
            "agente": agente.nome, "eh_avaliado": eh_avaliado, "acao": othello.nome_casa(acao),
            "numero_acoes_legais": len(acoes), "orcamento_solicitado": orc,
            "tempo_efetivo_s": round(tempo, 6), "iteracoes": inf["iteracoes"],
            "forcada": inf["forcada"], "contingencia": inf["contingencia"],
            "excesso_prazo_s": round(inf["excesso"], 6),
        })
        sequencia.append(othello.nome_casa(acao))
        estado = othello.aplicar_acao(estado, acao)

    pretas, brancas = othello.contagem(estado)
    pontos = othello.recompensa(estado, jogador_avaliado)
    registro = {
        "id_partida": p["id_partida"], "fase": p["fase"], "experimento": p["experimento"],
        "adversario": p["adversario"], "orcamento": p["orcamento"],
        "orcamento_adversario": p["orcamento_adversario"], "bloco": p["bloco"],
        "cor_avaliado": p["cor_avaliado"], "semente_avaliado": sem_av, "semente_adversario": sem_adv,
        "profundidade_minimax": p["profundidade_minimax"],
        "resultado": {1.0: "vitoria", 0.5: "empate", 0.0: "derrota"}[pontos], "pontos": pontos,
        "pretas": pretas, "brancas": brancas, "numero_jogadas": len(sequencia),
        "sequencia": " ".join(sequencia),
        "tempo_partida_s": round(time.perf_counter() - inicio_partida, 3),
        "data_hora": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    return registro, decisoes


def hash_do_codigo():
    h = hashlib.sha256()
    pasta = os.path.dirname(os.path.abspath(__file__))
    for nome in ["othello.py", "agentes.py", "executor.py", "analise.py"]:
        with open(os.path.join(pasta, nome), "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:12]


def salvar_manifesto(pasta, args, total, pendentes):
    caminho = os.path.join(pasta, "manifesto.json")
    lista = json.load(open(caminho, encoding="utf-8")) if os.path.exists(caminho) else []
    lista.append({
        "data_hora": datetime.datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split()[0], "sistema": platform.platform(),
        "processador": platform.processor() or platform.machine(),
        "nucleos_logicos": os.cpu_count(), "trabalhadores": args.trabalhadores,
        "versao_codigo": hash_do_codigo(), "argumentos": vars(args),
        "partidas_planejadas": total, "partidas_pendentes": pendentes,
    })
    json.dump(lista, open(caminho, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def abrir_csv(caminho, colunas):
    novo = not os.path.exists(caminho) or os.path.getsize(caminho) == 0
    arquivo = open(caminho, "a", encoding="utf-8", newline="")
    escritor = csv.DictWriter(arquivo, fieldnames=colunas)
    if novo:
        escritor.writeheader()
    return arquivo, escritor


def executar(args):
    os.makedirs(args.saida, exist_ok=True)
    caminho_partidas = os.path.join(args.saida, "partidas.csv")
    caminho_decisoes = os.path.join(args.saida, "decisoes.csv")

    experimentos = ["simulacoes", "tempo"] if args.experimento == "ambos" else [args.experimento]
    partidas = []
    for exp in experimentos:
        grade = GRADE_SIMULACOES if exp == "simulacoes" else GRADE_TEMPO_MS
        if args.grade:
            grade = [int(v) for v in args.grade.split(",")]
        partidas += montar_partidas(args.fase, exp, grade, args.adversarios.split(","),
                                    not args.sem_adjacentes, args.pares, args.pares_principal,
                                    args.profundidade_minimax)

    feitas = set()
    if os.path.exists(caminho_partidas):
        feitas = {linha["id_partida"] for linha in csv.DictReader(open(caminho_partidas, encoding="utf-8"))}
    pendentes = [p for p in partidas if p["id_partida"] not in feitas]
    random.Random(semente_derivada(SEMENTE_MESTRA, args.fase, args.experimento, "ordem")).shuffle(pendentes)

    salvar_manifesto(args.saida, args, len(partidas), len(pendentes))
    print("planejadas %d | ja feitas %d | pendentes %d | trabalhadores %d"
          % (len(partidas), len(feitas), len(pendentes), args.trabalhadores))
    if not pendentes:
        return

    arq_p, esc_p = abrir_csv(caminho_partidas, COLUNAS_PARTIDA)
    arq_d, esc_d = abrir_csv(caminho_decisoes, COLUNAS_DECISAO)
    inicio = time.perf_counter()
    n = 0

    def gravar(resultado):
        registro, decisoes = resultado
        for d in decisoes:
            esc_d.writerow(d)
        esc_p.writerow(registro)
        arq_d.flush()
        arq_p.flush()

    try:
        if args.trabalhadores <= 1:
            for p in pendentes:
                gravar(jogar_partida(p))
                n += 1
                progresso(n, len(pendentes), inicio)
        else:
            with multiprocessing.Pool(args.trabalhadores) as pool:
                for resultado in pool.imap_unordered(jogar_partida, pendentes):
                    gravar(resultado)
                    n += 1
                    progresso(n, len(pendentes), inicio)
    finally:
        arq_p.close()
        arq_d.close()
    print("fim: %d partidas em %.1f min" % (n, (time.perf_counter() - inicio) / 60))


def progresso(n, total, inicio):
    if n % 10 == 0 or n == total:
        passou = time.perf_counter() - inicio
        print("  %d/%d  (%.1f min, faltam ~%.1f min)" % (n, total, passou / 60, passou / n * (total - n) / 60), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fase", choices=["piloto", "final"], default="piloto")
    parser.add_argument("--experimento", choices=["simulacoes", "tempo", "ambos"], default="ambos")
    parser.add_argument("--saida", default="registros/piloto")
    parser.add_argument("--trabalhadores", type=int, default=1,
                        help="processos em paralelo (no experimento por tempo, no maximo os nucleos fisicos)")
    parser.add_argument("--profundidade-minimax", type=int, default=agentes.PROFUNDIDADE_MINIMAX)
    parser.add_argument("--adversarios", default=",".join(BASELINES))
    parser.add_argument("--sem-adjacentes", action="store_true")
    parser.add_argument("--grade", default=None, help="ex.: 25,50,100 (so pra testes)")
    parser.add_argument("--pares", type=int, default=None, help="pares por confronto (so pra testes)")
    parser.add_argument("--pares-principal", type=int, default=None,
                        help="fase final/tempo: total de pares em 640 e 1280 ms vs minimax (calculado com o piloto)")
    parser.add_argument("--teste-rapido", action="store_true", help="1 par e 2 orcamentos, so pra ver se roda")
    args = parser.parse_args()
    if args.teste_rapido:
        args.fase = "piloto"
        args.pares = 1
        args.experimento = "simulacoes" if args.experimento == "ambos" else args.experimento
        args.grade = "25,50" if args.experimento == "simulacoes" else "20,40"
        args.saida = "registros/teste_rapido"
    executar(args)
