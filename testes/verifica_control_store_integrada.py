#!/usr/bin/env python3
"""Verificador da control store da CPU integrada (cpu_microprogramada.circ).

A versao integrada e um datapath single-cycle com control store microcodificada
(uROM indexada pela PLA de dispatch), com layout de microword diferente da
unidade multiciclo standalone. Este script faz duas verificacoes que NAO exigem
o Logisim:

  1. CondPLA (avaliador de condicao embutido no ControlUnit): extrai a tabela
     direto do .circ e confere as 256 combinacoes de {cond, NZCV} contra a
     tabela A8-1 do manual, respeitando o OR de termos casados da PLA.
  2. Auditoria da control store: decodifica cada palavra apontada pela PLA de
     dispatch com o layout do splitter (900,1700) e confere regras por classe
     de instrucao (S-variant escreve flag, imediato liga ALUSrc, LDR le memoria,
     STR escreve memoria e nao escreve registrador, U alterna ADD/SUB, etc.).

Layout da microword (splitter 900,1700), bit0 = menos significativo:
  [0] SFI  [2:1] FLAGW  [3] BR  [4] MW  [5] RW  [6] M2R  [7] R2I
  [10:8] ALUC  [11] ALUSrc  [13:12] ImmSrc  [16:14] RegSrc  [29:17] (nao usado)
ALUC: 0=ADD 1=SUB 2=AND 3=ORR 4=MOV.  FLAGW bit0=escreve C/V, bit1=escreve N/Z.
"""
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, '..')
CIRC = os.path.join(RAIZ, 'circuitos', 'cpu_microprogramada.circ')
MICRO = os.path.join(RAIZ, 'microcodigo')

ADD, SUB, AND, ORR, MOV = 0, 1, 2, 3, 4


def cond_pass_ref(cond, N, Z, C, V):
    return [Z, not Z, C, not C, N, not N, V, not V,
            C and not Z, not C or Z, N == V, N != V,
            not Z and N == V, Z or N != V, True, True][cond]


def extrai_condpla(path):
    txt = open(path).read()
    m = re.search(r'CondPLA".*?<a name="table">(.*?)</a>', txt, re.S)
    termos = []
    for linha in m.group(1).splitlines():
        linha = linha.split('#')[0].strip()
        if not linha:
            continue
        padrao, saida = linha.split()
        termos.append((padrao, saida))
    return termos


def casa(padrao, valor8):
    bits = f'{valor8:08b}'
    return all(p in ('x', b) for p, b in zip(padrao, bits))


def verifica_condpla():
    termos = extrai_condpla(CIRC)
    div = 0
    for cond in range(16):
        for nzcv in range(16):
            N, Z, C, V = (nzcv >> 3) & 1, (nzcv >> 2) & 1, (nzcv >> 1) & 1, nzcv & 1
            entrada = (cond << 4) | nzcv          # [7:4]=cond, [3:0]=NZCV
            saida = 1 if any(casa(p, entrada) for p, _ in termos) else 0
            esperado = 1 if cond_pass_ref(cond, N, Z, C, V) else 0
            if saida != esperado:
                div += 1
                if div <= 5:
                    print(f'     cond={cond:04b} NZCV={nzcv:04b}: PLA={saida} ref={esperado}')
    print(f'[1] CondPLA integrada: {len(termos)} termos, 256 combinacoes, {div} divergencias')
    return div == 0


def load_urom(p):
    rom = {}
    for l in open(p):
        l = l.strip()
        if not l or l.startswith('v3.0') or ':' not in l:
            continue
        a, rest = l.split(':')
        b = int(a, 16)
        for i, w in enumerate(rest.split()):
            rom[b + i] = int(w, 16)
    return rom


def load_disp(p):
    t = []
    for l in open(p):
        c = l.split('#')
        corpo = c[0].strip()
        nome = c[1].strip() if len(c) > 1 else ''
        if not corpo:
            continue
        pat, out = corpo.split()
        t.append((pat, int(out, 2), nome))
    return t


