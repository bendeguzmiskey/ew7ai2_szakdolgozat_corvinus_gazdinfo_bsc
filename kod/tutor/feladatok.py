"""A feladatok és a megoldókulcsok betöltése és bővítése (data/feladatok.json).

Az oktatói felületen felvett új feladat kulcsát kódból ellenőrizzük, mert az ellenőrző,
a szűrő és a bíráló is a kulcs helyességére épít."""
import json
from dataclasses import dataclass
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "feladatok.json"


@dataclass(frozen=True)
class Sor:
    """Egy könyvelési tételsor: oldal (T/K), számla, összeg (eFt)."""
    oldal: str
    szamla: str
    osszeg: float


@dataclass(frozen=True)
class Feladat:
    id: str
    szoveg: str
    megoldas: tuple[Sor, ...]


def betolt() -> tuple[list[str], list[Feladat]]:
    """Visszaadja a választható számlák listáját és a feladatokat."""
    adat = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    feladatok = [
        Feladat(f["id"], f["szoveg"], tuple(Sor(**s) for s in f["megoldas"]))
        for f in adat["feladatok"]
    ]
    return adat["szamlak"], feladatok


def ellenoriz_kulcs(sorok: list[Sor], szamlak: list[str]) -> list[str]:
    """Egy megoldókulcs formai hibái (üres lista = rendben)."""
    hibak = []
    if not sorok:
        hibak.append("Legalább egy tartozik és egy követel sor kell.")
    for s in sorok:
        if s.oldal not in ("T", "K"):
            hibak.append(f"Ismeretlen oldal: {s.oldal}")
        if s.szamla not in szamlak:
            hibak.append(f"Nincs ilyen számla a listában: {s.szamla}")
        if not s.osszeg > 0:
            hibak.append(f"Az összeg legyen pozitív: {s.szamla}")
    t = sum(s.osszeg for s in sorok if s.oldal == "T")
    k = sum(s.osszeg for s in sorok if s.oldal == "K")
    if abs(t - k) > 1e-9:
        hibak.append(f"A tartozik ({t:g}) és a követel ({k:g}) oldal nem egyenlő.")
    return hibak


def hozzaad(szoveg: str, sorok: list[Sor], fajl: Path = DATA_FILE) -> str:
    """Új feladat a fájl végére, a következő szabad azonosítóval. Hibás kulcsnál ValueError."""
    adat = json.loads(fajl.read_text(encoding="utf-8"))
    hibak = ([] if szoveg.strip() else ["A feladat szövege üres."]) + ellenoriz_kulcs(sorok, adat["szamlak"])
    if hibak:
        raise ValueError("; ".join(hibak))
    szamok = [int(f["id"][1:]) for f in adat["feladatok"] if f["id"][1:].isdigit()]
    uj_id = f"F{max(szamok, default=0) + 1:02d}"
    adat["feladatok"].append({"id": uj_id, "szoveg": szoveg.strip(),
                              "megoldas": [{"oldal": s.oldal, "szamla": s.szamla, "osszeg": s.osszeg} for s in sorok]})
    fajl.write_text(json.dumps(adat, ensure_ascii=False, indent=1), encoding="utf-8")
    return uj_id
