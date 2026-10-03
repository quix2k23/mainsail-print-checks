#!/usr/bin/env python3
"""Rebuild install.py by embedding src/nozzle-check.js into src/install.template.py."""
import pathlib
root = pathlib.Path(__file__).parent
js = (root / 'src/nozzle-check.js').read_text()
assert "'''" not in js, "the script must not contain triple single quotes"
out = (root / 'src/install.template.py').read_text().replace('@@JS@@', js)
(root / 'install.py').write_text(out)
(root / 'install.py').chmod(0o755)
print('wrote install.py')
