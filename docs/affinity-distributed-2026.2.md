# Afinidade explícita e demonstração distribuída — etapa 1/5

Revisão técnica de 11/11/2026. A arquitetura Python → AST → TAC/C++20 → G++
permanece. A extensão acrescenta afinidade a Fork local e usa o RPC já existente.
Não é o relatório acadêmico definitivo.

## Comparação com a referência consultada

O projeto principal está em `C:/GitHub/Minipar-2026.2`; a referência está
diretamente em `C:/GitHub/MiniPar-Referencia-Colega`, sem pasta intermediária.
Foram consultados BNF, lexer, parser, AST, semântico, TAC, codegen, template
C++ e testes de Fork/Join/hosts. O PDF do relatório do colega não foi analisado.
Nenhum arquivo da referência foi copiado para o projeto ou alterado. Seus
hashes estão no [controle de preservação](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/preservacao-afinidade-inicio.json).

| Aspecto | Referência | Decisão no MiniPar atual |
|---|---|---|
| Sintaxe | `fork f(...) on core(n)` ou `on host(ip, porta)` | Preservar `fork local` e `fork remote(host, porta)`; acrescentar apenas o sufixo local. |
| CPU | Numeração a partir de 1; `(core-1) % hardware_concurrency()` | Rejeitar remapeamento por módulo. Usar ID lógico do SO e máscara permitida ao processo. |
| API | `SetThreadAffinityMask` / `pthread_setaffinity_np` | Aproveitar o conceito de afinidade nativa por thread; código próprio em `src/runtime/affinity.hpp`. Windows usa API com grupo explícito. |
| Falha ao fixar | `__pin_to_core` devolve false, mas `__fork` ignora o retorno | Falhar explicitamente antes do corpo; exceção nativa vai ao mesmo future/Join. |
| RPC | Registro por nome/assinatura e serialização; falha do cliente usa `_Exit(1)`; servidor cria threads detached sem limite explícito | Conservar nosso protocolo com versão, hash do programa, ID da tarefa, codecs, enquadramento, prazos e limite de trabalhadores. Não introduzir um segundo runtime. |
| Isolamento | Lambdas com init-capture | Conservar os snapshots e canais explícitos existentes, já verificados em testes. |
| Evidência remota | Os testes consultados usam processos em localhost | Também distinguir essa validação de duas máquinas físicas. |

O nosso runtime já executava tarefas em trabalhador independente, retornava
resultados/exceções por Join e tratava conexão recusada, mensagens inválidas,
programa incompatível e interrupção do trabalhador. A mudança necessária era
a afinidade local verificável, não uma reimplementação de TCP.

## Sintaxe, semântica e implementação

```minipar
func quadrado(number n) -> number { return n * n; }
var tarefa1 = fork local quadrado(7) on core(0);
var tarefa2 = fork local quadrado(8) on core(1);
number resultado1 = join(tarefa1);
number resultado2 = join(tarefa2);
print(resultado1, resultado2);
```

Esse exemplo exige que os IDs 0 e 1 sejam permitidos ao processo. Não basta
a máquina informar dois processadores. Use `available_cpus()` para escolher
IDs realmente permitidos, como no exemplo completo abaixo.

- `on` e `core` são identificadores contextuais: o lexer existente já os
  reconhece, assim como parênteses e expressões. Nomes antigos `var core` e
  `var on` continuam válidos. O parser reconhece o sufixo sem ignorar sobras.
- `TaskDestination.core` guarda a expressão na AST. A serialização da Web
  educacional já percorre esse campo, sem redesenhar a interface.
- A semântica exige número inteiro não negativo, verifica referências/tipos
  e rejeita o sufixo em Fork remoto. A disponibilidade efetiva é dinâmica.
- O TAC emite `t = fork local on core(cpu), funcao, N`; os argumentos e o
  seletor são materializados no pai, na ordem textual.
- O C++ usa `fork_local_on` com uma tupla de argumentos seguida do seletor.
  A CPU solicitada não fica referenciada a uma variável mutável do pai.
- O runtime valida o ID antes de criar a tarefa. Na thread filha, aplica a
  afinidade, confere a CPU atual e registra `affinity_applied` antes de
  `task_start` e do corpo. Erros da API produzem `task_error` e exceção em Join.
- Sem o sufixo, o caminho antigo de `fork_local` não consulta nem configura
  afinidade. PAR, Fork remoto, snapshots, retornos e exceções continuam usando
  seus mecanismos anteriores.

`available_cpus()` retorna uma lista de IDs lógicos permitidos; `current_cpu()`
retorna o ID lógico observado na thread chamadora. Ambos têm aridade zero e
usam as chamadas comuns da linguagem. Não são palavras reservadas.

