# Relatorio - Processador ARMv7 no Logisim com controle microprogramado

Disciplina de Arquitetura e Organizacao de Computadores - 2026/1.

**Equipe:** Vitor Oli e Renan (Grupo A) · Thiago Paiva e Sofia (Grupo B) · Thiago e Vitor Riguette (Grupo C) · Yan e Silvio (Grupo D).

Base tecnica: referencia ARMv7 destilada do manual *ARM Architecture Reference Manual - ARMv7-A and ARMv7-R edition* (ARM DDI 0406C.c) e repositorio de partida ARMv7-Logisim (David Eckhardt, TU Darmstadt, 2021).

---

## 1. Introducao e objetivos

Este trabalho projeta e implementa um subconjunto do processador ARMv7-A no Logisim Evolution, com caminho de dados modular (um subcircuito por bloco) e unidade de controle microprogramada, baseada em uma memoria de microcodigo (uROM) e em PLAs com conteudo entregue em arquivos separados.

O escopo implementado e o nucleo minimo do conjunto ARM: **MOV, ADD, SUB, AND, ORR, CMP, B (incluindo branch condicional), LDR e STR** com offset imediato, com execucao condicional por qualquer um dos 16 codigos de condicao e segundo operando com deslocamento (barrel shifter). Todas as instrucoes tem 32 bits, alinhadas em palavra, com o campo de condicao nos bits 31 a 28.

Arquivos entregues, organizados em quatro pastas:

**`circuitos/`** - os arquivos do Logisim Evolution:

| Arquivo | Conteudo |
|---|---|
| `circuitos/cpu_principal.circ` | Circuito principal da CPU integrada (abre com o programa P0 ja carregado na ROM; importa `avaliador_condicao.circ`) |
| `circuitos/avaliador_condicao.circ` | Subcircuito do avaliador de condicao (PLA) |
| `circuitos/unidade_controle_microprogramada.circ` | Unidade de controle microprogramada do Grupo C (uPC + uROM + PLA de dispatch) |
| `circuitos/modulo_alu_grupoA.circ` | Modulo do Grupo A: ALU com flags NZCV em nivel de porta, barrel shifter, ARMExpandImm e SignExtend, com testbench proprio |

**`microcodigo/`** - o conteudo da uROM e das PLAs em arquivos separados, como pede o enunciado:

| Arquivo | Conteudo |
|---|---|
| `microcodigo/urom.txt` | Conteudo da uROM (64 palavras de 30 bits, formato v3.0 hex do Logisim) |
| `microcodigo/pla_dispatch.txt` | Conteudo da PLA de dispatch (25 termos, preenchida pelo Grupo D) |
| `microcodigo/pla_condicao.txt` | Conteudo da PLA de condicao (22 termos, importavel no Logisim Evolution) |

**`testes/`** - assembly, binarios e verificadores automatizados:

| Arquivo | Conteudo |
|---|---|
| `testes/bateria_testes.md` | Assembly, binario e resultado esperado/observado de cada programa de teste |
| `testes/rom_p0.txt` … `rom_p4.txt` | Binarios dos programas de teste (imagens de ROM, formato v2.0 raw) |
| `testes/vetores_avaliador_condicao.txt` | Vetores de teste do avaliador de condicao (30 casos, executaveis via Simulate > Test Vector) |
| `testes/simulador_subconjunto.py` | Simulador de referencia do subconjunto ARM que calcula e confere os estados finais esperados de P0 a P4 |
| `testes/verifica_pla_condicao.py` | Verificacao exaustiva da PLA de condicao contra a tabela A8-1 (256 combinacoes) |
| `testes/verifica_microcodigo.py` | Verificador que executa P0-P4 sobre `pla_dispatch.txt` + `urom.txt` reais e confere os estados finais |

**`documentacao/`** - material de apoio e registros de integracao:

| Arquivo | Conteudo |
|---|---|
| `documentacao/fichas_instrucoes_grupoD.md` | Modelo de programacao e fichas detalhadas das instrucoes (Grupo D) |
| `documentacao/contrato_avaliador_condicao.md` | Contrato de interface do avaliador de condicao |
| `documentacao/resposta_dispatch_grupoD.md` | Resposta do Grupo D a pendencia do dispatch: mapa de microenderecos, correcoes na uROM e pontos de integracao |
| `documentacao/dossie_integracao_grupoC.docx` | Dossie de integracao do Grupo C (decisoes de projeto e convencoes de sinais) |
| `documentacao/referencia_armv7.md` | Referencia ARMv7 destilada do manual (base de todas as codificacoes) |
| `documentacao/plano_de_execucao.pdf` | Plano de execucao e divisao de tarefas |

