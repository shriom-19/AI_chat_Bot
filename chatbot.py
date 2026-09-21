from langchain_google_genai import ChatGoogleGenerativeAI

from config import GOOGLE_API_KEY, GEMINI_MODEL


llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=GOOGLE_API_KEY
)


def extract_text(content) -> str:

    if isinstance(content, str):
        return content

    if isinstance(content, list):

        parts = []

        for item in content:

            if isinstance(item, dict):
                text = item.get("text")

                if text:
                    parts.append(text)

        return "".join(parts)

    return str(content)


async def generate_rag_answer(
    question: str,
    context: str,
    history: list | None = None
) -> str:

    history_text = ""

    if history:

        for message in history:

            history_text += (
                f"{message['role']}: "
                f"{message['content']}\n"
            )

    prompt = f"""
You are a helpful website assistant.

Use only the website information provided below.

Rules:
- Do not invent information.
- If the answer is not in the website information, say you don't know.
- Keep the answer concise.
- Use conversation history only to understand context.

Conversation history:
{history_text}

Website information:
{context}

Current question:
{question}
"""

    response = await llm.ainvoke(prompt)

    return extract_text(response.content)