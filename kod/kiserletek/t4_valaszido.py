"""T4-mérés: mennyi ideig tart egy tutorválasz, és mennyit lassít rajta a szűrő, a bíráló és az újragenerálás?

Kérdés:    milyen gyorsan válaszol a végleges (v0.6) tutor, és melyik lépés mennyi időt visz el?
Kísérlet:  a T1 persona-szkriptjei (4 persona × 3 feladat × N ismétlés), a v0.6 tutorral,
           mérő bíráló nélkül (itt csak az időt mérjük, a kiszivárgást nem).
Mérés:     körönként a teljes válaszidő (valaszol() hívás), és ezen belül:
           - a válaszíró modell hívásai (db, mp), a bíráló hívásai (db, mp),
           - a RAG-keresés (benne a kérdés beágyazása, ami API-hívás),
           - a szűrő (tisztán kód),
           - az API-újrapróbálás miatti várakozás (429/503 esetén; ezt külön jelöljük,
             és az összesítésben külön mutatjuk, mert nem a rendszer tulajdonsága).
           Az útvonal a pipeline saját jelöléséből jön: szűrő = átment / újragenerálva / tartalék,
           bíráló = futott-e.
A tutor kódja változatlan: a szkript csak becsomagolja (időzíti) a meglévő függvényeket,
és a mérés után visszaállítja őket.
Korlát:    a válaszidő a hálózattól és az API pillanatnyi terhelésétől is függ (egyetlen gépről,
           egy időpontban mérünk). Ez leíró mérés, nincs előre rögzített sikerkritériuma.

Futtatás:  .venv/bin/python -m kiserletek.t4_valaszido [ismétlés, alapértelmezés: 1]
"""
import json
import statistics
import sys
import time
import types as pytypes
from pathlib import Path

from tutor import biralo, llm, pipeline, rag, szuro
from tutor.feladatok import betolt
from kiserletek import t1_kiszivargas as t1

KIMENET = Path(__file__).resolve().parents[2] / "kiertekeles" / "futtatasok"
MODELL = "kicsi"   # a tutor éles modellje (flash-lite)

# --- időzítés: egy kör méréseit ide gyűjtjük ---------------------------------------------
_kor: dict = {}
_biralon_belul = False   # a bíráló is llm.generate-et hív; azt a bírálóhoz számoljuk, nem a válaszíróhoz


def _uj_kor() -> None:
    _kor.clear()
    _kor.update(tutor_s=0.0, tutor_db=0, biralo_s=0.0, biralo_db=0, rag_s=0.0, szuro_s=0.0,
                ujraprobalas_s=0.0, ujraprobalas_db=0)


def _becsomagol():
    """Időzítő burkolók a meglévő függvények köré. Visszaadja az eredetieket a visszaállításhoz."""
    global _biralon_belul
    eredeti = {"generate": llm.generate, "sleep": llm.time, "biralo": biralo.ellenoriz,
               "keres": rag.Visszakereso.keres, "szuro": szuro.ellenoriz,
               "valaszol": t1.valaszol}

    def generate(*a, **k):
        t = time.perf_counter()
        try:
            return eredeti["generate"](*a, **k)
        finally:
            if not _biralon_belul:
                _kor["tutor_s"] += time.perf_counter() - t
                _kor["tutor_db"] += 1

    def sleep(mp):
        _kor["ujraprobalas_s"] += mp
        _kor["ujraprobalas_db"] += 1
        time.sleep(mp)

    def biralo_ellenoriz(*a, **k):
        global _biralon_belul
        t = time.perf_counter()
        _biralon_belul = True
        try:
            it = eredeti["biralo"](*a, **k)
        finally:
            _biralon_belul = False
            dt = time.perf_counter() - t
        if it.futott:                       # nem kockázatos körben a bíráló nem hív modellt
            _kor["biralo_s"] += dt
            _kor["biralo_db"] += 1
        return it

    def keres(self, *a, **k):
        t = time.perf_counter()
        try:
            return eredeti["keres"](self, *a, **k)
        finally:
            _kor["rag_s"] += time.perf_counter() - t

    def szuro_ellenoriz(*a, **k):
        t = time.perf_counter()
        try:
            return eredeti["szuro"](*a, **k)
        finally:
            _kor["szuro_s"] += time.perf_counter() - t

    meresek: list[dict] = []

    def valaszol(*a, **k):
        _uj_kor()
        t = time.perf_counter()
        v = eredeti["valaszol"](*a, **k)
        meresek.append({"teljes_s": time.perf_counter() - t, **_kor,
                        "szuro": v.szuro, "biralo": v.biralo, "szint": v.szint})
        return v

    llm.generate = generate
    llm.time = pytypes.SimpleNamespace(sleep=sleep)
    biralo.ellenoriz = biralo_ellenoriz
    rag.Visszakereso.keres = keres
    szuro.ellenoriz = szuro_ellenoriz
    t1.valaszol = valaszol
    return eredeti, meresek


