#!/usr/bin/env python3
"""Simulador do subconjunto ARMv7 do trabalho — verifica os estados finais esperados de P0-P4.
Semantica: PC lido no branch = endereco da instrucao + 8 (bytes). Reset zera tudo."""
import sys

M32 = 0xFFFFFFFF

def ror(v, n):
    n %= 32
    return ((v >> n) | (v << (32 - n))) & M32

def cond_pass(cond, N, Z, C, V):
    return [Z, not Z, C, not C, N, not N, V, not V,
            C and not Z, not C or Z, N == V, N != V,
            not Z and N == V, Z or N != V, True, True][cond]

def add_with_carry(x, y, cin):
    us = x + y + cin
    r = us & M32
    c = 1 if us > M32 else 0
    sx = x - (1 << 32) if x >> 31 else x
    sy = y - (1 << 32) if y >> 31 else y
    ss = sx + sy + cin
    sr = r - (1 << 32) if r >> 31 else r
    v = 1 if sr != ss else 0
    return r, c, v

def run(program, max_steps=10000):
    R = [0] * 16
    mem = {}
    N = Z = C = V = 0
    pc = 0
    steps = 0
    while steps < max_steps:
        steps += 1
        if pc // 4 >= len(program):
            raise RuntimeError(f'PC fora do programa: {pc:#x}')
        instr = program[pc // 4]
        cond = instr >> 28
        next_pc = pc + 4
        if cond_pass(cond, N, Z, C, V):
            op = (instr >> 25) & 7
            if op in (0, 1):  # data processing
                opcode = (instr >> 21) & 0xF
                S = (instr >> 20) & 1
                rn = (instr >> 16) & 0xF
                rd = (instr >> 12) & 0xF
                if op == 1:  # imediato modificado
                    rot = (instr >> 8) & 0xF
                    op2 = ror(instr & 0xFF, 2 * rot)
                    sh_c = C if rot == 0 else (op2 >> 31) & 1
                else:  # registrador com shift imediato
                    rm = instr & 0xF
                    imm5 = (instr >> 7) & 0x1F
                    typ = (instr >> 5) & 3
                    v0 = R[rm]
                    if typ == 0:  # LSL
                        op2 = (v0 << imm5) & M32
                        sh_c = ((v0 >> (32 - imm5)) & 1) if imm5 else C
                    elif typ == 1:  # LSR
                        n = imm5 or 32
                        op2 = (v0 >> n) & M32 if n < 32 else 0
                        sh_c = (v0 >> (n - 1)) & 1
                    elif typ == 2:  # ASR
                        n = imm5 or 32
                        sv = v0 - (1 << 32) if v0 >> 31 else v0
                        op2 = (sv >> min(n, 31)) & M32
                        sh_c = (v0 >> min(n - 1, 31)) & 1
                    else:  # ROR
                        op2 = ror(v0, imm5) if imm5 else ((C << 31) | (v0 >> 1))
                        sh_c = (op2 >> 31) & 1 if imm5 else v0 & 1
                a = R[rn]
                wr, res = True, None
                if opcode == 0b0000: res, c2, v2 = a & op2, sh_c, V
                elif opcode == 0b0010: res, c2, v2 = add_with_carry(a, op2 ^ M32, 1)
                elif opcode == 0b0100: res, c2, v2 = add_with_carry(a, op2, 0)
                elif opcode == 0b1010: res, c2, v2 = add_with_carry(a, op2 ^ M32, 1); wr = False
                elif opcode == 0b1100: res, c2, v2 = a | op2, sh_c, V
                elif opcode == 0b1101: res, c2, v2 = op2, sh_c, V
                else: raise RuntimeError(f'opcode DP nao implementado: {opcode:04b}')
                if wr:
                    R[rd] = res
                if S or not wr:
                    N, Z, C, V = (res >> 31) & 1, 1 if res == 0 else 0, c2, v2
            elif op in (2, 3):  # load/store imediato
                P = (instr >> 24) & 1; U = (instr >> 23) & 1
                B = (instr >> 22) & 1; W = (instr >> 21) & 1; L = (instr >> 20) & 1
                rn = (instr >> 16) & 0xF; rt = (instr >> 12) & 0xF
                off = instr & 0xFFF
                assert op == 2 and B == 0, 'so offset imediato de palavra'
                addr = R[rn] + (off if U else -off) if P else R[rn]
                if L: R[rt] = mem.get(addr, 0)
                else: mem[addr] = R[rt]
                if not P or W: R[rn] = R[rn] + (off if U else -off)
            elif op == 5:  # branch
                imm24 = instr & 0xFFFFFF
                if imm24 >> 23: imm24 -= 1 << 24
                target = pc + 8 + imm24 * 4
                if target == pc:  # B fim: estaciona
                    return R, mem, (N, Z, C, V), steps
                next_pc = target
            else:
                raise RuntimeError(f'classe nao implementada: op={op}')
        pc = next_pc
    raise RuntimeError('nao estacionou (max_steps)')

def load_rom(path):
    words = []
    for line in open(path):
        line = line.strip()
        if line == 'v2.0 raw' or not line: continue
        words += [int(w, 16) for w in line.split()]
    return words

if __name__ == '__main__':
    import os
    base = os.path.dirname(os.path.abspath(__file__)) + os.sep
    expected = {
        'p0': {'R': {1: 6, 2: 5, 3: 0, 4: 1, 5: 22}, 'F': (0, 1, 1, 0), 'M': {}},
        'p1': {'R': {0: 15}, 'F': (0, 1, 1, 0), 'M': {}},
        'p2': {'R': {0: 12, 1: 10, 2: 22, 3: 2, 4: 8, 5: 14}, 'F': (0, 0, 1, 0), 'M': {}},
        'p3': {'R': {0: 7, 1: 7, 2: 8}, 'F': (0, 1, 1, 0), 'M': {}},
        'p4': {'R': {0: 0xAB, 1: 0x40, 5: 0xAB, 6: 0xAB}, 'F': (0, 0, 0, 0), 'M': {0x40: 0xAB, 0x44: 0xAB}},
    }
    ok = True
    for p, exp in expected.items():
        prog = load_rom(base + f'rom_{p}.txt')
        R, mem, F, steps = run(prog)
        errs = []
        for i in range(16):
            want = exp['R'].get(i)
            if want is not None and R[i] != want:
                errs.append(f'R{i}: esperado {want:#x}, simulado {R[i]:#x}')
            if want is None and i < 15 and R[i] != 0:
                errs.append(f'R{i}: deveria ficar 0, simulado {R[i]:#x}')
        if F != exp['F']:
            errs.append(f'flags NZCV: esperado {exp["F"]}, simulado {F}')
        for a, want in exp['M'].items():
            if mem.get(a, 0) != want:
                errs.append(f'Mem[{a:#x}]: esperado {want:#x}, simulado {mem.get(a,0):#x}')
        status = 'OK' if not errs else 'DIVERGE'
        ok &= not errs
        print(f'{p.upper()}: {status} ({steps} instrucoes executadas)')
        for e in errs: print('   ', e)
    sys.exit(0 if ok else 1)
