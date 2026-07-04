# Resposta do Grupo D — preenchimento da PLA de Dispatch

Resposta a pendencia registrada no dossie de integracao do Grupo C ("precisamos
que voces enviem a lista com o Opcode, os 8 bits em binario, das 9 instrucoes da
Fase 1"). Os 8 bits sao `IR[27:20]`, do mais significativo para o menos:
`bit27 bit26 I opcode[24:21] S`.

## 1. Os 8 bits pedidos (visao por mnemonico)

| Instrucao | IR[27:20] | Observacao |
|---|---|---|
| ADD | `00x0100s` | x = I (imediato/registrador), s = S (flags) |
| SUB | `00x0010s` | idem |
| AND | `00x0000s` | idem |
| ORR | `00x1100s` | idem |
| CMP | `00x10101` | S sempre 1 |
| MOV | `00x1101s` | idem ADD |
| LDR | `01xxxxx1` | bit20 = L = 1 |
| STR | `01xxxxx0` | bit20 = L = 0 |
| B/Bcc | `101xxxxx` | bits 27:25 = 101 |

## 2. Por que a PLA foi preenchida com mais de 9 termos

Ao preencher, detectamos que **uma unica palavra de uROM por mnemonico nao e
suficiente**, por dois motivos verificados na propria uROM de voces:

1. **Bit S ignorado.** Todas as palavras de processamento de dados estavam com
   `FlagsWrite = 1`. Com isso, um `ADD` comum tambem escreveria as flags. No
   programa de teste P0, o `ADD R5,R5,#1` (sem S) fica entre o `SUBS` e o
   `BNE`: ele apagaria o Z do `SUBS` e o laco nunca terminaria (loop infinito).
2. **Operando imediato indistinguivel.** `ALU_srcB` estava fixo em `00`
   (shifter) nas palavras de processamento de dados. `MOV R1, #6` precisa de
   `ALU_srcB = 01` (imediato), e o sinal sai da uROM — entao imediato e
   registrador precisam de palavras diferentes.

Como a PLA de dispatch enxerga I (bit25) e S (bit20), resolvemos os dois casos
**sem mexer no circuito**: o dispatch separa as variantes e novas palavras
foram acrescentadas em enderecos livres da uROM. Mapa final:

| Classe | reg S=0 | reg S=1 | imm S=0 | imm S=1 |
|---|---|---|---|---|
| ADD | 0x10 | 0x16 | 0x08 | 0x02 |
| SUB | 0x11 | 0x17 | 0x09 | 0x03 |
| AND | 0x12 | 0x18 | 0x0A | 0x04 |
| ORR | 0x13 | 0x19 | 0x0B | 0x05 |
| MOV | 0x15 | 0x1A | 0x0C | 0x06 |
| CMP | — | 0x14 | — | 0x0D |
| LDR | 0x20–0x22 | | STR | 0x30–0x31 |
| B/Bcc | 0x3F | | | |

As palavras novas diferem das originais apenas em dois campos: variantes S=0
com `FlagsWrite = 0` (bit 3) e variantes imediatas com `ALU_srcB = 01`
(bits 12:11). Fetch (0x00), dispatch (0x01), LDR, STR e B ficaram intocados.
Os 25 termos sao mutuamente disjuntos (verificado sobre as 256 entradas) e
instrucao fora do subconjunto continua caindo no endereco 0 (NOP seguro).

## 3. Validacao

`testes/verifica_microcodigo.py` executa os cinco programas de teste
P0–P4 diretamente sobre `microcodigo/pla_dispatch.txt` + `microcodigo/urom.txt`,
interpretando os campos da palavra de 30 bits com o layout extraido do splitter
do `circuitos/unidade_controle_microprogramada.circ`, e compara com os estados
finais da bateria do Grupo D:

```
[1] PLA dispatch: 25 termos, 0 sobreposicoes nas 256 entradas
[2] P0..P4: OK (registradores, flags e memoria conferem)
```

## 4. Dois pontos de integracao a fechar (importantes)

1. **`cond_pass` nao pode cortar o PCWrite do fetch.** Hoje os 4 ANDs gateiam
   o pino `PCWrite_Out` sempre. Como o IR ainda segura a instrucao antiga
   durante o fetch seguinte, uma condicao falsa congela o PC por um ciclo e a
   instrucao seguinte **executa duas vezes**. Nos testes P0–P4 isso passa
   despercebido (as instrucoes re-executadas sao idempotentes), mas
   `ADDNE ...` seguido de `ADD R5,R5,#1` somaria 2. Conforme o contrato do
   avaliador (`documentacao/contrato_avaliador_condicao.md`), `cond_pass` deve
   gatear apenas os commits de execucao; o PCWrite do estado de fetch precisa
   passar por fora do AND (por exemplo, OR com o sinal "estado = fetch").
2. **Semantica de `invB_cin = 10` com o Grupo A.** Para subtracao, a intencao
   e `Rn + NOT(Op2) + 1`. Se a ALU ler os dois bits literalmente (bit1 =
   inverte B, bit0 = carry-in), `10` da carry-in 0 e toda subtracao sai com
   um a menos — o verificador mostra P1 travando e P0/P2/P3 divergindo nesse
   cenario. Ou a ALU liga o carry-in internamente quando inverte B, ou a
   palavra deve usar `11`. Precisa ser fechado com o Grupo A antes da
   integracao final.
