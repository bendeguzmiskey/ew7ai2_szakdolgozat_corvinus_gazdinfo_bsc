"""Az ellenőrző tesztjei.  Futtatás:  .venv/bin/python -m pytest -q"""
from tutor.ellenorzo import ellenoriz
from tutor.feladatok import Sor, betolt

MEGOLDAS = (Sor("T", "Áruk", 100), Sor("T", "Előzetes áfa", 25), Sor("K", "Szállítók", 125))


def test_helyes_sorrendtol_fuggetlenul():
    d = ellenoriz([Sor("K", "Szállítók", 125), Sor("T", "Áruk", 100), Sor("T", "Előzetes áfa", 25)], MEGOLDAS)
    assert d.statusz == "helyes"


def test_bruttó_aru_afa_nelkul():
    # A v0.1 tutor által is elkövetett hiba: az áru bruttó értéken, ÁFA külön sor nélkül.
    d = ellenoriz([Sor("T", "Áruk", 125), Sor("K", "Szállítók", 125)], MEGOLDAS)
    assert d.statusz == "részben helyes"
    assert len(d.rossz_osszeg) == 1 and d.hianyzo_db == 1


def test_felcserelt_oldalak():
    d = ellenoriz([Sor("K", "Áruk", 100), Sor("K", "Előzetes áfa", 25), Sor("T", "Szállítók", 125)], MEGOLDAS)
    assert len(d.rossz_oldal) == 3 and d.statusz == "részben helyes"


def test_teljesen_rossz():
    d = ellenoriz([Sor("T", "Készpénz", 10), Sor("K", "Bankszámla", 10)], MEGOLDAS)
    assert d.statusz == "hibás" and d.hianyzo_db == 3 and len(d.felesleges) == 2


def test_nem_arulja_el_a_hianyzo_szamlat():
    d = ellenoriz([Sor("T", "Áruk", 100)], MEGOLDAS)
    szoveg = d.osszegzes_hallgatonak()
    assert "Szállítók" not in szoveg and "Előzetes áfa" not in szoveg


def test_minden_megoldokulcs_egyensulyban():
    # Adatminőség: minden megoldásban T összeg = K összeg, és csak ismert számla szerepel.
    szamlak, feladatok = betolt()
    for f in feladatok:
        t = sum(s.osszeg for s in f.megoldas if s.oldal == "T")
        k = sum(s.osszeg for s in f.megoldas if s.oldal == "K")
        assert abs(t - k) < 0.01, f.id
        assert all(s.szamla in szamlak for s in f.megoldas), f.id
