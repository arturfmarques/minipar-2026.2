"""Exposição estruturada das fases do compilador MiniPar existente."""
from dataclasses import fields, is_dataclass

from ast_nodes import ASTNode, ForkExpr, walk
from codegen import CppCodeGenerator
from diagnostics import CompilerError, Diagnostic
from lexer import Lexer, TokenType
from parser import Parser
from semantic import SemanticAnalyzer
from tac import TACGenerator

STAGES = ('tokens', 'ast', 'semantic', 'tac', 'cpp')


def _diagnostic(error, phase):
    item = error.diagnostic if isinstance(error, CompilerError) else error
    if not isinstance(item, Diagnostic):
        item = Diagnostic(phase, str(error))
    return {'phase': item.phase, 'message': item.message,
            'line': item.line, 'column': item.col}


def serialize_ast(root):
    """Serializa todos os nós reais e suas arestas; a interface decide o que recolher."""
    serial = 0

    def visit(node, edge='raiz'):
        nonlocal serial
        serial += 1
        result = {'id': f'n{serial}', 'type': type(node).__name__, 'edge': edge,
                  'line': getattr(node, 'line', 1), 'column': getattr(node, 'col', 1),
                  'details': {}, 'children': []}
        if is_dataclass(node):
            for member in fields(node):
                value = getattr(node, member.name)
                if isinstance(value, ASTNode):
                    result['children'].append(visit(value, member.name))
                elif isinstance(value, list) and any(isinstance(x, ASTNode) for x in value):
                    for index, child in enumerate(value):
                        if isinstance(child, ASTNode):
                            result['children'].append(visit(child, f'{member.name}[{index}]'))
                elif member.name not in ('line', 'col') and value is not None:
                    result['details'][member.name] = value
        return result

    tree = visit(root)
    return tree, serial


def _symbol_rows(semantic):
    rows = []

    def add(symbol, scope, scope_id):
        full = semantic._functions.get(symbol.name) or semantic._classes.get(symbol.name)
        if full is None: full = semantic._callables.get(symbol.name, symbol)
        details = {}
        if full.params:
            details['parameters'] = [f'{name}: {typ}' for name, typ in
                                     zip(full.params, full.param_types)]
        if full.type == 'FUNC': details['return'] = full.return_type
        if full.superclass: details['superclass'] = full.superclass
        if full.attributes: details['attributes'] = full.attributes
        if full.methods: details['methods'] = list(full.methods)
        rows.append({'name': symbol.name, 'category': symbol.category,
                     'type': symbol.type, 'scope': scope, 'scope_id': scope_id,
                     'line': symbol.line, 'details': details})

    for scope in semantic.scope_history:
        for symbol in scope['symbols'].values():
            add(symbol, scope['label'], scope['id'])
    for symbol in semantic._scopes[0].values():
        add(symbol, 'global', 0)
    for class_name, class_symbol in semantic._classes.items():
        for name, method in class_symbol.methods.items():
            rows.append({'name': name, 'category': 'método', 'type': 'FUNC',
                         'scope': f'classe {class_name}', 'scope_id': None,
                         'line': method.definition.line if method.definition else 1,
                         'details': {'parameters': [f'{p}: {t}' for p, t in
                                     zip(method.params, method.param_types)],
                                     'return': method.return_type}})
    return rows


def analyze_source(code, stage):
    """Mantém os erros de cada fase e não produz TAC/C++ após erro impeditivo."""
    if stage not in STAGES: raise ValueError('Etapa desconhecida')
    result = {'stage': stage, 'success': False,
              'phases': {name: 'não executada' for name in STAGES}, 'diagnostics': []}

    try:
        tokens = Lexer(code).tokenize()
        result['tokens'] = [{'number': index, 'type': token.type.name,
                             'lexeme': token.lexeme, 'line': token.line, 'column': token.col}
                            for index, token in enumerate(tokens, 1)]
        result['phases']['tokens'] = 'aprovada'
        if stage == 'tokens':
            result['success'] = True
            return result
        program = Parser(tokens).parse()
        result['phases']['ast'] = 'aprovada'
        if stage == 'ast':
            result['ast'], result['node_count'] = serialize_ast(program)
            result['success'] = True
            return result
        semantic = SemanticAnalyzer()
        valid = semantic.analyze(program)
        result['symbols'] = _symbol_rows(semantic)
        result['diagnostics'] = [_diagnostic(item, 'SEMANTICO') for item in semantic.diagnostics]
        if not valid:
            result['phases']['semantic'] = 'reprovada'
            return result
        result['phases']['semantic'] = 'aprovada'
        result['remote_forks'] = sum(isinstance(node, ForkExpr) and
                                     node.destination.kind == 'remote' for node in walk(program))
        if stage == 'semantic':
            result['success'] = True
            return result
        result['tac'] = TACGenerator().generate_text(program)
        result['phases']['tac'] = 'aprovada'
        if stage == 'tac':
            result['success'] = True
            return result
        result['cpp'] = CppCodeGenerator(semantic).render(program)
        result['phases']['cpp'] = 'aprovada'
        result['success'] = True
        return result
    except CompilerError as error:
        phase = error.diagnostic.phase
        key = {'LEXICO': 'tokens', 'SINTATICO': 'ast', 'SEMANTICO': 'semantic',
               'BACKEND': 'cpp'}.get(phase, stage)
        result['phases'][key] = 'reprovada'
        result['diagnostics'].append(_diagnostic(error, phase))
        return result
