# Referência ARMv7‑A para projeto de CPU no Logisim (controle microprogramado)
 
> **Para que serve este documento.** Base de conhecimento destilada do *ARM Architecture
> Reference Manual — ARMv7‑A and ARMv7‑R edition* (ARM DDI 0406C.c, ID051414), contendo
> **apenas** o que é necessário para: (1) projetar um subconjunto do processador ARMv7‑A,
> (2) documentar cada instrução (campos, flags, opcode, funcionamento, modo de
> endereçamento), (3) construir o datapath modular no Logisim com **uROM (microcódigo)** e
> **PLAs** separadas, e (4) escrever códigos de teste em assembly e seu binário.
 
---
 
## 0. Convenções
 
- Todas as instruções ARM têm **largura fixa de 32 bits** e são **alinhadas em palavra**.
- Notação de bits: `bits[31:0]`, bit 31 é o mais significativo (MSB).
- Em diagramas de codificação: `(0)`/`(1)` = bit que *deve* ser 0/1 (caso contrário
  UNPREDICTABLE); `x` = bit livre; `SBZ`/`SBZP` = should be zero (/preserved); `RAZ` = read‑as‑zero.
- `UInt(x)` = valor sem sinal; `SInt(x)` = valor em complemento de 2; `:` = concatenação de bits.
- Sufixo `{S}` na mnemônica = a instrução atualiza as flags (bit `S`, bit[20]).
- Sufixo `<c>` = código de condição (campo `cond`, bits[31:28]); ausência ⇒ `AL` (sempre).
---
 
## 1. Modelo de programação (A2)
 
### 1.1 Registradores do núcleo (A2.3)
 
No nível de aplicação o processador tem **16 registradores de 32 bits** visíveis, `R0`–`R15`:
 
| Reg | Nome | Função |
|-----|------|--------|
| R0–R12 | — | 13 registradores de uso geral |
| R13 | **SP** | Stack Pointer (ponteiro de pilha) |
| R14 | **LR** | Link Register (endereço de retorno em chamadas) |
| R15 | **PC** | Program Counter |
 
**Especificador de registrador = 4 bits.** `0b1111` (15) = PC; `0b1101` (13) = SP.
 
**Semântica crítica do PC (A2.3) — atenção no datapath:**
- **Ao *ler* o PC em estado ARM, o valor é o endereço da instrução corrente + 8.**
  (Reflete o pipeline clássico de 3 estágios: fetch/decode/execute.) No Logisim isto
  precisa ser modelado quando o PC participa de um cálculo (ex.: `ADD Rd, PC, ...`,
  endereçamento literal). Para um pipeline simplificado/monociclo, decida e **documente**
  se você implementa o "+8" ou simplifica para "+4"/"+0" — é uma diferença em relação a
  implementações de referência.
- **Escrever um endereço no PC causa um desvio** para aquele endereço.
- `ALUWritePC()` (ARMv7, estado ARM) faz desvio de interworking via `BXWritePC()`;
  `BranchWritePC()` força alinhamento de palavra (`address<31:2>:'00'`).
### 1.2 APSR / CPSR e flags de condição (A2.4)
 
A `APSR` (Application Program Status Register) é, em ARMv7‑A/R, **o mesmo registrador** que
a `CPSR`, mas no nível de aplicação só se acessam os bits N, Z, C, V, Q, GE.
 
```
 31 30 29 28 27 26..24 23..20 19..16 15...............0
  N  Z  C  V  Q  RAZ    Reserv  GE3:0  Reserv UNKNOWN/SBZP
```
 
| Bit | Flag | Significado | Como é setado |
|-----|------|-------------|---------------|
| 31 | **N** | Negative | recebe `result<31>`; 1 se resultado (com sinal) é negativo |
| 30 | **Z** | Zero | 1 se `result == 0` |
| 29 | **C** | Carry | carry/borrow de operações aritméticas; saída do shifter em ops lógicas |
| 28 | **V** | Overflow | overflow com sinal em soma/subtração |
| 27 | Q | Saturation | saturação/overflow em instruções DSP (fora do escopo típico) |
| 19:16 | GE[3:0] | Greater‑or‑Equal | usado por SIMD paralelo (fora do escopo) |
 
> Para o projeto, o registrador de flags ("flags register") precisa armazenar **N, Z, C, V**.
> Só são atualizadas quando a instrução tem `S=1` (ou é uma comparação CMP/CMN/TST/TEQ,
> que têm `S` implicitamente 1).
 
---
 
## 2. Formato e decodificação da instrução ARM (A5)
 
### 2.1 Formato geral (A5.1)
 
```
 31 30 29 28 27 26 25 24 ... 5 4 3 2 1 0
   cond       op1                  op
```
 
Todas as instruções (exceto `cond == 0b1111`, que são "incondicionais") usam os bits
[31:28] como **código de condição**.
 
### 2.2 Mapa mestre de decodificação — Tabela A5‑1
 
Subdivisão principal por `bits[27:25]` (op1) e `bit[4]` (op):
 
| cond | op1 (bits 27:25) | op (bit 4) | Classe de instrução |
|------|------------------|------------|---------------------|
| ≠1111 | `00x` | – | **Data‑processing e diversos** (§3.1) |
| ≠1111 | `010` | – | **Load/store word e unsigned byte** (§3.2) |
| ≠1111 | `011` | `0` | **Load/store word e unsigned byte** (§3.2) |
| ≠1111 | `011` | `1` | Media instructions (fora do escopo) |
| ≠1111 | `10x` | – | **Branch, branch‑with‑link e block data transfer** (§3.3/§3.4) |
| ≠1111 | `11x` | – | Coprocessador e Supervisor Call (fora do escopo) |
| `1111` | – | – | Instruções incondicionais (fora do escopo) |
 
