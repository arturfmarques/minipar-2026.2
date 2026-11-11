"""Assinaturas da biblioteca nativa; nao dependem de programas de exemplo."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Builtin:
    arities: tuple[int, ...]
    parameters: tuple[str, ...]
    result: str
    cpp: str | None = None


BUILTINS = {
    'exp': Builtin((1,), ('number',), 'number'),
    'random': Builtin((0,), (), 'number'),
    'range': Builtin((1, 2), ('number', 'number'), 'list'),
    'len': Builtin((1,), ('collection',), 'number'),
    'to_number': Builtin((1,), ('string',), 'number'),
    'parse_ints': Builtin((1,), ('string',), 'list'),
    'floor': Builtin((1,), ('number',), 'number', 'std::floor'),
    'to_string': Builtin((1,), ('scalar',), 'string', '__minipar_text'),
    'monotonic': Builtin((0,), (), 'number', '__minipar_monotonic'),
    'available_cpus': Builtin((0,), (), 'list', 'mp::available_cpus'),
    'current_cpu': Builtin((0,), (), 'number', 'mp::current_cpu'),
    'write_text': Builtin((2,), ('string', 'string'), 'void', '__minipar_write_text'),
    'get_env': Builtin((2,), ('string', 'string'), 'string', '__minipar_get_env'),
    'require': Builtin((2,), ('bool', 'string'), 'void', '__minipar_require'),
    'is_finite': Builtin((1,), ('number',), 'bool', 'std::isfinite'),
    'try_write_text': Builtin((2,), ('string', 'string'), 'bool', '__minipar_try_write_text'),
    'set_exit_code': Builtin((1,), ('number',), 'void', '__minipar_set_exit_code'),
}
