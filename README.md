# Projeto MiniPAR 2026.2

O **MiniPar 2026.2** é um compilador desenvolvido em **Python** para uma linguagem orientada a objetos com suporte a **paralelismo real e comunicação entre processos**. Ele realiza análise léxica, sintática e semântica, constrói a tabela de símbolos e gera **TAC e código C++20**, compilado pelo G++ (`-O3`) em executáveis nativos.

A linguagem oferece blocos `seq` e `par`, **Fork/Join**, seleção de processadores lógicos com `on core(n)` e comunicação TCP por `c_channel` e `fork remote`. Para desenvolver e testar programas, o projeto disponibiliza **terminal, IDE Web e interface Web educacional**, que permite acompanhar as etapas da compilação.

**Disciplina:** Compiladores — Ciência da Computação, UFAL (2026.2)  
**Integrantes:** Artur Ferreira Marques da Silva e João Manoel Santos Lima  
**Professor:** Arturo Hernandez Dominguez

## Índice

- [Funcionalidades](#funcionalidades)
- [Arquitetura do compilador](#arquitetura-do-compilador)
- [Requisitos e instalação](#requisitos-e-instalação)
- [Como executar](#como-executar)
- [Paralelismo, Fork/Join e canais](#paralelismo-forkjoin-e-canais)
- [Programas de teste](#programas-de-teste)
- [Testes automatizados e validação](#testes-automatizados-e-validação)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Documentação](#documentação)

## Funcionalidades

| Área | Recursos implementados |
| --- | --- |
| Front-end | Lexer, Parser por descida recursiva, AST e diagnósticos com linha e coluna. |
| Semântica | Verificação de escopos, tipos, chamadas, classes, herança, regras de tarefas e tabela de símbolos. |
| Geração de código | TAC e C++20 gerados a partir da AST validada; compilação nativa com G++ `-O3`. |
| Linguagem | Variáveis tipadas, funções, recursão, condicionais, laços, listas, matrizes, classes, métodos, `init`, `this` e `extends`. |
| Paralelismo | Blocos `seq` e `par`, tarefas `fork local`, `join` e seleção opcional de CPU lógica com `on core(n)`. |
| Comunicação | `c_channel`, `send`, `receive` e `fork remote(host, porta)` com comunicação TCP entre processos. |
| Interfaces | Menu de terminal, IDE Web original e IDE Web educacional com inspeção das etapas de compilação. |
| Validação | Onze programas principais em MiniPar, testes de integração e execução do Teste 11 em ARMv7 no CPUlator. |

## Arquitetura do compilador

O processamento de um programa segue o fluxo:

```text
Código-fonte MiniPar (.minipar)
            |
            v
         Lexer
            |
            v
         Parser
            |
            v
           AST
            |
            v
Análise semântica + tabela de símbolos
            |
       +----+----+
       |         |
       v         v
      TAC       C++20
      .tac       .cpp
                 |
                 v
              G++ -O3
                 |
                 v
         Executável nativo
```

**Observação:** o TAC e o C++ são gerados **separadamente a partir da mesma AST**. O gerador C++ não traduz o arquivo TAC.

Os módulos principais ficam em `src/`:

- `lexer.py`: análise léxica e geração de tokens.
- `parser.py` e `ast_nodes.py`: análise sintática e estrutura da AST.
- `semantic.py` e `diagnostics.py`: validação semântica, símbolos e mensagens de erro.
- `tac.py`: geração do código intermediário de três endereços.
- `codegen.py` e `cpp_template.py`: geração de C++20.
- `runtime/*.hpp`: tarefas, canais, rede TCP, RPC, snapshots e afinidade.
- `toolchain.py`: integração com o compilador G++.

Gramática completa: [`BNF-grammar.md`](BNF-grammar.md).

## Requisitos e instalação

Ambiente utilizado nas validações documentadas:

- **Windows 11** e **Python 3.14.3**.
- **G++ com suporte a C++20** (utilizado: GCC 16.2.0 do MSYS2/MinGW-w64).
- **Flask** para as interfaces Web.
- **pytest** para os testes automatizados.
- **Navegador Web** para acessar as interfaces e o CPUlator.

Clone o projeto e entre na pasta:

```powershell
git clone https://github.com/arturfmarques/minipar-2026.2.git
cd minipar-2026.2
```

Instale as dependências de execução:

```powershell
py -m pip install -r requirements.txt
```

Para executar a suíte de testes, instale também as dependências de desenvolvimento:

```powershell
py -m pip install -r requirements-dev.lock.txt
```

O compilador C++ pode ser localizado automaticamente pelo projeto. Se necessário, indique seu caminho no PowerShell:

```powershell
$env:MINIPAR_CXX = 'C:\msys64\mingw64\bin\g++.exe'
```

Para executar os `.exe` compilados diretamente no terminal, disponibilize as DLLs do MSYS2 na sessão:

```powershell
$env:Path = 'C:\msys64\mingw64\bin;' + $env:Path
```

> Ajuste os caminhos do MSYS2 à sua instalação e execute os comandos na raiz do repositório.

## Como executar

### 1. Interface de terminal

```powershell
py main.py
```

Selecione **1 — Modo Terminal** para abrir o menu de programas e compilar/executar os testes. A opção **2 — Modo Web** inicia a interface no navegador.

### 2. IDE Web original

```powershell
py app.py
```

Acesse **http://127.0.0.1:5000/**.

A IDE permite carregar exemplos, editar programas MiniPar, compilar, executar e consultar os arquivos TAC e C++ produzidos, além de visualizar a saída.

### 3. IDE Web educacional

Com o mesmo servidor Flask iniciado, acesse **http://127.0.0.1:5000/educacional**.

A interface organiza o processo em etapas independentes:

- **Tokens:** tipos, lexemas, linhas e colunas.
- **AST:** representação gráfica interativa da árvore sintática.
- **Semântica:** diagnósticos e tabela de símbolos.
- **TAC:** código intermediário produzido.
- **C++:** código-fonte gerado pelo backend.
- **Execução:** compilação nativa, entrada, saída e download dos artefatos.

### 4. Compilar um programa diretamente

```powershell
py main.py tests/teste2_fatorial_fibonacci_par.minipar
```

O comando compila o programa e grava os artefatos em `output/`. No Windows, execute o binário correspondente:

```powershell
.\output\teste2_fatorial_fibonacci_par.exe
```

Para gerar **somente TAC**, sem invocar o G++:

```powershell
py main.py examples/fork_join_local.minipar --tac-only
```

A pasta `output/` não é versionada no Git.

## Paralelismo, Fork/Join e canais

A linguagem diferencia blocos `seq` (execução sequencial) e `par` (execução concorrente), além de oferecer Fork/Join explícito.

Exemplo de Fork local e afinidade:

```text
func square(number value) -> number {
    return value * value;
}

seq {
    var a = fork local square(7);
    var b = fork local square(9) on core(1);
    print(join(a), join(b));
}
```

`fork` inicia uma tarefa; `join` aguarda sua conclusão e recupera o resultado. A implementação local usa `std::async` no runtime C++20. O sufixo `on core(n)` permite selecionar um **processador lógico** disponível.

A linguagem também permite canais TCP por meio de `c_channel`, `send` e `receive`, além de tarefas remotas com `fork remote(host, porta)`. No modo remoto, um processo trabalhador recebe argumentos tipados, executa uma função registrada no programa compilado e devolve seu resultado.

### Exemplo prático: Fork local + remoto

Compile o programa:

```powershell
py main.py examples/fork_join_mixed.minipar
```

**Terminal 1 — iniciar o trabalhador:**

```powershell
py tools/run_worker.py output/fork_join_mixed.exe --port 7000
```

**Terminal 2 — executar o cliente:**

```powershell
$env:Path = 'C:\msys64\mingw64\bin;' + $env:Path
.\output\fork_join_mixed.exe
```

No exemplo, as tarefas retornam **`x = 49`** e **`y = 64`**. O cenário apresentado utiliza dois processos comunicando-se por TCP em `127.0.0.1`.

Para testar a afinidade, use [`examples/fork_join_affinity.minipar`](examples/fork_join_affinity.minipar) e `tools/validate_affinity.py`.

## Programas de teste

Os onze programas principais estão em `tests/`.

| Teste | Programa | Objetivo |
| --- | --- | --- |
| 1 | `teste1_calculadora_cliente_servidor.minipar` | Calculadora cliente/servidor com comunicação por canais TCP. |
| 2 | `teste2_fatorial_fibonacci_par.minipar` | Fatorial e sequência de Fibonacci em paralelo. |
| 3 | `teste3_neuronio.minipar` | Treinamento de um neurônio simples com classes e atualização de pesos. |
| 4 | `teste4_rede_neural_xor.minipar` | Rede neural para aprender a função XOR. |
| 5 | `teste5_recomendacao.minipar` | Sistema de recomendação baseado em histórico de compras e rede neural. |
| 6 | `teste6_quicksort_classes.minipar` | Quicksort recursivo com orientação a objetos. |
| 7 | `teste7_quicksort_iterativo_tac.minipar` | Quicksort iterativo com pilha explícita e geração de TAC. |
| 8 | `teste8_avaliacao_paralela.minipar` | Avaliação de 160 atividades com quatro avaliadores. |
| 9 | `teste9_avaliacao_mandelbrot.minipar` | Avaliação paralela e geração de Mandelbrot em ASCII. |
| 10 | `teste10_avaliacao_fractais.minipar` | Avaliação paralela, Mandelbrot e tapete de Sierpinski em SVG. |
| 11 | `teste11_minicompilador_armv7.minipar` | Minicompilador de expressões com Lexer, Parser, AST, TAC e geração de ARMv7. |

Para validar os programas, execute:

```powershell
py tools/validate_programs.py
py tools/validate_parallel.py
py tools/validate_minicompiler.py
```

### Testes 8, 9 e 10: desempenho paralelo

Os programas avaliam a mesma carga em modo sequencial e paralelo e apresentam os tempos e o **speedup**. O Teste 9 acrescenta o Mandelbrot ASCII e o Teste 10 produz arquivos SVG do tapete de Sierpinski.

Os tempos variam conforme o ambiente. No [relatório técnico](docs/Relatorio-Minipar2026.2.pdf), o Teste 8 apresenta pequeno ganho, enquanto os Testes 9 e 10 registram maior tempo no modo paralelo.

### Teste 11: minicompilador ARMv7

O Teste 11 implementa, **em MiniPar**, um minicompilador de expressões aritméticas. O executável gerado analisa uma expressão infixada, exibe tokens, AST, tabela de símbolos e TAC, calcula o resultado e escreve um arquivo Assembly ARMv7.

```powershell
py main.py tests/teste11_minicompilador_armv7.minipar
.\output\teste11_minicompilador_armv7.exe
```

O Assembly é salvo em `output/teste11-expressao.arm` e pode ser carregado no [CPUlator ARMv7 DE1-SoC](https://cpulator.01xz.net/?sys=arm-de1soc).

| Expressão | Resultado decimal | Registrador `r0` |
| --- | ---: | --- |
| `((2+4)*7)-(5*4)` | 22 | `0x00000016` |
| `((10-8*7)+4)*2` | -84 | `0xFFFFFFAC` |
| `((2+4)*7)-(5*4)` | 22 | `0x00000016` |

As três expressões foram executadas manualmente no CPUlator. Os exemplos de Assembly e as saídas correspondentes estão em [`docs/evidencias/teste11/`](docs/evidencias/teste11/).

## Testes automatizados e validação

A suíte de testes utiliza **pytest**, com testes unitários, de integração, do backend nativo, do runtime e das interfaces Web.

```powershell
py -m pytest
```

O **registro consolidado informa 519 testes automatizados aprovados** no Windows 11, com Python 3.14.3 e G++ 16.2.0.

Os testes de integração abrangem, entre outros:

- Fluxo Lexer → Parser → AST.
- Análise semântica, escopos e tabela de símbolos.
- Geração de TAC e C++ a partir da AST.
- Compilação G++ e execução de programas MiniPar.
- Fork/Join, comunicação TCP e afinidade de tarefas.
- APIs Flask e interfaces Web.
- Saídas e resultados dos programas de teste.

## Estrutura do repositório

```text
minipar-2026.2/
├── BNF-grammar.md             # Gramática BNF 2026.2
├── README.md                  # Apresentação e execução do projeto
├── main.py                    # Compilador e menu de entrada
├── menu.py                    # Interface interativa de terminal
├── app.py                     # Servidor Flask
├── educational_web.py         # Etapas e serviços da Web educacional
├── src/                       # Lexer, Parser, AST, semântica, TAC e C++
│   └── runtime/               # Runtime C++20 de tarefas e comunicação
├── templates/                 # Páginas HTML das interfaces
├── static/                    # CSS e JavaScript das interfaces
├── tests/                     # Programas MiniPar e testes automatizados
├── examples/                  # Exemplos básicos, Fork/Join e afinidade
├── tools/                     # Validadores, trabalhador e utilitários
├── docs/                      # Relatório, UML, manuais e evidências
│   ├── Relatorio-Minipar2026.2.pdf
│   ├── uml/
│   └── evidencias/
├── requirements.txt           # Dependências das interfaces
├── requirements-dev.txt       # Dependências de desenvolvimento
└── requirements-dev.lock.txt  # Dependências fixadas para validação
```

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [**Relatório técnico final (PDF)**](docs/Relatorio-Minipar2026.2.pdf) | Arquitetura, algoritmos, testes, UML, resultados e evidências. |
| [**Gramática BNF 2026.2**](BNF-grammar.md) | Regras sintáticas completas da linguagem. |
| [Pseudocódigos do compilador](docs/pseudocodigos-compilador-2026.2.md) | Lexer, Parser, análise semântica e tabela de símbolos. |
| [Product Backlog](docs/product-backlog-2026.2.md) | Funcionalidades e prioridades do projeto. |
| [Sprint Backlogs](docs/sprint-backlogs-2026.2.md) | Organização das etapas de desenvolvimento. |
| [Diagramas UML](docs/uml/README.md) | Casos de uso, componentes e classes. |
| [Runtime e paralelismo](docs/runtime-2026.2.md) | Implementação de tarefas, canais e RPC. |
| [Programas paralelos](docs/parallel-programs-2026.2.md) | Testes 8–10, métricas e fractais. |
| [Minicompilador ARMv7](docs/teste11-minicompilador.md) | Organização e funcionamento do Teste 11. |
| [Testes de integração](docs/testes-integracao-2026.2.md) | Escopo e critérios da suíte de integração. |
| [Interface Web educacional](docs/web-educacional-2026.2.md) | Etapas interativas de análise e geração de código. |

