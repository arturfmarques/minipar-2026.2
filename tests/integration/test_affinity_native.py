"""Afinidade nativa observada, restricao de processo e falhas reais da API."""
import ast as literal_ast
import ctypes
import json
import os
from pathlib import Path
import subprocess
import pytest
from codegen import CppCodeGenerator
from cpp_template import _CPP_HEADER
from semantic import SemanticAnalyzer
from toolchain import compile_cpp, executable_suffix, runtime_environment
from test_runtime import Running, worker, trace_records, free_port

ROOT = Path(__file__).resolve().parents[2]
OBSERVATIONS = []
pytestmark = pytest.mark.native
SOURCE = '''
func square(number n) -> number { return n * n; }
func argument() -> number { print("ARGUMENT"); return 7; }
func selector() -> number { print("SELECTOR"); return available_cpus()[0]; }
func zero() -> number { return current_cpu(); }
func sample(number expected, number value) -> list {
    require(current_cpu() == expected, "CPU_INCORRETA");
    var total = 0;
    for (var i in range(20000)) { total = total + i; }
    require(current_cpu() == expected, "MIGRACAO_INDEVIDA");
    return [current_cpu(), value * value];
}
func fail() -> number { require(false, "AFFINITY_BODY_ERROR"); return 0; }
func rendezvous(number cpu, c_channel ready, c_channel gate) -> number {
    require(current_cpu() == cpu, "CPU_ANTES_BARREIRA");
    send(ready, cpu);
    var release = receive(gate);
    require(current_cpu() == cpu, "CPU_APOS_BARREIRA");
    return current_cpu();
}
seq {
    var mode = input();
    if (mode == "allowed") { print(available_cpus()); }
    if (mode == "plain") { var t = fork local square(7); print(join(t)); }
    if (mode == "pin" || mode == "restrict") {
        if (mode == "restrict") { print("READY"); }
        var cpu = to_number(input());
        if (mode == "restrict") { print("ALLOWED", available_cpus()); }
        var t = fork local sample(cpu, 7) on core(cpu);
        cpu = 999999;
        var result = join(t);
        result[1] = 0;
        print(join(t));
    }
    if (mode == "zero") {
        var cpu = available_cpus()[0];
        var t = fork local zero() on core(cpu);
        print(join(t));
    }
    if (mode == "error") {
        var cpu = available_cpus()[0];
        var t = fork local fail() on core(cpu);
        print(join(t));
    }
    if (mode == "order") { var t = fork local square(argument()) on core(selector()); print(join(t)); }
    if (mode == "two") {
        var cpus = available_cpus();
        var ready = c_channel("127.0.0.1", to_number(input()));
        var gate0 = c_channel("127.0.0.1", to_number(input()));
        var gate1 = c_channel("127.0.0.1", to_number(input()));
        var t0 = fork local rendezvous(cpus[0], ready, gate0) on core(cpus[0]);
        var t1 = fork local rendezvous(cpus[1], ready, gate1) on core(cpus[1]);
        var ready0 = receive(ready); var ready1 = receive(ready);
        send(gate0, "go"); send(gate1, "go");
        print(join(t0), join(t1));
    }
    if (mode == "remote") {
        var port = to_number(input());
        var cpu = available_cpus()[0];
        var local_task = fork local sample(cpu, 7) on core(cpu);
        var remote_task = fork remote("127.0.0.1", port) square(8);
        print(join(local_task), join(remote_task));
    }
}
'''


