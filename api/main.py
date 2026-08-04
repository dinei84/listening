from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes_books import router as books_router
from storage import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Garante que o schema do SQLite existe antes de aceitar requisições."""
    db.init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(books_router)
