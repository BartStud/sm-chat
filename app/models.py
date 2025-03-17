from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

user_chat_association = Table(
    "user_chat_association",
    Base.metadata,
    Column("user_id", String, ForeignKey("users.id")),
    Column("chat_id", Integer, ForeignKey("chats.id")),
)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    chats = relationship(
        "Chat", secondary=user_chat_association, back_populates="participants"
    )


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    participants = relationship(
        "User", secondary=user_chat_association, back_populates="chats"
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"))
    sender = Column(String, index=True)
    content = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
