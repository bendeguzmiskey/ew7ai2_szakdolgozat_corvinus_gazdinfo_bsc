"""Egy korábbi T1-futás beszélgetéseinek (újra)bírálata, ahol a bírálat elmaradt.

Futtatás:  .venv/bin/python -m kiserletek.ujrabiral <futás.jsonl> [bíráló: nagy|kicsi]
A fájlt helyben frissíti (előtte .bak másolatot készít).
"""
import json
import shutil
import sys

from tutor.feladatok import betolt
from .t1_kiszivargas import biral

fajl = sys.argv[1]
biralo = sys.argv[2] if len(sys.argv) > 2 else "nagy"
fmap = {f.id: f for f in betolt()[1]}
shutil.copy(fajl, fajl + ".bak")
sorok = [json.loads(l) for l in open(fajl, encoding="utf-8")]
for s in sorok:
    if s["biralo"].get("teljes") is None:
        s["biralo"] = biral(fmap[s["feladat"]], s["valaszok"], biralo, s["history"])
        print(s["feladat"], s["persona"], s["valtozat"], s["biralo"].get("teljes"), s["biralo"].get("reszleges"), flush=True)
with open(fajl, "w", encoding="utf-8") as f:
    for s in sorok:
        f.write(json.dumps(s, ensure_ascii=False) + "\n")
