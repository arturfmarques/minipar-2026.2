# Demonstração presencial em duas máquinas Windows

**Situação: não executada em duas máquinas físicas.** O runtime/RPC foi
testado com processos distintos em localhost. Este roteiro atende à preparação
solicitada nas pp. 3 e 10–11 do PDF, sem inventar IPs, PIDs ou medições.

## Preparação

Use dois computadores A (cliente/pai) e B (trabalhador), em LAN confiável.
Prepare dependências/G++ em ambos conforme o README. Na raiz de A:

```powershell
python main.py examples/fork_join_network.minipar network_demo
$env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH
.\output\network_demo.exe --manifest
Get-FileHash .\output\network_demo.exe -Algorithm SHA256
```

Transfira esse executável para `output/network_demo.exe` em B. Pode compilar
o mesmo fonte/versão em B, mas não misture runtimes. Compare o identificador
`program=` dos manifests; se foi o mesmo binário transferido, compare também
seu SHA256. O binário depende das DLLs do G++ compatível, resolvidas pelo
wrapper `tools/run_worker.py` usando a configuração de toolchain de B.

## Computador B

```powershell
hostname
ipconfig
$env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH
.\output\network_demo.exe --manifest
Get-FileHash .\output\network_demo.exe -Algorithm SHA256
$env:MINIPAR_TRACE = Join-Path (Get-Location) 'output/network-worker.tsv'
python tools/run_worker.py output/network_demo.exe --host 0.0.0.0 --port 7000 --workers 4
```

Registre o IPv4 real da interface LAN e a mensagem `MINIPAR_WORKER_READY`, com
PID, porta e hash efetivamente impressos. `0.0.0.0` é endereço de escuta, não
o destino a configurar no cliente. O worker fica em execução até Ctrl+C.

Se necessário, o administrador de B pode criar uma regra **temporária** para
essa porta em rede privada. Os comandos abaixo são instruções, não foram
executados nesta auditoria:

```powershell
New-NetFirewallRule -DisplayName 'MiniPar demonstracao TCP 7000' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 7000 -Profile Private -RemoteAddress LocalSubnet
# Após a demonstração:
Remove-NetFirewallRule -DisplayName 'MiniPar demonstracao TCP 7000'
```

Não altere políticas institucionais sem o administrador. O protocolo atual
não tem autenticação/TLS; use somente o ambiente de demonstração autorizado.

## Computador A

```powershell
hostname
$env:MINIPAR_WORKER_HOST = Read-Host 'IPv4 real do computador B'
$env:MINIPAR_WORKER_PORT = '7000'
$env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH
Test-NetConnection -ComputerName $env:MINIPAR_WORKER_HOST -Port 7000
$env:MINIPAR_TRACE = Join-Path (Get-Location) 'output/network-client.tsv'
.\output\network_demo.exe
Get-Content .\output\network-client.tsv
```

O resultado esperado pelo algoritmo é `CLIENTE recebeu 49 64`, calculado por
duas chamadas remotas de quadrado. Em B devem aparecer os prints da função e
`worker_start/worker_end` no trace. Em A, `remote_result` registra o PID do
worker e Join coleta valores. Esses números são resultados esperados, não
evidência de que o ensaio presencial já ocorreu.

## Registro necessário

Capture A e B com identificação do equipamento, horário real, manifest, porta,
IP LAN efetivo, processos e traces dos dois lados. Não use só duas janelas no
mesmo computador como comprovação física. Pare B e execute A novamente para
mostrar falha remota explícita, sem resultado local substituto. Depois encerre
os processos e remova somente a regra temporária criada para a demonstração.

Os Testes 1 e 2 do PDF também pedem duas máquinas. Este exemplo comprova o
mecanismo geral; não transforma seus fontes localhost em versões já
demonstradas remotamente. Antes de apresentar esses casos específicos, adaptar
somente configuração/main de demonstração, usar as mesmas funções e repetir
os oráculos, preservando os programas entregues. Essa adaptação e execução
presencial permanecem pendentes; não foram realizadas nesta etapa.

Detalhes e limites de mensagens/afinidade:
[manual do runtime](runtime-2026.2.md) e
[manual de afinidade](affinity-distributed-2026.2.md).
