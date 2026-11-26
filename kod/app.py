"""A hallgatói felület (Streamlit): feladatválasztás, megoldási kísérlet beküldése, chat a tutorral.

Indítás:  .venv/bin/streamlit run app.py
"""
import pandas as pd
import streamlit as st

from tutor import config, szabalymag
from tutor.ellenorzo import ellenoriz
from tutor.feladatok import Sor, betolt
from tutor.pipeline import Allapot, valaszol

st.set_page_config(page_title="Számvitel tutor", page_icon="📘")
st.title("Számvitel tutor")

SZAMLAK, FELADATOK = betolt()
FELADAT_BY_ID = {f.id: f for f in FELADATOK}


def uj_munkamenet():
    f = FELADAT_BY_ID[st.session_state.feladat_id]
    st.session_state.history = []
    st.session_state.allapot = Allapot(feladat_id=f.id, feladat_szoveg=f.szoveg)


with st.sidebar:
    model_key = st.radio("Modell", list(config.MODELS), index=0,
                         format_func=lambda k: f"{k} ({config.MODELS[k]})")
    st.selectbox("Feladat", list(FELADAT_BY_ID), key="feladat_id", on_change=uj_munkamenet)
    st.button("Új beszélgetés", on_click=uj_munkamenet)

if "allapot" not in st.session_state:
    uj_munkamenet()
allapot: Allapot = st.session_state.allapot
feladat = FELADAT_BY_ID[allapot.feladat_id]

with st.sidebar:
    st.divider()
    st.caption(f"Sikertelen kísérletek: {allapot.sikertelen_kiserletek}")
    st.caption(f"Segítségi szint: {szabalymag.szint(allapot.sikertelen_kiserletek, allapot.plafon)}/4 "
               f"(plafon: {allapot.plafon})")

st.info(f"**{feladat.id}.** {feladat.szoveg}")

# --- Megoldás beírása --------------------------------------------------------
with st.expander("Megoldási kísérlet beküldése", expanded=True):
    ures = pd.DataFrame({"Oldal": ["T", "K"], "Számla": [None, None], "Összeg (eFt)": [None, None]})
    tabla = st.data_editor(
        ures, num_rows="dynamic", key=f"tabla_{feladat.id}_{allapot.munkamenet_id}", width="stretch",
        column_config={
            "Oldal": st.column_config.SelectboxColumn(options=["T", "K"], required=True),
            "Számla": st.column_config.SelectboxColumn(options=SZAMLAK, required=True),
            "Összeg (eFt)": st.column_config.NumberColumn(min_value=0, step=1.0),
        },
    )
    if st.button("Ellenőrzés"):
        sorok = [Sor(r["Oldal"], r["Számla"], float(r["Összeg (eFt)"]))
                 for _, r in tabla.iterrows()
                 if r["Oldal"] and r["Számla"] and pd.notna(r["Összeg (eFt)"])]
        if not sorok:
            st.warning("Adj meg legalább egy teljes sort.")
        else:
            d = ellenoriz(sorok, feladat.megoldas)
            if d.statusz != "helyes":
                allapot.sikertelen_kiserletek += 1
            for s in d.jo_sorok:  # amit helyesen leírt, az a szűrő számára már nem titok
                if s not in allapot.helyes_sorok:
                    allapot.helyes_sorok.append(s)
            allapot.utolso_diagnozis = d.osszegzes_hallgatonak()
            kiserlet = "; ".join(f"{s.oldal} {s.szamla} {s.osszeg:g}" for s in sorok)
            st.session_state.history += [
                {"role": "user", "text": f"Megoldási kísérletem: {kiserlet}"},
                {"role": "model", "text": f"Ellenőrzés: {allapot.utolso_diagnozis}"},
            ]
            st.rerun()

# --- Chat --------------------------------------------------------------------
for msg in st.session_state.history:
    with st.chat_message("user" if msg["role"] == "user" else "assistant"):
        st.markdown(msg["text"])

if user_text := st.chat_input("Kérdezz a tutortól"):
    st.session_state.history.append({"role": "user", "text": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)
    with st.chat_message("assistant"):
        with st.spinner("Gondolkodom..."):
            try:
                v = valaszol(st.session_state.history, allapot, model_key)
            except Exception as e:  # pl. túlterhelt modell (503) vagy elfogyott kvóta (429)
                st.session_state.history.pop()
                st.error(f"Hiba a modell hívásakor, próbáld újra: {e}")
                st.stop()
        st.markdown(v.szoveg)
        if v.valsag:
            st.caption("Válságkezelés: rögzített válasz, nyelvi modell nélkül.")
        else:
            st.caption(f"{v.model_version} · szint {v.szint}/4 · szűrő: {v.szuro} · "
                       f"jegyzet: {', '.join(v.jegyzet) or '–'} · "
                       f"{v.input_tokens}+{v.output_tokens} token")
    st.session_state.history.append({"role": "model", "text": v.szoveg})
