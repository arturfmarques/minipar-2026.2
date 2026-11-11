"""Compile e execute uma sonda C++20: python tools/check_toolchain.py."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from toolchain import compile_cpp, compiler_path, executable_suffix, runtime_environment


def check():
    compiler = compiler_path()
    version = subprocess.run([compiler, '--version'], capture_output=True, text=True,
                             env=runtime_environment(compiler), timeout=10, check=True).stdout
    directory = ROOT / 'output' / 'toolchain-check'
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / 'probe.cpp'
    source.write_text('''#include <concepts>
#include <thread>
#include <type_traits>
#include <iostream>
int twice(std::integral auto x) { return x * 2; }
int main() {
    static_assert(std::is_constructible_v<int, int>);
    int value = 0;
    std::thread worker([&] { value = twice(21); });
    worker.join();
    std::cout << value << std::endl;
}
''', encoding='utf-8')
    executable = directory / ('probe' + executable_suffix())
    built = compile_cpp(source, executable)
    report = {'compiler': compiler, 'version': version, 'command': built.args,
              'compile_returncode': built.returncode, 'compile_stderr': built.stderr}
    if built.returncode == 0:
        ran = subprocess.run([str(executable)], capture_output=True, text=True,
                             env=runtime_environment(compiler), timeout=10)
        report.update(execute_returncode=ran.returncode, stdout=ran.stdout, stderr=ran.stderr)
        report['success'] = ran.returncode == 0 and ran.stdout.strip() == '42'
    else:
        report['success'] = False
    return report


if __name__ == '__main__':
    try:
        result = check()
    except Exception as exc:
        result = {'success': False, 'error': str(exc)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result['success'] else 1)
