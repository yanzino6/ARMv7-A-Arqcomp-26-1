# Documentacao Grupo D (parte independente)

Processador ARMv7 no Logisim com controle microprogramado.
Autoria: Yan e Silvio. Base tecnica: referencia ARMv7 destilada do manual ARM DDI 0406C.c.

Este documento cobre as tres entregas do Grupo D que nao dependem de outros grupos: o modelo de programacao, as fichas das instrucoes do nucleo minimo e a secao do avaliador de condicao.

---

## 1. Modelo de programacao adotado

### 1.1 Registradores

O processador tem 16 registradores visiveis de 32 bits, de R0 a R15. O especificador de registrador em qualquer instrucao ocupa 4 bits.

| Registrador | Nome | Funcao |
|-------------|------|--------|
| R0 a R12 | uso geral | 13 registradores de proposito geral |
| R13 | SP | ponteiro de pilha |
| R14 | LR | registrador de link (endereco de retorno) |
| R15 | PC | contador de programa |

### 1.2 Flags de condicao (APSR)

O estado de condicao fica nos quatro bits mais altos do APSR (o mesmo registrador que a CPSR no nivel de aplicacao).

| Bit | Flag | Significado | Como e setada |
|-----|------|-------------|---------------|
| 31 | N | Negative | recebe o bit 31 do resultado; 1 se o resultado com sinal e negativo |
| 30 | Z | Zero | 1 se o resultado e igual a zero |
| 29 | C | Carry | vem e vai da soma ou subtracao; nas operacoes logicas recebe o carry do shifter |
| 28 | V | Overflow | overflow com sinal em soma ou subtracao |

As flags so sao atualizadas quando a instrucao tem o bit S igual a 1, ou quando e uma comparacao (CMP, CMN, TST, TEQ), que tem S implicitamente 1.

### 1.3 Semantica do PC (decisao do grupo)

No ARM real, ao ler o PC em estado ARM o valor entregue e o endereco da instrucao corrente mais 8, por causa do pipeline classico de tres estagios. Escrever um endereco no PC causa um desvio.

**Decisao adotada:** implementamos o mais 8 fiel, porem localizado apenas no somador de desvio (o adder do branch). O fetch continua usando o incremento normal de PC mais 4.

**Justificativa:** os binarios de teste do repositorio de partida foram montados assumindo que o PC lido no calculo do branch e o endereco da instrucao mais 8. Localizar o mais 8 so no somador do branch preserva a compatibilidade com esses binarios e mantem o restante do caminho de dados simples, sem precisar propagar o mais 8 por toda a leitura de registradores.

### 1.4 Formato geral da instrucao

Todas as instrucoes ARM tem largura fixa de 32 bits e sao alinhadas em palavra. Os bits 31 a 28 sao sempre o codigo de condicao (campo `cond`). A ausencia de sufixo de condicao equivale a `AL` (sempre), codigo `1110`.

```
 31    28 27 26 25 24                                    0
| cond  |            resto conforme a classe             |
```

---

## 2. Fichas das instrucoes do nucleo minimo

O nucleo minimo cobre MOV, ADD, SUB, AND, ORR, CMP, B (e branch condicional), LDR e STR. Todas as fichas usam a codificacao Encoding A1.

Codigos de operacao (bits 24 a 21) do grupo de processamento de dados usados aqui: AND `0000`, SUB `0010`, ADD `0100`, CMP `1010`, ORR `1100`, MOV `1101`.

Legenda dos campos de processamento de dados:

```
 31    28 27 26 25 24    21 20 19   16 15   12 11              0
| cond  | 0  0 | I | opcode | S |  Rn   |  Rd   |   operand2    |
```

Onde `I` seleciona operando imediato (1) ou registrador (0), `S` habilita a escrita de flags, `Rn` e o primeiro operando, `Rd` e o destino e `operand2` e o segundo operando (imediato modificado, registrador ou registrador deslocado).

### 2.1 MOV

- **Sintaxe:** `MOV{S}{<c>} Rd, <operando2>`
- **Opcode:** `1101` (bits 24 a 21). `Rn` e ignorado (deve ser `0000`).
- **Flags afetadas:** apenas se `S` igual a 1. N e Z do resultado, C do carry do shifter, V inalterada.
- **Funcionamento:** copia o operando 2 para `Rd`.
- **Modo de endereco:** imediato modificado, registrador ou registrador deslocado.
- **Exemplo:** `MOV R1, #5` = `E3A01005`. `MOV R2, R1, LSL #2` = `E1A02101`.

