from __future__ import annotations
from dataclasses import dataclass, field, fields, is_dataclass
from typing import List, Optional

class ASTNode:
    line: int = 1
    col: int = 1

@dataclass
class NumberExpr(ASTNode):
    value: str
    line: int = 1

@dataclass
class StringExpr(ASTNode):
    value: str
    line: int = 1

@dataclass
class BoolExpr(ASTNode):
    value: bool
    line: int = 1

@dataclass
class IdentifierExpr(ASTNode):
    name: str
    line: int = 1

@dataclass
class BinaryExpr(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode
    line: int = 1

@dataclass
class UnaryExpr(ASTNode):
    op: str
    operand: ASTNode
    line: int = 1

@dataclass
class VarDecl(ASTNode):
    name: str
    init_value: Optional[ASTNode] = None
    type: str = "var"
    line: int = 1

@dataclass
class Assignment(ASTNode):
    name: str
    value: ASTNode = None
    line: int = 1

@dataclass
class PrintStmt(ASTNode):
    arguments: List[ASTNode] = field(default_factory=list)
    line: int = 1

@dataclass
class SeqBlock(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)
    line: int = 1

@dataclass
class ParBlock(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)
    line: int = 1

@dataclass
class IfStmt(ASTNode):
    condition: ASTNode
    then_branch: ASTNode
    else_branch: Optional[ASTNode] = None
    line: int = 1

@dataclass
class WhileStmt(ASTNode):
    condition: ASTNode
    body: ASTNode
    line: int = 1

@dataclass
class DoWhileStmt(ASTNode):
    body: ASTNode
    condition: ASTNode
    line: int = 1

@dataclass
class ForStmt(ASTNode):
    initializer: Optional[ASTNode]
    condition: Optional[ASTNode]
    increment: Optional[ASTNode]
    body: ASTNode
    iterator_name: Optional[str] = None
    iterable: Optional[ASTNode] = None
    line: int = 1

@dataclass
class BreakStmt(ASTNode):
    line: int = 1

@dataclass
class ContinueStmt(ASTNode):
    line: int = 1

@dataclass
class ClassDecl(ASTNode):
    name: str
    superclass: Optional[str]
    attributes: List[VarDecl]
    methods: List[FuncDecl]
    line: int = 1

@dataclass
class FuncDecl(ASTNode):
    name: str
    params: List[str]
    body: ASTNode
    line: int = 1
    param_types: List[str] = field(default_factory=list)
    return_type: Optional[str] = None

@dataclass
class ReturnStmt(ASTNode):
    value: Optional[ASTNode]
    line: int = 1

@dataclass
class MethodCall(ASTNode):
    object: ASTNode
    method_name: str
    arguments: List[ASTNode]
    line: int = 1

@dataclass
class FuncCallExpr(ASTNode):
    name: str
    arguments: List[ASTNode]
    line: int = 1

@dataclass
class PropertyAccess(ASTNode):
    object: ASTNode
    property_name: str
    line: int = 1

@dataclass
class PropertyAssign(ASTNode):
    object: ASTNode
    property_name: str
    value: ASTNode
    line: int = 1

@dataclass
class NewExpr(ASTNode):
    class_name: str
    arguments: List[ASTNode]
    line: int = 1

@dataclass
class ThisExpr(ASTNode):
    line: int = 1

@dataclass
class CChannelExpr(ASTNode):
    ip: ASTNode
    port: ASTNode
    line: int = 1

@dataclass
class SendStmt(ASTNode):
    channel: ASTNode
    message: ASTNode
    line: int = 1

@dataclass
class ReceiveExpr(ASTNode):
    channel: ASTNode
    line: int = 1

@dataclass
class InputExpr(ASTNode):
    prompt: Optional[ASTNode] = None
    line: int = 1

@dataclass
class ListLiteral(ASTNode):
    elements: List[ASTNode]
    line: int = 1

@dataclass
class MatrixCreateExpr(ASTNode):
    rows: ASTNode
    cols: ASTNode
    init_value: ASTNode
    line: int = 1

@dataclass
class IndexExpr(ASTNode):
    object: ASTNode
    index: ASTNode
    line: int = 1

@dataclass
class IndexAssign(ASTNode):
    target: ASTNode
    value: ASTNode
    line: int = 1

@dataclass
class Program(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)
    line: int = 1


@dataclass
class TaskDestination(ASTNode):
    kind: str                         # local | remote
    host: Optional[ASTNode] = None
    port: Optional[ASTNode] = None
    line: int = 1
    core: Optional[ASTNode] = None


@dataclass
class ForkExpr(ASTNode):
    function: str
    arguments: List[ASTNode]
    destination: TaskDestination
    line: int = 1


@dataclass
class JoinExpr(ASTNode):
    task: IdentifierExpr
    line: int = 1


def walk(node):
    """Percurso somente de campos AST, reutilizado por semântica e backends."""
    if not isinstance(node, ASTNode):
        return
    yield node
    if is_dataclass(node):
        for member in fields(node):
            value = getattr(node, member.name)
            if isinstance(value, ASTNode):
                yield from walk(value)
            elif isinstance(value, list):
                for child in value:
                    yield from walk(child)