---

## 2. Modelo de programacao adotado

### 2.1 Registradores

16 registradores visiveis de 32 bits, R0 a R15. O especificador de registrador em qualquer instrucao ocupa 4 bits.

| Registrador | Nome | Funcao |
|-------------|------|--------|
| R0 a R12 | uso geral | 13 registradores de proposito geral |
| R13 | SP | ponteiro de pilha |
| R14 | LR | registrador de link (endereco de retorno) |
| R15 | PC | contador de programa |

O banco de registradores segue o modelo "15 + 1" do repositorio de partida: R0 a R14 sao registradores fisicos no banco e o PC e um registrador dedicado do caminho de fetch, exposto ao banco como a 16a posicao de leitura.

### 2.2 Flags de condicao (APSR)

O estado de condicao fica nos quatro bits mais altos da APSR (o mesmo registrador que a CPSR no nivel de aplicacao).

| Bit | Flag | Significado | Como e setada |
|-----|------|-------------|---------------|
| 31 | N | Negative | recebe o bit 31 do resultado; 1 se o resultado com sinal e negativo |
| 30 | Z | Zero | 1 se o resultado e igual a zero |
| 29 | C | Carry | carry/borrow da soma ou subtracao; nas operacoes logicas recebe o carry do shifter |
| 28 | V | Overflow | overflow com sinal em soma ou subtracao |

As flags so sao atualizadas quando a instrucao tem o bit S igual a 1, ou quando e uma comparacao (CMP, CMN, TST, TEQ), que tem S implicitamente 1.

### 2.3 Semantica do PC (decisao do grupo)

No ARM real, ao ler o PC em estado ARM o valor entregue e o endereco da instrucao corrente mais 8, por causa do pipeline classico de tres estagios. Escrever um endereco no PC causa um desvio.

**Decisao adotada:** implementamos o "mais 8" fiel, porem localizado apenas no somador de desvio (o adder do branch). O fetch continua usando o incremento normal de PC.

**Detalhe de implementacao:** o PC do circuito tem 24 bits e e **enderecado por palavra** (a ROM de instrucoes tem enderecos de 24 bits e palavras de 32 bits). Assim, o incremento de fetch e PC+1 (uma palavra = proxima instrucao) e o "mais 8" do ARM vira **PC+2** no somador de branch - dois adders dedicados no circuito principal (`PCPlus1` e `PCPlus2`). O offset `imm24` do branch ja e um deslocamento em palavras no proprio ARM, entao os binarios montados com a convencao byte-a-byte do manual funcionam sem ajuste.

**Justificativa:** os binarios de teste foram montados assumindo que o PC lido no calculo do branch e o endereco da instrucao mais 8. Localizar o "mais 8" so no somador do branch preserva a compatibilidade com esses binarios e mantem o restante do caminho de dados simples.

### 2.4 Formato geral da instrucao

```
 31    28 27 26 25 24                                    0
| cond  |            resto conforme a classe             |
```

Os bits 31 a 28 sao sempre o codigo de condicao (campo `cond`). A ausencia de sufixo de condicao equivale a `AL` (sempre), codigo `1110`.

---

## 3. Conjunto de instrucoes implementadas

Codigos de operacao (bits 24 a 21) do grupo de processamento de dados usados: AND `0000`, SUB `0010`, ADD `0100`, CMP `1010`, ORR `1100`, MOV `1101`. Todas as fichas usam a codificacao Encoding A1 do manual.

Legenda dos campos de processamento de dados:

```
 31    28 27 26 25 24    21 20 19   16 15   12 11              0
| cond  | 0  0 | I | opcode | S |  Rn   |  Rd   |   operand2    |
```

Onde `I` seleciona operando imediato (1) ou registrador (0), `S` habilita a escrita de flags, `Rn` e o primeiro operando, `Rd` e o destino e `operand2` e o segundo operando (imediato modificado, registrador ou registrador deslocado).