def observe(name, **data):
    OBSERVATIONS.append({'test':name, **data})
    (ROOT/'output/validacoes').mkdir(parents=True,exist_ok=True)
    (ROOT/'output/validacoes/afinidade-tests.json').write_text(json.dumps(OBSERVATIONS,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


@pytest.fixture(scope='module')
def affinity_binary(tmp_path_factory):
    from lexer import Lexer
    from parser import Parser
    directory = tmp_path_factory.mktemp('affinity')
    program = Parser(Lexer(SOURCE).tokenize()).parse()
    analyzer = SemanticAnalyzer()
    assert analyzer.analyze(program), analyzer.diagnostics
    cpp = directory/'program.cpp'
    cpp.write_text(CppCodeGenerator(analyzer).render(program),encoding='utf-8')
    binary = directory/('program'+executable_suffix())
    built = compile_cpp(cpp,binary)
    assert built.returncode == 0, built.stderr
    return binary


def execute(binary, mode, *values, trace=None):
    env = runtime_environment()
    if trace is not None: env['MINIPAR_TRACE'] = str(trace)
    result = subprocess.run([str(binary)],input='\n'.join(map(str,[mode,*values]))+'\n',
                            capture_output=True,text=True,env=env,timeout=20)
    observe(mode,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
            trace=trace_records(trace) if trace is not None and trace.exists() else [])
    return result


@pytest.fixture(scope='module')
def allowed(affinity_binary):
    result = execute(affinity_binary,'allowed')
    assert result.returncode == 0, result.stderr
    cpus = list(map(int,literal_ast.literal_eval(result.stdout)))
    assert cpus and len(set(cpus)) == len(cpus)
    return cpus


def test_plain_fork_does_not_request_affinity(affinity_binary,tmp_path):
    trace = tmp_path/'plain.tsv'
    result = execute(affinity_binary,'plain',trace=trace)
    assert result.returncode == 0 and result.stdout == '49\n'
    assert not any(r['event']=='affinity_applied' for r in trace_records(trace))


def test_affinity_before_body_join_and_result_copies(affinity_binary,allowed,tmp_path):
    trace = tmp_path/'pin.tsv'
    result = execute(affinity_binary,'pin',allowed[-1],trace=trace)
    assert result.returncode == 0, result.stderr
    assert literal_ast.literal_eval(result.stdout) == [allowed[-1],49]
    rows = trace_records(trace)
    pin = next(r for r in rows if r['event']=='affinity_applied')
    start = next(r for r in rows if r['event']=='task_start')
    assert pin['detail'] == f'requested={allowed[-1]} actual={allowed[-1]}'
    assert int(pin['micros']) <= int(start['micros'])


def test_zero_arguments_and_evaluation_order(affinity_binary,allowed):
    result = execute(affinity_binary,'zero')
    assert result.returncode == 0 and float(result.stdout) == allowed[0]
    order = execute(affinity_binary,'order')
    assert order.returncode == 0 and order.stdout == 'ARGUMENT\nSELECTOR\n49\n'


@pytest.mark.parametrize('cpu', ['-1','0.5','999999','nan'])
def test_dynamic_invalid_cpu_is_never_remapped(affinity_binary,cpu,tmp_path):
    trace = tmp_path/'invalid.tsv'
    result = execute(affinity_binary,'pin',cpu,trace=trace)
    assert result.returncode == 1 and ('processador logico' in result.stderr or 'nao permitido' in result.stderr)
    assert not result.stdout and not trace.exists()


def test_two_processors_and_concurrent_tasks(affinity_binary,allowed,tmp_path):
    if len(allowed)<2:
        observe('two_unavailable',status='NAO EXECUTADO',reason='Somente um processador permitido')
        pytest.skip('Somente um processador permitido ao processo')
    ports = set()
    while len(ports)<3: ports.add(free_port())
    trace = tmp_path/'two.tsv'
    result = execute(affinity_binary,'two',*ports,trace=trace)
    assert result.returncode == 0, result.stderr
    assert list(map(int,result.stdout.split())) == allowed[:2]
    rows = trace_records(trace)
    starts = [int(r['micros']) for r in rows if r['event']=='task_start']
    ends = [int(r['micros']) for r in rows if r['event']=='task_end']
    assert len(starts)==len(ends)==2 and max(starts)<min(ends)


def test_cpu_excluded_by_process_mask_is_rejected(affinity_binary,allowed):
    if len(allowed)<2:
        pytest.skip('Restricao exige pelo menos dois processadores inicialmente permitidos')
    running = Running([affinity_binary])
    try:
        running.process.stdin.write('restrict\n'); running.process.stdin.flush()
        running.line('READY')
        if os.name == 'nt':
            from ctypes import wintypes
            api = ctypes.WinDLL('kernel32',use_last_error=True).SetProcessAffinityMask
            api.argtypes = [wintypes.HANDLE,ctypes.c_size_t]; api.restype = wintypes.BOOL
            assert api(int(running.process._handle),1 << (allowed[-1] % 64)), ctypes.get_last_error()
        else:
            os.sched_setaffinity(running.process.pid,{allowed[-1]})
        running.process.stdin.write(str(allowed[0])+'\n'); running.process.stdin.close()
        code,stdout,stderr = running.finish()
        observe('process_restriction',returncode=code,stdout=stdout,stderr=stderr)
        assert code == 1 and 'nao permitido ao processo' in stderr
        assert 'ALLOWED ['+str(allowed[-1])+']' in stdout
    finally:
        running.stop()


def test_pinned_body_exception_reaches_join(affinity_binary,tmp_path):
    trace = tmp_path/'error.tsv'
    result = execute(affinity_binary,'error',trace=trace)
    assert result.returncode == 1 and 'AFFINITY_BODY_ERROR' in result.stderr
    rows = trace_records(trace)
    assert any(r['event']=='affinity_applied' for r in rows)
    assert any(r['event']=='task_error' for r in rows)


def test_real_native_affinity_configuration_failure_is_propagated(tmp_path):
    # Grupo inexistente (Windows)/mascara vazia (Linux): falha real da API,
    # injetada no limite interno para
    # exercitar o erro apos a validacao normal, antes de chamar o corpo.
    cpp = tmp_path/'failure.cpp'
    cpp.write_text(_CPP_HEADER+'''
int main() {
    mp::TaskScope scope;
    mp::CpuAffinity invalid;
#ifdef _WIN32
    invalid.native.Group=USHRT_MAX;
    invalid.native.Mask=1;
#endif
    auto task=mp::launch_task("invalid-native",[] { std::cout << "BODY"; return 1; },invalid);
    try { task.join(); return 2; }
    catch(const mp::Error& error) { std::cout << error.what() << std::endl; return 0; }
}
''',encoding='utf-8')
    binary = tmp_path/('failure'+executable_suffix())
    compiled = compile_cpp(cpp,binary)
    assert compiled.returncode == 0, compiled.stderr
    result = subprocess.run([str(binary)],capture_output=True,text=True,env=runtime_environment(),timeout=10)
    observe('native_api_failure',returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
    operation = 'SetThreadGroupAffinity' if os.name=='nt' else 'pthread_setaffinity_np'
    assert result.returncode == 0 and operation+' falhou (' in result.stdout
    assert 'BODY' not in result.stdout


def test_remote_worker_and_pinned_local_task_are_independent(affinity_binary,allowed,tmp_path):
    with worker(affinity_binary,tmp_path) as (running,ready,trace):
        result = execute(affinity_binary,'remote',ready['port'])
        assert result.returncode == 0 and result.stdout == f'[{allowed[0]}, 49] 64\n', result.stderr
        assert running.finish()[0] == 0
        rows = trace_records(trace)
        assert any(r['event']=='worker_start' and int(r['pid'])==ready['pid'] for r in rows)
        assert not any(r['event']=='affinity_applied' for r in rows)
        observe('remote_distinct_process',worker_pid=ready['pid'],worker_trace=rows,stdout=result.stdout)


@pytest.fixture(scope='module')
def network_binary(tmp_path_factory):
    from tools import validate_programs as pipeline
    built = pipeline.build(ROOT/'examples/fork_join_network.minipar',tmp_path_factory.mktemp('network-demo'))
    assert built['phases']['native_compilation'] == pipeline.PASS, built
    return Path(built['executable'])


def test_network_example_two_real_worker_requests(network_binary,tmp_path):
    with worker(network_binary,tmp_path,requests=2) as (running,ready,worker_trace):
        env = runtime_environment()
        parent_trace = tmp_path/'parent.tsv'
        env.update(MINIPAR_WORKER_PORT=str(ready['port']),MINIPAR_TRACE=str(parent_trace))
        client = subprocess.Popen([str(network_binary)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        try:
            stdout,stderr = client.communicate(timeout=15)
        finally:
            if client.poll() is None: client.kill(); client.wait()
        code,worker_stdout,worker_stderr = running.finish()
        assert client.returncode == code == 0, (stderr,worker_stderr)
        assert stdout == 'CLIENTE recebeu 49 64\n'
        assert worker_stdout.count('TRABALHADOR executou quadrado de') == 2
        results = [r for r in trace_records(parent_trace) if r['event']=='remote_result']
        assert len(results)==2 and all(r['detail']==str(ready['pid']) for r in results)
        assert client.pid != ready['pid']
        observe('network_example',client_pid=client.pid,worker_pid=ready['pid'],stdout=stdout,
                worker_stdout=worker_stdout,parent_trace=trace_records(parent_trace),worker_trace=trace_records(worker_trace))


def test_network_example_without_worker_has_no_local_fallback(network_binary):
    env = runtime_environment()
    env.update(MINIPAR_WORKER_PORT=str(free_port()),MINIPAR_CONNECT_TIMEOUT_MS='300')
    result = subprocess.run([str(network_binary)],capture_output=True,text=True,env=env,timeout=10)
    observe('network_unavailable',returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
    assert result.returncode == 1 and result.stderr and not result.stdout


def test_affinity_example_uses_two_allowed_processors(allowed,tmp_path):
    if len(allowed)<2: pytest.skip('Exemplo exige dois processadores permitidos')
    from tools import validate_programs as pipeline
    built = pipeline.build(ROOT/'examples/fork_join_affinity.minipar',tmp_path)
    assert built['phases']['native_compilation'] == pipeline.PASS, built
    result = pipeline.run(built)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert literal_ast.literal_eval(lines[1].split(' ',1)[1]) == [49,allowed[0]]
    assert literal_ast.literal_eval(lines[2].split(' ',1)[1]) == [64,allowed[1]]
    observe('affinity_example',returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)


@pytest.mark.parametrize('interface',['original','educational'])
def test_affinity_uses_shared_compiler_in_both_webs(interface,tmp_path,monkeypatch):
    from app import app
    import educational_web
    code = '''func check(number cpu) -> string {
        require(current_cpu() == cpu, "CPU_WEB_INCORRETA"); return "AFFINITY_WEB_OK";
    }
    var cpu = available_cpus()[0];
    var t = fork local check(cpu) on core(cpu); print(join(t));'''
    client = app.test_client()
    if interface == 'original':
        payload = client.post('/api/compile',json={'code':code,'filename':'pytest_affinity_web.minipar','inputs':[]}).get_json()
        assert payload['success'] and 'AFFINITY_WEB_OK\n' in payload['stdout'], payload
    else:
        monkeypatch.setattr(educational_web,'WORKSPACE',tmp_path/'jobs')
        built = client.post('/api/educacional/compile',json={'code':code}).get_json()
        assert built['success'], built
        result = client.post('/api/educacional/jobs/'+built['job_id']+'/run',json={}).get_json()
        assert result['success'] and result['execution']['stdout']=='AFFINITY_WEB_OK\n', result
    observe('web_'+interface,status='APROVADO')
