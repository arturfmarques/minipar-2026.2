# Programas MiniPar 8, 9 e 10

A etapa 1/5 acrescentou [afinidade opcional](affinity-distributed-2026.2.md).
`python tools/validate_affinity.py` gera cópias temporárias com `on core(...)`
para 4/5/6 IDs lógicos permitidos e valida resultados/CPU observada. Os fontes
obrigatórios abaixo continuam sem essa exigência e sem alteração de algoritmo.
As medições anteriores de barreira não são reclassificadas como prova de afinidade.

Os arquivos em tests/ são programas completos, independentes e compiláveis em
MiniPar. Nenhum algoritmo é executado por Python durante sua execução. Python
implementa o compilador, inicia processos nos testes e compara resultados com
oráculos independentes. O backend não contém seleção pelo nome dos programas.

## Atividades e divisão de trabalho

Cada programa cria 40 alunos × 4 atividades = 160 registros. IDs internos vão
de 0 a 159; alunos e atividades individuais são numerados a partir de 1.
Grupos contíguos de 40 atividades correspondem a Professor e Monitores 1–3.
As funções comuns estão iguais nos três fontes, verificado por testes da AST;
não foi acrescentado um sistema de imports/includes à linguagem.

A referência simula avaliação por carga CPU, sem atribuir notas. A conversão
preserva esse algoritmo: para cada atividade, calcula um número de iterações
e soma de 0 a n−1 num laço MiniPar. O checksum é retornado e verificado para
que o trabalho tenha resultado observável. Não há sleep como carga nem saída
de conclusão pré-calculada.

O LCG mantém multiplicador 1103515245, incremento 12345, módulo 2³¹ e semente
123456789. A multiplicação modular é decomposta em partes de 16 bits, mantendo
os inteiros exatos em double sem introduzir operadores bitwise na gramática.
As 160 sementes são criadas antes da medição e associadas aos registros,
para que sequencial e paralelo executem a mesma quantidade de trabalho.
Isso elimina a diferença de estado aleatório entre processos da referência.

Para uma semente s, n=floor((0,05+0,10×s/2147483647)×1500000×fator).
Esse coeficiente vem da referência; não significa que a atividade levará
0,05–0,15 segundos em C++ compilado. O tempo real é medido por steady_clock.
`MINIPAR_WORK_FACTOR` tem padrão 1 e intervalo 0,001 a 10. Os testes de benchmark
usam 1; outros fatores permitem variar a carga sem alterar os resultados de
identificação/cobertura das atividades.

Cada modo devolve 160 linhas `ATIVIDADE modo id aluno atividade avaliador n soma`.
No sequencial, Professor (ID 0) executa todas; no paralelo, cada avaliador
executa 40. Comparações entre modos ignoram apenas essa atribuição de papel.
IDs, alunos, atividades, iterações e checksums precisam corresponder.

## Fork, barreiras e Join

Teste 8 lança quatro tarefas de avaliação; Teste 9 lança também Mandelbrot;
Teste 10 lança ainda Sierpinski, **antes de qualquer Join**. Funções recebem
explicitamente seus lotes/parâmetros e canais; não capturam estado global.
Resultados vêm dos futures tipados por Join e são combinados no principal.

Uma barreira usa c_channel: cada tarefa anuncia seu ID e espera a liberação
no próprio canal. O principal exige todos os IDs distintos e só então libera
os canais. Isso comprova que todas as tarefas foram iniciadas antes de qualquer
uma terminar, inclusive os fractais rápidos. A ordem de chegada/finalização
não é fixada nem usada como condição de aprovação.

Traces com `MINIPAR_TRACE` registram spawn, task_start/end, join_begin/end e,
no remoto, worker_start/end/remote_result. Os testes exigem sobreposição dos
intervalos de vida e todos os resultados coletados. Intervalos incluem espera
na barreira; não são prova de instruções simultâneas nem de afinidade. Threads
reais são escalonadas pelo SO e podem ocupar núcleos diferentes.

## Mandelbrot

Os Testes 9/10 calculam iterações de z=z²+c com componentes reais zx/zy.
Padrão: largura 50, altura 20, máximo 100, cx=x/largura×3−2 e
cy=y/altura×2,4−1,2. A condição de escape é zx²+zy² > 4.
O caractere é selecionado de ` .:-=+#%@` por
floor(iteracao/max_iter×(len(paleta)−1)), como na referência.

O retorno string tem exatamente 20 linhas de 50 caracteres. O programa verifica
igualdade entre os modos. Os testes comparam também as matrizes completas de
iterações, incluindo outras dimensões e limites; o desenho não é uma string pronta.

## Sierpinski e arquivo gráfico

O Teste 10 usa o lado 300 e profundidade 4 da referência. Um quadrado inicial
navy é perfurado por um centro branco; há oito chamadas recursivas para os
subquadrados restantes, repetindo até grau zero. A saída padrão contém 585
retângulos centrais brancos, além do fundo, e é SVG válido e visualizável.
Os testes conferem a geometria de todos os retângulos, limites, dimensões,
contagem por profundidade e igualdade de bytes entre as duas execuções.

Arquivos padrão:

- `output/teste10-sierpinski-seq.svg`
- `output/teste10-sierpinski-par.svg`

