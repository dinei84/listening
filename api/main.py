from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routes_audio import router as audio_router
from api.routes_books import router as books_router
from storage import audio_store, db, progress_store

PLAYER_DIR = Path(__file__).resolve().parent.parent / "player"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Garante que o schema do SQLite existe antes de aceitar requisições."""
    db.init_db()
    audio_store.init_db()
    progress_store.init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(books_router)
app.include_router(audio_router)
# Montado por último: só serve caminhos que nenhuma rota da API acima já respondeu.
app.mount("/", StaticFiles(directory=PLAYER_DIR, html=True), name="player")