### 2.2 ADD

- **Sintaxe:** `ADD{S}{<c>} Rd, Rn, <operando2>`
- **Opcode:** `0100`.
- **Flags afetadas:** apenas se `S` igual a 1. N, Z, C e V da soma.
- **Funcionamento:** `Rd = Rn + operando2`.
- **Modo de endereco:** imediato modificado, registrador ou registrador deslocado.
- **Exemplo:** `ADD R0, R1, R2` = `E0810002`. `ADDS R0, R1, R2` = `E0910002`.

### 2.3 SUB

- **Sintaxe:** `SUB{S}{<c>} Rd, Rn, <operando2>`
- **Opcode:** `0010`.
- **Flags afetadas:** apenas se `S` igual a 1. N, Z, C (borrow) e V da subtracao.
- **Funcionamento:** `Rd = Rn menos operando2`.
- **Modo de endereco:** imediato modificado, registrador ou registrador deslocado.
- **Exemplo:** `SUB R3, R3, #1` = `E2433001`. `SUBS R3, R3, #1` = `E2533001`.

### 2.4 AND

- **Sintaxe:** `AND{S}{<c>} Rd, Rn, <operando2>`
- **Opcode:** `0000`.
- **Flags afetadas:** apenas se `S` igual a 1. N e Z do resultado, C do carry do shifter, V inalterada.
- **Funcionamento:** `Rd = Rn E operando2` (E logico bit a bit).
- **Modo de endereco:** imediato modificado, registrador ou registrador deslocado.
- **Exemplo:** `AND R4, R5, R6` = `E0054006`.

### 2.5 ORR

- **Sintaxe:** `ORR{S}{<c>} Rd, Rn, <operando2>`
- **Opcode:** `1100`.
- **Flags afetadas:** apenas se `S` igual a 1. N e Z do resultado, C do carry do shifter, V inalterada.
- **Funcionamento:** `Rd = Rn OU operando2` (OU logico bit a bit).
- **Modo de endereco:** imediato modificado, registrador ou registrador deslocado.
- **Exemplo:** `ORR R4, R5, R6` = `E1854006`.

### 2.6 CMP

- **Sintaxe:** `CMP{<c>} Rn, <operando2>`
- **Opcode:** `1010`. `S` e sempre 1 e `Rd` e ignorado.
- **Flags afetadas:** sempre. N, Z, C e V do resultado de `Rn menos operando2`.
- **Funcionamento:** calcula `Rn menos operando2`, atualiza as flags e descarta o resultado.
- **Modo de endereco:** imediato modificado, registrador ou registrador deslocado.
- **Exemplo:** `CMP R0, R1` = `E1500001`.

### 2.7 LDR

Formato de carga e armazenamento com offset imediato:

```
 31    28 27 26 25 24 23 22 21 20 19   16 15   12 11        0
| cond  | 0  1 | I  P  U  B  W  L |  Rn   |  Rt   |  imm12    |
```

Onde `I` igual a 0 seleciona offset imediato, `P` seleciona pre indexacao ou offset, `U` soma (1) ou subtrai (0) o offset, `B` seleciona byte (1) ou palavra (0), `W` habilita writeback e `L` igual a 1 indica carga.

- **Sintaxe:** `LDR{<c>} Rt, [Rn, #imm]`
- **Codificacao:** classe load/store, `L` igual a 1, `B` igual a 0 (palavra).
- **Flags afetadas:** nenhuma.
- **Funcionamento:** `Rt = Mem[Rn + imm]`.
- **Modo de endereco:** offset imediato. Formas pre e pos indexadas ficam para a fase 2.
- **Exemplo:** `LDR R0, [R1]` = `E5910000`. `LDR R0, [R1, #4]` = `E5910004`.

### 2.8 STR

- **Sintaxe:** `STR{<c>} Rt, [Rn, #imm]`
- **Codificacao:** classe load/store, `L` igual a 0, `B` igual a 0 (palavra).
- **Flags afetadas:** nenhuma.
- **Funcionamento:** `Mem[Rn + imm] = Rt`.
- **Modo de endereco:** offset imediato. Formas pre e pos indexadas ficam para a fase 2.
- **Exemplo:** `STR R0, [R1]` = `E5810000`.

