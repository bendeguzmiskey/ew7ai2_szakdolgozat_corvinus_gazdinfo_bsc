"""Beállítások: API-kulcs és modellnevek a .env fájlból."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_KEY = os.environ.get("gemini_api_key")

# Rögzített modellverziók, hogy a mérés megismételhető legyen (a "-latest" alias közben
# másik modellre válthat). A gemini-3.5-flash hívásait a Google a 3.6-ra irányította,
# ezért a nagy modell a 3.6.
MODELS = {
    "kicsi": os.environ.get("MODEL_SMALL", "gemini-3.5-flash-lite"),  # a tutor motorja
    "nagy": os.environ.get("MODEL_LARGE", "gemini-3.6-flash"),        # a mérés bírálója
}
EMBED_MODEL = os.environ.get("MODEL_EMBED", "gemini-embedding-001")

DEFAULT_MODEL = "kicsi"

TEMPERATURE = 0.3
MAX_OUTPUT_TOKENS = 1024
