# Testes de integração do MiniPar 2026.2

> Material provisório preservado para revisão acadêmica posterior.

**Revisão de int/XOR/OO:** 519 testes aprovados em 497,90 s, incluindo os 482
publicados e 37 novos. [Resultado final](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/conformidade-resultados.json)
e [comparação técnica](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/revisao-conformidade-2026.2.md). Os testes novos cobrem
int64 desde símbolos/TAC/C++ até operações/objetos/Fork/Join local e remoto,
gradiente numérico dos 13 parâmetros XOR e estado independente dos objetos
3–6. Nenhum teste anterior teve sua expectativa alterada. Os números das
seções originais abaixo preservam o snapshot da auditoria anterior.

Documento do item 13 da página 48 do PDF. Fonte de resultados: execuções reais
de pytest e validadores; [auditoria atual](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/auditoria-requisitos-2026.2.md)
consolida contagens, comandos, versões e limitações desta etapa. Resultados
anteriores são históricos e não substituem a regressão atual.

## Execução da auditoria de 11/11/2026

A suíte completa aprovou **482 casos em 467,88 s**, sem falhas, erros, skips ou
xfails: [JUnit](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-auditoria-etapa4.xml) e
[comparação de regressão](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/regressao-auditoria-etapa4.json).
Os validadores separados aprovaram [1–7](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/auditoria-etapa4-1a7.json),
[8–10](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/auditoria-etapa4-8910.json),
[afinidade 4/5/6 lógica](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/auditoria-etapa4-afinidade.json) e
[oito casos ARM do Teste 11](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/auditoria-etapa4-teste11/validacao.json).
Todos recompilaram/rodaram artefatos reais. A auditoria registra os tempos,
a desaceleração dos benchmarks e as divergências que os oráculos não cobrem.
O [servidor HTTP real](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/auditoria-etapa4-http.json) também respondeu,
sem aprovação visual do navegador.

## Contratos entre componentes

| Integração | Testes existentes | Verificação real e limite |
| --- | --- | --- |
| Lexer → Parser | `tests/unit/test_frontend.py`, `test_tasks_grammar.py` | Tokens produzidos pelo Lexer entram no Parser; posição, precedência, comentários e entradas inválidas. |
| Parser → AST | `test_tasks_grammar.py`, `test_affinity_frontend.py` | Tipo/campos dos nós, argumentos, destino, seletor de CPU, handle e localização; tokens desconhecidos/EOF inválido rejeitados. |
| AST → Semântica | `test_semantic_2026_2.py`, `test_types_1a7.py` | Escopos, chamadas, tipos conhecidos, contextos this/return e herança; var/unknown não equivale a prova completa. |
| Semântica → Símbolos | `test_frontend.py`; `test_real_semantics_scopes_signatures_and_diagnostics` em `test_educational_web.py` | Declarações, busca de escopo, assinaturas, histórico e tabela JSON refletem o analisador real. |
| AST/compilador → TAC | `test_tac_2026_2.py`, `test_tac_programs_1a7.py` | Laços, continue, curto-circuito, chamadas/métodos, for-in e criação/sincronização explícita de tarefas. Renomear Quicksort não preserva um TAC fixo. |
| AST/semântica → C++ | `test_generation.py`, `test_task_pipeline.py`, `test_educational_web.py` | C++ vem do mesmo Program e contexto semântico; equivalência dos geradores nas interfaces e proibição de produzir artefatos após erros. |
| TAC e backend | `test_cli_generates_tac_cpp_and_binary`, `test_tac_and_cpp_are_exact_outputs_of_existing_generators` | O compilador entrega os dois artefatos coerentes com a AST. **Não há tradutor de texto TAC para C++**; os dois geradores são ramos sobre a AST validada. |
| C++ → G++ → binário | `tests/integration/test_native.py`, `test_programs_1a7.py` | Subprocessos reais, C++20/-O3, retorno/stderr, execução e stdin. Falha de compilação/compilador ausente não é simulada como sucesso. |
| Backend → Runtime paralelo | `test_runtime.py` | Threads reais, barreiras, snapshots de valores/objetos, retornos copiados, exceções e aninhamento de tarefas. |
| Canais TCP | `test_runtime.py`, Teste 1 e drivers 1–7 | Socket real, enquadramento, ACK, timeout, mensagens inválidas/truncadas; não são mocks de send/receive. |
| RPC → Trabalhador → Join | `test_runtime.py`, `test_programs_8910.py`, `test_affinity_native.py` | Processos locais distintos, registry/manifest, serialização, resultados e falhas, sem fallback silencioso para execução local. Não prova duas máquinas físicas. |
| Afinidade → corpo → Join | `test_affinity_native.py`, `test_affinity_frontend.py` | CPU aplicada antes do corpo, solicitação/observação, máscara permitida e propagação de erro. CPU lógica não é core físico. |
| IDE original → compilador | `test_web.py`, `test_task_pipeline.py`, `test_minicompiler.py` | API chama main.py em subprocesso, obtém TAC/C++, executa com entrada e oferece artefatos reais. |
| Educacional → pipeline → G++ | `test_educational_web.py`, `test_web_unified.py` | Cinco fases, AST completa, diagnósticos, jobs isolados, stdin, códigos de saída, limites de saída, downloads e afinidade real. |
| Navegação e apresentação JS | `tests/web/unified-web.test.cjs`, invocado por `test_web_unified.py` | Dez verificações de passagem da fonte, storage, filtros, geometria da AST real e zoom. Ambiente de teste de eventos não é navegador visual. |
| MiniPar → aplicação Teste 11 → ARM | `test_minicompiler.py`, `test_minicompiler_delivery.py` | Execução nativa, tokens/AST/TAC/símbolos, arquivo regravado, Zig/LLVM e Unicorn. CPUlator possui evidência separada da etapa 3. |

