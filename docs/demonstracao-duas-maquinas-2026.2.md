# Execução de Fork remoto em dois computadores

Este documento descreve a configuração de uma demonstração em rede local com dois computadores Windows. A comunicação TCP e o trabalhador foram verificados entre processos no mesmo computador; **este roteiro não é um registro de execução já realizada entre duas máquinas físicas**.

## Pré-requisitos

- Dois computadores na mesma rede autorizada, com o ambiente de execução MiniPar preparado.
- G++/MSYS2 compatível com o executável C++20 gerado e suas DLLs disponíveis.
- Um computador **A** para iniciar o cliente e um computador **B** para iniciar o trabalhador.
- Porta TCP livre, por exemplo `7000`, e permissão de rede/firewall.

## Preparar o executável

No computador A, compile o exemplo:

```powershell
py main.py examples/fork_join_network.minipar network_demo
$env:Path = 'C:\msys64\mingw64\bin;' + $env:Path
.\output\network_demo.exe --manifest
```

Copie `output/network_demo.exe` para `output/` no computador B, preservando o mesmo programa. Compare os manifests e, se necessário, a soma SHA-256 dos binários.

## Computador B: trabalhador

```powershell
ipconfig
$env:Path = 'C:\msys64\mingw64\bin;' + $env:Path
py tools/run_worker.py output/network_demo.exe --host 0.0.0.0 --port 7000 --workers 4
```

O endereço `0.0.0.0` é o endereço de escuta do servidor, não o IP que deve ser usado pelo cliente. Identifique o IPv4 real da interface LAN. Configure uma regra de firewall restrita à rede autorizada somente se necessário.

## Computador A: cliente

```powershell
$env:MINIPAR_WORKER_HOST = Read-Host 'IPv4 do computador B'
$env:MINIPAR_WORKER_PORT = '7000'
Test-NetConnection -ComputerName $env:MINIPAR_WORKER_HOST -Port 7000
$env:Path = 'C:\msys64\mingw64\bin;' + $env:Path
.\output\network_demo.exe
```

Para o exemplo de quadrados, o resultado esperado é `49` e `64`. Registre a identificação dos dois computadores, o IP de B, os processos e o resultado do cliente. Interromper o trabalhador deve produzir uma falha remota identificável, sem substituir silenciosamente a operação por uma tarefa local.

O protocolo de demonstração não implementa autenticação/TLS. Utilize apenas uma rede de teste confiável e autorizada. Consulte [runtime](runtime-2026.2.md) para a arquitetura de comunicação.