## O que significa core(n)

**Processador lógico não é núcleo físico.** SMT pode expor dois IDs no mesmo
núcleo; IDs consecutivos não provam núcleos distintos. A extensão não faz
descoberta de topologia nem promete isolamento físico, utilização contínua ou
aceleração. Afinidade limita onde a thread pode ser escalonada.

No Windows, o ID é `grupo * 64 + número`. São consultados
`GetProcessGroupAffinity` e `GetProcessAffinityMask`, e a thread é configurada
com `SetThreadGroupAffinity`; `GetCurrentProcessorNumberEx` confirma a CPU.
Esta versão aceita processo em **um único grupo**. Caso o processo abranja
mais de um grupo, informa indisponibilidade em vez de inferir máscaras de
outros grupos. Essa limitação importa especialmente em sistemas com mais de
64 processadores lógicos. Ver [grupos de processadores](https://learn.microsoft.com/en-us/windows/win32/procthread/processor-groups)
e [máscara do processo](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getprocessaffinitymask).

No Linux, a máscara vem de `sched_getaffinity(getpid(), ...)`, isto é, da
thread principal; um Fork aninhado não fica limitado à máscara já reduzida
da thread pai. `pthread_setaffinity_np` aplica a máscara unitária e
`sched_getcpu` confere o ID. A implementação usa `cpu_set_t`/`CPU_SETSIZE`;
se a máscara do sistema exceder esse limite, a consulta pode falhar e o erro
é propagado. Restrições de cpuset e mudanças concorrentes de configuração
também podem causar falhas. Ver [pthread_setaffinity_np](https://man7.org/linux/man-pages/man3/pthread_setaffinity_np.3.html)
e [sched_getaffinity](https://man7.org/linux/man-pages/man2/sched_getaffinity.2.html).

Em outros sistemas, pedidos e consultas de afinidade retornam erro explícito.
O Fork sem afinidade não depende dessas APIs. A ramificação Linux está
implementada, mas **NÃO FOI EXECUTADA** nesta sessão Windows. A consulta ao WSL
listou somente a distribuição interna `docker-desktop`, sem um ambiente Linux
de desenvolvimento usado na validação.

## Exemplo local adaptado aos processadores permitidos

Fonte: [fork_join_affinity.minipar](../examples/fork_join_affinity.minipar).

```minipar
func quadrado_na_cpu(number n, number cpu) -> list {
    require(current_cpu() == cpu, "CPU observada diferente da solicitada");
    return [n * n, current_cpu()];
}
seq {
    var cpus = available_cpus();
    print("PROCESSADORES_LOGICOS_PERMITIDOS", cpus);
    require(len(cpus) >= 2, "Esta demonstracao exige dois processadores logicos permitidos");
    var tarefa1 = fork local quadrado_na_cpu(7, cpus[0]) on core(cpus[0]);
    var tarefa2 = fork local quadrado_na_cpu(8, cpus[1]) on core(cpus[1]);
    print("RESULTADO_CPU_1", join(tarefa1));
    print("RESULTADO_CPU_2", join(tarefa2));
}
```

Na raiz do projeto, Windows/PowerShell, usando o ambiente do README:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock.txt
$env:MINIPAR_CXX = 'C:\msys64\mingw64\bin\g++.exe'
.\.venv\Scripts\python.exe main.py examples/fork_join_affinity.minipar affinity_demo
$env:PATH = (Split-Path $env:MINIPAR_CXX) + ';' + $env:PATH
$env:MINIPAR_TRACE = Join-Path (Get-Location) 'output/affinity-demo.tsv'
.\output\affinity_demo.exe
Get-Content .\output\affinity-demo.tsv
```

Confira os pares `requested=... actual=...` em `affinity_applied` e sua posição
anterior a `task_start`. A função também exige a igualdade dentro do corpo.
Com menos de dois IDs permitidos, esse exemplo informa a limitação; não
substitui a CPU solicitada por outra.

## Demonstração remota em A e B

Fonte próprio: [fork_join_network.minipar](../examples/fork_join_network.minipar).

```minipar
func quadrado_remoto(number n) -> number {
    print("TRABALHADOR executou quadrado de", n);
    return n * n;
}
seq {
    var host = get_env("MINIPAR_WORKER_HOST", "127.0.0.1");
    var porta = to_number(get_env("MINIPAR_WORKER_PORT", "7000"));
    var tarefa1 = fork remote(host, porta) quadrado_remoto(7);
    var tarefa2 = fork remote(host, porta) quadrado_remoto(8);
    number resultado1 = join(tarefa1);
    number resultado2 = join(tarefa2);
    print("CLIENTE recebeu", resultado1, resultado2);
}
```

Prepare Python/dependências e G++ em ambas as máquinas como no README. Compile
em A e transfira **esse mesmo executável** para `output/network_demo.exe` em B:

```powershell
.\.venv\Scripts\python.exe main.py examples/fork_join_network.minipar network_demo
$env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH
.\output\network_demo.exe --manifest
```

O executável precisa das DLLs do compilador compatível; o wrapper abaixo usa
a configuração de toolchain de B para preparar o PATH. Também é possível
compilar o mesmo fonte com a mesma versão do projeto em B. Compare o campo
`program=` dos manifests; mudar o IP pela variável de ambiente não altera esse
hash. Não misture versões do compilador/runtime.

**Em B**, use uma rede local confiável, identifique o IPv4 real e inicie:

```powershell
hostname
ipconfig
$env:MINIPAR_TRACE = Join-Path (Get-Location) 'output/network-worker.tsv'
.\.venv\Scripts\python.exe tools/run_worker.py output/network_demo.exe --host 0.0.0.0 --port 7000 --workers 4
```

O processo deve imprimir `MINIPAR_WORKER_READY` com PID, porta e hash reais.
`0.0.0.0` permite receber conexões da LAN; não é o endereço a configurar no
cliente. O padrão do runtime continua sendo localhost.

Se o firewall de B bloquear a porta, o administrador pode criar uma regra
temporária restrita à rede privada/sub-rede local, em PowerShell administrativo:

```powershell
New-NetFirewallRule -DisplayName 'MiniPar demonstracao TCP 7000' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 7000 -Profile Private -RemoteAddress LocalSubnet
# Depois da demonstracao:
Remove-NetFirewallRule -DisplayName 'MiniPar demonstracao TCP 7000'
```

Esses comandos de firewall **não foram executados** nesta sessão. Não exponha
o trabalhador à Internet: o protocolo atual não oferece autenticação ou TLS.

**Em A**, informe o IPv4 real de B, sem inventar um endereço:

```powershell
hostname
$env:MINIPAR_WORKER_HOST = Read-Host 'IPv4 real do computador B'
$env:MINIPAR_WORKER_PORT = '7000'
$env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH
$env:MINIPAR_TRACE = Join-Path (Get-Location) 'output/network-client.tsv'
.\output\network_demo.exe
Get-Content .\output\network-client.tsv
```

Em B, os prints `TRABALHADOR ...` e os eventos `worker_start/worker_end`
pertencem ao PID do trabalhador. Em A, `remote_result` informa esse PID,
enquanto o PID da linha de trace é o do cliente. Confira também os hostnames
e os dois equipamentos físicos. Resultado numérico isolado ou dois terminais
de monitoramento não comprovam distribuição física.

O ensaio automatizado usa localhost com processos independentes e duas
requisições reais. **Duas máquinas físicas NÃO FORAM VERIFICADAS. Localhost
não substitui essa verificação.**

## Testes 8, 9 e 10

Os fontes obrigatórios permanecem sem afinidade obrigatória e sem alterações
de algoritmo. Eles lançam quatro avaliadores (160 atividades, 40 por papel),
acrescentam Mandelbrot no Teste 9 e Sierpinski no 10. A barreira por mensagens
e os Joins existentes são mantidos.

O comando opcional abaixo consulta CPUs permitidas e gera em `output/` uma
cópia do fonte com **somente** os sufixos de afinidade nas chamadas locais,
usando posições dos tokens do lexer real. O fonte gerado percorre parser,
semântico, TAC, C++ e G++; os oráculos anteriores conferem seus resultados.
Com CPUs insuficientes, registra NÃO EXECUTADO e retorna falha, sem alterar os
testes padrão ou remapear IDs.

```powershell
.\.venv\Scripts\python.exe tools/validate_affinity.py
# Ou apenas uma demonstracao (4, 5 ou 6 CPUs logicas):
.\.venv\Scripts\python.exe tools/validate_affinity.py --program 8
.\.venv\Scripts\python.exe tools/validate_affinity.py --program 9
.\.venv\Scripts\python.exe tools/validate_affinity.py --program 10
```

Nesta execução, os IDs permitidos foram **0–15**. Os traces confirmaram
afinidades/CPUs observadas **0–3**, **0–4** e **0–5**, com todos os intervalos
das tarefas sobrepostos após a barreira. Isso confirma tarefas concorrentes
fixadas a IDs lógicos, sem afirmar núcleos físicos distintos.

| Teste fixado | Tempo SEQ (s) | Tempo PAR (s) | Speedup observado |
|---|---:|---:|---:|
| 8 | 0,022383 | 0,553756 | 0,04042 |
| 9 | 0,022000 | 0,558263 | 0,03941 |
| 10 | 0,026787 | 0,572191 | 0,04682 |

O paralelo foi **mais lento** nessa carga. Os tempos são medições reais, com
barreiras, mensagens e overhead; não foram ajustados para produzir aceleração.
Resultados completos, hashes dos fontes e eventos estão em
[afinidade-8910.json](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/afinidade-8910.json).

## Validação e arquivos

Alterados: `src/ast_nodes.py`, `parser.py`, `semantic.py`, `tac.py`, `codegen.py`,
`native_builtins.py`, `cpp_template.py`, `runtime/tasks.hpp` e BNF. Acrescentados:
`runtime/affinity.hpp`, dois exemplos, dois módulos de teste, o validador
opcional e esta documentação. O lexer existente é reutilizado sem reservar
novos nomes; o RPC e as três interfaces não receberam substituições.

Os 42 testes específicos cobrem frontend, selector dinâmico, precedência,
avaliação de argumentos, cópia de resultados, máscara real do processo,
exceções, falha nativa de configuração, barreiras, worker remoto, exemplos e
execução pelas duas APIs Web. No ensaio de restrição, o processo ficou limitado
à CPU 15 e rejeitou a CPU 0. O teste de falha nativa usa grupo Windows
inexistente: a API retornou erro 87 e o corpo não executou.

A tentativa inicial teve 25 aprovações, 11 erros de preparação e uma falha:
o novo fixture usava `receive` isolado (inválido na gramática já existente),
e uma máscara vazia não falhou na API deste Windows. Corrigiu-se o fixture
para atribuir `receive`, e o teste de falha passou a usar grupo inexistente.
Não foram alterados testes antigos nem seus resultados esperados. A segunda
execução aprovou 37 casos; após acrescentar exemplos/Webs, **42/42 passaram**.
As tentativas estão preservadas nos JUnits específicos.

Na regressão completa, **474 testes passaram em 450,87 s**, sem falhas,
erros, skips ou xfails: todos os 432 casos anteriores e 42 casos novos.
Os validadores separados também aprovaram os programas 1–7, os modos padrão
dos Testes 8–10 e oito expressões do Teste 11, com Assembly montado/emulado.
Os algoritmos anteriores, os testes existentes e as duas interfaces Web foram
conferidos por hashes; a referência consultada permanece intacta.

Evidências:

- [Tentativa inicial](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-afinidade-inicial.xml),
  [segunda execução](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-afinidade-segundo.xml),
  [42 casos específicos](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-afinidade-especifico.xml) e
  [suíte completa](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-afinidade-final.xml).
- [Observações nativas](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/afinidade-tests.json): CPU aplicada/observada,
  máscara restrita, erro real da API, PID do cliente e do trabalhador remoto.
- [Programas 1–7](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/validacao-afinidade-1a7.json),
  [8–10 sem afinidade](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/validacao-afinidade-8910-padrao.json),
  [8–10 com afinidade](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/afinidade-8910.json) e
  [Teste 11/ARM](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/afinidade-teste11/validacao.json).
- [CLI e interfaces](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/afinidade-interfaces.json): compilação pelo
  `main.py`, resultados `[49, 0]`/`[64, 1]`, inicialização do menu e HTTP 200
  nas duas páginas e APIs de catálogo. A suíte também compilou/executou código
  com afinidade pelas duas APIs. A inspeção visual de navegador não foi refeita.
- [Conferência final](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/afinidade-final.json): hashes dos 81 arquivos
  da referência e 57 arquivos anteriores de testes/exemplos/interfaces,
  comparação dos casos pytest, links e inclusão simulada no Git.

O ambiente de validação foi reproduzido fora do repositório com Python 3.14.3
e `pip install -r requirements-dev.lock.txt`, sem bibliotecas novas. Os ensaios
usaram G++ MSYS2 16.2.0. O ambiente temporário foi removido ao concluir os
ensaios, depois de conferir que nenhum processo o utilizava. Metadados de
perfil local/hostname nos relatórios foram
anonimizados, conservando resultados e erros. O CPUlator permanece
**NÃO VERIFICADO**; a validação ARM citada é Zig/LLVM + Unicorn Cortex-A9.

Não se iniciou a etapa 2/5, redesign das Webs ou relatório acadêmico definitivo.
Não foram feitos commits, push ou alteração de remoto.