### 2.9 B e branch condicional

Formato de desvio:

```
 31    28 27 26 25 24 23                             0
| cond  | 1  0  1 | L |             imm24            |
```

Para `B`, `L` igual a 0. O campo `cond` diferente de `1110` transforma o desvio em condicional (por exemplo `BNE` com `cond` igual a `0001`).

- **Sintaxe:** `B{<c>} <label>`
- **Codificacao:** bits 27 a 24 iguais a `1010`.
- **Flags afetadas:** nenhuma.
- **Funcionamento:** `PC = PC + SignExtend(imm24 concatenado com 00)`, lembrando que o PC lido no calculo vale endereco mais 8.
- **Modo de endereco:** relativo ao PC, com offset com sinal multiplicado por 4.
- **Exemplo:** `B .` (desvio para a propria instrucao) = `EAFFFFFE`. `BNE loop` = `1AFFFFFC`.

---

## 3. Avaliador de condicao (secao do relatorio)

### 3.1 Funcao e interface

O avaliador de condicao e um subcircuito proprio que implementa diretamente a tabela de codigos de condicao da secao A8.3 do manual. Ele recebe o campo `cond` (bits 31 a 28 da instrucao) e as flags N, Z, C, V, e produz um unico sinal `cond_pass`.

| Pino | Direcao | Largura | Significado |
|------|---------|---------|-------------|
| `cond` | entrada | 4 bits | campo de condicao, IR bits 31 a 28 |
| `NZCV` | entrada | 4 bits | flags atuais, com N no bit 3 e V no bit 0 |
| `cond_pass` | saida | 1 bit | 1 se a condicao e satisfeita |

### 3.2 Tabela de codigos de condicao (A8.3)

| cond | Mnem. | cond_pass = 1 quando |
|------|-------|----------------------|
| 0000 | EQ | Z = 1 |
| 0001 | NE | Z = 0 |
| 0010 | CS / HS | C = 1 |
| 0011 | CC / LO | C = 0 |
| 0100 | MI | N = 1 |
| 0101 | PL | N = 0 |
| 0110 | VS | V = 1 |
| 0111 | VC | V = 0 |
| 1000 | HI | C = 1 e Z = 0 |
| 1001 | LS | C = 0 ou Z = 1 |
| 1010 | GE | N = V |
| 1011 | LT | N diferente de V |
| 1100 | GT | Z = 0 e N = V |
| 1101 | LE | Z = 1 ou N diferente de V |
| 1110 | AL | sempre |
| 1111 | (incondicional) | tratado como sempre |

### 3.3 Tabela verdade da PLA (22 termos)

A funcao acima foi implementada como uma PLA de 8 entradas (cond concatenado com NZCV) e 1 saida. Cada linha e um termo produto; entradas nao marcadas sao indiferentes. Qualquer combinacao que nao case com nenhum termo produz saida 0.

Ordem das entradas, do mais significativo para o menos: cond3 cond2 cond1 cond0 N Z C V.

| Termo | Entrada (cond N Z C V) | Saida | Codigo |
|-------|------------------------|-------|--------|
| 1 | `0000 - 1 - -` | 1 | EQ |
| 2 | `0001 - 0 - -` | 1 | NE |
| 3 | `0010 - - 1 -` | 1 | CS/HS |
| 4 | `0011 - - 0 -` | 1 | CC/LO |
| 5 | `0100 1 - - -` | 1 | MI |
| 6 | `0101 0 - - -` | 1 | PL |
| 7 | `0110 - - - 1` | 1 | VS |
| 8 | `0111 - - - 0` | 1 | VC |
| 9 | `1000 - 0 1 -` | 1 | HI |
| 10 | `1001 - - 0 -` | 1 | LS (ramo C=0) |
| 11 | `1001 - 1 - -` | 1 | LS (ramo Z=1) |
| 12 | `1010 1 - - 1` | 1 | GE (ramo N=V=1) |
| 13 | `1010 0 - - 0` | 1 | GE (ramo N=V=0) |
| 14 | `1011 1 - - 0` | 1 | LT (ramo N=1,V=0) |
| 15 | `1011 0 - - 1` | 1 | LT (ramo N=0,V=1) |
| 16 | `1100 1 0 - 1` | 1 | GT (ramo N=V=1) |
| 17 | `1100 0 0 - 0` | 1 | GT (ramo N=V=0) |
| 18 | `1101 - 1 - -` | 1 | LE (ramo Z=1) |
| 19 | `1101 1 - - 0` | 1 | LE (ramo N=1,V=0) |
| 20 | `1101 0 - - 1` | 1 | LE (ramo N=0,V=1) |
| 21 | `1110 - - - -` | 1 | AL |
| 22 | `1111 - - - -` | 1 | incondicional |

