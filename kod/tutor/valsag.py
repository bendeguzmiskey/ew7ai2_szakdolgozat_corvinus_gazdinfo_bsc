"""Válságkezelés (NF6): önsértésre vagy veszélyre utaló üzenet felismerése.

Kulcsszavas felismerés, nyelvi modell nélkül, így determinisztikus és tesztelhető.
Inkább legyen túl érzékeny, mint hogy elmulasszon egy valódi vészhelyzetet.
Ha jelez, a rendszer kilép a tutorszerepből, és a nyelvi modell meg sem hívódik,
így érzelmi nyomásra sem szivároghat ki a megoldás.

Korlát: a kulcsszólista nem teljes, és nem minden helyesírási változatot fog meg.
"""
import re
import unicodedata

# Ékezet nélkül: az üzenetet és a mintát is ékezettelenítjük az illesztés előtt.
MINTAK = [
    r"meg ?fogok halni", r"meghalok", r"megolom magam", r"ongyilk",
    r"nem akarok (tovabb )?elni", r"bantom magam", r"vegzek magammal",
    r"megvert?", r"meg ?fog verni", r"bant(anak|ani fog)",
]

VALASZ = (
    "Most félreteszem a feladatot, mert amit írtál, az fontosabb.\n\n"
    "Ha veszélyben érzed magad, vagy azon gondolkodsz, hogy bántod magad, kérlek, beszélj "
    "valakivel most:\n"
    "- **Lelki Elsősegély Telefonszolgálat: 116-123** (ingyenes, éjjel-nappal hívható)\n"
    "- **Közvetlen veszély esetén: 112**\n\n"
    "Egy tanár vagy egy barát is segíthet. A feladat megvár, a megoldás nem éri meg, hogy "
    "emiatt bajod essen."
)


def _normal(szoveg: str) -> str:
    """Kisbetűsít és ékezetteleníti a szöveget, hogy a minták ékezet nélkül is illeszkedjenek."""
    s = unicodedata.normalize("NFKD", szoveg.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def jelez(uzenet: str) -> bool:
    n = _normal(uzenet)
    return any(re.search(_normal(m), n) for m in MINTAK)
