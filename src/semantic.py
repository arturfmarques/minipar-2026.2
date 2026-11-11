from __future__ import annotations
import sys
import math
from decimal import Decimal
from dataclasses import dataclass, field, fields
from typing import Dict, List, Optional
from diagnostics import Diagnostic
from native_builtins import BUILTINS
from ast_nodes import (
    ASTNode, Program, VarDecl, Assignment, PrintStmt, IdentifierExpr, BinaryExpr,
    UnaryExpr, NumberExpr, StringExpr, BoolExpr, SeqBlock, ParBlock, IfStmt, WhileStmt,
    DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, InputExpr,
    ClassDecl, FuncDecl, ReturnStmt, MethodCall, FuncCallExpr, PropertyAccess, PropertyAssign, NewExpr, ThisExpr,
    CChannelExpr, SendStmt, ReceiveExpr, ListLiteral, MatrixCreateExpr, IndexExpr, IndexAssign,
    ForkExpr, JoinExpr, walk
)

@dataclass
class Symbol:
    name: str
    type: str
    params: List[str] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)
    methods: Dict[str, Symbol] = field(default_factory=dict)
    param_types: List[str] = field(default_factory=list)
    return_type: str = 'unknown'
    superclass: Optional[str] = None
    definition: Optional[FuncDecl] = None
    captures: set[str] = field(default_factory=set)
    calls: set[str] = field(default_factory=set)
    unresolved_methods: bool = False
    category: str = 'variável'
    line: int = 1

