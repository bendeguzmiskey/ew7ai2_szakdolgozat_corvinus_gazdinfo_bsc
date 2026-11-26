"""A vezérlő (orchestrator): egy chatkör teljes útja a hallgató üzenetétől a válaszig.

A Streamlit felület és az automatikus tesztek is ezt hívják, így ugyanazt a
logikát mérjük, amit a hallgató használ.

Egy kör:
  1. válságfelismerés (szabály)  → ha jelez: rögzített válasz, LLM nélkül
  2. segítségi szint (szabálymag) → csak a sikertelen kísérletek számából
  3. visszakeresés (RAG) → a jegyzet legrelevánsabb szakaszai
  4. rendszerprompt összeállítása: szabályok + feladat + ellenőrzési eredmény + szint + jegyzet
  5. LLM-hívás
  6. kiszivárgás-szűrő, majd a kockázatos körökben bíráló → ha bármelyik
     elbukik: egy újragenerálás figyelmeztetéssel, ha az is elbukik: rögzített tartalék válasz
  7. forrásjelölés: csak a ténylegesen visszakeresett szakaszokra hivatkozhat
  8. naplózás
"""
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import biralo, config, llm, rag, szabalymag, szuro, valsag
from .feladatok import Sor, betolt
from .prompts import rendszerprompt

_FELADATOK = {f.id: f for f in betolt()[1]}

# Tartalékválaszok szintenként: a szintnek megfelelő, általános rávezető kérdés az elutasítás
# helyett (Pisan, 2026, P4). Nincs benne LLM és semmi a feladatból (számla, oldal, összeg),
# így nem szivároghat ki vele semmi. A vezérlő sorban váltogatja őket, hogy ne ismételje magát.
TARTALEKOK = {
    1: [
        "Ezt most nem mondhatom meg konkrétan, de segítek elindulni. Mi történt a cégnél ebben az "
        "eseményben: mit kapott, és mit adott vagy vállalt érte cserébe?",
        "Gondold végig az érintett tételek jellegét: melyik eszköz (E), melyik forrás (F), melyik "
        "ráfordítás (R) vagy bevétel (B)? Mindegyiknél: nő vagy csökken?",
        "Próbáld meg leírni a saját szavaiddal, mi változik a cég vagyonában. Ha van egy ötleted, "
        "írd be a táblázatba, és az ellenőrzés után pontosabban tudok segíteni.",
    ],
    2: [
        "Nézd meg az ellenőrzés visszajelzését, és azt a részt gondold újra, amelyet hibásnak jelzett. "
        "Ha egy fogalom nem világos, kérdezz rá, azt el tudom magyarázni.",
        "Vedd sorra a kísérleted sorait: mindegyiknél gondold végig a számla jellegét (E, F, R, B), "
        "és hogy a változás növekedés vagy csökkenés. Melyik sornál vagy bizonytalan?",
    ],
    3: [
        "Válaszd ki a kísérletedből azt az egy sort, amelyben a legbizonytalanabb vagy, és kérdezz "
        "rá konkrétan. Abban az egy sorban tudok egy lépéssel tovább segíteni.",
        "Nézd meg az ellenőrzés visszajelzését: melyik sor hibás vagy hiányzik? Arra az egy sorra "
        "kérdezz rá, és abban segítek.",
    ],
}
TARTALEKOK[4] = TARTALEKOK[3]


def tartalek(szint: int, korabbi: list[str]) -> str:
    """A szintnek megfelelő tartalékválasz; a már kiküldötteket sorban váltogatja."""
    valtozatok = TARTALEKOK[szint]
    eddig = sum(t in valtozatok for t in korabbi)
    return valtozatok[eddig % len(valtozatok)]


NAPLO_DIR = Path(__file__).resolve().parent.parent / "naplo"

_visszakereso: rag.Visszakereso | None = None


def _rag() -> rag.Visszakereso:
    """Csak az első használatkor töltjük be (a jegyzet beágyazása API-hívás)."""
    global _visszakereso
    if _visszakereso is None:
        _visszakereso = rag.Visszakereso()
    return _visszakereso


@dataclass
class Allapot:
    """Egy munkamenet (egy hallgató, egy feladat) megbízható állapota."""
    feladat_id: str
    feladat_szoveg: str
    sikertelen_kiserletek: int = 0
    utolso_diagnozis: str | None = None
    plafon: int = field(default_factory=szabalymag.plafon)  # az oktató beállítása
    helyes_sorok: list[Sor] = field(default_factory=list)  # amit a hallgató már helyesen leírt
    munkamenet_id: str = field(default_factory=lambda: time.strftime("%Y%m%d-%H%M%S"))


