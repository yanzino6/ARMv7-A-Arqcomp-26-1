#!/usr/bin/env python3
"""Prova de regressao do item 1 (gating do cond_pass no PCWrite do fetch).

Constroi um programa adversarial que os testes P0-P4 nao cobrem: uma instrucao
com condicao FALSA seguida imediatamente de uma instrucao NAO idempotente
(ADD R1,R1,#1). No circuito antigo, o cond_pass=0 tambem cortava o PCWrite do
fetch, entao o PC congelava por um ciclo e a instrucao seguinte executava DUAS
vezes (R1 somava 2). Com a correcao (PCWrite_Out = PCWrite AND (cond_pass OR
MemRead)), o fetch sempre avanca e a instrucao executa uma unica vez.

Reaproveita o microsequenciador de verifica_microcodigo.py:
  gate_fetch_pc=True  -> modela o circuito ANTIGO (bug)
  gate_fetch_pc=False -> modela o circuito CORRIGIDO (cond_pass OR MemRead)
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from verifica_microcodigo import carrega_dispatch, carrega_urom, executa  # noqa

MICRO = os.path.join(AQUI, '..', 'microcodigo')

# Programa: R1=5; CMP R0,#1 (Z=0 => EQ falso); ADDEQ R1,R1,#100 (pulado);
#           ADD R1,R1,#1 (nao idempotente, deve rodar 1x); B .
PROG = [
    0xE3A00000,  # MOV R0, #0
    0xE3A01005,  # MOV R1, #5
    0xE3500001,  # CMP R0, #1      -> N=1 Z=0 C=0 V=0  (EQ falso)
    0x02811064,  # ADDEQ R1,R1,#100 -> condicao falsa, NAO comita
    0xE2811001,  # ADD R1,R1,#1     -> R1 deve virar 6, nao 7
    0xEAFFFFFE,  # B .              -> estaciona
]
ESPERADO_R1 = 6


def main():
    termos = carrega_dispatch(os.path.join(MICRO, 'pla_dispatch.txt'))
    urom = carrega_urom(os.path.join(MICRO, 'urom.txt'))

    R_bug, _, _, obs_bug = executa(PROG, termos, urom, gate_fetch_pc=True)
    R_fix, _, _, obs_fix = executa(PROG, termos, urom, gate_fetch_pc=False)

    print(f'circuito ANTIGO  (cond_pass corta PCWrite do fetch): '
          f'R1={R_bug[1]}  re-execucoes={obs_bug["dupla_exec"]}')
    print(f'circuito CORRIGIDO (cond_pass OR MemRead)          : '
          f'R1={R_fix[1]}  re-execucoes={obs_fix["dupla_exec"]}')

    ok = True
    if R_bug[1] == ESPERADO_R1:
        print('AVISO: o cenario nao expos o bug (esperava R1 errado no antigo)')
        ok = False
    if R_fix[1] != ESPERADO_R1:
        print(f'FALHA: circuito corrigido deu R1={R_fix[1]}, esperado {ESPERADO_R1}')
        ok = False
    if obs_fix['dupla_exec'] != 0:
        print('FALHA: ainda ha re-execucao no circuito corrigido')
        ok = False
    print('RESULTADO:', 'OK - o fix elimina a re-execucao apos condicao falsa'
          if ok else 'PROBLEMA')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