### 3.1 MOV

- **Sintaxe:** `MOV{S}{<c>} Rd, <operando2>`
- **Opcode:** `1101` (bits 24 a 21). `Rn` e ignorado (deve ser `0000`).
- **Flags afetadas:** apenas se `S` igual a 1. N e Z do resultado, C do carry do shifter, V inalterada.
- **Funcionamento:** copia o operando 2 para `Rd`.
- **Modo de enderecamento:** imediato modificado, registrador ou registrador deslocado.
- **Exemplos:** `MOV R1, #5` = `E3A01005`. `MOV R2, R1, LSL #2` = `E1A02101` (os shifts LSL/LSR/ASR/ROR sao, na arquitetura, codificados como MOV com o campo `type`/`imm5` indicando o deslocamento).

### 3.2 ADD

- **Sintaxe:** `ADD{S}{<c>} Rd, Rn, <operando2>`
- **Opcode:** `0100`.
- **Flags afetadas:** apenas se `S` igual a 1. N, Z, C e V da soma.
- **Funcionamento:** `Rd = Rn + operando2`.
- **Modo de enderecamento:** imediato modificado, registrador ou registrador deslocado.
- **Exemplos:** `ADD R0, R1, R2` = `E0810002`. `ADDS R0, R1, R2` = `E0910002`.

### 3.3 SUB

- **Sintaxe:** `SUB{S}{<c>} Rd, Rn, <operando2>`
- **Opcode:** `0010`.
- **Flags afetadas:** apenas se `S` igual a 1. N, Z, C (borrow) e V da subtracao.
- **Funcionamento:** `Rd = Rn - operando2` (realizada na ALU como `Rn + NOT(operando2) + 1`).
- **Modo de enderecamento:** imediato modificado, registrador ou registrador deslocado.
- **Exemplos:** `SUB R3, R3, #1` = `E2433001`. `SUBS R3, R3, #1` = `E2533001`.

### 3.4 AND

- **Sintaxe:** `AND{S}{<c>} Rd, Rn, <operando2>`
- **Opcode:** `0000`.
- **Flags afetadas:** apenas se `S` igual a 1. N e Z do resultado, C do carry do shifter, V inalterada.
- **Funcionamento:** `Rd = Rn E operando2` (E logico bit a bit).
- **Modo de enderecamento:** imediato modificado, registrador ou registrador deslocado.
- **Exemplo:** `AND R4, R5, R6` = `E0054006`.

### 3.5 ORR

- **Sintaxe:** `ORR{S}{<c>} Rd, Rn, <operando2>`
- **Opcode:** `1100`.
- **Flags afetadas:** apenas se `S` igual a 1. N e Z do resultado, C do carry do shifter, V inalterada.
- **Funcionamento:** `Rd = Rn OU operando2` (OU logico bit a bit).
- **Modo de enderecamento:** imediato modificado, registrador ou registrador deslocado.
- **Exemplo:** `ORR R4, R5, R6` = `E1854006`.

### 3.6 CMP

- **Sintaxe:** `CMP{<c>} Rn, <operando2>`
- **Opcode:** `1010`. `S` e sempre 1 e `Rd` e ignorado.
- **Flags afetadas:** sempre. N, Z, C e V do resultado de `Rn - operando2`.
- **Funcionamento:** calcula `Rn - operando2`, atualiza as flags e descarta o resultado.
- **Modo de enderecamento:** imediato modificado, registrador ou registrador deslocado.
- **Exemplo:** `CMP R0, R1` = `E1500001`.

### 3.7 LDR

Formato de carga e armazenamento com offset imediato:

```
 31    28 27 26 25 24 23 22 21 20 19   16 15   12 11        0
| cond  | 0  1 | I  P  U  B  W  L |  Rn   |  Rt   |  imm12    |
```

Onde `I` igual a 0 seleciona offset imediato, `P` seleciona pre-indexacao ou offset, `U` soma (1) ou subtrai (0) o offset, `B` seleciona byte (1) ou palavra (0), `W` habilita writeback e `L` igual a 1 indica carga.

