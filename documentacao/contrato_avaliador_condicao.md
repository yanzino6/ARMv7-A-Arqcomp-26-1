# Folha de contrato: Avaliador de condicao


**Subcircuito:** `AvaliadorCondicao`

---

## 1. Interface de sinais

| Pino | Direcao | Largura | Origem / significado |
|------|---------|---------|----------------------|
| `cond` | entrada | 4 bits | Campo de condicao da instrucao, IR bits 31 a 28. |
| `NZCV` | entrada | 4 bits | Flags atuais vindas do registrador de flags. |
| `cond_pass` | saida | 1 bit | 1 se a condicao e satisfeita; 0 caso contrario. |

---

## 2. Convencao de bits (obrigatorio respeitar na ligacao)

**NZCV**, do bit mais significativo para o menos significativo:

| bit 3 | bit 2 | bit 1 | bit 0 |
|:-----:|:-----:|:-----:|:-----:|
| **N** | **Z** | **C** | **V** |

**cond** segue a mesma orientacao: bit 3 e IR[31], bit 0 e IR[28].

> **Atencao:** se o registrador de flags do Grupo A entregar as flags em outra ordem, avisar o Grupo D antes de ligar. A tabela interna do avaliador assume exatamente esta ordem.

---

## 3. Semantica e regra de gating

`cond_pass` e uma **habilitacao global de commit**. Quando vale 0, a instrucao vira NOP: nao escreve resultado, nao escreve memoria, nao atualiza flags e nao toma o desvio. O processador continua avancando normalmente.

**Aplicar apenas como AND com os sinais de escrita da microinstrucao:**

- `RegWrite_efetivo   = RegWrite_micro   E cond_pass`
- `MemWrite_efetivo   = MemWrite_micro   E cond_pass`
- `FlagsWrite_efetivo = FlagsWrite_micro E cond_pass`
- `PCWrite_branch_efetivo = PCWrite_branch_micro E cond_pass`

> **Regra:** `cond_pass` nunca entra no PC mais 4, no ciclo de fetch, nem no sequenciamento do microendereco. Ele so governa os quatro sinais de commit acima. O fetch e o incremento normal do PC acontecem independentemente da condicao.

---

## 4. Tabela de referencia dos codigos de condicao (A8.3)

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
| 1110 | AL | sempre (1) |
| 1111 | (incondicional) | tratado como sempre (1) |

> O campo `cond = 1111` (instrucoes incondicionais no ARM real) foi mapeado para `cond_pass = 1`, ou seja, sempre executa. Todos os binarios de teste do repositorio usam `AL = 1110`, entao essa escolha nao muda o comportamento dos testes e mantem o avaliador simples.

---

## 5. Garantia de correcao

A tabela verdade foi verificada por script contra as 256 combinacoes possiveis de entrada (cond mais NZCV), com zero divergencias. O conteudo entregue (`pla_condicao.txt`) e o subcircuito reproduzem exatamente essa funcao.
