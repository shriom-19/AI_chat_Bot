import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from config import (
    CHROMA_PATH,
    RAG_MAX_DISTANCE
)

CHROMA_PATH = "chroma_db"


embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


vectorstore = Chroma(
    collection_name="website_knowledge",
    embedding_function=embeddings,
    persist_directory=CHROMA_PATH
)


def get_site_id(url: str) -> str:
    return urlparse(url).netloc.lower()


async def store_pages(
    pages: list[tuple[str, str]]
) -> int:

    def store():

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

        documents = []

        for url, text in pages:

            chunks = splitter.create_documents([text])

            site_id = get_site_id(url)

            for chunk in chunks:

                chunk.metadata = {
                    "source": url,
                    "site_id": site_id,
                    "crawled_at": datetime.now(
                        timezone.utc
                    ).isoformat()
                }

                documents.append(chunk)

        if documents:
            vectorstore.add_documents(documents)

        return len(documents)

    return await asyncio.to_thread(store)


async def search_knowledge(
    query: str,
    site_id: str,
    k: int = 3
):
    def search():
        return vectorstore.similarity_search_with_score(
            query,
            k=k,
            filter={"site_id": site_id}
        )

    return await asyncio.to_thread(search)


async def get_rag_context(
    query: str,
    site_id: str
):
    results = await search_knowledge(
        query,
        site_id,
        k=3
    )

    if not results:
        return ""

    parts = []

    for document, distance in results:
        parts.append(
            f"SOURCE: {document.metadata['source']}\n"
            f"{document.page_content[:700]}"
        )

    return "\n\n".join(parts)

async def find_relevant_context(
    query: str,
    site_id: str,
    k: int = 3
):
    results = await search_knowledge(
        query=query,
        site_id=site_id,
        k=k
    )

    if not results:
        return None

    best_document, best_distance = results[0]

    print(
        f"Best distance: {best_distance:.4f}"
    )

    if best_distance > RAG_MAX_DISTANCE:

        print(
            f"No sufficiently relevant result "
            f"(threshold: {RAG_MAX_DISTANCE:.2f})"
        )

        return None

    context_parts = []

    for document, distance in results:

        if distance > RAG_MAX_DISTANCE:
            continue

        context_parts.append(
            f"SOURCE: "
            f"{document.metadata.get('source')}\n"
            f"{document.page_content[:700]}"
        )

    if not context_parts:
        return None

    return "\n\n".join(context_parts)