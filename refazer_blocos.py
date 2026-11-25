import csv
import os
import shutil
import sys

import executor

LIMITE = 50

pasta = sys.argv[1]
if executor.hash_do_codigo() == "73865154cb4a":
    print("ERRO: o executor.py ainda e a versao antiga (hash 73865154cb4a). atualize antes.")
    sys.exit(1)

for nome in ("partidas.csv", "decisoes.csv"):
    caminho = os.path.join(pasta, nome)
    copia = caminho + ".antes_de_refazer"
    if not os.path.exists(copia):
        shutil.copy(caminho, copia)

caminho_p = os.path.join(pasta, "partidas.csv")
with open(caminho_p, encoding="utf-8", newline="") as f:
    partidas = list(csv.DictReader(f))
manter = [p for p in partidas if int(p["bloco"]) > LIMITE]
ids = {p["id_partida"] for p in manter}
with open(caminho_p, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=executor.COLUNAS_PARTIDA)
    w.writeheader()
    w.writerows(manter)

caminho_d = os.path.join(pasta, "decisoes.csv")
tmp = caminho_d + ".tmp"
mantidas = 0
with open(caminho_d, encoding="utf-8", newline="") as f, open(tmp, "w", encoding="utf-8", newline="") as g:
    leitor = csv.DictReader(f)
    w = csv.DictWriter(g, fieldnames=executor.COLUNAS_DECISAO)
    w.writeheader()
    for d in leitor:
        if d["id_partida"] in ids:
            w.writerow(d)
            mantidas += 1
os.replace(tmp, caminho_d)

print("partidas: %d removidas, %d mantidas; decisoes mantidas: %d" % (len(partidas) - len(manter), len(manter), mantidas))
print("agora rode de novo os dois comandos da coleta final (mesmos parametros); so os blocos removidos serao jogados.")
