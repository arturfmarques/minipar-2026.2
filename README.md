# Compilador MiniPar
Trabalho de Compiladores - UFAL 

Último estado validado: **519 testes automatizados**. Relatórios transitórios
são gerados em `output/validacoes/`, ignorado pelo Git.

### Três formas de usar o MiniPar 2026.2

- Terminal: `python main.py`, opção **1**.
- IDE Web original: `python app.py`, em **http://127.0.0.1:5000/**.
- [Laboratório educacional](docs/web-educacional-2026.2.md): no mesmo servidor,
  **http://127.0.0.1:5000/educacional**. Mostra tokens, AST interativa,
  semântica e símbolos, TAC, C++20, compilação, execução e downloads reais.

A nova interface usa o compilador existente e diretórios separados por
compilação/execução. Execute apenas programas confiáveis no servidor local.
A demonstração histórica das três expressões no CPUlator está descrita no
[guia de apresentação](docs/teste11-cpulator-2026.2.md); as capturas finais
permanecem pendentes. Afinidade e execução distribuída estão no
[manual de uso](docs/affinity-distributed-2026.2.md). As duas Webs preservam a
fonte ao alternar IDE | Educacional; inspeção visual final, Linux e duas
máquinas físicas ainda dependem de validação manual.

### Teste 11: minicompilador de expressões em MiniPar

`tests/teste11_minicompilador_armv7.minipar` implementa Lexer, Parser, AST,
tabela de símbolos, TAC, avaliação e geração ARMv7 em classes MiniPar.
As três expressões obrigatórias produziram **22, -84 e 22**, confirmados
também em `r0` por montagem Zig/LLVM e execução Unicorn Cortex-A9.
**CPUlator: verificação histórica aprovada nas três expressões obrigatórias**, em execução real
ARMv7 DE1-SoC com os nossos `.arm`, mantendo o resultado em `r0`.

```powershell
python -m pip install -r requirements-dev.lock.txt
python main.py tests/teste11_minicompilador_armv7.minipar
$env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH
'((2+4)*7)-(5*4)' | .\output\teste11_minicompilador_armv7.exe
python tools/validate_minicompiler.py
python -m pytest
```

O arquivo padrão é `output/teste11-expressao.arm`; `MINIPAR_ARM_OUTPUT`
permite escolher outro caminho `.arm`. A Web original oferece seu download.
O backend ARM exige valores intermediários inteiros assinados de 32 bits;
erros e resultados fracionários são diagnosticados, sem gerar ARM inválido.
Veja [arquitetura, resultados e limites](docs/teste11-minicompilador.md),
[arquivos ARM e saídas canônicas](docs/evidencias/teste11/).

### Programas paralelos 8, 9 e 10

Os três novos programas estão escritos integralmente em MiniPar:

- `tests/teste8_avaliacao_paralela.minipar`: 160 atividades e quatro avaliadores.
- `tests/teste9_avaliacao_mandelbrot.minipar`: avaliações e Mandelbrot ASCII 50×20.
- `tests/teste10_avaliacao_fractais.minipar`: seis tarefas, incluindo Sierpinski
  recursivo de grau 4 com saída SVG.

```powershell
python main.py tests/teste8_avaliacao_paralela.minipar
python main.py tests/teste9_avaliacao_mandelbrot.minipar
python main.py tests/teste10_avaliacao_fractais.minipar
$env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH
.\output\teste8_avaliacao_paralela.exe
.\output\teste9_avaliacao_mandelbrot.exe
.\output\teste10_avaliacao_fractais.exe
python tools/validate_parallel.py
python -m pytest
```

Cada programa mede os modos sequencial/paralelo com a mesma carga, recupera
resultados reais por Join e verifica as 160 atividades sem perdas/duplicatas.
Speedup pode ficar abaixo de 1; barreiras TCP e criação/coleta de tarefas fazem
parte do custo medido. Os fontes padrão não exigem afinidade. A demonstração
opcional `python tools/validate_affinity.py` fixa as 4/5/6 tarefas em IDs
lógicos permitidos, sem mudar os algoritmos nem exigir essas CPUs nos testes padrão.