- **Sintaxe:** `LDR{<c>} Rt, [Rn, #imm]`
- **Codificacao:** classe load/store, `L` igual a 1, `B` igual a 0 (palavra).
- **Flags afetadas:** nenhuma.
- **Funcionamento:** `Rt = Mem[Rn + imm]`.
- **Modo de enderecamento:** offset imediato (`P=1, W=0`). Formas pre e pos-indexadas ficam para a fase 2.
- **Exemplos:** `LDR R0, [R1]` = `E5910000`. `LDR R0, [R1, #4]` = `E5910004`.

### 3.8 STR

- **Sintaxe:** `STR{<c>} Rt, [Rn, #imm]`
- **Codificacao:** classe load/store, `L` igual a 0, `B` igual a 0 (palavra).
- **Flags afetadas:** nenhuma.
- **Funcionamento:** `Mem[Rn + imm] = Rt`.
- **Modo de enderecamento:** offset imediato. Formas pre e pos-indexadas ficam para a fase 2.
- **Exemplo:** `STR R0, [R1]` = `E5810000`.

### 3.9 B e branch condicional

Formato de desvio:

```
 31    28 27 26 25 24 23                             0
| cond  | 1  0  1 | L |             imm24            |
```

Para `B`, `L` igual a 0. O campo `cond` diferente de `1110` transforma o desvio em condicional (por exemplo `BNE` com `cond` igual a `0001`).

- **Sintaxe:** `B{<c>} <label>`
- **Codificacao:** bits 27 a 24 iguais a `1010`.
- **Flags afetadas:** nenhuma.
- **Funcionamento:** `PC = PC + SignExtend(imm24)` em palavras, lembrando que o PC lido no calculo vale endereco da instrucao mais 2 palavras (o "+8" do ARM).
- **Modo de enderecamento:** relativo ao PC, offset com sinal em palavras (alcance de ±32 MB).
- **Exemplos:** `B .` (desvio para a propria instrucao) = `EAFFFFFE`. `BNE loop` = `1AFFFFFC`.

### 3.10 Resumo dos modos de enderecamento implementados

| Modo | Onde aparece | Como e formado |
|---|---|---|
| Imediato modificado | operando 2 das instrucoes de processamento de dados (`I=1`) | `ROR(ZeroExtend(imm8), 2*rotation)` - ARMExpandImm |
| Registrador | operando 2 (`I=0`, `bit4=0`, `imm5=0`) | valor de `Rm` sem deslocamento |
| Registrador deslocado por imediato | operando 2 (`I=0`, `bit4=0`, `imm5!=0`) | `Rm` deslocado por `imm5` segundo `type` (LSL/LSR/ASR/ROR) |
| Offset imediato | LDR/STR | endereco efetivo `Rn + imm12` (`P=1, U=1, W=0`) |
| Relativo ao PC | B / Bcc | `PC(+2 palavras) + SignExtend(imm24)` |

---

## 4. Arquitetura do caminho de dados

A CPU e monociclo: cada instrucao executa em um ciclo de clock, com fetch, decodificacao, execucao e escrita acontecendo de forma combinacional dentro do mesmo ciclo. O circuito principal (`main`) instancia um subcircuito por bloco.

```
                +--------------------------------------------------------------+
                |                                                              |
                v                                                              |
   +----+   +-------+    +----+     +---------------+                          |
   | PC |-->|  ROM  |--->| IR |--+->| RegisterField |--Rn--> +---------+       |
   +----+   |(instr)|    +----+  |  |  (R0..R14+PC) |--Rm--> | Shifter |--+    |
     ^      +-------+            |  +---------------+        +---------+  |    |
     |                           |          ^                             v    |
 +--------+                      |  +-----------+   +-----------------------+  |
 | NextPC |<--PCSrc(controle)    +->| Extender  |-->|     ALU c/ flags      |--+--> RAM (dados)
 +--------+                      |  |(imediatos)|   |  (ALUw_Flags: NZCV)   |         |
   ^   ^                         |  +-----------+   +-----------------------+         v
   |   |                         |                            |                   MemtoReg
 PC+1 PC+2+imm24                 +--> ControlUnit <---NZCV----+                  (mux p/ Rd)
                                       (secao 5)
```

### 4.1 Blocos

