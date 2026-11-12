# Runtime de execução — MiniPar 2026.2

O runtime em C++20 fornece as operações usadas pelo código nativo gerado: execução sequencial e paralela, Fork/Join, cópia de valores entre tarefas, canais TCP, trabalhador remoto e afinidade de processador lógico.

## Componentes

| Arquivo | Função principal |
| --- | --- |
| `src/runtime/tasks.hpp` | Tarefas locais, sincronização, resultados e Join |
| `src/runtime/snapshot.hpp` | Cópia dos dados transferidos às tarefas |
| `src/runtime/channel.hpp` | Canais `c_channel`, `send` e `receive` |
| `src/runtime/net.hpp` | Recursos de socket e transporte |
| `src/runtime/wire.hpp` | Representação e serialização de mensagens |
| `src/runtime/rpc.hpp` | Fork remoto e execução por trabalhador |
| `src/runtime/affinity.hpp` | Afinidade de threads e consulta à CPU lógica |

## Modelo de execução

- **`seq`** executa comandos em sequência.
- **`par`** inicia seus filhos como tarefas concorrentes e sincroniza o término antes de prosseguir.
- **`fork local`** inicia uma função global em uma tarefa nativa e devolve um identificador do tipo `task`.
- **`join`** aguarda a tarefa e recupera o resultado ou propaga o erro.
- **`fork remote(host, porta)`** envia função e argumentos ao trabalhador TCP compatível com o programa compilado.
- **`on core(n)`** seleciona um processador lógico válido para a tarefa local.

A independência das tarefas é tratada no compilador pela análise semântica e no runtime por cópias dos dados de entrada (snapshots). A comunicação explícita entre tarefas ocorre pelos canais previstos na linguagem.

## Compilação e execução local

O compilador Python gera C++20 a partir da AST validada, sem interpretar diretamente o TAC. O G++ é chamado com otimização `-O3` e suporte a threads.

```powershell
py main.py examples/fork_join_local.minipar
$env:Path = 'C:\msys64\mingw64\bin;' + $env:Path
.\output\fork_join_local.exe
```

## Fork remoto em localhost

```powershell
py main.py examples/fork_join_mixed.minipar
# Terminal do trabalhador
py tools/run_worker.py output/fork_join_mixed.exe --port 7000
# Terminal do cliente
$env:Path = 'C:\msys64\mingw64\bin;' + $env:Path
.\output\fork_join_mixed.exe
```

O exemplo processa `square(7)` localmente e `square(8)` remotamente, retornando `49` e `64`. O trabalhador deve usar um executável correspondente ao programa do cliente. O protocolo utiliza sockets TCP, mensagens estruturadas, prazos e propagação de falhas. Não há fallback silencioso para execução local quando o worker não está acessível.

## Afinidade

O runtime aplica a afinidade antes da execução do corpo da tarefa. No Windows, usa `SetThreadGroupAffinity`; a implementação Linux utiliza `pthread_setaffinity_np`. A validação documentada foi realizada no Windows. IDs são de **processadores lógicos**; não é assumida correspondência direta com núcleos físicos.

## Verificação

```powershell
py -m pytest tests/integration/test_runtime.py tests/integration/test_affinity_native.py
py tools/validate_programs.py
py tools/validate_parallel.py
```

A comunicação entre processos distintos foi observada em localhost. O roteiro para uma eventual demonstração em LAN está em [demonstracao-duas-maquinas-2026.2.md](demonstracao-duas-maquinas-2026.2.md).
