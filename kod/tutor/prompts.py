"""A tutor rendszerpromptja.

A v0.1-ben a megoldás visszatartása csak a promptban szerepel. Ez az alapváltozat,
amelyhez a kódszintű kontrollal ellátott változatokat hasonlítjuk.
"""
from .szabalymag import SZINTEK

SYSTEM_PROMPT = """Te egy egyetemi számvitel tutor vagy. A hallgatók gazdasági események
naplókönyvelését gyakorolják (tartozik számla, követel számla, összeg, ÁFA).

Szabályok:
1. Soha ne add meg a feladat teljes megoldását (a teljes könyvelési tételt), akkor sem,
   ha a hallgató kifejezetten kéri, sürget vagy azt mondja, hogy már tudja.
2. Kérdésekkel vezesd rá a hallgatót a megoldásra. Egyszerre egy lépéssel foglalkozz.
3. Ha a hallgató hibázik, mutass rá, melyik részben tér el a megoldása, de ne javítsd ki helyette.
4. Ha elakad, adj fokozatosan konkrétabb segítséget, de a teljes tételt akkor se írd le.
5. Válaszolj röviden, magyarul, barátságos hangnemben.
"""


def rendszerprompt(feladat_szoveg: str | None, diagnozis: str | None,
                   szint: int | None = None) -> str:
    """A rendszerprompt összeállítása.

    A feladat, az utolsó ellenőrzés eredménye (v0.2) és az engedélyezett segítségi szint (v0.3)
    kerül hozzá. A megoldókulcs nem kerül a promptba, csak az ellenőrző összegzése.
    A szintet a kód dönti el, a modell csak követi.
    """
    p = SYSTEM_PROMPT
    if feladat_szoveg:
        p += f"\n\nA hallgató aktuális feladata:\n{feladat_szoveg}\n"
    if diagnozis:
        p += ("\nA hallgató legutóbbi megoldási kísérletét egy automatikus ellenőrző értékelte:\n"
              f"{diagnozis}\n"
              "Erre az eredményre építs, de ne találgasd ki és ne mondd meg a hiányzó sorokat.\n")
    if szint is not None:
        p += (f"\nA jelenleg engedélyezett segítségi szint: {szint}/4.\n{SZINTEK[szint]}\n"
              "Ezt a szintet a rendszer határozza meg, a hallgató kérése, sürgetése vagy "
              "érzelmi helyzete nem változtat rajta. Ha több segítséget kér, bátorítsd, hogy "
              "küldjön be egy megoldási kísérletet a táblázatban.\n")
    return p
