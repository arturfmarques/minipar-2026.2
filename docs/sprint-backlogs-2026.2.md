# Sprint Backlogs — MiniPar 2026.2

Os Sprint Backlogs organizam o trabalho de implementação e documentação em quatro conjuntos de entregas. Essa divisão apresenta os incrementos técnicos do projeto, sem pressupor cerimônias, datas ou estimativas Scrum que não foram registradas.

| Sprint | Itens do Product Backlog | Objetivo | Principais atividades e entregas |
| --- | --- | --- | --- |
| 1 — Base e front-end | PB01–PB03 | Ampliar a linguagem e preservar o comportamento anterior | Ambiente G++, gramática BNF, tokens, AST de Fork/Join, semântica, símbolos e testes do front-end |
| 2 — Geração e runtime | PB04–PB07 | Produzir executáveis e executar tarefas independentes | TAC, geração C++20, snapshots, `std::async`, Join, canais TCP, RPC, trabalhador e afinidade de CPU |
| 3 — Programas de teste | PB08–PB10 | Demonstrar os requisitos com programas MiniPar | Testes 1–11, validadores, resultados dos fractais, Assembly ARMv7 e verificação no CPUlator |
| 4 — Interfaces e documentação | PB11–PB12 | Integrar ferramentas e documentar a entrega | Web educacional, navegação entre IDEs, três diagramas UML, pseudocódigos, testes de integração e relatório técnico |

## Resultados e rastreabilidade

- **Linguagem e compilador:** `BNF-grammar.md`, `src/lexer.py`, `src/parser.py`, `src/semantic.py`, `src/tac.py` e `src/codegen.py`.
- **Execução nativa e comunicação:** `src/runtime/`, `tools/run_worker.py` e exemplos em `examples/`.
- **Programas e testes:** fontes em `tests/`, testes automatizados e validadores em `tools/`.
- **Interfaces:** `app.py`, `educational_web.py`, `templates/` e `static/`.
- **Documentação:** arquivos em `docs/`, diagramas em `docs/uml/` e relatório acadêmico em `docs/Relatorio-Minipar2026.2.pdf`.

As atividades e prioridades correspondentes estão descritas no [Product Backlog](product-backlog-2026.2.md).
