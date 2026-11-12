# Product Backlog — MiniPar 2026.2

O Product Backlog reúne as funcionalidades implementadas na versão 2026.2. As prioridades indicam a importância técnica para a entrega, e os critérios de aceitação permitem relacionar cada item ao código e aos testes.

| ID | Prioridade | Funcionalidade | Critério de aceitação | Situação |
| --- | --- | --- | --- | --- |
| PB01 | Alta | Preservação da base MiniPar 2026.1 | Terminal, IDE Web e exemplos anteriores continuam disponíveis | Concluído |
| PB02 | Alta | Léxico, sintaxe, AST e BNF | Reconhecimento dos novos elementos, precedência e erros posicionados | Concluído |
| PB03 | Alta | Semântica e tabela de símbolos | Escopos, tipos, funções, classes e isolamento de tarefas validados | Concluído |
| PB04 | Alta | Geração de TAC e C++20 | Artefatos produzidos a partir da AST e executável compilado com G++ `-O3` | Concluído |
| PB05 | Alta | SEQ, PAR, Fork e Join | Tarefas nativas, sincronização, retorno de valores e propagação de erros | Concluído |
| PB06 | Alta | Canais TCP e trabalhador remoto | Comunicação por mensagens e Fork remoto entre processos | Implementado e validado em localhost |
| PB07 | Alta | Afinidade de processador | `on core(n)` validado e aplicado a processador lógico permitido | Concluído no Windows |
| PB08 | Alta | Testes 1–7 | Calculadora, fatorial/Fibonacci, redes neurais, recomendação e Quicksort | Concluído |
| PB09 | Alta | Testes 8–10 | Avaliação de 160 atividades, Mandelbrot e Sierpinski | Concluído |
| PB10 | Alta | Teste 11 | Minicompilador escrito em MiniPar, geração ARMv7 e três expressões verificadas | Concluído |
| PB11 | Alta | Web educacional integrada | Tokens, AST interativa, semântica, símbolos, TAC, C++ e execução | Concluído |
| PB12 | Média | Documentação e entrega | BNF, pseudocódigos, UML, relatório técnico e evidências | Concluído |

A organização dos incrementos está descrita em [Sprint Backlogs](sprint-backlogs-2026.2.md). O relatório acadêmico reúne a apresentação e os resultados gerais em [Relatorio-Minipar2026.2.pdf](Relatorio-Minipar2026.2.pdf).