Esta tabela foi verificada por script contra as 256 combinacoes possiveis de entrada, com zero divergencias. O arquivo `pla_condicao.txt`, no formato de importacao do Logisim Evolution, contem exatamente esses 22 termos.

### 3.4 Vetores de teste (30 casos)

Cada codigo de condicao tem pelo menos um caso que passa e um que falha. `AL` e o campo incondicional tem um caso cada.

| # | cond | Mnem. | N | Z | C | V | cond_pass |
|---|------|-------|---|---|---|---|-----------|
| 1 | 0000 | EQ | 0 | 1 | 0 | 0 | 1 |
| 2 | 0000 | EQ | 0 | 0 | 0 | 0 | 0 |
| 3 | 0001 | NE | 0 | 0 | 0 | 0 | 1 |
| 4 | 0001 | NE | 0 | 1 | 0 | 0 | 0 |
| 5 | 0010 | CS/HS | 0 | 0 | 1 | 0 | 1 |
| 6 | 0010 | CS/HS | 0 | 0 | 0 | 0 | 0 |
| 7 | 0011 | CC/LO | 0 | 0 | 0 | 0 | 1 |
| 8 | 0011 | CC/LO | 0 | 0 | 1 | 0 | 0 |
| 9 | 0100 | MI | 1 | 0 | 0 | 0 | 1 |
| 10 | 0100 | MI | 0 | 0 | 0 | 0 | 0 |
| 11 | 0101 | PL | 0 | 0 | 0 | 0 | 1 |
| 12 | 0101 | PL | 1 | 0 | 0 | 0 | 0 |
| 13 | 0110 | VS | 0 | 0 | 0 | 1 | 1 |
| 14 | 0110 | VS | 0 | 0 | 0 | 0 | 0 |
| 15 | 0111 | VC | 0 | 0 | 0 | 0 | 1 |
| 16 | 0111 | VC | 0 | 0 | 0 | 1 | 0 |
| 17 | 1000 | HI | 0 | 0 | 1 | 0 | 1 |
| 18 | 1000 | HI | 0 | 1 | 1 | 0 | 0 |
| 19 | 1001 | LS | 0 | 1 | 1 | 0 | 1 |
| 20 | 1001 | LS | 0 | 0 | 1 | 0 | 0 |
| 21 | 1010 | GE | 1 | 0 | 0 | 1 | 1 |
| 22 | 1010 | GE | 1 | 0 | 0 | 0 | 0 |
| 23 | 1011 | LT | 1 | 0 | 0 | 0 | 1 |
| 24 | 1011 | LT | 1 | 0 | 0 | 1 | 0 |
| 25 | 1100 | GT | 1 | 0 | 0 | 1 | 1 |
| 26 | 1100 | GT | 1 | 1 | 0 | 1 | 0 |
| 27 | 1101 | LE | 1 | 1 | 0 | 0 | 1 |
| 28 | 1101 | LE | 0 | 0 | 0 | 0 | 0 |
| 29 | 1110 | AL | 0 | 0 | 0 | 0 | 1 |
| 30 | 1111 | NV | 0 | 0 | 0 | 0 | 1 |

### 3.5 Nota de integracao (gating de commit)

`cond_pass` e usado pelo Grupo C como habilitacao global de commit. Ele governa apenas os sinais de escrita: RegWrite, MemWrite, FlagsWrite e o PCWrite condicional do branch. Quando a condicao falha, a instrucao vira NOP, mas o fetch e o incremento normal do PC continuam. O sinal nunca entra no PC mais 4, no ciclo de fetch nem no sequenciamento do microendereco.
