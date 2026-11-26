"""A bíráló indítási szabályának tesztjei (a kód dönti el, mikor fut, API nélkül)."""
from tutor import biralo


def test_alacsony_szinten_oldal_nelkul_nem_fut():
    assert not biralo.kockazatos("Mit gondolsz, mi változik a cégnél?", szint=1)


def test_oldalemlites_kockazatos():
    assert biralo.kockazatos("Ez a tartozik oldalon nő.", szint=1)
    assert biralo.kockazatos("Melyik oldalra kerül: Követel?", szint=2)


def test_magas_szint_mindig_kockazatos():
    assert biralo.kockazatos("Gondold végig még egyszer.", szint=3)


def test_nem_kockazatos_korben_nincs_hivas():
    it = biralo.ellenoriz("Mit gondolsz?", [], feladat=None, ismert=[], szint=1)
    assert not it.futott and not it.kiszivargas
