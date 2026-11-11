from pathlib import Path
import pytest
from ast_nodes import ForkExpr, JoinExpr, walk
from diagnostics import ParseError
from lexer import Lexer, Token, TokenType, LexerError
from parser import Parser
from semantic import SemanticAnalyzer
from tac import TACGenerator

FUNCTION = 'func twice(number x) -> number { return x * 2; } '


def test_task_tokens_and_locations():
    tokens = Lexer('\n  fork local remote join task ->').tokenize()
    assert [t.type for t in tokens[:-1]] == [TokenType.FORK, TokenType.LOCAL,
        TokenType.REMOTE, TokenType.JOIN, TokenType.TYPE, TokenType.ARROW]
    assert (tokens[0].line, tokens[0].col) == (2, 3)


@pytest.mark.parametrize('destination', ['local', 'remote("localhost", 7000)', 'remote(input(), 8000 + 1)'])
def test_fork_ast_keeps_target_arguments_destination_and_location(parse, destination):
    program = parse(FUNCTION + '\nvar t = fork ' + destination + ' twice(2 + 3); var r = join(t);')
    fn, declaration, result = program.statements
    fork = declaration.init_value
    assert isinstance(fork, ForkExpr) and fork.function == 'twice'
    assert fork.arguments[0].op == '+'
    assert fork.destination.kind == ('local' if destination == 'local' else 'remote')
    if fork.destination.kind == 'remote': assert fork.destination.host and fork.destination.port
    assert (fork.line, fork.col) == (2, 9)
    assert isinstance(result.init_value, JoinExpr) and result.init_value.task.name == 't'
    assert fn.param_types == ['number'] and fn.return_type == 'number'


@pytest.mark.parametrize('source', [
    'var t = fork local twice(3); number r = join(t);',
    'task t = fork remote("127.0.0.1", 7000) twice(3); join(t);',
    'var t; t = fork local twice(3); var alias = t; print(join(alias));',
    'var t = fork local twice(3); var a = join(t); var b = join(t);',
    'var input_value = 2; var t = fork local twice(input_value); print(join(t));',
    'func constant() -> number { return 2; } var t = fork local constant(); number r = join(t);',
    'func emit() -> void { print(1); } task t = fork local emit(); join(t);',
])
def test_valid_tasks(parse, source):
    analyzer = SemanticAnalyzer()
    assert analyzer.analyze(parse(FUNCTION + source)), analyzer.diagnostics


def test_void_worker_and_channel_parameters(parse):
    source = '''func emit(c_channel channel, string value) -> void { send(channel, value); }
var channel = c_channel("localhost", 7001);
var t = fork remote("localhost", 7002) emit(channel, "done"); join(t);'''
    assert SemanticAnalyzer().analyze(parse(source))


@pytest.mark.parametrize('source', [
    'var t = fork twice(1);', 'var t = fork local twice;',
    'var t = fork remote("host") twice(1);',
    'var t = fork remote("host", 1, 2) twice(1);',
    'var t = fork remote("host", 1 twice(1);',
    'var t = fork local obj.method();', 'join();', 'join(1);',
    'join(missing, other);', 'join(t)', 'var r = join(t[0]);',
    'fork local twice(1);', 'func f(number) {}', 'func f() -> {}',
])
def test_invalid_new_syntax(parse, source):
    with pytest.raises(ParseError) as error:
        parse(source)
    assert error.value.diagnostic.line > 0 and error.value.diagnostic.col > 0


@pytest.mark.parametrize(('source', 'message'), [
    ('var t = fork local missing(1);', 'funcao global'),
    ('var t = fork local random();', 'funcao global'),
    ('var t = fork local twice();', 'espera 1'),
    ('var t = fork local twice("bad");', 'Tipo incompativel'),
    ('var t = fork remote(1, 7000) twice(2);', 'host'),
    ('var t = fork remote("host", "bad") twice(2);', 'porta'),
    ('var t = fork remote("", 7000) twice(2);', 'Host'),
    ('var t = fork remote("host", 0) twice(2);', 'Porta'),
    ('var t = fork remote("host", 70000) twice(2);', 'Porta'),
    ('var t = fork remote("host", 1.5) twice(2);', 'Porta'),
    ('var t = fork remote("host", -1) twice(2);', 'Porta'),
    ('join(missing);', 'nao declarada'),
    ('var t = 2; join(t);', 'Join exige'),
    ('var t = fork local twice(2); string r = join(t);', 'Tipo incompativel'),
    ('task t;', 'Task deve'),
    ('var r = 2 + fork local twice(2);', 'Fork deve'),
    ('var t = fork local twice(2); print(t);', 'Print exige'),
    ('seq { var t = fork local twice(2); } join(t);', 'nao declarada'),
])
def test_invalid_task_semantics(parse, source, message):
    analyzer = SemanticAnalyzer()
    assert not analyzer.analyze(parse(FUNCTION + source))
    assert any(message in d.message for d in analyzer.diagnostics)


