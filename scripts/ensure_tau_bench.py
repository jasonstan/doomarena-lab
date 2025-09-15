import importlib
import os
import subprocess
import sys


def has_tau_bench() -> bool:
    try:
        importlib.import_module('tau_bench')
        return True
    except Exception:
        return False


def main() -> int:
    if has_tau_bench():
        print('tau_bench: available')
        return 0

    sources = [
        ('tau-bench', ['pip', 'install', '-U', 'tau-bench']),
        ('tau_bench', ['pip', 'install', '-U', 'tau_bench']),
        (
            'git+https://github.com/ServiceNow/tau-bench@main',
            ['pip', 'install', '-U', 'git+https://github.com/ServiceNow/tau-bench@main'],
        ),
    ]

    for label, cmd in sources:
        try:
            env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
            subprocess.check_call([sys.executable, '-m', *cmd], env=env)
            if has_tau_bench():
                print(f'tau_bench installed from {label}')
                return 0
        except Exception:
            continue

    print('tau_bench could not be installed from any source', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
