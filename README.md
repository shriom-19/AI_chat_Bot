# Multi-Bot Website RAG Platform

Create multiple independent chatbots, each answering **only** from its own
website's knowledge base. Bots never see each other's data.

## Architecture

```
Streamlit admin (admin.py)  ──HTTP Basic + JSON──▶  FastAPI backend (app.py)
                                                        │
                                                        ▼
                                          chat_service.ask(bot_id, session_id, message)
                                            ├─ RAG retrieval  (Chroma, filtered by bot_id)
                                            ├─ Gemini         (LangChain)
                                            └─ Memory         (MongoDB Atlas, bot_id + session_id)
```

- **FastAPI** is the only backend. It owns the database, RAG, and indexing.
- **Streamlit** is a thin admin frontend; it imports no DB/RAG code and talks
  to the backend only through `/api/*`.
- **MongoDB Atlas** stores bots, documents, chunks, conversations, messages.
- **Chroma** (local `chroma_db/`) stores vectors, every one tagged with `bot_id`.
- **Twilio/WhatsApp is not implemented.** Later it becomes another client of
  `chat_service.ask()`: `whatsapp_number → bot_id → ask() → reply`.

## API (all `/api/*` routes require HTTP Basic auth)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/bots` | List bots |
| POST | `/api/bots` | Create bot and start indexing |
| GET | `/api/bots/{bot_id}` | Bot detail + document/chunk counts |
| PUT | `/api/bots/{bot_id}` | Edit bot |
| DELETE | `/api/bots/{bot_id}` | Delete bot and only its data |
| POST | `/api/bots/{bot_id}/ingest` | (Re)build knowledge base |
| POST | `/api/bots/{bot_id}/enable` / `disable` | Toggle bot |
| POST | `/api/bots/{bot_id}/chat` | Ask a question (bot-specific RAG) |
| GET | `/api/conversations[/{id}]` | Conversation history |
| GET | `/api/analytics` | Totals + per-bot counts |

Interactive docs: http://127.0.0.1:8000/docs

## Setup

```bash
uv sync
```

Copy `.env.example` to `.env` and fill in `GOOGLE_API_KEY`, `ADMIN_USERNAME`,
`ADMIN_PASSWORD`, `MONGODB_URI`, `MONGODB_DATABASE`. Never commit `.env`.

## Run (two terminals)

```bash
# Backend
uv run uvicorn app:app --reload

# Admin panel
uv run streamlit run admin.py
```

Open the Streamlit URL (usually http://localhost:8501) and log in with
`ADMIN_USERNAME` / `ADMIN_PASSWORD`. The backend validates them; Streamlit
never stores or hardcodes credentials beyond the login session.

## Using it

1. **Create Bot** — name + website URL (description optional). Indexing runs
   in the background: `creating → indexing → ready`.
2. **Bots** — view status, doc/chunk counts, edit, rebuild knowledge base,
   enable/disable, delete.
3. **Test Chat** — pick a bot and ask questions; answers come only from that
   bot's knowledge base.

## Limitations

- Single admin account; credentials are sent as HTTP Basic (use HTTPS if
  you ever expose the backend beyond localhost).
- Crawler: same-domain, max 50 pages, no JS rendering.
- Chroma vectors are local files (single-instance).