@pytest.mark.parametrize('source', [
    'var state = 1; func worker() { return state; } var t = fork local worker();',
    'var state = 1; func helper() { return state; } func worker() { return helper(); } var t = fork local worker();',
    'par { var private = 1; print(private); }',
    'var state = 1; par { state = 2; print(1); }',
    'var items = [1]; par { items[0] = 2; print(1); }',
    'var items = [1]; par { items.append(2); print(1); }',
    'var state = 1; func f() { return state; } par { f(); }',
])
def test_independent_tasks_reject_implicit_dependencies(parse, source):
    assert not SemanticAnalyzer().analyze(parse(source))


def test_explicit_snapshots_and_channels_are_allowed_in_par(parse):
    assert SemanticAnalyzer().analyze(parse('var c = c_channel("localhost",7000); par { seq { send(c, 2); } seq { print(receive(c)); } }'))
    assert SemanticAnalyzer().analyze(parse('var n = 2; par { seq { var private = n; print(private); } print(n); }'))


def test_unresolved_dispatch_cannot_hide_global_capture_in_worker(parse):
    source = 'var secret = 1; class C { func read() { return secret; } } func worker(obj) { return obj.read(); } var c = new C(); var t = fork local worker(c);'
    analyzer = SemanticAnalyzer()
    assert not analyzer.analyze(parse(source))
    assert any('receptor de tipo desconhecido' in d.message for d in analyzer.diagnostics)


def test_typed_dispatch_keeps_transitive_capture_checks(parse):
    source = 'var secret = 1; class C { func read() { return secret; } } func worker(C obj) { return obj.read(); } var c = new C(); var t = fork local worker(c);'
    analyzer = SemanticAnalyzer()
    assert not analyzer.analyze(parse(source))
    assert any('captura estado global' in d.message for d in analyzer.diagnostics)


def test_typed_dispatch_without_capture_is_valid(parse):
    source = 'class C { var value = 2; func read() { return this.value; } } func worker(C obj) { return obj.read(); } var c = new C(); var t = fork local worker(c); print(join(t));'
    assert SemanticAnalyzer().analyze(parse(source))


def test_unknown_and_trailing_tokens_cannot_be_ignored():
    with pytest.raises(ParseError, match='desconhecido'):
        Parser([Token(TokenType.UNKNOWN, '@', 3, 8), Token(TokenType.END_OF_FILE, '', 3, 9)])
    with pytest.raises(ParseError, match='apos EOF'):
        Parser([Token(TokenType.END_OF_FILE, '', 1, 1), Token(TokenType.END_OF_FILE, '', 1, 2)])
    with pytest.raises(ParseError): Parser([])


def test_all_original_programs_keep_frontend_compatibility(parse):
    paths = sorted((Path(__file__).resolve().parents[1]).glob('*.minipar'))
    historical = {
        'teste1_calculadora_cliente_servidor.minipar', 'teste2_fatorial_fibonacci_par.minipar',
        'teste3_neuronio.minipar', 'teste4_rede_neural_xor.minipar', 'teste5_recomendacao.minipar',
        'teste6_quicksort_classes.minipar', 'teste7_quicksort_iterativo_tac.minipar',
        'teste_adicional1_paralelismo_3_computadores.minipar', 'teste_adicional2_tapete_sierpinski.minipar',
        'teste_ascii_art_divertidapkrl.minipar', 'teste_bnf_controles_input.minipar',
    }
    assert historical <= {p.name for p in paths}
    for path in paths:
        analyzer = SemanticAnalyzer()
        assert analyzer.analyze(parse(path.read_text(encoding='utf-8'))), (path.name, analyzer.diagnostics)


def test_task_ir_has_explicit_parameters_destination_and_result(parse):
    program = parse(FUNCTION + 'var t = fork remote("host",7000) twice(3); number result = join(t);')
    text = TACGenerator().generate_text(program)
    assert 'task_param_copy' in text and '= fork remote(' in text
    assert ', twice, 1' in text and '= join t' in text and 'result = ' in text
    assert 'func twice:' in text and 'arg x: number' in text
