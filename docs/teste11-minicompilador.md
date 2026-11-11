# Teste 11 — minicompilador de expressões MiniPar → ARMv7

**Revisão etapa 3/5, 11/11/2026:** os três PDFs oficiais foram encontrados em
Downloads e examinados diretamente. Os arquivos gerados foram montados e
executados no CPUlator, com `r0=22, -84, 22`. Comparação, evidências atuais e
roteiro de apresentação: [Teste 11 no CPUlator](teste11-cpulator-2026.2.md).
Regressão: 482 aprovados (481 preservados e um novo). As seções abaixo
documentam também a implementação e as verificações históricas.

## Implementação e materiais

O [fonte MiniPar](../tests/teste11_minicompilador_armv7.minipar) usa o compilador
Python existente, que produz TAC e C++20 e chama G++. O executável resultante
recebe **uma expressão** e realiza todas as fases do minicompilador em MiniPar.
Python controla processos e verifica saídas; não interpreta as expressões nem
produz seu Assembly. Há dois TACs distintos: o TAC do programa MiniPar inteiro
gerado pelo compilador principal e o TAC da expressão impresso pelo executável.

Materiais consultados durante o desenvolvimento (retirados da entrega na
[limpeza](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/limpeza-git-2026.2.md); não são dependências de execução):

- `MiniCompiladorCompleto_ARMv7.java.txt`: organização didática das fases;
- `Codigo-Assembly-ARMV7.arm.txt`: exemplo de instruções e expressão;
- `Execucao-Saida-okRodounoCPULATOR.txt`: tokens, árvore, símbolos, TAC e 22;
- `Projeto-Compilador-MiniPar2026-2-Atualizado.pdf`: enunciado disponível,
  com os testes 1–10. Não foi localizada nele uma seção/imagem específica
  do Teste 11; a imagem final de fractal inspecionada é Sierpinski.

As três expressões obrigatórias, incluindo a repetição, seguem a solicitação
fornecida. A referência ARM usa `r8`; esta implementação documenta e usa `r0`.
As deficiências do Java de referência (caracteres ignorados, símbolos indefinidos
tratados como zero, falta de EOF e registradores crescentes) não foram reproduzidas.

## Classes e fluxo

| Classe | Responsabilidade |
|---|---|
| Diagnostics | Primeiro erro, fase, mensagem, linha e coluna; reinício entre compilações. |
| Token | Tipo, lexema, valor numérico e posição. |
| Lexer | Percurso caractere a caractere; números, identificadores, operadores, parênteses e EOF. |
| ASTNode | Nó NUMBER, IDENTIFIER, UNARY ou BINARY, filhos reais, altura e resultado avaliado. |
| Parser | Descida recursiva com precedência, associatividade à esquerda e consumo completo. |
| SymbolEntry / SymbolTable | CONST deduplicadas e VAR com valor/estado de definição/uso. |
| TACGenerator | Percurso pós-ordem e temporários dinâmicos, evitando colisões com nomes VAR. |
| ExpressionEvaluator | Avaliação recursiva; rejeita símbolo indefinido, divisão por zero e não finitos. |
| ARMCodeGenerator | Validação de inteiros, emissão A32, pilha, constantes, dados e divisão por software. |
| MiniCompiler | Encadeia fases, imprime evidências, salva `.arm` e define status do processo. |

O Lexer aceita espaços, tabulações e quebras de linha; caracteres desconhecidos
geram erro. O Parser constrói a árvore antes da geração TAC; os parênteses alteram
a árvore sem virar nós artificiais. Uma folha isolada tem TAC vazio, pois não há
operação de três endereços a emitir. Unários geram instruções próprias.

## Gramática das expressões

Esta é a linguagem de entrada do minicompilador, não uma substituição da
[BNF MiniPar 2026.2](../BNF-grammar.md).

```bnf
<entrada> ::= <expressao> EOF
<expressao> ::= <termo> <resto-expressao>
<resto-expressao> ::= "+" <termo> <resto-expressao>
                  | "-" <termo> <resto-expressao> | ε
<termo> ::= <unario> <resto-termo>
<resto-termo> ::= "*" <unario> <resto-termo>
              | "/" <unario> <resto-termo> | ε
<unario> ::= "+" <unario> | "-" <unario> | <primario>
<primario> ::= NUMBER | IDENTIFIER | "(" <expressao> ")"
NUMBER ::= <digitos> | <digitos> "." <digitos>
<digitos> ::= <digito> | <digito> <digitos>
<digito> ::= "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"
IDENTIFIER ::= <letra> <resto-identificador>
<resto-identificador> ::= <letra> <resto-identificador>
                       | <digito> <resto-identificador> | ε
<letra> ::= "A" | ... | "Z" | "a" | ... | "z" | "_"
```

