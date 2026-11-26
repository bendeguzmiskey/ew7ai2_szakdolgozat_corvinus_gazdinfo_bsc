"""T2b: mennyire alátámasztottak a tutor válaszának állításai? (FActScore / RAGAS hűség)

Egy hosszabb válaszban keveredik az alátámasztott és a nem alátámasztott állítás, ezért
nem elég az egész választ egyben minősíteni (Min et al., 2023). Ez a mérés a T2 válaszait
elemi állításokra bontja, és mindegyiket a jegyzethez méri.

Adat:      a T2 meglévő 72 válasza (2026-11-01), új beszélgetés nincs.
Mérés:     a mérés bírálója (nagy modell) a válaszból kiszedi a tárgyi állításokat (a kérdéseket
           és a biztatást nem), és mindegyikről eldönti a teljes jegyzet alapján:
             alatamasztott – a jegyzet valamelyik szakasza kimondja vagy egyértelműen következik belőle;
             ellentmond     – a jegyzet mást mond;
             nincs_benne    – a jegyzet nem szól róla.
           Mindkét feltételnél ugyanaz a mérce (a teljes jegyzet), így a RAG nélküli válasz is mérhető.
Mutatók:   alátámasztottsági arány (FActScore-szerű) = alátámasztott / összes állítás;
           ellentmondási arány; RAG-gal a hűség (RAGAS-szerű) = a ténylegesen visszakeresett
           szakaszok által alátámasztott állítások aránya.
Korlát:    a bontást és az ítéletet is LLM végzi egy hívásban (a RAGAS két lépésben teszi);
           a bíráló nincs emberhez mérve.

Futtatás:  .venv/bin/python -m kiserletek.t2_huseg <T2-fájl> [darab]
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from tutor import llm, rag

PROMPT = """Egy számviteli kurzus tutorának válaszát kell ellenőrizned a kurzus jegyzete alapján.

A JEGYZET (szakaszonként, azonosítóval):
{jegyzet}

A hallgató kérdése: {kerdes}
A tutor válasza:
\"\"\"{valasz}\"\"\"

1. Bontsd a választ elemi tárgyi állításokra: egy állítás egyetlen ellenőrizhető tényt mond ki
   (pl. "az előzetes áfa eszköz jellegű számla"). A kérdések, a biztatás, a felszólítások és a
   puszta ismétlése annak, amit a hallgató kérdezett, NEM állítások.
2. Mindegyik állításról döntsd el a JEGYZET alapján:
   "alatamasztott": a jegyzet valamelyik szakasza kimondja, vagy egyértelműen következik belőle;
   "ellentmond": a jegyzet mást mond;
   "nincs_benne": a jegyzet nem szól róla (akkor is, ha egyébként igaz).
   Alátámasztott állításnál add meg a szakasz azonosítóját (pl. "J6").
Válaszolj csak JSON-ban:
{{"allitasok": [{{"allitas": "...", "itelet": "alatamasztott|ellentmond|nincs_benne", "szakasz": "J6 vagy null"}}]}}"""


def jegyzet_szoveg() -> str:
    return "\n".join(f"[{s.id}] {s.cim}: {s.szoveg}" for s in rag.szakaszok())


def tiszta(valasz: str) -> str:
    """A forrássort levesszük: az a rendszer jelölése, nem a modell állítása."""
    return re.sub(r"\n*\*Forrás:.*\*\s*$", "", valasz).strip()


def bontas(kerdes: str, valasz: str, jegyzet: str) -> dict:
    r = llm.generate([{"role": "user", "text": PROMPT.format(jegyzet=jegyzet, kerdes=kerdes, valasz=valasz)}],
                     "Szigorú, pontos ellenőr vagy.", "nagy", json_valasz=True, max_tokens=8192)
    out = json.loads(r.text)
    out["tokenek"] = [r.input_tokens, r.output_tokens, r.thinking_tokens]
    out["biralo_modell"] = r.model_version
    return out


def main():
    be = Path(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else None
    ki = be.with_name(be.stem + "_huseg.jsonl")
    sorok = [json.loads(l) for l in be.read_text(encoding="utf-8").splitlines()][:n]
    jegyzet = jegyzet_szoveg()
    for s in sorok:
        try:
            b = bontas(s["kerdes"], tiszta(s["valasz"]), jegyzet)
        except Exception as e:  # a hibát rögzítjük, nem hallgatjuk el
            b = {"hiba": str(e), "allitasok": []}
        rec = {k: s[k] for k in ("ismetles", "kerdes", "referencia", "rag", "jegyzet")} | {"huseg": b}
        with open(ki, "a", encoding="utf-8") as out:
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        db = defaultdict(int)
        for a in b["allitasok"]:
            db[a.get("itelet")] += 1
        print(f"rag={'be ' if s['rag'] else 'ki '} {s['referencia']:3s} {dict(db)} {b.get('hiba', '')[:80]}", flush=True)
    osszesit(ki)


def osszesit(fajl: Path) -> None:
    sorok = [json.loads(l) for l in fajl.read_text(encoding="utf-8").splitlines()]
    for feltetel in (False, True):
        t = defaultdict(int)
        for s in (x for x in sorok if x["rag"] == feltetel):
            if s["huseg"].get("hiba"):
                t["hiba"] += 1
                continue
            t["valasz"] += 1
            al = s["huseg"]["allitasok"]
            t["nulla_allitas"] += not al
            for a in al:
                t["osszes"] += 1
                t[a.get("itelet")] += 1
                if feltetel and a.get("itelet") == "alatamasztott" and a.get("szakasz") in s["jegyzet"]:
                    t["visszakeresettbol"] += 1
        o = t["osszes"] or 1
        print(f"RAG {'BE ' if feltetel else 'KI '}: {t['valasz']} válasz ({t['nulla_allitas']} állítás nélkül, "
              f"{t['hiba']} hiba), {t['osszes']} állítás | alátámasztott {100*t['alatamasztott']/o:.0f}% | "
              f"ellentmond {100*t['ellentmond']/o:.0f}% | nincs benne {100*t['nincs_benne']/o:.0f}%"
              + (f" | hűség a visszakeresetthez {100*t['visszakeresettbol']/o:.0f}%" if feltetel else ""))


if __name__ == "__main__":
    if sys.argv[1] == "osszesit":
        osszesit(Path(sys.argv[2]))
    else:
        main()
