"""Testes nativos A-N: resultados calculados pelo C++, TCP e barreiras reais."""
from contextlib import contextmanager
from pathlib import Path
import json
import os
import queue
import socket
import struct
import subprocess
import threading
import time
import pytest
from lexer import Lexer
from parser import Parser
from semantic import SemanticAnalyzer
from codegen import CppCodeGenerator
from toolchain import compile_cpp, executable_suffix, runtime_environment

ROOT=Path(__file__).resolve().parents[2]
EVIDENCE=ROOT/'output/validacoes/runtime-tests.json'
OBSERVATIONS=[]
pytestmark=pytest.mark.native


def observe(name, **data):
    OBSERVATIONS.append({'test':name,**data})
    EVIDENCE.parent.mkdir(parents=True,exist_ok=True)
    EVIDENCE.write_text(json.dumps(OBSERVATIONS,indent=2,ensure_ascii=False),encoding='utf-8')


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    directory=tmp_path_factory.mktemp('runtime')
    ast=Parser(Lexer((ROOT/'tests/fixtures/runtime.minipar').read_text(encoding='utf-8')).tokenize()).parse()
    analyzer=SemanticAnalyzer()
    assert analyzer.analyze(ast), analyzer.diagnostics
    cpp=directory/'runtime.cpp'
    cpp.write_text(CppCodeGenerator(analyzer).render(ast),encoding='utf-8')
    exe=directory/('runtime'+executable_suffix())
    built=compile_cpp(cpp,exe)
    observe('compile',command=built.args,returncode=built.returncode,stderr=built.stderr)
    assert built.returncode==0,built.stderr
    return exe


def environment(extra=None):
    return {**runtime_environment(),'MINIPAR_TIMEOUT_MS':'5000','MINIPAR_CONNECT_TIMEOUT_MS':'1500',
            'MINIPAR_JOIN_TIMEOUT_MS':'8000',**(extra or {})}


def execute(binary, mode, *values, extra=None):
    result=subprocess.run([str(binary)],input='\n'.join([mode,*map(str,values)])+'\n',
                          capture_output=True,text=True,encoding='utf-8',errors='replace',
                          env=environment(extra),timeout=20)
    observe(mode,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
    return result


class Running:
    def __init__(self,command,inputs=None,extra=None):
        self.process=subprocess.Popen(list(map(str,command)),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,text=True,encoding='utf-8',env=environment(extra))
        self.lines=[]; self.errors=[]; self.queue=queue.Queue()
        def output():
            for line in self.process.stdout:
                self.lines.append(line); self.queue.put(line.rstrip('\n'))
        def errors():
            self.errors.extend(self.process.stderr)
        self.readers=[threading.Thread(target=output,daemon=True),threading.Thread(target=errors,daemon=True)]
        for reader in self.readers: reader.start()
        if inputs is not None:
            self.process.stdin.write('\n'.join(map(str,inputs))+'\n'); self.process.stdin.flush()
            self.process.stdin.close()
    def line(self, expected=None,timeout=8):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            try: line=self.queue.get(timeout=min(.1,max(.001,until-time.monotonic())))
            except queue.Empty:
                if self.process.poll() is not None: break
                continue
            if expected is None or line==expected: return line
        raise AssertionError(f'Linha {expected!r} nao recebida; pid={self.process.pid}; stdout={self.lines}; stderr={self.errors}')
    def finish(self,timeout=15):
        code=self.process.wait(timeout=timeout)
        for reader in self.readers: reader.join(timeout=2)
        return code,''.join(self.lines),''.join(self.errors)
    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=3)
            except subprocess.TimeoutExpired: self.process.kill(); self.process.wait(timeout=3)
        for reader in self.readers: reader.join(timeout=2)


@contextmanager
def worker(binary,tmp_path,requests=1):
    trace=tmp_path/'worker.tsv'
    running=Running([binary,'--worker','--port','0','--max-requests',requests],extra={'MINIPAR_TRACE':str(trace)})
    try:
        line=running.line()
        assert line.startswith('MINIPAR_WORKER_READY '),(line,running.errors)
        ready=json.loads(line.split(' ',1)[1])
        assert ready['host']=='127.0.0.1' and ready['pid']==running.process.pid
        yield running,ready,trace
    finally:
        running.stop()


