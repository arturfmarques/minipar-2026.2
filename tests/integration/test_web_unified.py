"""Navegacao compartilhada e dados reais das visualizacoes, sem outro servidor."""
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest
from app import app
import educational_web as web
from educational_pipeline import serialize_ast
from lexer import Lexer
from parser import Parser

ROOT = Path(__file__).resolve().parents[2]


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links, self.ids, self.stages = [], set(), set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'): self.ids.add(attrs['id'])
        if attrs.get('data-stage'): self.stages.add(attrs['data-stage'])
        if tag == 'a' and 'web-mode-link' in attrs.get('class','').split(): self.links.append(attrs)


@pytest.mark.parametrize(('route','current'),[('/','/'),('/educacional','/educacional')])
def test_shared_header_preserves_routes_and_active_environment(route,current):
    response = app.test_client().get(route)
    assert response.status_code == 200
    page = Page(response.get_data(as_text=True))
    assert {link['href'] for link in page.links} == {'/','/educacional'}
    assert [link['href'] for link in page.links if link.get('aria-current')=='page'] == [current]
    assert all('target' not in link for link in page.links)
    assert b'MiniPar 2026.2' in response.data and b'web-common.js' in response.data
    assert not any(link['href'].startswith(('http:','https:')) for link in page.links)


def test_original_controls_and_educational_pipeline_remain_available():
    client = app.test_client()
    original = Page(client.get('/').get_data(as_text=True))
    assert {'editor-minipar','editor-cpp','editor-tac','terminal-output','test-list','btn-run','btn-clear'} <= original.ids
    html = client.get('/educacional').get_data(as_text=True)
    educational = Page(html)
    assert {'source-editor','stdin-editor','compile-button','run-button','downloads-button','execution-console'} <= educational.ids
    assert educational.stages == {'tokens','ast','semantic','tac','cpp'}
    assert 'intro-route' not in html and 'brand-mark' not in html and 'eyebrow' not in html
    assert 'educacional-view.js' in html and 'd3.min.js' not in html


def test_shared_assets_are_served_by_the_same_flask_application():
    client = app.test_client()
    for path in ('css/web-common.css','css/educacional.css','js/web-common.js','js/educacional-view.js','js/educacional.js','js/script.js'):
        response = client.get('/static/'+path)
        assert response.status_code == 200 and len(response.data)>100
    assert app.blueprints['educational'] is web.educational


def test_programs_1_to_11_are_loaded_from_the_same_files_in_both_modes():
    client = app.test_client()
    old = set(client.get('/api/tests').get_json()['tests'])
    educational = client.get('/api/educacional/examples').get_json()['examples']
    for number in range(1,12):
        source = next((ROOT/'tests').glob(f'teste{number}_*.minipar'))
        assert source.name in old and any(item['key']==source.name for item in educational)
        a = client.post('/api/get_test',json={'filename':source.name}).get_json()['code']
        b = client.get('/api/educacional/examples/'+source.name).get_json()['code']
        assert a == b == source.read_text(encoding='utf-8')


def test_javascript_navigation_filters_and_ast_with_real_compiler_data(tmp_path):
    node = shutil.which('node')
    if not node: pytest.skip('Node indisponivel para executar testes JavaScript sem navegador')
    code = '''func f(number n) -> number { return n + 1; }
        var cpu=available_cpus()[0]; var t=fork local f(2) on core(cpu); print(join(t));'''
    large = next((ROOT/'tests').glob('teste11_*.minipar')).read_text(encoding='utf-8')
    tokens = [{'number':i+1,'type':token.type.name,'lexeme':token.lexeme,'line':token.line,'column':token.col}
              for i,token in enumerate(Lexer(code).tokenize())]
    data = tmp_path/'ui-data.json'
    data.write_text(json.dumps({'tokens':tokens,'small_ast':serialize_ast(Parser(Lexer(code).tokenize()).parse())[0],
                                'large_ast':serialize_ast(Parser(Lexer(large).tokenize()).parse())[0]}),encoding='utf-8')
    result = subprocess.run([node,'--test',str(ROOT/'tests/web/unified-web.test.cjs')],cwd=ROOT,
                            capture_output=True,text=True,encoding='utf-8',env={**os.environ,'MINIPAR_UI_DATA':str(data)},timeout=30)
    (ROOT/'output/validacoes').mkdir(parents=True,exist_ok=True)
    (ROOT/'output/validacoes/web-integrada-js.json').write_text(json.dumps({'returncode':result.returncode,
        'stdout':result.stdout,'stderr':result.stderr},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert result.returncode == 0, result.stdout+result.stderr


@pytest.mark.native
def test_educational_affinity_input_and_downloads_use_the_real_compiler(tmp_path,monkeypatch):
    monkeypatch.setattr(web,'WORKSPACE',tmp_path/'jobs')
    client = app.test_client()
    code = '''func f(number cpu, number n) -> number {
        require(current_cpu()==cpu, "CPU_INCORRETA"); return n*n;
    }
    var cpu=available_cpus()[0]; var n=to_number(input());
    var t=fork local f(cpu,n) on core(cpu); print(join(t));'''
    for stage in ('tokens','ast','semantic','tac','cpp'):
        result = client.post('/api/educacional/analyze',json={'code':code,'stage':stage}).get_json()
        assert result['success'], result
    compiled = client.post('/api/educacional/compile',json={'code':code}).get_json()
    assert compiled['success'] and compiled['compilation']['returncode']==0
    for key in ('cpp','tac','executable'):
        response = client.get(compiled['downloads'][key])
        assert response.status_code == 200 and response.data
        assert 'attachment' in response.headers['Content-Disposition']
    executed = client.post('/api/educacional/jobs/'+compiled['job_id']+'/run',json={'stdin':'8\n'}).get_json()
    assert executed['success'] and executed['execution']['stdout']=='64\n'
