from pathlib import Path
import os
import subprocess
import sys
import pytest
from codegen import CppCodeGenerator
from diagnostics import BackendUnsupportedError
from app import app

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('example', ['fork_join_local', 'fork_join_remote'])
def test_cli_tac_only_requires_no_compiler_or_network(tmp_path, example):
    source = ROOT / 'examples' / (example + '.minipar')
    environment = {**os.environ, 'MINIPAR_CXX': '/nonexistent/g++'}
    ran = subprocess.run([sys.executable, str(ROOT/'main.py'), str(source), '--tac-only'],
                         cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    tac = (tmp_path/'output'/f'{example}.tac').read_text(encoding='utf-8')
    assert '= fork ' in tac and '= join ' in tac
    assert not list((tmp_path/'output').glob('*.cpp'))
    assert not list((tmp_path/'output').glob('*.exe'))


@pytest.mark.native
def test_cli_default_compiles_and_executes_local_runtime(tmp_path):
    ran = subprocess.run([sys.executable, str(ROOT/'main.py'), str(ROOT/'examples/fork_join_local.minipar')],
                         cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert ran.returncode == 0, ran.stderr
    assert (tmp_path/'output/fork_join_local.tac').exists()
    assert (tmp_path/'output/fork_join_local.cpp').exists()
    from toolchain import runtime_environment, executable_suffix
    executed=subprocess.run([str(tmp_path/('output/fork_join_local'+executable_suffix()))],
                            capture_output=True,text=True,env=runtime_environment(),timeout=10)
    assert (executed.returncode,executed.stdout)==(0,'49\n')


def test_backend_direct_call_cannot_silently_lower_task_to_zero(parse):
    program = parse('func f() { return 2; } var t = fork local f(); join(t);')
    cpp=CppCodeGenerator().render(program)
    assert 'mp::fork_local("f"' in cpp and 'mp::join(t)' in cpp
    assert 'std::launch::async' in cpp and 'std::launch::deferred' not in cpp


@pytest.mark.parametrize('source', [
    'return 1;', 'print(this);', 'send(1,2);',
    'func f(number x) {return x;} var t = fork local f("bad");',
])
def test_semantic_errors_prevent_all_artifacts_and_native_invocation(tmp_path, source):
    path = tmp_path/'bad.minipar'
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, str(ROOT/'main.py'), str(path)],
                         cwd=tmp_path, env={**os.environ,'MINIPAR_CXX':'/nonexistent/g++'},
                         capture_output=True, text=True, timeout=10)
    assert ran.returncode == 1 and 'ERRO SEMANTICO' in ran.stderr
    assert 'TOOLCHAIN' not in ran.stderr and not (tmp_path/'output').exists()


def test_first_web_uses_same_tac_pipeline(monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv('MINIPAR_CXX','/nonexistent/g++')
    client = app.test_client()
    code = (ROOT/'examples/fork_join_remote.minipar').read_text(encoding='utf-8')
    response = client.post('/api/compile', json={'filename':'pytest_task_ir.minipar','code':code,'tac_only':True})
    result = response.get_json()
    assert response.status_code == 200 and result['success']
    assert '= fork remote(' in result['tac'] and '= join remote_id' in result['tac']
    assert result['cpp'] == ''


def test_terminal_preserves_common_entry_point():
    import main
    import menu
    assert menu.compile_file is main.compile_file


def test_web_does_not_present_stale_artifacts_after_semantic_error(monkeypatch):
    monkeypatch.chdir(ROOT)
    (ROOT/'output/pytest_stale.cpp').write_text('stale cpp', encoding='utf-8')
    (ROOT/'output/pytest_stale.tac').write_text('stale tac', encoding='utf-8')
    response = app.test_client().post('/api/compile', json={'filename':'pytest_stale.minipar', 'code':'return 1;'})
    result = response.get_json()
    assert not result['success'] and 'ERRO SEMANTICO' in result['stderr']
    assert result['cpp'] == result['tac'] == ''
