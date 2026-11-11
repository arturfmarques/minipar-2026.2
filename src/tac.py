from __future__ import annotations
import os
import json
from typing import Optional
from ast_nodes import (
    ASTNode, Program, VarDecl, Assignment, PrintStmt, SeqBlock, ParBlock, BinaryExpr,
    UnaryExpr, NumberExpr, StringExpr, BoolExpr, IdentifierExpr, IfStmt, WhileStmt,
    DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, InputExpr,
    ClassDecl, FuncDecl, ReturnStmt, MethodCall, FuncCallExpr, PropertyAccess, PropertyAssign, NewExpr, ThisExpr,
    CChannelExpr, SendStmt, ReceiveExpr, ListLiteral, MatrixCreateExpr, IndexExpr, IndexAssign,
    ForkExpr, JoinExpr, walk
)


class TACGenerator:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.temp_count = 0
        self.label_count = 0
        self.break_stack: list[str] = []
        self.continue_stack: list[str] = []
        self.current_class: Optional[str] = None
        self.scopes: list[dict[str, str]] = [{}]
        self.scope_ids = [0]
        self.scope_count = 0
        self.reserved: set[str] = set()
        self.classes: dict[str, ClassDecl] = {}

    def _temp(self) -> str:
        name = f"t{self.temp_count}"
        self.temp_count += 1
        while name in self.reserved:
            name = f't{self.temp_count}'
            self.temp_count += 1
        return name

    def _name(self, name):
        return next((scope[name] for scope in reversed(self.scopes) if name in scope), name)

    def _declare(self, name):
        symbol = name if self.scope_ids[-1] == 0 else f'{name}@S{self.scope_ids[-1]}'
        self.scopes[-1][name] = symbol
        return symbol

    def _enter_scope(self):
        self.scope_count += 1
        self.scope_ids.append(self.scope_count)
        self.scopes.append({})
        self._emit('scope_begin')

    def _exit_scope(self):
        self._emit('scope_end')
        self.scopes.pop()
        self.scope_ids.pop()

    def _branch(self, statement):
        self._enter_scope()
        self._stmt(statement)
        self._exit_scope()

    def _label(self, prefix: str) -> str:
        name = f"{prefix}_{self.label_count}"
        self.label_count += 1
        return name

    def _emit(self, line: str = "") -> None:
        self.lines.append(line)

    def _expr(self, node: Optional[ASTNode]) -> str:
        if node is None: return "0"
        if isinstance(node, NumberExpr): return node.value
        if isinstance(node, StringExpr): return json.dumps(node.value, ensure_ascii=False)
        if isinstance(node, BoolExpr): return "true" if node.value else "false"
        if isinstance(node, IdentifierExpr): return self._name(node.name)
        if isinstance(node, ThisExpr): return "this"
        if isinstance(node, UnaryExpr):
            value = self._expr(node.operand)
            tmp = self._temp()
            self._emit(f"{tmp} = {node.op}{value}")
            return tmp
        if isinstance(node, BinaryExpr):
            if node.op in ('&&', '||'):
                result, end = self._temp(), self._label('LOGIC_END')
                self._emit(f"{result} = {'false' if node.op == '&&' else 'true'}")
                branch = 'ifFalse' if node.op == '&&' else 'if'
                self._emit(f"{branch} {self._expr(node.left)} goto {end}")
                self._emit(f"{branch} {self._expr(node.right)} goto {end}")
                self._emit(f"{result} = {'true' if node.op == '&&' else 'false'}")
                self._emit(f'{end}:')
                return result
            left = self._expr(node.left)
            right = self._expr(node.right)
            tmp = self._temp()
            self._emit(f"{tmp} = {left} {node.op} {right}")
            return tmp
        if isinstance(node, ListLiteral):
            tmp = self._temp()
            values = ", ".join(self._expr(e) for e in node.elements)
            self._emit(f"{tmp} = [{values}]")
            return tmp
        if isinstance(node, MatrixCreateExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = matrix({self._expr(node.rows)}, {self._expr(node.cols)}, {self._expr(node.init_value)})")
            return tmp
        if isinstance(node, IndexExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = {self._expr(node.object)}[{self._expr(node.index)}]")
            return tmp
        if isinstance(node, PropertyAccess):
            tmp = self._temp()
            self._emit(f"{tmp} = {self._expr(node.object)}.{node.property_name}")
            return tmp
        if isinstance(node, (FuncCallExpr, MethodCall)):
            receiver = self._method_receiver(node.object) if isinstance(node, MethodCall) else None
            args = self._arguments(node.arguments)
            for value in args:
                self._emit(f"param {value}")
            tmp = self._temp()
            if receiver is not None:
                self._emit(f"{tmp} = callmethod {receiver}, {node.method_name}, {len(args)}")
            else:
                self._emit(f"{tmp} = call {node.name}, {len(args)}")
            return tmp
        if isinstance(node, NewExpr):
            args = self._arguments(node.arguments)
            for value in args: self._emit(f'param {value}')
            tmp = self._temp()
            self._emit(f"{tmp} = new {node.class_name}, {len(args)}")
            return tmp
        if isinstance(node, ForkExpr):
            destination = node.destination.kind
            if destination == 'remote':
                host, port = self._snapshot(node.destination.host), self._snapshot(node.destination.port)
                destination = f'remote({host}, {port})'
            args = self._arguments(node.arguments)
            if node.destination.core is not None:
                destination += f' on core({self._snapshot(node.destination.core)})'
            for value in args: self._emit(f'task_param_copy {value}')
            tmp = self._temp()
            self._emit(f'{tmp} = fork {destination}, {node.function}, {len(args)}')
            return tmp
        if isinstance(node, JoinExpr):
            tmp = self._temp()
            self._emit(f'{tmp} = join {self._name(node.task.name)}')
            return tmp
        if isinstance(node, CChannelExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = c_channel({self._expr(node.ip)}, {self._expr(node.port)})")
            return tmp
        if isinstance(node, ReceiveExpr):
            tmp = self._temp()
            self._emit(f"{tmp} = receive {self._expr(node.channel)}")
            return tmp
        if isinstance(node, InputExpr):
            tmp = self._temp()
            if node.prompt:
                self._emit(f"{tmp} = input({self._expr(node.prompt)})")
            else:
                self._emit(f"{tmp} = input()")
            return tmp
        raise TypeError(f'Expressao sem lowering TAC: {type(node).__name__}')

    def _snapshot(self, node):
        value, temporary = self._expr(node), self._temp()
        self._emit(f'{temporary} = {value}')
        return temporary

    def _arguments(self, arguments):
        # Materializa antes de emitir params: chamadas aninhadas não corrompem a lista externa.
        return [self._snapshot(argument) for argument in arguments]

    def _reference(self, node):
        if isinstance(node, (IndexExpr, PropertyAccess)):
            address, reference = self._address(node), self._temp()
            self._emit(f'{reference} = load_ref {address}')
            return reference
        return self._expr(node)

    def _method_receiver(self, node):
        # append/pop/clear e metodos devem atuar sobre a colecao/objeto original.
        # Uma atribuicao TAC comum e copia de valor, como nas variaveis C++.
        if isinstance(node, IdentifierExpr):
            reference = self._temp()
            self._emit(f'{reference} = ref {self._name(node.name)}')
            return reference
        return self._reference(node)

    def _address(self, target):
        base = self._reference(target.object)
        address = self._temp()
        if isinstance(target, IndexExpr):
            self._emit(f'{address} = index_addr {base}, {self._expr(target.index)}')
        else:
            self._emit(f'{address} = field_addr {base}, {target.property_name}')
        return address

    def _stmt(self, node: Optional[ASTNode]) -> None:
        if node is None: return
        if isinstance(node, VarDecl):
            value = self._expr(node.init_value)
            self._emit(f"{self._declare(node.name)} = {value}")
        elif isinstance(node, Assignment):
            self._emit(f"{self._name(node.name)} = {self._expr(node.value)}")
        elif isinstance(node, PropertyAssign):
            address = self._address(PropertyAccess(node.object, node.property_name))
            self._emit(f'store {address}, {self._expr(node.value)}')
        elif isinstance(node, IndexAssign):
            address = self._address(node.target)
            self._emit(f'store {address}, {self._expr(node.value)}')
        elif isinstance(node, PrintStmt):
            for arg in node.arguments:
                self._emit(f"print {self._expr(arg)}")
        elif isinstance(node, SendStmt):
            self._emit(f"send {self._expr(node.channel)}, {self._expr(node.message)}")
        elif isinstance(node, SeqBlock):
            self._enter_scope()
            for stmt in node.statements: self._stmt(stmt)
            self._exit_scope()
        elif isinstance(node, ParBlock):
            barrier = self._label('PAR_JOIN')
            tasks = [(self._temp(), self._label('TASK'), child) for child in node.statements]
            self._emit('par_begin')
            for handle, entry, _ in tasks: self._emit(f'{handle} = spawn {entry}, copy_readonly_environment')
            self._emit(f'goto {barrier}')
            for _, entry, child in tasks:
                self._emit(f'{entry}:')
                old_break, old_continue = self.break_stack, self.continue_stack
                self.break_stack, self.continue_stack = [], []
                self._branch(child)
                self._emit('task_return')
                self.break_stack, self.continue_stack = old_break, old_continue
            self._emit(f'{barrier}:')
            for handle, _, _ in tasks: self._emit(f'join {handle}')
            self._emit('par_end')
        elif isinstance(node, IfStmt):
            end = self._label("ENDIF")
            else_label = self._label("ELSE") if node.else_branch else end
            self._emit(f"ifFalse {self._expr(node.condition)} goto {else_label}")
            self._branch(node.then_branch)
            if node.else_branch:
                self._emit(f"goto {end}")
                self._emit(f"{else_label}:")
                self._branch(node.else_branch)
            self._emit(f"{end}:")
        elif isinstance(node, WhileStmt):
            start, end = self._label("WHILE"), self._label("ENDWHILE")
            self.break_stack.append(end); self.continue_stack.append(start)
            self._emit(f"{start}:")
            self._emit(f"ifFalse {self._expr(node.condition)} goto {end}")
            self._branch(node.body)
            self._emit(f"goto {start}")
            self._emit(f"{end}:")
            self.break_stack.pop(); self.continue_stack.pop()
        elif isinstance(node, DoWhileStmt):
            start, check, end = self._label("DO"), self._label('DO_CHECK'), self._label("ENDDO")
            self.break_stack.append(end); self.continue_stack.append(check)
            self._emit(f"{start}:")
            self._branch(node.body)
            self._emit(f'{check}:')
            self._emit(f"if {self._expr(node.condition)} goto {start}")
            self._emit(f"{end}:")
            self.break_stack.pop(); self.continue_stack.pop()
        elif isinstance(node, ForStmt):
            self._enter_scope()
            if node.iterator_name:
                collection, iterator = self._snapshot(node.iterable), self._temp()
                self._emit(f'{iterator} = iter {collection}')
                start, end = self._label('FOR_IN'), self._label('END_FOR_IN')
                self.break_stack.append(end); self.continue_stack.append(start)
                self._emit(f'{start}:')
                has_next = self._temp()
                self._emit(f'{has_next} = iter_has_next {iterator}')
                self._emit(f'ifFalse {has_next} goto {end}')
                self._emit(f'{self._declare(node.iterator_name)} = iter_next {iterator}')
                self._branch(node.body)
                self._emit(f'goto {start}')
                self._emit(f'{end}:')
                self.break_stack.pop(); self.continue_stack.pop()
                self._exit_scope()
                return
            start, step, end = self._label("FOR"), self._label("FOR_STEP"), self._label("ENDFOR")
            self._stmt(node.initializer)
            self.break_stack.append(end); self.continue_stack.append(step)
            self._emit(f"{start}:")
            if node.condition:
                self._emit(f"ifFalse {self._expr(node.condition)} goto {end}")
            self._branch(node.body)
            self._emit(f"{step}:")
            self._stmt(node.increment)
            self._emit(f"goto {start}")
            self._emit(f"{end}:")
            self.break_stack.pop(); self.continue_stack.pop()
            self._exit_scope()
        elif isinstance(node, BreakStmt):
            if not self.break_stack: raise ValueError('break sem laco na AST')
            self._emit(f"goto {self.break_stack[-1]}")
        elif isinstance(node, ContinueStmt):
            if not self.continue_stack: raise ValueError('continue sem laco na AST')
            self._emit(f"goto {self.continue_stack[-1]}")
        elif isinstance(node, ReturnStmt):
            self._emit(f"return {self._expr(node.value)}" if node.value else "return")
        elif isinstance(node, (FuncCallExpr, MethodCall, JoinExpr)):
            self._expr(node)
        elif isinstance(node, (NumberExpr, StringExpr, BoolExpr, IdentifierExpr, BinaryExpr, UnaryExpr,
                               NewExpr, ThisExpr, CChannelExpr, ReceiveExpr, InputExpr, ListLiteral,
                               MatrixCreateExpr, IndexExpr, PropertyAccess)):
            self._expr(node)  # Expressões nos cabeçalhos de for.
        elif isinstance(node, ClassDecl):
            self._emit(f"class {node.name}" + (f' extends {node.superclass}' if node.superclass else ''))
            previous = self.current_class
            self.current_class = node.name
            for attribute in node.attributes:
                self._emit(f'field {attribute.name}: {attribute.type} = {self._expr(attribute.init_value)}')
            for method in node.methods: self._stmt(method)
            self.current_class = previous
            self._emit(f'endclass {node.name}')
        elif isinstance(node, FuncDecl):
            qualified = f'{self.current_class}.{node.name}' if self.current_class else node.name
            self._emit(f"func {qualified}:")
            self._enter_scope()
            current, seen = self.current_class, set()
            while current in self.classes and current not in seen:
                seen.add(current)
                cls = self.classes[current]
                for attribute in cls.attributes:
                    self.scopes[-1].setdefault(attribute.name, f'this.{attribute.name}')
                current = cls.superclass
            if self.current_class: self._emit('arg this')
            for name, typ in zip(node.params, node.param_types or ['var'] * len(node.params)):
                self.scopes[-1][name] = name
                self._emit(f'arg {name}: {typ}')
            if node.return_type: self._emit(f'returns {node.return_type}')
            self._stmt(node.body)
            self._exit_scope()
            self._emit(f"endfunc {qualified}")
        else:
            raise TypeError(f'Instrucao sem lowering TAC: {type(node).__name__}')

    def generate_text(self, program: Program) -> str:
        self.__init__()
        self.classes = {node.name: node for node in program.statements if isinstance(node, ClassDecl)}
        self.reserved = {node.name for node in walk(program) if isinstance(node, (IdentifierExpr, VarDecl))}
        for node in walk(program):
            if isinstance(node, FuncDecl): self.reserved.update(node.params)
        for stmt in program.statements:
            self._stmt(stmt)
        return "\n".join(self.lines) + ("\n" if self.lines else "")

    def generate(self, program: Program, output_name: str) -> str:
        os.makedirs("output", exist_ok=True)
        tac_path = os.path.join("output", f"{output_name}.tac")
        text = self.generate_text(program)
        with open(tac_path, "w", encoding="utf-8") as f:
            f.write(text)
        return tac_path