def exact(connection,count):
    chunks=[]
    while count:
        part=connection.recv(count)
        if not part: raise EOFError('frame incompleto')
        chunks.append(part); count-=len(part)
    return b''.join(chunks)


def frame(connection,payload):
    connection.sendall(struct.pack('!I',len(payload))+payload)


def receive_frame(connection):
    return exact(connection,struct.unpack('!I',exact(connection,4))[0])


def listener():
    sock=socket.socket(); sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    sock.bind(('127.0.0.1',0)); sock.listen(8); sock.settimeout(8)
    return sock


def free_port():
    with listener() as sock: return sock.getsockname()[1]


def send_channel(port,data):
    until=time.monotonic()+4
    while True:
        try: connection=socket.create_connection(('127.0.0.1',port),timeout=3); break
        except OSError:
            if time.monotonic()>until: raise
            time.sleep(.02)
    with connection:
        frame(connection,data); assert receive_frame(connection)==b'OK'


def trace_records(path):
    return [dict(zip(['event','pid','task','micros','detail'],line.split('\t',4)))
            for line in path.read_text(encoding='utf-8').splitlines()]


@pytest.mark.parametrize(('mode','values','expected'),[
    ('local',[7],'49\n'), ('four',[],'4 9 16 25\n'),
    ('aliases',[],'[2, 4, 6]\n'), ('object',[],'99 1 1\n'), ('nested',[],'10\n'),
])
def test_local_values_lifecycle_and_isolation(binary,mode,values,expected):
    result=execute(binary,mode,*values)
    assert result.returncode==0,result.stderr
    assert result.stdout==expected


@pytest.mark.parametrize('mode',['error','unjoined_error','invalid'])
def test_local_errors_are_real_and_finalization_observes_failures(binary,mode):
    result=execute(binary,mode)
    assert result.returncode==1 and '[ERRO RUNTIME]' in result.stderr
    assert ('invalido' in result.stderr if mode=='invalid' else 'Tarefa ' in result.stderr)


def test_par_copies_mutable_objects_instead_of_sharing_references(binary):
    result=execute(binary,'par')
    assert result.returncode==0,result.stderr
    assert sorted(result.stdout.splitlines())==['1','88','parent 1']


@pytest.mark.parametrize(('mode','values','expected'),[
    ('remote',[8],'64\n'), ('mixed',[],'x = 49\ny = 64\n'),
    ('remote_list',[],'[6, 12, 18]\n'), ('remote_matrix',[],'[[3, 3], [3, 3]]\n'),
    ('remote_void',[],'VOID\n'),
    ('remote_bool',[],'1\n'),
])
def test_remote_values_come_from_independent_compiled_worker(binary,tmp_path,mode,values,expected):
    parent_trace=tmp_path/'parent.tsv'
    with worker(binary,tmp_path) as (server,ready,worker_trace):
        result=execute(binary,mode,ready['port'],*values,extra={'MINIPAR_TRACE':str(parent_trace)})
        assert result.returncode==0,result.stderr
        assert result.stdout==expected
        assert server.finish()[0]==0
        worker_events=trace_records(worker_trace)
        starts=[r for r in worker_events if r['event']=='worker_start']
        assert starts and all(int(r['pid'])==ready['pid'] for r in starts)
        returned=[r for r in trace_records(parent_trace) if r['event']=='remote_result']
        assert returned and returned[0]['detail']==str(ready['pid'])
        assert returned[0]['pid']!=str(ready['pid'])
        observe('remote_process_proof',worker=ready,worker_events=worker_events,parent_events=trace_records(parent_trace))


def test_remote_payload_larger_than_4096_and_embedded_nul(binary,tmp_path):
    payload='áé-test\x00-'*3000
    with worker(binary,tmp_path) as (server,ready,_):
        result=execute(binary,'remote_string',ready['port'],payload)
        assert result.returncode==0,result.stderr
        assert result.stdout==payload+'\n'
        assert server.finish()[0]==0


def test_remote_task_failure_is_returned_by_worker(binary,tmp_path):
    with worker(binary,tmp_path) as (server,ready,_):
        result=execute(binary,'remote_error',ready['port'])
        assert result.returncode==1 and 'Trabalhador '+str(ready['pid']) in result.stderr
        assert server.finish()[0]==0


