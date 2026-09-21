import asyncio
import re
from urllib.parse import urlparse

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from website_search import crawl_website
import hashlib

INDEX_PATH = "chroma_db"

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

page_index = Chroma(
    collection_name="website_pages",
    embedding_function=embeddings,
    persist_directory=INDEX_PATH
)


def get_site_id(url: str) -> str:
    return urlparse(url).netloc.lower()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


async def index_pages(
    pages: list[tuple[str, str]]
) -> int:

    def index():

        documents = []
        ids = []
        metadatas = []

        for url, text in pages:

            text = normalize(text)

            if not text:
                continue

            page_id = hashlib.sha256(
                url.encode("utf-8")
            ).hexdigest()

            documents.append(
                text[:5000]
            )

            ids.append(page_id)

            metadatas.append({
                "source": url,
                "site_id": get_site_id(url)
            })

        if documents:

            page_index._collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

        return len(documents)

    return await asyncio.to_thread(index)

    

async def search_pages(
    query: str,
    site_id: str,
    k: int = 5
):

    def search():

        return page_index.similarity_search_with_score(
            query,
            k=k,
            filter={
                "site_id": site_id
            }
        )

    return await asyncio.to_thread(search)

async def find_best_page(
    query: str,
    site_id: str,
    max_distance: float = 1.70
):
    results = await search_pages(
        query=query,
        site_id=site_id,
        k=5
    )

    if not results:
        return None

    best_document, best_distance = results[0]

    print(
        f"Best website-page distance: "
        f"{best_distance:.4f}"
    )

    if best_distance > max_distance:
        return None

    return (
        best_document.metadata["source"],
        best_distance
    )


async def main():

    website = input(
        "Website URL: "
    ).strip()

    print(
        f"\nIndexing website: {website}"
    )

    print("\nCrawling website...\n")

    pages = await crawl_website(
        website
    )

    print(
        f"\nFetched {len(pages)} pages."
    )

    print("\nBuilding website page index...")

    count = await index_pages(
        pages
    )

    print(
        f"Indexed {count} pages."
    )

    print("\nWebsite indexing completed.")


if __name__ == "__main__":
    asyncio.run(main())