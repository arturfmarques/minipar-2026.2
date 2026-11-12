# Teste 11 — verificação ARMv7 no CPUlator

O Teste 11 é um minicompilador escrito na própria linguagem MiniPar. Seu fonte está em [teste11_minicompilador_armv7.minipar](../tests/teste11_minicompilador_armv7.minipar). O compilador principal traduz esse programa para C++20; o executável obtido recebe uma expressão aritmética e gera o correspondente Assembly ARMv7.

## Expressões verificadas

| Expressão | Resultado decimal | Valor esperado de `r0` |
| --- | ---: | --- |
| `((2+4)*7)-(5*4)` | 22 | `0x00000016` |
| `((10-8*7)+4)*2` | -84 | `0xFFFFFFAC` |
| `((2+4)*7)-(5*4)` | 22 | `0x00000016` |

As três entradas foram executadas manualmente no CPUlator ARMv7 DE1-SoC. Os valores de resultado constam do relatório acadêmico e dos arquivos de evidência em [evidencias/teste11](evidencias/teste11/). A terceira entrada repete a primeira, conforme a lista de expressões exigidas.

## Fluxo de execução

1. O Lexer reconhece tokens, identificadores, operadores e parênteses.
2. O Parser constrói uma AST, respeitando precedência e associatividade.
3. A tabela de símbolos registra constantes e identificadores utilizados.
4. O TAC é produzido dinamicamente a partir da AST.
5. O gerador ARMv7 cria o código Assembly; o resultado fica em `r0`.

Os arquivos gerados na pasta `output/` são artefatos de execução e não precisam ser versionados. As versões correspondentes às três expressões estão preservadas como `.arm` em `docs/evidencias/teste11/`.

## Reprodução no Windows

```powershell
py main.py tests/teste11_minicompilador_armv7.minipar
$env:Path = 'C:\msys64\mingw64\bin;' + $env:Path
.\output\teste11_minicompilador_armv7.exe
```

Digite uma das expressões e copie o arquivo anunciado como `ARQUIVO: output/teste11-expressao.arm` para o editor do [CPUlator](https://cpulator.01xz.net/?sys=arm-de1soc). Use **Compile and Load**, execute e interrompa no laço final para inspecionar o registrador `r0`. O arquivo de saída é sobrescrito a cada execução; guarde cópias se quiser comparar expressões diferentes.

## Validação automatizada

```powershell
py tools/validate_minicompiler.py
py -m pytest tests/integration/test_minicompiler.py tests/integration/test_minicompiler_delivery.py
```

Os validadores incluem montagem e execução em ambiente ARM por ferramentas auxiliares quando as dependências correspondentes estão instaladas. A verificação manual no CPUlator é uma etapa separada.

Mais detalhes internos estão em [teste11-minicompilador.md](teste11-minicompilador.md).
