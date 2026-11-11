"""Executa MiniPar/C++ real; Python apenas controla e confere os resultados."""
import ast
import json
from pathlib import Path
import socket
import subprocess
import pytest
from tools import validate_programs as pipeline
from tools import validate_parallel as validation
from test_runtime import Running,worker,trace_records,free_port

ROOT=pipeline.ROOT
OBSERVATIONS=[]
pytestmark=pytest.mark.native


def observe(name,**data):
    OBSERVATIONS.append({'test':name,**data})
    pipeline.save(ROOT/'output/validacoes/testes-8910-casos.json',OBSERVATIONS)


def sync_base(count):
    for base in range(22000,32000,10):
        reserved=[]
        try:
            for port in range(base,base+count+1):
                sock=socket.socket(); reserved.append(sock); sock.bind(('127.0.0.1',port))
            return base
        except OSError: pass
        finally:
            for sock in reserved: sock.close()
    raise AssertionError('Nenhum intervalo de portas livre para barreira')


@pytest.fixture(scope='module')
def programs(tmp_path_factory):
    records={}
    for number,source in validation.SOURCES.items():
        record=pipeline.build(source,tmp_path_factory.mktemp(f'program{number}'))
        assert record['phases']['native_compilation']==pipeline.PASS,record
        records[number]=record
        observe('build',number=number,record=record)
    return records


def check_lifetimes(events,count,start='task_start',end='task_end'):
    starts={e['task']:int(e['micros']) for e in events if e['event']==start}
    ends={e['task']:int(e['micros']) for e in events if e['event']==end}
    assert len(starts)==len(ends)==count and starts.keys()==ends.keys()
    assert max(starts.values())<min(ends.values())


@pytest.mark.parametrize('number',[8,9,10])
def test_full_pipeline_results_real_times_and_overlapping_tasks(programs,tmp_path,number):
    record=programs[number]; trace=tmp_path/'trace.tsv'
    result=pipeline.run(record,env={'MINIPAR_WORK_FACTOR':'1','MINIPAR_REMOTE':'0',
        'MINIPAR_SYNC_BASE_PORT':str(sync_base(number-4)),
        'MINIPAR_OUTPUT_PREFIX':str(tmp_path/'carpet'),'MINIPAR_TRACE':str(trace)})
    assert result.returncode==0,result.stderr
    verified=validation.validate(number,result.stdout)
    events=trace_records(trace)
    check_lifetimes(events,number-4)
    for kind in ('spawn','join_begin','join_end'):
        assert sum(e['event']==kind for e in events)==number-4
    assert max(int(e['micros']) for e in events if e['event']=='spawn') <= min(int(e['micros']) for e in events if e['event']=='join_begin')
    if number==10:
        assert sum(e['event']=='task_start' and e['detail']=='trabalhador_sierpinski' for e in events)==1
    observe('full_pipeline',number=number,execution=record['execution'],verified=verified,events=events)


def test_four_evaluators_execute_in_an_independent_worker_process(programs,tmp_path):
    record=programs[8]; binary=Path(record['executable']); parent_trace=tmp_path/'parent.tsv'
    with worker(binary,tmp_path,requests=4) as (remote,ready,worker_trace):
        parent=Running([binary],extra={'MINIPAR_REMOTE':'1','MINIPAR_REMOTE_HOST':'127.0.0.1',
            'MINIPAR_PARENT_HOST':'127.0.0.1','MINIPAR_REMOTE_PORT':str(ready['port']),
            'MINIPAR_WORK_FACTOR':'1','MINIPAR_SYNC_BASE_PORT':str(sync_base(4)),
            'MINIPAR_TRACE':str(parent_trace)})
        try:
            code,stdout,stderr=parent.finish()
            assert code==0,stderr
            verified=validation.validate(8,stdout)
            assert parent.process.pid!=ready['pid']
            assert remote.finish()[0]==0
            events=trace_records(worker_trace); replies=trace_records(parent_trace)
            check_lifetimes(events,4,start='worker_start',end='worker_end')
            assert len([e for e in replies if e['event']=='remote_result' and e['detail']==str(ready['pid'])])==4
            observe('remote',parent_pid=parent.process.pid,worker=ready,events=events,parent_events=replies,verified=verified,stdout=stdout)
        finally: parent.stop()