Eles aparecem automaticamente no menu e na Web original. A Web oferece links
para os SVGs produzidos; os arquivos padrão são
`output/teste10-sierpinski-seq.svg` e `output/teste10-sierpinski-par.svg`.
O [manual dos programas](docs/parallel-programs-2026.2.md) explica resultados,
biblioteca nativa, métricas e a configuração remota demonstrada para o Teste 8.
Evidências copiadas da saída nativa: [Mandelbrot ASCII](docs/evidencias/fractais/teste9-mandelbrot.txt)
e [Sierpinski SVG](docs/evidencias/fractais/teste10-sierpinski.svg).

### Validação dos programas 1 a 7

Os sete programas obrigatórios têm resultados verificados; os quatro
adicionais antigos também compilam e executam com suas saídas conferidas.

O Quicksort iterativo agora usa uma pilha dinâmica de pares e calcula os
limites pelo comprimento da entrada. A validação cobre listas vazias,
negativas, repetidas e maiores que a antiga pilha. A calculadora trata divisão
por zero e foi exercitada com servidor em outro processo. Neurônio e
recomendador seguem as regras do enunciado; XOR é verificado por tolerância
numérica e redução do erro após treinamento.

```powershell
python -m pytest
python tools/validate_programs.py
```

O segundo comando compila/executa os sete programas com assertions de limites,
verifica seus resultados e grava estados por fase em
`output/validacoes/validacao-1a7.json`.
As variantes usam as funções/classes dos próprios programas, com entradas
reproduzíveis. Os oráculos Python apenas conferem a saída do C++ executado.
Os exemplos anteriores a esta etapa estão preservados em
`tests/fixtures/originais-2026-1/`; resultados esperados e referências não
foram alterados. ASan/UBSan não ligaram nesta instalação MSYS2 por ausência
de `libasan`/`libubsan`; a alternativa executada usa `_GLIBCXX_ASSERTIONS`
e índices verificados no backend. O caso original permanece como fixture de regressão.

### Fork/Join e runtime 2026.2

A [BNF completa](BNF-grammar.md) amplia a gramática 2026.1 e documenta as regras
de tipos, canais e isolamento. Exemplo de criação e coleta de resultado:

```minipar
func square(number value) -> number { return value * value; }
var local_id = fork local square(7);
var remote_id = fork remote("127.0.0.1", 7000) square(8);
number local_result = join(local_id);
number remote_result = join(remote_id);
```

Compile o exemplo misto e inicie um trabalhador em outro terminal:

```powershell
python main.py examples/fork_join_mixed.minipar
# Terminal 1: espera solicitações de funções deste programa
python tools/run_worker.py output/fork_join_mixed.exe --port 7000
# Terminal 2: ambiente das DLLs do MSYS2, se necessário
$env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH
.\output\fork_join_mixed.exe
python -m pytest
```

Saída calculada pelas tarefas: `x = 49` e `y = 64`. Fork local cria uma tarefa
com `std::async(std::launch::async)`; Fork remoto envia argumentos tipados por
TCP ao trabalhador compilado. Join aguarda o resultado ou propaga o erro.
O mesmo executável oferece os modos cliente, `--worker` e `--manifest`.
O trabalhador aceita somente as funções/assinaturas remotas registradas pelo
compilador e exige o mesmo identificador de programa.

O [manual do runtime](docs/runtime-2026.2.md) descreve instalação em dois
computadores, protocolo, snapshots, timeouts, traces e limitações. A validação
real foi realizada entre processos distintos no Windows/localhost; dois
computadores físicos e Linux permanecem sem execução. A extensão opcional
`on core(n)` aplica afinidade real no Windows/Linux; os testes nativos desta
etapa verificaram a implementação Windows. Sem o sufixo, continua o
escalonamento normal do sistema operacional.