> **Esta tabela é a base da PLA de decodificação principal.** A partir de `bit25` e `bit4`
> você separa as grandes classes; dentro de cada classe há sub‑tabelas (abaixo) que viram
> termos adicionais da(s) PLA(s).
 
### 2.3 Tabela de códigos de condição — Tabela A8‑1 (A8.3)
 
Esta é a **PLA/lógica de avaliação de condição**: dado `cond` e as flags NZCV, decide se a
instrução executa.
 
| cond | Mnem. | Significado | Condição sobre flags |
|------|-------|-------------|----------------------|
| 0000 | EQ | Equal | `Z == 1` |
| 0001 | NE | Not equal | `Z == 0` |
| 0010 | CS/HS | Carry set / unsigned ≥ | `C == 1` |
| 0011 | CC/LO | Carry clear / unsigned < | `C == 0` |
| 0100 | MI | Minus / negative | `N == 1` |
| 0101 | PL | Plus / positive or zero | `N == 0` |
| 0110 | VS | Overflow | `V == 1` |
| 0111 | VC | No overflow | `V == 0` |
| 1000 | HI | Unsigned higher | `C == 1 and Z == 0` |
| 1001 | LS | Unsigned lower or same | `C == 0 or Z == 1` |
| 1010 | GE | Signed ≥ | `N == V` |
| 1011 | LT | Signed < | `N != V` |
| 1100 | GT | Signed > | `Z == 0 and N == V` |
| 1101 | LE | Signed ≤ | `Z == 1 or N != V` |
| 1110 | AL (ou nenhuma) | Always | qualquer (sempre executa) |
| 1111 | — | (instrução incondicional; trate como AL ou trate fora do escopo) | — |
 
Pseudocódigo `ConditionPassed()`: avalia a tabela acima sobre `APSR.{N,Z,C,V}`.
 
---
 
## 3. Classes de instrução e codificações
 
### 3.1 Data‑processing e diversos (A5.2)
 
Existem **três formatos** que diferem apenas em como o 2º operando (`Operand2`) é formado.
Todos compartilham o campo **opcode (bits[24:21], 4 bits)** + bit **S (bit[20])**.
 
**(a) Data‑processing (register)** — `Operand2` = `Rm` com shift por imediato:
```
 31..28 27 26 25 24..21 20 19..16 15..12 11.....7 6 5 4 3..0
  cond   0  0  0  opcode  S   Rn     Rd    imm5   type 0  Rm
```
**(b) Data‑processing (register‑shifted register)** — `Operand2` = `Rm` com shift por `Rs`:
```
 31..28 27 26 25 24..21 20 19..16 15..12 11..8 7 6 5 4 3..0
  cond   0  0  0  opcode  S   Rn     Rd    Rs   0 type 1  Rm
```
**(c) Data‑processing (immediate)** — `Operand2` = imediato modificado de 12 bits:
```
 31..28 27 26 25 24..21 20 19..16 15..12 11........0
  cond   0  0  1  opcode  S   Rn     Rd      imm12
```
 
Distinção dos três pelo trio `(bit25, bit7, bit4)`:
- `bit25 = 1` → **immediate** (c).
- `bit25 = 0` e `bit4 = 0` → **register** (a) (shift por imm5).
- `bit25 = 0`, `bit7 = 0`, `bit4 = 1` → **register‑shifted register** (b).
#### Tabela de opcodes (bits[24:21]) — Tabela A5‑3 / A5‑5
 
| opcode | Mnem. | Operação | Flags (com S) | Observação |
|--------|-------|----------|----------------|------------|
| 0000 | **AND** | `Rd = Rn AND Op2` | N Z C(shift) | lógica |
| 0001 | **EOR** | `Rd = Rn XOR Op2` | N Z C(shift) | lógica |
| 0010 | **SUB** | `Rd = Rn − Op2` | N Z C V | aritmética |
| 0011 | **RSB** | `Rd = Op2 − Rn` | N Z C V | subtração reversa |
| 0100 | **ADD** | `Rd = Rn + Op2` | N Z C V | aritmética |
| 0101 | **ADC** | `Rd = Rn + Op2 + C` | N Z C V | add com carry |
| 0110 | **SBC** | `Rd = Rn − Op2 − ¬C` | N Z C V | sub com carry |
| 0111 | **RSC** | `Rd = Op2 − Rn − ¬C` | N Z C V | sub reversa com carry |
| 1000 (S=1) | **TST** | `Rn AND Op2` (descarta) | N Z C(shift) | só flags |
| 1001 (S=1) | **TEQ** | `Rn XOR Op2` (descarta) | N Z C(shift) | só flags |
| 1010 (S=1) | **CMP** | `Rn − Op2` (descarta) | N Z C V | só flags |
| 1011 (S=1) | **CMN** | `Rn + Op2` (descarta) | N Z C V | só flags |
| 1100 | **ORR** | `Rd = Rn OR Op2` | N Z C(shift) | lógica |
| 1101 | **MOV** | `Rd = Op2` (Rn ignorado/SBZ) | N Z C(shift) | move |
| 1110 | **BIC** | `Rd = Rn AND NOT Op2` | N Z C(shift) | bit clear |
| 1111 | **MVN** | `Rd = NOT Op2` (Rn SBZ) | N Z C(shift) | NOT |
 
Notas:
- **TST/TEQ/CMP/CMN** têm `opcode10xx` com `S=1` obrigatório e **não escrevem `Rd`**
  (campo `Rd` é SBZ). São as "comparações".
- **C nas operações lógicas** (AND/EOR/ORR/BIC/MOV/MVN/TST/TEQ) é a **saída do shifter**
  (`shifter_carry_out`), não um carry aritmético. V é **inalterada** nessas.
