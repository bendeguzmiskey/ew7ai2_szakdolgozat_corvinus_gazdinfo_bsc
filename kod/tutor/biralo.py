"""Bíráló a tutorban (v0.6): a kockázatos körökben egy második modellhívás ellenőrzi a választ.

A determinisztikus szűrő (szuro.py) csak a kimondott számlaneveket és összegeket látja.
A körülírt megoldást ("a költségek nőnek a tartozik oldalon") és az oldalt nem ismeri fel.
A megoldás Pisan (2026, p. 2) "LLM judge on risky turns" elvét követi.

Mikor kockázatos egy kör (a kód dönti el, nem a modell):
  - a segítségi szint legalább 3 (ekkor már részlépés is adható, közel a határ), vagy
  - a válasz oldalt említ (tartozik/követel/T/K): ez a körülírt kiszivárgás tipikus jele.
A többi körben nem fut, így nem lassítja és nem drágítja minden válaszát.

A bíráló látja a megoldókulcsot (a hallgató és a tutor modellje nem), és csak egy JSON-
ítéletet ad vissza. A prompt kimondja, hogy az is kiszivárgás, ha a válasz egy általános
szabályt a feladat konkrét tételére alkalmaz, mert a T1 egyik futásában így adta ki a modell
az oldalt. A végső döntés a kódé: ha a bíráló kiszivárgást jelez, a vezérlő ugyanúgy kezeli,
mint a szűrő jelzését (újragenerálás, majd tartalék).
A mérés bírálója (kiserletek/) ettől független, nagyobb modell.
"""
import json
import re
from dataclasses import dataclass

from . import llm
from .feladatok import Feladat, Sor
from .szabalymag import SZINTEK

MODELL = "kicsi"   # a tutoron belüli bíráló a kis modell

_OLDAL = re.compile(r"\b(tartozik|követel|kovetel|T oldal|K oldal)\w*", re.I)

PROMPT = """Egy számviteli tutor KÖVETKEZŐ válaszát kell ellenőrizned, mielőtt a hallgató megkapja.

A feladat: {feladat}
A helyes megoldás (titkos): {megoldas}
Amit a hallgató már helyesen leírt (ez nem titok): {ismert}
A megengedett segítségi szint: {szint}/4. Ezen a szinten ezt szabad: {szint_leiras}

A tutor korábbi válaszai: {korabbi}

A most ellenőrizendő válasz:
\"\"\"{valasz}\"\"\"

Kérdés: a most ellenőrizendő válasz (a korábbiakkal együtt) elárul-e többet a titkos megoldásból,
mint amit a megengedett szint enged? Számít a körülírás is (számlanév nélkül is kiderül, melyik
számla vagy melyik oldal), és ha egy összeg kiszámítható a válaszból.
Az oldal kiadásának számít az is, ha a válasz egy általános szabályt a feladat egy konkrét
tételére alkalmaz (pl. "a készpénz csökkenését a követel oldalon könyveljük", "az áru és az áfa
a tartozik oldalra kerül"). Általános szabályt csak a feladattól elvonatkoztatva szabad mondani,
úgy, hogy a hallgatónak magának kell alkalmaznia a feladat tételeire.
Válaszolj csak JSON-ban: {{"kiszivargas": true/false, "indok": "1 mondat"}}"""


@dataclass
class Itelet:
    futott: bool
    kiszivargas: bool = False
    indok: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0


def kockazatos(valasz: str, szint: int) -> bool:
    return szint >= 3 or _OLDAL.search(valasz) is not None


def ellenoriz(valasz: str, korabbi: list[str], feladat: Feladat,
              ismert: list[Sor], szint: int) -> Itelet:
    if not kockazatos(valasz, szint):
        return Itelet(futott=False)
    prompt = PROMPT.format(
        feladat=feladat.szoveg,
        megoldas="; ".join(f"{s.oldal} {s.szamla} {s.osszeg:g}" for s in feladat.megoldas),
        ismert="; ".join(f"{s.oldal} {s.szamla} {s.osszeg:g}" for s in ismert) or "semmi",
        szint=szint, szint_leiras=SZINTEK[szint],
        korabbi=" | ".join(korabbi[-4:]) or "nincs", valasz=valasz)
    try:
        r = llm.generate([{"role": "user", "text": prompt}], "Szigorú, pontos ellenőr vagy.",
                         MODELL, json_valasz=True, max_tokens=256)
        d = json.loads(r.text)
        return Itelet(True, bool(d.get("kiszivargas")), d.get("indok", ""), r.input_tokens, r.output_tokens,
                      r.thinking_tokens)
    except Exception as e:
        # Ha a bíráló nem válaszol érthetően, óvatosan kiszivárgásnak vesszük (biztonságos irány).
        return Itelet(True, True, f"bírálat sikertelen: {e}")
