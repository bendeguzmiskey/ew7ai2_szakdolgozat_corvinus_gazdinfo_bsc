"""Kiszivárgás-szűrő (v0.5): a modell válaszát kiküldés előtt, kódból ellenőrzi.

A v0.3-ban a szintet már a kód döntötte el, de a modell nem mindig tartotta be.

Titkos megoldáselem:
  - a megoldókulcs olyan számlája, amely nem szerepel a feladat szövegében,
    és amelyet a hallgató még nem írt le helyesen;
  - a megoldókulcs olyan összege, amely nem szerepel a feladat szövegében
    (pl. az áfa és a bruttó összeg), és a hallgató még nem írta le.

Szabályok szintenként (a szabálymag szintje alapján):
  1. szint: semmilyen titkos elem nem jelenhet meg
  2. szint: titkos számlanév megjelenhet (fogalommagyarázat), titkos összeg nem
  3. szint: számlanevek és legfeljebb egy titkos összeg a beszélgetés során
  4. szint: számlanevek és összegek is, de a teljes tétel nem
Minden szinten: a beszélgetés egészében (az eddigi tutorválaszokkal együtt) sem
állhat össze a teljes megoldás (az apránkénti kicsalás ellen).

Korlát: a körülírt megoldást (számlanév és szám nélkül, pl. "a költségek nőnek a
tartozik oldalon") nem ismeri fel, és a T/K oldalt sem ellenőrzi. Ezért a mérésnél
nem ezt a szűrőt használjuk mércének, hanem egy független bírálót (lásd kiserletek/).
"""
import re
import unicodedata
from dataclasses import dataclass, field

from .feladatok import Feladat, Sor

# Számlánként a felismerendő szótövek (ékezet nélkül, kisbetűvel)
SZOTOVEK = {
    "Áruk": ["aru "],  # szóköz: hogy az "árut", "áruk" tő ne egyezzen minden "áru"-val
    "Előzetes áfa": ["elozetes"],
    "Fizetendő áfa": ["fizetendo"],
    "Szállítók": ["szallito"],
    "Vevők": ["vevo"],
    "Bankszámla": ["bankszamla"],
    "Készpénz": ["keszpenz", "penztar"],
    "Adminisztratív ráfordítások": ["adminisztrat"],
    "Értékesítési ráfordítások": ["ertekesitesi raford"],
    "ELÁBÉ": ["elabe", "eladott aruk beszerzesi"],
    "Értékesítés nettó árbevétele": ["arbevetel"],
    "Gépek, járművek": ["gepek", "jarmu"],
    "Rövid lejáratú hitel": ["rovid lejaratu"],
    "Hosszú lejáratú hitel": ["hosszu lejaratu"],
}

# A feladat szövegében a számla ragozott alakban is szerepelhet: ami ott van, az nem titok.
# A válaszra illesztett "aru " minta az "árut" szót nem fogja meg, ezért itt külön kell.
FELADATBAN = {"Áruk": ["arut", "aruk"]}


def _normal(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _tovek(szamla: str) -> list[str]:
    return SZOTOVEK.get(szamla, [_normal(szamla)])


def _van_szamla(szoveg_n: str, szamla: str) -> bool:
    return any(t in szoveg_n for t in _tovek(szamla))


def _feladatban_van(feladat_n: str, szamla: str) -> bool:
    return _van_szamla(feladat_n, szamla) or any(t in feladat_n for t in FELADATBAN.get(szamla, []))


def _van_osszeg(szoveg: str, osszeg: float) -> bool:
    o = f"{osszeg:g}"
    return re.search(rf"(?<![\d.,]){re.escape(o)}(?![\d])", szoveg) is not None


@dataclass
class SzuroEredmeny:
    rendben: bool
    indok: str = ""
    titkos_szamlak: list[str] = field(default_factory=list)   # a válaszban (vagy összesítve) talált titkos számlák
    titkos_osszegek: list[str] = field(default_factory=list)


def titkos_elemek(feladat: Feladat, hallgato_helyes_sorai: list[Sor]) -> tuple[set[str], set[float]]:
    """Mely számlák és összegek számítanak még titkosnak ennél a feladatnál."""
    feladat_n = _normal(feladat.szoveg)
    ismert_szamlak = {s.szamla for s in hallgato_helyes_sorai}
    ismert_osszegek = {s.osszeg for s in hallgato_helyes_sorai}
    szamlak = {s.szamla for s in feladat.megoldas
               if s.szamla not in ismert_szamlak and not _feladatban_van(feladat_n, s.szamla)}
    osszegek = {s.osszeg for s in feladat.megoldas
                if s.osszeg not in ismert_osszegek and not _van_osszeg(feladat.szoveg, s.osszeg)}
    return szamlak, osszegek


def titkos_szamlat_nevez(szoveg: str, feladat: Feladat, hallgato_helyes_sorai: list[Sor]) -> bool:
    """Szerepel-e a szövegben a megoldás olyan számlája, amely még titkos?"""
    n = _normal(szoveg)
    return any(_van_szamla(n, s) for s in titkos_elemek(feladat, hallgato_helyes_sorai)[0])


def ellenoriz(valasz: str, korabbi_tutor_valaszok: list[str], feladat: Feladat,
              hallgato_helyes_sorai: list[Sor], szint: int) -> SzuroEredmeny:
    szamlak, osszegek = titkos_elemek(feladat, hallgato_helyes_sorai)
    v_n = _normal(valasz)
    most_szamla = sorted(s for s in szamlak if _van_szamla(v_n, s))
    most_osszeg = sorted(f"{o:g}" for o in osszegek if _van_osszeg(valasz, o))

    # Összesítve a beszélgetésben (apránkénti kicsalás)
    egesz = " ".join(korabbi_tutor_valaszok + [valasz])
    e_n = _normal(egesz)
    ossz_szamla = {s for s in szamlak if _van_szamla(e_n, s)}
    ossz_osszeg = {o for o in osszegek if _van_osszeg(egesz, o)}

    if (szamlak or osszegek) and ossz_szamla == szamlak and ossz_osszeg == osszegek:
        return SzuroEredmeny(False, "A beszélgetésben összeállna a teljes megoldás.",
                             sorted(ossz_szamla), sorted(f"{o:g}" for o in ossz_osszeg))
    if szint == 1 and (most_szamla or most_osszeg):
        return SzuroEredmeny(False, "Az 1. szinten nem nevezhető meg a megoldás számlája vagy összege.",
                             most_szamla, most_osszeg)
    if szint == 2 and most_osszeg:
        return SzuroEredmeny(False, "A 2. szinten nem adható meg a megoldás összege.", most_szamla, most_osszeg)
    if szint == 3 and len(ossz_osszeg) > 1:
        return SzuroEredmeny(False, "A 3. szinten legfeljebb egy összeg adható meg.",
                             most_szamla, most_osszeg)
    return SzuroEredmeny(True)
