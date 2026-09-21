import asyncio

from website_search import fetch_page_direct

from website_index import find_best_page

from rag import (
    get_site_id,
    store_pages,
    find_relevant_context,
)

from chatbot import generate_rag_answer


async def chat(
    question: str,
    website: str,
):
    site_id = get_site_id(website)

    print("\nSearching stored knowledge...")

    context = await find_relevant_context(
        question,
        site_id,
    )

    if context:

        print(
            "✓ Found information in ChromaDB"
        )

    else:

        print(
            "No strong RAG match found."
        )

        print(
            "Searching website page index..."
        )

        candidate = await find_best_page(
            question,
            site_id,
        )

        if not candidate:

            return (
                "I couldn't find a relevant "
                "page on the website."
            )

        selected_url, distance = candidate

        print(
            f"✓ Best page: {selected_url}"
        )

        print(
            f"Distance: {distance:.4f}"
        )

        print(
            "Fetching page..."
        )

        page_text = await fetch_page_direct(
            selected_url
        )

        if not page_text:

            return (
                "I found a relevant page, "
                "but couldn't read it."
            )

        print(
            "Storing page in ChromaDB..."
        )

        await store_pages([
            (
                selected_url,
                page_text
            )
        ])

        print(
            "✓ Page stored"
        )

        context = await find_relevant_context(
            question,
            site_id,
        )

    if not context:

        return (
            "I couldn't find this information "
            "on the website."
        )

    print(
        "Generating answer..."
    )

    return await generate_rag_answer(
        question,
        context
    )


async def main():

    website = input(
        "Website URL: "
    ).strip()

    site_id = get_site_id(
        website
    )

    print(
        f"\nUsing website: {site_id}"
    )

    while True:

        question = input(
            "\nAsk a question "
            "(type exit to quit): "
        ).strip()

        if question.lower() == "exit":
            break

        answer = await chat(
            question,
            website
        )

        print(
            "\nBot:",
            answer
        )


if __name__ == "__main__":
    asyncio.run(main())