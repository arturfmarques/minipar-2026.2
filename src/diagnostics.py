"""Diagnósticos das fases do compilador, independentes das interfaces."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnostic:
    phase: str
    message: str
    line: int = 1
    col: int = 1

    def __str__(self):
        return f"[ERRO {self.phase}] Linha {self.line}, coluna {self.col}: {self.message}"


class CompilerError(ValueError):
    def __init__(self, message, line=1, col=1, phase='COMPILADOR'):
        self.diagnostic = Diagnostic(phase, message, line, col)
        super().__init__(str(self.diagnostic))


class ParseError(CompilerError):
    def __init__(self, message, line=1, col=1):
        super().__init__(message, line, col, 'SINTATICO')


class BackendUnsupportedError(CompilerError):
    def __init__(self, message, line=1, col=1):
        super().__init__(message, line, col, 'BACKEND')
