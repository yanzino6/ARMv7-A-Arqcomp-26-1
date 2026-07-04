#!/usr/bin/env python3
"""Verificador do microcodigo do Grupo C (microcodigo/pla_dispatch.txt + urom.txt).

Faz tres verificacoes:
1. PLA de dispatch: termos mutuamente disjuntos (a PLA do Logisim faz OR de
   todos os termos casados) e cobertura de todas as instrucoes dos programas
   de teste P0-P4.
2. Execucao comportamental: roda P0-P4 atraves do microsequenciador
   (fetch -> dispatch -> exec -> fetch), interpretando os campos reais da
   palavra de 30 bits da uROM, e compara o estado final com o esperado.
   Layout da palavra derivado do splitter de
   circuitos/unidade_controle_microprogramada.circ.
3. Analises de integracao: reporta o comportamento sob interpretacoes
   alternativas dos sinais (gating do PCWrite no fetch e semantica literal
   de invB_cin), que sao os dois pontos a fechar com os Grupos A e B.

Formato da palavra de 30 bits (derivado do splitter do ControlUnit.circ):
  [1:0] PC_src  [2] PCWrite  [3] FlagsWrite  [4] RegWrite  [6:5] wb_src
  [7] MemWrite  [8] MemRead  [10:9] shift_ctl  [12:11] ALU_srcB
  [13] ALU_srcA  [15:14] invB_cin  [19:16] ALU_op  [21:20] reg_read_sel
  [27:22] next_uaddr  [29:28] useq_sel (00 uPC+1, 01 dispatch, 10 salto)
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
MICRO = os.path.join(AQUI, '..', 'microcodigo')
ROMS = AQUI
M32 = 0xFFFFFFFF

ESPERADO = {
    'p0': {'R': {1: 6, 2: 5, 3: 0, 4: 1, 5: 22}, 'F': (0, 1, 1, 0), 'M': {}},
    'p1': {'R': {0: 15}, 'F': (0, 1, 1, 0), 'M': {}},
    'p2': {'R': {0: 12, 1: 10, 2: 22, 3: 2, 4: 8, 5: 14}, 'F': (0, 0, 1, 0), 'M': {}},
    'p3': {'R': {0: 7, 1: 7, 2: 8}, 'F': (0, 1, 1, 0), 'M': {}},
    'p4': {'R': {0: 0xAB, 1: 0x40, 5: 0xAB, 6: 0xAB}, 'F': (0, 0, 0, 0),
           'M': {0x40: 0xAB, 0x44: 0xAB}},
}


def carrega_dispatch(path):
    termos = []
    for linha in open(path):
        linha = linha.split('#')[0].strip()
        if not linha:
            continue
        padrao, saida = linha.split()
        assert len(padrao) == 8 and len(saida) == 6
        termos.append((padrao, int(saida, 2)))
    return termos


def casa(padrao, valor8):
    bits = f'{valor8:08b}'
    return all(p in ('x', b) for p, b in zip(padrao, bits))


def dispatch(termos, valor8):
    hits = [(p, s) for p, s in termos if casa(p, valor8)]
    if not hits:
        return 0, []          # nao casado: PLA produz 0 (fetch = NOP seguro? addr0)
    return hits[0][1], hits


def carrega_urom(path):
    rom = [0] * 64
    for linha in open(path):
        linha = linha.strip()
        if not linha or linha.startswith('v3.0'):
            continue
        addr, resto = linha.split(':')
        a = int(addr, 16)
        for i, w in enumerate(resto.split()):
            rom[a + i] = int(w, 16)
    return rom


def campos(w):
    return {
        'PC_src': w & 3, 'PCWrite': (w >> 2) & 1, 'FlagsWrite': (w >> 3) & 1,
        'RegWrite': (w >> 4) & 1, 'wb_src': (w >> 5) & 3, 'MemWrite': (w >> 7) & 1,
        'MemRead': (w >> 8) & 1, 'shift_ctl': (w >> 9) & 3, 'ALU_srcB': (w >> 11) & 3,
        'ALU_srcA': (w >> 13) & 1, 'invB_cin': (w >> 14) & 3, 'ALU_op': (w >> 16) & 0xF,
        'next_uaddr': (w >> 22) & 0x3F, 'useq_sel': (w >> 28) & 3,
    }


def cond_pass(cond, N, Z, C, V):
    return [Z, not Z, C, not C, N, not N, V, not V,
            C and not Z, not C or Z, N == V, N != V,
            not Z and N == V, Z or N != V, True, True][cond]


def ror(v, n):
    n %= 32
    return ((v >> n) | (v << (32 - n))) & M32


def shifter(instr, R, C):
    """Segundo operando por registrador com shift imediato (IR[11:0])."""
    rm, imm5, typ = instr & 0xF, (instr >> 7) & 0x1F, (instr >> 5) & 3
    v0 = R[rm]
    if typ == 0:
        return (v0 << imm5) & M32, ((v0 >> (32 - imm5)) & 1) if imm5 else C
    if typ == 1:
        n = imm5 or 32
        return (v0 >> n) if n < 32 else 0, (v0 >> (n - 1)) & 1
    if typ == 2:
        n = imm5 or 32
        sv = v0 - (1 << 32) if v0 >> 31 else v0
        return (sv >> min(n, 31)) & M32, (v0 >> min(n - 1, 31)) & 1
    if imm5:
        r = ror(v0, imm5)
        return r, (r >> 31) & 1
    return ((C << 31) | (v0 >> 1)) & M32, v0 & 1


def imediato(instr):
    """Selecao de imediato por classe (papel do Extender/ImmSrc no datapath)."""
    op = (instr >> 25) & 7
    if op == 1:                      # data-processing imediato
        rot = (instr >> 8) & 0xF
        return ror(instr & 0xFF, 2 * rot), rot
    if op in (2, 3):                 # load/store imm12
        return instr & 0xFFF, None
    imm24 = instr & 0xFFFFFF         # branch
    if imm24 >> 23:
        imm24 -= 1 << 24
    return imm24 * 4, None


def executa(prog, termos, urom, gate_fetch_pc=False, invb_cin_literal=False,
            max_ciclos=20000):
    """Roda um programa pelo microsequenciador. Retorna (R, mem, flags, obs).

    gate_fetch_pc: se True, cond_pass corta o PCWrite tambem no fetch
    (como os 4 ANDs do circuito fazem hoje); se False, o gating segue o
    contrato do avaliador (so os commits de exec).
    invb_cin_literal: se True, invB_cin=10 e lido literalmente como
    (inverte B, carry-in 0); se False, como complemento de dois completo.
    """
    R = [0] * 16
    mem = {}
    N = Z = C = V = 0
    pc, ir, upc, mar = 0, 0, 0, 0
    obs = {'dupla_exec': 0, 'nao_casadas': set()}
    ultimo_fetch_pc = None
    for _ in range(max_ciclos):
        w = campos(urom[upc])
        cp = cond_pass(ir >> 28, N, Z, C, V)
        if upc == 0:                                   # FETCH
            if pc // 4 >= len(prog):
                raise RuntimeError(f'PC fora do programa: {pc:#x}')
            if ultimo_fetch_pc == pc and (ir >> 28) == 14:
                obs['dupla_exec'] += 1
            ir_novo = prog[pc // 4]
            pode_escrever_pc = cp if gate_fetch_pc else True
            if ir_novo == prog[pc // 4] and (ir_novo >> 24) & 0xF in (0xA, 0xB) \
               and (ir_novo & 0xFFFFFF) == 0xFFFFFE:
                # B para si mesmo: estaciona
                if cond_pass(ir_novo >> 28, N, Z, C, V):
                    return R, mem, (N, Z, C, V), obs
            ultimo_fetch_pc = pc
            ir = ir_novo
            if pode_escrever_pc:
                pc = pc + 4
            upc = 1
            continue
        if w['useq_sel'] == 1:                         # DISPATCH
            alvo, hits = dispatch(termos, (ir >> 20) & 0xFF)
            if not hits:
                obs['nao_casadas'].add(f'{ir:08X}')
            if len(hits) > 1:
                raise RuntimeError(f'termos sobrepostos p/ {ir:08X}: {hits}')
            upc = alvo if hits else 0
            continue
        # EXEC: monta operandos conforme os campos da palavra
        rn, rd = (ir >> 16) & 0xF, (ir >> 12) & 0xF
        a = pc if w['ALU_srcA'] else R[rn]
        sh_c = C
        if w['ALU_srcB'] == 0:
            b, sh_c = shifter(ir, R, C)
        elif w['ALU_srcB'] == 1:
            b, rot = imediato(ir)
            if rot is not None and rot != 0:
                sh_c = (b >> 31) & 1
        else:
            b = 4
        if w['ALU_op'] == 0:
            inv = (w['invB_cin'] >> 1) & 1
            cin = (w['invB_cin'] & 1) if invb_cin_literal else inv
            x, y = a, (b ^ M32) if inv else b
            us = x + y + cin
            res, c2 = us & M32, 1 if us > M32 else 0
            sx = x - (1 << 32) if x >> 31 else x
            sy = y - (1 << 32) if y >> 31 else y
            sr = res - (1 << 32) if res >> 31 else res
            v2 = 0 if sr == sx + sy + cin else 1
        elif w['ALU_op'] == 2:
            res, c2, v2 = a & b, sh_c, V
        elif w['ALU_op'] == 3:
            res, c2, v2 = a | b, sh_c, V
        elif w['ALU_op'] == 4:
            res, c2, v2 = b, sh_c, V
        else:
            raise RuntimeError(f'ALU_op nao usado: {w["ALU_op"]}')
        if upc in (0x20, 0x30):                        # calculo de endereco
            assert (ir >> 23) & 1 == 1, 'testes usam apenas U=1'
            mar = res
        if w['MemRead'] and upc != 0:
            pass                                       # leitura fica p/ commit abaixo
        if cp:
            if w['RegWrite']:
                R[rd] = mem.get(mar, 0) if w['wb_src'] == 1 else res
            if w['MemWrite']:
                mem[mar] = R[rd]
            if w['FlagsWrite']:
                N, Z = (res >> 31) & 1, 1 if res == 0 else 0
                C, V = c2, v2
            if w['PCWrite'] and w['PC_src'] == 1:      # branch: PC ja vale instr+4
                pc = (pc + 4 + imediato(ir)[0]) & M32
        # sequenciamento
        upc = w['next_uaddr'] if w['useq_sel'] == 2 else upc + 1
    raise RuntimeError('nao estacionou (max_ciclos)')


def carrega_rom(path):
    words = []
    for linha in open(path):
        linha = linha.strip()
        if linha == 'v2.0 raw' or not linha:
            continue
        words += [int(x, 16) for x in linha.split()]
    return words


def confere(nome, R, mem, F, exp):
    erros = []
    for i in range(15):
        want = exp['R'].get(i, 0)
        if R[i] != want:
            erros.append(f'R{i}: esperado {want:#x}, obtido {R[i]:#x}')
    if F != exp['F']:
        erros.append(f'flags NZCV: esperado {exp["F"]}, obtido {F}')
    for a, want in exp['M'].items():
        if mem.get(a, 0) != want:
            erros.append(f'Mem[{a:#x}]: esperado {want:#x}, obtido {mem.get(a, 0):#x}')
    return erros


def main():
    termos = carrega_dispatch(os.path.join(MICRO, 'pla_dispatch.txt'))
    urom = carrega_urom(os.path.join(MICRO, 'urom.txt'))

    # 1. Disjuncao dos termos da PLA (necessario: a PLA do Logisim faz OR)
    sobrepostos = 0
    for v in range(256):
        hits = [p for p, _ in termos if casa(p, v)]
        if len(hits) > 1:
            sobrepostos += 1
            print(f'SOBREPOSICAO em {v:08b}: {hits}')
    print(f'[1] PLA dispatch: {len(termos)} termos, '
          f'{sobrepostos} sobreposicoes nas 256 entradas')

    # 2. Execucao dos programas P0-P4 pelo microcodigo (semantica de contrato)
    falhas = 0
    for p, exp in ESPERADO.items():
        prog = carrega_rom(os.path.join(ROMS, f'rom_{p}.txt'))
        R, mem, F, obs = executa(prog, termos, urom)
        erros = confere(p, R, mem, F, exp)
        status = 'OK' if not erros else 'DIVERGE'
        falhas += bool(erros)
        extra = f' | instrucoes sem termo na PLA: {sorted(obs["nao_casadas"])}' \
            if obs['nao_casadas'] else ''
        print(f'[2] {p.upper()}: {status}{extra}')
        for e in erros:
            print('     ', e)

    # 3a. Como o circuito esta hoje: cond_pass corta PCWrite tambem no fetch
    print('[3a] gating do PCWrite tambem no fetch (como os 4 ANDs estao ligados hoje):')
    for p, exp in ESPERADO.items():
        prog = carrega_rom(os.path.join(ROMS, f'rom_{p}.txt'))
        try:
            R, mem, F, obs = executa(prog, termos, urom, gate_fetch_pc=True)
            erros = confere(p, R, mem, F, exp)
            aviso = ' (com re-execucao de instrucao apos condicao falsa)' \
                if obs['dupla_exec'] else ''
            print(f'      {p.upper()}: {"OK" if not erros else "DIVERGE"}{aviso}')
            for e in erros:
                print('       ', e)
        except RuntimeError as e:
            print(f'      {p.upper()}: TRAVA ({e})')

    # 3b. invB_cin=10 interpretado literalmente (inverte B, carry-in = 0)
    print('[3b] invB_cin=10 literal, carry-in 0 (subtracao sem o +1):')
    for p, exp in ESPERADO.items():
        prog = carrega_rom(os.path.join(ROMS, f'rom_{p}.txt'))
        try:
            R, mem, F, _ = executa(prog, termos, urom, invb_cin_literal=True)
            erros = confere(p, R, mem, F, exp)
            print(f'      {p.upper()}: {"OK" if not erros else "DIVERGE: " + erros[0]}')
        except RuntimeError as e:
            print(f'      {p.upper()}: TRAVA ({e})')

    return 1 if falhas else 0


if __name__ == '__main__':
    sys.exit(main())