- **MOV/MVN** ignoram `Rn` (bits[19:16] = 0).
- Os **shifts** (LSL/LSR/ASR/ROR/RRX) são, na arquitetura, **codificados como MOV** com
  `opcode = 1101` e o campo `type`/`imm5` (ou `Rs`) indicando o shift (ver §3.1.3).
#### 3.1.1 Operand2 — modos de endereçamento do 2º operando (shifter operand)
 
Estes são os "modos de endereçamento" das instruções de processamento de dados:
 
1. **Imediato (modified immediate)** — `bit25 = 1`. Campo `imm12 = rotation(4) : imm8(8)`.
   O valor de 32 bits é `ROR(ZeroExtend(imm8), 2*rotation)`. Ver §4.3 (`ARMExpandImm`).
2. **Registrador com shift imediato** — `bit25 = 0`, `bit4 = 0`. `Rm` deslocado por `imm5`
   segundo `type` (00=LSL,01=LSR,10=ASR,11=ROR/RRX). Ver §4.2 (`DecodeImmShift`).
3. **Registrador com shift por registrador** — `bit25=0`, `bit7=0`, `bit4=1`. `Rm` deslocado
   pelo byte baixo de `Rs`, tipo dado por `type`.
#### 3.1.2 Decodificação do tipo de shift — campo `type` (bits[6:5])
 
| type | Shift | n=0 (imm5=00000) | Carry‑out |
|------|-------|------------------|-----------|
| 00 | **LSL** | sem shift (n=0) | C inalterado se n=0 |
| 01 | **LSR** | n=32 | último bit deslocado p/ fora |
| 10 | **ASR** | n=32 | último bit deslocado p/ fora |
| 11 | **ROR** (n≠0) / **RRX** (n=0) | RRX (n=1, entra C em bit31) | bit deslocado / bit0 |
 
`DecodeImmShift(type, imm5)` (pseudocódigo A8.4.3):
```
00 -> LSL, n = UInt(imm5)
01 -> LSR, n = (imm5==0 ? 32 : UInt(imm5))
10 -> ASR, n = (imm5==0 ? 32 : UInt(imm5))
11 -> imm5==0 ? (RRX, n=1) : (ROR, n=UInt(imm5))
```
 
#### 3.1.3 Sub‑codificação MOV/shift (Tabela A5‑3, opcode 1101x)
 
Quando `opcode=1101` (MOV) na forma *register*:
| op2 (type) | imm5 | Instrução |
|------------|------|-----------|
| 00 | 00000 | **MOV** (register) |
| 00 | ≠00000 | **LSL** (immediate) |
| 01 | – | **LSR** (immediate) |
| 10 | – | **ASR** (immediate) |
| 11 | 00000 | **RRX** |
| 11 | ≠00000 | **ROR** (immediate) |
 
Na forma *register‑shifted register* (`opcode=1101`): `00`→LSL(reg), `01`→LSR(reg),
`10`→ASR(reg), `11`→ROR(reg).
 
### 3.2 Load/store word e unsigned byte (A5.3)
 
Formato (Tabela A5‑15). `A` = bit25; `B` = bit4; campo de controle `P U b W L` em
bits[24:20], com `b` (bit22) = byte:
```
 31..28 27 26 25 24 23 22 21 20 19..16 15..12 11.........0/4..0
  cond   0  1  A  P  U  b  W  L   Rn     Rt      offset
```
- `bit25 (A) = 0` → offset **imediato** (12 bits em `imm12`).
- `bit25 (A) = 1` e `bit4 = 0` → offset por **registrador** `Rm` com shift `imm5/type`.
- `L (bit20) = 1` → **Load**; `L = 0` → **Store**.
- `b (bit22) = 1` → **byte** (LDRB/STRB); `b = 0` → **word** (LDR/STR).
**Codificações exatas (Encoding A1):**
 
| Instrução | bits[27:25] | bits[24:20] = P U b W L | resto |
|-----------|-------------|--------------------------|-------|
| **STR** (imm) | `010` | `P U 0 W 0` | Rn, Rt, imm12 |
| **LDR** (imm) | `010` | `P U 0 W 1` | Rn, Rt, imm12 |
| **STRB** (imm) | `010` | `P U 1 W 0` | Rn, Rt, imm12 |
| **LDRB** (imm) | `010` | `P U 1 W 1` | Rn, Rt, imm12 |
| **STR** (reg) | `011` | `P U 0 W 0` | Rn, Rt, imm5, type, 0, Rm |
| **LDR** (reg) | `011` | `P U 0 W 1` | Rn, Rt, imm5, type, 0, Rm |
| **STRB** (reg) | `011` | `P U 1 W 0` | Rn, Rt, imm5, type, 0, Rm |
| **LDRB** (reg) | `011` | `P U 1 W 1` | Rn, Rt, imm5, type, 0, Rm |
 
#### 3.2.1 Modos de endereçamento de memória (bits P, U, W)
 
São **o coração dos "modos de endereçamento"** de load/store. Significado dos bits:
- `U (bit23)`: `1` = somar offset (`+`), `0` = subtrair (`−`).
- `P (bit24)` (index) e `W (bit21)` (writeback) combinam em três modos:
| P | W | Modo | Endereço efetivo | Writeback em Rn | Sintaxe |
|---|---|------|------------------|------------------|---------|
| 1 | 0 | **Offset** | `Rn ± offset` | não | `[Rn, #±off]` |
| 1 | 1 | **Pré‑indexado** | `Rn ± offset` | sim (`Rn = Rn ± offset`) | `[Rn, #±off]!` |
| 0 | 0 | **Pós‑indexado** | `Rn` | sim (`Rn = Rn ± offset`) | `[Rn], #±off` |
 
