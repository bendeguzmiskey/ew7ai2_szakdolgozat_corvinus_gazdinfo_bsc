# Szókratészi számviteli tutor

Szakdolgozati pályamű, Budapesti Corvinus Egyetem, Gazdaságinformatikus BSc.
LLM-alapú tutor naplókönyvelés gyakorlásához (könyvelési tétel áfával). A tutor nem adja ki
a megoldást: a segítség mértékét kódszintű szabály dönti el, a választ kiküldés előtt
szűrő és bíráló ellenőrzi, a magyarázat a saját jegyzetből dolgozik (RAG).

## Mappák

| Mappa | Tartalom |
|---|---|
| `kod/tutor/` | A tutor: ellenőrző, szabálymag, RAG, szűrő, bíráló, vezérlő (`pipeline.py`) |
| `kod/app.py`, `kod/pages/` | Hallgatói és oktatói felület (Streamlit) |
| `kod/data/` | Feladatok megoldókulccsal, a jegyzet és a beágyazások gyorsítótára |
| `kod/kiserletek/` | A mérések szkriptjei (T1–T4) |
| `kod/tests/` | Automatikus tesztek (API nélkül) |
| `kiertekeles/` | A mérések nyers eredményei és összesítése (`eredmenyek.md`) |
| `tools/` | A T3 kézi címkézéséhez használt felület |

## Telepítés

Python 3.14-gyel készült.

    cd kod
    python -m venv .venv
    .venv/bin/pip install -r requirements.lock.txt pytest

A `kod/.env` fájlba kell a Google Gemini API-kulcs:

    gemini_api_key=...

## Futtatás

    cd kod
    .venv/bin/streamlit run app.py        # felület
    .venv/bin/python -m pytest -q         # tesztek
    .venv/bin/python -m kiserletek.t1_kiszivargas kicsi 1   # egy mérés (fizetős API-hívások)

A modellek: `gemini-3.5-flash-lite` (tutor), `gemini-3.6-flash` (a mérés bírálója).
