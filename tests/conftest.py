import pytest
from lexer import Lexer
from parser import Parser


@pytest.fixture
def parse():
    return lambda source: Parser(Lexer(source).tokenize()).parse()
