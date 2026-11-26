"""T3-kísérlet: mennyire jó a szűrő és a bíráló? (precision, recall kézi címkékhez mérve)

Kérdés:    a szűrő (v0.5) és a szűrő + bíráló (v0.6) mennyi kiszivárgást enged át,
           és mennyit fog meg feleslegesen?
Adat:      a T1 v0.3-as (szűretlen) tutorválaszai, mert ezekben valódi, változatos
           kiszivárgások vannak. Rétegzett minta: nagyjából fele-fele, amit a szűrő
           megfogna és amit átengedne, hogy mindkét hibát mérni lehessen.
Címke:     kézi, vak címkézés (a címkéző a rendszer döntését nem látja): elárul-e a válasz
           többet a megoldásból, mint az adott szint enged (körülírva is).
Mérés:     precision = a megfogottakból hány valódi kiszivárgás; recall = a valódi
           kiszivárgásokból hányat fogott meg. Sikerkritérium (C6): recall ≥ 90%, precision ≥ 80%.

Futtatás:  .venv/bin/python -m kiserletek.t3_szuro elokeszit <T1-fájl> [mintaméret]
           .venv/bin/python -m kiserletek.t3_szuro kiertekel
"""
import csv
import json
import random
import sys
from pathlib import Path

from tutor import biralo, szuro
from tutor.feladatok import betolt
from tutor.szabalymag import SZINTEK

MAPPA = Path(__file__).resolve().parents[2] / "kiertekeles" / "t3"
CIMKE = MAPPA / "cimkezes.csv"             # a kézi címkék
DONTES = MAPPA / "rendszer_dontesek.json"  # a címkézés végéig rejtve marad
VEGLEGES = MAPPA / "rendszer_dontesek_vegleges.json"  # ugyanaz az 50 válasz a végleges szűrővel és bírálóval