- **PC (registrador de 24 bits) + somadores.** O PC e enderecado por palavra. Dois somadores dedicados produzem `PC+1` (fetch sequencial) e `PC+2` (base do calculo de branch, o "+8" do ARM). O subcircuito **NextPC** seleciona a proxima fonte do PC entre sequencial e alvo do desvio, governado pelo sinal `PCSrc` do controle.
- **ROM de instrucoes** (enderecos de 24 bits, palavras de 32 bits) e **IR** (registro de instrucao), que retem a palavra buscada e a expoe aos decodificadores de campo.
- **RegisterField** - banco de registradores 15+1 (R0 a R14 fisicos, PC como 16a leitura), com duas portas de leitura (`Rn`, `Rm`) e uma de escrita (`Rd`/`Rt`), habilitada por `RegWrite`.
- **Extender** - gerador de imediatos: expande `imm12` do processamento de dados (imediato modificado), `imm12` de load/store (zero-extend) e `imm24` de branch (sign-extend), selecionado por `ImmSrc`.
- **Shifter** - barrel shifter (LSL, LSR, ASR, ROR) aplicado ao segundo operando, controlado pelos campos `type` e `imm5` da instrucao.
- **ALUw_Flags** - ALU baseada em soma unica com inversao de operando e carry de entrada (AddWithCarry), mais bloco logico (AND/OR), com saidas de resultado e das quatro flags N, Z, C, V. A operacao e selecionada por `ALUControl`.
- **RAM de dados** (enderecos de 24 bits, palavras de 32 bits), lida em LDR e escrita em STR (`MemWrite`); o mux `MemtoReg` escolhe entre resultado da ALU e dado da memoria para a escrita no banco.
- **ControlUnit** - unidade de controle, detalhada na secao 5. Recebe os campos `cond`, `Op`, `Funct` e `Rd` da instrucao e as flags correntes, e produz todos os sinais de controle do caminho de dados. Contem o registrador de flags (NZCV) e o avaliador de condicao.
- **Modulo do Grupo A** (`circuitos/modulo_alu_grupoA.circ`): implementacao propria, em nivel de porta, da ALU com flags NZCV (arvore de somadores de 1, 2, 4, 8, 16 e 32 bits), do barrel shifter completo e dos geradores de imediato ARMExpandImm e SignExtend, com testbench dedicado. Este modulo valida em separado a logica aritmetica usada pela CPU.

---

## 5. Unidade de controle microprogramada

### 5.1 Visao geral

O controle microprogramado e o modulo do Grupo C (`circuitos/unidade_controle_microprogramada.circ`), composto por tres pecas, cada uma com conteudo entregue em arquivo separado:

1. **PLA de dispatch** (`microcodigo/pla_dispatch.txt`) - recebe os 8 bits de decodificacao `IR[27:20]` (`bit27 bit26 I opcode[24:21] S`) e produz o microendereco (6 bits) do microprograma correspondente na uROM. Os padroes foram preenchidos pelo Grupo D em resposta a pendencia do dossie de integracao (`documentacao/resposta_dispatch_grupoD.md`).
2. **uROM** (`microcodigo/urom.txt`) - memoria de microcodigo horizontal, 64 palavras de 30 bits. O sequenciamento usa um registrador **uPC de 6 bits**, um somador de incremento e um mux governado pelo campo `useq_sel` da propria palavra: `00` segue para uPC+1, `01` carrega o microendereco vindo da PLA de dispatch, `10` salta para o campo `next_uaddr` da palavra. O fluxo e **multiciclo**: fetch (microendereco 0) → dispatch (microendereco 1) → 1 a 3 ciclos de execucao → salto de volta ao fetch. Instrucoes de processamento de dados e branch executam em 1 ciclo; STR em 2; LDR em 3.
3. **PLA de condicao** (`microcodigo/pla_condicao.txt`) - o avaliador de condicao, secao 5.4. Dentro da unidade, `cond_pass` entra em quatro portas AND que mascaram os sinais de commit (`RegWrite`, `MemWrite`, `FlagsWrite`, `PCWrite`).

O microendereco 0 e o proprio fetch e o padrao nao casado na PLA produz saida `000000`: **qualquer instrucao fora do subconjunto volta ao fetch sem levantar nenhum sinal de escrita** (NOP seguro).

**Estado de integracao:** o `circuitos/cpu_principal.circ` entregue integra o caminho de dados com uma unidade de controle cabeada (adaptada do repositorio de partida), que ja embute o avaliador de condicao e valida o caminho de dados de ponta a ponta. A substituicao dessa unidade pela microprogramada do Grupo C e o ultimo passo de integracao, e depende de fechar os dois pontos listados no fim da secao 5.3.

