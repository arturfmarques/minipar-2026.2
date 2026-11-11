import pytest
from ast_nodes import BinaryExpr, ParBlock, SeqBlock
from lexer import Lexer, LexerError, TokenType
from semantic import SemanticAnalyzer
from diagnostics import ParseError


def test_lexer_comments_escapes_and_locations():
    tokens = Lexer('# comentario\nvar nome = "a\\n\\\"b";').tokenize()
    assert [t.type for t in tokens] == [TokenType.VAR, TokenType.IDENTIFIER,
        TokenType.ASSIGN, TokenType.STRING_LITERAL, TokenType.SEMICOLON, TokenType.END_OF_FILE]
    assert (tokens[0].line, tokens[0].col) == (2, 1)
    assert tokens[3].lexeme == 'a\n"b'


@pytest.mark.parametrize('source', ['@', 'var x = "abc', 'var x = "abc' + chr(92), '&'])
def test_lexer_rejects_invalid_input(source):
    with pytest.raises(LexerError, match='Linha 1, coluna'):
        Lexer(source).tokenize()


def test_parser_precedence_and_blocks(parse):
    program = parse('seq { var x = 2 + 3 * 4; par { print(x); print(7); } }')
    block = program.statements[0]
    assert isinstance(block, SeqBlock)
    expression = block.statements[0].init_value
    assert isinstance(expression, BinaryExpr) and expression.op == '+'
    assert expression.right.op == '*'
    assert isinstance(block.statements[1], ParBlock)
    assert len(block.statements[1].statements) == 2


@pytest.mark.parametrize('source', ['print(1)', 'seq { print(1);', 'var = 3;'])
def test_parser_rejects_invalid_input(parse, capsys, source):
    with pytest.raises(ParseError) as error:
        parse(source)
    assert error.value.diagnostic.phase == 'SINTATICO'
    assert error.value.diagnostic.line == 1 and error.value.diagnostic.col > 0
    assert 'ERRO SINTATICO' in str(error.value)


def test_semantic_scope_and_assignment(parse):
    assert SemanticAnalyzer().analyze(parse('var x = 1; seq { var y = x + 2; x = y; } print(x);'))


@pytest.mark.parametrize(('source', 'message'), [
    ('print(x);', 'nao declarada'),
    ('var x = 1; var x = 2;', 'ja declarada'),
    ('number x = "a";', 'Tipo incompativel'),
    ('seq { var x = 1; } print(x);', 'nao declarada'),
    ('break;', 'fora de laco'),
    ('func f(a) { return a; } f();', 'espera 1'),
])
def test_semantic_rejects_invalid_program(parse, capsys, source, message):
    assert not SemanticAnalyzer().analyze(parse(source))
    assert message in capsys.readouterr().err
