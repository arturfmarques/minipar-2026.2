from pathlib import Path
import pytest
from semantic import SemanticAnalyzer
from parser import Parser
from lexer import Lexer
from ast_nodes import ForkExpr, JoinExpr, FuncDecl, SeqBlock, walk
from tac import TACGenerator
from tools.validate_parallel import SOURCES
from program_analyzer import get_program_spec


@pytest.mark.parametrize('source', [
    'var a=monotonic(); require(monotonic() >= a,"clock");',
    'print(floor(-1.2),to_string(42),get_env("X","fallback"));',
    'write_text("output/text.txt","contents");',
    'func save(string p) -> string { write_text(p,"svg"); return p; } var t=fork local save("output/x.svg"); print(join(t));',
])
def test_generic_native_library_valid_signatures(parse,source):
    analyzer=SemanticAnalyzer()
    assert analyzer.analyze(parse(source)),analyzer.diagnostics


@pytest.mark.parametrize('source', [
    'monotonic(1);', 'floor("bad");', 'to_string([1]);',
    'write_text(1,"text");', 'write_text("path",[1]);', 'get_env("name");',
    'require("bad","message");', 'require(true,1);',
    'func monotonic() {}', 'func floor(x) { return x; }',
    'var x=write_text("path","text");',
    'func f(){} var t=fork local f(); to_string(t);',
])
def test_generic_native_library_invalid_signatures(parse,source):
    analyzer=SemanticAnalyzer()
    assert not analyzer.analyze(parse(source))
    assert analyzer.diagnostics


@pytest.mark.parametrize('number',[8,9,10])
def test_new_programs_have_real_forks_before_joins_and_valid_tac(number):
    program=Parser(Lexer(SOURCES[number].read_text(encoding='utf-8')).tokenize()).parse()
    analyzer=SemanticAnalyzer()
    assert analyzer.analyze(program),analyzer.diagnostics
    main=next(s for s in program.statements if isinstance(s,SeqBlock))
    nodes=list(walk(main))
    forks=[n for n in nodes if isinstance(n,ForkExpr)]
    assert len(forks)==(8 if number==8 else number-4)
    assert max(nodes.index(f) for f in forks)<min(i for i,n in enumerate(nodes) if isinstance(n,JoinExpr))
    if number==10:
        assert [f.function for f in forks].count('trabalhador_sierpinski')==1
        recursive=next(s for s in program.statements if isinstance(s,FuncDecl) and s.name=='perfurar')
        assert any(getattr(n,'name','')=='perfurar' for n in walk(recursive.body))
    text=TACGenerator().generate_text(program)
    assert 'call monotonic, 0' in text and '= fork local' in text and '= join ' in text
    if number==10: assert 'call write_text, 2' in text
    spec=get_program_spec(str(SOURCES[number]))
    assert spec['multi_computer'] is None and spec['task_modes'] and not spec['requires_input']


def test_shared_algorithms_are_equivalent_across_the_three_sources():
    functions=[]
    for source in SOURCES.values():
        program=Parser(Lexer(source.read_text(encoding='utf-8')).tokenize()).parse()
        functions.append({s.name:s for s in program.statements if isinstance(s,FuncDecl)})
    for name in functions[0]:
        assert functions[0][name]==functions[1][name]==functions[2][name],name


def test_comments_and_string_literals_do_not_create_managed_tasks(tmp_path):
    file=tmp_path/'comments.minipar'
    file.write_text('# fork local missing()\nprint("fork remote(1,2)");',encoding='utf-8')
    assert get_program_spec(str(file))['task_modes']==[]