class SemanticAnalyzer:
    def __init__(self) -> None:
        self._scopes: List[Dict[str, Symbol]] = []
        self._has_errors = False
        self._current_function: Optional[str] = None
        self._current_class: Optional[str] = None
        self._classes: Dict[str, Symbol] = {}
        self._functions: Dict[str, Symbol] = {}
        self._loop_depth = 0
        self.diagnostics: list[Diagnostic] = []
        self._current_callable: Optional[Symbol] = None
        self._task_boundaries: list[int] = []
        self._callables: dict[str, Symbol] = {}
        self._forks: list[ForkExpr] = []
        self._independent_calls: list[tuple[ASTNode, str]] = []
        self._node: Optional[ASTNode] = None
        self._parent: Optional[ASTNode] = None
        self._specializing: set[str] = set()
        self.scope_history: list[dict] = []
        self._scope_tags: list[dict] = []
        self._scope_serial = 0
        self._capture_scopes = False
        self._enter_scope()

    def _enter_scope(self) -> None:
        self._scopes.append({})
        node = self._node
        label = ('global' if not self._scope_tags else
                 f'{type(node).__name__} linha {getattr(node, "line", 1)}')
        self._scope_tags.append({'id': self._scope_serial, 'label': label,
                                 'parent': self._scope_tags[-1]['id'] if self._scope_tags else None})
        self._scope_serial += 1
    def _exit_scope(self) -> None:
        if len(self._scopes) > 1:
            if self._capture_scopes and self._scopes[-1]:
                self.scope_history.append({**self._scope_tags[-1], 'symbols': self._scopes[-1].copy()})
            self._scopes.pop()
            self._scope_tags.pop()

    def _get_context(self) -> str:
        return f" (Funcao: {self._current_function})" if self._current_function else ""

    def _define_symbol(self, name: str, type_: str, line: int, params: Optional[List[str]] = None) -> None:
        if name in self._scopes[-1]:
            self._report(line, f"Variavel '{name}' ja declarada.")
        else:
            category = ('função' if type_ == 'FUNC' else 'classe' if type_ == 'CLASS' else
                        'parâmetro' if isinstance(self._node, FuncDecl) and name in self._node.params else 'variável')
            self._scopes[-1][name] = Symbol(name=name, type=type_, params=params or [],
                                             category=category, line=line)

    def _lookup(self, name: str) -> Optional[Symbol]:
        for scope in reversed(self._scopes):
            if name in scope: return scope[name]
        return None

    def _report(self, line: int, message: str) -> None:
        diagnostic = Diagnostic('SEMANTICO', message + self._get_context(), line,
                                getattr(self._node, 'col', 1))
        self.diagnostics.append(diagnostic)
        print(diagnostic, file=sys.stderr)
        self._has_errors = True

    def _member(self, class_name, member, methods=False):
        seen = set()
        while class_name in self._classes and class_name not in seen:
            seen.add(class_name)
            cls = self._classes[class_name]
            table = cls.methods if methods else cls.attributes
            if member in table:
                return table[member]
            class_name = cls.superclass
        return None

    def _check_type(self, node, expected, actual, description):
        if not self._types_compatible(expected, actual):
            self._report(node.line, f"Tipo incompativel em {description}: esperado {expected}, recebido {actual}.")
        elif expected == 'int' and node is not None:
            value = node.value if isinstance(node, (ReturnStmt, PropertyAssign)) else node
            literal = self._numeric_literal(value)
            if literal is not None and (not literal.is_finite() or literal != literal.to_integral_value()
                                        or not -(2**63) <= literal < 2**63):
                self._report(node.line, f"Tipo incompativel em {description}: int exige inteiro assinado de 64 bits.")
            if value is not None:
                value.int_conversion = True

    @staticmethod
    def _numeric_literal(node):
        if isinstance(node, NumberExpr): return Decimal(node.value)
        if isinstance(node, UnaryExpr) and node.op in ('+', '-'):
            value = SemanticAnalyzer._numeric_literal(node.operand)
            if value is not None: return value if node.op == '+' else -value
        return None

    def _integer_operand(self, node):
        if isinstance(node, NumberExpr): return node.value.isdigit()
        if isinstance(node, UnaryExpr) and node.op in ('+', '-'):
            return self._integer_operand(node.operand)
        return self._infer_type(node) == 'int'

    def _check_arguments(self, node, symbol, arguments, description):
        if len(symbol.params) != len(arguments):
            self._report(node.line, f"{description} espera {len(symbol.params)} argumento(s), recebeu {len(arguments)}.")
        for expected, arg in zip(symbol.param_types, arguments):
            self._check_type(arg, expected, self._infer_type(arg), f"argumento de {description}")
            if self._infer_type(arg).startswith('task<') or self._infer_type(arg) == 'void':
                self._report(arg.line, 'Handle task/void nao pode ser passado a funcao/metodo.')
        if isinstance(node, ForkExpr):
            node.argument_types = ['int' if typ == 'int' else self._infer_type(arg)
                                   for typ, arg in zip(symbol.param_types, arguments)]
        self._check_untyped_arguments(node, symbol, arguments)
        if self._current_callable:
            self._current_callable.calls.add(symbol.name)
        if self._task_boundaries:
            self._independent_calls.append((node, symbol.name))

    def _validate_type_name(self, name, node, allow_void=False):
        if name not in {'var', 'number', 'int', 'string', 'bool', 'list', 'dict', 'matrix', 'c_channel', 'task', *self._classes} and not (allow_void and name == 'void'):
            self._report(node.line, f"Tipo '{name}' nao permitido neste contexto.")

    def _endpoint(self, node, host, port):
        self.validate_node(host)
        self.validate_node(port)
        self._check_type(host, 'string', self._infer_type(host), 'host do destino/canal')
        self._check_type(port, 'number', self._infer_type(port), 'porta do destino/canal')
        if isinstance(host, StringExpr) and not host.value.strip():
            self._report(host.line, 'Host nao pode ser vazio.')
        if isinstance(port, NumberExpr):
            value = float(port.value)
            if not value.is_integer() or not 1 <= value <= 65535:
                self._report(port.line, 'Porta deve ser inteiro entre 1 e 65535.')
        if isinstance(port, UnaryExpr) and port.op == '-' and isinstance(port.operand, NumberExpr):
            self._report(port.line, 'Porta deve ser inteiro entre 1 e 65535.')

    def _core_affinity(self, node):
        core = node.destination.core
        if core is None:
            return
        self.validate_node(core)
        previous = self._node
        self._node = core
        try:
            if node.destination.kind != 'local':
                self._report(core.line, 'on core(...) exige fork local; nao seleciona CPU de trabalhador remoto.')
            self._check_type(core, 'number', self._infer_type(core), 'processador de core')
            value = None
            if isinstance(core, NumberExpr):
                value = float(core.value)
            elif isinstance(core, UnaryExpr) and core.op == '-' and isinstance(core.operand, NumberExpr):
                value = -float(core.operand.value)
            if value is not None and (not math.isfinite(value) or value < 0 or not value.is_integer()):
                self._report(core.line, 'core exige identificador inteiro nao negativo de processador logico.')
        finally:
            self._node = previous

    def _check_write(self, node, target):
        while isinstance(target, (PropertyAccess, IndexExpr)):
            target = target.object
        if isinstance(target, IdentifierExpr) and self._task_boundaries:
            boundary = self._task_boundaries[-1]
            for index in range(len(self._scopes) - 1, -1, -1):
                if target.name in self._scopes[index]:
                    if index < boundary:
                        self._report(node.line, f"Tarefa independente nao pode escrever em '{target.name}' do escopo externo; use mensagens.")
                    break

    def _check_builtin(self, node):
        signature = BUILTINS[node.name]
        counts, types = list(signature.arities), signature.parameters
        if len(node.arguments) not in counts:
            self._report(node.line, f"Funcao '{node.name}' espera {counts} argumento(s), recebeu {len(node.arguments)}.")
        for expected, arg in zip(types, node.arguments):
            actual = self._infer_type(arg)
            if expected == 'collection':
                if actual not in ('list', 'matrix', 'string', 'var', 'unknown'):
                    self._report(arg.line, 'len exige lista, matriz ou string.')
            elif expected == 'scalar':
                if actual not in ('number','int','bool','string','var','unknown'):
                    self._report(arg.line, f"{node.name} exige valor escalar.")
            else:
                self._check_type(arg, expected, actual, f"argumento de '{node.name}'")

    def _check_untyped_arguments(self, node, symbol, arguments):
        # Restrições óbvias do corpo também se aplicam aos parâmetros legados sem tipo.
        actuals = {name: self._infer_type(arg) for name, arg, typ in
                   zip(symbol.params, arguments, symbol.param_types) if typ == 'var'}
        def inspect(expression, shadowed):
            if isinstance(expression, (FuncDecl, ClassDecl)):
                return
            if isinstance(expression, SeqBlock):
                local = set(shadowed)
                for statement in expression.statements:
                    inspect(statement, local)
                    if isinstance(statement, VarDecl): local.add(statement.name)
                return
            if isinstance(expression, ForStmt):
                local = set(shadowed)
                if expression.iterator_name:
                    inspect(expression.iterable, shadowed)
                    local.add(expression.iterator_name)
                else:
                    inspect(expression.initializer, shadowed)
                    if isinstance(expression.initializer, VarDecl): local.add(expression.initializer.name)
                for child in (expression.condition, expression.increment, expression.body): inspect(child, local)
                return
            if expression is None: return
            constrained = []
            if isinstance(expression, BinaryExpr) and expression.op in ('-', '*', '/', '%'):
                constrained = [(expression.left, {'number', 'int'}), (expression.right, {'number', 'int'})]
            elif isinstance(expression, BinaryExpr) and expression.op in ('+', '<', '>', '<=', '>=', '==', '!='):
                def operand_type(operand):
                    if isinstance(operand, IdentifierExpr):
                        return actuals.get(operand.name, 'unknown') if operand.name not in shadowed else 'unknown'
                    return self._infer_type(operand) if isinstance(operand, (NumberExpr, StringExpr, BoolExpr, ListLiteral)) else 'unknown'
                left, right = operand_type(expression.left), operand_type(expression.right)
                if left not in ('unknown', 'var') and right not in ('unknown', 'var'):
                    compatible = self._types_compatible(left, right) or self._types_compatible(right, left)
                    if expression.op == '+':
                        compatible = compatible and left in ('number', 'int', 'string', 'list')
                    if not compatible:
                        self._report(node.line, f"Tipo incompativel nos operandos de '{symbol.name}': {left}, {right}.")
            elif isinstance(expression, BinaryExpr) and expression.op in ('&&', '||'):
                constrained = [(expression.left, {'number', 'int', 'bool'}), (expression.right, {'number', 'int', 'bool'})]
            elif isinstance(expression, UnaryExpr):
                constrained = [(expression.operand, {'number', 'int', 'bool'} if expression.op == '!' else {'number', 'int'})]
            elif isinstance(expression, (ReceiveExpr, SendStmt)):
                constrained = [(expression.channel, {'c_channel'})]
                if isinstance(expression, SendStmt):
                    constrained.append((expression.message, {'number', 'int', 'bool', 'string'}))
            elif isinstance(expression, CChannelExpr):
                constrained = [(expression.ip, {'string'}), (expression.port, {'number', 'int'})]
            elif isinstance(expression, IndexExpr):
                constrained = [(expression.object, {'list', 'matrix', 'string'}), (expression.index, {'number', 'int'})]
            for operand, allowed in constrained:
                if isinstance(operand, IdentifierExpr) and operand.name not in shadowed:
                    actual = actuals.get(operand.name, 'unknown')
                    if actual not in allowed | {'unknown', 'var'}:
                        self._report(node.line, f"Tipo incompativel no argumento '{operand.name}' de '{symbol.name}': {actual}.")
            for member in fields(expression):
                value = getattr(expression, member.name)
                if isinstance(value, ASTNode): inspect(value, shadowed)
                elif isinstance(value, list):
                    for child in value:
                        if isinstance(child, ASTNode): inspect(child, set(shadowed))
        inspect(symbol.definition.body, set())

    def _gather_return_types(self, node):
        """Inferência respeita escopos; um nome sombreado não altera o parâmetro externo."""
        if node is None or isinstance(node, (FuncDecl, ClassDecl, ParBlock)): return []
        if isinstance(node, ReturnStmt):
            return [self._infer_type(node.value) if node.value else 'void']
        if isinstance(node, VarDecl):
            typ = self._infer_type(node.init_value) if node.type == 'var' else node.type
            self._scopes[-1][node.name] = Symbol(node.name, typ)
            return []
        if isinstance(node, SeqBlock):
            self._enter_scope()
            result = []
            for child in node.statements: result.extend(self._gather_return_types(child))
            self._exit_scope()
            return result
        if isinstance(node, (IfStmt, WhileStmt, DoWhileStmt, ForStmt)):
            self._enter_scope()
            if isinstance(node, ForStmt):
                self._gather_return_types(node.initializer)
                if node.iterator_name:
                    self._scopes[-1][node.iterator_name] = Symbol(node.iterator_name, 'var')
            if isinstance(node, IfStmt):
                result = []
                for branch in (node.then_branch, node.else_branch):
                    self._enter_scope()
                    result.extend(self._gather_return_types(branch))
                    self._exit_scope()
            else:
                result = self._gather_return_types(node.body)
            self._exit_scope()
            return result
        return []

    def _specialized_return(self, symbol, arguments):
        if symbol.return_type not in ('unknown', 'var') or symbol.name in self._specializing:
            return symbol.return_type
        actuals = [self._infer_type(arg) for arg in arguments]
        old_scopes, old_class = self._scopes, self._current_class
        self._specializing.add(symbol.name)
        try:
            self._scopes = [old_scopes[0], {name: Symbol(name, typ) for name, typ in zip(symbol.params, actuals)}]
            self._current_class = symbol.name.split('.')[0] if '.' in symbol.name else None
            returns = self._gather_return_types(symbol.definition.body)
            known = set(returns) - {'unknown', 'var'}
            return next(iter(known)) if len(known) == 1 else 'unknown'
        finally:
            self._scopes, self._current_class = old_scopes, old_class
            self._specializing.remove(symbol.name)

    def _infer_type(self, node: Optional[ASTNode]) -> str:
        if node is None: return "unknown"
        if isinstance(node, NumberExpr): return "number"
        if isinstance(node, StringExpr): return "string"
        if isinstance(node, BoolExpr): return "bool"
        if isinstance(node, InputExpr): return "string"
        if isinstance(node, CChannelExpr): return "c_channel"
        if isinstance(node, ReceiveExpr): return "string"
        if isinstance(node, ListLiteral): return "list"
        if isinstance(node, MatrixCreateExpr): return "matrix"
        if isinstance(node, NewExpr): return node.class_name
        if isinstance(node, ThisExpr): return self._current_class or "unknown"
        if isinstance(node, ForkExpr):
            symbol = self._functions.get(node.function)
            return f"task<{self._specialized_return(symbol, node.arguments) if symbol else 'unknown'}>"
        if isinstance(node, JoinExpr):
            symbol = self._lookup(node.task.name)
            return symbol.type[5:-1] if symbol and symbol.type.startswith('task<') else 'unknown'
        if isinstance(node, IdentifierExpr):
            sym = self._lookup(node.name)
            return sym.type if sym else "unknown"
        if isinstance(node, UnaryExpr):
            return "bool" if node.op == "!" else self._infer_type(node.operand)
        if isinstance(node, BinaryExpr):
            lt, rt = self._infer_type(node.left), self._infer_type(node.right)
            if node.op in ("==", "!=", "<", ">", "<=", ">=", "&&", "||"): return "bool"
            if node.op == "+" and (lt == "string" or rt == "string"): return "string"
            if node.op == "+" and (lt == "list" or rt == "list"): return "list"
            if node.op in ('+', '-', '*', '%') and 'int' in (lt, rt) and self._integer_operand(node.left) and self._integer_operand(node.right):
                return 'int'
            return "number"
        if isinstance(node, PropertyAccess):
            obj_type = self._infer_type(node.object)
            attribute = self._member(obj_type, node.property_name)
            if attribute is not None: return attribute
            if node.property_name == 'size' and obj_type in ('list', 'matrix', 'string'): return 'number'
            return "unknown"
        if isinstance(node, MethodCall):
            symbol = self._member(self._infer_type(node.object), node.method_name, methods=True)
            if symbol: return self._specialized_return(symbol, node.arguments)
            if node.method_name == 'size': return 'number'
            if node.method_name in ('append', 'push_back', 'clear'): return 'void'
            return "unknown"
        if isinstance(node, FuncCallExpr):
            if node.name in BUILTINS: return BUILTINS[node.name].result
            if node.name in self._functions: return self._specialized_return(self._functions[node.name], node.arguments)
            return "unknown"
        if isinstance(node, IndexExpr): return "unknown"
        return "unknown"

    def _types_compatible(self, declared: str, actual: str) -> bool:
        if declared in ("var", "unknown") or actual in ("unknown", "var"): return True
        if declared == "int" and actual == "number": return True
        if declared == "number" and actual == "int": return True
        if declared == 'task' and actual.startswith('task<'): return True
        if declared in self._classes and actual in self._classes:
            current, seen = actual, set()
            while current in self._classes and current not in seen:
                if current == declared: return True
                seen.add(current)
                current = self._classes[current].superclass
        return declared == actual

    def _collect_declarations(self, program: Program) -> None:
        for stmt in program.statements:
            if isinstance(stmt, FuncDecl):
                if stmt.name in BUILTINS:
                    self._report(stmt.line, f"Funcao builtin '{stmt.name}' nao pode ser redefinida.")
                if stmt.name in self._functions:
                    self._report(stmt.line, f"Funcao '{stmt.name}' ja declarada.")
                symbol = Symbol(stmt.name, "FUNC", params=stmt.params,
                                param_types=stmt.param_types or ['var'] * len(stmt.params),
                                return_type=stmt.return_type or 'unknown', definition=stmt)
                self._functions[stmt.name] = symbol
                self._callables[stmt.name] = symbol
            elif isinstance(stmt, ClassDecl):
                attrs = {a.name: self._infer_type(a.init_value) if a.type == 'var' else a.type for a in stmt.attributes}
                methods = {}
                for method in stmt.methods:
                    if method.name in methods:
                        self._report(method.line, f"Metodo '{method.name}' ja declarado.")
                    symbol = Symbol(f'{stmt.name}.{method.name}', 'FUNC', params=method.params,
                                    param_types=method.param_types or ['var'] * len(method.params),
                                    return_type=method.return_type or 'unknown', definition=method)
                    methods[method.name] = symbol
                    self._callables[symbol.name] = symbol
                self._classes[stmt.name] = Symbol(stmt.name, "CLASS", attributes=attrs, methods=methods, superclass=stmt.superclass)

    def _infer_signatures(self):
        # Ponto fixo: chamadas futuras e recursivas usam os retornos conhecidos.
        # unknown continua gradual para parâmetros antigos sem anotações.
        old_scopes, old_class = self._scopes, self._current_class
        for _ in range(len(self._callables) + 2):
            changed = False
            for symbol in self._callables.values():
                fn = symbol.definition
                if fn.return_type:
                    continue
                self._current_class = symbol.name.split('.')[0] if '.' in symbol.name else None
                self._scopes = [old_scopes[0].copy(), {p: Symbol(p, t) for p, t in zip(fn.params, symbol.param_types)}]
                if self._current_class:
                    for name, cls in self._classes.items():
                        if name == self._current_class:
                            for attr, typ in cls.attributes.items():
                                self._scopes[-1][attr] = Symbol(attr, typ)
                returned = self._gather_return_types(fn.body)
                known = {t for t in returned if t not in ('unknown', 'var')}
                inferred = 'void' if not returned else (next(iter(known)) if len(known) == 1 else 'unknown')
                if symbol.return_type != inferred:
                    symbol.return_type = inferred
                    changed = True
            if not changed:
                break
        self._scopes, self._current_class = old_scopes, old_class

    def validate_node(self, node: ASTNode) -> None:
        previous = self._node
        previous_parent = self._parent
        self._parent = previous
        self._node = node
        try:
            self._validate_node(node)
            if node is not None:
                node.resolved_type = self._infer_type(node)
        finally:
            self._node = previous
            self._parent = previous_parent

    def _validate_node(self, node: ASTNode) -> None:
        if node is None: return

        if isinstance(node, VarDecl):
            self._validate_type_name(node.type, node)
            self.validate_node(node.init_value)
            actual_type = self._infer_type(node.init_value)
            declared_type = actual_type if node.type == "var" and actual_type != "unknown" else node.type
            if node.type == 'task' and actual_type.startswith('task<'):
                declared_type = actual_type
            if actual_type == 'void':
                self._report(node.line, 'Valor void nao pode inicializar variavel.')
            if node.type == 'task' and not actual_type.startswith('task<'):
                self._report(node.line, 'Task deve ser inicializada por fork ou outro identificador de tarefa.')
            self._check_type(node.init_value or node, declared_type, actual_type, f"'{node.name}'")
            self._define_symbol(node.name, declared_type, node.line)
            node.symbol = self._lookup(node.name)
            if isinstance(node.init_value, ForkExpr): node.symbol.task_origin = node.init_value
        elif isinstance(node, Assignment):
            self._check_write(node, IdentifierExpr(node.name))
            sym = self._lookup(node.name)
            if sym is None:
                self._report(node.line, f"Variavel '{node.name}' nao declarada.")
            self.validate_node(node.value)
            if self._infer_type(node.value) == 'void':
                self._report(node.line, 'Valor void nao pode ser atribuido.')
            if sym:
                self._check_type(node.value, sym.type, self._infer_type(node.value), f"atribuicao de '{node.name}'")
            if sym and sym.type in ('var', 'unknown'):
                sym.type = self._infer_type(node.value)
            if sym and isinstance(node.value, ForkExpr): sym.task_origin = node.value
        elif isinstance(node, PrintStmt):
            for arg in node.arguments:
                self.validate_node(arg)
                if self._infer_type(arg) == 'void' or self._infer_type(arg).startswith('task<'):
                    self._report(arg.line, 'Print exige valor, nao void/identificador de tarefa.')
        elif isinstance(node, SendStmt):
            self.validate_node(node.channel)
            self.validate_node(node.message)
            self._check_type(node.channel, 'c_channel', self._infer_type(node.channel), 'canal de send')
            if self._infer_type(node.message) not in ('number', 'int', 'bool', 'string', 'var', 'unknown'):
                self._report(node.message.line, 'Send exige mensagem escalar (numero, bool ou string).')
        elif isinstance(node, CChannelExpr):
            self._endpoint(node, node.ip, node.port)
        elif isinstance(node, ReceiveExpr):
            self.validate_node(node.channel)
            self._check_type(node.channel, 'c_channel', self._infer_type(node.channel), 'canal de receive')
        elif isinstance(node, ForkExpr):
            node.argument_types = [self._infer_type(arg) for arg in node.arguments]
            node.result_type = self._infer_type(node)[5:-1]
            if not ((isinstance(self._parent, VarDecl) and self._parent.init_value is node) or
                    (isinstance(self._parent, Assignment) and self._parent.value is node)):
                self._report(node.line, 'Fork deve inicializar ou atribuir diretamente um identificador de tarefa.')
            self._forks.append(node)
            self._core_affinity(node)
            for arg in node.arguments:
                self.validate_node(arg)
                if self._infer_type(arg).startswith('task<') or self._infer_type(arg) == 'void':
                    self._report(arg.line, 'Fork nao aceita handle de tarefa ou void como argumento.')
            symbol = self._functions.get(node.function)
            binding = self._lookup(node.function)
            if binding and binding.type != 'FUNC':
                self._report(node.line, f"Alvo de fork '{node.function}' e sombreado por variavel.")
            if symbol is None:
                self._report(node.line, f"Fork exige funcao global declarada: '{node.function}'.")
            else:
                self._check_arguments(node, symbol, node.arguments, f"Fork '{node.function}'")
            if node.destination.kind == 'remote':
                self._endpoint(node.destination, node.destination.host, node.destination.port)
            elif node.destination.kind != 'local':
                self._report(node.line, 'Destino de fork invalido.')
        elif isinstance(node, JoinExpr):
            self.validate_node(node.task)
            symbol = self._lookup(node.task.name)
            if symbol and not symbol.type.startswith('task<'):
                self._report(node.line, f"Join exige identificador de tarefa compativel; '{node.task.name}' tem tipo {symbol.type}.")
        elif isinstance(node, ListLiteral):
            for e in node.elements:
                self.validate_node(e)
                if self._infer_type(e) == 'void' or self._infer_type(e).startswith('task<'):
                    self._report(e.line, 'Lista nao pode armazenar void/handle task.')
            known = {self._infer_type(e) for e in node.elements} - {'unknown', 'var'}
            if len(known - {'number', 'int'}) > 1 or (known & {'number', 'int'} and known - {'number', 'int'}):
                self._report(node.line, 'Lista exige elementos de tipos compativeis.')
        elif isinstance(node, MatrixCreateExpr):
            self.validate_node(node.rows)
            self.validate_node(node.cols)
            self.validate_node(node.init_value)
            for dimension in (node.rows, node.cols):
                self._check_type(dimension, 'number', self._infer_type(dimension), 'dimensao da matriz')
            if self._infer_type(node.init_value) == 'void' or self._infer_type(node.init_value).startswith('task<'):
                self._report(node.line, 'Matriz nao pode armazenar void/handle task.')
        elif isinstance(node, IndexExpr):
            self.validate_node(node.object)
            self.validate_node(node.index)
            self._check_type(node.index, 'number', self._infer_type(node.index), 'indice')
            if self._infer_type(node.object) not in ('list', 'matrix', 'string', 'unknown', 'var'):
                self._report(node.line, 'Indexacao exige lista, matriz ou string.')
        elif isinstance(node, IndexAssign):
            self._check_write(node, node.target)
            self.validate_node(node.target)
            self.validate_node(node.value)
        elif isinstance(node, IdentifierExpr):
            symbol = self._lookup(node.name)
            if symbol is None:
                self._report(node.line, f"Variavel '{node.name}' nao declarada.")
            elif symbol.type in ('CLASS', 'FUNC'):
                self._report(node.line, f"'{node.name}' nao e um valor de variavel.")
            elif self._current_callable and self._scopes[0].get(node.name) is symbol:
                self._current_callable.captures.add(node.name)
        elif isinstance(node, BinaryExpr):
            self.validate_node(node.left)
            self.validate_node(node.right)
            lt, rt = self._infer_type(node.left), self._infer_type(node.right)
            gradual, numeric = ('var', 'unknown'), ('number', 'int')
            if 'void' in (lt, rt) or any(t.startswith('task<') for t in (lt, rt)):
                self._report(node.line, 'Operador nao aceita void/identificador de tarefa.')
            elif node.op in ('+', '-', '*', '/', '%'):
                allowed_pair = node.op == '+' and lt == rt and lt in ('string', 'list')
                if not allowed_pair and (lt not in (*numeric, *gradual) or rt not in (*numeric, *gradual)):
                    self._report(node.line, f"Operador '{node.op}' exige operandos numericos ou '+' com duas strings/listas.")
            elif node.op in ('&&', '||'):
                if any(t not in ('bool', *numeric, *gradual) for t in (lt, rt)):
                    self._report(node.line, 'Operador logico exige bool ou numero.')
            elif not (self._types_compatible(lt, rt) or self._types_compatible(rt, lt)):
                self._report(node.line, 'Comparacao entre tipos incompativeis.')
        elif isinstance(node, UnaryExpr):
            self.validate_node(node.operand)
            allowed = ('number', 'int', 'var', 'unknown') + (('bool',) if node.op == '!' else ())
            if self._infer_type(node.operand) not in allowed:
                self._report(node.line, f"Operador unario '{node.op}' com tipo incompativel.")
        elif isinstance(node, SeqBlock):
            self._enter_scope()
            for stmt in node.statements: self.validate_node(stmt)
            self._exit_scope()
        elif isinstance(node, ParBlock):
            # Cada filho é uma tarefa: declarações não vazam entre irmãos.
            for stmt in node.statements:
                self._enter_scope()
                self._task_boundaries.append(len(self._scopes) - 1)
                old_loop = self._loop_depth
                self._loop_depth = 0
                self.validate_node(stmt)
                self._loop_depth = old_loop
                self._task_boundaries.pop()
                self._exit_scope()
        elif isinstance(node, IfStmt):
            self.validate_node(node.condition)
            self._condition(node.condition)
            for branch in (node.then_branch, node.else_branch):
                self._enter_scope()
                self.validate_node(branch)
                self._exit_scope()
        elif isinstance(node, WhileStmt):
            self.validate_node(node.condition)
            self._condition(node.condition)
            self._loop_depth += 1
            self._enter_scope()
            self.validate_node(node.body)
            self._exit_scope()
            self._loop_depth -= 1
        elif isinstance(node, DoWhileStmt):
            self._loop_depth += 1
            self._enter_scope()
            self.validate_node(node.body)
            self._exit_scope()
            self._loop_depth -= 1
            self.validate_node(node.condition)
            self._condition(node.condition)
        elif isinstance(node, ForStmt):
            self._enter_scope()
            if node.iterator_name:
                self.validate_node(node.iterable)
                if self._infer_type(node.iterable) not in ('list', 'matrix', 'string', 'var', 'unknown'):
                    self._report(node.line, 'For-in exige lista, matriz ou string.')
                self._define_symbol(node.iterator_name, "var", node.line)
            else:
                self.validate_node(node.initializer)
                self.validate_node(node.condition)
                if node.condition: self._condition(node.condition)
                self.validate_node(node.increment)
            self._loop_depth += 1
            self.validate_node(node.body)
            self._loop_depth -= 1
            self._exit_scope()
        elif isinstance(node, (BreakStmt, ContinueStmt)):
            if self._loop_depth == 0:
                self._report(node.line, f"'{node.__class__.__name__.replace('Stmt', '').lower()}' usado fora de laco.")
        elif isinstance(node, ClassDecl):
            if self._current_function or len(self._scopes) != 1:
                self._report(node.line, 'Classe deve ser declarada no escopo global.')
            if node.superclass and node.superclass not in self._classes:
                self._report(node.line, f"Superclasse '{node.superclass}' nao declarada.")
            self._define_symbol(node.name, "CLASS", node.line)
            self._enter_scope()
            old_class = self._current_class
            self._current_class = node.name
            for attr in node.attributes: self.validate_node(attr)
            for method in node.methods: self.validate_node(method)
            self._current_class = old_class
            self._exit_scope()
        elif isinstance(node, FuncDecl):
            if self._current_function:
                self._report(node.line, 'Funcoes aninhadas nao sao permitidas.')
            elif self._current_class is None and len(self._scopes) != 1:
                self._report(node.line, 'Funcao deve ser declarada no escopo global.')
            self._define_symbol(node.name, "FUNC", node.line, node.params)
            self._enter_scope()
            old_function = self._current_function
            old_callable, old_loop = self._current_callable, self._loop_depth
            self._current_function = node.name
            self._current_callable = self._member(self._current_class, node.name, methods=True) if self._current_class else self._functions.get(node.name)
            if self._current_class and node.name == 'init' and self._current_callable.return_type not in ('void','unknown','var'):
                self._report(node.line, 'Inicializador init deve retornar void.')
            self._loop_depth = 0
            for p, typ in zip(node.params, node.param_types or ['var'] * len(node.params)):
                self._validate_type_name(typ, node)
                if typ == 'task': self._report(node.line, 'Handle task nao pode ser parametro; use argumentos por valor/canais.')
                self._define_symbol(p, typ, node.line)
            if node.return_type:
                self._validate_type_name(node.return_type, node, allow_void=True)
            returns = [n for n in walk(node.body) if isinstance(n, ReturnStmt)]
            if node.return_type and node.return_type != 'void' and not self._always_returns(node.body):
                self._report(node.line, f"Funcao '{node.name}' deve retornar {node.return_type} em todos os caminhos.")
            self.validate_node(node.body)
            known_returns = {self._infer_return_in_context(n) for n in returns}
            known_returns -= {'unknown', 'var'}
            if len(known_returns) > 1 and not known_returns <= {'number', 'int'}:
                self._report(node.line, f"Retornos incompativeis em '{node.name}': {sorted(known_returns)}.")
            self._current_function = old_function
            self._current_callable, self._loop_depth = old_callable, old_loop
            self._exit_scope()
        elif isinstance(node, ReturnStmt):
            if self._task_boundaries:
                self._report(node.line, 'return nao pode sair de tarefa PAR inline; use funcao com fork/join.')
            if node.value: self.validate_node(node.value)
            actual = self._infer_type(node.value) if node.value else 'void'
            node.inferred_return_type = actual
            if not self._current_function:
                self._report(node.line, 'return usado fora de funcao/metodo.')
            elif self._current_callable:
                self._check_type(node, self._current_callable.return_type, actual, 'retorno')
            if actual.startswith('task<'):
                self._report(node.line, 'Handle task nao pode escapar por return.')
        elif isinstance(node, MethodCall):
            obj_type = self._infer_type(node.object)
            cls = self._classes.get(obj_type)
            symbol = self._member(obj_type, node.method_name, methods=True)
            if cls and symbol is None:
                self._report(node.line, f"Metodo '{node.method_name}' nao declarado em '{obj_type}'.")
            elif symbol:
                self._check_arguments(node, symbol, node.arguments, f"Metodo '{node.method_name}'")
                self._check_write(node, node.object)
            elif obj_type in ('list', 'matrix', 'string'):
                arities = {'size': 0}
                if obj_type in ('list', 'matrix'): arities.update(append=1, push_back=1, pop=0, clear=0)
                if node.method_name not in arities or len(node.arguments) != arities[node.method_name]:
                    self._report(node.line, f"Chamada de metodo '{node.method_name}' invalida para {obj_type}.")
                if node.method_name in ('append', 'push_back', 'pop', 'clear'):
                    self._check_write(node, node.object)
            elif obj_type not in ('var', 'unknown'):
                self._report(node.line, f"Tipo '{obj_type}' nao possui metodos.")
            elif self._current_callable:
                self._current_callable.unresolved_methods = True
            self.validate_node(node.object)
            for arg in node.arguments: self.validate_node(arg)
        elif isinstance(node, FuncCallExpr):
            binding = self._lookup(node.name)
            if binding and binding.type != 'FUNC':
                self._report(node.line, f"'{node.name}' nao e funcao neste escopo.")
            if node.name not in self._functions and node.name not in BUILTINS:
                self._report(node.line, f"Funcao '{node.name}' nao declarada.")
            elif node.name in self._functions and len(self._functions[node.name].params) != len(node.arguments):
                self._report(node.line, f"Funcao '{node.name}' espera {len(self._functions[node.name].params)} argumento(s), recebeu {len(node.arguments)}.")
            for arg in node.arguments: self.validate_node(arg)
            if node.name in self._functions:
                if len(self._functions[node.name].params) == len(node.arguments):
                    self._check_arguments(node, self._functions[node.name], node.arguments, f"Funcao '{node.name}'")
            elif node.name in BUILTINS:
                self._check_builtin(node)
        elif isinstance(node, PropertyAccess):
            self.validate_node(node.object)
            obj_type = self._infer_type(node.object)
            cls = self._classes.get(obj_type)
            if cls and self._member(obj_type, node.property_name) is None:
                self._report(node.line, f"Atributo '{node.property_name}' nao declarado em '{obj_type}'.")
            elif not cls and obj_type not in ('var', 'unknown') and not (node.property_name == 'size' and obj_type in ('list', 'matrix', 'string')):
                self._report(node.line, f"Acesso de atributo invalido para '{obj_type}'.")
        elif isinstance(node, PropertyAssign):
            self._check_write(node, node.object)
            self.validate_node(node.object)
            self.validate_node(node.value)
            obj_type = self._infer_type(node.object)
            cls = self._classes.get(obj_type)
            if cls and self._member(obj_type, node.property_name) is None:
                self._report(node.line, f"Atributo '{node.property_name}' nao declarado em '{obj_type}'.")
            elif cls:
                self._check_type(node, self._member(obj_type, node.property_name), self._infer_type(node.value), 'atribuicao de atributo')
            elif obj_type not in ('var', 'unknown'):
                self._report(node.line, 'Atribuicao de atributo exige objeto.')
        elif isinstance(node, NewExpr):
            if node.class_name not in self._classes:
                self._report(node.line, f"Classe '{node.class_name}' nao declarada.")
            for arg in node.arguments: self.validate_node(arg)
            initializer = self._member(node.class_name, 'init', methods=True)
            if initializer:
                self._check_arguments(node, initializer, node.arguments, f"Construtor '{node.class_name}'")
                if initializer.return_type not in ('void', 'unknown', 'var'):
                    self._report(node.line, 'Inicializador init deve retornar void.')
            elif node.arguments:
                self._report(node.line, 'Construtor padrao nao recebe argumentos; inicialize por metodos.')
        elif isinstance(node, ThisExpr):
            if not self._current_class or not self._current_function:
                self._report(node.line, 'this usado fora de metodo de classe.')
        elif isinstance(node, InputExpr):
            if node.prompt:
                self.validate_node(node.prompt)
                self._check_type(node.prompt, 'string', self._infer_type(node.prompt), 'prompt de input')

    def _condition(self, node):
        if self._infer_type(node) not in ('bool', 'number', 'int', 'var', 'unknown'):
            self._report(node.line, 'Condicao exige bool ou numero.')

    def _infer_return_in_context(self, node):
        return getattr(node, 'inferred_return_type', 'unknown')

    def _always_returns(self, node):
        if isinstance(node, ReturnStmt): return True
        if isinstance(node, SeqBlock): return any(self._always_returns(s) for s in node.statements)
        if isinstance(node, IfStmt):
            return node.else_branch is not None and self._always_returns(node.then_branch) and self._always_returns(node.else_branch)
        return False

    def analyze(self, program: Program) -> bool:
        self.__init__()
        self._collect_declarations(program)
        self._infer_signatures()
        self._capture_scopes = True
        for name in self._classes:
            seen, current = set(), name
            while current in self._classes:
                if current in seen:
                    self._report(1, f"Ciclo de heranca envolvendo '{name}'.")
                    break
                seen.add(current)
                current = self._classes[current].superclass
        for stmt in program.statements: self.validate_node(stmt)
        # Fecho transitivo: um helper também não pode capturar estado global.
        independent = [(node, node.function) for node in self._forks] + self._independent_calls
        for origin, function in independent:
            pending, seen, captures = [function], set(), set()
            unresolved = False
            while pending:
                name = pending.pop()
                if name in seen: continue
                seen.add(name)
                symbol = self._callables.get(name)
                if symbol:
                    captures.update(symbol.captures)
                    pending.extend(symbol.calls)
                    unresolved = unresolved or symbol.unresolved_methods
            if captures:
                self._node = origin
                self._report(origin.line, f"Tarefa independente captura estado global {sorted(captures)}; passe argumentos/canais explicitamente.")
            if unresolved:
                self._node = origin
                self._report(origin.line, 'Tarefa independente chama metodo com receptor de tipo desconhecido; anote o parametro para validar isolamento.')
        self._node = None
        return not self._has_errors