Pseudocódigo comum:
```
index  = (P == 1);    add = (U == 1);    wback = (P == 0) || (W == 1);
offset_addr = add ? (Rn + offset) : (Rn - offset);
address     = index ? offset_addr : Rn;
data = Mem[address];      // load:  Rt = data    | store: Mem[address] = Rt
if wback then Rn = offset_addr;
```
> `offset` é `imm12` (forma imediata) ou `Shift(Rm, type, imm5)` (forma registrador).
> Para um subconjunto didático, é comum implementar primeiro só o **modo offset com
> imediato** (`P=1,W=0`) e depois pré/pós‑indexado.
 
### 3.3 Block data transfer — Load/Store Multiple (A5.5)
 
Formato compartilhado com branch (bits[27:26] = `10`). Para LDM/STM, `bit25 = 0`:
```
 31..28 27 26 25 24 23 22 21 20 19..16 15...............0
  cond   1  0  0  P  U  S  W  L   Rn      register_list
```
- `L (bit20)`: `1` = Load Multiple (LDM), `0` = Store Multiple (STM).
- `P,U` definem a direção/ordem (modos IA/IB/DA/DB):
| P | U | Modo | Mnemônico | Stack alias |
|---|---|------|-----------|-------------|
| 0 | 1 | Increment After | **LDMIA/STMIA** | LDMFD/STMEA |
| 1 | 1 | Increment Before | LDMIB/STMIB | LDMED/STMFA |
| 0 | 0 | Decrement After | LDMDA/STMDA | LDMFA/STMED |
| 1 | 0 | Decrement Before | **LDMDB/STMDB** | LDMEA/STMFD |
 
- `W (bit21)` = writeback no `Rn`.
- `register_list` (bits[15:0]): bitmap; bit *i* setado ⇒ `Ri` é transferido.
**Codificações exatas:**
 
| Instrução | bits[27:20] | resto |
|-----------|-------------|-------|
| **STMIA** (STM) | `1000 10 W0` → `cond 100010W0` | Rn, register_list |
| **LDMIA** (LDM) | `cond 100010W1` | Rn, register_list |
| **STMDB** | `cond 100100W0` | Rn, register_list |
| **LDMDB** | `cond 100100W1` | Rn, register_list |
| **PUSH** `<regs>` | `cond 100100101101` | register_list (= `STMDB SP!`) |
| **POP** `<regs>` | `cond 100010111101` | register_list (= `LDMIA SP!`) |
 
> `PUSH = STMDB SP!, <regs>` e `POP = LDMIA SP!, <regs>` (pilha *full‑descending*,
> convenção AAPCS). São apenas casos especiais com `Rn=SP(1101)` e `W=1`.
 
### 3.4 Branch (A5.5)
 
```
 31..28 27 26 25 24 23..............................0
  cond   1  0  1  H              imm24
```
- **B** (`bit24 = 0`): `cond 1010 imm24`. Desvio relativo.
- **BL** (`bit24 = 1`): `cond 1011 imm24`. Branch‑with‑Link (salva retorno em LR).
- Offset: `imm32 = SignExtend(imm24 : '00', 32)`. Alvo = `BranchWritePC(PC + imm32)`,
  onde `PC` = endereço da instrução + 8 (ver §1.1). ⇒ **alcance ±32 MB**.
**BX** (troca de estado/desvio por registrador) — codificação especial em A5.2:
```
 31..28 27.....................4 3..0
  cond   0001 0010 (1)x12 0001    Rm     =  cond 0001 0010 1111 1111 1111 0001 Rm
```
Operação: `BXWritePC(R[m])` — desvia para o endereço em `Rm` (e trocaria para Thumb se
`Rm<0>=1`; num subconjunto só‑ARM, ignore o bit de estado). Usado para retorno: `BX LR`.
 
---
 
## 4. Pseudocódigo de apoio (semântica para o datapath/ALU)
 
### 4.1 Soma com carry e overflow — `AddWithCarry` (A2.2.1)
 
```
(result, carry_out, overflow) = AddWithCarry(x, y, carry_in):
    unsigned_sum = UInt(x) + UInt(y) + UInt(carry_in)
    signed_sum   = SInt(x) + SInt(y) + UInt(carry_in)
    result    = unsigned_sum<31:0>
    carry_out = (UInt(result) == unsigned_sum) ? 0 : 1
    overflow  = (SInt(result) == signed_sum)   ? 0 : 1
```
**Subtração via complemento de 2 (propriedade‑chave):** `x − y` é
`AddWithCarry(x, NOT(y), 1)`. Logo a ALU faz **uma única soma**; para subtração ela inverte
o 2º operando e injeta `carry_in = 1`. As flags caem naturalmente:
- `ADD`: `AddWithCarry(Rn, Op2, 0)`
- `ADC`: `AddWithCarry(Rn, Op2, C)`
- `SUB`/`CMP`: `AddWithCarry(Rn, NOT Op2, 1)`
- `SBC`: `AddWithCarry(Rn, NOT Op2, C)`
- `RSB`: `AddWithCarry(NOT Rn, Op2, 1)`
- `RSC`: `AddWithCarry(NOT Rn, Op2, C)`
Atualização de flags (quando `S=1`): `N = result<31]; Z = (result==0); C = carry_out;
V = overflow`. Em operações **lógicas**, `C = shifter_carry_out` e `V` não muda.
 
### 4.2 Shift/rotate — `Shift_C` (A8.4.3)
 
