import asyncio
import re
import hashlib

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from config import CHROMA_PATH

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

page_index = Chroma(
    collection_name="website_pages",
    embedding_function=embeddings,
    persist_directory=CHROMA_PATH
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


async def index_pages(bot_id: int, pages: list[tuple[str, str]]) -> int:

    def index():
        documents = []
        ids = []
        metadatas = []

        for url, text in pages:
            text = normalize(text)

            if not text:
                continue

            page_id = hashlib.sha256(f"{bot_id}:{url}".encode("utf-8")).hexdigest()

            documents.append(text[:5000])
            ids.append(page_id)
            metadatas.append({"source": url, "bot_id": str(bot_id)})

        if documents:
            page_index._collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

        return len(documents)

    return await asyncio.to_thread(index)


async def search_pages(query: str, bot_id: int, k: int = 5):

    def search():
        return page_index.similarity_search_with_score(
            query,
            k=k,
            filter={"bot_id": str(bot_id)}
        )

    return await asyncio.to_thread(search)


async def find_best_page(query: str, bot_id: int, max_distance: float = 1.70):
    results = await search_pages(query, bot_id, k=5)

    if not results:
        return None

    best_document, best_distance = results[0]

    if best_distance > max_distance:
        return None

    return best_document.metadata["source"], best_distance


def delete_bot_pages(bot_id: int):
    """Remove this bot's page index only. Never touches other bots."""
    page_index._collection.delete(where={"bot_id": str(bot_id)})
