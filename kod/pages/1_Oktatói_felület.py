"""Oktatói felület: a segítség plafonja, új feladat felvétele, összesítő a naplóból.

Prototípus: nincs bejelentkezés, a beállítás és a feladatok helyi fájlban vannak
(data/beallitasok.json, data/feladatok.json). A napló: naplo/*.jsonl.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from tutor import szabalymag
from tutor.feladatok import Sor, betolt, ellenoriz_kulcs, hozzaad
from tutor.pipeline import NAPLO_DIR

st.set_page_config(page_title="Oktatói felület", page_icon="🧑‍🏫")
st.title("Oktatói felület")

SZAMLAK, FELADATOK = betolt()

# --- 1. A segítség plafonja ---------------------------------------------------
st.header("A segítség felső határa")
st.caption("A segítségi szintet a sikertelen kísérletek száma emeli, de a plafon fölé nem mehet.")
for n, leiras in szabalymag.SZINTEK.items():
    st.markdown(f"**{n}. szint:** {leiras}")
uj = st.radio("Plafon", [1, 2, 3, 4], index=szabalymag.plafon() - 1, horizontal=True)
if st.button("Plafon mentése"):
    szabalymag.plafon_mentes(uj)
    st.success(f"Mentve: legfeljebb {uj}. szint. Az új beszélgetésekre érvényes.")

# --- 2. Új feladat ------------------------------------------------------------
st.header("Új feladat")
st.caption("Elég a feladat szövege és a megoldókulcs. A tutor szabályai minden feladatra közösek.")
szoveg = st.text_area("A feladat szövege")
ures = pd.DataFrame({"Oldal": ["T", "K"], "Számla": [None, None], "Összeg (eFt)": [None, None]})
kulcs = st.data_editor(
    ures, num_rows="dynamic", key="uj_kulcs", width="stretch",
    column_config={
        "Oldal": st.column_config.SelectboxColumn(options=["T", "K"], required=True),
        "Számla": st.column_config.SelectboxColumn(options=SZAMLAK, required=True),
        "Összeg (eFt)": st.column_config.NumberColumn(min_value=0, step=1.0),
    },
)
sorok = [Sor(r["Oldal"], r["Számla"], float(r["Összeg (eFt)"]))
         for _, r in kulcs.iterrows() if r["Oldal"] and r["Számla"] and pd.notna(r["Összeg (eFt)"])]
if sorok:
    hibak = ellenoriz_kulcs(sorok, SZAMLAK)
    for h in hibak:
        st.warning(h)
    if not hibak:
        st.caption("A kulcs formailag rendben (a tartozik és a követel oldal egyenlő).")
if st.button("Feladat mentése"):
    try:
        fid = hozzaad(szoveg, sorok)
        st.success(f"Mentve {fid} azonosítóval. A hallgatói felületen frissítés után választható.")
    except ValueError as e:
        st.error(str(e))

# --- 3. Összesítő -------------------------------------------------------------
st.header("Hol akadnak el a hallgatók?")
sorok_naplo = []
for f in sorted(Path(NAPLO_DIR).glob("*.jsonl")):
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            sorok_naplo.append(json.loads(line))
        except json.JSONDecodeError:
            pass
if not sorok_naplo:
    st.info("Még nincs naplózott beszélgetés.")
else:
    df = pd.DataFrame(sorok_naplo)
    if "biralo" not in df:
        df["biralo"] = "nem futott"
    ossz = df.groupby("feladat_id").agg(
        munkamenetek=("munkamenet_id", "nunique"),
        korok=("hallgato", "size"),
        max_sikertelen=("sikertelen_kiserletek", "max"),
        max_szint=("szint", "max"),
        tartalek=("szuro", lambda s: int((s == "tartalék").sum())),
        biralo_megfogta=("biralo", lambda s: int((s == "megfogta").sum())),
    ).reset_index().rename(columns={"feladat_id": "feladat"})
    st.dataframe(ossz, hide_index=True, width="stretch")
    st.caption("max_sikertelen: a legtöbb hibás kísérlet egy munkamenetben · tartalek: ahány "
               "válasz helyett a rögzített tartalékválasz ment ki · biralo_megfogta: ahányszor a "
               "bíráló kiszivárgást jelzett.")