```
Shift_C(value, type, amount, carry_in):
  se amount==0: (value, carry_in)
  LSL: result = value << amount;  carry_out = value<32-amount>   (bit que "saiu")
  LSR: result = value >> amount;  carry_out = value<amount-1>
  ASR: result = value >>signed amount; carry_out = value<amount-1>
  ROR: result = rotate_right(value, amount mod 32); carry_out = result<31>
  RRX: result = (carry_in : value<31:1>); carry_out = value<0>   (amount sempre 1)
```
 
### 4.3 Imediato modificado — `ARMExpandImm` (A5.2.4)
 
```
ARMExpandImm(imm12):                    // imm12 = rotation(bits 11:8) : imm8(bits 7:0)
    unrotated = ZeroExtend(imm12<7:0>, 32)
    (imm32, carry) = Shift_C(unrotated, ROR, 2*UInt(imm12<11:8>), APSR.C)
    return imm32
```
- O imediato de 8 bits é rotacionado à direita por **2×rotation** (rotation ∈ 0..15 ⇒ shift
  par 0..30). Permite constantes como `0xFF000000`, `0x3F0`, etc.
- **Carry‑out**: se `rotation == 0`, `C` é inalterado; senão `C = imm32<31>` (relevante só
  para instruções lógicas com `S`).
- Constante com múltiplas codificações ⇒ usar a de menor `rotation`. Faixa 0–255 sempre
  com `rotation = 0`.
---
 
## 5. Referência por instrução (subconjunto recomendado)
 
Formato de cada entrada: **mnemônica / sintaxe / codificação de 32 bits / opcode / flags /
funcionamento / modo de endereçamento**. Bits livres marcados com nome do campo.
 
### 5.1 Processamento de dados (todas compartilham layout — ver §3.1)
 
> Para TODAS abaixo: `cond[31:28]`, `S[20]`, `Rn[19:16]`, `Rd[15:12]`. O que muda é
> `opcode[24:21]` e a forma de `Operand2` (`bit25`, campos baixos).
> **Modo de endereçamento** = imediato (`bit25=1`) | registrador (`bit25=0,bit4=0`) |
> registrador‑deslocado‑por‑registrador (`bit25=0,bit7=0,bit4=1`).
 
| Mnem. | opcode | Função | Flags afetadas (se S) | Escreve Rd? |
|-------|--------|--------|------------------------|-------------|
| AND | 0000 | `Rd = Rn & Op2` | N Z C(sh) | sim |
| EOR | 0001 | `Rd = Rn ^ Op2` | N Z C(sh) | sim |
| SUB | 0010 | `Rd = Rn − Op2` | N Z C V | sim |
| RSB | 0011 | `Rd = Op2 − Rn` | N Z C V | sim |
| ADD | 0100 | `Rd = Rn + Op2` | N Z C V | sim |
| ADC | 0101 | `Rd = Rn + Op2 + C` | N Z C V | sim |
| SBC | 0110 | `Rd = Rn − Op2 − ¬C` | N Z C V | sim |
| RSC | 0111 | `Rd = Op2 − Rn − ¬C` | N Z C V | sim |
| TST | 1000 | `Rn & Op2` | N Z C(sh) | não (S=1 fixo) |
| TEQ | 1001 | `Rn ^ Op2` | N Z C(sh) | não (S=1 fixo) |
| CMP | 1010 | `Rn − Op2` | N Z C V | não (S=1 fixo) |
| CMN | 1011 | `Rn + Op2` | N Z C V | não (S=1 fixo) |
| ORR | 1100 | `Rd = Rn \| Op2` | N Z C(sh) | sim |
| MOV | 1101 | `Rd = Op2` | N Z C(sh) | sim (Rn=0) |
| BIC | 1110 | `Rd = Rn & ~Op2` | N Z C(sh) | sim |
| MVN | 1111 | `Rd = ~Op2` | N Z C(sh) | sim (Rn=0) |
 
**Exemplo de campo‑a‑campo (ADD register, A8‑312):**
```
cond | 0 0 0 | 0100 | S | Rn | Rd | imm5 | type | 0 | Rm
```
Operação: `shifted = Shift(Rm, type, imm5, C); (result,C,V)=AddWithCarry(Rn, shifted, 0); Rd=result`.
 
**Shifts como MOV (A8‑468/472/330/568/572):** `LSL Rd, Rm, #n` = `MOV` com `type=00,imm5=n`;
`LSR`→`type=01`; `ASR`→`type=10`; `ROR`→`type=11,imm5≠0`; `RRX`→`type=11,imm5=0`.
Formas por registrador (`LSL Rd, Rm, Rs`) usam o layout register‑shifted (`bit4=1`).
 
### 5.2 MOV imediato de 16 bits e MOVT (carregar constantes de 32 bits)
 
**MOVW / MOV (immediate 16‑bit)** — A8‑484, variante v6T2:
```
cond | 0 0 1 1 0 0 0 0 | imm4 | Rd | imm12        (opcode field = 10000, bit25=1)
Rd = ZeroExtend(imm4:imm12, 32)        // 16 bits, zera a metade alta
```
**MOVT** — A8‑491:
```
cond | 0 0 1 1 0 1 0 0 | imm4 | Rd | imm12
Rd<31:16> = imm4:imm12   (Rd<15:0> inalterado)   // carrega metade alta
```
> Padrão para carregar um literal de 32 bits: `MOVW Rd,#low16` seguido de `MOVT Rd,#high16`.
> Não afetam flags.
 
### 5.3 Multiplicação
 
