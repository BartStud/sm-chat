import asyncio
import json
import os
from typing import Dict, List, Set

import aioredis
import httpx
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.auth import get_current_user, verify_token
from app.database import get_db
from app.models import Chat, Message, User

router = APIRouter(prefix="/api/chat")
ws_router = APIRouter()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")


class ConnectionManager:
    """Zarządza połączeniami WebSocket i jednorazowym nasłuchem Redis"""

    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = (
            {}
        )  # Przechowuje połączenia WebSocket dla każdego pokoju
        self.redis_tasks: Dict[str, asyncio.Task] = (
            {}
        )  # Przechowuje jednorazowy nasłuch Redis

    async def connect(self, chat_id: str, websocket: WebSocket):
        """Dodaje WebSocket do listy aktywnych połączeń w danym pokoju"""
        await websocket.accept()
        if chat_id not in self.rooms:
            self.rooms[chat_id] = set()
        self.rooms[chat_id].add(websocket)

        # Jeśli jeszcze nie ma nasłuchu dla tego pokoju, uruchamiamy go
        if chat_id not in self.redis_tasks:
            self.redis_tasks[chat_id] = asyncio.create_task(
                self.listen_to_redis(chat_id)
            )

    async def disconnect(self, chat_id: str, websocket: WebSocket):
        """Usuwa WebSocket z listy aktywnych połączeń"""
        if chat_id in self.rooms:
            self.rooms[chat_id].discard(websocket)
            if not self.rooms[chat_id]:  # Jeśli pokój jest pusty, usuwamy nasłuch Redis
                del self.rooms[chat_id]
                self.redis_tasks[chat_id].cancel()
                del self.redis_tasks[chat_id]

    async def broadcast(self, chat_id: str, message: str):
        """Wysyła wiadomość do wszystkich użytkowników w danym pokoju"""
        if chat_id in self.rooms:
            for connection in self.rooms[chat_id]:
                await connection.send_text(message)

    async def listen_to_redis(self, chat_id: str):
        """Jednorazowy nasłuch Redis dla pokoju czatu"""
        redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"chat_channel:{chat_id}")

        async for message in pubsub.listen():
            if message["type"] == "message":
                await self.broadcast(chat_id, message["data"])


manager = ConnectionManager()


@ws_router.websocket("/ws/chat/{chat_id}")
async def chat_endpoint(
    websocket: WebSocket, chat_id: str, db: AsyncSession = Depends(get_db)
):

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)  # 1008: Policy Violation
        return

    # Validate token manually
    try:
        user = verify_token(token)
    except HTTPException:
        await websocket.close(code=1008)
        return

    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"chat_channel:{chat_id}")

    user_db = await db.execute(
        select(User).options(selectinload(User.chats)).where(User.id == user["sub"])
    )
    user_db = user_db.scalar()

    if not user_db or chat_id not in [chat.id for chat in user_db.chats]:
        await websocket.close()
        return
    await manager.connect(str(chat_id), websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message = Message(
                chat_id=chat_id, sender=user["preferred_username"], content=data
            )
            # do dodania tam gdzie tworzymy wiadomośc w bazie
            db.add(message)
            await db.commit()
            payload = {
                "id": message.id,
                "sender": message.sender,
                "content": data,
                "timestamp": message.timestamp.isoformat(),
            }
            await redis.publish(f"chat_channel:{chat_id}", json.dumps(payload))
    except WebSocketDisconnect:
        await manager.disconnect(str(chat_id), websocket)


class ChatCreate(BaseModel):
    userId: str


@router.post("/chats/")
async def create_chat(
    chat: ChatCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Tworzenie nowego czatu"""
    participant = chat.userId
    # existing_chat = await db.execute(select(Chat).where(Chat.name == chat_name))
    # if existing_chat.scalar():
    #     raise HTTPException(status_code=400, detail="Chat already exists")

    chat = Chat(name="")
    user_db = await db.execute(select(User).where(User.id == user["sub"]))
    user_2 = await db.execute(select(User).where(User.id == participant))
    user_db = user_db.scalar()
    user_2 = user_2.scalar()

    if not user_db or not user_2:
        raise HTTPException(
            status_code=400, detail="Użytkownik musi być zarejestrowany"
        )

    chat.participants.append(user_db)
    chat.participants.append(user_2)
    db.add(chat)
    await db.commit()
    return {"message": "Chat created", "chat_id": chat.id}


@router.get("/chats/")
async def list_chats(
    user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User)
        .options(joinedload(User.chats).joinedload(Chat.participants))
        .where(User.id == user["sub"])
    )
    user_db = result.unique().scalar_one_or_none()

    if not user_db:
        return []

    async with httpx.AsyncClient() as client:

        async def fetch_picture(participant):
            try:
                resp = await client.get(
                    f"http://user_service:8000/admin/api/users/users/{participant.id}"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("picture")
                return None
            except Exception:
                return None

        chats_response = []
        for chat in user_db.chats:
            tasks = [fetch_picture(p) for p in chat.participants]
            pictures = await asyncio.gather(*tasks)
            participants_data = [
                {"id": p.id, "username": p.username, "picture": pictures[idx]}
                for idx, p in enumerate(chat.participants)
            ]
            chats_response.append(
                {
                    "id": chat.id,
                    "name": chat.name,
                    "participants": participants_data,
                }
            )
    return chats_response


@router.get("/chats/{chat_id}/messages", response_model=List[dict])
async def get_chat_history(
    chat_id: str, limit: int = 50, db: AsyncSession = Depends(get_db)
):
    """Pobiera historię wiadomości dla danego czatu"""
    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.timestamp.desc())
        .limit(limit)
    )
    messages = result.scalars().all()

    if not messages:
        raise HTTPException(status_code=404, detail="No messages found")

    return [
        {
            "id": msg.id,
            "sender": msg.sender,
            "content": msg.content,
            "timestamp": msg.timestamp,
        }
        for msg in messages
    ]
