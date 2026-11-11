# Sprint Backlogs — reconstrução documental MiniPar 2026.2

> Material provisório preservado para revisão acadêmica posterior.

O PDF solicita Sprint Backlogs (p. 48, item 9). Não há registros suficientes
de planejamento Scrum formal, cerimônias, responsáveis, capacidade ou datas
de início/fim de sprints. Os grupos abaixo são uma **reconstrução documental**
das etapas verificadas, não uma afirmação de que esses sprints ocorreram.
Não se atribuem atividades a integrantes da equipe sem evidência.

O Git conserva a base MiniPar 2026.1, cujo HEAD local é
`36e25fc6234c95fd60cdadebd7ec22c65c5d7657` (15/06/2026, ajuste da BNF).
As evoluções 2026.2 estão no diretório de trabalho e em documentos/evidências;
não foram inventados commits para atribuir esses incrementos ao histórico.
As datas dos JUnits/relatórios são datas de execução, não durações de sprint.

| Grupo reconstruído | Objetivo e itens do Product Backlog | Atividades efetivamente registradas | Verificação/documento | Limitação histórica |
| --- | --- | --- | --- | --- |
| SB01 — Auditoria e base funcional | PB01/PB02 | Inventariar projeto/referências; localizar G++; estabelecer pipeline e pytest | `diagnostico-2026.2.md`, `evidencias/baseline-funcional.json`, `pytest-funcional.xml` | Falhas iniciais e xfail histórico não são reclassificados como aprovação. |
| SB02 — Gramática e representações | PB03/PB04/PB05 | Ampliar BNF, AST de Fork/Join, semântica, eliminar TAC fixo | `BNF-grammar.md`, `pytest-grammar.xml`, `fork-join-tac.json` | Novos reservados e restrições são explicitados; compatibilidade não significa aceitar todo Python. |
| SB03 — Runtime independente/TCP | PB06/PB07 | Snapshots, tasks/futures, Join, canais enquadrados, RPC/worker, erros | `runtime-2026.2.md`, `pytest-runtime.xml`, `runtime-tests.json` | Ensaios remotos são locais, sem prova de LAN física. |
| SB04 — Fidelidade dos algoritmos 1–7 | PB09 | Corrigir cálculos reais, treino, recomendação, Quicksort e acessos inválidos | `pytest-algorithms-complete.xml`, `validacao-1a7.json`, originais preservados | OOP/XOR ainda possuem divergências identificadas na auditoria final. |
| SB05 — Programas paralelos 8–10 | PB10 | 160 atividades, lotes, Mandelbrot, SVG Sierpinski, benchmark e oráculos | `parallel-programs-2026.2.md`, `pytest-8910-complete.xml` | Tempos reais, inclusive desaceleração; SVG não é Turtle. |
| SB06 — Aplicação minicompilador | PB11 | Implementar fases em MiniPar, ARM dinâmico, arquivos, montagem/emulação | `teste11-minicompilador.md`, `pytest-11-complete.xml` | CPUlator não foi executado naquele incremento inicial. |
| SB07 — Segunda interface Web | PB12 | Fachada de etapas, AST gráfica, símbolos, jobs e downloads | `web-educacional-2026.2.md`, `pytest-educacional-validado.xml` | Integração/API não prova qualidade visual. |
| SB08 — Organização e limpeza | PB01/PB15 | Comparar base Git, preservar interfaces, documentar remoção de materiais locais | `organizacao-2026.2.md`, `limpeza-git-2026.2.md` | Caches inacessíveis ignorados e não removidos à força; nenhuma publicação. |
| SB09 — Etapa 1/5, afinidade | PB08/PB10 | Aplicar/validar afinidade antes do corpo, exemplos e ensaios 4/5/6 IDs | `affinity-distributed-2026.2.md`, `pytest-afinidade-final.xml` | 474 testes; IDs lógicos, sem prova de cores físicos. |
| SB10 — Etapa 2/5, Web integrada | PB12 | Cabeçalho comum, passagem de fonte, filtros e exploração da AST | `web-integrada-2026.2.md`, `pytest-web-integrada-final.xml` | 481 testes; inspeção visual bloqueada. |
| SB11 — Etapa 3/5, CPUlator | PB11/PB14 | Comparar PDFs diretamente, gerar arquivos e executar os três casos no CPUlator | `teste11-cpulator-2026.2.md`, `teste11-etapa3/cpulator.json`, `pytest-teste11-etapa3.xml` em evidencias/ | 482 testes; capturas acadêmicas não foram exportadas como PNG. |
| SB12 — Etapa 4/5, auditoria/documentação | PB13/PB16 | Mapear requisitos/páginas, registrar lacunas, produzir pseudocódigos, UML, backlogs e roteiros | [auditoria atual](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/auditoria-requisitos-2026.2.md) e [matriz](matriz-requisitos-2026.2.md) | Documentação técnica, sem relatório acadêmico definitivo nem refatoração. |

## Backlog aberto de demonstração e entrega

As próximas ações são pendências, não atividades ficticiamente executadas:

1. Decidir com base no enunciado a adequação dos exemplos funcionais à
   orientação a objetos e a fidelidade da atualização XOR; avaliar o contrato int.
2. Demonstrar comunicação em duas máquinas Windows e registrar dados reais.
3. Confirmar a topologia física se a exigência de núcleos for interpretada
   literalmente, além da afinidade a processadores lógicos já demonstrada.
4. Executar o roteiro visual das interfaces e salvar capturas próprias.
5. Salvar as três capturas definitivas CPUlator e consolidar relatório/capa/link.
6. Fazer revisão de entrega e publicação somente na etapa 5 e conforme autorização.

Critérios de aceitação e prioridades: [Product Backlog](product-backlog-2026.2.md).
Não se inventaram pontos de história, burndown, reuniões ou métricas de equipe.