@dataclass
class Valasz:
    szoveg: str
    szint: int | None
    valsag: bool
    model_version: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    szuro: str = "nem futott"   # "átment" | "újragenerálva" | "tartalék" | "nem futott"
    szuro_indok: str = ""
    biralo: str = "nem futott"  # "átment" | "megfogta" | "nem futott" (az utolsó vázlatra)
    jegyzet: list[str] = field(default_factory=list)   # visszakeresett szakaszok
    forrasok: list[str] = field(default_factory=list)  # amire a válasz ténylegesen hivatkozott


def valaszol(history: list[dict], allapot: Allapot, model_key: str = config.DEFAULT_MODEL,
             naplo: bool = True, szuro_be: bool = True, rag_be: bool = True,
             biralo_be: bool = True) -> Valasz:
    """A kapcsolók a kísérleti összehasonlításhoz:
    v0.3 = szuro_be, rag_be, biralo_be mind False; v0.5 = rag_be és biralo_be False;
    v0.6 (a teljes rendszer) = minden True."""
    utolso = history[-1]["text"]

    if valsag.jelez(utolso):
        v = Valasz(szoveg=valsag.VALASZ, szint=None, valsag=True)
    else:
        sz = szabalymag.szint(allapot.sikertelen_kiserletek, allapot.plafon)
        prompt = rendszerprompt(allapot.feladat_szoveg, allapot.utolso_diagnozis, sz)
        talalatok = _rag().keres(f"{allapot.feladat_szoveg}\n{utolso}") if rag_be else []
        prompt += rag.promptresz(talalatok)
        r = llm.generate(history, prompt, model_key)
        v = Valasz(r.text, sz, False, r.model_version, r.input_tokens, r.output_tokens)
        v.thinking_tokens = r.thinking_tokens
        v.jegyzet = [t.id for t in talalatok]
        if szuro_be:
            v = _szurt(v, history, allapot, prompt, model_key, biralo_be)
        if v.szuro != "tartalék":
            feladat = _FELADATOK[allapot.feladat_id]
            v.szoveg, v.forrasok = rag.forrasok(
                v.szoveg, talalatok,
                lambda cim: szuro.titkos_szamlat_nevez(cim, feladat, allapot.helyes_sorok))

    if naplo:
        _naploz(allapot, utolso, v)
    return v


def _vizsgal(szoveg: str, korabbi: list[str], allapot: Allapot, szint: int,
            biralo_be: bool, v: Valasz) -> tuple[bool, str]:
    """Előbb a determinisztikus szűrő, utána (ha kockázatos a kör) a bíráló."""
    feladat = _FELADATOK[allapot.feladat_id]
    e = szuro.ellenoriz(szoveg, korabbi, feladat, allapot.helyes_sorok, szint)
    if not e.rendben:
        return False, f"szűrő: {e.indok}"
    if biralo_be:
        it = biralo.ellenoriz(szoveg, korabbi, feladat, allapot.helyes_sorok, szint)
        v.input_tokens += it.input_tokens
        v.output_tokens += it.output_tokens
        v.thinking_tokens += it.thinking_tokens
        if it.futott:
            v.biralo = "megfogta" if it.kiszivargas else "átment"
        if it.kiszivargas:
            return False, f"bíráló: {it.indok}"
    return True, ""


def _szurt(v: Valasz, history: list[dict], allapot: Allapot, prompt: str, model_key: str,
           biralo_be: bool = False) -> Valasz:
    korabbi = [m["text"] for m in history if m["role"] == "model"]
    rendben, indok = _vizsgal(v.szoveg, korabbi, allapot, v.szint, biralo_be, v)
    if rendben:
        v.szuro = "átment"
        return v
    # Egy újragenerálás a hibát megnevezve (a megoldást nem adjuk meg a modellnek)
    figyelmeztetes = (f"\nFIGYELEM: az előző válaszvázlatod túl sokat árult el ({indok}). "
                      "Írd újra úgy, hogy ne szerepeljen benne a megoldás egyetlen számlaneve, oldala vagy "
                      "összege sem, amelyet a hallgató még nem írt le, körülírva sem. Kérdezz inkább.\n")
    r = llm.generate(history, prompt + figyelmeztetes, model_key)
    v.input_tokens += r.input_tokens
    v.output_tokens += r.output_tokens
    v.thinking_tokens += r.thinking_tokens
    rendben2, indok2 = _vizsgal(r.text, korabbi, allapot, v.szint, biralo_be, v)
    if rendben2:
        v.szoveg, v.szuro, v.szuro_indok = r.text, "újragenerálva", indok
    else:
        v.szoveg, v.szuro, v.szuro_indok = tartalek(v.szint, korabbi), "tartalék", indok2
    return v


def _naploz(allapot: Allapot, uzenet: str, v: Valasz) -> None:
    NAPLO_DIR.mkdir(exist_ok=True)
    sor = {"ido": time.strftime("%Y-%m-%dT%H:%M:%S"), **asdict(allapot),
           "hallgato": uzenet, **asdict(v)}
    with open(NAPLO_DIR / f"{allapot.munkamenet_id}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(sor, ensure_ascii=False) + "\n")
