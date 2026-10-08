import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = "gemini-3.6-flash"

CHROMA_PATH = "chroma_db"
RAG_MAX_DISTANCE = 1.60
PAGE_MAX_DISTANCE = 1.70
MAX_CRAWL_PAGES = 50

# MongoDB Atlas — online database for bots, documents, chunks, conversations, messages
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE")

_missing = [
    name for name, value in (
        ("MONGODB_URI", MONGODB_URI),
        ("MONGODB_DATABASE", MONGODB_DATABASE),
    )
    if not value
]

if _missing:
    raise RuntimeError(
        "Missing required environment variable(s): " + ", ".join(_missing) + ". "
        "Create a .env file in the project root (see .env.example) and set them there. "
        "Values are never printed here."
    )

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