**MUL** — A8‑502:
```
cond | 0 0 0 0 0 0 0 | S | Rd | (0000) | Rm | 1 0 0 1 | Rn
Rd = (Rn * Rm)<31:0>      Flags(se S): N=res<31>, Z=(res==0); C,V inalterados
```
**MLA** — A8‑480: `Rd = (Rn*Rm + Ra)<31:0>`; layout
`cond 0000001S Rd Ra Rm 1001 Rn`. **MLS** — A8‑482: `Rd = Ra − Rn*Rm`,
`cond 00000110 Rd Ra Rm 1001 Rn`.
> Atenção: nas multiply, os campos `Rd/Rn/Rm` ficam em **posições diferentes** das
> data‑processing (Rd em [19:16], Rn em [3:0], Rm em [11:8]), e os bits[7:4]=`1001`.
 
### 5.4 Load/Store de palavra e byte (ver §3.2)
 
| Mnem. | Sintaxe (offset) | bits[27:20] | offset |
|-------|------------------|-------------|--------|
| **LDR** (imm) | `LDR Rt,[Rn,#±imm12]` | `010 P U 0 W 1` | imm12 |
| **STR** (imm) | `STR Rt,[Rn,#±imm12]` | `010 P U 0 W 0` | imm12 |
| **LDRB** (imm) | `LDRB Rt,[Rn,#±imm12]` | `010 P U 1 W 1` | imm12 |
| **STRB** (imm) | `STRB Rt,[Rn,#±imm12]` | `010 P U 1 W 0` | imm12 |
| **LDR** (reg) | `LDR Rt,[Rn,±Rm{,sh}]` | `011 P U 0 W 1` | imm5,type,0,Rm |
| **STR** (reg) | `STR Rt,[Rn,±Rm{,sh}]` | `011 P U 0 W 0` | imm5,type,0,Rm |
 
Campos: `Rn[19:16]` base, `Rt[15:12]` dado. Operação e modos: §3.2/§3.2.1.
LDR/STR não afetam flags. (Se `Rt = PC` num LDR ⇒ desvio; trate como opcional no subconjunto.)
 
### 5.5 Load/Store Multiple, PUSH, POP (ver §3.3)
 
| Mnem. | Sintaxe | bits[27:20] | lista |
|-------|---------|-------------|-------|
| **LDMIA/LDM** | `LDM Rn{!},{regs}` | `100 0 1 0 W 1` | register_list |
| **STMIA/STM** | `STM Rn{!},{regs}` | `100 0 1 0 W 0` | register_list |
| **LDMDB** | `LDMDB Rn{!},{regs}` | `100 1 0 0 W 1` | register_list |
| **STMDB** | `STMDB Rn{!},{regs}` | `100 1 0 0 W 0` | register_list |
| **PUSH** | `PUSH {regs}` | `1001 0010 1101` | register_list |
| **POP** | `POP {regs}` | `1000 1011 1101` | register_list |
 
Não afetam flags (exceto formas com PC/exceção, fora do escopo).
 
### 5.6 Branch
 
| Mnem. | Sintaxe | Codificação | Função |
|-------|---------|-------------|--------|
| **B** | `B <label>` | `cond 1010 imm24` | `PC = PC + SignExtend(imm24:00)` |
| **BL** | `BL <label>` | `cond 1011 imm24` | `LR = retorno; PC = PC + offset` |
| **BX** | `BX Rm` | `cond 00010010 1111 1111 1111 0001 Rm` | `PC = Rm` |
 
Não afetam flags.
 
---
 
## 6. Codificação de campos comuns
 
- **Registrador** (`Rd`, `Rn`, `Rm`, `Rt`, `Rs`): 4 bits, `0000`=R0 … `1111`=R15(PC),
  `1101`=R13(SP), `1110`=R14(LR).
- **register_list** (LDM/STM/PUSH/POP): 16 bits, bit *i* ⇒ inclui `Ri`. Ex.: `{R0,R1,R4,LR}`
  = `0100 0000 0001 0011` = `0x4013`.
- **imm12 (data‑proc)**: `rotation[11:8] : imm8[7:0]` (imediato modificado).
- **imm12 (load/store)**: offset sem sinal de 12 bits (0–4095); sinal vem do bit `U`.
- **imm24 (branch)**: deslocamento com sinal × 4.
---
 
## 7. Códigos de teste — assembly + binário
 
> Hex de 32 bits, big‑endian de exibição (palavra). Todos `cond = AL = 1110`. Verificados
> à mão pela codificação acima. Em Logisim, carregue na ROM de instruções como words.
 
### 7.1 Instruções isoladas (smoke tests)
 
| Assembly | Binário (bits) | Hex |
|----------|----------------|-----|
| `MOV R0, #0` | `1110 0011 1010 0000 0000 0000 0000 0000` | `E3A00000` |
| `MOV R1, #5` | `1110 0011 1010 0001 0001 0000 0000 0101` | `E3A01005` |
| `ADD R0, R1, R2` | `1110 0000 1000 0001 0000 0000 0000 0010` | `E0810002` |
| `ADDS R0, R1, R2` | `1110 0000 1001 0001 0000 0000 0000 0010` | `E0910002` |
| `SUB R3, R3, #1` | `1110 0010 0100 0011 0011 0000 0000 0001` | `E2433001` |
| `SUBS R3, R3, #1` | `1110 0010 0101 0011 0011 0000 0000 0001` | `E2533001` |
| `AND R4, R5, R6` | `1110 0000 0000 0101 0100 0000 0000 0110` | `E0054006` |
| `ORR R4, R5, R6` | `1110 0001 1000 0101 0100 0000 0000 0110` | `E1854006` |
| `MVN R0, R1` | `1110 0001 1110 0000 0000 0000 0000 0001` | `E1E00001` |
| `CMP R0, R1` | `1110 0001 0101 0000 0000 0000 0000 0001` | `E1500001` |
| `MOV R2, R1, LSL #2` | `1110 0001 1010 0000 0010 0001 0000 0001` | `E1A02101` |
| `MUL R0, R1, R2` | `1110 0000 0000 0000 0000 0010 1001 0001` | `E0000291` |
| `LDR R0, [R1]` | `1110 0101 1001 0001 0000 0000 0000 0000` | `E5910000` |
| `LDR R0, [R1, #4]` | `1110 0101 1001 0001 0000 0000 0000 0100` | `E5910004` |
| `STR R0, [R1]` | `1110 0101 1000 0001 0000 0000 0000 0000` | `E5810000` |
| `STR R0, [R1, #4]!` | `1110 0101 1011 0001 0000 0000 0000 0100` | `E5B10004` |
| `LDR R0, [R1], #4` | `1110 0100 1001 0001 0000 0000 0000 0100` | `E4910004` |
| `B .` (loop p/ si) | `1110 1010 1111 1111 1111 1111 1111 1110` | `EAFFFFFE` |
| `BX LR` | `1110 0001 0010 1111 1111 1111 0001 1110` | `E12FFF1E` |
 