### 5.2 Formato da microinstrucao (palavra de controle, 30 bits)

Layout derivado diretamente do splitter da saida da uROM no `ControlUnit.circ` (bit 0 = menos significativo):

| Bits | Campo | Funcao |
|---|---|---|
| 1:0 | `PC_src` | proxima fonte do PC: 00 = PC+4 (fetch), 01 = alvo do branch |
| 2 | `PCWrite` | escrita no PC - **mascarado por cond_pass** |
| 3 | `FlagsWrite` | escrita das flags NZCV - **mascarado por cond_pass** |
| 4 | `RegWrite` | escrita no banco de registradores - **mascarado por cond_pass** |
| 6:5 | `wb_src` | dado de writeback: 00 = saida da ALU, 01 = leitura da RAM (LDR) |
| 7 | `MemWrite` | escrita na RAM de dados - **mascarado por cond_pass** |
| 8 | `MemRead` | leitura de memoria (fetch da instrucao / leitura do LDR) |
| 10:9 | `shift_ctl` | controle do shifter no caminho do segundo operando |
| 12:11 | `ALU_srcB` | operando B: 00 = shifter, 01 = imediato, 10 = constante 4 |
| 13 | `ALU_srcA` | operando A: 0 = registrador lido, 1 = PC |
| 15:14 | `invB_cin` | inversao do operando B + carry de entrada (subtracao) |
| 19:16 | `ALU_op` | 0000 = ADD, 0010 = AND, 0011 = ORR, 0100 = passa B (MOV); SUB/CMP usam ADD com `invB_cin = 10` |
| 21:20 | `reg_read_sel` | selecao dos enderecos de leitura do banco |
| 27:22 | `next_uaddr` | microendereco de salto (usado quando `useq_sel = 10`) |
| 29:28 | `useq_sel` | sequenciamento: 00 = uPC+1, 01 = dispatch (PLA), 10 = salto para `next_uaddr` |

Exemplo de leitura: a palavra de fetch (microendereco 0, `0x00003104`) levanta `MemRead` (busca da instrucao), seleciona `ALU_srcA = PC` e `ALU_srcB = constante 4`, opera ADD e levanta `PCWrite` com `PC_src = 00` - ou seja, `IR <- Mem[PC]; PC <- PC + 4` em um ciclo.

### 5.3 Conteudo da uROM e da PLA de dispatch

Como `FlagsWrite` e `ALU_srcB` saem da uROM, variantes com e sem S e com operando imediato ou registrador precisam de palavras distintas - a PLA de dispatch enxerga os bits I e S e separa as variantes (detalhes e justificativa em `documentacao/resposta_dispatch_grupoD.md`). Mapa de microenderecos de execucao:

| Classe | reg S=0 | reg S=1 | imm S=0 | imm S=1 | Palavra base (hex) |
|---|---|---|---|---|---|
| ADD | 0x10 | 0x16 | 0x08 | 0x02 | `20000010` |
| SUB | 0x11 | 0x17 | 0x09 | 0x03 | `20008010` (`invB_cin=10`) |
| AND | 0x12 | 0x18 | 0x0A | 0x04 | `20020010` |
| ORR | 0x13 | 0x19 | 0x0B | 0x05 | `20030010` |
| MOV | 0x15 | 0x1A | 0x0C | 0x06 | `20040010` |
| CMP | - | 0x14 | - | 0x0D | `20008008` (so flags) |
| LDR | 0x20 → 0x21 → 0x22 | | | | endereco, leitura, writeback |
| STR | 0x30 → 0x31 | | | | endereco, escrita |
| B/Bcc | 0x3F | | | | `20000005` (PCWrite, PC_src=01) |

Variantes S=1 somam `FlagsWrite` (bit 3) a palavra base; variantes imediatas somam `ALU_srcB = 01` (bit 11). Todas as palavras de execucao terminam com `useq_sel = 10` e `next_uaddr` de volta ao fetch (as intermediarias de LDR/STR seguem com uPC+1).