def test_original_web_executes_local_and_remote_tasks_with_same_program_id(binary,tmp_path,monkeypatch):
    from app import app
    monkeypatch.chdir(ROOT)
    with worker(binary,tmp_path) as (server,ready,_):
        code=(ROOT/'tests/fixtures/runtime.minipar').read_text(encoding='utf-8')
        response=app.test_client().post('/api/compile',json={
            'code':code,'filename':'pytest_web_runtime.minipar','inputs':['mixed',str(ready['port'])]})
        result=response.get_json()
        assert response.status_code==200 and result['success'],result
        assert 'x = 49\ny = 64\n' in result['stdout']
        assert ready['program'] in result['cpp']
        assert server.finish()[0]==0
        observe('original_web_runtime',program=ready['program'],stdout=result['stdout'],worker_pid=ready['pid'])


def test_connection_refused_is_not_simulated_success(binary):
    result=execute(binary,'remote',free_port(),8)
    assert result.returncode==1 and 'Conexao TCP falhou' in result.stderr


@pytest.mark.parametrize('port',[-1,0,65536,1.5])
def test_remote_runtime_validates_dynamic_port(binary,port):
    result=execute(binary,'remote',port,8)
    assert result.returncode==1 and 'Porta deve ser inteiro' in result.stderr


def test_peer_that_never_replies_is_bounded_by_io_timeout(binary):
    sock=listener(); release=threading.Event(); connected=threading.Event(); failure=[]
    def peer():
        try:
            with sock.accept()[0] as connection:
                receive_frame(connection); connected.set(); release.wait(5)
        except Exception as error: failure.append(str(error))
    thread=threading.Thread(target=peer,daemon=True); thread.start()
    try:
        start=time.monotonic()
        result=execute(binary,'remote',sock.getsockname()[1],8,extra={'MINIPAR_TIMEOUT_MS':'250'})
        elapsed=time.monotonic()-start
        assert connected.is_set() and not failure
        assert result.returncode==1 and 'Timeout TCP' in result.stderr
        assert elapsed<4
        observe('bounded_timeout',elapsed_seconds=elapsed,stderr=result.stderr)
    finally: release.set(); thread.join(timeout=3); sock.close()


def test_worker_cannot_steal_an_active_listener_port(binary,tmp_path):
    with worker(binary,tmp_path,requests=0) as (_,ready,_):
        attempt=subprocess.run([str(binary),'--worker','--port',str(ready['port']),'--max-requests','1'],
                               env=environment(),capture_output=True,text=True,timeout=4)
        assert attempt.returncode==1 and 'bind TCP falhou' in attempt.stderr
        observe('port_conflict',stderr=attempt.stderr,port=ready['port'])


def test_channel_repeated_frames_and_large_message(binary):
    port=free_port(); payload=('large-channel-'*600).encode()
    process=Running([binary],['channel',port])
    try:
        process.line('LISTENING')
        for data in [b'first',payload,b'last']: send_channel(port,data)
        code,stdout,stderr=process.finish()
        assert code==0,stderr
        assert stdout=='LISTENING\nfirst\n'+payload.decode()+'\nlast\n'
    finally: process.stop()


@pytest.mark.parametrize('count',[2,4])
def test_barrier_proves_overlapping_local_intervals_and_nonblocking_fork(binary,tmp_path,count):
    sockets=[listener() for _ in range(count)]
    gates=[free_port() for _ in range(count)]
    ports=[value for i,sock in enumerate(sockets) for value in [sock.getsockname()[1],gates[i]]]
    path=tmp_path/'overlap.tsv'
    process=Running([binary],['parallel',count,0,*ports],extra={'MINIPAR_TRACE':str(path)})
    try:
        # Nenhuma tarefa pode terminar antes que o teste libere todos os gates.
        process.line('FORKED')
        for sock in sockets:
            with sock.accept()[0] as connection:
                assert float(receive_frame(connection))>0
                frame(connection,b'OK')
        for port in gates: send_channel(port,b'release')
        code,stdout,stderr=process.finish()
        assert code==0,stderr
        records=trace_records(path)
        starts=[int(r['micros']) for r in records if r['event']=='task_start']
        ends=[int(r['micros']) for r in records if r['event']=='task_end']
        assert len(starts)==len(ends)==count and max(starts)<min(ends)
        observe('overlap',count=count,stdout=stdout,intervals=records,barrier=True)
    finally:
        process.stop()
        for sock in sockets: sock.close()


