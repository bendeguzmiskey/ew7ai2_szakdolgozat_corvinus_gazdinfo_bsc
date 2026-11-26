"""T2-kísérlet: követi-e a tutor a kurzus jelöléseit, ha a jegyzetből dolgozik (RAG)?

Kérdés:    a v0.4-es visszakeresés mennyivel növeli a kurzuskonform válaszok arányát?
Kísérlet:  12 fogalmi hallgatói kérdés, mindegyik egy olyan pontra, ahol a kurzus jelölése
           eltér attól, amit a modell máshonnan tud (számlaszám helyett számlanév, E/F/R/B,
           funkcionális ráfordítás költségnem helyett, Áfa pénzügyi rendezése).
           Két feltétel, minden más azonos: a teljes rendszer RAG-gal és RAG nélkül.
           Egy kör, 2. segítségi szint (ekkor szabad fogalmat magyarázni), N ismétlés.
Mérés:     független bíráló (nagy modell) a jegyzet megfelelő szakaszát kapja referenciának:
           (1) kurzuskonform-e a válasz (a kurzus jelöléseit használja, nem mond ellent nekik),
           (2) tárgyilag helyes-e. Sikerkritérium (C4): RAG-gal ≥ 20 százalékponttal több
           kurzuskonform válasz.

Futtatás:  .venv/bin/python -m kiserletek.t2_rag [ismétlés] [bíráló: nagy|kicsi]
"""
import json
import sys
import time
from pathlib import Path

from tutor import llm, rag
from tutor.feladatok import betolt
from tutor.pipeline import Allapot, valaszol

KIMENET = Path(__file__).resolve().parents[2] / "kiertekeles" / "futtatasok"

# (kérdés, a referencia-szakasz azonosítója a jegyzetben)
KERDESEK = [
    ("Milyen számlaszámra kell könyvelni a szállítói tartozást?", "J1"),
    ("Mi az előzetes áfa számlaszáma?", "J1"),
    ("Az előzetes áfa eszköz vagy forrás?", "J6"),
    ("A fizetendő áfa milyen jellegű számla?", "J7"),
    ("Mit jelent az, hogy egy számla R jellegű?", "J2"),
    ("Milyen betűvel jelöljük a bevétel jellegű számlákat?", "J2"),
    ("Az irodaszer vásárlását melyik költségnemre, milyen számlára könyveljük?", "J9"),
    ("A reklám költsége melyik számlára kerül?", "J9"),
    ("Mikor használjuk az Áfa pénzügyi rendezése számlát?", "J8"),
    ("Minden áfás beszerzésnél az Áfa pénzügyi rendezése számlára könyvelünk?", "J8"),
    ("Az eladott áru beszerzési értéke milyen számlára kerül?", "J10"),
    ("A ráfordítás növekedése a tartozik vagy a követel oldalra kerül?", "J3"),
]
FELADAT = "F01"  # semleges háttérfeladat; a kérdések általános fogalmakra vonatkoznak
SZINT2 = 2       # 2 sikertelen kísérlet → 2. szint: fogalmat szabad magyarázni

BIRALO_PROMPT = """Egy egyetemi számviteli kurzus tutorának válaszát kell értékelned.
A kurzus saját jelöléseket használ. A kurzus jegyzetének vonatkozó része (ez a mérce):
\"\"\"{referencia}\"\"\"
A kurzus általános jelölései: a számlákat névvel jelöljük, számlaszámot nem használunk;
a számlák jellege E (eszköz), F (forrás), R (ráfordítás), B (bevétel); a ráfordításokat
funkció szerint (Adminisztratív ráfordítások, Értékesítési ráfordítások, ELÁBÉ) számoljuk el,
nem költségnemek szerint.

A hallgató kérdése: {kerdes}
A tutor válasza:
\"\"\"{valasz}\"\"\"

Döntsd el:
(1) kurzuskonform: a válasz a kurzus jelöléseit használja, és semmi nem mond ellent nekik
    (pl. nem ad meg számlaszámot, nem költségnemre könyvel, nem nevez mást E/F/R/B-nek);
    ha a válasz csak kérdez vissza, és semmilyen jelölést nem használ, az is kurzuskonform;
(2) helyes: amit tényként állít, az tárgyilag helyes a mérce szerint;
(3) erdemi: a válasz ténylegesen foglalkozik a kérdéssel (nem csak elutasít).
Válaszolj csak JSON-ban: {{"kurzuskonform": true/false, "helyes": true/false, "erdemi": true/false, "indoklas": "1 mondat"}}"""


def biral(kerdes: str, valasz: str, ref_id: str, biralo_model: str, szakaszok: dict) -> dict:
    s = szakaszok[ref_id]
    prompt = BIRALO_PROMPT.format(referencia=f"{s.cim}: {s.szoveg}", kerdes=kerdes, valasz=valasz)
    try:
        r = llm.generate([{"role": "user", "text": prompt}], "Szigorú, pontos értékelő vagy.",
                         biralo_model, json_valasz=True, max_tokens=4096)
        out = json.loads(r.text)
        out["biralo_modell"] = r.model_version
        return out
    except Exception as e:
        return {"kurzuskonform": None, "helyes": None, "erdemi": None, "indoklas": f"bírálat sikertelen: {e}"}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    biralo = sys.argv[2] if len(sys.argv) > 2 else "nagy"
    _, feladatok = betolt()
    f = {x.id: x for x in feladatok}[FELADAT]
    szakaszok = {s.id: s for s in rag.szakaszok()}
    KIMENET.mkdir(parents=True, exist_ok=True)
    fajl = KIMENET / f"{time.strftime('%Y-%m-%d_%H%M')}_T2_rag.jsonl"
    for i in range(n):
        for kerdes, ref in KERDESEK:
            for rag_be in (False, True):
                allapot = Allapot(feladat_id=f.id, feladat_szoveg=f.szoveg, sikertelen_kiserletek=SZINT2)
                v = valaszol([{"role": "user", "text": kerdes}], allapot, "kicsi", naplo=False, rag_be=rag_be)
                b = biral(kerdes, v.szoveg, ref, biralo, szakaszok)
                sor = {"ismetles": i + 1, "kerdes": kerdes, "referencia": ref, "rag": rag_be,
                       "valasz": v.szoveg, "szint": v.szint, "szuro": v.szuro, "biralo_tutor": v.biralo,
                       "jegyzet": v.jegyzet, "forrasok": v.forrasok, "model": v.model_version,
                       "tokenek": [v.input_tokens, v.output_tokens], "biralo": b}
                with open(fajl, "a", encoding="utf-8") as out:
                    out.write(json.dumps(sor, ensure_ascii=False) + "\n")
                print(f"{i+1} {ref:3s} rag={'be ' if rag_be else 'ki '} konform={b.get('kurzuskonform')} "
                      f"helyes={b.get('helyes')} érdemi={b.get('erdemi')} | jegyzet={v.jegyzet} | {kerdes[:45]}",
                      flush=True)
    print("Mentve:", fajl)


if __name__ == "__main__":
    main()
