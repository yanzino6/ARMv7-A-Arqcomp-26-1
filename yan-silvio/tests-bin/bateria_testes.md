# Bateria de testes (Grupo D)

Programas de teste do nucleo minimo, com binario gerado e estado final esperado calculado por simulador do subconjunto ARMv7. A coluna observado e preenchida apos a integracao do Grupo B.

Convencoes: reset zera todos os registradores e a memoria. O PC lido no calculo de branch vale endereco mais 8. Cada programa termina em `B fim` (desvio para a propria instrucao), entao o processador estaciona nesse endereco; o valor final de R15/PC nao e um dado a conferir. As flags sao mostradas na ordem N Z C V.

## P1: Soma de 1 a 5 com laco condicional

Exercita MOV imediato, ADD registrador, SUBS com flags, BNE (branch condicional) e B.

_R0 acumula 5+4+3+2+1 = 15._

### Programa (assembly e binario)

| Endereco | Assembly | Hex |
|---|---|---|
| 0x00 | `MOV R0, #0` | `E3A00000` |
| 0x04 | `MOV R1, #5` | `E3A01005` |
| 0x08 | `ADD R0, R0, R1` | `E0800001` |
| 0x0C | `SUBS R1, R1, #1` | `E2511001` |
| 0x10 | `BNE loop` | `1AFFFFFC` |
| 0x14 | `B fim` | `EAFFFFFE` |

Arquivo de ROM pronto para carregar: `rom_p1.txt` (formato v2.0 raw do Logisim).

### Estado final esperado

| Item | Esperado | Observado |
|---|---|---|
| R0 | 0xF (15) |  |
| Flags N Z C V | 0 1 1 0 |  |

> Registradores nao listados devem permanecer em 0.

## P2: Aritmetica e logica sem desvio

Exercita MOV, ADD, SUB, AND, ORR e CMP, verificando registradores e flags.

_CMP 12 menos 10 deixa resultado positivo nao nulo sem borrow._

### Programa (assembly e binario)

| Endereco | Assembly | Hex |
|---|---|---|
| 0x00 | `MOV R0, #12` | `E3A0000C` |
| 0x04 | `MOV R1, #10` | `E3A0100A` |
| 0x08 | `ADD R2, R0, R1` | `E0802001` |
| 0x0C | `SUB R3, R0, R1` | `E0403001` |
| 0x10 | `AND R4, R0, R1` | `E0004001` |
| 0x14 | `ORR R5, R0, R1` | `E1805001` |
| 0x18 | `CMP R0, R1` | `E1500001` |
| 0x1C | `B fim` | `EAFFFFFE` |

Arquivo de ROM pronto para carregar: `rom_p2.txt` (formato v2.0 raw do Logisim).

### Estado final esperado

| Item | Esperado | Observado |
|---|---|---|
| R0 | 0xC (12) |  |
| R1 | 0xA (10) |  |
| R2 | 0x16 (22) |  |
| R3 | 0x2 (2) |  |
| R4 | 0x8 (8) |  |
| R5 | 0xE (14) |  |
| Flags N Z C V | 0 0 1 0 |  |

> Registradores nao listados devem permanecer em 0.

## P3: Execucao condicional (prova do cond_pass)

CMP iguala os operandos (Z=1). ADDEQ deve comitar e ADDNE deve virar NOP. Prova o gating do avaliador.

_So a instrucao cuja condicao passa escreve destino._

### Programa (assembly e binario)

| Endereco | Assembly | Hex |
|---|---|---|
| 0x00 | `MOV R0, #7` | `E3A00007` |
| 0x04 | `MOV R1, #7` | `E3A01007` |
| 0x08 | `CMP R0, R1` | `E1500001` |
| 0x0C | `ADDEQ R2, R0, #1` | `02802001` |
| 0x10 | `ADDNE R3, R0, #1` | `12803001` |
| 0x14 | `B fim` | `EAFFFFFE` |

Arquivo de ROM pronto para carregar: `rom_p3.txt` (formato v2.0 raw do Logisim).

### Estado final esperado

| Item | Esperado | Observado |
|---|---|---|
| R0 | 0x7 (7) |  |
| R1 | 0x7 (7) |  |
| R2 | 0x8 (8) |  |
| Flags N Z C V | 0 1 1 0 |  |

> Registradores nao listados devem permanecer em 0.

## P4: Load e store (ida e volta na memoria)

Grava um valor na RAM de dados com STR e le de volta com LDR, com e sem offset.

_O valor gravado deve voltar identico em outro registrador._

### Programa (assembly e binario)

| Endereco | Assembly | Hex |
|---|---|---|
| 0x00 | `MOV R1, #0x40` | `E3A01040` |
| 0x04 | `MOV R0, #0xAB` | `E3A000AB` |
| 0x08 | `STR R0, [R1]` | `E5810000` |
| 0x0C | `STR R0, [R1, #4]` | `E5810004` |
| 0x10 | `LDR R5, [R1]` | `E5915000` |
| 0x14 | `LDR R6, [R1, #4]` | `E5916004` |
| 0x18 | `B fim` | `EAFFFFFE` |

Arquivo de ROM pronto para carregar: `rom_p4.txt` (formato v2.0 raw do Logisim).

### Estado final esperado

| Item | Esperado | Observado |
|---|---|---|
| R0 | 0xAB (171) |  |
| R1 | 0x40 (64) |  |
| R5 | 0xAB (171) |  |
| R6 | 0xAB (171) |  |
| Flags N Z C V | 0 0 0 0 |  |
| Mem[0x40] | 0xAB |  |
| Mem[0x44] | 0xAB |  |

> Registradores nao listados devem permanecer em 0.
