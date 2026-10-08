"""Central chat entry point. Both the admin Test Chat and (later) the
Twilio webhook must call ask() — never duplicate RAG logic elsewhere."""

import db
from chatbot import generate_rag_answer
from rag import find_relevant_context, store_pages
from website_index import find_best_page
from website_search import fetch_page_direct


async def ask(bot_id: str, session_id: str, message: str, user_identifier: str | None = None) -> str:
    bot = await db.get_bot(bot_id)

    if not bot:
        return "This bot does not exist."

    if bot["status"] == "disabled":
        return "This bot is currently disabled."

    if bot["status"] != "ready":
        return "This bot is still being set up. Please try again shortly."

    conversation = await db.get_or_create_conversation(bot_id, session_id, user_identifier)
    history = await db.get_recent_messages(conversation["id"], limit=10)

    await db.save_message(conversation["id"], "user", message)

    context = await find_relevant_context(message, bot_id)

    if not context:
        candidate = await find_best_page(message, bot_id)

        if candidate:
            url, _distance = candidate
            page_text = await fetch_page_direct(url)

            if page_text:
                await store_pages(bot_id, [(url, page_text)])
                context = await find_relevant_context(message, bot_id)

    if not context:
        answer = "I couldn't find this information on the website."
    else:
        answer = await generate_rag_answer(message, context, history, bot["system_prompt"])

    await db.save_message(conversation["id"], "assistant", answer)

    return answer
