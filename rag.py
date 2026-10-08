import asyncio
from datetime import datetime, timezone

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from config import CHROMA_PATH, RAG_MAX_DISTANCE

import db

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vectorstore = Chroma(
    collection_name="website_knowledge",
    embedding_function=embeddings,
    persist_directory=CHROMA_PATH
)


async def store_pages(bot_id: str, pages: list[tuple[str, str]]) -> int:
    """Chunk pages (CPU-bound, off the event loop), write chunk metadata to
    MongoDB Atlas (async), then embed and store vectors in Chroma
    (filtered by bot_id)."""

    def split():
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        return [(url, text, splitter.create_documents([text])) for url, text in pages]

    split_pages = await asyncio.to_thread(split)

    documents = []

    for url, text, chunks in split_pages:
        document_id = await db.add_document(bot_id, url, url, text)

        for chunk in chunks:
            chunk.metadata = {
                "source": url,
                "bot_id": str(bot_id),
                "crawled_at": datetime.now(timezone.utc).isoformat(),
            }
            documents.append(chunk)
            await db.add_chunk(bot_id, document_id, chunk.page_content[:500], url)

    if documents:
        await asyncio.to_thread(vectorstore.add_documents, documents)

    return len(documents)


async def search_knowledge(query: str, bot_id: str, k: int = 3):
    def search():
        return vectorstore.similarity_search_with_score(
            query,
            k=k,
            filter={"bot_id": str(bot_id)}
        )

    return await asyncio.to_thread(search)


async def find_relevant_context(query: str, bot_id: str, k: int = 3):
    results = await search_knowledge(query, bot_id, k)

    if not results:
        return None

    best_document, best_distance = results[0]

    if best_distance > RAG_MAX_DISTANCE:
        return None

    context_parts = []

    for document, distance in results:
        if distance > RAG_MAX_DISTANCE:
            continue

        context_parts.append(
            f"SOURCE: {document.metadata.get('source')}\n"
            f"{document.page_content[:700]}"
        )

    if not context_parts:
        return None

    return "\n\n".join(context_parts)


def delete_bot_knowledge(bot_id: str):
    """Remove this bot's vectors only. Never touches other bots."""
    vectorstore._collection.delete(where={"bot_id": str(bot_id)})
