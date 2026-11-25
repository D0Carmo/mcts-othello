# MCTS no Othello — código do experimento

**Autores:** Vinicius do Carmo, Miguel Pereira Gonçalves, Rafael da Silva Cruz.

Python 3 puro (matplotlib só pros gráficos). Cada arquivo corresponde a uma parte da Metodologia do artigo:

| arquivo | o que faz | artigo |
|---|---|---|
| `othello.py` | regras do jogo, passe, fim de jogo, recompensa | III.A |
| `agentes.py` | MCTS (as 4 fases e o UCT) e os adversários: aleatório, guloso e minimax (eq. 2) | III.B e III.C |
| `executor.py` | joga as partidas em blocos com as cores trocadas, sementes, grades, registros csv e manifesto | III.D e III.E |
| `analise.py` | confere as partidas, taxa de pontuação, intervalo por bootstrap, ganhos e gráficos | III.D e III.F |
| `testes.py` | os 19 testes automáticos | III.G |
| `ver_partida.py` | janela pra rever partidas gravadas ou ver o MCTS jogando ao vivo | demonstração |
| `refazer_blocos.py` | correção usada uma vez na coleta final (ver abaixo) | — |

## Rodando

O `decisoes.csv` de cada coleta está compactado (`registros/<fase>/decisoes.zip`) por causa do limite de tamanho do GitHub. Descompacte na mesma pasta antes de rodar a análise.

```
python -m unittest testes -v                  # 19 testes
python executor.py --teste-rapido             # 1 min, só pra ver funcionando
python analise.py registros/teste_rapido

# piloto (50 pares por confronto)
python executor.py --fase piloto --experimento simulacoes --saida registros/piloto --trabalhadores 8 --profundidade-minimax 2
python executor.py --fase piloto --experimento tempo      --saida registros/piloto --trabalhadores 7 --profundidade-minimax 2
python analise.py registros/piloto

# final (o número de pares da comparação principal vem do planejamento.json do piloto)
python executor.py --fase final --experimento simulacoes --saida registros/final --trabalhadores 8 --profundidade-minimax 2
python executor.py --fase final --experimento tempo      --saida registros/final --trabalhadores 7 --profundidade-minimax 2 --pares-principal 1084
python analise.py registros/final
```

- `--trabalhadores`: quantas partidas rodam ao mesmo tempo. No experimento por tempo usamos menos que os núcleos físicos, pra uma partida não roubar tempo da outra.
- se cair no meio (Ctrl+C, reboot), é só rodar o mesmo comando de novo: o que já está no `partidas.csv` não é jogado outra vez.
- as sementes incluem a fase, então a coleta final nunca repete partidas do piloto. Na primeira coleta final isso falhou porque rodou um executor desatualizado; o `refazer_blocos.py registros\final` tirou os blocos 1 a 50 e o executor jogou eles de novo.
- a análise grava em `registros/<pasta>/analise/`: `resumo.txt`, `taxas.csv`, `ganhos.csv`, `planejamento.json` e os gráficos.

## Ver as partidas

```
python ver_partida.py registros\final                                  # rever qualquer partida gravada
python ver_partida.py --ao-vivo --simulacoes 25                        # MCTS pensando pouco contra o minimax
python ver_partida.py --ao-vivo --tempo-ms 1280                        # MCTS pensando muito
python ver_partida.py --ao-vivo --tempo-ms 640 --mcts-de brancas
```

Botões: Início, Voltar, Avançar (uma jogada por vez), Jogar até o fim (automático, vira Pausar) e Fim. No modo ao vivo também tem Nova partida. Setas do teclado avançam e voltam, espaço liga e desliga o automático. Anel laranja = última jogada, ponto laranja = peça que virou, bolinha clara = jogada possível.

Não usar o modo ao vivo enquanto roda o experimento de tempo (disputa o processador).

## Coisas que valem explicar

- o tabuleiro é guardado como 10x10 com uma borda: andar numa direção é só somar um deslocamento, sem testar se saiu do tabuleiro.
- `jogada_aleatoria_rapida`: sorteia uma casa vazia e testa só ela. Continua com a mesma chance pra todas as jogadas válidas e é cerca de 2x mais rápido que listar todas.
- a recompensa é somada pelo "jogador de entrada" de cada nó (quem fez a jogada que chegou nele). É isso que faz o passe funcionar; inverter o sinal a cada nível daria errado.
- minimax: na raiz cada jogada é avaliada sem poda, pra ter o valor exato e sortear entre empates; a poda alfa-beta fica nos níveis de baixo.
- sementes: `sha256(mestra|fase|adversario|bloco|cor|papel)`. O orçamento não entra, então o mesmo bloco tem a mesma sorte em todos os orçamentos.
- o executor desliga o coletor de lixo do Python durante a decisão e limpa depois; sem isso apareciam estouros de prazo de até ~100 ms que não tinham nada a ver com o algoritmo.

## Decisões tomadas antes do piloto

- **minimax com profundidade 2**: com profundidade 4 (a proposta do artigo), o MCTS perdeu todas as partidas em todos os orçamentos, até com 1.600 simulações e 1,28 s. Com tudo em zero não dá pra medir a melhora, então mudamos pra 2 e mantivemos igual em toda a coleta.
- **tamanho da amostra**: o piloto deu 1.084 pares pra comparação principal (640 ms contra 1,28 s), que foi o que usamos na coleta final.
