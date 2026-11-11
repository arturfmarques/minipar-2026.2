"""A Web educacional consome o compilador e executáveis reais."""
import json
from pathlib import Path
import re

import pytest

from app import app
import educational_web as web
from ast_nodes import ForkExpr, JoinExpr, walk
from lexer import Lexer
from parser import Parser
from semantic import SemanticAnalyzer
from tac import TACGenerator
from codegen import CppCodeGenerator
from tools import validate_programs as pipeline

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(web, 'WORKSPACE', tmp_path / 'jobs')
    monkeypatch.chdir(ROOT)
    return app.test_client()


def analyze(client, code, stage):
    response = client.post('/api/educacional/analyze', json={'code': code, 'stage': stage})
    assert response.status_code == 200
    return response.get_json()


def compile_code(client, code):
    response = client.post('/api/educacional/compile', json={'code': code})
    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload['success'], payload
    return payload


def test_independent_page_links_original_editor_and_preserves_old_routes(client):
    page = client.get('/educacional')
    assert page.status_code == 200
    assert b'educacional.js' in page.data and b'editor-minipar' not in page.data
    assert b'source-editor' in page.data and b'Tokens' in page.data and b'AST' in page.data
    old = client.get('/')
    assert old.status_code == 200 and b'editor-minipar' in old.data and b'/educacional' in old.data
    assert client.get('/api/tests').status_code == 200
    assert client.post('/api/get_test',json={'filename':'../README.md'}).status_code == 400
    assert client.post('/api/compile',json={'filename':'../escape.minipar','code':'print(1);'}).status_code == 400
    assert client.post('/api/session/create',json={'filename':'../escape.minipar'}).status_code == 400


def test_catalog_loads_existing_sources_and_short_real_files(client):
    items = client.get('/api/educacional/examples').get_json()['examples']
    required = [item for item in items if item['group'] == 'Programas 1–11']
    assert sorted(item['order'] for item in required) == list(range(1, 12))
    names = {item['key'] for item in items}
    assert {'aritmetica.minipar','variaveis.minipar','condicionais.minipar',
            'lacos.minipar','funcoes.minipar','classes.minipar','seq_par.minipar',
            'fork_join_local.minipar'} <= names
    for item in items:
        response = client.get('/api/educacional/examples/' + item['key'])
        assert response.status_code == 200
        if item['group'] == 'Programas 1–11': source = ROOT / 'tests' / item['key']
        elif item['key'].startswith('fork_join_'): source = ROOT / 'examples' / item['key']
        else: source = ROOT / 'examples/didaticos' / item['key']
        assert response.get_json()['code'] == source.read_text(encoding='utf-8')
    assert client.get('/api/educacional/examples/..%2Fapp.py').status_code == 404


def test_live_tokens_change_with_source_and_report_positions(client):
    first = analyze(client, 'var x = 10 + 20;', 'tokens')
    expected = Lexer('var x = 10 + 20;').tokenize()
    assert first['success'] and [(t['type'],t['lexeme'],t['line'],t['column'])
        for t in first['tokens']] == [(t.type.name,t.lexeme,t.line,t.col) for t in expected]
    second = analyze(client, 'var y = 4;', 'tokens')
    assert [t['lexeme'] for t in first['tokens']] != [t['lexeme'] for t in second['tokens']]
    assert second['phases']['ast'] == 'não executada'
    invalid = analyze(client, 'var x = @;', 'tokens')
    assert not invalid['success'] and invalid['diagnostics'][0]['phase'] == 'LEXICO'
    assert invalid['diagnostics'][0]['line'] == 1 and invalid['diagnostics'][0]['column'] > 1


def test_ast_serializes_real_nodes_edges_and_all_nodes_of_test11(client):
    code = '''func square(number n) -> number { return n*n; }
        var task_id = fork local square(7); print(join(task_id));'''
    data = analyze(client, code, 'ast')
    assert data['success']
    parsed = Parser(Lexer(code).tokenize()).parse()
    assert data['node_count'] == len(list(walk(parsed)))
    found = []
    def visit(node):
        found.append((node['type'],node['edge'],node['line']))
        for child in node['children']: visit(child)
    visit(data['ast'])
    assert len(found) == data['node_count']
    assert ('ForkExpr','init_value',2) in found
    assert any(t == 'JoinExpr' for t,_,_ in found)
    source = (ROOT/'tests/teste11_minicompilador_armv7.minipar').read_text(encoding='utf-8')
    large = analyze(client, source, 'ast')
    assert large['success'] and large['node_count'] > 1000
    assert large['ast']['type'] == 'Program'


