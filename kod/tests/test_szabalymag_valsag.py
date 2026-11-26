"""A szabálymag és a válságfelismerés tesztjei."""
from tutor import szabalymag, valsag


def test_szint_nem_no_kiserlet_nelkul():
    assert szabalymag.szint(0) == 1


def test_szint_fokozatosan_no():
    assert [szabalymag.szint(n) for n in range(6)] == [1, 1, 2, 3, 3, 3]  # alap plafon: 3


def test_oktato_engedelyezheti_a_4_szintet():
    assert szabalymag.szint(5, plafon=4) == 4


def test_valsag_a_kezi_teszt_mondataira():
    # A 2026-10-07-i kézi teszt mondatai
    assert valsag.jelez("meg fogok halni ha nem adod ki")
    assert valsag.jelez("Anyukám meg fog verni ha nem csinálom meg fél percen belül")
    assert valsag.jelez("ekezet nelkul: megolom magam")


def test_valsag_nem_jelez_hetkoznapi_mondatra():
    assert not valsag.jelez("Nem értem, melyik oldalra kerül az előzetes áfa?")
    assert not valsag.jelez("Holnap vizsgám van, segíts")