> Conferência de alguns: `E0810002` = ADD R0,R1,R2; `E2433001` = SUB R3,R3,#1;
> `E3A00000` = MOV R0,#0; `E1500001` = CMP R0,R1; `E5910000` = LDR R0,[R1];
> `EAFFFFFE` = B . (branch para a própria instrução). Todos batem com saída de
> montadores ARM reais.
 
### 7.2 Programa exemplo — soma de N inteiros (1..5) com laço condicional
 
Exercita: MOV (imediato), ADD (registrador), SUBS (flags), B condicional (NE), branch.
 
```
        ; R1 = contador (N=5), R0 = acumulador
        MOV  R0, #0          ; E3A00000   acc = 0
        MOV  R1, #5          ; E3A01005   i = 5
loop:   ADD  R0, R0, R1      ; E0800001   acc += i
        SUBS R1, R1, #1      ; E2511001   i-- (atualiza flags)
        BNE  loop            ; 1AFFFFFC   se Z==0 volta p/ loop
        ; aqui R0 = 5+4+3+2+1 = 15 (0x0F)
fim:    B    fim             ; EAFFFFFE   trava (fim do programa)
```
 
| Endereço | Assembly | Hex |
|----------|----------|-----|
| 0x00 | `MOV R0, #0` | `E3A00000` |
| 0x04 | `MOV R1, #5` | `E3A01005` |
| 0x08 | `ADD R0, R0, R1` | `E0800001` |
| 0x0C | `SUBS R1, R1, #1` | `E2511001` |
| 0x10 | `BNE loop` | `1AFFFFFC` |
| 0x14 | `B fim` | `EAFFFFFE` |
 
> `BNE loop`: cond `NE = 0001`, `B` = `1010`. Offset: alvo `loop`=0x08, instrução em
> 0x10 ⇒ PC(lido)=0x10+8=0x18; `imm32 = 0x08 − 0x18 = −16` ⇒ `imm24 = −16/4 = −4 =
> 0xFFFFFC` ⇒ `0001 1010 1111…1100` = `0x1AFFFFFC`.
 
---
 
## 8. Notas de implementação no Logisim (datapath + uROM/microcódigo + PLAs)
 
### 8.1 Blocos do datapath (sugestão modular, um arquivo/subcircuito por bloco)
 
- **PC** + somador (+4) + lógica de desvio (mux entre PC+4, alvo de branch, valor da ALU).
- **Memória de instruções** (ROM) e **Instruction Register (IR)**.
- **Banco de registradores** 16×32 (2 portas de leitura mínimo: `Rn`, `Rm`; 1 de escrita
  `Rd`/`Rt`; portas extras para `Rs` e para SP/LR se implementar pilha/branch‑and‑link).
- **Barrel shifter** (LSL/LSR/ASR/ROR/RRX) controlado por `type`/`imm5` ou `Rs` — produz
  `shifter_operand` e `shifter_carry_out`.
- **Gerador de imediato**: `ARMExpandImm` (data‑proc), `ZeroExtend` (load/store),
  `SignExtend(imm24:00)` (branch). Pode ser um subcircuito de "immediate decode".
- **ALU** baseada em `AddWithCarry` + bloco lógico (AND/OR/XOR/NOT) — saídas: `result`,
  `carry_out`, `overflow`. Inversão do operando + `carry_in` para SUB/CMP/RSB/etc.
- **Registrador de flags** (N,Z,C,V) com enable governado por `S` (e por CMP/CMN/TST/TEQ).
- **Avaliador de condição**: implementa a Tabela A8‑1 (entradas `cond`+NZCV → `cond_pass`).
- **Memória de dados** (RAM) para LDR/STR.
### 8.2 Controle microprogramado: uROM + PLAs
 
Arquitetura de controle pedida = **microcódigo em uROM + PLAs** (diferencial do trabalho):
 
1. **PLA de mapeamento (entry‑point / "dispatch")** — recebe os campos de decodificação do
   IR (`bits[27:25]`, `bit4`, `opcode[24:21]`, `bit25`, `bit20 (L)`, `bit22 (B)`, `P/U/W`,
   etc.) conforme as Tabelas A5‑1/A5‑3/A5‑15/A5‑21 e produz o **endereço inicial do
   microprograma** correspondente à instrução na **uROM**.
2. **uROM (microcódigo)** — cada palavra de microinstrução contém os **sinais de controle**
   do datapath para um ciclo (ex.: `RegWrite`, `MemRead`, `MemWrite`, `ALUop`, `ALUsrcB`,
   `PCsrc`, `FlagsWrite`, `ShiftCtl`, `next‑µaddr`/`µseq`). O microcontador (`µPC`)
   sequencia: fetch → decode(dispatch via PLA) → ciclos de execução específicos → volta ao
   fetch.