@pytest.fixture(scope='module')
def drivers(tmp_path_factory):
    bodies={
        'mandelbrot': (9, 'var w=to_number(input()); var h=to_number(input()); var n=to_number(input()); print(mandelbrot_iteracoes(w,h,n)); print("ASCII_BEGIN"); print(mandelbrot(w,h,n)); print("ASCII_END");'),
        'sierpinski': (10, 'var size=to_number(input()); var depth=to_number(input()); var path=input(); var t=fork local gravar_sierpinski(size,depth,path); print(join(t));'),
        'validation': (8, '''var mode=input(); var tasks=criar_atividades(40,4);
            if(mode=="students") { var bad=criar_atividades(0,4); }
            if(mode=="factor") { var t=fork local avaliar_lote(tasks,0,0); print(join(t)); }
            if(mode=="slice") { var bad=fatiar(tasks,-1,10); }
            if(mode=="join") { var invalid; if(false) { invalid=fork local avaliar_lote(tasks,0,.01); } print(join(invalid)); }
            var results=avaliar_lote(tasks,0,.001);
            if(mode=="duplicate") { results[1]=results[0]; }
            if(mode=="missing") { var removed=results.pop(); }
            if(mode=="checksum") { results[0][5]=results[0][5]+1; }
            var validation_task=fork local validar_resultados(results,160,false); join(validation_task);'''.replace(',.01',',0.01').replace(',.001',',0.001')),
        'library': (8, '''func save(string path,string text) -> string { write_text(path,text); return path; }
            var path=input(); var content=input(); var before=monotonic();
            var t=fork local save(path,content); print(join(t));
            require(monotonic()>=before,"Relogio regrediu");
            print(floor(-1.2),to_string(true),get_env("MINIPAR_TEST_NATIVE","fallback"));'''),
    }
    results={}
    for name,(number,main) in bodies.items():
        record=pipeline.build(validation.SOURCES[number],tmp_path_factory.mktemp(name),main=main)
        observe('build_driver',driver=name,record=record)
        assert record['phases']['native_compilation']==pipeline.PASS,record
        results[name]=record
    return results


@pytest.mark.parametrize(('width','height','maximum'),[(50,20,100),(7,4,9),(5,3,1)])
def test_mandelbrot_exact_iteration_counts_and_ascii(drivers,width,height,maximum):
    result=pipeline.run(drivers['mandelbrot'],f'{width}\n{height}\n{maximum}\n')
    assert result.returncode==0,result.stderr
    counts=ast.literal_eval(result.stdout.splitlines()[0])
    expected,lines=validation.mandelbrot_oracle(width,height,maximum)
    assert counts==expected
    actual=result.stdout.split('ASCII_BEGIN\n')[1].split('\nASCII_END')[0].split('\n')
    assert actual==lines
    observe('mandelbrot_iterations',width=width,height=height,maximum=maximum,counts=counts)


@pytest.mark.parametrize('depth',[0,1,2,4])
def test_recursive_svg_changes_with_parameters_and_is_created_by_task(drivers,tmp_path,depth):
    path=tmp_path/f'carpet-{depth}.svg'
    result=pipeline.run(drivers['sierpinski'],f'81\n{depth}\n{path}\n')
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()==str(path)
    observe('svg_parameterized',**validation.svg_checks(path,depth,81))


@pytest.mark.parametrize('values',['0\n20\n100\n','50\n-1\n100\n','50\n20\n0\n','2.5\n20\n100\n'])
def test_mandelbrot_invalid_parameters_are_rejected(drivers,values):
    result=pipeline.run(drivers['mandelbrot'],values)
    assert result.returncode==1 and '[ERRO RUNTIME]' in result.stderr


@pytest.mark.parametrize(('side','depth'),[(0,4),(81,-1),(81,1.5),(81,7)])
def test_sierpinski_invalid_parameters_fail_inside_task(drivers,tmp_path,side,depth):
    path=tmp_path/'invalid.svg'
    result=pipeline.run(drivers['sierpinski'],f'{side}\n{depth}\n{path}\n')
    assert result.returncode==1 and 'Tarefa ' in result.stderr
    assert not path.exists()


def test_file_write_failure_propagates_through_join(drivers,tmp_path):
    path=tmp_path/'does-not-exist'/'carpet.svg'
    result=pipeline.run(drivers['sierpinski'],f'81\n4\n{path}\n')
    assert result.returncode==1 and 'Tarefa ' in result.stderr and 'Falha ao escrever arquivo' in result.stderr
    assert not path.exists() and 'STATUS APROVADO' not in result.stdout
    observe('file_failure',**drivers['sierpinski']['execution'])