def _visszaallit(eredeti: dict) -> None:
    llm.generate = eredeti["generate"]
    llm.time = eredeti["sleep"]
    biralo.ellenoriz = eredeti["biralo"]
    rag.Visszakereso.keres = eredeti["keres"]
    szuro.ellenoriz = eredeti["szuro"]
    t1.valaszol = eredeti["valaszol"]


def utvonal(m: dict) -> str:
    if m["szuro"] == "tartalék":
        return "tartalék"
    if m["szuro"] == "újragenerálva":
        return "újragenerálva"
    return "szűrő + bíráló" if m["biralo_db"] else "csak szűrő"


def _p90(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(0.9 * (len(xs) - 1)))]


def osszesit(meresek: list[dict]) -> str:
    tiszta = [m for m in meresek if not m["ujraprobalas_db"]]
    sorok = [f"Körök: {len(meresek)}, ebből API-újrapróbálás nélkül: {len(tiszta)} "
             f"(a táblázat csak ezeket tartalmazza)", "",
             "| Útvonal | Körök | Medián (mp) | 90. percentilis (mp) | Válaszíró hívás/kör | Bíráló hívás/kör |",
             "|---|---|---|---|---|---|"]
    for u in ["csak szűrő", "szűrő + bíráló", "újragenerálva", "tartalék", "összes"]:
        ms = tiszta if u == "összes" else [m for m in tiszta if utvonal(m) == u]
        if not ms:
            continue
        ido = [m["teljes_s"] for m in ms]
        sorok.append(f"| {u} | {len(ms)} | {statistics.median(ido):.1f} | {_p90(ido):.1f} | "
                     f"{statistics.mean(m['tutor_db'] for m in ms):.1f} | "
                     f"{statistics.mean(m['biralo_db'] for m in ms):.1f} |")
    if tiszta:
        sorok += ["", "Átlagos időmegoszlás (mp/kör): "
                  f"válaszíró {statistics.mean(m['tutor_s'] for m in tiszta):.2f}, "
                  f"bíráló {statistics.mean(m['biralo_s'] for m in tiszta):.2f}, "
                  f"RAG {statistics.mean(m['rag_s'] for m in tiszta):.2f}, "
                  f"szűrő {statistics.mean(m['szuro_s'] for m in tiszta):.4f}"]
    return "\n".join(sorok)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    _, feladatok = betolt()
    fmap = {f.id: f for f in feladatok}
    KIMENET.mkdir(parents=True, exist_ok=True)
    fajl = KIMENET / f"{time.strftime('%Y-%m-%d_%H%M')}_T4_valaszido.jsonl"
    pipeline._rag()   # a jegyzet betöltése előre, hogy az első kör ne ezzel induljon
    eredeti, meresek = _becsomagol()
    try:
        for i in range(n):
            for fid in t1.FELADAT_IDK:
                for persona in t1.PERSONAK:
                    elotte = len(meresek)
                    t1.beszelgetes("v0.6", fmap[fid], persona, MODELL)
                    for k, m in enumerate(meresek[elotte:]):
                        sor = {"ismetles": i + 1, "feladat": fid, "persona": persona, "kor": k + 1,
                               "utvonal": utvonal(m), **m}
                        with open(fajl, "a", encoding="utf-8") as out:
                            out.write(json.dumps(sor, ensure_ascii=False) + "\n")
                    uj = meresek[elotte:]
                    print(f"{fid} {persona:10s} {len(uj)} kör, medián "
                          f"{statistics.median(m['teljes_s'] for m in uj):.1f} mp", flush=True)
    finally:
        _visszaallit(eredeti)
    print()
    print(osszesit(meresek))
    print("\nMentve:", fajl)


if __name__ == "__main__":
    main()
