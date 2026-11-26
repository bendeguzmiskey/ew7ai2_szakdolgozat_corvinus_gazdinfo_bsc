"""Szabálymag: eldönti, mekkora segítség adható ebben a körben.

A döntés csak megbízható adatokból születik: a sikertelen megoldási kísérletek
számából és az oktatói plafonból. A hallgató chatüzeneteit nem olvassa, így a hallgató
nem tudja rábeszélni a rendszert több segítségre (Pisan, 2026, P2).
"""
import json
from pathlib import Path

# A segítségi szintek leírása: ezt kapja meg a modell utasításként.
SZINTEK = {
    1: ("Csak kérdezhetsz. Ne nevezz meg számlát, oldalt vagy összeget, amelyet a hallgató "
        "még nem írt le. Kérdésekkel indítsd el a gondolkodását (mi változik, mi nő, mi csökken)."),
    2: ("Rámutathatsz, melyik részben hibás a kísérlete (az ellenőrző eredménye alapján), és "
        "elmagyarázhatsz általános fogalmakat (pl. mi az előzetes áfa). Konkrét számlát, oldalt "
        "vagy összeget a megoldásból továbbra sem mondhatsz."),
    3: ("Megadhatsz egyetlen részlépést: egy hiányzó vagy hibás sor EGY elemét (vagy a számla "
        "nevét, vagy az oldalát, vagy az összegét). Teljes sort nem adhatsz meg."),
    4: ("Megadhatsz legfeljebb egy teljes tételsort (oldal, számla, összeg). A teljes könyvelési "
        "tételt (az összes sort) soha nem írhatod le."),
}

ALAP_PLAFON = 3  # a 4. szintet csak az oktató engedélyezheti

# Az oktató a felületen állítja a plafont, a beállítás fájlban marad meg.
BEALLITAS = Path(__file__).resolve().parent.parent / "data" / "beallitasok.json"


def plafon() -> int:
    """Az oktató által beállított plafon (ha nincs beállítva: ALAP_PLAFON)."""
    try:
        return int(json.loads(BEALLITAS.read_text(encoding="utf-8"))["plafon"])
    except (FileNotFoundError, KeyError, ValueError):
        return ALAP_PLAFON


def plafon_mentes(ertek: int) -> None:
    if ertek not in (1, 2, 3, 4):
        raise ValueError("A plafon 1 és 4 közötti egész szám.")
    BEALLITAS.write_text(json.dumps({"plafon": ertek}), encoding="utf-8")


def szint(sikertelen_kiserletek: int, plafon: int = ALAP_PLAFON) -> int:
    """0-1 sikertelen kísérlet → 1. szint, 2 → 2., 3 → 3., 4 vagy több → 4. szint,
    de soha nem a plafon fölött.

    Indok: a segítség csak akkor nőhet, ha a hallgató tényleg próbálkozott
    (Wood et al., 1976, p. 98: a tutor a tanuló képességeihez igazítja a segítséget,
    a túl korai segítség függést okoz). Már az első sikertelen kísérlet után is
    az 1. szinten maradunk, hogy legyen még egy esélye segítség nélkül.
    """
    javasolt = 1 + max(0, sikertelen_kiserletek - 1)
    return max(1, min(javasolt, plafon, 4))
