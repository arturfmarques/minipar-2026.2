# Runtime MiniPar 2026.2

Implementação validada em 10/11/2026: Windows 11, Python 3.14.3 e MSYS2 G++
16.2.0. Fork/Join executam código C++ nativo. Os testes usam processos TCP
distintos em localhost. Não houve validação entre duas máquinas físicas nem
execução em Linux. A arquitetura Python → lexer → parser → AST → semântica →
TAC/C++ → G++ foi preservada; o TAC continua textual, sem executor próprio.

## Compilar e executar

Use o ambiente Python já preparado, ou instale `requirements-dev.lock.txt`
num ambiente virtual. `MINIPAR_CXX`/`CXX` selecionam o compilador, sem flags no
valor. Não é necessário instalar bibliotecas C++ adicionais.

```powershell
$env:MINIPAR_CXX = 'C:\msys64\mingw64\bin\g++.exe'
.\.venv\Scripts\python.exe main.py examples/fork_join_local.minipar
$env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH
.\output\fork_join_local.exe
```

O exemplo local imprime `49`. O CLI compila; a execução é um comando separado.
Menu e interface Flask original continuam usando o mesmo compilador e
preparam o PATH das DLLs. A opção `--tac-only` permanece disponível e não usa
G++ nem rede. Erros impeditivos de análise impedem código nativo novo.

Exemplo com dois destinos, sem alteração da sintaxe:

```minipar
func square(number n) -> number { return n * n; }
var a = fork local square(7);
var b = fork remote("127.0.0.1", 7000) square(8);
number x = join(a);
number y = join(b);
print("x =", x);
print("y =", y);
```

```powershell
.\.venv\Scripts\python.exe main.py examples/fork_join_mixed.minipar
# Terminal trabalhador (mantém o processo aberto):
.\.venv\Scripts\python.exe tools/run_worker.py output/fork_join_mixed.exe --port 7000
# Outro terminal, com o PATH das DLLs preparado:
.\output\fork_join_mixed.exe
```

Resultado real registrado: `x = 49` e `y = 64`, cliente PID 5440 e trabalhador
PID 28992; ambos retornaram 0. Veja [runtime-demo.json](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/runtime-demo.json).
Para repetir a demonstração com compilação, trabalhador e cliente coordenados:

```powershell
.\.venv\Scripts\python.exe tools/demo_runtime.py
```

A demonstração usa a porta 7000 e falha explicitamente se ela estiver ocupada.
Não calcula os resultados em Python; apenas compila, inicia e observa os executáveis.

## Organização e escolha de concorrência

`src/cpp_template.py` incorpora os arquivos de `src/runtime/` no C++ emitido.
O `.cpp` gerado é autossuficiente: não depende de include paths deste projeto.

| Arquivo | Responsabilidade |
|---|---|
| `src/codegen.py` | Tradução da AST, tipos, snapshots de campos, PAR e registro de chamadas remotas. |
| `net.hpp` | Sockets RAII, framing, deadlines, IPv4, portas e trace. |
| `channel.hpp` | Descritores de canais, inbox persistente, fila e confirmação de envio. |
| `snapshot.hpp` | Cópia profunda de argumentos/resultados e campos de objetos locais. |
| `tasks.hpp` | Identificadores, async, shared_future, grupos e Join. |
| `wire.hpp` | Codificação binária tipada e validação de mensagens. |
| `rpc.hpp` | Cliente remoto, trabalhador, registro e protocolo MiniParRPC/1. |
| `affinity.hpp` | Consulta de IDs lógicos permitidos e afinidade explícita por thread. |

Foi escolhido `std::async(std::launch::async)` porque fornece execução em uma
thread real, resultado tipado e transporte de exceções sem uma fila manual
de promises. Não há `std::launch::deferred`. A função não espera o Join para
começar. As threads podem ocupar múltiplos núcleos conforme o escalonador;
criação de threads não garante afinidade a núcleos específicos.

Afinidade opcional foi acrescentada na etapa 1/5 com `fork local f(...) on
core(n)`. Máscaras do processo são verificadas; falhas não provocam remapeamento
silencioso. Os limites de grupos Windows, a implementação Linux e as evidências
de CPU observada estão no [manual de afinidade](affinity-distributed-2026.2.md).
Os testes de barreira sem esse sufixo continuam demonstrando sobreposição,
sem usar speedup como prova de afinidade.