`python main.py examples/fork_join_local.minipar --tac-only` continua validando
e gerando TAC sem G++, binário ou rede. A API Flask aceita `tac_only: true`;
no modo padrão compila/executa o runtime real. Menu e Web usam o mesmo compilador.


Arquitetura orientada a objetos baseada na versão C++ original, agora expandida para incluir **Geração de Código Intermediário (TAC)** de 3 endereços e uma nova **IDE Web**, capaz de gerar, compilar e executar o código C++ produzido pelo compilador.
Desenvolvido por:

Emanuele Vitória de Jesus Lima - [Manu-Vii](https://github.com/Manu-Vii)

José Lucas de Oliveira Quintela - [lucasqtl](https://github.com/lucasqtl)

Luiz Miguel de Melo Bomfim - [luizwhirl](https://github.com/luizwhirl)

---

## Estrutura do Projeto

```text
MiniPar-2026.2/
├── src/
│   ├── ast_nodes.py      # Nós da AST (dataclasses)
│   ├── lexer.py          # Analisador Léxico
│   ├── parser.py         # Analisador Sintático
│   ├── semantic.py       # Analisador Semântico
│   ├── tac.py            # Gerador de Código Intermediário (TAC)
│   ├── codegen.py        # Gerador de Código C++
│   ├── cpp_template.py   # Template base em C++, incorpora runtime na saída
│   └── runtime/          # TCP, canais, snapshots, tarefas, codecs e RPC C++20
├── docs/                 # Documentação acadêmica, manuais e evidências
├── examples/             # Exemplos mínimos local, remoto e misto
├── tools/                # Toolchain, linha de base, trabalhador e demo real
├── static/               # Arquivos estáticos da IDE Web (CSS, JS)
├── templates/            # Arquivos HTML da IDE Web
├── tests/                # Programas 1–11, exemplos anteriores e testes pytest
├── app.py                # Servidor Flask da Interface Web
├── main.py               # Ponto de entrada principal (CLI e Interativo)
├── menu.py               # Menu interativo para terminal
├── BNF-grammar.md        # Gramática MiniPar 2026.2
├── requirements.txt      # Dependências Python
└── README.md
```

---

## Requisitos

- Python 3.10 ou superior (validado com 3.14.3)
- G++ com C++20, recomendado GCC 13 ou superior (validado com MSYS2 GCC 16.2.0)
- Flask (para executar a IDE Web)

Instalação das dependências:

```bash
pip install -r requirements.txt
```

`requirements.txt` declara diretamente o Flask necessário às interfaces Web.
`requirements-dev.txt` acrescenta pytest e inclui
`requirements-arm-validation.txt` (Zig/LLVM, Unicorn e leitura ELF);
`requirements-dev.lock.txt` fixa também as dependências transitivas usadas nos
testes. Nenhum ambiente virtual é distribuído. Os materiais de `referencias/`
e o clone interno foram retirados da entrega; execução e testes independem deles.

### Preparar ambiente e executar testes

Na raiz do repositório, em PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock.txt
$env:MINIPAR_CXX = 'C:\msys64\mingw64\bin\g++.exe'
.\.venv\Scripts\python.exe tools\check_toolchain.py
.\.venv\Scripts\python.exe -m pytest
```

`MINIPAR_CXX` tem prioridade sobre `CXX`; ambas recebem um caminho de executável,
sem flags e sem aspas embutidas. Se não definidas, no Windows são procurados
`C:/msys64/ucrt64/bin/g++.exe`, `C:/msys64/mingw64/bin/g++.exe` e depois `g++` no
PATH. Em outros sistemas usa-se `g++` no PATH. Um override inválido gera erro,
sem substituição silenciosa. O diretório do compilador é acrescentado ao PATH
dos subprocessos para localizar as DLLs; o PATH global do Windows não é alterado.

No Linux/macOS, após instalar um G++ C++20, use `python3 -m venv .venv`,
`.venv/bin/python -m pip install -r requirements-dev.lock.txt` e `.venv/bin/python -m pytest`.
Essas plataformas ainda não foram executadas nesta etapa. O comando de teste
inclui testes nativos reais; se o compilador não estiver disponível, eles falham.
`python -m pytest -m 'not native'` executa apenas a parte sem compilação nativa.

`tools/check_toolchain.py` compila e executa uma sonda de concepts/threads/tipos,
exigindo saída `42`. Não basta a ferramenta anunciar uma versão recente.

Para registrar as fases dos programas de tests/, além do smoke:

```powershell
.\.venv\Scripts\python.exe tools\run_baseline.py --report output/validacoes/baseline-funcional.json
```

O relatório contém fases, comandos, entradas, saídas e códigos de retorno.
O coletor retorna 1 se algum exemplo falhar e registra que retorno zero não
equivale a validar resultados. A validação matemática dos sete obrigatórios
é feita por `tools/validate_programs.py` e pytest. O defeito da pilha do Teste 7
foi corrigido nesta etapa; os relatórios anteriores conservam a falha original.
O TAC continua dinâmico, inclusive para `quicksort_iterativo`.

Compilação CLI e execução mínima no Windows (o CLI somente compila):

```powershell
.\.venv\Scripts\python.exe main.py tests\fixtures\smoke.minipar
$env:PATH = (Split-Path $env:MINIPAR_CXX) + ';' + $env:PATH
.\output\smoke.exe
```

Saída esperada: `42`. O menu e a interface Flask já preparam o ambiente das DLLs.
Execute as interfaces a partir da raiz, pois os caminhos de saída ainda são relativos.

---

## Como Usar

O compilador oferece múltiplas formas de interação.

### 1. Menu Interativo (Terminal ou IDE Web)

Execute o programa sem argumentos:

```bash
python main.py
```

Opções disponíveis:

- **[1] Modo Terminal**: navegação pelos testes através de um menu textual.
- **[2] Modo Web Interface**: inicia o servidor Flask.

Após iniciar a interface web, acesse:

```text
http://127.0.0.1:5000
```

A IDE permite:

- Editar código MiniPar
- Compilar o programa
- Visualizar o código TAC gerado
- Visualizar o código C++ gerado
- Executar o programa e ver a saída

### 2. Execução Direta (CLI)

Para compilar um arquivo específico:

```bash
python main.py tests/teste3_neuronio.minipar
```

O nome do arquivo de saída é opcional. Por padrão, será utilizado o mesmo nome do arquivo `.minipar`.

Os arquivos gerados (`.cpp`, `.tac` e executáveis) serão armazenados na pasta `output/`.

---

## Fases do Compilador

| Fase | Arquivos | Descrição |
|------|----------|------------|
| 1 | `lexer.py` / `parser.py` | Tokenização do código-fonte e construção da AST |
| 2 | `semantic.py` | Verificação de declarações, redeclarações e escopo |
| 3 | `tac.py` | Geração de Código Intermediário (TAC) |
| 4 | `codegen.py` | Geração de código C++ e compilação automática via `g++ -O3` |

---

## Sintaxe MiniPar

Exemplo:

```minipar
seq {
    var x = 42;

    print("Valor:", x);

    par {
        print("Thread A");
        print("Thread B");
    }
}
```

### Comandos Disponíveis

| Sintaxe | Descrição |
|----------|------------|
| `seq { ... }` | Bloco sequencial |
| `par { ... }` | Bloco paralelo (cada instrução gera uma thread C++) |
| `var nome = expr;` | Declaração de variável |
| `nome = expr;` | Atribuição |
| `print(expr, ...);` | Impressão na saída padrão |
| `# comentário` | Comentário de linha |

---
