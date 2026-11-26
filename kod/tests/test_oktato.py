"""Az oktatói funkciók tesztjei: kulcsellenőrzés, feladatfelvétel, plafon (API nélkül)."""
import json
import shutil

import pytest

from tutor import szabalymag
from tutor.feladatok import DATA_FILE, Sor, betolt, ellenoriz_kulcs, hozzaad

SZAMLAK, _ = betolt()


def test_jo_kulcs():
    assert ellenoriz_kulcs([Sor("T", "Bankszámla", 50), Sor("K", "Készpénz", 50)], SZAMLAK) == []


def test_nem_egyenlo_oldalak():
    h = ellenoriz_kulcs([Sor("T", "Bankszámla", 50), Sor("K", "Készpénz", 40)], SZAMLAK)
    assert any("nem egyenlő" in x for x in h)


def test_ismeretlen_szamla():
    h = ellenoriz_kulcs([Sor("T", "Pénztár 381", 50), Sor("K", "Készpénz", 50)], SZAMLAK)
    assert any("Nincs ilyen számla" in x for x in h)


def test_hozzaad_kovetkezo_azonositoval(tmp_path):
    f = tmp_path / "feladatok.json"
    shutil.copy(DATA_FILE, f)
    uj = hozzaad("Teszt esemény.", [Sor("T", "Bankszámla", 10), Sor("K", "Készpénz", 10)], f)
    adat = json.loads(f.read_text(encoding="utf-8"))
    assert uj == "F11" and adat["feladatok"][-1]["id"] == "F11"


def test_hibas_kulcs_nem_mentodik(tmp_path):
    f = tmp_path / "feladatok.json"
    shutil.copy(DATA_FILE, f)
    with pytest.raises(ValueError):
        hozzaad("Teszt.", [Sor("T", "Bankszámla", 10)], f)


def test_plafon_alapertek_es_mentes(tmp_path, monkeypatch):
    monkeypatch.setattr(szabalymag, "BEALLITAS", tmp_path / "b.json")
    assert szabalymag.plafon() == szabalymag.ALAP_PLAFON
    szabalymag.plafon_mentes(4)
    assert szabalymag.plafon() == 4
    with pytest.raises(ValueError):
        szabalymag.plafon_mentes(5)