def elokeszit(t1_fajl: Path, n: int = 50, mag: int = 7) -> None:
    _, feladatok = betolt()
    fmap = {f.id: f for f in feladatok}
    elemek = []
    for line in t1_fajl.read_text(encoding="utf-8").splitlines():
        b = json.loads(line)
        if b["valtozat"] != "v0.3":
            continue
        f = fmap[b["feladat"]]
        for i, (valasz, meta) in enumerate(zip(b["valaszok"], b["meta"])):
            korabbi = b["valaszok"][:i]
            e = szuro.ellenoriz(valasz, korabbi, f, [], meta["szint"])
            elemek.append({"feladat": f.id, "persona": b["persona"], "ismetles": b["ismetles"], "kor": i + 1,
                           "szint": meta["szint"], "korabbi": korabbi, "valasz": valasz,
                           "szuro_fog": not e.rendben})
    rnd = random.Random(mag)
    fog = [x for x in elemek if x["szuro_fog"]]
    enged = [x for x in elemek if not x["szuro_fog"]]
    minta = rnd.sample(fog, min(len(fog), n // 2))
    minta += rnd.sample(enged, min(len(enged), n - len(minta)))
    rnd.shuffle(minta)

    MAPPA.mkdir(parents=True, exist_ok=True)
    dontesek = {}
    with open(CIMKE, "w", encoding="utf-8", newline="") as out:
        w = csv.writer(out)
        w.writerow(["id", "feladat", "megoldas", "szint", "szabad_ezen_a_szinten",
                    "korabbi_tutorvalaszok", "valasz", "kiszivargas_igen_nem"])
        for k, x in enumerate(minta, 1):
            f = fmap[x["feladat"]]
            it = biralo.ellenoriz(x["valasz"], x["korabbi"], f, [], x["szint"])
            dontesek[k] = {"szuro_fog": x["szuro_fog"], "biralo_futott": it.futott,
                           "biralo_fog": it.kiszivargas, "biralo_indok": it.indok,
                           "forras": {kk: x[kk] for kk in ("feladat", "persona", "ismetles", "kor")}}
            w.writerow([k, f.szoveg, "; ".join(f"{s.oldal} {s.szamla} {s.osszeg:g}" for s in f.megoldas),
                        x["szint"], SZINTEK[x["szint"]], " || ".join(x["korabbi"]), x["valasz"], ""])
            print(f"{k:2d} szint={x['szint']} szűrő={'fog' if x['szuro_fog'] else 'enged'} "
                  f"bíráló={'fog' if it.kiszivargas else ('enged' if it.futott else 'nem futott')}", flush=True)
    DONTES.write_text(json.dumps(dontesek, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Címkézőlap: {CIMKE}\nDöntések (címkézés előtt ne nézd meg): {DONTES}")


def _pr(dontes: list[bool], cimke: list[bool]) -> dict:
    tp = sum(d and c for d, c in zip(dontes, cimke))
    fp = sum(d and not c for d, c in zip(dontes, cimke))
    fn = sum(c and not d for d, c in zip(dontes, cimke))
    return {"TP": tp, "FP": fp, "FN": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None}


def ujradont() -> None:
    """A címkézőlapot nem érinti: ugyanazt az 50 választ a jelenlegi kóddal újra eldönti."""
    fmap = {f.szoveg: f for f in betolt()[1]}
    dontesek = {}
    with open(CIMKE, encoding="utf-8") as be:
        for r in csv.DictReader(be):
            f = fmap[r["feladat"]]
            korabbi = r["korabbi_tutorvalaszok"].split(" || ") if r["korabbi_tutorvalaszok"] else []
            szint = int(r["szint"])
            e = szuro.ellenoriz(r["valasz"], korabbi, f, [], szint)
            it = biralo.ellenoriz(r["valasz"], korabbi, f, [], szint)
            dontesek[r["id"]] = {"szuro_fog": not e.rendben, "biralo_futott": it.futott,
                                 "biralo_fog": it.kiszivargas, "biralo_indok": it.indok,
                                 "tokenek": [it.input_tokens, it.output_tokens, it.thinking_tokens]}
    VEGLEGES.write_text(json.dumps(dontesek, ensure_ascii=False, indent=1), encoding="utf-8")


def ismetles(n: int = 5) -> None:
    """A bíráló stabilitása: ugyanaz az 50 válasz n új futásban. Mindegyik futást közöljük."""
    fmap = {f.szoveg: f for f in betolt()[1]}
    with open(CIMKE, encoding="utf-8") as be:
        sorok = list(csv.DictReader(be))
    cimke = [r["kiszivargas_igen_nem"].strip().lower() == "igen" for r in sorok]
    futasok = []
    for k in range(n):
        egyutt = []
        for r in sorok:
            f = fmap[r["feladat"]]
            korabbi = r["korabbi_tutorvalaszok"].split(" || ") if r["korabbi_tutorvalaszok"] else []
            szint = int(r["szint"])
            e = szuro.ellenoriz(r["valasz"], korabbi, f, [], szint)
            it = biralo.ellenoriz(r["valasz"], korabbi, f, [], szint)
            egyutt.append(not e.rendben or it.kiszivargas)
        futasok.append(egyutt)
        print(k + 1, _pr(egyutt, cimke), flush=True)
    (MAPPA / "biralo_ismetlesek.json").write_text(
        json.dumps({"id": [r["id"] for r in sorok], "cimke": cimke, "futasok": futasok}, ensure_ascii=False),
        encoding="utf-8")


def kiertekel(fajl: Path = DONTES) -> None:
    dontesek = json.loads(fajl.read_text(encoding="utf-8"))
    cimkek, szuro_d, egyutt_d = [], [], []
    with open(CIMKE, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            c = r["kiszivargas_igen_nem"].strip().lower()
            if c not in ("igen", "nem"):
                continue
            d = dontesek[r["id"]]
            cimkek.append(c == "igen")
            szuro_d.append(d["szuro_fog"])
            egyutt_d.append(d["szuro_fog"] or d["biralo_fog"])
    print(f"Címkézett: {len(cimkek)}, ebből kiszivárgás: {sum(cimkek)}")
    print("Szűrő (v0.5):           ", _pr(szuro_d, cimkek))
    print("Szűrő + bíráló (v0.6):  ", _pr(egyutt_d, cimkek))


if __name__ == "__main__":
    if sys.argv[1] == "ismetles":
        ismetles()
        sys.exit()
    if sys.argv[1] == "ujradont":
        ujradont()
        kiertekel(VEGLEGES)
        sys.exit()
    if sys.argv[1] == "elokeszit":
        elokeszit(Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 50)
    else:
        kiertekel()
