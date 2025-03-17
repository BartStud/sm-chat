from fastapi import APIRouter
from app.search import search_users

router = APIRouter()


@router.get("/api/chat/users/search")
async def search_users_api(username: str):
    """Wyszukuje użytkowników w Elasticsearch"""
    users = await search_users(username)
    return users
