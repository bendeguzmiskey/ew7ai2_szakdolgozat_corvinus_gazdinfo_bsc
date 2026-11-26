"""Visszakereső (v0.4, RAG): a tutor a saját jegyzetből magyaráz, nem a modell általános tudásából.

A kurzus jelölései (nevesített számlák, E/F/R/B jelleg, Áfa pénzügyi rendezése)
eltérnek attól, amit a modell máshonnan tud.

Lépések:
  1. a jegyzet (data/jegyzet.md) "## J.." szakaszokra bontva, egy szakasz = egy egység
  2. minden szakaszhoz beágyazás (embedding), gyorsítótárban (data/jegyzet_emb.json)
  3. körönként: a feladat szövege + a hallgató utolsó üzenete → beágyazás → koszinusz-
     hasonlóság → a legjobb K szakasz kerül a promptba, azonosítóval együtt
  4. a modell a válaszban [J..] jelöléssel hivatkozik; a kód csak a ténylegesen
     visszakeresett azonosítókat fogadja el, és ezekből írja ki a forrást

A megoldókulcs továbbra sem kerül a promptba; a jegyzet általános szabályokat tartalmaz,
kidolgozott megoldást nem.
"""
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from . import config

JEGYZET = Path(__file__).resolve().parent.parent / "data" / "jegyzet.md"
CACHE = Path(__file__).resolve().parent.parent / "data" / "jegyzet_emb.json"
TOP_K = 2


@dataclass(frozen=True)
class Szakasz:
    id: str      # pl. "J6"
    cim: str     # pl. "Előzetes áfa"
    szoveg: str


def szakaszok(utvonal: Path = JEGYZET) -> list[Szakasz]:
    szoveg = re.sub(r"<!--.*?-->", "", utvonal.read_text(encoding="utf-8"), flags=re.S)
    talalat = re.findall(r"^## (J\d+) (.+?)\n(.*?)(?=^## J\d+ |\Z)", szoveg, flags=re.S | re.M)
    return [Szakasz(i, c.strip(), t.strip()) for i, c, t in talalat]


def _beagyaz(szovegek: list[str], feladat: str) -> list[list[float]]:
    """feladat: "RETRIEVAL_DOCUMENT" a jegyzethez, "RETRIEVAL_QUERY" a kérdéshez."""
    from google.genai import types

    from .llm import client
    r = client().models.embed_content(model=config.EMBED_MODEL, contents=szovegek,
                                     config=types.EmbedContentConfig(task_type=feladat))
    return [e.values for e in r.embeddings]


def _koszinusz(a: list[float], b: list[float]) -> float:
    s = sum(x * y for x, y in zip(a, b))
    return s / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


class Visszakereso:
    def __init__(self, beagyazo=_beagyaz, utvonal: Path = JEGYZET, cache: Path | None = CACHE):
        self.szakaszok = szakaszok(utvonal)
        self._beagyazo = beagyazo
        self._vektorok = self._jegyzet_vektorai(cache)

    def _jegyzet_vektorai(self, cache: Path | None) -> list[list[float]]:
        # A gyorsítótár csak akkor érvényes, ha a jegyzet és a modell is ugyanaz.
        kulcs = hashlib.sha256((config.EMBED_MODEL + "".join(
            s.id + s.szoveg for s in self.szakaszok)).encode()).hexdigest()
        if cache and cache.exists():
            adat = json.loads(cache.read_text(encoding="utf-8"))
            if adat.get("kulcs") == kulcs:
                return adat["vektorok"]
        vektorok = self._beagyazo([f"{s.cim}\n{s.szoveg}" for s in self.szakaszok], "RETRIEVAL_DOCUMENT")
        if cache:
            cache.write_text(json.dumps({"kulcs": kulcs, "vektorok": vektorok}), encoding="utf-8")
        return vektorok

    def keres(self, kerdes: str, k: int = TOP_K) -> list[Szakasz]:
        q = self._beagyazo([kerdes], "RETRIEVAL_QUERY")[0]
        rang = sorted(range(len(self.szakaszok)), key=lambda i: -_koszinusz(q, self._vektorok[i]))
        return [self.szakaszok[i] for i in rang[:k]]


def promptresz(talalatok: list[Szakasz]) -> str:
    """A visszakeresett szakaszok a rendszerprompt végére."""
    if not talalatok:
        return ""
    reszek = "\n".join(f"[{s.id}] {s.cim}: {s.szoveg}" for s in talalatok)
    return ("\nA kurzus jegyzetének ide vonatkozó részei. Magyarázatnál ezekre támaszkodj, "
            "a kurzus jelöléseit használd (számlanév, nem számlaszám), és ha valamelyikre "
            "építesz, jelöld a végén szögletes zárójelben az azonosítóját, pl. [J3]. "
            "Ezekből se mondd meg a feladat megoldását.\n" + reszek + "\n")


def forrasok(valasz: str, talalatok: list[Szakasz],
             rejtett=lambda cim: False) -> tuple[str, list[str]]:
    """A válaszból kiveszi a [J..] jelöléseket, és csak a visszakeresett szakaszokra
    hivatkozó jelöléseket fogadja el. Visszaadja a tisztított szöveget és a forrásokat.

    rejtett(cim): igaz, ha a szakasz címe nem jelenhet meg. A címek gyakran számlanevek
    ("J7 Fizetendő áfa"), a forrássor pedig a szűrő után kerül a válaszhoz, ezért itt kell
    megfogni: ilyenkor csak az azonosító látszik."""
    ervenyes = {s.id: s for s in talalatok}
    hivatkozott = [i for i in dict.fromkeys(re.findall(r"\[(J\d+)\]", valasz)) if i in ervenyes]
    tiszta = re.sub(r"\s*\[J\d+\]", "", valasz).rstrip()
    if hivatkozott:
        tiszta += "\n\n*Forrás: jegyzet – " + "; ".join(
            i if rejtett(ervenyes[i].cim) else f"{i} {ervenyes[i].cim}" for i in hivatkozott) + "*"
    return tiszta, hivatkozott
