"""MongoDB Atlas persistence: bots, documents, chunks, conversations, messages.

Every function is async — this module is the online-database equivalent of
the earlier SQLite version, same function names/shapes, so callers barely
changed. IDs are Mongo ObjectId hex strings (bot["id"], conversation["id"]).
"""

from datetime import datetime, timezone

import certifi
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import AsyncMongoClient

from config import MONGODB_URI, MONGODB_DATABASE

client = AsyncMongoClient(MONGODB_URI, tls=True, tlsCAFile=certifi.where())
mongo_db = client[MONGODB_DATABASE]

bots_col = mongo_db["bots"]
documents_col = mongo_db["documents"]
chunks_col = mongo_db["document_chunks"]
conversations_col = mongo_db["conversations"]
messages_col = mongo_db["messages"]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _oid(id_str):
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        return None


def _with_id(doc):
    if not doc:
        return None
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


async def init_db():
    await conversations_col.create_index([("bot_id", 1), ("session_id", 1)], unique=True)
    await documents_col.create_index("bot_id")
    await chunks_col.create_index("bot_id")
    await messages_col.create_index("conversation_id")


# ---------- Bots ----------

async def create_bot(name, website_url, description, system_prompt):
    now = _now()
    result = await bots_col.insert_one({
        "name": name,
        "website_url": website_url,
        "description": description,
        "system_prompt": system_prompt,
        "status": "creating",
        "created_at": now,
        "updated_at": now,
    })
    return str(result.inserted_id)


async def get_bot(bot_id):
    oid = _oid(bot_id)
    if not oid:
        return None
    return _with_id(await bots_col.find_one({"_id": oid}))


async def list_bots():
    cursor = bots_col.find().sort("created_at", -1)
    return [_with_id(doc) async for doc in cursor]


async def update_bot_status(bot_id, status):
    await bots_col.update_one({"_id": _oid(bot_id)}, {"$set": {"status": status, "updated_at": _now()}})


async def update_bot(bot_id, name, website_url, description, system_prompt):
    await bots_col.update_one(
        {"_id": _oid(bot_id)},
        {"$set": {
            "name": name,
            "website_url": website_url,
            "description": description,
            "system_prompt": system_prompt,
            "updated_at": _now(),
        }},
    )


async def delete_bot_cascade(bot_id):
    """Delete a bot and everything scoped to it. Never touches other bots."""
    conversation_ids = [
        str(c["_id"]) async for c in conversations_col.find({"bot_id": bot_id}, {"_id": 1})
    ]
    if conversation_ids:
        await messages_col.delete_many({"conversation_id": {"$in": conversation_ids}})
    await conversations_col.delete_many({"bot_id": bot_id})
    await chunks_col.delete_many({"bot_id": bot_id})
    await documents_col.delete_many({"bot_id": bot_id})
    await bots_col.delete_one({"_id": _oid(bot_id)})


# ---------- Documents & chunks ----------

async def add_document(bot_id, url, title, content):
    now = _now()
    result = await documents_col.insert_one({
        "bot_id": bot_id,
        "url": url,
        "title": title,
        "content": content,
        "created_at": now,
        "updated_at": now,
    })
    return str(result.inserted_id)


async def clear_documents(bot_id):
    await chunks_col.delete_many({"bot_id": bot_id})
    await documents_col.delete_many({"bot_id": bot_id})


async def add_chunk(bot_id, document_id, chunk_text, embedding_ref):
    await chunks_col.insert_one({
        "bot_id": bot_id,
        "document_id": document_id,
        "chunk_text": chunk_text,
        "embedding_ref": embedding_ref,
    })


async def count_documents(bot_id):
    return await documents_col.count_documents({"bot_id": bot_id})


async def count_chunks(bot_id):
    return await chunks_col.count_documents({"bot_id": bot_id})


# ---------- Conversations & messages ----------

async def get_or_create_conversation(bot_id, session_id, user_identifier=None):
    now = _now()
    doc = await conversations_col.find_one({"bot_id": bot_id, "session_id": session_id})
    if doc:
        return _with_id(doc)

    result = await conversations_col.insert_one({
        "bot_id": bot_id,
        "session_id": session_id,
        "user_identifier": user_identifier,
        "created_at": now,
        "updated_at": now,
    })
    return _with_id(await conversations_col.find_one({"_id": result.inserted_id}))


async def get_conversation(conversation_id):
    oid = _oid(conversation_id)
    if not oid:
        return None
    return _with_id(await conversations_col.find_one({"_id": oid}))


async def save_message(conversation_id, role, content):
    now = _now()
    await messages_col.insert_one({
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "created_at": now,
    })
    await conversations_col.update_one({"_id": _oid(conversation_id)}, {"$set": {"updated_at": now}})


async def get_recent_messages(conversation_id, limit=10):
    cursor = (
        messages_col.find({"conversation_id": conversation_id}, {"role": 1, "content": 1})
        .sort("_id", -1)
        .limit(limit)
    )
    messages = [doc async for doc in cursor]
    messages.reverse()
    for m in messages:
        m.pop("_id", None)
    return messages


async def get_conversation_messages(conversation_id):
    cursor = messages_col.find(
        {"conversation_id": conversation_id}, {"role": 1, "content": 1, "created_at": 1}
    ).sort("_id", 1)
    messages = [doc async for doc in cursor]
    for m in messages:
        m.pop("_id", None)
    return messages


async def list_conversations(bot_id=None):
    query = {"bot_id": bot_id} if bot_id else {}
    cursor = conversations_col.find(query).sort("updated_at", -1)
    conversations = [_with_id(doc) async for doc in cursor]

    bot_names = {}
    for c in conversations:
        if c["bot_id"] not in bot_names:
            bot = await get_bot(c["bot_id"])
            bot_names[c["bot_id"]] = bot["name"] if bot else "Unknown"
        c["bot_name"] = bot_names[c["bot_id"]]
        c["message_count"] = await messages_col.count_documents({"conversation_id": c["id"]})

    return conversations


# ---------- Analytics ----------

async def analytics_totals():
    total_bots = await bots_col.count_documents({})
    ready = await bots_col.count_documents({"status": "ready"})
    indexing = await bots_col.count_documents({"status": "indexing"})
    conversations_total = await conversations_col.count_documents({})
    messages_total = await messages_col.count_documents({})
    today = datetime.now(timezone.utc).date().isoformat()
    messages_today = await messages_col.count_documents({"created_at": {"$regex": f"^{today}"}})

    return {
        "total_bots": total_bots,
        "ready_bots": ready,
        "indexing_bots": indexing,
        "total_conversations": conversations_total,
        "total_messages": messages_total,
        "messages_today": messages_today,
    }


async def analytics_per_bot():
    bots = await list_bots()
    result = []

    for bot in bots:
        conversations = await conversations_col.count_documents({"bot_id": bot["id"]})
        conv_ids = [
            str(c["_id"]) async for c in conversations_col.find({"bot_id": bot["id"]}, {"_id": 1})
        ]
        messages = await messages_col.count_documents({"conversation_id": {"$in": conv_ids}}) if conv_ids else 0
        result.append({"name": bot["name"], "conversations": conversations, "messages": messages})

    return result
