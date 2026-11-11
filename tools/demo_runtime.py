"""Demonstração real do exemplo misto em dois processos, com relatório JSON."""
from pathlib import Path
import json
import os
import queue
import subprocess
import sys
import threading
import argparse

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from main import compile_file
from toolchain import runtime_environment,executable_suffix


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('examples/fork_join_mixed.minipar'))
    parser.add_argument('--report',type=Path,default=Path('output/validacoes/runtime-demo.json'))
    parser.add_argument('--expect-line',action='append')
    arguments=parser.parse_args()
    os.chdir(ROOT)
    report={'source':str(arguments.source)}
    if not compile_file(str(ROOT/report['source']),'demo_mixed'):
        return 1
    executable=ROOT/'output'/('demo_mixed'+executable_suffix())
    server=None
    try:
        environment=runtime_environment()
        environment['MINIPAR_TRACE']=str(ROOT/'output/demo-worker.tsv')
        server=subprocess.Popen([str(executable),'--worker','--port','7000','--max-requests','1'],
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=environment)
        lines=queue.Queue()
        def ready(): lines.put(server.stdout.readline())
        thread=threading.Thread(target=ready,daemon=True); thread.start()
        line=lines.get(timeout=10)
        if not line.startswith('MINIPAR_WORKER_READY '):
            raise RuntimeError('Trabalhador nao iniciou: '+line+server.stderr.read())
        report['worker']=json.loads(line.split(' ',1)[1]); report['worker_pid']=server.pid
        environment['MINIPAR_TRACE']=str(ROOT/'output/demo-parent.tsv')
        client=subprocess.Popen([str(executable)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=environment)
        try: stdout,stderr=client.communicate(timeout=15)
        except subprocess.TimeoutExpired: client.kill(); client.communicate(); raise
        report.update(parent_pid=client.pid,returncode=client.returncode,stdout=stdout,stderr=stderr)
        worker_stdout,worker_stderr=server.communicate(timeout=10)
        report.update(worker_returncode=server.returncode,worker_stdout=worker_stdout,worker_stderr=worker_stderr)
        expected='\n'.join(arguments.expect_line or ['x = 49','y = 64'])+'\n'
        report['expected_stdout']=expected
        report['success']=(client.returncode==server.returncode==0 and stdout==expected and client.pid!=server.pid)
    except Exception as error:
        report.update(success=False,error=str(error))
    finally:
        if server and server.poll() is None:
            server.terminate(); server.wait(timeout=5)
    target=ROOT/arguments.report
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0 if report.get('success') else 1


if __name__=='__main__':
    sys.exit(main())
