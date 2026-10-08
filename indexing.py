"""Bot website indexing: crawl -> page index -> chunked knowledge base.
Runs as a FastAPI background task on create and on re-index."""

import traceback

import db
from config import MAX_CRAWL_PAGES
from website_search import crawl_website
from website_index import index_pages, delete_bot_pages
from rag import store_pages, delete_bot_knowledge


async def index_bot(bot_id: str, website_url: str, is_reindex: bool = False):
    await db.update_bot_status(bot_id, "indexing")

    try:
        pages = await crawl_website(website_url, max_pages=MAX_CRAWL_PAGES)

        if not pages:
            # Don't destroy an existing working knowledge base on a failed crawl.
            await db.update_bot_status(bot_id, "error")
            return

        if is_reindex:
            delete_bot_knowledge(bot_id)
            delete_bot_pages(bot_id)
            await db.clear_documents(bot_id)

        await index_pages(bot_id, pages)
        await store_pages(bot_id, pages)

        await db.update_bot_status(bot_id, "ready")

    except Exception:
        traceback.print_exc()
        await db.update_bot_status(bot_id, "error")
