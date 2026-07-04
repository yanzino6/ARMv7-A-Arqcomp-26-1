#!/usr/bin/env python3
"""Verificacao exaustiva da PLA de condicao (microcodigo/pla_condicao.txt).

Compara a saida da PLA (OR de todos os termos casados, semantica do componente
PLA do Logisim Evolution) com a tabela A8-1 do manual ARM, para as 256
combinacoes de entrada (cond de 4 bits + NZCV de 4 bits).
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
PLA = os.path.join(AQUI, '..', 'microcodigo', 'pla_condicao.txt')


def referencia(cond, N, Z, C, V):
    """Tabela A8-1: cond_pass esperado. cond=1111 tratado como sempre."""
    return [Z, not Z, C, not C, N, not N, V, not V,
            C and not Z, not C or Z, N == V, N != V,
            not Z and N == V, Z or N != V, True, True][cond]


def carrega_termos(path):
    termos = []
    for linha in open(path):
        linha = linha.split('#')[0].strip()
        if not linha:
            continue
        padrao, saida = linha.split()[:2]
        assert len(padrao) == 8 and saida == '1', f'linha inesperada: {linha}'
        termos.append(padrao)
    return termos


def pla_saida(termos, bits8):
    for padrao in termos:
        if all(p in ('x', b) for p, b in zip(padrao, bits8)):
            return 1
    return 0


def main():
    termos = carrega_termos(PLA)
    divergencias = 0
    for cond in range(16):
        for nzcv in range(16):
            N, Z, C, V = (nzcv >> 3) & 1, (nzcv >> 2) & 1, (nzcv >> 1) & 1, nzcv & 1
            bits8 = f'{cond:04b}{nzcv:04b}'
            got = pla_saida(termos, bits8)
            want = 1 if referencia(cond, N, Z, C, V) else 0
            if got != want:
                divergencias += 1
                print(f'DIVERGE cond={cond:04b} NZCV={nzcv:04b}: PLA={got} esperado={want}')
    print(f'{len(termos)} termos, 256 combinacoes testadas, {divergencias} divergencias')
    return 0 if divergencias == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
