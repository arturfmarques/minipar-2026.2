# Modelagem UML do MiniPar 2026.2

> Material provisório preservado para revisão acadêmica posterior.

Fontes próprias, baseadas no código local, para os itens 10–12 da página 48
do enunciado. A página 49 exige acrescentar TAC e C/C++ ao exemplo de componentes.

| Artefato | Fonte editável | Renderização |
| --- | --- | --- |
| Casos de uso | [casos-de-uso.puml](casos-de-uso.puml) | [SVG](casos-de-uso.svg) |
| Componentes | [componentes.puml](componentes.puml) | [SVG](componentes.svg) |
| Classes principais | [classes.puml](classes.puml) | [SVG](classes.svg) |

Atores dos casos de uso são papéis de utilização, não contas/controle de acesso
implementados. A compilação nativa depende de G++ externo. O trabalhador é
iniciado explicitamente e executa funções registradas no mesmo programa.

No diagrama de componentes, contratos `tokenize`, `parse` e `analyze` são
métodos reais, não classes de interface adicionadas. `main.compile_file` e
`educational_pipeline.analyze_source` são as duas fachadas existentes que usam
os mesmos componentes. A tabela de símbolos está contida em `SemanticAnalyzer`,
com dicionários de `Symbol`. Não se desenhou uma classe inexistente para ela.
Os dois geradores consomem a AST; não há dependência fictícia TAC → C++.

O diagrama de classes seleciona as classes centrais e nós relevantes para
tarefas/OO; não pretende listar cada dataclass ou cada template C++ do runtime.
`CompilerError` herda de `ValueError` em Python; subclasses específicas e
`Diagnostic` representam a propagação estruturada dos erros. As associações
mostram referências/posse lógica, sem afirmar persistência em banco de dados.

Para reproduzir com Java e o JAR da [distribuição oficial PlantUML](https://plantuml.com/download):

```powershell
java -jar CAMINHO/plantuml-1.2026.9.jar -charset UTF-8 -tsvg docs/uml/*.puml
```

Usou-se PlantUML 1.2026.9 e Java 25.0.2. Casos de uso e componentes usam Smetana;
classes usam o Graphviz 2.44.1 detectado pela distribuição. Smetana é integrado,
conforme a [documentação oficial](https://plantuml.com/smetana02). O JAR é
ferramenta temporária de documentação; não foi adicionado às dependências ou
ao conteúdo publicável. SVGs são vetoriais, com texto ampliável. Evidências
de renderização e integridade constam da auditoria da etapa 4.
I1, I2 e I3 no diagrama de componentes identificam os contratos detalhados
na legenda. Os identificadores curtos evitam sobrepor rótulos das interfaces.
Abra os SVGs com zoom para inspeção; na diagramação acadêmica, reserve página
paisagem ou ampliação para os diagramas de componentes/classes, sem comprimir
seus textos em uma coluna.