`MINIPAR_OUTPUT_PREFIX` troca o prefixo (sem extensão); o diretório pai deve
existir. A tarefa paralela escreve o arquivo e retorna o caminho ao principal.
Erro de escrita é propagado por Join. A versão sequencial também gera seu SVG
dentro do intervalo medido, corrigindo a omissão da referência Python. O Turtle
original executava após a sincronização; aqui Sierpinski é a sexta tarefa real.

## Compilar, selecionar e executar

Na raiz, com o Python/G++ já configurados:

```powershell
python main.py tests/teste8_avaliacao_paralela.minipar
python main.py tests/teste9_avaliacao_mandelbrot.minipar
python main.py tests/teste10_avaliacao_fractais.minipar
$env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH
.\output\teste8_avaliacao_paralela.exe
.\output\teste9_avaliacao_mandelbrot.exe
.\output\teste10_avaliacao_fractais.exe
```

O menu (`python main.py`, opção terminal) e a lista Web descobrem os três
arquivos em tests/ automaticamente. Canais internos de programas Fork/Join
não solicitam participantes extras na coordenação de terminais antiga.
A Web carrega o fonte, usa o CLI comum e apresenta os resultados e links SVG.
Linhas `ARQUIVO: caminho` anunciam os artefatos; a rota de visualização só
serve SVGs resolvidos dentro de output/, com CSP sandbox. Programas inválidos
ou que falharam não retornam links de sucesso.

O limite Web de execução continua 30 s e o de compilação 125 s. O menu passou
a limitar a execução sem input a 30 s; a entrada interativa antiga foi mantida.
Não houve aumento geral de timeouts nem criação de segunda interface.

## Configuração de canais e execução remota

`MINIPAR_SYNC_BASE_PORT` escolhe a porta de prontidão; os próximos N números
formam os canais de liberação. Padrões: Teste 8 usa 5800–5804, Teste 9 usa
5900–5905 e Teste 10 usa 6000–6006. As portas devem estar livres. O runtime
continua validando host/porta e reporta conflitos/timeouts.

O Teste 8 suporta quatro avaliações no trabalhador remoto. Compila-se uma vez
e usa-se o mesmo executável/registro nos dois processos:

```powershell
# Terminal trabalhador, antes de executar o cliente:
python tools/run_worker.py output/teste8_avaliacao_paralela.exe --port 7000 --max-requests 4

# Terminal cliente (PATH das DLLs preparado):
$env:MINIPAR_REMOTE = '1'
$env:MINIPAR_REMOTE_HOST = '127.0.0.1'
$env:MINIPAR_REMOTE_PORT = '7000'
$env:MINIPAR_PARENT_HOST = '127.0.0.1'
.\output\teste8_avaliacao_paralela.exe
```

O trabalhador precisa permitir ao menos quatro handlers simultâneos (padrão 8),
pois todos chegam à barreira antes da liberação. Os argumentos são matrizes
numéricas e descritores de canais, já suportados pelo protocolo. Não há memória
compartilhada entre processos. A suíte verifica PIDs distintos, quatro respostas
RPC do worker e todos os 160 resultados.

Para futura LAN, configure os IPs do trabalhador e cliente, --host no worker,
MINIPAR_CHANNEL_BIND em cada receptor e firewall para os canais de retorno e
liberação. A versão do programa deve coincidir. Não foram testadas máquinas
físicas distintas, Linux ou afinidade. O serviço não tem autenticação/TLS;
os limites do runtime continuam no [manual](runtime-2026.2.md).
Para voltar ao modo local, remova as variáveis da demonstração remota ou use
MINIPAR_REMOTE=0 com hosts de canal locais.

## Biblioteca genérica e equivalência da medição

Novos builtins: floor, to_string, monotonic, write_text, get_env e require.
As assinaturas estão na [BNF](../BNF-grammar.md#10-biblioteca-nativa) e em
src/native_builtins.py. Lexer, parser, AST e sintaxe Fork/Join foram preservados;
o TAC usa as produções/chamadas existentes. C++ gerado continua autossuficiente.

Tempos incluem chamadas de avaliação e fractais de cada cenário. No paralelo,
incluem snapshots, async, canais de barreira, Join e combinação; no remoto,
incluem conexão/transporte RPC. Criação de atividades/sementes/fatias, configuração
dos descritores, compilação e apresentação das linhas ficam fora de ambos.
O trabalhador remoto é iniciado antes da medição; seu startup não é contado.
SVG é escrito em ambos os modos. Não há aquecimento deliberado.

As fórmulas são tempo_seq/tempo_par e ((tempo_seq−tempo_par)/tempo_seq)×100.
A implementação nativa executa a pequena carga CPU muito rapidamente; canais
e sincronização podem dominar, gerando speedup < 1 e redução negativa. Nenhum
teste exige aceleração e nenhuma medição constitui garantia de desempenho.
Benchmarks e observações reais estão no [diagnóstico](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/diagnostico-2026.2.md#15-programas-paralelos-8-9-e-10).

```powershell
python tools/validate_parallel.py
python -m pytest
```

O primeiro comando registra fases, comandos G++, entrada/saída, métricas e
checks dos fractais em output/validacoes/validacao-8910.json. O segundo executa
também toda a regressão anterior. Testes negativos incluem parâmetros inválidos,
duplicatas/perdas, checksum incorreto, tarefa/Join/argumentos inválidos, trabalhador
indisponível e falha de arquivo. Teste 11 e segunda Web permanecem fora desta etapa.
