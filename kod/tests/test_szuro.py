"""A kiszivárgás-szűrő tesztjei (F02: irodaszer 200 + 25% ÁFA készpénzért)."""
from tutor import szuro
from tutor.feladatok import Sor, betolt

_, FELADATOK = betolt()
F02 = next(f for f in FELADATOK if f.id == "F02")


def test_titkos_elemek_f02():
    szamlak, osszegek = szuro.titkos_elemek(F02, [])
    # A "Készpénz" szerepel a feladatszövegben ("készpénzért"), a 200 is, ezért nem titkos.
    assert szamlak == {"Adminisztratív ráfordítások", "Előzetes áfa"}
    assert osszegek == {50, 250}


def test_kerdes_atmegy_1_szinten():
    e = szuro.ellenoriz("Szerinted mi történik a cég készpénzével?", [], F02, [], szint=1)
    assert e.rendben


def test_osszeg_tilos_1_szinten():
    e = szuro.ellenoriz("Az ÁFA itt 50 eFt lesz.", [], F02, [], szint=1)
    assert not e.rendben and e.titkos_osszegek == ["50"]


def test_szamlanev_megengedett_2_szinten_osszeg_nem():
    assert szuro.ellenoriz("Gondolj az előzetes áfa szerepére!", [], F02, [], szint=2).rendben
    assert not szuro.ellenoriz("A bruttó összeg 250.", [], F02, [], szint=2).rendben


def test_apronkent_kicsalt_megoldas_osszesitve():
    korabbi = ["Az irodaszer adminisztratív ráfordítás.", "Az előzetes áfa 50 eFt."]
    e = szuro.ellenoriz("A készpénz 250-nel csökken.", korabbi, F02, [], szint=4)
    assert not e.rendben and "teljes megoldás" in e.indok


def test_amit_a_hallgato_mar_leirt_az_nem_titkos():
    helyes = [Sor("T", "Előzetes áfa", 50)]
    e = szuro.ellenoriz("Igen, az előzetes áfa 50, ez stimmel.", [], F02, helyes, szint=1)
    assert e.rendben


def test_a_feladat_ragozott_szava_nem_titok():
    f = {x.id: x for x in betolt()[1]}
    szamlak, _ = szuro.titkos_elemek(f["F01"], [])
    assert "Áruk" not in szamlak
    assert {"Előzetes áfa", "Szállítók"} <= szamlak
    assert szuro.ellenoriz("Hova kerül az áru a raktárból?", [], f["F01"], [], 1).rendben
    assert not szuro.ellenoriz("Gondolj a szállító felé fennálló tartozásra.", [], f["F01"], [], 1).rendben
