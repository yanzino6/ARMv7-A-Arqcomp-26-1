#!/usr/bin/env python3
"""Prova de equivalencia entre a ControlUnit cabeada (cpu_principal.circ) e a
microprogramada (cpu_microprogramada.circ), executada no proprio Logisim.

Gera 768 vetores cobrindo todo o espaco de decodificacao (256 combinacoes de
Opt:Funct x condicao verdadeira/falsa, mais variantes de shift e Rd=15), roda
os dois circuitos em modo headless (--test-vector) e compara as saidas.

Diferencas ACEITAS (deliberadas, documentadas no relatorio):
1. Opcodes fora do subconjunto: a CU cabeada emite sinais residuais (inclusive
   RegWrite=1 e ate PCSrc=1); a microprogramada produz NOP seguro.
2. MOV com shift tipo ROR (nao suportado pela ALU em ambas): ALUControl difere.

Uso: python3 testes/verifica_equivalencia_cu.py [caminho_do_logisim.jar]
"""
import os
import re
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, '..')
JAR = sys.argv[1] if len(sys.argv) > 1 else \
    '/Applications/Logisim-evolution.app/Contents/app/logisim-evolution-4.1.0-all.jar'

SAIDAS = {'RegSrc': '000', 'ImmSrc': '00', 'ALUSrc': '0', 'ALUControl': '000',
          'R2orImmtoReg': '0', 'MemtoReg': '0', 'RegWrite': '0', 'MemWrite': '0',
          'PCSrc': '0', 'cond_pass_dbg': '0'}


def gera_vetores():
    rows = []
    for optfunct in range(256):
        for cond in ('1110', '0000'):
            rows.append((optfunct >> 6, optfunct & 0x3F, 0, '000', cond))
    for optfunct in range(64):
        for sh in ('010', '100', '110'):
            rows.append((0, optfunct, 0, sh, '1110'))
    for optfunct in range(64):
        rows.append((0, optfunct, 15, '000', '1110'))
    hdr = ('Opt[2] Funct[6] Rd[4] Shift[3] Cond[4] Flags[4] CLK '
           'RegSrc[3] ImmSrc[2] ALUSrc ALUControl[3] R2orImmtoReg MemtoReg '
           'RegWrite MemWrite PCSrc cond_pass_dbg')
    linhas = [hdr] + [f'{o:02b} {f:06b} {r:04b} {s} {c} 0000 0 '
                      '000 00 0 000 0 0 0 0 0 0' for o, f, r, s, c in rows]
    return rows, '\n'.join(linhas) + '\n'


def roda(circ, vetores_path):
    p = subprocess.run(['java', '-jar', JAR, '-w', 'ControlUnit',
                        vetores_path, circ], capture_output=True, text=True)
    saida = p.stdout + p.stderr
    res = {}
    cur = None
    for line in saida.splitlines():
        m = re.match(r'Error on test vector (\d+):', line)
        if m:
            cur = int(m.group(1))
            res[cur] = dict(SAIDAS)
            continue
        m = re.match(r'\s+(\w+) = ([01ExU]+)[^(]*\(expected', line)
        if m and cur:
            res[cur][m.group(1)] = m.group(2)
    return res


def classe_implementada(opt, funct):
    if opt == 0:
        opc = (funct >> 1) & 0xF
        s = funct & 1
        nomes = {0b0100: 'ADD', 0b0010: 'SUB', 0b0000: 'AND',
                 0b1100: 'ORR', 0b1101: 'MOV', 0b1010: 'CMP'}
        if opc in nomes and (opc != 0b1010 or s == 1):
            return nomes[opc]
        return None
    if opt == 1:
        return 'LDR/STR'
    if opt == 2:
        return 'B' if funct >> 5 else None
    return None


def main():
    rows, texto = gera_vetores()
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
        f.write(texto)
        vet = f.name
    velho = roda(os.path.join(RAIZ, 'circuitos', 'cpu_principal.circ'), vet)
    novo = roda(os.path.join(RAIZ, 'circuitos', 'cpu_microprogramada.circ'), vet)
    os.unlink(vet)
    n = len(rows)
    impl_inesperadas = 0
    ror = 0
    nop_seguro = 0
    for i, (opt, funct, rd, sh, cond) in enumerate(rows, 1):
        a = velho.get(i, dict(SAIDAS))
        b = novo.get(i, dict(SAIDAS))
        if a == b:
            continue
        cls = classe_implementada(opt, funct)
        if cls is None:
            nop_seguro += 1
        elif cls == 'MOV' and sh == '110':
            ror += 1
        else:
            impl_inesperadas += 1
            print(f'DIFERENCA INESPERADA opt={opt:02b} funct={funct:06b} '
                  f'rd={rd} sh={sh} cond={cond} [{cls}]:',
                  {k: (a[k], b[k]) for k in SAIDAS if a[k] != b[k]})
    print(f'{n} vetores | inesperadas: {impl_inesperadas} | '
          f'ROR aceitas: {ror} | NOP seguro em nao implementadas: {nop_seguro}')
    return 0 if impl_inesperadas == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
