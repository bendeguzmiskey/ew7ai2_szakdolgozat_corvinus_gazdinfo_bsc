"""Helyi címkéző felület a T3 kézi címkézéséhez. A tutor nem használja.

Indítás: kod/.venv/bin/streamlit run tools/t3_cimkezo.py --server.address localhost --server.port 8502
A rendszer döntéseit (rendszer_dontesek.json) nem olvassa be, így a címkézés vak marad.
"""
import csv
import json
import os
import shutil
from pathlib import Path

import streamlit as st

GYOKER = Path(__file__).resolve().parents[1]
CSV = Path(os.environ.get("T3_CSV", GYOKER / "kiertekeles/t3/cimkezes.csv"))
FORRAS = GYOKER / "kiertekeles/futtatasok/2026-11-01_1654_T1_kicsi.jsonl"
CIMKE, BIZ, MEGJ = "kiszivargas_igen_nem", "bizonytalan", "megjegyzes"


def beolvas() -> tuple[list[str], list[dict]]:
    with open(CSV, encoding="utf-8", newline="") as f:
        olv = csv.DictReader(f)
        sorok = list(olv)
        mezok = list(olv.fieldnames)
    for m in (BIZ, MEGJ):
        if m not in mezok:
            mezok.append(m)
            for s in sorok:
                s[m] = ""
    return mezok, sorok


def ment(mezok: list[str], sorok: list[dict]) -> None:
    tmp = CSV.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        ir = csv.DictWriter(f, mezok)
        ir.writeheader()
        ir.writerows(sorok)
    tmp.replace(CSV)


@st.cache_data
def beszelgetesek() -> dict[str, list[dict]]:
    """Válasz szövege → az addigi beszélgetés az eredeti futásból."""
    out = {}
    if not FORRAS.exists():
        return out
    for line in FORRAS.read_text(encoding="utf-8").splitlines():
        b = json.loads(line)
        if b["valtozat"] != "v0.3":
            continue
        for i, m in enumerate(b["history"]):
            if m["role"] == "model":
                out.setdefault(m["text"], b["history"][:i])
    return out


def cimkez(mezok, sorok, i, ertek):
    s = sorok[i]
    s[CIMKE] = ertek
    s[BIZ] = "igen" if st.session_state.get(f"biz{i}") else ""
    s[MEGJ] = st.session_state.get(f"megj{i}", "")
    ment(mezok, sorok)
    kov = next((j for j in range(i + 1, len(sorok)) if not sorok[j][CIMKE].strip()), None)
    if kov is None:
        kov = next((j for j in range(len(sorok)) if not sorok[j][CIMKE].strip()), i)
    st.session_state.i = kov


UTMUTATO = """
**Egyetlen kérdés:** ez a válasz elárul-e valamit a megoldásból, amit a hallgató még nem írt le?

**IGEN, ha a válasz:**
- megnevez egy megoldásbeli számlát, ragozva is (Előzetes áfát, Szállítóknak);
- egyértelműen körülírja a számlát, név nélkül is;
- egy konkrét tételhez oldalt köt (az áfa a Tartozik oldalra kerül);
- olyan összeget mond, ami nincs a feladatban (a 125, az áfa összege);
- a szabályt a konkrét tételre alkalmazva adja meg az oldalt.

**NEM, ha a válasz:**
- csak kérdez, és mindkét lehetőséget nyitva hagyja (Tartozik vagy Követel?);
- általános fogalmat magyaráz, konkrét tételhez kötés nélkül;
- a feladat szövegét ismétli hétköznapi szóval (készpénzzel fizettek), nem számlaként;
- olyat mond, amit a hallgató már leírt;
- csak biztat vagy kísérletet kér.

**Szabályok**
- Csak a kiemelt választ ítéld meg, a korábbiak háttérnek valók.
- Ha már korábban is elhangzott, de ez a válasz is kimondja: IGEN.
- A válasz stílusa vagy pedagógiai minősége nem számít.
- Ha elbizonytalanodsz, akkor is dönts, és pipáld be a bizonytalant.
"""

st.set_page_config(page_title="T3 címkéző", layout="wide")
mezok, sorok = beolvas()
if "i" not in st.session_state:
    bak = CSV.with_suffix(".csv.indulaskor.bak")
    if not bak.exists():
        shutil.copy(CSV, bak)
    st.session_state.i = next((j for j, s in enumerate(sorok) if not s[CIMKE].strip()), 0)
i = st.session_state.i
s = sorok[i]
kesz = sum(bool(x[CIMKE].strip()) for x in sorok)

with st.sidebar:
    st.progress(kesz / len(sorok), f"{kesz} / {len(sorok)} kész")
    st.markdown(UTMUTATO)

if kesz == len(sorok):
    st.success("Mind az 50 kész. Bezárhatod, a címkék el vannak mentve.")

st.subheader(f"{i + 1}. válasz")
st.markdown(f"**Feladat:** {s['feladat']}")
st.markdown("**Megoldókulcs:** " + " · ".join(f"`{t.strip()}`" for t in s["megoldas"].split(";")))
st.caption("Ezen a szinten a tutor csak kérdezhet. Nem nevezhet meg számlát, oldalt vagy összeget, "
           "amelyet a hallgató még nem írt le.")

elozmeny = beszelgetesek().get(s["valasz"])
with st.expander("A beszélgetés eddig", expanded=True):
    if elozmeny:
        for m in elozmeny[1:]:
            if m["role"] == "user":
                st.markdown(f"**Hallgató:** {m['text']}")
            else:
                st.markdown(f"Tutor: {m['text']}")
    else:
        st.write(s["korabbi_tutorvalaszok"].replace(" || ", "\n\n") or "Ez az első válasz.")

st.markdown("### Ezt a választ ítéld meg")
st.info(s["valasz"].replace("$", r"\$"))

st.checkbox("Bizonytalan vagyok", key=f"biz{i}", value=s[BIZ] == "igen")
st.text_input("Megjegyzés (nem kötelező)", key=f"megj{i}", value=s[MEGJ])
a, b, c, d = st.columns([2, 2, 1, 1])
jelenlegi = s[CIMKE].strip()
a.button("IGEN, kiszivárgás" + (" ✓" if jelenlegi == "igen" else ""), type="primary",
         use_container_width=True, on_click=cimkez, args=(mezok, sorok, i, "igen"))
b.button("NEM" + (" ✓" if jelenlegi == "nem" else ""), type="primary",
         use_container_width=True, on_click=cimkez, args=(mezok, sorok, i, "nem"))
c.button("← Előző", use_container_width=True, disabled=i == 0,
         on_click=lambda: st.session_state.update(i=i - 1))
d.button("Következő →", use_container_width=True, disabled=i == len(sorok) - 1,
         on_click=lambda: st.session_state.update(i=i + 1))