@pytest.mark.parametrize('mode',['students','factor','slice','join','duplicate','missing','checksum'])
def test_invalid_activity_inputs_duplicate_missing_results_and_join_are_detected(drivers,mode):
    result=pipeline.run(drivers['validation'],mode+'\n')
    assert result.returncode==1 and '[ERRO RUNTIME]' in result.stderr
    observe('invalid_activity',mode=mode,**drivers['validation']['execution'])


def test_generic_library_writes_utf8_nul_and_uses_real_monotonic_clock(drivers,tmp_path):
    path=tmp_path/'dados-ação.txt'
    text='conteúdo UTF-8: ação\x00fim'
    result=pipeline.run(drivers['library'],f'{path}\n{text}\n',env={'MINIPAR_TEST_NATIVE':'provided'})
    assert result.returncode==0,result.stderr
    assert path.read_bytes()==text.encode('utf-8')
    assert '-2 true provided' in result.stdout


def test_unavailable_remote_worker_does_not_produce_success(programs,tmp_path):
    result=pipeline.run(programs[8],env={'MINIPAR_REMOTE':'1','MINIPAR_REMOTE_PORT':str(free_port()),
        'MINIPAR_SYNC_BASE_PORT':str(sync_base(4)),'MINIPAR_TIMEOUT_MS':'250',
        'MINIPAR_CONNECT_TIMEOUT_MS':'150','MINIPAR_WORK_FACTOR':'0.01'},timeout=5)
    assert result.returncode==1 and 'STATUS APROVADO' not in result.stdout
    observe('remote_unavailable',**programs[8]['execution'])


@pytest.mark.parametrize('main',[
    'var t=fork local no_such_task();', 'number value=join(missing);',
    'var a=criar_atividades(40,4); var t=fork local avaliar_lote(a,"wrong",1);',
])
def test_static_task_errors_stop_before_native_compilation(tmp_path,main):
    record=pipeline.build(validation.SOURCES[8],tmp_path,main=main)
    assert record['phases']['semantic']==pipeline.FAIL
    assert record['phases']['native_compilation']==pipeline.NOT_RUN


@pytest.mark.parametrize('number',[8,9,10])
def test_original_web_lists_loads_compiles_executes_and_exposes_svg(monkeypatch,tmp_path,number):
    import app as web
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv('MINIPAR_WORK_FACTOR','1')
    monkeypatch.setenv('MINIPAR_REMOTE','0')
    monkeypatch.setenv('MINIPAR_SYNC_BASE_PORT',str(sync_base(number-4)))
    monkeypatch.setenv('MINIPAR_OUTPUT_PREFIX',str(ROOT/'output'/f'pytest-web-{number}'))
    client=web.app.test_client(); filename=validation.SOURCES[number].name
    assert filename in client.get('/api/tests').get_json()['tests']
    source=client.post('/api/get_test',json={'filename':filename}).get_json()['code']
    assert source==validation.SOURCES[number].read_text(encoding='utf-8')
    spec=client.post('/api/test_spec',json={'filename':filename}).get_json()
    assert spec['multi_computer'] is None
    result=client.post('/api/compile',json={'filename':f'pytest_web_{number}.minipar','code':source}).get_json()
    assert result['success'],result.get('stderr')
    assert result['cpp'] and result['tac']
    validation.validate(number,result['stdout'])
    if number==10:
        assert len(result['artifacts'])==2
        for artifact in result['artifacts']:
            response=client.get(artifact['url'])
            assert response.status_code==200 and response.mimetype=='image/svg+xml'
            assert 'sandbox' in response.headers['Content-Security-Policy']
            assert b'<svg' in response.data
    else: assert result['artifacts']==[]
    observe('web',number=number,artifacts=result['artifacts'])


def test_svg_endpoint_rejects_paths_outside_output_and_other_extensions():
    from app import app
    client=app.test_client()
    assert client.get('/api/artifacts/../README.md').status_code==404
    assert client.get('/api/artifacts/../../referencias/x.svg').status_code==404


def test_terminal_selection_and_execution_use_existing_pipeline(monkeypatch,capsys):
    import menu
    import main
    selected=str(validation.SOURCES[8])
    assert all(source.name in {Path(p).name for p in menu.obter_testes()} for source in validation.SOURCES.values())
    monkeypatch.setenv('MINIPAR_REMOTE','0')
    monkeypatch.setenv('MINIPAR_SYNC_BASE_PORT',str(sync_base(4)))
    monkeypatch.setenv('MINIPAR_WORK_FACTOR','1')
    assert main.compile_file(selected,'pytest_terminal_8')
    stdout=menu.executar_binario('pytest_terminal_8')
    validation.validate(8,stdout)