Na última produção, os intervalos denotam somente letras ASCII. Os laços
de `parseExpression` e `parseTerm` acumulam à esquerda: `20-3-2` vale 15,
`48/4/3` vale 4. Unários têm precedência maior que multiplicação/divisão.
Não há atribuição, chamadas, potência, notação científica nem comentários na
expressão. Comentários `#` continuam válidos no programa MiniPar hospedeiro.

O console não recebe declarações VAR: `x+1` é erro até que `x` seja definido.
A API MiniPar permite `compiler.symbols.define("x",9)` antes de `compile`.
O teste dessa API compila e executa as mesmas classes com um pequeno main
MiniPar que define `x` e `t1`; não injeta valores no avaliador Python.
CONST são limpas a cada compilação; VAR explicitamente definidas permanecem.

## Contrato numérico, registradores e memória

A avaliação MiniPar usa `number` (double). O backend ARM aceita somente
expressões cujos valores em **cada nó** sejam inteiros na faixa
−2147483648..2147483647. `2.0+3` pode ser emitida; `1.5+0.5` e `5/2` são
avaliadas mas rejeitadas pelo ARM. Overflow intermediário também é recusado.
O literal com magnitude 2147483648 é permitido exclusivamente sob unário `-`.

O Assembly usa `.syntax unified`, `.arch armv7-a`, `.arm`, `_start`, `.text`,
`.data` e `.bss`. Resultado em `r0`; `r12=0` indica caminho normal. O símbolo
`__expr_done` contém um laço final; deve-se parar ali, não esperar saída textual.

Folhas usam `ldr r0, =constante`, evitando limites de imediatos MOV. Identificadores
usam rótulos `.word`. Pools literais são emitidos a cada 128 instruções, com
salto para não executar seus dados. O lado esquerdo de uma operação é salvo
com `push {r0,r1}` e recuperado em `r1` por `pop {r1,r2}` depois de avaliar o
lado direito em `r0`. Isso preserva a ordem da subtração/divisão e reutiliza
registradores em árvores grandes. Multiplicação usa `r2` como destino auxiliar.

`sp` é inicializado pelo programa no topo de uma área `.bss` de 64 KiB,
alinhada a oito bytes. Não depende do valor inicial do simulador. Divisão usa
uma rotina inteira de 32 passos escrita em Assembly emitido pelo próprio
MiniPar, com sinal, divisor zero defensivo e preservação de `r2`–`r6`/`lr`.
Não emite SDIV/UDIV: Cortex-A9 não oferece essas instruções, conforme
[documentação Arm sobre divisão](https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/divide-and-conquer).

Limites: 4096 caracteres, 1024 tokens antes de EOF, altura de AST 128 e
profundidade de parênteses/unários 128. Limites excedidos recebem diagnóstico.
Os testes exercitam 60 operações aninhadas, 256 folhas com constantes grandes,
pools literais, extremos de int32 e divisão com sinais. Não são promessa de
suporte a expressões ilimitadas ou aritmética decimal exata.

## Execuções e evidências

| Expressão | Resultado MiniPar / `r0` assinado | `r0` hexadecimal | Arquivo produzido |
|---|---:|---|---|
| `((2+4)*7)-(5*4)` | 22 | `0x00000016` | [expressao-1.arm](evidencias/teste11/expressao-1.arm) |
| `((10-8*7)+4)*2` | -84 | `0xFFFFFFAC` | [expressao-2.arm](evidencias/teste11/expressao-2.arm) |
| `((2+4)*7)-(5*4)` | 22 | `0x00000016` | [expressao-3.arm](evidencias/teste11/expressao-3.arm) |
| `2+3*4` | 14 | `0x0000000E` | [expressao-4.arm](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/teste11/expressao-4.arm) |
| `-(2+3)*4` | -20 | `0xFFFFFFEC` | [expressao-5.arm](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/teste11/expressao-5.arm) |
| `1000000+234567` | 1234567 | `0x0012D687` | [expressao-6.arm](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/teste11/expressao-6.arm) |
| `(-2147483648)/2` | -1073741824 | `0xC0000000` | [expressao-7.arm](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/teste11/expressao-7.arm) |
| `81/(3*3)` | 9 | `0x00000009` | [expressao-8.arm](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/teste11/expressao-8.arm) |

TAC das expressões 1 e 3:

```text
t1 = 2 + 4
t2 = t1 * 7
t3 = 5 * 4
t4 = t2 - t3
```

TAC da expressão 2:

```text
t1 = 8 * 7
t2 = 10 - t1
t3 = t2 + 4
t4 = t3 * 2
```

O [relatório de execução](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/teste11/validacao.json) guarda comandos,
códigos de retorno, stdout, tokens, AST, símbolos, TAC e registradores.
Os arquivos `expressao-N.txt` nessa pasta contêm a saída nativa completa.
Binários, ELF e caches permanecem em `output/`, ignorado pelo Git.