def test_real_semantics_scopes_signatures_and_diagnostics(client):
    code = '''class Box { number value = 1; func get() -> number { return this.value; } }
        func add(number a) -> number { var total=a+1; return total; }
        seq { var box = new Box(); number answer=add(box.get()); print(answer); }'''
    result = analyze(client, code, 'semantic')
    assert result['success'] and result['phases']['semantic'] == 'aprovada'
    rows = result['symbols']
    assert any(r['name']=='Box' and r['category']=='classe' and 'value' in r['details']['attributes'] for r in rows)
    assert any(r['name']=='add' and r['category']=='função' and r['details']['return']=='number' for r in rows)
    assert any(r['name']=='a' and r['category']=='parâmetro' and r['type']=='number' for r in rows)
    assert any(r['name']=='total' and r['scope'].startswith('SeqBlock') for r in rows)
    for bad in ['print(missing);', 'number x=1; number x=2;', 'number x="wrong";',
                'print(join(missing));', 'var value=4; func f() -> number { return value; } var t=fork local f();']:
        failure = analyze(client, bad, 'semantic')
        assert not failure['success'] and failure['diagnostics']
        assert failure['phases']['semantic'] == 'reprovada'
        assert all(d['phase']=='SEMANTICO' and d['line']>=1 and d['column']>=1 for d in failure['diagnostics'])
    parsed = analyze(client, 'var x=;', 'ast')
    assert not parsed['success'] and parsed['diagnostics'][0]['phase']=='SINTATICO'


def test_tac_and_cpp_are_exact_outputs_of_existing_generators(client):
    code = (ROOT/'examples/fork_join_local.minipar').read_text(encoding='utf-8')
    parsed = Parser(Lexer(code).tokenize()).parse()
    semantic = SemanticAnalyzer()
    assert semantic.analyze(parsed)
    tac = analyze(client, code, 'tac')
    assert tac['success'] and tac['tac'] == TACGenerator().generate_text(parsed)
    assert '= fork local' in tac['tac'] and '= join ' in tac['tac']
    cpp = analyze(client, code, 'cpp')
    assert cpp['success'] and cpp['cpp'] == CppCodeGenerator(semantic).render(parsed)
    assert 'std::async' in cpp['cpp'] or 'fork' in cpp['cpp']
    invalid = analyze(client, 'print(nope);', 'cpp')
    assert not invalid['success'] and 'cpp' not in invalid and 'tac' not in invalid


def test_bad_payload_and_old_download_paths_are_rejected(client):
    assert client.post('/api/educacional/analyze', json={'stage':'tokens','code':123}).status_code == 400
    assert client.post('/api/educacional/analyze', json={'stage':'unknown','code':'print(1);'}).status_code == 400
    assert client.post('/api/educacional/compile', json={'code':'x' * (web.CODE_LIMIT+1)}).status_code == 400
    assert client.post('/api/educacional/compile', json={'code':'var x=;'}).status_code == 422
    assert not web.WORKSPACE.exists() or not any(web.WORKSPACE.iterdir())
    assert client.get('/api/educacional/jobs/'+'0'*32+'/files/program.cpp').status_code == 404


@pytest.mark.native
def test_native_compile_run_outputs_downloads_and_isolation(client):
    code='var text=input(); print("recebido", text);'
    first = compile_code(client, code)
    second = compile_code(client, code)
    assert first['job_id'] != second['job_id']
    for payload in (first, second):
        job = web.WORKSPACE / payload['job_id']
        assert payload['compilation']['returncode']==0 and not payload['compilation']['timed_out']
        assert (job/'program.cpp').read_text(encoding='utf-8') == analyze(client, code, 'cpp')['cpp']
        for key in ('tac','cpp','executable'):
            response = client.get(payload['downloads'][key])
            assert response.status_code == 200 and response.data == (job / Path(payload['downloads'][key]).name).read_bytes()
            assert 'attachment;' in response.headers['Content-Disposition']
    path = f"/api/educacional/jobs/{first['job_id']}/run"
    ran = client.post(path, json={'stdin':'olá mundo\n'}).get_json()
    assert ran['success'] and ran['execution']['returncode']==0
    assert ran['execution']['stdout'].strip()=='recebido olá mundo'
    assert ran['execution']['stderr']==''
    assert client.get('/api/educacional/jobs/'+first['job_id']+'/files/../app.py').status_code==404
    assert client.get('/api/educacional/jobs/'+first['job_id']+'/files/job.json').status_code==404
    assert client.post(path,json={'stdin':'a'*(web.INPUT_LIMIT+1)}).status_code==400


