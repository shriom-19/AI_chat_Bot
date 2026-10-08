"""Streamlit admin panel for the Multi-Bot Website RAG Platform.

This talks to the FastAPI backend (app.py) exclusively through its JSON
API — no direct DB or RAG imports here. Login credentials are typed in,
sent as HTTP Basic auth on every request, and validated server-side by
FastAPI's require_auth (see auth.py) — nothing is hardcoded here.

Run with: uv run streamlit run admin.py
"""

import os
import secrets

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="RAG Bot Admin", layout="wide")


# ---------- API helpers ----------

def _handle_response(response: httpx.Response) -> httpx.Response:
    if response.status_code == 401:
        st.session_state.clear()
        st.error("Session expired or credentials invalid. Please log in again.")
        st.stop()
    response.raise_for_status()
    return response


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=API_BASE_URL,
        auth=(st.session_state["username"], st.session_state["password"]),
        timeout=30,
    )


def api_get(path: str, **params):
    with _client() as client:
        response = _handle_response(client.get(path, params=params))
    return response.json()


def api_post(path: str, json: dict | None = None):
    with _client() as client:
        response = _handle_response(client.post(path, json=json))
    return response.json() if response.content else None


def api_put(path: str, json: dict | None = None):
    with _client() as client:
        response = _handle_response(client.put(path, json=json))
    return response.json()


def api_delete(path: str):
    with _client() as client:
        _handle_response(client.delete(path))


# ---------- Login ----------

