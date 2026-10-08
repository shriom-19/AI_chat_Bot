"""Conversation memory, isolated by bot_id + session_id.
Backed by MongoDB Atlas (db.py). Kept as a thin module so future clients
(e.g. Twilio) can reuse these function names without depending on db.py's
document shapes directly."""

import db


async def save_message(bot_id: str, session_id: str, role: str, content: str):
    conversation = await db.get_or_create_conversation(bot_id, session_id)
    await db.save_message(conversation["id"], role, content)


async def get_chat_history(bot_id: str, session_id: str, limit: int = 10):
    conversation = await db.get_or_create_conversation(bot_id, session_id)
    return await db.get_recent_messages(conversation["id"], limit=limit)