PLA de dispatch (25 termos, entrada `IR[27:20]`, saida = microendereco de 6 bits): processamento de dados casa os 8 bits por completo (opcode + I + S); LDR/STR casam `01xxxxx1`/`01xxxxx0` (bit L) e branch casa `101xxxxx`. Os termos sao mutuamente disjuntos, verificado sobre as 256 combinacoes de entrada - necessario porque a PLA do Logisim faz OR das saidas de todos os termos casados (`testes/verifica_microcodigo.py`, verificacao [1]).

O microcodigo completo foi validado executando os cinco programas de teste P0–P4 diretamente sobre os arquivos `pla_dispatch.txt` + `urom.txt` reais (`testes/verifica_microcodigo.py`, verificacao [2]): os estados finais de registradores, flags e memoria conferem com a bateria do Grupo D nos cinco programas.

**Pontos de integracao em aberto** (detalhados em `documentacao/resposta_dispatch_grupoD.md`): (i) o `cond_pass` hoje mascara tambem o `PCWrite` do estado de fetch, o que re-executa a instrucao seguinte a uma condicao falsa - o gating deve valer so para os commits de execucao, conforme o contrato do avaliador; (ii) a semantica dos dois bits de `invB_cin` precisa ser confirmada com o Grupo A (se o carry de entrada nao acompanhar a inversao de B, toda subtracao sai com um a menos - cenario [3b] do verificador).

### 5.4 Avaliador de condicao (PLA de condicao)

O avaliador de condicao e um subcircuito proprio (`circuitos/avaliador_condicao.circ`) que implementa diretamente a tabela de codigos de condicao da secao A8.3 do manual, como uma PLA de 8 entradas (cond concatenado com NZCV) e 1 saida.

| Pino | Direcao | Largura | Significado |
|------|---------|---------|-------------|
| `cond` | entrada | 4 bits | campo de condicao, IR bits 31 a 28 |
| `NZCV` | entrada | 4 bits | flags atuais, com N no bit 3 e V no bit 0 |
| `cond_pass` | saida | 1 bit | 1 se a condicao e satisfeita |

| cond | Mnem. | cond_pass = 1 quando | cond | Mnem. | cond_pass = 1 quando |
|------|-------|----------------------|------|-------|----------------------|
| 0000 | EQ | Z = 1 | 1000 | HI | C = 1 e Z = 0 |
| 0001 | NE | Z = 0 | 1001 | LS | C = 0 ou Z = 1 |
| 0010 | CS/HS | C = 1 | 1010 | GE | N = V |
| 0011 | CC/LO | C = 0 | 1011 | LT | N != V |
| 0100 | MI | N = 1 | 1100 | GT | Z = 0 e N = V |
| 0101 | PL | N = 0 | 1101 | LE | Z = 1 ou N != V |
| 0110 | VS | V = 1 | 1110 | AL | sempre |
| 0111 | VC | V = 0 | 1111 | - | tratado como sempre |

A PLA tem 22 termos-produto (`pla_condicao.txt`), verificados por script contra as 256 combinacoes possiveis de entrada, com zero divergencias. O arquivo esta no formato de importacao do componente PLA do Logisim Evolution.

**Regra de gating (commit condicional):** `cond_pass` e uma habilitacao global de commit. Quando vale 0, a instrucao vira NOP: aplica-se como AND apenas sobre os sinais de escrita - `RegWrite`, `MemWrite`, `FlagsWrite` e o `PCWrite` condicional do branch. O sinal nunca entra no incremento normal do PC nem no fetch: o processador continua avancando normalmente quando a condicao falha. O teste P3 da bateria prova esse comportamento (ADDEQ comita, ADDNE vira NOP).

---

## 6. Testes - assembly, binario e resultados

A bateria completa esta em `testes/bateria_testes.md`, com uma imagem de ROM pronta por programa (`testes/rom_p0.txt` a `rom_p4.txt`, formato v2.0 raw). Convencoes: reset zera registradores e memoria; cada programa termina em `B fim` (desvio para si mesmo), entao o processador estaciona; flags na ordem N Z C V.

Validacoes automatizadas ja executadas (todas reproduziveis por linha de comando):