## Handles, Join e finalização

1. Os argumentos são avaliados na ordem textual e copiados antes do lançamento.
2. Cada tarefa recebe ID formado por PID, nonce do processo e contador atômico.
3. O grupo da execução mantém seu estado vivo mesmo se o handle sair de escopo.
4. Join valida o handle, aguarda o future e entrega o resultado tipado ou erro.
5. Aliases e joins repetidos usam o mesmo shared_future. O resultado permanece
   armazenado e cada coleta produz um snapshot; alterar uma lista coletada
   não altera a próxima coleta. Tarefas void são aguardadas como comando.
6. Ao finalizar o main, tarefa filha ou requisição remota, o grupo aguarda
   todos os filhos. Erros de tarefas sem Join também falham a execução normal.

Exceções de tarefas incluem ID e função; o main imprime `ERRO RUNTIME` e
retorna 1. Handle não inicializado falha em runtime; nome inexistente ou tipo
incompatível falha na semântica. Auto-Join é rejeitado pelo runtime.

Join tem timeout configurável e sockets têm deadlines finitos. Isso não é
cancelamento: uma função CPU com laço infinito não pode ser interrompida com
segurança por future/async. A finalização aguarda sua thread, podendo continuar
bloqueada. Não há cancelamento remoto, recuperação de worker perdido ou
detecção geral de ciclos de dependência. Use funções finitas e comunicação
com timeout; não se promete ausência geral de deadlocks.

## Isolamento e PAR

Fork usa lambdas sem capturas de variáveis do chamador. Listas e matrizes
são copiadas; instâncias locais são clonadas recursivamente pelos campos
conhecidos, preservando aliases/ciclos de objetos de tipo estático no mesmo
snapshot. Descritores de canal são copiados, mantendo comunicação explícita
por mensagens. Métodos que usam `this` dentro de PAR recebem uma cópia do objeto.

PAR lança tarefas void com capturas explícitas por snapshot e sincroniza todas
ao final do bloco. Não usa `[&]` para compartilhar variáveis do programa.
As verificações semânticas existentes continuam rejeitando escrita em estado
externo e dependências globais transitivas nas tarefas independentes.

Não há clone polimórfico geral nem serialização de objetos remotos. Uma
referência tipada como base não promete preservar o estado extra de subclasses.
Handles não podem ser passados como argumentos/retornos ou dentro de coleções.
Entrada de terminal dentro de tarefas continua uma interação com o mesmo stdin;
prefira argumentos e canais para a comunicação entre tarefas.

## Trabalhadores e funções autorizadas

O mesmo binário tem três modos:

```powershell
.\output\fork_join_mixed.exe --manifest
.\output\fork_join_mixed.exe --worker --host 127.0.0.1 --port 7000 --workers 8
.\output\fork_join_mixed.exe
```

`--manifest` lista hash SHA-256 do programa, protocolo e assinaturas remotas.
O gerador registra somente funções/assinaturas efetivamente usadas por Fork
remote na AST. O hash deriva do C++ completo, inclusive runtime, excluindo o
próprio campo do hash. Fontes/runtime diferentes são rejeitados. O nome do
arquivo não integra o hash; CLI e Web geram a mesma identidade para a mesma fonte.

O trabalhador entra antes das instruções principais do programa. Ao receber
uma requisição, procura o handler pré-compilado no registro fechado, decodifica
argumentos e chama essa função. Não há shell, eval, import dinâmico ou execução
de código recebido. O cliente remoto executa somente o transporte; a função
solicitada é calculada no processo trabalhador.

`--workers` aceita 1 a 64 requisições simultâneas (padrão 8).
`--max-requests N` encerra após N conexões aceitas e aguarda os handlers; 0 é
ilimitado. Conexões inválidas também contam. `--port 0` escolhe porta efêmera,
útil nos testes. A linha `MINIPAR_WORKER_READY` fornece JSON com host, porta,
PID e hash. Escuta padrão: apenas `127.0.0.1`.

O hash identifica a versão autorizada, não autentica pessoas e não é segredo.
Não há autenticação, TLS nem controle de acesso por usuário. Exponha o serviço
somente em rede confiável, usando firewall para limitar os clientes.