def fields(w):
    return dict(SFI=w & 1, FLAGW=(w >> 1) & 3, BR=(w >> 3) & 1, MW=(w >> 4) & 1,
                RW=(w >> 5) & 1, M2R=(w >> 6) & 1, R2I=(w >> 7) & 1,
                ALUC=(w >> 8) & 7, ALUSrc=(w >> 11) & 1, ImmSrc=(w >> 12) & 3,
                RegSrc=(w >> 14) & 7, SEQ=(w >> 17) & 0x1FFF)


def audita_control_store():
    rom = load_urom(os.path.join(MICRO, 'urom_cpu_integrada.txt'))
    disp = load_disp(os.path.join(MICRO, 'pla_dispatch_cpu_integrada.txt'))
    op_de = {'ADD': ADD, 'SUB': SUB, 'AND': AND, 'ORR': ORR, 'MOV': MOV}
    problemas = []
    for pat, addr, nome in disp:
        f = fields(rom.get(addr, 0))
        n = nome.upper()
        eh_s = 'S ' in n or n.split()[0].endswith('S') or 'CMP' in n
        eh_imm = 'IMM' in n
        eh_reg = 'REG' in n
        # regra: campo de sequenciamento sempre 0 (single-cycle)
        if f['SEQ'] != 0:
            problemas.append(f'{nome}: SEQ!=0')
        # data-processing aritm/logico
        base = n.split()[0].rstrip('S')
        if base in op_de:
            if f['ALUC'] != op_de[base]:
                problemas.append(f'{nome}: ALUC={f["ALUC"]} != {base}')
            # CMP nao escreve registrador; demais escrevem
            if 'CMP' in n:
                if f['RW'] != 0:
                    problemas.append(f'{nome}: CMP com RW=1')
                if f['FLAGW'] == 0:
                    problemas.append(f'{nome}: CMP sem FLAGW')
            else:
                if f['RW'] != 1:
                    problemas.append(f'{nome}: dataproc com RW=0')
            # S-variant / CMP escreve flags; sem S nao escreve
            if eh_s and f['FLAGW'] == 0:
                problemas.append(f'{nome}: variante S sem FLAGW')
            if not eh_s and 'CMP' not in n and f['FLAGW'] != 0:
                problemas.append(f'{nome}: variante sem S escrevendo FLAGW')
            # imediato liga ALUSrc; MOV reg usa shifter (SFI)
            if eh_imm and f['ALUSrc'] != 1:
                problemas.append(f'{nome}: imediato sem ALUSrc')
        # load/store
        if n.startswith('LDR'):
            if not (f['RW'] == 1 and f['M2R'] == 1):
                problemas.append(f'{nome}: LDR deve ter RW=1,M2R=1')
            if f['ALUC'] != (SUB if 'U=0' in nome or 'U0' in nome else ADD):
                problemas.append(f'{nome}: LDR ALUC nao bate com bit U')
        if n.startswith('STR'):
            if not (f['MW'] == 1 and f['RW'] == 0):
                problemas.append(f'{nome}: STR deve ter MW=1,RW=0')
            if f['ALUC'] != (SUB if 'U=0' in nome or 'U0' in nome else ADD):
                problemas.append(f'{nome}: STR ALUC nao bate com bit U')
        if n.startswith('B'):
            if f['BR'] != 1:
                problemas.append(f'{nome}: B sem BR')
    print(f'[2] Control store: {len(disp)} classes auditadas, '
          f'{len(problemas)} problemas')
    for p in problemas:
        print('     ', p)
    return not problemas


def main():
    ok1 = verifica_condpla()
    ok2 = audita_control_store()
    print('RESULTADO:', 'OK' if (ok1 and ok2) else 'PROBLEMAS ENCONTRADOS')
    return 0 if (ok1 and ok2) else 1


if __name__ == '__main__':
    sys.exit(main())
