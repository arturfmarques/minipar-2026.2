import pytest
from ast_nodes import BinaryExpr, ForkExpr, walk
from codegen import CppCodeGenerator
from diagnostics import CompilerError, ParseError
from educational_pipeline import serialize_ast
from lexer import Lexer, TokenType
from semantic import SemanticAnalyzer
from tac import TACGenerator

FUNCTION = 'func square(number x) -> number { return x * x; } '


def test_affinity_words_are_contextual_and_old_identifiers_still_work(parse):
    tokens = Lexer('on core(0)').tokenize()
    assert [t.type for t in tokens[:2]] == [TokenType.IDENTIFIER, TokenType.IDENTIFIER]
    analyzer = SemanticAnalyzer()
    assert analyzer.analyze(parse('var on = 1; var core = 2; print(on + core);'))


@pytest.mark.parametrize('selector', ['0', '1', 'cpu', 'cpu + 2 * 3', 'available_cpus()[0]'])
def test_fork_affinity_ast_and_semantics(parse, selector):
    program = parse(FUNCTION + 'var cpu = 0;\nvar t = fork local square(7) on core(' + selector + '); print(join(t));')
    node = next(n for n in walk(program) if isinstance(n, ForkExpr))
    assert node.destination.kind == 'local' and node.destination.core is not None
    assert node.destination.core.line == 2 and node.destination.core.col > node.col
    analyzer = SemanticAnalyzer()
    assert analyzer.analyze(program), analyzer.diagnostics
    if selector == 'cpu + 2 * 3':
        assert isinstance(node.destination.core, BinaryExpr)
        assert node.destination.core.op == '+' and node.destination.core.right.op == '*'
    data = serialize_ast(program)
    assert 'core' in str(data)


@pytest.mark.parametrize('suffix', ['on', 'on core', 'on core()', 'on core(1, 2)',
    'on core 1', 'on core(1', 'on host("localhost", 7000)', 'on CORE(0)', 'on core(0) on core(1)'])
def test_invalid_affinity_syntax_is_not_ignored(parse, suffix):
    with pytest.raises(ParseError) as error:
        parse(FUNCTION + 'var t = fork local square(7) ' + suffix + ';')
    assert error.value.diagnostic.line > 0 and error.value.diagnostic.col > 0


@pytest.mark.parametrize(('selector', 'message'), [
    ('"0"', 'Tipo incompativel'), ('true', 'Tipo incompativel'),
    ('-1', 'inteiro nao negativo'), ('0.5', 'inteiro nao negativo'),
    ('missing', 'nao declarada'), ('[0]', 'Tipo incompativel'),
])
def test_invalid_affinity_semantics_blocks_backend(parse, selector, message):
    program = parse(FUNCTION + '\nvar t = fork local square(7) on core(' + selector + ');')
    analyzer = SemanticAnalyzer()
    assert not analyzer.analyze(program)
    assert any(message in d.message for d in analyzer.diagnostics)
    assert any(d.line == 2 and d.col > 1 for d in analyzer.diagnostics)
    with pytest.raises(CompilerError):
        CppCodeGenerator(analyzer).render(program)


def test_remote_affinity_is_rejected_explicitly(parse):
    program = parse(FUNCTION + 'var t = fork remote("localhost", 7000) square(7) on core(0);')
    analyzer = SemanticAnalyzer()
    assert not analyzer.analyze(program)
    assert any('exige fork local' in d.message for d in analyzer.diagnostics)


def test_tac_cpp_and_old_forks_keep_their_destinations(parse):
    program = parse(FUNCTION + 'var cpu = 0; var t = fork local square(7) on core(cpu + 1); print(join(t));')
    analyzer = SemanticAnalyzer()
    assert analyzer.analyze(program)
    tac = TACGenerator().generate_text(program)
    cpp = CppCodeGenerator(analyzer).render(program)
    assert 'fork local on core(' in tac and ' = join ' in tac
    assert 'mp::fork_local_on("square"' in cpp
    changed = TACGenerator().generate_text(parse(FUNCTION + 'var t = fork local square(7) on core(3);'))
    assert changed != tac and '3' in changed
    for destination, call in [('local', 'mp::fork_local("square"'), ('remote("localhost", 7000)', 'mp::fork_remote(')]:
        old = parse(FUNCTION + 'var t = fork ' + destination + ' square(7); print(join(t));')
        assert all(n.destination.core is None for n in walk(old) if isinstance(n, ForkExpr))
        assert call in CppCodeGenerator().render(old)
        assert 'on core(' not in TACGenerator().generate_text(old)


@pytest.mark.parametrize('source', ['print(current_cpu(0));', 'print(available_cpus(1));'])
def test_cpu_query_arity_is_checked(parse, source):
    analyzer = SemanticAnalyzer()
    assert not analyzer.analyze(parse(source))
    assert any('argumento' in d.message for d in analyzer.diagnostics)
