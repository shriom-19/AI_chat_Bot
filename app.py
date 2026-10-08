"""Multi-Bot Website RAG Platform — FastAPI backend/API.

The admin UI lives separately in admin.py (Streamlit). This file is a
clean JSON API: Streamlit and the future Twilio webhook both go through
chat_service.ask(bot_id, session_id, message) the same way — no RAG or
DB logic lives in either frontend.

Every /api/* route requires HTTP Basic auth (see auth.py).
"""

from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from pydantic import BaseModel

import db
import rag
import website_index
from auth import require_auth
from indexing import index_bot
from chat_service import ask


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    yield


app = FastAPI(title="Multi-Bot RAG Platform API", lifespan=lifespan)


class BotCreate(BaseModel):
    name: str
    website_url: str
    description: str = ""
    system_prompt: str = ""


class BotUpdate(BaseModel):
    name: str
    website_url: str
    description: str = ""
    system_prompt: str = ""


class ChatRequest(BaseModel):
    session_id: str
    message: str


async def _run_index_bot(bot_id: str, website_url: str, is_reindex: bool):
    await index_bot(bot_id, website_url, is_reindex)


@app.get("/")
def root():
    return {"service": "multi-bot-rag-platform", "status": "ok"}


# ---------- Bots ----------

@app.get("/api/bots")
async def list_bots(_: str = Depends(require_auth)):
    return await db.list_bots()


@app.post("/api/bots", status_code=201)
async def create_bot(payload: BotCreate, background_tasks: BackgroundTasks, _: str = Depends(require_auth)):
    bot_id = await db.create_bot(payload.name, payload.website_url, payload.description, payload.system_prompt)
    background_tasks.add_task(_run_index_bot, bot_id, payload.website_url, False)
    return await db.get_bot(bot_id)


@app.get("/api/bots/{bot_id}")
async def get_bot(bot_id: str, _: str = Depends(require_auth)):
    bot = await db.get_bot(bot_id)

    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    bot["documents"] = await db.count_documents(bot_id)
    bot["chunks"] = await db.count_chunks(bot_id)
    return bot


@app.put("/api/bots/{bot_id}")
async def update_bot(bot_id: str, payload: BotUpdate, _: str = Depends(require_auth)):
    bot = await db.get_bot(bot_id)

    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    await db.update_bot(bot_id, payload.name, payload.website_url, payload.description, payload.system_prompt)
    return await db.get_bot(bot_id)


@app.delete("/api/bots/{bot_id}", status_code=204)
async def delete_bot(bot_id: str, _: str = Depends(require_auth)):
    bot = await db.get_bot(bot_id)

    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    # Vector cleanup is bot_id-scoped only — never touches another bot.
    rag.delete_bot_knowledge(bot_id)
    website_index.delete_bot_pages(bot_id)
    await db.delete_bot_cascade(bot_id)


@app.post("/api/bots/{bot_id}/enable")
async def enable_bot(bot_id: str, _: str = Depends(require_auth)):
    bot = await db.get_bot(bot_id)

    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    count = await db.count_documents(bot_id)
    await db.update_bot_status(bot_id, "ready" if count > 0 else "error")
    return await db.get_bot(bot_id)


@app.post("/api/bots/{bot_id}/disable")
async def disable_bot(bot_id: str, _: str = Depends(require_auth)):
    bot = await db.get_bot(bot_id)

    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    await db.update_bot_status(bot_id, "disabled")
    return await db.get_bot(bot_id)


@app.post("/api/bots/{bot_id}/ingest")
async def ingest_bot(bot_id: str, background_tasks: BackgroundTasks, _: str = Depends(require_auth)):
    """(Re)build a bot's knowledge base from its website. Used for both the
    initial index and the 'rebuild knowledge base' action."""
    bot = await db.get_bot(bot_id)

    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    is_reindex = (await db.count_documents(bot_id)) > 0
    background_tasks.add_task(_run_index_bot, bot_id, bot["website_url"], is_reindex)
    return {"status": "indexing"}


@app.post("/api/bots/{bot_id}/chat")
async def chat_with_bot(bot_id: str, payload: ChatRequest, _: str = Depends(require_auth)):
    bot = await db.get_bot(bot_id)

    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")

    answer = await ask(bot_id, payload.session_id, payload.message.strip(), user_identifier="admin-test")
    return {"answer": answer}


# ---------- Conversations ----------

@app.get("/api/conversations")
async def list_conversations(bot_id: str | None = None, _: str = Depends(require_auth)):
    return await db.list_conversations(bot_id)


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, _: str = Depends(require_auth)):
    conversation = await db.get_conversation(conversation_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await db.get_conversation_messages(conversation_id)
    return {"conversation": conversation, "messages": messages}


# ---------- Analytics ----------

@app.get("/api/analytics")
async def analytics(_: str = Depends(require_auth)):
    return {
        "totals": await db.analytics_totals(),
        "per_bot": await db.analytics_per_bot(),
    }


# ---------- Public API (No Auth) ----------

class PublicChatRequest(BaseModel):
    bot_id: str
    session_id: str
    message: str


@app.post("/api/public/chat")
async def public_chat(payload: PublicChatRequest):
    """
    Public endpoint for a frontend, WhatsApp integration, or Telegram webhook 
    to interact with the bots. No HTTP Basic Auth required.
    """
    bot = await db.get_bot(payload.bot_id)

    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")

    if bot.get("status") not in ("ready", "indexing"):
        # We can optionally block chats if it's completely empty, 
        # but let's allow it as long as it's not strictly disabled
        if bot.get("status") == "disabled":
            raise HTTPException(status_code=400, detail="Bot is disabled")

    # Use the session_id as the user identifier for analytics/logging
    answer = await ask(payload.bot_id, payload.session_id, payload.message.strip(), user_identifier=payload.session_id)
    return {"answer": answer}

