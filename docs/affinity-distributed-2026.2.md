# Afinidade de processadores e execução distribuída

O MiniPar 2026.2 permite iniciar tarefas com `fork local`, selecionar um processador lógico com `on core(n)` e encaminhar funções globais a um processo trabalhador por TCP com `fork remote`.

## Sintaxe e comportamento

```minipar
func square(number value) -> number { return value * value; }
seq {
    var a = fork local square(7);
    var b = fork remote("127.0.0.1", 7000) square(8);
    var c = fork local square(9) on core(1);
    print(join(a), join(b), join(c));
}
```

`ForkExpr` e `TaskDestination` são representados na AST. O parser reconhece `on core(...)` no contexto do Fork. A análise semântica verifica o destino, o tipo da expressão de CPU e a independência do alvo. O gerador C++ encaminha a operação ao runtime de tarefas e afinidade.

Uma tarefa local é executada em thread nativa; o seletor `on core(n)` restringe a afinidade dessa thread antes da execução da função. Em Windows, o runtime utiliza `SetThreadGroupAffinity`; em Linux, possui implementação com `pthread_setaffinity_np`. A validação prática registrada ocorreu no Windows.

**Processador lógico não é necessariamente núcleo físico.** `on core(n)` seleciona um ID lógico permitido pelo sistema operacional, sem garantir exclusividade da CPU ou topologia física distinta.

## Verificação da afinidade

O exemplo [fork_join_affinity.minipar](../examples/fork_join_affinity.minipar) demonstra a solicitação de CPU e a verificação com `current_cpu()` e `available_cpus()`.

```powershell
py main.py examples/fork_join_affinity.minipar
$env:Path = 'C:\msys64\mingw64\bin;' + $env:Path
.\output\fork_join_affinity.exe
```

A máquina precisa disponibilizar os processadores lógicos usados no exemplo. Para verificações adicionais, utilize `py tools/validate_affinity.py` e os testes `tests/unit/test_affinity_frontend.py` e `tests/integration/test_affinity_native.py`.

## Trabalhador TCP

O destino remoto recebe a função e os argumentos serializados e executa somente funções incluídas no registro do programa compilado. O Join recebe o resultado ou propaga a falha. O trabalhador é outro processo e pode ser iniciado em localhost; o mecanismo aceita endereços de rede configurados para o destino.

```powershell
py main.py examples/fork_join_mixed.minipar
# Terminal 1
py tools/run_worker.py output/fork_join_mixed.exe --port 7000
# Terminal 2
$env:Path = 'C:\msys64\mingw64\bin;' + $env:Path
.\output\fork_join_mixed.exe
```

A demonstração local registra os resultados `49` e `64`. O ensaio entre dois computadores físicos pode ser realizado conforme [o roteiro de rede](demonstracao-duas-maquinas-2026.2.md); ele não integra as evidências de execução local apresentadas no relatório.

## Programas 8–10

Os três programas obrigatórios lançam quatro, cinco e seis tarefas, respectivamente. Os fontes permanecem independentes de IDs fixos de processador; o validador de afinidade pode gerar variantes temporárias com `on core(...)` para conferir a distribuição pelas CPUs lógicas disponíveis.

Mais detalhes: [runtime](runtime-2026.2.md), [programas paralelos](parallel-programs-2026.2.md) e [testes de integração](testes-integracao-2026.2.md).
