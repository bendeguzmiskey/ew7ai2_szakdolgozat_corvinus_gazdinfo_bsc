"""A visszakereső tesztjei, API nélkül: egy egyszerű szózsák-beágyazással."""
import re

from tutor import rag

SZOTAR = ["elozetes", "fizetendo", "afa", "szamla", "tartozik", "kovetel", "raford", "aru", "elabe", "bank"]


def _ascii(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def hamis_beagyazo(szovegek, _feladat):
    return [[float(len(re.findall(sz, _ascii(t)))) + 1e-6 for sz in SZOTAR] for t in szovegek]


def test_szakaszok_beolvasasa():
    sz = rag.szakaszok()
    assert len(sz) == 12 and sz[0].id == "J1" and sz[5].cim == "Előzetes áfa"
    assert all("ELLENŐRIZENDŐ" not in s.szoveg for s in sz)  # a megjegyzés nem kerül be


def test_kereses_a_relevans_szakaszt_hozza():
    v = rag.Visszakereso(beagyazo=hamis_beagyazo, cache=None)
    ids = [s.id for s in v.keres("Mi az az előzetes áfa?")]
    assert "J6" in ids


def test_forras_csak_visszakeresett_szakaszra():
    v = rag.Visszakereso(beagyazo=hamis_beagyazo, cache=None)
    tal = [s for s in v.szakaszok if s.id in ("J3", "J6")]
    szoveg, forr = rag.forrasok("Gondold végig, melyik oldal nő. [J3] [J9]", tal)
    assert forr == ["J3"]                      # a J9-et nem kerestük vissza, nem fogadjuk el
    assert "[J" not in szoveg.split("*Forrás")[0]
    assert "J3 Melyik oldalra" in szoveg


def test_hivatkozas_nelkul_nincs_forrassor():
    szoveg, forr = rag.forrasok("Mit gondolsz, mi változik?", [])
    assert forr == [] and "Forrás" not in szoveg


def test_forrassor_nem_adja_ki_a_titkos_szamlat():
    from tutor import szuro
    from tutor.feladatok import Sor, betolt
    f = {x.id: x for x in betolt()[1]}["F04"]
    tal = [x for x in rag.szakaszok() if x.id in ("J5", "J7")]
    rejt = lambda cim: szuro.titkos_szamlat_nevez(cim, f, [])
    szoveg, forr = rag.forrasok("Gondold végig. [J7] [J5]", tal, rejt)
    assert "Fizetendő" not in szoveg and "J7" in szoveg and "J5 Összegek" in szoveg
    assert forr == ["J7", "J5"]
    # ha a hallgató már helyesen leírta a sort, a cím megjelenhet
    ismert = [Sor("K", "Fizetendő áfa", 75)]
    szoveg, _ = rag.forrasok("Gondold végig. [J7]", tal,
                             lambda cim: szuro.titkos_szamlat_nevez(cim, f, ismert))
    assert "J7 Fizetendő áfa" in szoveg