## Dois computadores na mesma rede (procedimento ainda não executado)

1. Compile uma única fonte com Fork remote apontando para o IPv4 real do
   trabalhador. Não use localhost para designar outro computador.
2. Em sistemas iguais, copie o mesmo binário ao trabalhador. Em sistemas
   diferentes, compile o mesmo `.cpp` autossuficiente com C++20/pthreads e,
   no Windows, Winsock `-lws2_32`. Compare `--manifest` nos dois lados.
3. No MSYS2 dinâmico, disponibilize `libstdc++-6.dll`, `libgcc_s_seh-1.dll` e
   `libwinpthread-1.dll` compatíveis ao lado do executável ou no PATH. O
   trabalhador nativo não precisa do Python nem do repositório.
4. Inicie `programa.exe --worker --host 192.168.1.20 --port 7000` no computador
   correspondente. A exposição exige esse host explícito; o padrão é loopback.
5. Libere somente a porta e os clientes necessários no firewall local. Execute
   o cliente e observe os traces de ambos, usando arquivos distintos.
6. Se houver canais de retorno entre computadores, configure também
   `MINIPAR_CHANNEL_BIND` no receptor para seu IPv4 e use o IP desse receptor
   no descritor enviado. Canais não fazem descoberta automática.

Somente endereços IPv4 numéricos e `localhost` são aceitos; não há DNS genérico
nem IPv6. Canais/task endpoints exigem porta inteira de 1 a 65535. A porta 0
é exclusiva da opção de escuta do trabalhador.

## Protocolo e confiabilidade

TCP é um stream. Todo frame começa com `u32` big-endian de tamanho e tem
exatamente esse número de bytes. Loops completam envios/recebimentos parciais;
EOF, reset, timeout e tamanho excessivo são erros. Cada string/campo binário
usa também tamanho `u32` e bytes, preservando UTF-8 e NUL. Readers rejeitam
campos truncados, tipo errado e bytes excedentes.

Requisição RPC: seis campos, nesta ordem:

| Campo | Conteúdo |
|---|---|
| versão | `MiniParRPC/1` |
| programa | SHA-256 do código compilado |
| tarefa | ID único |
| função | Nome da função registrada |
| assinatura | Tipos dos argumentos, separados por vírgula |
| argumentos | `u32` aridade e sequência de valores tipados |

Resposta: versão, programa do worker, tarefa, estado `ok`/`error`, PID do
worker e corpo binário. Em sucesso, corpo contém valor tipado (ou tag void);
em erro, mensagem. O cliente verifica versão, programa, ID, estado e tipo do
retorno. A requisição inteira é validada antes da chamada da função.

Valores: tag string `number` seguida de 8 bytes IEEE-754 double em ordem de
rede; `bool` seguida de um byte; `string` seguida de tamanho/bytes;
`list(T)` seguida de contagem e elementos tipados; `c_channel` com host/porta.
Inteiros MiniPar tornam-se number no transporte. Coleções são recursivas;
o backend resolve listas/matrizes numéricas nos argumentos, e o runtime pode
transportar coleções tipadas de outros codecs quando o C++ tem o tipo concreto.
Objetos e argumentos desconhecidos sem codec são rejeitados pelo backend.

Canais usam o mesmo framing de rede para o conteúdo textual legado, com ACK
framed `OK`. Há listener persistente por porta, fila protegida e timeout no
receive. O emissor pode aguardar o listener iniciar dentro do prazo de conexão.
Porta ocupada por outro processo falha explicitamente; sockets usam RAII.
O protocolo de canais mudou: todos os pares devem usar o runtime novo. Não
há compatibilidade de wire com binários antigos sem enquadramento.

## Configuração e observação

| Variável | Padrão | Efeito |
|---|---:|---|
| `MINIPAR_TIMEOUT_MS` | 10000 | Deadline de I/O e espera de receive. |
| `MINIPAR_CONNECT_TIMEOUT_MS` | 3000 | Conexão TCP; canais podem tentar novamente nesse prazo. |
| `MINIPAR_JOIN_TIMEOUT_MS` | 30000 | Espera explícita de Join; não cancela a tarefa. |
| `MINIPAR_MAX_FRAME_BYTES` | 16777216 | Limite de frame; configuração de 64 a 134217728 bytes. |
| `MINIPAR_CHANNEL_BIND` | 127.0.0.1 | Endereço de escuta dos canais. |
| `MINIPAR_TRACE` | desativado | Caminho do arquivo TSV de eventos. |

