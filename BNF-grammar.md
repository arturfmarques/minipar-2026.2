# Gramática BNF da Linguagem MiniPar 2026.2

**Projeto:** Compilador da Linguagem MiniPar 2026.2  
**Autores:** Artur Ferreira Marques da Silva · João Manoel Santos Lima  
**Instituição:** Universidade Federal de Alagoas — Instituto de Computação · Ciência da Computação  
**Disciplina:** Compiladores — Prof. Arturo Hernandez Dominguez  
**Repositório:** https://github.com/arturfmarques/MiniPar-2026.2  
**Revisão:** 11/11/2026

---

## Sumário

1. [Escopo e convenções](#1-escopo-e-convenções)
2. [Gramática léxica](#2-gramática-léxica)
3. [Programa e declarações](#3-programa-e-declarações)
4. [Comandos](#4-comandos)
5. [Controle de fluxo](#5-controle-de-fluxo)
6. [Expressões e precedência](#6-expressões-e-precedência)
7. [Fork, Join e seleção de processador](#7-fork-join-e-seleção-de-processador)
8. [Correspondência com a AST](#8-correspondência-com-a-ast)
9. [Restrições semânticas](#9-restrições-semânticas)
10. [Biblioteca nativa](#10-biblioteca-nativa)
11. [Exemplo completo](#11-exemplo-completo)

---

## 1. Escopo e convenções

> Esta gramática formaliza as construções léxicas e sintáticas implementadas no
> compilador MiniPar 2026.2. As produções foram elaboradas a partir dos módulos
> responsáveis pela análise léxica e sintática (`src/lexer.py` e
> `src/parser.py`), enquanto as restrições de tipos, escopos e utilização dos
> recursos da linguagem são apresentadas separadamente, de acordo com a
> implementação do analisador semântico (`src/semantic.py`), na Seção 9.
> Repositório: <https://github.com/arturfmarques/MiniPar-2026.2>. A gramática
> amplia a BNF 2026.1 do próprio projeto, como exige o enunciado.

Todos os 27 programas `.minipar` do repositório (`tests/` e `examples/`),
incluindo os Testes 1 a 11, são aceitos por esta gramática e pela análise
semântica.

Notação (BNF com abreviações EBNF):

| Símbolo | Significado |
|---|---|
| `<nome>` | não terminal |
| `"texto"` | terminal (token literal) |
| `ID`, `NUM`, `STR` | tokens produzidos pelo analisador léxico |
| `::=` | definição |
| `\|` | alternativa |
| `[ x ]` | ocorrência opcional (0 ou 1) |
| `{ x }` | repetição (0 ou mais) |
| `( x )` | agrupamento |
| `EOF` | fim do arquivo |

Palavras reservadas e símbolos são sensíveis a maiúsculas: `seq`, `par`,
`fork` e `join` são minúsculos; `SEQ` ou `Fork` são identificadores comuns.

---

## 2. Gramática léxica

### 2.1 Palavras reservadas

```text
class    extends  new      this     func     var      return
if       else     while    do       for      in       break    continue
seq      par      fork     join     local    remote
c_channel send    receive  input    print    matrix
true     false
number   int      string   bool     void     list     dict     task
```

Os oito nomes da última linha formam o token `TIPO`. As palavras `true` e
`false` formam o token `BOOL`.

**Palavras contextuais:** `on` e `core` não são reservadas. O analisador léxico
as produz como `ID`; somente ao final de um `fork` o analisador sintático as
interpreta como seletor de processador (Seção 7). Fora desse ponto, são nomes
válidos (`var on = 1;` é aceito).

### 2.2 Tokens

```bnf
ID        ::= ( <letra> | "_" ) { <car_id> }
NUM       ::= <digito> { <digito> } [ "." { <digito> } ]
STR       ::= '"' { <car_string> } '"'
BOOL      ::= "true" | "false"
TIPO      ::= "number" | "int" | "string" | "bool" | "void" | "list" | "dict" | "task"

<car_string> ::= <qualquer caractere exceto '"' e '\'>
               | "\" <qualquer caractere>
<car_id>     ::= <caractere para o qual str.isalnum() é verdadeiro>
               | "_"
<letra>      ::= <caractere para o qual str.isalpha() é verdadeiro>
<digito>     ::= <caractere para o qual str.isdigit() é verdadeiro>
```

Observações sobre os tokens:

* Uma palavra que casa com `ID` e está na lista de reservadas gera o token da
  palavra reservada, e não `ID`.
* Como o Lexer usa `str.isalpha()` e `str.isalnum()` do Python, letras e
  dígitos Unicode também são aceitos em identificadores (por exemplo, `ação`
  e `x²`). Um identificador não pode começar por dígito: `1abc` é lido como
  `NUM` seguido de `ID`.
* `NUM` não tem sinal (o sinal é o operador unário `-`) nem notação
  exponencial; `1.` é um número válido.
* Em `STR`, os escapes `\n`, `\t`, `\"` e `\\` são decodificados; qualquer
  outro caractere após `\` é mantido sem a barra. Quebras de linha reais são
  permitidas dentro da string. Não existem strings com aspas simples.

### 2.3 Operadores e delimitadores

```text
Operadores:    +  -  *  /  %  =  ==  !=  !  &&  ||  <  >  <=  >=  ->
Delimitadores: (  )  {  }  [  ]  .  ;  ,
```

Os operadores de dois caracteres são reconhecidos pelo caractere seguinte
(maior casamento). `&` e `|` isolados são inválidos.

### 2.4 Espaços, comentários e erros léxicos

```bnf
<comentario> ::= "#" { <qualquer caractere exceto nova linha> } ( <nova linha> | EOF )
```

Espaços em branco e comentários são descartados fora de strings. Cada token
registra linha e coluna de início. São erros léxicos (`LexerError`, com linha e
coluna): string sem aspas de fechamento, `\` no fim do arquivo dentro de uma
string e qualquer caractere que não inicie um token.

---

## 3. Programa e declarações

```bnf
<programa>         ::= { <comando> } EOF

<decl_variavel>    ::= <inicio_decl> ID [ "=" <expressao> ] ";"
<inicio_decl>      ::= "var" | <tipo_decl>
<tipo_decl>        ::= TIPO
                     | ( "c_channel" | "matrix" | ID )      (* somente se seguido de ID *)

<tipo>             ::= TIPO | "c_channel" | "matrix" | ID

<decl_funcao>      ::= "func" ID "(" [ <lista_parametros> ] ")" [ "->" <tipo> ] <corpo>
<corpo>            ::= [ "seq" ] "{" { <comando> } "}"
<lista_parametros> ::= <parametro> { "," <parametro> }
<parametro>        ::= [ <tipo_parametro> ] ID
<tipo_parametro>   ::= TIPO | "c_channel" | "matrix"
                     | ID                                    (* somente se seguido de ID *)

<decl_classe>      ::= "class" ID [ "extends" ID ] "{" { <membro_classe> } "}"
<membro_classe>    ::= <decl_variavel> | <decl_funcao>
```

Dois identificadores consecutivos no início de uma declaração ou de um
parâmetro significam *tipo nome* (por exemplo, `Ponto p = new Ponto();` ou
`func f(Usuario u)`). Um parâmetro sem tipo é gradual (`var`). O corpo de uma
função é sempre um bloco entre chaves.

---

## 4. Comandos

```bnf
<comando>          ::= <decl_classe>
                     | <decl_funcao>
                     | <decl_variavel>
                     | <comando_return>
                     | <comando_break>
                     | <comando_continue>
                     | <bloco_seq>
                     | <bloco_par>
                     | <comando_print>
                     | <comando_send>
                     | <comando_if>
                     | <comando_while>
                     | <comando_do_while>
                     | <comando_for>
                     | <atribuicao> ";"
                     | <chamada_como_comando> ";"

<bloco_seq>        ::= [ "seq" ] "{" { <comando> } "}"
<bloco_par>        ::= "par" "{" { <comando> } "}"

<comando_print>    ::= "print" "(" [ <lista_argumentos> ] ")" ";"
<comando_send>     ::= "send" "(" <expressao> "," <expressao> ")" ";"
<comando_return>   ::= "return" ";"
                     | "return" <expressao> [ ";" ]
<comando_break>    ::= "break" [ ";" ]
<comando_continue> ::= "continue" [ ";" ]

<atribuicao>       ::= <alvo> "=" <expressao>
<alvo>             ::= ID
                     | <expressao_posfixa> "." ID
                     | <expressao_posfixa> "[" <expressao> "]"
                     | "(" <alvo> ")"

<chamada_como_comando> ::= <expressao>
                     (* restrição do Parser: ver observações abaixo *)
```

Observações:

* Um comando que começa por expressão é lido inteiro como expressão (por
  `_parse_expression()`); só depois o Parser (`_parse_statement_impl()`)
  decide se ele é válido. Essa restrição é **sintática**, verificada pelo
  Parser, e não pelo analisador semântico:
  * Se vier `=`, o comando é uma atribuição, e o lado esquerdo precisa ser um
    `<alvo>` válido: variável, atributo ou posição indexada
    (`_parse_assignment_tail()`). `f() = 1;` é rejeitado com
    “Atribuicao invalida”.
  * Sem `=`, a expressão isolada só é aceita se for uma chamada de função
    (`FuncCallExpr`), uma chamada de método (`MethodCall`) ou um `join`
    (`JoinExpr`), seguida de `;`. Exemplos válidos: `calcular(1, 2);`,
    `obj.metodo();` e `join(tarefa);`.
  * Parênteses agrupadores não alteram a classificação, pois não geram nó na
    AST: `(f());` e `(join(t));` são aceitos, e `(1 + 2);` continua inválido.
  * Expressões aritméticas, literais ou identificadores isolados (`1 + 2;`,
    `x;`) são rejeitados com “Instrucao ou expressao isolada invalida”.
* `print(...)` e `send(...)` não passam por essa regra: são comandos próprios
  da gramática, iniciados por palavra reservada.
* `fork` não inicia um comando: ele deve inicializar ou atribuir uma variável
  (Seção 7).
* `return` sem valor exige `;`; com valor, e em `break`/`continue`, o `;` é
  opcional por compatibilidade com a versão 2026.1. Recomenda-se sempre
  usá-lo.
* Em `par { ... }`, cada comando filho direto é uma tarefa independente; um
  `seq { ... }` interno agrupa vários comandos de uma mesma tarefa.

---

## 5. Controle de fluxo

```bnf
<comando_if>       ::= "if" "(" <expressao> ")" <comando> [ "else" <comando> ]
<comando_while>    ::= "while" "(" <expressao> ")" <comando>
<comando_do_while> ::= "do" <comando> "while" "(" <expressao> ")" [ ";" ]
<comando_for>      ::= "for" "(" <cabecalho_for> ")" <comando>

<cabecalho_for>    ::= <for_iterador> | <for_classico>
<for_iterador>     ::= "var" ID "in" <expressao>
<for_classico>     ::= [ <inicio_for> ] ";" [ <expressao> ] ";" [ <passo_for> ]
<inicio_for>       ::= "var" ID [ "=" <expressao> ]
                     | <tipo_decl> ID [ "=" <expressao> ]
                     | <expressao>
                     | <alvo> "=" <expressao>
<passo_for>        ::= <expressao>
                     | <alvo> "=" <expressao>
```

O `else` pertence ao `if` sem `else` mais próximo. O iterador exige `var`
(`for (x in lista)` é rejeitado). No inicializador e no passo do `for`
clássico, qualquer expressão é aceita; quando há `=`, o lado esquerdo precisa
ser um `<alvo>` válido (Seção 4), a mesma regra das atribuições comuns. Assim,
`for (i = 0; i < 3; lista[i] = 0)` e `for (p.x = 0; ...; p.x = p.x + 1)` são
aceitos, e `for (1 = 2; true; 1 = 3)` é rejeitado pelo Parser com
“Atribuicao invalida”.

---

## 6. Expressões e precedência

```bnf
<expressao>         ::= <expressao_ou>
<expressao_ou>      ::= <expressao_e> { "||" <expressao_e> }
<expressao_e>       ::= <expressao_comp> { "&&" <expressao_comp> }
<expressao_comp>    ::= <expressao_termo> { <op_comp> <expressao_termo> }
<op_comp>           ::= "==" | "!=" | "<" | ">" | "<=" | ">="
<expressao_termo>   ::= <expressao_fator> { ( "+" | "-" ) <expressao_fator> }
<expressao_fator>   ::= <expressao_unaria> { ( "*" | "/" | "%" ) <expressao_unaria> }
<expressao_unaria>  ::= ( "+" | "-" | "!" ) <expressao_unaria>
                      | <expressao_posfixa>
<expressao_posfixa> ::= <primaria> { <sufixo> }
<sufixo>            ::= "." ID [ "(" [ <lista_argumentos> ] ")" ]
                      | "[" <expressao> "]"

<primaria>          ::= NUM | STR | BOOL
                      | ID [ "(" [ <lista_argumentos> ] ")" ]
                      | "this"
                      | "new" ID "(" [ <lista_argumentos> ] ")"
                      | "[" [ <lista_argumentos> ] "]"
                      | "matrix" "(" <expressao> "," <expressao> "," <expressao> ")"
                      | "c_channel" "(" <expressao> "," <expressao> ")"
                      | "receive" "(" <expressao> ")"
                      | "input" "(" [ <expressao> ] ")"
                      | <expressao_fork>
                      | <expressao_join>
                      | "(" <expressao> ")"

<lista_argumentos>  ::= <expressao> { "," <expressao> }
```

| Nível | Operadores | Associatividade |
|:---:|---|---|
| 1 (menor) | `\|\|` | esquerda |
| 2 | `&&` | esquerda |
| 3 | `==` `!=` `<` `>` `<=` `>=` | esquerda |
| 4 | `+` `-` | esquerda |
| 5 | `*` `/` `%` | esquerda |
| 6 | `+` `-` `!` unários | direita |
| 7 (maior) | chamada, `.campo`, `.metodo()`, `[índice]` | esquerda |

Parênteses prevalecem sobre a precedência. Comparações encadeadas são aceitas
pela sintaxe como `(a < b) < c`, mas a análise semântica as rejeita por
comparar bool com número. `&&` e `||` têm curto-circuito. A divisão `/` é
sempre real.

---

## 7. Fork, Join e seleção de processador

```bnf
<expressao_fork>  ::= "fork" <destino> ID "(" [ <lista_argumentos> ] ")" [ <afinidade> ]
<destino>         ::= "local"
                    | "remote" "(" <expressao> "," <expressao> ")"   (* host, porta *)
<afinidade>       ::= "on" "core" "(" <expressao> ")"                 (* on e core: ID contextual *)
<expressao_join>  ::= "join" "(" ID ")"
```

Exemplo aceito:

```minipar
func square(number value) -> number { return value * value; }
seq {
    var a = fork local square(7);
    task b = fork remote("127.0.0.1", 7000) square(8);
    var c = fork local square(9) on core(1);
    number x = join(a);
    print(x, join(b), join(c));
}
```

---

## 8. Correspondência com a AST

Cada produção gera um nó de `src/ast_nodes.py`:

| Produção | Nó da AST |
|---|---|
| `<programa>` | `Program` |
| `<decl_classe>`, `<decl_funcao>`, `<decl_variavel>` | `ClassDecl`, `FuncDecl`, `VarDecl` |
| `<bloco_seq>`, `<bloco_par>` | `SeqBlock`, `ParBlock` |
| `<comando_if>`, `<comando_while>`, `<comando_do_while>`, `<comando_for>` | `IfStmt`, `WhileStmt`, `DoWhileStmt`, `ForStmt` |
| `<comando_return>`, `<comando_break>`, `<comando_continue>` | `ReturnStmt`, `BreakStmt`, `ContinueStmt` |
| `<comando_print>`, `<comando_send>` | `PrintStmt`, `SendStmt` |
| `<atribuicao>` com alvo ID / atributo / índice | `Assignment` / `PropertyAssign` / `IndexAssign` |
| operadores binários e unários | `BinaryExpr`, `UnaryExpr` |
| `NUM`, `STR`, `BOOL`, `ID` | `NumberExpr`, `StringExpr`, `BoolExpr`, `IdentifierExpr` |
| chamada, método, atributo, índice | `FuncCallExpr`, `MethodCall`, `PropertyAccess`, `IndexExpr` |
| `new`, `this`, lista, `matrix` | `NewExpr`, `ThisExpr`, `ListLiteral`, `MatrixCreateExpr` |
| `c_channel`, `receive`, `input` | `CChannelExpr`, `ReceiveExpr`, `InputExpr` |
| `<expressao_fork>`, `<destino>` + `<afinidade>`, `<expressao_join>` | `ForkExpr`, `TaskDestination` (`kind`, `host`, `port`, `core`), `JoinExpr` |

---

## 9. Restrições semânticas

A gramática aceita algumas formas que a análise semântica rejeita. As regras
abaixo são verificadas em `src/semantic.py`; erros impedem a geração de TAC e
C++.

**Declarações e escopos**

* Classes e funções só podem ser declaradas no escopo global; não há funções
  aninhadas. Funções nativas não podem ser redefinidas.
* Um nome não pode ser declarado duas vezes no mesmo escopo; escopos internos
  podem sombrear nomes externos. Blocos, ramos de `if`, laços, funções,
  classes e cada tarefa de `par` abrem escopo.
* `void` só é válido como tipo de retorno; `task` não pode ser tipo de
  parâmetro. `dict` é aceito apenas como nome de tipo legado, sem operações.
* Uma variável `task` deve ser inicializada por `fork` ou por outro handle de
  tarefa.

**Tipos**

* Aritmética exige números; `+` também aceita duas strings ou duas listas.
  `&&`, `||` e `!` aceitam bool ou número. Comparações exigem tipos
  compatíveis. `void` e handles de tarefa não são operandos.
* Condições de `if`, `while`, `do` e `for` aceitam bool ou número.
* O tipo `int` corresponde a um inteiro assinado de 64 bits. Literais
  numéricos incompatíveis com esse tipo são identificados durante a análise
  semântica (`int x = 1.5;` e `int x = 9223372036854775808;` são
  rejeitados). Conversões e operações avaliadas dinamicamente também possuem
  verificações em tempo de execução, incluindo a detecção de overflow (por
  exemplo, `int x = a;` com `a` igual a 1.5, ou `big + 1` com
  `big = 9223372036854775807`, terminam com `[ERRO RUNTIME]`). Literais
  numéricos sem contexto `int` são tratados como `number`, representado por
  ponto flutuante de dupla precisão.
* Elementos de lista devem ter tipos compatíveis. Índices são numéricos e
  indexação vale para lista, matriz ou string. `for-in` percorre lista,
  matriz ou string.
* Quando o retorno é declarado e diferente de `void`, todos os caminhos devem
  retornar. Retornos não declarados são inferidos.

**Funções, classes e objetos**

* Chamadas devem respeitar a aridade e os tipos conhecidos dos parâmetros.
* A superclasse deve existir e não pode haver ciclo de herança. Atributos e
  métodos são procurados na classe e nos ancestrais.
* `new C(args)` chama o método `init` de `C` (ou herdado), que deve retornar
  `void`; sem `init`, `new C()` não recebe argumentos.
* `this` só dentro de métodos; `return` só dentro de funções ou métodos;
  `break` e `continue` só dentro de laços do mesmo contexto.

**Canais**

* Em `c_channel(host, porta)` e em `remote(host, porta)`, o host é string não
  vazia e a porta, se literal, é inteiro entre 1 e 65535.
* `send` e `receive` exigem um `c_channel`; `send` aceita apenas escalares
  (número, bool ou string). `receive` e `input` retornam string.

**Tarefas (PAR, Fork e Join)**

* Uma tarefa de `par` não pode escrever em variável, coleção ou objeto de
  escopo externo (leitura é permitida, por cópia) nem usar `return`.
* `fork` deve ser o valor direto de uma declaração ou atribuição.
* O alvo de `fork` deve ser uma função global declarada (não método, não
  função nativa, não sombreada por variável).
* A função alvo, e todas as funções que ela chama, não podem ler variáveis
  globais; dados e canais devem ser passados como argumentos.
* Handles de tarefa e valores `void` não podem ser argumentos de `fork`,
  parâmetros, retornos ou elementos de lista.
* `on core(n)` só é permitido com `fork local`; `n` deve ser numérico, inteiro
  e não negativo, e é o ID de um processador **lógico** do sistema
  operacional.
* `join(t)` exige que `t` seja um handle `task<T>` e devolve um valor `T`.
* `fork remote` só aceita argumentos de tipos serializáveis (número, int,
  bool, string, lista, matriz ou canal); objetos não são enviados.

---

## 10. Biblioteca nativa

As funções abaixo usam a produção comum de chamada (`ID "(" ... ")"`); não são
palavras reservadas. Assinaturas em `src/native_builtins.py`.

| Função | Argumentos | Retorno |
|---|---|---|
| `exp`, `floor` | número | number |
| `random`, `monotonic` | — | number |
| `range` | um ou dois números | list |
| `len` | lista, matriz ou string | number |
| `to_number` | string | number |
| `parse_ints` | string | list |
| `to_string` | escalar | string |
| `available_cpus` | — | list |
| `current_cpu` | — | number |
| `write_text` | caminho, conteúdo (strings) | void |
| `try_write_text` | caminho, conteúdo (strings) | bool |
| `get_env` | nome, valor padrão (strings) | string |
| `require` | condição (bool), mensagem (string) | void |
| `is_finite` | número | bool |
| `set_exit_code` | inteiro de 0 a 255 | void |

Métodos de listas e matrizes: `.append(v)` / `.push_back(v)`, `.pop()`,
`.clear()` e `.size()`; strings têm `.size()`.

---

## 11. Exemplo completo

```minipar
# Teste 2: fatorial e Fibonacci em paralelo
func fatorial(number n) -> number {
    var fat = 1;
    var i = 1;
    while (i <= n) {
        fat = fat * i;
        i = i + 1;
    }
    return fat;
}

func fibonacci(number limite) -> list {
    var serie = [];
    var a = 0;
    var b = 1;
    var i = 0;
    while (i < limite) {
        serie.append(a);
        var prox = a + b;
        a = b;
        b = prox;
        i = i + 1;
    }
    return serie;
}

par {
    seq { print("Fatorial de 5:", fatorial(5)); }
    seq {
        var serie = fibonacci(8);
        print("Fibonacci:");
        for (var valor in serie) { print(valor); }
    }
}
```