| Verificacao | Ferramenta | Resultado |
|---|---|---|
| Estados finais esperados de P0–P4 (ISA de referencia) | `simulador_subconjunto.py`, executa os proprios `rom_pX.txt` | 5/5 OK |
| Avaliador de condicao no circuito real | Logisim Evolution headless, `--test-vector AvaliadorCondicao testes/vetores_avaliador_condicao.txt circuitos/avaliador_condicao.circ` | 30/30 passam |
| PLA de condicao contra a tabela A8-1 | `verifica_pla_condicao.py`, 256 combinacoes exaustivas | 0 divergencias |
| Microcodigo do Grupo C (`pla_dispatch.txt` + `urom.txt`) executando P0–P4 | `testes/verifica_microcodigo.py` | 5/5 OK, 0 sobreposicoes na PLA |

Falta apenas a validacao visual de ponta a ponta no Logisim (GUI), que preenche a coluna "observado" da bateria: o circuito principal nao tem pinos de saida, entao registradores e RAM sao conferidos na interface.

**Procedimento de execucao:** abrir `circuitos/cpu_principal.circ` no Logisim Evolution → clique direito na ROM de instrucoes → *Load Image* → `rom_pX.txt` → *Simulate > Reset Simulation* → habilitar o clock automatico (Ctrl+K) ate o PC estacionar → conferir registradores, flags e RAM.

| # | Programa | Instrucoes exercitadas | Resultado-chave esperado |
|---|----------|------------------------|--------------------------|
| P0 | Laco com shift (programa embarcado na ROM) | MOV imm, ADD reg, MOV com LSL, SUBS, BNE | R5 = 22 iteracoes, R3 = 0, Z=1 C=1 |
| P1 | Soma de 1 a 5 com laco | MOV, ADD, SUBS, BNE, B | R0 = 15 |
| P2 | Aritmetica e logica sem desvio | MOV, ADD, SUB, AND, ORR, CMP | R2=22, R3=2, R4=8, R5=14, C=1 |
| P3 | Execucao condicional (prova do cond_pass) | CMP, ADDEQ, ADDNE | R2=8 escrito, R3 permanece 0 |
| P4 | Load e store (ida e volta na memoria) | MOV, STR, LDR com e sem offset | Mem[0x40]=Mem[0x44]=0xAB, R5=R6=0xAB |

*(As tabelas completas de estado final esperado/observado, instrucao por instrucao, estao na bateria; a coluna "observado" e preenchida na sessao de validacao no Logisim.)*

---

## 7. Responsabilidades de cada aluno

| Grupo | Alunos | Modulos e entregaveis sob responsabilidade |
|-------|--------|--------------------------------------------|
| A | Vitor Oli e Renan | Caminho de dados aritmetico e logico: ALU baseada em AddWithCarry com bloco logico, registrador de flags NZCV, barrel shifter, geradores de imediato (ARMExpandImm, ZeroExtend, SignExtend). |
| B | Thiago Paiva e Sofia | Montagem e integracao do circuito: adaptacao dos subcircuitos do repositorio de partida, PC + somadores + logica de desvio (NextPC) + IR, integracao de nivel superior e organizacao modular do arquivo.  |
| C | Thiago e Vitor Riguette | Unidade de controle microprogramada: formato da microinstrucao, uROM com o microcodigo, PLA de dispatch, integracao do avaliador de condicao na logica de commit, exportacao dos conteudos em arquivos separados.|
| D | Yan e Silvio | Busca e avaliação de conteúdos e referências técnicas, montagem do plano de ação para execução do processador em partes,Avaliador de condicao como subcircuito proprio (PLA), documentacao do modelo de programacao e das fichas de instrucao, bateria de testes em assembly e binario com esperado vs. observado, diagrama de blocos e consolidacao do relatorio. |
| Todos | - | Decisoes de arquitetura (secao 2.3), validacao dos testes e revisao final. |

---

## 8. Referencias

- *ARM Architecture Reference Manual - ARMv7-A and ARMv7-R edition*, ARM DDI 0406C.c (ID051414). Secoes A2 (modelo de programacao), A5 (decodificacao), A8 (instrucoes e codigos de condicao).
- Referencia ARMv7 destilada do manual, anexada ao projeto (`documentacao/referencia_armv7.md`).
- Harris, D.; Harris, S. *Digital Design and Computer Architecture - ARM Edition*. (arquitetura monociclo ARM de referencia da unidade de controle)
- Logisim Evolution (componente PLA nativo): https://github.com/logisim-evolution/logisim-evolution