def test_join_fast_task_does_not_wait_for_slow_task(binary,tmp_path):
    sockets=[listener(),listener()]; gates=[free_port(),free_port()]
    values=['different_times',2,0,sockets[0].getsockname()[1],gates[0],sockets[1].getsockname()[1],gates[1]]
    path=tmp_path/'different.tsv'; process=Running([binary],values,extra={'MINIPAR_TRACE':str(path)})
    try:
        process.line('FORKED')
        for sock in sockets:
            with sock.accept()[0] as connection: receive_frame(connection); frame(connection,b'OK')
        send_channel(gates[1],b'fast')
        process.line('FAST 16')
        # Slow permanece bloqueada no gate neste instante, sem depender de speedup.
        assert process.process.poll() is None
        send_channel(gates[0],b'slow')
        assert process.finish()[0]==0
        observe('different_completion_order',events=trace_records(path),stdout=process.lines)
    finally:
        process.stop()
        for sock in sockets: sock.close()


def test_scope_finalization_waits_for_pending_task_without_join(binary,tmp_path):
    ready=listener(); gate=free_port(); trace=tmp_path/'unjoined.tsv'
    process=Running([binary],['unjoined',1,0,ready.getsockname()[1],gate,free_port(),free_port()],extra={'MINIPAR_TRACE':str(trace)})
    try:
        process.line('MAIN_DONE')
        with ready.accept()[0] as connection: receive_frame(connection); frame(connection,b'OK')
        assert process.process.poll() is None
        send_channel(gate,b'finish')
        assert process.finish()[0]==0
        events=trace_records(trace)
        assert any(r['event']=='task_end' for r in events)
        observe('safe_finalization',events=events,explicit_join=False)
    finally: process.stop(); ready.close()


def test_worker_dies_after_starting_function(binary,tmp_path):
    ready_socket=listener(); gate1=free_port(); gate2=free_port()
    try:
        with worker(binary,tmp_path) as (server,ready,_):
            client=Running([binary],['remote_gate',1,ready['port'],ready_socket.getsockname()[1],gate1,free_port(),gate2])
            try:
                client.line('FORKED')
                with ready_socket.accept()[0] as connection: receive_frame(connection); frame(connection,b'OK')
                server.stop()
                code,stdout,stderr=client.finish()
                assert code==1 and 'encerrou antes da mensagem completa' in stderr
                observe('worker_died',worker_pid=ready['pid'],stdout=stdout,stderr=stderr)
            finally: client.stop()
    finally: ready_socket.close()


def put_string(value):
    value=value.encode() if isinstance(value,str) else value
    return struct.pack('!I',len(value))+value


def get_strings(data):
    result=[]
    while data:
        size=struct.unpack('!I',data[:4])[0]; result.append(data[4:4+size]); data=data[4+size:]
    return result


@pytest.mark.parametrize('fault',['program','function','type','argument','partial','oversize'])
def test_worker_rejects_unauthorized_and_malformed_requests(binary,tmp_path,fault):
    with worker(binary,tmp_path) as (server,ready,_):
        with socket.create_connection(('127.0.0.1',ready['port']),timeout=5) as connection:
            if fault=='oversize':
                connection.sendall(struct.pack('!I',200*1024*1024))
            elif fault=='partial':
                connection.sendall(b'\x00\x00'); connection.shutdown(socket.SHUT_WR)
            else:
                program='wrong-program' if fault=='program' else ready['program']
                name='system' if fault=='function' else 'square'
                kind='string' if fault=='type' else 'number'
                args=struct.pack('!I',1)+(put_string('string')+put_string('bad') if fault=='argument' else put_string('number')+struct.pack('!d',8))
                request=b''.join(put_string(v) for v in ['MiniParRPC/1',program,'test-id',name,kind,args])
                # Envio fragmentado exercita recepção parcial, sem socket.send presumido completo.
                data=struct.pack('!I',len(request))+request
                for offset in range(0,len(data),3): connection.sendall(data[offset:offset+3])
            response=get_strings(receive_frame(connection))
            assert response[3]==b'error',response
        assert server.finish()[0]==0
        observe('protocol_rejected',fault=fault,error=response[-1].decode(errors='replace'))
