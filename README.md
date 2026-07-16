# Processador ARMv7-A no Logisim   controle microprogramado (uROM + PLAs)

Projeto da disciplina de Arquitetura e Organizacao de Computadores (2026/1).
Subconjunto do ARMv7-A com caminho de dados modular no Logisim Evolution e
unidade de controle microprogramada.

**Comece por aqui:** [`relatorio.md`](relatorio.md)   relatorio completo, com o
conjunto de instrucoes (campos, opcode, flags, funcionamento e modos de
enderecamento), a arquitetura, o microcodigo e os testes.

## Organizacao da entrega

| Pasta | Conteudo |
|---|---|
| `circuitos/` | Arquivos do Logisim: `cpu_principal.circ` (CPU integrada, ja com o programa P0 na ROM), `avaliador_condicao.circ`, `unidade_controle_microprogramada.circ` (Grupo C) e `modulo_alu_grupoA.circ` |
| `microcodigo/` | Conteudo da uROM (`urom.txt`) e das PLAs (`pla_dispatch.txt`, `pla_condicao.txt`) em arquivos separados, importaveis no Logisim Evolution |
| `testes/` | Programas de teste em assembly + binario (`bateria_testes.md`, `rom_p0.txt` a `rom_p4.txt`), vetores de teste e verificadores automatizados em Python |
| `documentacao/` | Fichas das instrucoes, contratos de integracao entre grupos, referencia ARMv7 destilada do manual e plano de execucao |

## Como executar

**CPU no Logisim:** abrir `circuitos/cpu_principal.circ`, clicar com o botao
direito na ROM de instrucoes → *Load Image* → `testes/rom_pX.txt` →
*Simulate > Reset Simulation* → habilitar o clock (Ctrl+K). Estados finais
esperados em `testes/bateria_testes.md`.

**Verificacoes automatizadas** (da raiz do repositorio):

```sh
python3 testes/simulador_subconjunto.py     # estados esperados de P0-P4 (5/5 OK)
python3 testes/verifica_pla_condicao.py     # PLA de condicao, 256 combinacoes
python3 testes/verifica_microcodigo.py      # P0-P4 atraves da uROM + dispatch reais
```

**Vetores do avaliador de condicao no Logisim (headless):**

```sh
java -jar <logisim-evolution.jar> -w AvaliadorCondicao \
     testes/vetores_avaliador_condicao.txt circuitos/avaliador_condicao.circ
```

## Equipe

Grupo A: Vitor Oli e Renan · Grupo B: Thiago Paiva e Sofia ·
Grupo C: Thiago e Vitor Riguette · Grupo D: Yan e Silvio.
Responsabilidades detalhadas na secao 7 do relatorio.