Timeouts aceitam 1 a 600000 ms. Configurações numéricas inválidas falham.
Clientes e trabalhadores devem usar limites de frame compatíveis.
O decoder limita contagem de elementos a um milhão, além do limite de frame.

```powershell
$env:MINIPAR_TRACE = 'output/cliente.tsv'
.\output\fork_join_mixed.exe
```

Use outro caminho no terminal trabalhador. Campos TSV: evento, PID, ID de
tarefa, microssegundos de relógio monotônico e detalhe. Eventos incluem spawn,
task_start/end/error, join_begin/end, worker_start/end/error e remote_result
(contém PID do worker). Relógios monotônicos de máquinas distintas não são
comparáveis diretamente. Mutex protege gravações de threads no mesmo processo;
um único arquivo entre processos não tem coordenação global.

## Testes reais e limites da validação

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe tools/run_baseline.py --report output/validacoes/baseline-runtime.json
```

`tests/integration/test_runtime.py` compila o programa MiniPar da fixture e
executa C++ nativo em cada cenário; Python apenas controla processos/barreiras,
valida bytes e compara saídas. [runtime-tests.json](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/runtime-tests.json)
registra observações e traces; [pytest-runtime.xml](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-runtime.xml)
é a contagem da suíte. Testes de erro exigem falha real, não resultados fixos.

| Requisito | Evidência automatizada |
|---|---|
| A, D | Fork square e Join numérico, valores reais. |
| B, C | Duas/quatro tarefas chegam a barreiras antes da liberação; intervalos sobrepostos. |
| E | Listas, matriz remota e coletas repetidas com cópias independentes. |
| F | Conversão inválida em tarefa local/remota e erro de tarefa não coletada. |
| G | Handle não inicializado em runtime e identificadores/tipos inválidos na semântica. |
| H, I | Cliente e worker com PIDs distintos; worker_start/end e remote_result correlacionados. |
| J | Conexão recusada, endpoint inválido, peer sem resposta e worker encerrado no meio da função. |
| K | Local 49 e remoto 64 na mesma execução, inclusive via Flask original. |
| L | Suíte anterior, SEQ/PAR, recursão, isolamento de objetos, canais com mensagens repetidas. |
| M | RPC string UTF-8/NUL e canal com conteúdo acima de 4096 bytes. |
| N | Gate rápido liberado enquanto tarefa lenta permanece bloqueada; Join rápido termina primeiro. |

Também se verificam programa/função/assinatura/tipo não autorizados, frames
incompletos/excessivos, conflito de porta e finalização com tarefa pendente.
O programa principal imprime FORKED antes da liberação das barreiras: Fork não
bloqueia a execução principal. As comparações de tempo são do trace do mesmo
processo e não pressupõem speedup nem CPU fixada.

Os 11 exemplos anteriores compilam e executam com código 0 após a validação
dos algoritmos. A pilha do Teste 7 foi corrigida e os sete obrigatórios têm
resultados matemáticos conferidos; veja a [seção 14 do diagnóstico](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/diagnostico-2026.2.md#14-validação-funcional-dos-programas-1-a-7).
Os relatórios históricos preservam a antiga falha 3221226356. Retorno zero
isolado continua insuficiente para certificar resultados.

O sandbox restringiu testes de sockets/processos; a rodada externa autorizada
é registrada separadamente, com a falha do sandbox preservada. Não foram
testados nessa rodada original: duas máquinas físicas, execução Linux, afinidade de CPU, desconexões
em todas as fases possíveis ou cargas hostis prolongadas. Não há escalonador
distribuído, retentativa idempotente ou persistência após queda. Os programas
MiniPar 8-10 foram acrescentados depois desta etapa e estão documentados em
[parallel-programs-2026.2.md](parallel-programs-2026.2.md). Teste 11 e segunda
interface Web continuavam pendentes nessa rodada; já foram implementados nas
etapas seguintes. Afinidade Windows foi validada na etapa 1/5 acima; Linux e
duas máquinas físicas continuam sem validação nativa.