@pytest.mark.native
def test_real_execution_error_and_timeout_are_reported(client, monkeypatch):
    invalid = compile_code(client, 'print(to_number(input()));')
    failed = client.post(f"/api/educacional/jobs/{invalid['job_id']}/run", json={'stdin':'not-a-number\n'}).get_json()
    assert not failed['success'] and failed['execution']['returncode']==1
    assert '[ERRO RUNTIME]' in failed['execution']['stderr'] and not failed['artifacts']
    loop = compile_code(client, 'while (true) { var x = 1 + 2; }')
    monkeypatch.setattr(web, 'EXEC_TIMEOUT', .25)
    timed = client.post(f"/api/educacional/jobs/{loop['job_id']}/run", json={'stdin':''}).get_json()
    assert not timed['success'] and timed['execution']['timed_out']


@pytest.mark.native
def test_stdout_is_bounded_while_process_runs_to_completion(client):
    built = compile_code(client, 'for (var i in range(30000)) { print(i); }')
    ran = client.post(f"/api/educacional/jobs/{built['job_id']}/run", json={'stdin':''}).get_json()
    assert ran['success'] and ran['execution']['returncode']==0
    assert ran['execution']['stdout_truncated'] and len(ran['execution']['stdout'].encode()) <= web.LOG_LIMIT + 4


@pytest.mark.native
def test_test11_two_compiler_levels_and_arm_download_per_run(client):
    source=(ROOT/'tests/teste11_minicompilador_armv7.minipar').read_text(encoding='utf-8')
    data=analyze(client, source, 'semantic')
    assert data['success'] and any(s['name']=='MiniCompiler' for s in data['symbols'])
    job=compile_code(client, source)
    url=f"/api/educacional/jobs/{job['job_id']}/run"
    first=client.post(url,json={'stdin':'((2+4)*7)-(5*4)\n'}).get_json()
    second=client.post(url,json={'stdin':'((10-8*7)+4)*2\n'}).get_json()
    assert first['success'] and second['success']
    for output,number in ((first,22),(second,-84)):
        stdout=output['execution']['stdout']
        assert f'RESULTADO {number}' in stdout and 'TOKENS_BEGIN' in stdout and 'AST_BEGIN' in stdout
        assert 'TAC_BEGIN' in stdout and 'ARM_BEGIN' in stdout and 'STATUS APROVADO' in stdout
        assert len(output['artifacts'])==1 and output['artifacts'][0]['name'].endswith('.arm')
        arm=client.get(output['artifacts'][0]['url'])
        assert arm.status_code==200 and b'.arch armv7-a' in arm.data
    assert first['artifacts'][0]['url'] != second['artifacts'][0]['url']
    assert client.get('/api/educacional/jobs/'+job['job_id']+'/files/runs/'+'0'*32+'/output/teste11-expressao.arm').status_code==404


def test_terminal_entrypoint_and_original_routes_still_exist(client):
    import main
    assert callable(main.compile_file) and callable(main.start_interactive)
    assert client.get('/').status_code==200
    assert client.post('/api/get_test',json={'filename':'teste11_minicompilador_armv7.minipar'}).status_code==200


@pytest.mark.native
@pytest.mark.parametrize(('file','expected'), [
    ('aritmetica','14'), ('variaveis','14'), ('condicionais','aprovado'),
    ('lacos','7'), ('funcoes','120'), ('classes','1'), ('seq_par','inicio'),
])
def test_short_examples_are_real_compilable_minipar(tmp_path, file, expected):
    path=ROOT/'examples/didaticos'/f'{file}.minipar'
    record=pipeline.build(path,tmp_path)
    assert record['phases']['native_compilation']==pipeline.PASS,record
    result=pipeline.run(record)
    assert result.returncode==0 and expected in result.stdout
    if file=='seq_par': assert 'fim' in result.stdout and 'tarefa A' in result.stdout and 'tarefa B' in result.stdout
