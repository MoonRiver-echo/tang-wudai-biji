# -*- coding: utf-8 -*-
import re, sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
para_re = re.compile(r'^(【\d{2}-\d{3}】)')
total = 0
for w in sorted(Path('.').iterdir()):
    if not w.is_dir():
        continue
    f = w / (w.name + '-校订全本.md')
    if not f.exists():
        continue
    n = sum(1 for l in f.read_text(encoding='utf-8').splitlines() if para_re.match(l.strip()))
    total += n
    print(f"{w.name}: {n}")
print(f"TOTAL: {total}")
