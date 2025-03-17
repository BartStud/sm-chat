from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import auth, chat, users
from app.es import init_indices, wait_for_elasticsearch, get_es_instance


@asynccontextmanager
async def lifespan(_: FastAPI):
    es = get_es_instance()
    if not await wait_for_elasticsearch(es):
        raise Exception("Elasticsearch is not available after waiting")

    await init_indices(es)

    yield


app = FastAPI(lifespan=lifespan)

app.include_router(chat.router)
app.include_router(chat.ws_router)
app.include_router(users.router)
app.include_router(auth.router)
