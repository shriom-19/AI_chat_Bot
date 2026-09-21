import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

GEMINI_MODEL = "gemini-3.6-flash"

CHROMA_PATH = "chroma_db"

RAG_MAX_DISTANCE = 1.60