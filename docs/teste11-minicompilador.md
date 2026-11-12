# Teste 11 — minicompilador de expressões em MiniPar

O [Teste 11](../tests/teste11_minicompilador_armv7.minipar) implementa um compilador de expressões aritméticas **dentro de um programa MiniPar**. O código Python do compilador principal serve para transformar e compilar esse programa; a análise da expressão de entrada, o TAC da expressão e o Assembly ARMv7 são produzidos pelo executável MiniPar.

## Etapas e classes

| Classe | Responsabilidade |
| --- | --- |
| `Diagnostics` | Identifica erros por fase e posição |
| `Token` e `Lexer` | Formam tokens numéricos, nomes, operadores e parênteses |
| `ASTNode` e `Parser` | Constroem a árvore sintática com precedência correta |
| `SymbolEntry` e `SymbolTable` | Registram constantes e identificadores |
| `TACGenerator` | Emite temporários e operações intermediárias |
| `ExpressionEvaluator` | Calcula o valor da expressão e valida operações |
| `ARMCodeGenerator` | Traduz a expressão para Assembly ARMv7 |
| `MiniCompiler` | Coordena as fases, exibe resultados e salva o `.arm` |

O TAC mostrado pelo executável é o **TAC da expressão digitada**. Ele é distinto do TAC do programa MiniPar completo, produzido pelo compilador principal.

## Gramática das expressões

O minicompilador reconhece números, identificadores, operações `+`, `-`, `*`, `/`, sinais unários e parênteses. O parser usa descida recursiva com precedência da multiplicação e divisão sobre adição e subtração.

```bnf
<entrada> ::= <expressao> EOF
<expressao> ::= <termo> { ("+" | "-") <termo> }
<termo> ::= <unario> { ("*" | "/") <unario> }
<unario> ::= "+" <unario> | "-" <unario> | <primario>
<primario> ::= NUMBER | IDENTIFIER | "(" <expressao> ")"
```

Essa gramática descreve a entrada aritmética do Teste 11, **não substitui** a gramática geral do MiniPar, disponível em [BNF-grammar.md](../BNF-grammar.md).

## Saída e resultado ARMv7

Para `((2+4)*7)-(5*4)`, o TAC da expressão contém as etapas equivalentes a:

```text
t1 = 2 + 4
t2 = t1 * 7
t3 = 5 * 4
t4 = t2 - t3
```

O resultado aritmético é 22. O gerador ARMv7 materializa as operações e deixa o valor final no registrador `r0`. Os três arquivos de Assembly de referência da entrega estão em [evidencias/teste11](evidencias/teste11/).

| Expressão | Resultado |
| --- | ---: |
| `((2+4)*7)-(5*4)` | 22 |
| `((10-8*7)+4)*2` | -84 |
| `((2+4)*7)-(5*4)` | 22 |

## Execução

```powershell
py main.py tests/teste11_minicompilador_armv7.minipar
$env:Path = 'C:\msys64\mingw64\bin;' + $env:Path
.\output\teste11_minicompilador_armv7.exe
```

Na execução, informe uma expressão. O programa imprime tokens, AST, tabela de símbolos, TAC e Assembly, além de gravar `output/teste11-expressao.arm`. Cada execução atualiza o arquivo de saída.

Para reproduzir a conferência no simulador e consultar os valores de `r0`, veja [Teste 11 no CPUlator](teste11-cpulator-2026.2.md).