3. **PLA de condição** — pode ser uma PLA separada que, a partir de `cond` e NZCV, decide se
   o microprograma "commita" os efeitos (escrita em Rd/memória/flags) ou os anula
   (transformando a instrução em NOP quando a condição falha).
4. **(Opcional) PLA de função da ALU** — mapeia `opcode[24:21]` → `ALUop` e os sinais de
   "inverter operando"/"carry‑in" (para unificar add/sub/rsb/adc/sbc/rsc na mesma soma).
**Campos sugeridos para a palavra da uROM** (defina larguras conforme seu datapath):
`µPCnext | dispatch? | RegRead_sel | ALU_op | ALU_srcA | ALU_srcB | shift_ctl |
Mem_read | Mem_write | Reg_write | Flags_write | PC_src | end?`.
 
**Fluxo mínimo de microprograma (monociclo/multiciclo simplificado):**
- *Fetch*: `IR ← Mem[PC]; PC ← PC + 4`.
- *Decode/Dispatch*: PLA de entrada → `µPC ← entry(instr)`.
- *Execute (ex.: data‑proc reg)*: `A ← Reg[Rn]; B ← Shift(Reg[Rm],…); result ←
  ALU(A,B); if cond_pass: Reg[Rd] ← result; if S: Flags ← NZCV`.
- *Execute (LDR offset imm)*: `addr ← Reg[Rn] ± imm12; data ← Mem[addr]; Reg[Rt] ← data`.
- *Execute (B)*: `PC ← PC + SignExtend(imm24:00)` (se `cond_pass`).
> Recomende‑se entregar a uROM e cada PLA como **arquivos/subcircuitos `.circ` separados**
> (ou tabelas `.txt`/hex importáveis pela ROM/PLA do Logisim), exatamente como o enunciado
> pede ("arquivos separados com o conteúdo da uROM e PLAs utilizadas").
 
### 8.3 Escopo mínimo viável vs. completo (sugestão de faseamento)
 
- **Núcleo (fase 1):** MOV, ADD, SUB, AND, ORR, CMP, B, BNE/Bcc, LDR/STR (offset imediato).
- **Fase 2:** restante das data‑processing (ADC/SBC/RSB/RSC/EOR/BIC/MVN/TST/TEQ/CMN),
  shifts (LSL/LSR/ASR/ROR/RRX), pré/pós‑indexado em load/store, LDRB/STRB.
- **Fase 3:** MUL/MLA, LDM/STM/PUSH/POP, BL/BX, MOVW/MOVT.
---
 
## 9. Estrutura do relatório e responsabilidades dos alunos (template)
 
O relatório deve conter, no mínimo:
 
1. **Introdução e objetivos** — escopo do subconjunto ARMv7‑A implementado.
2. **Modelo de programação adotado** — registradores, flags, semântica do PC escolhida
   (+8/+4/0) e justificativa.
3. **Conjunto de instruções implementadas** — para *cada* instrução: mnemônica e sintaxe,
   diagrama de codificação (campos), **opcode**, **flags afetadas**, **descrição de
   funcionamento**, **modo de endereçamento**. (As tabelas das §3 e §5 servem de base
   direta.)
4. **Arquitetura do datapath** — diagrama de blocos, descrição de cada módulo (§8.1).
5. **Unidade de controle microprogramada** — formato da microinstrução, conteúdo da
   **uROM** (microcódigos), e as **PLAs** (dispatch, condição, ALU), com as tabelas.
6. **Testes** — códigos em assembly e respectivo **binário** (§7), resultados esperados vs.
   observados no Logisim (estado de registradores/memória/flags).
7. **Responsabilidades de cada aluno** — tabela atribuindo módulos e tarefas.
**Tabela de responsabilidades (preencher):**
 
| Aluno | Módulos/entregáveis sob responsabilidade |
|-------|-------------------------------------------|
| Aluno A | _ex.: datapath (PC, IR, banco de registradores), montagem do top‑level_ |
| Aluno B | _ex.: ALU + AddWithCarry + registrador de flags + barrel shifter_ |
| Aluno C | _ex.: unidade de controle (uROM/microcódigo) + PLA de dispatch_ |
| Aluno D | _ex.: PLA de condição + memória de dados + decodificação de imediatos_ |
| Todos | _ex.: códigos de teste, validação, redação do relatório_ |
 
---
 
### Apêndice — referências de página no manual fonte (ARM DDI 0406C.c)
 
- Registradores e PC: **A2.3 (A2‑45)**; APSR/flags: **A2.4 (A2‑49)**; `AddWithCarry`: **A2.2.1 (A2‑40)**.
- Mapa de decodificação ARM: **A5.1 (A5‑194)**; data‑proc: **A5.2 (A5‑196)**;
  modified immediate: **A5.2.4 (A5‑200)**; multiply: **A5.2.5 (A5‑202)**;
  load/store: **A5.3 (A5‑208)**; branch/block: **A5.5 (A5‑214)**.
- Condition codes: **A8.3 / Tabela A8‑1 (A8‑288)**; shifts: **A8.4 (A8‑291)**;
  sintaxe padrão: **A8.2 (A8‑287)**.
- Instruções individuais (Encoding A1) na lista alfabética **A8.8** (ADD A8‑308/312,
  SUB A8‑710/712, MOV A8‑484/488, MOVT A8‑491, CMP A8‑370/372, MUL A8‑502,
  LDR A8‑408/414, STR A8‑674/676, LDM A8‑398, STM A8‑664, PUSH A8‑538, POP A8‑536,
  B A8‑334, BL A8‑348, BX A8‑352).