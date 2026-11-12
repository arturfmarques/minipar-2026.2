# Testes de integração — MiniPar 2026.2

A suíte automatizada verifica a passagem entre os componentes da compilação e o comportamento dos executáveis produzidos. O registro consolidado do ambiente de desenvolvimento contém **519 testes aprovados**, sem falhas. Esse número se refere à validação registrada no projeto e pode variar conforme dependências e plataforma.

## Integrações verificadas

| Integração | Arquivos e componentes | Verificação |
| --- | --- | --- |
| Lexer → Parser → AST | `tests/unit/test_frontend.py`, `test_tasks_grammar.py` | Tokens, precedência, construções válidas e erros de sintaxe |
| AST → Semântica → Símbolos | `test_semantic_2026_2.py`, `test_types_1a7.py` | Escopos, tipos, classes, chamadas e isolamento |
| AST → TAC e C++ | `test_tac_2026_2.py`, `test_generation.py` | Artefatos gerados a partir do mesmo programa validado |
| C++ → G++ → executável | `tests/integration/test_native.py`, `test_programs_1a7.py` | Compilação nativa, execução e saídas observadas |
| Runtime, TCP e trabalhador | `test_runtime.py`, `test_affinity_native.py` | Threads, comunicação, Fork remoto e afinidade |
| Interfaces Web | `test_web.py`, `test_educational_web.py`, `test_web_unified.py` | APIs, etapas educacionais, catálogo e execução |
| Programas paralelos | `test_programs_8910.py` | 160 atividades, resultados e fractais |
| Minicompilador ARMv7 | `test_minicompiler.py`, `test_minicompiler_delivery.py` | Fases internas, arquivo Assembly e oráculos numéricos |

A geração de TAC e a geração de C++ são caminhos independentes sobre a **AST validada**: o backend C++ não interpreta o texto TAC.

## Como executar

Na raiz do repositório, com o ambiente Python e o G++ configurados:

```powershell
py -m pip install -r requirements-dev.lock.txt
py -m pytest
```

Para selecionar áreas específicas:

```powershell
py -m pytest tests/unit
py -m pytest tests/integration/test_runtime.py tests/integration/test_affinity_native.py
py -m pytest tests/integration/test_educational_web.py tests/integration/test_web_unified.py
py -m pytest tests/integration/test_minicompiler.py
```

Para executar os programas obrigatórios com validadores próprios:

```powershell
py tools/validate_programs.py
py tools/validate_parallel.py
py tools/validate_minicompiler.py
```

Alguns testes precisam de G++, dependências de rede, Node.js ou ferramentas ARM opcionais. Ausência dessas ferramentas pode impedir a execução de casos específicos e deve ser distinguida de falha funcional.

## Evidências complementares

- [Resultados e arquivos ARMv7](evidencias/teste11/)
- [Fractais produzidos](evidencias/fractais/)
- [Relatório técnico](Relatorio-Minipar2026.2.pdf)

Os testes de TCP documentados entre processos diferentes no mesmo host não equivalem, por si só, a ensaio entre dois computadores físicos.