Os nomes curtos na coluna de testes pertencem a `tests/unit/` para frontend,
semântica/geração, e a `tests/integration/` para Web/runtime/programas. Nenhum
teste foi excluído ou teve seu resultado esperado alterado nesta auditoria.

## Comandos reproduzíveis

Na raiz, com G++ C++20 e dependências do README. Node é necessário para os dez
casos de apresentação; sua ausência gera skip explícito no teste Python.

```powershell
python -m pytest
# Seleções úteis para uma demonstração dirigida:
python -m pytest tests/integration/test_runtime.py tests/integration/test_affinity_native.py
python -m pytest tests/integration/test_web.py tests/integration/test_educational_web.py tests/integration/test_web_unified.py
python tools/validate_programs.py --report output/validacoes/auditoria-etapa4-1a7.json --output output/auditoria-etapa4-1a7
python tools/validate_parallel.py --report output/validacoes/auditoria-etapa4-8910.json --output output/auditoria-etapa4-8910
python tools/validate_affinity.py --report output/validacoes/auditoria-etapa4-afinidade.json --output output/auditoria-etapa4-afinidade
python tools/validate_minicompiler.py --report output/validacoes/auditoria-etapa4-teste11/validacao.json
```

As seleções dirigidas são comandos de reprodução; a suíte completa inclui esses
mesmos casos e é o registro de execução desta auditoria, sem somá-los duas vezes.
Os quatro validadores acima são executados separadamente com suas medições.

`validate_programs` usa entradas definidas e oráculos para os Testes 1–7.
`validate_parallel` confere cobertura das 160 atividades, quatro papéis,
matrizes/ASCII/geometria dos fractais e relações aritméticas das métricas.
`validate_affinity` cria cópias temporárias com on core, mantendo os fontes.
`validate_minicompiler` monta e emula os ARM que a aplicação MiniPar produz.

## O que as evidências não demonstram

- Passar nos oráculos funcionais não resolve automaticamente a fidelidade
  literal ao algoritmo XOR, o contrato int ou a interpretação OO dos exemplos.
- Um benchmark pode ter speedup menor que 1. Não há exigência de repetir
  tempos publicados em outro computador/linguagem; o PDF também exibe desaceleração.
- Barreiras asseguram tarefas vivas sobrepostas, incluindo esperas; não provam
  uso simultâneo contínuo de cores físicos nem utilização de 100% de CPU.
- HTTP/API e testes JavaScript não aprovam legibilidade, cliques/arrasto ou
  downloads no navegador. O roteiro visual permanece obrigatório.
- Testes locais de TCP e PIDs diferentes não substituem ensaio presencial
  distribuído. Timeout de Join não significa cancelamento de tarefa.
- O CPUlator foi observado na etapa 3 para três arquivos; os novos testes
  Zig/Unicorn desta auditoria não são uma nova execução CPUlator.

Veja [matriz](matriz-requisitos-2026.2.md),
[roteiro de capturas](roteiro-capturas-2026.2.md) e
[duas máquinas](demonstracao-duas-maquinas-2026.2.md).
