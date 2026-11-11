from __future__ import annotations
import os
import sys
from pathlib import Path
import hashlib
from typing import Optional
from ast_nodes import (
    ASTNode, Program, VarDecl, Assignment, PrintStmt, SeqBlock, ParBlock, BinaryExpr, 
    UnaryExpr, NumberExpr, StringExpr, BoolExpr, IdentifierExpr, IfStmt, WhileStmt,
    DoWhileStmt, ForStmt, BreakStmt, ContinueStmt, InputExpr,
    ClassDecl, FuncDecl, ReturnStmt, MethodCall, FuncCallExpr, PropertyAccess, PropertyAssign, NewExpr, ThisExpr,
    CChannelExpr, SendStmt, ReceiveExpr, ListLiteral, MatrixCreateExpr, IndexExpr, IndexAssign
)
from cpp_template import _CPP_HEADER
from toolchain import ToolchainError, compile_cpp, executable_suffix
from diagnostics import BackendUnsupportedError, CompilerError
from native_builtins import BUILTINS
from ast_nodes import ForkExpr, JoinExpr, walk

class CppCodeGenerator:
    def __init__(self, semantic=None):
        self.semantic = semantic
        self._provided_semantic = semantic is not None
        self.program_id = ''
        self.this_alias = 'this'
        self.classes = {}

    def _cpp_type(self, name):
        types = {'number':'double','int':'std::int64_t','string':'std::string','bool':'bool',
                 'list':'std::vector<double>','matrix':'std::vector<std::vector<double>>',
                 'c_channel':'std::shared_ptr<MiniParChannel>','void':'void'}
        if name in types: return types[name]
        if name in self.classes: return f'std::shared_ptr<{name}>'
        return None

    def _function_return(self, node, cls=None):
        symbol = None
        if self.semantic:
            symbol = self.semantic._member(cls,node.name,methods=True) if cls else self.semantic._functions.get(node.name)
        name = node.return_type or (symbol.return_type if symbol else None)
        # matrix pode conter números ou strings; a dedução C++ conserva o elemento.
        if name in ('list', 'matrix') and not node.return_type:
            return 'auto'  # preserva listas de strings/objetos e matrizes concretas
        return (self._cpp_type(name) if name != 'matrix' else None) or self._return_type(node.body)

    def _function_params(self, node):
        return ', '.join(f'{self._cpp_type(typ) or "auto"} {name}' for name,typ in
                         zip(node.params,node.param_types or ['var']*len(node.params)))

    def _callable(self, name):
        return f'[](auto... __mp_values) {{ return {name}(__mp_values...); }}'

    def _all_attributes(self, name):
        result = []
        seen = set()
        while name in self.classes and name not in seen:
            seen.add(name)
            node = self.classes[name]
            result.extend(a.name for a in node.attributes if a.name not in result)
            name = node.superclass
        return result

    def _ordered_functions(self, program):
        functions = {n.name:n for n in program.statements if isinstance(n,FuncDecl)}
        ordered, visited = [], set()
        def visit(name):
            if name in visited: return
            visited.add(name)
            function = functions[name]
            for child in walk(function.body):
                dependency = child.name if isinstance(child,FuncCallExpr) else (child.function if isinstance(child,ForkExpr) else None)
                if dependency in functions: visit(dependency)
            ordered.append(function)
        for name in functions: visit(name)
        return ordered

    def _ordered_classes(self):
        ordered,visited=[],set()
        def visit(name):
            if name in visited: return
            visited.add(name)
            node=self.classes[name]
            if node.superclass in self.classes: visit(node.superclass)
            ordered.append(node)
        for name in self.classes: visit(name)
        return ordered

    def _free_variables(self, statement):
        free = set()
        def visit(node, bound):
            if node is None: return
            if isinstance(node, IdentifierExpr):
                if node.name not in bound: free.add(node.name)
                return
            if isinstance(node, JoinExpr):
                visit(node.task,bound); return
            if isinstance(node, SeqBlock):
                local = set(bound)
                for child in node.statements:
                    visit(child,local)
                    if isinstance(child,VarDecl): local.add(child.name)
                return
            if isinstance(node, VarDecl): visit(node.init_value,bound); return
            if isinstance(node, ForStmt):
                local = set(bound)
                visit(node.initializer,local); visit(node.iterable,local)
                if isinstance(node.initializer,VarDecl): local.add(node.initializer.name)
                if node.iterator_name: local.add(node.iterator_name)
                for child in (node.condition,node.increment,node.body): visit(child,local)
                return
            from dataclasses import fields
            for member in fields(node):
                value = getattr(node,member.name)
                if isinstance(value,ASTNode): visit(value,bound)
                elif isinstance(value,list):
                    for child in value:
                        if isinstance(child,ASTNode): visit(child,set(bound))
        visit(statement,set())
        return free

    def _registry(self, program):
        entries = {}
        for node in walk(program):
            if not isinstance(node,ForkExpr) or node.destination.kind != 'remote': continue
            argument_types = getattr(node,'argument_types',[])
            supported = {'number','int','bool','string','list','matrix','c_channel'}
            if any(t not in supported for t in argument_types):
                raise BackendUnsupportedError('Argumento remoto exige tipo serializavel conhecido (numero/bool/string/lista/matriz/canal)',node.line,node.col)
            if getattr(node,'result_type','unknown') in self.classes:
                raise BackendUnsupportedError('Objetos remotos ainda nao possuem codec; use dados escalares/colecoes',node.line,node.col)
            types = tuple(self._cpp_type(t) for t in argument_types)
            entries[(node.function,types)] = node
        code = '\nmp::Registry __mp_registry() {\n    mp::Registry registry;\n'
        for (name,types),node in sorted(entries.items()):
            parameters = ', '.join(f'{typ} a{i}' for i,typ in enumerate(types))
            arguments = ', '.join(f'a{i}' for i in range(len(types)))
            template_types = ', '.join(types)
            code += f'    registry.emplace(mp::rpc_key("{name}", mp::type_list<{template_types}>()), mp::bind_rpc<{template_types}>([]({parameters}) {{ return {name}({arguments}); }}));\n'
        return code + '    return registry;\n}\n'

    def _fork_expression(self, node):
        values = ', '.join(self._translate_expression(arg) for arg in node.arguments)
        function = self._callable(node.function)
        if node.destination.kind == 'local':
            if node.destination.core is not None:
                arguments = ', '.join([self._translate_expression(arg) for arg in node.arguments]
                                      + [self._translate_expression(node.destination.core)])
                return f'mp::fork_local_on("{node.function}", {function}, std::tuple{{{arguments}}})'
            return f'mp::fork_local("{node.function}", {function}, std::tuple{{{values}}})'
        host = self._translate_expression(node.destination.host)
        port = self._translate_expression(node.destination.port)
        # A lista braced é avaliada da esquerda para a direita antes de iniciar a tarefa.
        arguments = ', '.join([host,port] + [self._translate_expression(a) for a in node.arguments])
        return f'mp::fork_remote(__mp_program_id, "{node.function}", {function}, std::tuple{{{arguments}}})'

    @staticmethod
    def _escape_string(value: str) -> str:
        res = []
        for ch in value:
            if ch == "\n": res.append("\\n")
            elif ch == "\t": res.append("\\t")
            elif ch == '"': res.append('\\"')
            elif ch == "\\": res.append("\\\\")
            else: res.append(ch)
        return "".join(res)

    @staticmethod
    def _integer_operand(node):
        if getattr(node, 'resolved_type', '') == 'int': return True
        if isinstance(node, NumberExpr): return node.value.isdigit()
        return isinstance(node, UnaryExpr) and node.op in ('+', '-') and CppCodeGenerator._integer_operand(node.operand)

    def _integer_expression(self, node):
        literal = self.semantic._numeric_literal(node)
        if literal is not None and literal == literal.to_integral_value() and -(2**63) <= literal < 2**63:
            value = int(literal)
            return '(-9223372036854775807LL - 1)' if value == -(2**63) else f'std::int64_t{{{value}LL}}'
        if isinstance(node, BinaryExpr) and node.op in ('+', '-', '*', '%') and all(self._integer_operand(n) for n in (node.left, node.right)):
            operation = {'+':'add', '-':'sub', '*':'mul', '%':'mod'}[node.op]
            return f'__minipar_int_{operation}({self._integer_expression(node.left)}, {self._integer_expression(node.right)})'
        if isinstance(node, UnaryExpr) and node.op == '-' and self._integer_operand(node.operand):
            return f'__minipar_int_sub(0, {self._integer_expression(node.operand)})'
        return f'__minipar_int({self._translate_expression(node, convert_int=False)})'

    def _translate_expression(self, node: Optional[ASTNode], convert_int=True) -> str:
        if node is not None and convert_int and (getattr(node, 'int_conversion', False) or
                (isinstance(node, (BinaryExpr, UnaryExpr)) and getattr(node, 'resolved_type', '') == 'int')):
            return self._integer_expression(node)
        if node is None: return "0"
        if isinstance(node, NumberExpr):
            # number nao herda divisao/overflow de int dos literais C++.
            return node.value if any(c in node.value for c in '.eE') else node.value + '.0'
        if isinstance(node, StringExpr): return f'std::string("{self._escape_string(node.value)}")'
        if isinstance(node, BoolExpr): return "true" if node.value else "false"
        if isinstance(node, IdentifierExpr): return node.name
        if isinstance(node, UnaryExpr): return f"({node.op}{self._translate_expression(node.operand)})"
        if isinstance(node, BinaryExpr):
            if node.op in ('==', '!=', '<', '<=', '>', '>=') and any(getattr(n, 'resolved_type', '') == 'int' for n in (node.left, node.right)) and all(self._integer_operand(n) for n in (node.left, node.right)):
                return f'({self._integer_expression(node.left)} {node.op} {self._integer_expression(node.right)})'
            if node.op == '/':
                return f'__minipar_div({self._translate_expression(node.left)}, {self._translate_expression(node.right)})'
            if node.op == '%':
                return f'__minipar_mod({self._translate_expression(node.left)}, {self._translate_expression(node.right)})'
            return f"({self._translate_expression(node.left)} {node.op} {self._translate_expression(node.right)})"
        if isinstance(node, ForkExpr): return self._fork_expression(node)
        if isinstance(node, JoinExpr): return f'mp::join({node.task.name})'
        
        if isinstance(node, NewExpr):
            args = ", ".join(self._translate_expression(a) for a in node.arguments)
            return f"__minipar_new<{node.class_name}>({args})"
        if isinstance(node, ThisExpr): return self.this_alias
        if isinstance(node, PropertyAccess):
            if node.property_name == "size": return f"static_cast<double>({self._translate_expression(node.object)}.size())"
            return f"{self._translate_expression(node.object)}->{node.property_name}"
        
        if isinstance(node, MethodCall):
            args = ", ".join(self._translate_expression(a) for a in node.arguments)
            m_name = node.method_name
            if m_name in ("append", "push_back"): return f"{self._translate_expression(node.object)}.push_back({args})"
            if m_name == "pop": return f"__array_pop({self._translate_expression(node.object)})"
            if m_name == "clear": return f"{self._translate_expression(node.object)}.clear()"
            if m_name == "size": return f"static_cast<double>({self._translate_expression(node.object)}.size())"
            return f"{self._translate_expression(node.object)}->{m_name}({args})"
        
        if isinstance(node, FuncCallExpr):
            args = ", ".join(self._translate_expression(a) for a in node.arguments)
            if node.name in BUILTINS and BUILTINS[node.name].cpp:
                return f'{BUILTINS[node.name].cpp}({args})'
            if node.name == "exp":
                return f"std::exp({args})"
            if node.name == "random":
                return "random_val()"
            if node.name == "len":
                return f"static_cast<double>({self._translate_expression(node.arguments[0])}.size())"
            if node.name == "range":
                return f"__minipar_range({args})"
            if node.name == "to_number":
                return f"std::stod({args})"
            if node.name == "parse_ints":
                return f"__parse_ints({args})"
            return f"{node.name}({args})"

        if isinstance(node, CChannelExpr):
            ip = self._translate_expression(node.ip)
            port = self._translate_expression(node.port)
            return f"std::make_shared<MiniParChannel>({ip}, {port})"
        if isinstance(node, ReceiveExpr):
            return f"{self._translate_expression(node.channel)}->receiveData()"
        if isinstance(node, InputExpr):
            if node.prompt:
                return f"input({self._translate_expression(node.prompt)})"
            return "input()"

        if isinstance(node, ListLiteral):
            elems = ", ".join(self._translate_expression(e) for e in node.elements)
            return f"__minipar_list({elems})"
        if isinstance(node, MatrixCreateExpr):
            r = self._translate_expression(node.rows)
            c = self._translate_expression(node.cols)
            v = self._translate_expression(node.init_value)
            return f"__make_matrix({r}, {c}, {v})"
        if isinstance(node, IndexExpr):
            obj = self._translate_expression(node.object)
            idx = self._translate_expression(node.index)
            return f"__minipar_at({obj}, {idx}, {node.line}, {node.col})"

        return "0"

    def _has_value_return(self, node: Optional[ASTNode]) -> bool:
        if node is None: return False
        if isinstance(node, ReturnStmt): return node.value is not None
        if isinstance(node, (SeqBlock, ParBlock)):
            return any(self._has_value_return(stmt) for stmt in node.statements)
        if isinstance(node, IfStmt):
            return self._has_value_return(node.then_branch) or self._has_value_return(node.else_branch)
        if isinstance(node, (WhileStmt, DoWhileStmt, ForStmt)):
            return self._has_value_return(node.body)
        return False

    def _uses_float_return(self, node: Optional[ASTNode]) -> bool:
        """Detecta aritmética de ponto flutuante no corpo da função."""
        if node is None:
            return False
        if isinstance(node, BinaryExpr):
            if node.op == "/":
                return True
            return self._uses_float_return(node.left) or self._uses_float_return(node.right)
        if isinstance(node, NumberExpr):
            return "." in node.value
        if isinstance(node, (SeqBlock, ParBlock)):
            return any(self._uses_float_return(stmt) for stmt in node.statements)
        if isinstance(node, IfStmt):
            return self._uses_float_return(node.then_branch) or self._uses_float_return(node.else_branch)
        if isinstance(node, (WhileStmt, DoWhileStmt, ForStmt)):
            return self._uses_float_return(node.body)
        if isinstance(node, ReturnStmt):
            return self._uses_float_return(node.value)
        return False

    def _return_type(self, body: Optional[ASTNode]) -> str:
        if not self._has_value_return(body):
            return "void"
        # auto falha no g++ quando há return double e return 0 (int) na mesma função
        if self._uses_float_return(body):
            return "double"
        return "auto"

    def _translate_statement(self, node: Optional[ASTNode], indent: str = "") -> str:
        if node is None: return ""
        if isinstance(node, VarDecl):
            if node.init_value is None and getattr(getattr(node,'symbol',None),'type','').startswith('task<'):
                origin = getattr(node.symbol,'task_origin',None)
                if origin is None: raise BackendUnsupportedError('Tipo de tarefa sem origem conhecida',node.line,node.col)
                arg_types = [self._cpp_type(t) for t in origin.argument_types]
                if not all(arg_types): raise BackendUnsupportedError('Anote tipos dos argumentos da tarefa',node.line,node.col)
                args = ', '.join(f'std::declval<{t}>()' for t in arg_types)
                return f'{indent}mp::Task<mp::canonical_t<decltype({origin.function}({args}))>> {node.name};\n'
            expr = self._translate_expression(node.init_value) if node.init_value else "0"
            typ = self._cpp_type(node.type) if node.type not in ('var','task','matrix') else None
            if node.type == 'var' and getattr(getattr(node, 'symbol', None), 'type', '') in ('number', 'int'):
                typ = self._cpp_type(node.symbol.type)
            return f"{indent}{typ or 'auto'} {node.name} = {expr};\n"
        if isinstance(node, Assignment):
            return f"{indent}{node.name} = {self._translate_expression(node.value)};\n"
        if isinstance(node, PropertyAssign):
            obj = self._translate_expression(node.object)
            return f"{indent}{obj}->{node.property_name} = {self._translate_expression(node.value)};\n"
        if isinstance(node, IndexAssign):
            tgt = self._translate_expression(node.target)
            return f"{indent}{tgt} = {self._translate_expression(node.value)};\n"
        
        if isinstance(node, (MethodCall, FuncCallExpr, JoinExpr)):
            return f"{indent}{self._translate_expression(node)};\n"
        if isinstance(node, ReturnStmt):
            val = self._translate_expression(node.value) if node.value else ""
            return f"{indent}return {val};\n"
        if isinstance(node, BreakStmt):
            return f"{indent}break;\n"
        if isinstance(node, ContinueStmt):
            return f"{indent}continue;\n"
        
        if isinstance(node, SendStmt):
            chan = self._translate_expression(node.channel)
            msg = self._translate_expression(node.message)
            return f"{indent}{chan}->sendData(__to_string({msg}));\n"

        if isinstance(node, PrintStmt):
            parts = []
            for i, arg in enumerate(node.arguments):
                if i > 0:
                    parts.append(' << " "')
                parts.append(f" << {self._translate_expression(arg)}")
            return f"{indent}{{ std::lock_guard<std::mutex> __mp_output(mp::output_mutex()); std::cout{ ''.join(parts) } << std::endl; }}\n"
        
        if isinstance(node, SeqBlock):
            lines = [f"{indent}{{\n"]
            for stmt in node.statements: lines.append(self._translate_statement(stmt, indent + "    "))
            lines.append(f"{indent}}}\n")
            return "".join(lines)
        if isinstance(node, ParBlock):
            lines = [f"{indent}{{\n", f"{indent}    std::vector<mp::Task<void>> __m_thr;\n"]
            for stmt in node.statements:
                free = self._free_variables(stmt)
                capture = [f'{name}=mp::snapshot({name})' for name in sorted(free)]
                previous_this = self.this_alias
                if any(isinstance(n,ThisExpr) for n in walk(stmt)):
                    capture.append(f'__mp_this=mp::snapshot_raw({previous_this})')
                    self.this_alias = '__mp_this.get()'
                body = self._translate_statement(stmt,indent+'        ')
                self.this_alias = previous_this
                lines.append(f'{indent}    __m_thr.push_back(mp::fork_local("par", [{", ".join(capture)}]() mutable {{\n{body}{indent}    }}, std::tuple{{}}));\n')
            lines.append(f"{indent}    mp::join_all(__m_thr);\n{indent}}}\n")
            return "".join(lines)
        if isinstance(node, WhileStmt):
            res = f"{indent}while ({self._translate_expression(node.condition)})\n"
            res += self._translate_statement(node.body, indent if isinstance(node.body, (SeqBlock, ParBlock)) else indent + "    ")
            return res
        if isinstance(node, DoWhileStmt):
            res = f"{indent}do\n"
            res += self._translate_statement(node.body, indent if isinstance(node.body, (SeqBlock, ParBlock)) else indent + "    ").rstrip()
            res += f"\n{indent}while ({self._translate_expression(node.condition)});\n"
            return res
        if isinstance(node, ForStmt):
            if node.iterator_name and node.iterable:
                res = f"{indent}for (auto {node.iterator_name} : {self._translate_expression(node.iterable)})\n"
                res += self._translate_statement(node.body, indent if isinstance(node.body, (SeqBlock, ParBlock)) else indent + "    ")
                return res
            init = self._translate_for_part(node.initializer)
            cond = self._translate_expression(node.condition) if node.condition else "true"
            inc = self._translate_for_part(node.increment)
            res = f"{indent}for ({init}; {cond}; {inc})\n"
            res += self._translate_statement(node.body, indent if isinstance(node.body, (SeqBlock, ParBlock)) else indent + "    ")
            return res
        if isinstance(node, IfStmt):
            res = f"{indent}if ({self._translate_expression(node.condition)})\n"
            res += self._translate_statement(node.then_branch, indent if isinstance(node.then_branch, (SeqBlock, ParBlock)) else indent + "    ")
            if node.else_branch:
                res = res.rstrip() + f"\n{indent}else\n"
                if isinstance(node.else_branch, IfStmt):
                    res = res.rstrip() + " " + self._translate_statement(node.else_branch, indent).lstrip()
                else:
                    res += self._translate_statement(node.else_branch, indent if isinstance(node.else_branch, (SeqBlock, ParBlock)) else indent + "    ")
            return res
        return ""

    def _translate_for_part(self, node: Optional[ASTNode]) -> str:
        if node is None: return ""
        if isinstance(node, VarDecl):
            expr = self._translate_expression(node.init_value) if node.init_value else "0"
            typ = self._cpp_type(node.type) if node.type not in ('var', 'matrix', 'task') else None
            if node.type == 'var' and getattr(getattr(node,'symbol',None),'type','') in ('number','int'):
                typ = self._cpp_type(node.symbol.type)
            return f"{typ or 'auto'} {node.name} = {expr}"
        if isinstance(node, Assignment):
            return f"{node.name} = {self._translate_expression(node.value)}"
        if isinstance(node, PropertyAssign):
            return f"{self._translate_expression(node.object)}->{node.property_name} = {self._translate_expression(node.value)}"
        if isinstance(node, IndexAssign):
            return f"{self._translate_expression(node.target)} = {self._translate_expression(node.value)}"
        return self._translate_expression(node)

    def render(self, program: Program) -> str:
        """Gera C++ da AST sem invocar ferramentas externas."""
        if not self._provided_semantic:
            from semantic import SemanticAnalyzer
            analyzer = SemanticAnalyzer()
            if not analyzer.analyze(program):
                diagnostic=analyzer.diagnostics[0]
                raise CompilerError(diagnostic.message,diagnostic.line,diagnostic.col,diagnostic.phase)
            self.semantic = analyzer
        elif self.semantic._has_errors:
            raise BackendUnsupportedError('AST com erros semanticos; backend nao sera executado')
        self.classes = {node.name:node for node in program.statements if isinstance(node,ClassDecl)}
        self.program_id = '__MINIPAR_PROGRAM_HASH__'
        cpp_code = _CPP_HEADER
        cpp_code += f'\nconst std::string __mp_program_id = "{self.program_id}";\n'
        for name in self.classes: cpp_code += f'class {name};\n'
        functions = self._ordered_functions(program)
        for node in functions:
            cpp_code += f'{self._function_return(node)} {node.name}({self._function_params(node)});\n'
        
        for node in self._ordered_classes() + functions:
            if isinstance(node, ClassDecl):
                cpp_code += f"class {node.name}" + (f" : public {node.superclass}" if node.superclass else "") + " {\npublic:\n"
                for attr in node.attributes:
                    if attr.init_value:
                        init = self._translate_expression(attr.init_value)
                        typ = self._cpp_type(attr.type) if attr.type != 'var' else ('double' if isinstance(attr.init_value,NumberExpr) else None)
                        cpp_code += f"    {typ or f'decltype({init})'} {attr.name} = {init};\n"
                    else:
                        cpp_code += f"    {self._cpp_type(attr.type) or 'double'} {attr.name}{{}};\n"
                cpp_code += f'    void __minipar_copy_into({node.name}& copy, mp::SnapshotContext& context) const {{\n'
                for name in self._all_attributes(node.name):
                    cpp_code += f'        copy.{name} = mp::clone_field(this->{name}, context);\n'
                cpp_code += '    }\n'
                for method in node.methods:
                    params = self._function_params(method)
                    ret = self._function_return(method,node.name)
                    cpp_code += f"    {ret} {method.name}({params}) {{\n"
                    if isinstance(method.body, SeqBlock):
                        for stmt in method.body.statements: cpp_code += self._translate_statement(stmt, "        ")
                    else: cpp_code += self._translate_statement(method.body, "        ")
                    cpp_code += "    }\n"
                cpp_code += "};\n\n"
            elif isinstance(node, FuncDecl):
                params = self._function_params(node)
                ret = self._function_return(node)
                cpp_code += f"{ret} {node.name}({params}) {{\n"
                if isinstance(node.body, SeqBlock):
                    for stmt in node.body.statements: cpp_code += self._translate_statement(stmt, "    ")
                else: cpp_code += self._translate_statement(node.body, "    ")
                cpp_code += "}\n\n"

        cpp_code += self._registry(program)
        cpp_code += 'int main(int argc, char** argv) {\n    try {\n    mp::network_init();\n    mp::TaskScope __mp_scope;\n    int __mp_mode = mp::worker_mode(argc, argv, __mp_program_id, __mp_registry());\n    if (__mp_mode >= 0) return __mp_mode;\n'
        for node in program.statements:
            if not isinstance(node, (ClassDecl, FuncDecl)):
                cpp_code += self._translate_statement(node, "    ")
        cpp_code += '\n    __mp_scope.finish();\n    return __minipar_program_status.load();\n    } catch (const std::exception& error) {\n        std::cerr << "[ERRO RUNTIME] " << error.what() << std::endl;\n        return 1;\n    }\n}\n'
        self.program_id = hashlib.sha256(cpp_code.encode('utf-8')).hexdigest()
        return cpp_code.replace('__MINIPAR_PROGRAM_HASH__', self.program_id, 1)

    def generate(self, program: Program, output_name: str) -> bool:
        cpp_code = self.render(program)
        os.makedirs("output", exist_ok=True)
        cpp_path = os.path.join("output", f"{output_name}.cpp")
        exe_path = os.path.join("output", f"{output_name}{executable_suffix()}")

        with open(cpp_path, "w", encoding="utf-8") as f: f.write(cpp_code)
        
        print("[CODEGEN] Compilando via g++ com -std=c++20 e -O3...")
        try:
            result = compile_cpp(Path(cpp_path), Path(exe_path))
        except ToolchainError as exc:
            print(f"[ERRO TOOLCHAIN] {exc}", file=sys.stderr)
            return False
        print(f"[CODEGEN] Compilador: {result.args[0]}")
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if result.returncode == 0:
            print(f"[SUCESSO] Executavel: {exe_path}")
            return True
        print("[ERRO] Falha na compilacao.", file=sys.stderr)
        return False
