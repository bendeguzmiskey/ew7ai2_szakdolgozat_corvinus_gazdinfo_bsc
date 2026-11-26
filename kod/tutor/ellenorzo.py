"""Determinisztikus ellenőrző: a hallgató kísérletét összeveti a megoldókulccsal.

Nincs benne nyelvi modell. Ugyanarra a bemenetre mindig ugyanazt adja,
ezért erre a jelre épülhet a szabálymag (Pisan, 2026, P3).
"""
from dataclasses import dataclass, field

from .feladatok import Sor

TOLERANCIA = 0.01  # kerekítési hiba összegeknél (eFt)


@dataclass
class Diagnozis:
    statusz: str                                   # "helyes" | "részben helyes" | "hibás"
    jo_sorok: list[Sor] = field(default_factory=list)
    rossz_oldal: list[Sor] = field(default_factory=list)   # számla és összeg jó, az oldal nem
    rossz_osszeg: list[Sor] = field(default_factory=list)  # számla és oldal jó, az összeg nem
    felesleges: list[Sor] = field(default_factory=list)    # nincs ilyen sor a megoldásban
    hianyzo_db: int = 0                            # ennyi megoldássor hiányzik (a tartalmát nem adjuk ki)
    egyensulyban: bool = True                      # T összeg = K összeg?

    def osszegzes_hallgatonak(self) -> str:
        """Rövid visszajelzés, amely nem árulja el a hiányzó sorok tartalmát."""
        if self.statusz == "helyes":
            return "A tétel helyes."
        reszek = []
        if self.jo_sorok:
            reszek.append(f"{len(self.jo_sorok)} sor helyes")
        if self.rossz_oldal:
            reszek.append(f"{len(self.rossz_oldal)} sor rossz oldalon van")
        if self.rossz_osszeg:
            reszek.append(f"{len(self.rossz_osszeg)} sornál hibás az összeg")
        if self.felesleges:
            reszek.append(f"{len(self.felesleges)} sor nem tartozik ide")
        if self.hianyzo_db:
            reszek.append(f"{self.hianyzo_db} sor hiányzik")
        if not self.egyensulyban:
            reszek.append("a tartozik és a követel oldal összege nem egyezik")
        return "A tétel még nem helyes: " + ", ".join(reszek) + "."


def _egyenlo(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCIA


def ellenoriz(kiserlet: list[Sor], megoldas: tuple[Sor, ...]) -> Diagnozis:
    """Összeveti a kísérlet sorait a megoldás soraival.

    Lépések:
    1. pontos egyezések (oldal, számla, összeg) kivétele mindkét oldalról;
    2. a maradékból: ugyanaz a számla és összeg, de más oldal → rossz oldal;
    3. a maradékból: ugyanaz a számla és oldal, de más összeg → rossz összeg;
    4. ami a kísérletből marad: felesleges; ami a megoldásból marad: hiányzó.
    """
    d = Diagnozis(statusz="hibás")
    maradek_k = list(kiserlet)
    maradek_m = list(megoldas)

    def parosit(feltetel, cel: list[Sor]):
        for s in list(maradek_k):
            for m in maradek_m:
                if feltetel(s, m):
                    cel.append(s)
                    maradek_k.remove(s)
                    maradek_m.remove(m)
                    break

    parosit(lambda s, m: s.oldal == m.oldal and s.szamla == m.szamla and _egyenlo(s.osszeg, m.osszeg), d.jo_sorok)
    parosit(lambda s, m: s.oldal != m.oldal and s.szamla == m.szamla and _egyenlo(s.osszeg, m.osszeg), d.rossz_oldal)
    parosit(lambda s, m: s.oldal == m.oldal and s.szamla == m.szamla, d.rossz_osszeg)

    d.felesleges = maradek_k
    d.hianyzo_db = len(maradek_m)

    t = sum(s.osszeg for s in kiserlet if s.oldal == "T")
    k = sum(s.osszeg for s in kiserlet if s.oldal == "K")
    d.egyensulyban = _egyenlo(t, k)

    if len(d.jo_sorok) == len(megoldas) and not d.felesleges:
        d.statusz = "helyes"
    elif d.jo_sorok or d.rossz_oldal or d.rossz_osszeg:
        d.statusz = "részben helyes"
    return d
