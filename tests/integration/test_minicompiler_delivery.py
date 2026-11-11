"""O artefato ARM deve ser regenerado pelo executavel MiniPar a cada entrada."""
import pytest

from tools import validate_programs as pipeline
from tools.arm_validation import validate_arm
from tools.validate_minicompiler import SOURCE, MANDATORY, check_success


@pytest.mark.native
def test_arm_file_is_recreated_for_repeated_and_changed_expressions(tmp_path):
    built = pipeline.build(SOURCE, tmp_path / 'build')
    assert built['phases']['native_compilation'] == pipeline.PASS, built
    target = tmp_path / 'regenerated.arm'
    assemblies = []
    for index, (expression, expected) in enumerate(MANDATORY + [('6*9-1', 53)]):
        # Um arquivo anterior nao pode ser confundido com a geracao atual.
        target.write_text('artefato anterior invalido\n', encoding='utf-8')
        result = pipeline.run(built, expression + '\n', env={'MINIPAR_ARM_OUTPUT': str(target)})
        check_success(result, target, expected)
        assemblies.append(target.read_text(encoding='utf-8'))
        arm = validate_arm(target, tmp_path / f'run-{index}.elf')
        assert arm['assembler']['returncode'] == 0, arm
        assert arm['emulation']['r0_signed'] == expected, arm
    assert assemblies[0] == assemblies[2]
    assert len(set(assemblies)) == 3
