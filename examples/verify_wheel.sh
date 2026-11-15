#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
python -m pip wheel --no-deps --wheel-dir "$tmp/dist" "$root"
python -m venv "$tmp/env"
"$tmp/env/bin/python" -m pip install --no-deps "$tmp"/dist/*.whl
cp -R "$root/examples" "$root/assets" "$tmp/"
(
    cd "$root"
    python -m hamiltonlab demo > "$tmp/source-demo.json"
    python examples/render_windows.py --check --json "$tmp/source-curves.json"
)
cd "$tmp"
"$tmp/env/bin/python" -I - "$root" <<'PY'
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
root = Path(sys.argv[1]).resolve()
modules = ['hamiltonlab'+('.'+p.stem if p.stem != '__init__' else '')
           for p in (root/'hamiltonlab').glob('*.py') if p.stem != '__main__']
# The figure tests load a source renderer. Load every package module from the
# installed distribution first and verify origins again after the full suite.
for name in modules:
    importlib.import_module(name)
def origins():
    paths = {name: importlib.util.find_spec(name).origin
             for name in modules+['hamiltonlab.__main__']}
    for path in paths.values():
        assert 'site-packages' in path and not Path(path).resolve().is_relative_to(root)
    return paths
origins()
suite = unittest.defaultTestLoader.discover(str(root/'tests'))
assert unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()
paths = origins()
exe = str(Path(sys.executable).parent/'hamiltonlab')
commands = [('sample', 'chain.json'), ('sample', 'random_length.json'),
            ('diagnose', 'chains.json'), ('quadratic', 'quadratic.json'),
            ('harmonic', 'harmonic.json'), ('window', 'window.json'),
            ('window-mixture', 'window_mixture.json')]
for command, filename in commands:
    result = subprocess.run([exe, command, str(root/'examples'/filename)],
                            capture_output=True, text=True, check=True)
    json.loads(result.stdout)
    Path(command+'-'+filename).write_text(result.stdout)
print(json.dumps({'installed_origins': paths, 'documented_input_commands': len(commands)}))
PY
"$tmp/env/bin/python" -I -m hamiltonlab demo > installed-demo.json
cmp source-demo.json installed-demo.json
"$tmp/env/bin/python" -I examples/render_demo.py installed-demo.json --check
"$tmp/env/bin/python" -I examples/render_windows.py --check --json installed-curves.json
cmp source-curves.json installed-curves.json