## Reprodução e testes

Ferramentas utilizadas: Python 3.14.3, G++ 16.2.0, pytest 9.2.0,
ziglang 0.17.1 (Zig/LLVM), Unicorn 2.1.4 e pyelftools 0.33.
Os três últimos são **ferramentas de validação**; não executam fases do
minicompilador nem são dependências da aplicação Flask em produção.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock.txt
.\.venv\Scripts\python.exe tools/validate_minicompiler.py
.\.venv\Scripts\python.exe -m pytest
```

Para execução interativa, a partir da raiz:

```powershell
.\.venv\Scripts\python.exe main.py tests/teste11_minicompilador_armv7.minipar
$env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH
$env:MINIPAR_ARM_OUTPUT = 'output/minha-expressao.arm'
.\output\teste11_minicompilador_armv7.exe
```

Digite a expressão quando solicitado. O menu existente também lista o teste.
A primeira Web permite carregar o fonte, fornecer a expressão e baixar o `.arm`
anunciado em `ARQUIVO:`. A rota só oferece arquivos dentro de `output/`.
O [laboratório educacional](web-educacional-2026.2.md), acrescentado na etapa
seguinte, separa os painéis da análise do programa MiniPar da saída do
minicompilador de expressões.

Status nativo: 0 para sucesso; 1 para erro léxico, sintático, semântico,
avaliação ou arquivo; 2 para expressão avaliada fora do subconjunto ARM.
Erros incluem fase/linha/coluna e não anunciam um arquivo novo. Um arquivo
anterior no mesmo caminho não é apagado em caso de erro; deve-se conferir o
status e a saída da execução atual. O diretório pai deve existir.

`tools/arm_validation.py` monta e liga o Assembly usando `zig cc -target
arm-freestanding-eabi -mcpu=cortex_a9 -x assembler -nostdlib -Wl,-e,_start`.
Carrega os segmentos ELF, inicializa Unicorn Cortex-A9 e executa os bytes
até `__expr_done`, com limite de um milhão de instruções. Verifica `r0`,
`r12`, alinhamento, consumo e restauração de `sp`. O emulador roda em processo
filho com timeout, retorno e stderr conferidos. Não recebe a expressão ou seu
resultado esperado. Montagem e emulação são etapas separadas no JSON.

Os testes em `tests/integration/test_minicompiler.py` compilam o fonte real
com G++, comparam AST/TAC/tokens e resultados, montam/emulam casos válidos,
exercitam erros e verificam o menu e a API Flask com subprocessos reais.
`tests/unit/test_minicompiler_library.py` verifica as assinaturas dos builtins.
Contagem e tempo finais estão no [diagnóstico](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/diagnostico-2026.2.md#16-teste-11-minicompilador-e-validação-armv7).

## CPUlator — verificação inicial (histórico)

O material fornecido identifica ARMv7, mas não nomeia a placa. A configuração
escolhida para a verificação manual é [ARMv7 DE1-SoC](https://cpulator.01xz.net/?sys=arm-de1soc),
coerente com Cortex-A9/A32. Não há dependência de periféricos.
A ferramenta de navegador foi interrompida por não conseguir identificar a URL
com segurança. Não houve carregamento/montagem/execução confirmados no CPUlator;
as saídas históricas do professor não são evidências desta implementação.

Procedimento manual, baseado na [documentação oficial](https://cpulator.01xz.net/doc/):

1. Abra ARMv7 DE1-SoC e copie integralmente `expressao-1.arm` para o Editor.
2. Use **Compile and Load (F5)** e confira as mensagens do assembler.
3. No Disassembly, localize `__expr_done` e marque um breakpoint na instrução
   `b __expr_done`, clicando na coluna cinza à esquerda.
4. Execute até o breakpoint. Confira `r0=00000016`, `r12=0` e `sp` no endereço
   de `__expr_stack_top`. Se executar sem breakpoint, use Stop no laço final.
5. Repita com `expressao-2.arm`: `r0=FFFFFFAC` (−84 em int32). Recarregue
   `expressao-3.arm`: `r0=00000016`.
6. Registre versão/configuração do simulador, mensagens, registradores e captura
   real. Só então atualize o status CPUlator. Não desative verificações para aprovar.

| Validação | Estado |
|---|---|
| Execução nativa MiniPar/C++ | APROVADA nas expressões e testes registrados |
| Montagem/link ARM Zig/LLVM | APROVADA nos casos registrados |
| Execução ARM Unicorn Cortex-A9 | APROVADA nos casos registrados |
| Montagem GNU e execução CPUlator | Não verificadas naquela etapa; três casos aprovados na [etapa 3/5](teste11-cpulator-2026.2.md) |
| Placa ARM física / Linux | NÃO EXECUTADOS |
