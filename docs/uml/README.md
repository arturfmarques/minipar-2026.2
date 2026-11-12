# Diagramas UML — MiniPar 2026.2

A modelagem UML representa os principais componentes e atores envolvidos no MiniPar 2026.2. Os arquivos-fonte PlantUML (`.puml`) são mantidos juntamente com as versões vetoriais (`.svg`) para consulta e atualização.

## Diagramas disponíveis

| Diagrama | Fonte PlantUML | Visualização |
| --- | --- | --- |
| Casos de uso | [casos-de-uso.puml](casos-de-uso.puml) | [casos-de-uso.svg](casos-de-uso.svg) |
| Componentes | [componentes.puml](componentes.puml) | [componentes.svg](componentes.svg) |
| Classes | [classes.puml](classes.puml) | [classes.svg](classes.svg) |

**Casos de uso:** edição de programas, compilação, execução, visualização dos artefatos e utilização do trabalhador remoto.

**Componentes:** três interfaces, analisadores, tabela de símbolos, geradores de TAC e C++, toolchain e runtime de execução. Os geradores de TAC e C++ consomem a AST validada, sem dependência de tradução de um arquivo TAC para C++.

**Classes:** visão dos principais objetos do compilador e suas associações, incluindo Lexer, Parser, nós da AST, SemanticAnalyzer, TACGenerator e CppCodeGenerator.

## Reprodução dos SVGs

Para regenerar os arquivos, use o [PlantUML](https://plantuml.com/) instalado ou seu arquivo JAR, com suporte a SVG:

```powershell
java -jar plantuml.jar -tsvg docs/uml/casos-de-uso.puml docs/uml/componentes.puml docs/uml/classes.puml
```

Os diagramas também estão incorporados ao [relatório técnico](../Relatorio-Minipar2026.2.pdf).
