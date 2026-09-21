import os
import asyncio
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import AsyncMongoClient


load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE")

client = AsyncMongoClient(MONGODB_URI)
db = client[MONGODB_DATABASE]

users_collection = db["users"]
messages_collection = db["messages"]


async def save_message(
    whatsapp_number: str,
    role: str,
    content: str
):
    """
    Save a message for a WhatsApp user.
    """

    # Create user if they don't exist
    await users_collection.update_one(
        {"whatsapp_number": whatsapp_number},
        {
            "$setOnInsert": {
                "whatsapp_number": whatsapp_number,
                "created_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )

    # Save message
    await messages_collection.insert_one(
        {
            "whatsapp_number": whatsapp_number,
            "role": role,
            "content": content,
            "created_at": datetime.now(timezone.utc)
        }
    )


async def get_chat_history(
    whatsapp_number: str,
    limit: int = 10
):
    """
    Get the latest messages for a WhatsApp user.
    """

    cursor = (
        messages_collection
        .find(
            {"whatsapp_number": whatsapp_number},
            {
                "_id": 0,
                "role": 1,
                "content": 1,
                "created_at": 1
            }
        )
        .sort("created_at", -1)
        .limit(limit)
    )

    messages = await cursor.to_list(length=limit)

    # We retrieved newest → oldest.
    # Reverse so Gemini receives oldest → newest.
    messages.reverse()

    return messages


async def main():

    test_user = "919876543210"

    # Save test conversation
    await save_message(
        test_user,
        "user",
        "Hello, my name is Rahul."
    )

    await save_message(
        test_user,
        "assistant",
        "Hello Rahul! Nice to meet you."
    )

    await save_message(
        test_user,
        "user",
        "What is my name?"
    )

    # Retrieve conversation
    history = await get_chat_history(test_user)

    print("\n===== CHAT HISTORY =====\n")

    for message in history:
        print(
            f"{message['role']}: "
            f"{message['content']}"
        )

    print("\n========================\n")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())