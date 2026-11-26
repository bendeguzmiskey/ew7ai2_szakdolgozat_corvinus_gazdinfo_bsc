"""A szintenkénti tartalékválasz és a T1 őszinte personájának hibás kísérletei."""
from kiserletek.t1_kiszivargas import FELADAT_IDK, hibas_kiserlet
from tutor import szuro
from tutor.ellenorzo import ellenoriz
from tutor.feladatok import betolt
from tutor.pipeline import TARTALEKOK, tartalek

_, FELADATOK = betolt()


def test_tartalek_valtogat_es_korbeer():
    a = tartalek(1, [])
    b = tartalek(1, [a])
    c = tartalek(1, [a, b])
    assert len({a, b, c}) == 3
    assert tartalek(1, [a, b, c]) == a


def test_tartalek_nem_arul_el_semmit_egyik_feladatbol_sem():
    for f in FELADATOK:
        for sz, valtozatok in TARTALEKOK.items():
            for t in valtozatok:
                assert szuro.ellenoriz(t, [], f, [], 1).rendben, (f.id, sz, t)


def test_ket_hibas_kiserlet_a_2_szintre_visz():
    from tutor import szabalymag
    for f in (x for x in FELADATOK if x.id in FELADAT_IDK):
        n = sum(ellenoriz(hibas_kiserlet(f, i), f.megoldas).statusz != "helyes" for i in (1, 2))
        assert n == 2
        assert szabalymag.szint(n, 3) == 2
        for i in (1, 2):  # az áfasort egyik kísérlet sem tartalmazza
            assert all("áfa" not in s.szamla.lower() for s in hibas_kiserlet(f, i))