def login_screen():
    st.title("RAG Bot Admin — Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        try:
            with httpx.Client(base_url=API_BASE_URL, auth=(username, password), timeout=10) as client:
                response = client.get("/api/bots")
        except httpx.RequestError as e:
            st.error(f"Could not reach the backend API at {API_BASE_URL}: {e}")
            return

        if response.status_code == 200:
            st.session_state["authed"] = True
            st.session_state["username"] = username
            st.session_state["password"] = password
            st.rerun()
        else:
            st.error("Invalid credentials.")


if "authed" not in st.session_state:
    st.session_state["authed"] = False

if not st.session_state["authed"]:
    login_screen()
    st.stop()


# ---------- Sidebar ----------

st.sidebar.title("RAG Bot Admin")
page = st.sidebar.radio("Go to", ["Dashboard", "Bots", "Create Bot", "Test Chat"])

if st.sidebar.button("Log out"):
    st.session_state.clear()
    st.rerun()


# ---------- Dashboard ----------

def render_dashboard():
    st.header("Dashboard")

    try:
        data = api_get("/api/analytics")
    except httpx.HTTPStatusError as e:
        st.error(f"Failed to load analytics: {e}")
        return

    totals = data["totals"]
    cols = st.columns(6)
    cols[0].metric("Total Bots", totals["total_bots"])
    cols[1].metric("Ready", totals["ready_bots"])
    cols[2].metric("Indexing", totals["indexing_bots"])
    cols[3].metric("Conversations", totals["total_conversations"])
    cols[4].metric("Messages", totals["total_messages"])
    cols[5].metric("Messages Today", totals["messages_today"])

    st.subheader("Per Bot")
    if data["per_bot"]:
        st.table(data["per_bot"])
    else:
        st.info("No bots yet.")


# ---------- Bots (list + manage) ----------

def render_bots():
    st.header("Bots")

    try:
        bots = api_get("/api/bots")
    except httpx.HTTPStatusError as e:
        st.error(f"Failed to load bots: {e}")
        return

    if not bots:
        st.info("No bots yet — create one from the 'Create Bot' page.")
        return

    for bot in bots:
        with st.expander(f"{bot['name']} — {bot['status']}"):
            st.write(f"**Website:** {bot['website_url']}")
            st.write(f"**Description:** {bot.get('description') or '—'}")
            st.write(f"**Created:** {bot.get('created_at', '')[:19]}")
            st.write(f"**Updated:** {bot.get('updated_at', '')[:19]}")

            try:
                detail = api_get(f"/api/bots/{bot['id']}")
                st.write(f"**Documents:** {detail['documents']}  |  **Chunks:** {detail['chunks']}")
            except httpx.HTTPStatusError:
                pass

            with st.form(f"edit_form_{bot['id']}"):
                st.markdown("**Edit bot**")
                name = st.text_input("Name", value=bot["name"], key=f"name_{bot['id']}")
                website_url = st.text_input("Website URL", value=bot["website_url"], key=f"url_{bot['id']}")
                description = st.text_area(
                    "Description", value=bot.get("description", ""), key=f"desc_{bot['id']}"
                )
                system_prompt = st.text_area(
                    "System Prompt", value=bot.get("system_prompt", ""), key=f"sp_{bot['id']}"
                )
                save = st.form_submit_button("Save changes")

            if save:
                api_put(
                    f"/api/bots/{bot['id']}",
                    json={
                        "name": name,
                        "website_url": website_url,
                        "description": description,
                        "system_prompt": system_prompt,
                    },
                )
                st.success("Saved.")
                st.rerun()

            action_cols = st.columns(4)

            if action_cols[0].button("Rebuild knowledge base", key=f"reindex_{bot['id']}"):
                api_post(f"/api/bots/{bot['id']}/ingest")
                st.success("Re-index started in the background.")
                st.rerun()

            if bot["status"] == "disabled":
                if action_cols[1].button("Enable", key=f"enable_{bot['id']}"):
                    api_post(f"/api/bots/{bot['id']}/enable")
                    st.rerun()
            else:
                if action_cols[1].button("Disable", key=f"disable_{bot['id']}"):
                    api_post(f"/api/bots/{bot['id']}/disable")
                    st.rerun()

            confirm = action_cols[2].checkbox("Confirm delete", key=f"confirm_del_{bot['id']}")

            if action_cols[3].button("Delete", key=f"delete_{bot['id']}", disabled=not confirm):
                api_delete(f"/api/bots/{bot['id']}")
                st.success("Deleted.")
                st.rerun()


# ---------- Create Bot ----------

def render_create_bot():
    st.header("Create Bot")

    with st.form("create_bot_form"):
        name = st.text_input("Bot Name")
        website_url = st.text_input("Website URL", placeholder="https://example.com")
        description = st.text_area("Description (optional)")
        system_prompt = st.text_area("System Prompt (optional)")
        submitted = st.form_submit_button("Create Bot")

    if submitted:
        if not name or not website_url:
            st.error("Bot name and website URL are required.")
            return

        bot = api_post(
            "/api/bots",
            json={
                "name": name,
                "website_url": website_url,
                "description": description,
                "system_prompt": system_prompt,
            },
        )
        st.success(f"Bot '{bot['name']}' created — indexing has started in the background.")


# ---------- Test Chat ----------

def render_test_chat():
    st.header("Test Chat")
    st.caption("Each bot answers only from its own knowledge base — isolated per bot_id.")

    try:
        bots = api_get("/api/bots")
    except httpx.HTTPStatusError as e:
        st.error(f"Failed to load bots: {e}")
        return

    if not bots:
        st.info("No bots yet.")
        return

    bot_labels = {b["id"]: f"{b['name']} ({b['status']})" for b in bots}
    bot_id = st.selectbox("Select a bot", options=list(bot_labels.keys()), format_func=lambda i: bot_labels[i])

    if st.session_state.get("chat_bot_id") != bot_id:
        st.session_state["chat_bot_id"] = bot_id
        st.session_state["chat_session_id"] = secrets.token_hex(6)
        st.session_state["chat_history"] = []

    if st.button("New session"):
        st.session_state["chat_session_id"] = secrets.token_hex(6)
        st.session_state["chat_history"] = []
        st.rerun()

    for role, content in st.session_state["chat_history"]:
        with st.chat_message(role):
            st.write(content)

    question = st.chat_input("Ask a question...")

    if question:
        st.session_state["chat_history"].append(("user", question))
        try:
            result = api_post(
                f"/api/bots/{bot_id}/chat",
                json={"session_id": st.session_state["chat_session_id"], "message": question},
            )
            answer = result["answer"]
        except httpx.HTTPStatusError as e:
            answer = f"Error: {e}"
        st.session_state["chat_history"].append(("assistant", answer))
        st.rerun()


# ---------- Router ----------

if page == "Dashboard":
    render_dashboard()
elif page == "Bots":
    render_bots()
elif page == "Create Bot":
    render_create_bot()
elif page == "Test Chat":
    render_test_chat()
