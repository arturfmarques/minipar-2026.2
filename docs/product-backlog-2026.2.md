# Product Backlog — MiniPar 2026.2

> Material provisório preservado para revisão acadêmica posterior.

Reconstrução documental em 11/11/2026, fundamentada no código, Git da base e
registros técnicos existentes. Não é uma ata histórica de Product Owner,
não atribui trabalho a pessoas e não inventa estimativas ou reuniões.
Prioridades abaixo são uma organização desta auditoria: P1 é essencial à
conformidade/execução; P2 organiza demonstração e entrega. Situação refere-se
ao produto observado, não a uma declaração de conclusão de disciplina.

| Item | Prioridade | Requisito/resultado verificável | Critério de aceitação | Situação e rastreabilidade |
| --- | --- | --- | --- | --- |
| PB01 | P1 | Preservar base 2026.1 e interfaces | CLI/menu/IDE e programas legados continuam executáveis | Implementado; `organizacao-2026.2.md`, testes legados e hashes. M01/M02/D05. |
| PB02 | P1 | Ambiente nativo reproduzível | G++ selecionável, C++20 -O3, dependências fixadas, erros reais | Implementado; `toolchain.py`, requirements, testes nativos. M10. |
| PB03 | P1 | Lexer/Parser/AST/BNF 2026.2 | Sintaxe válida vira AST, erro inválido não é ignorado, precedência preservada | Implementado; testes frontend/tarefas/afinidade. M02/M03/M05/M06. |
| PB04 | P1 | Semântica e símbolos | Escopos, tipos conhecidos, chamadas/retornos/canais validados antes do backend | Implementado com limites documentados; tipo int diverge de Python. M04/M07/M08. |
| PB05 | P1 | TAC e C++ dinâmicos | Saídas mudam com a AST e passam por G++ real | Implementado; testes de geração/renomeação e nativos. M09/M10. |
| PB06 | P1 | SEQ/PAR/Fork/Join independentes | Snapshots, sincronização, valores e exceções demonstrados | Implementado; runtime e testes nativos. M12/M13. |
| PB07 | P1 | TCP/canais e Fork remoto | Trabalhador distinto recebe argumentos e Join devolve resultado; erro remoto não vira sucesso local | Implementado/validado em localhost. M15/M16; demonstração física pendente. |
| PB08 | P1 | Seleção explícita de CPU | Validar IDs permitidos, aplicar antes do corpo e registrar CPU real | Implementado Windows; Linux não executado. M14/M18; topologia física não comprovada. |
| PB09 | P1 | Programas 1–7 | Resultados calculados, classes/recursão onde aplicáveis, TAC iterativo real | Funcionais; T01/T02 distribuição e T04 fidelidade ao XOR ainda parciais. |
| PB10 | P1 | Programas 8–10 | 160 atividades, 4/5/6 tarefas, Mandelbrot e tapete, métricas reais | Funcionais; validar núcleos físicos/interpretação OO e capturas. T08–T10. |
| PB11 | P1 | Minicompilador MiniPar → ARM | Tokens/AST/TAC/símbolos/ARM reais; 22,-84,22 e arquivos regenerados | Implementado; CPUlator da etapa 3 observado, capturas finais pendentes. C01–C06. |
| PB12 | P1 | Web educacional e navegação integrada | Etapas reais, AST interativa, entrada, execução, downloads e seletor no mesmo Flask | Implementado/testado por API e JS; inspeção visual atual bloqueada. D06. |
| PB13 | P1 | Artefatos de engenharia | Pseudocódigos fiéis, três UMLs e testes de integração documentados | Produzidos nesta etapa; D01–D04/D07–D12. |
| PB14 | P2 | Demonstração acadêmica verificável | Capturas próprias, duas máquinas reais e identificação dos resultados | Roteiros prontos; execução presencial/capturas pendentes. D15/M16/C06. |
| PB15 | P2 | Relatório e publicação | Relatório final com capa/link e repositório contendo fontes/testes/documentos | Pendente etapa 5; D16/D17. Sem commit/push nesta auditoria. |
| PB16 | P1 | Resolver divergências formais | Decisão sobre int, OO dos exemplos e atualização XOR, com oráculos antes de alterações | Pendente de decisão/adequação posterior, sem refatoração nesta auditoria. M04/M17/T04. |

Referências: [matriz de conformidade](matriz-requisitos-2026.2.md),
[auditoria](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/auditoria-requisitos-2026.2.md) e
[reconstrução dos Sprint Backlogs](sprint-backlogs-2026.2.md).

O backlog distingue implementação, validação e entrega. Não se fecha PB07
apenas por localhost, PB08 por contar threads, PB11 por um emulador alternativo,
nem PB12 apenas por HTTP 200. Funcionalidades adicionais já existentes, como
divisão inteira ARM, não criam novos requisitos oficiais.
