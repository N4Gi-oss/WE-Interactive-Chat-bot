"""
Retrieval + answer generation.
Change from the original notebook: google.colab.userdata (only works
inside Colab) -> os.getenv with python-dotenv, so this runs anywhere
(local machine, on-prem server, Docker container).
"""

import os
from dotenv import load_dotenv
from google import genai

from vector_store import search

load_dotenv()  # reads .env in the project root if present

_client_gemini = None

# Cosine distance above this = "not actually relevant", so it's dropped
# from context instead of confusing the model with unrelated chunks.
# (ChromaDB always returns top_k results even if none are close -- this
# threshold is what turns "closest available" into "actually relevant".)
RELEVANCE_THRESHOLD = 0.55

SYSTEM_PROMPT = """You are a friendly customer support assistant for Telecom Egypt (WE).

- If the customer sends casual small talk (greetings like "ازيك", "hello", "hi", thanks, goodbye, etc.), respond naturally and briefly and warmly — you don't need the context for this.
- If the customer asks about a WE service or price, answer ONLY using the information provided in the context below. If the answer is not in the context, say clearly that you don't have this information and suggest contacting WE customer service on 155.
- Never invent prices, USSD codes, or details that aren't in the context.
- Always answer in the same language as the customer's question (Arabic or English).
- Be concise."""

QUERY_NORMALIZE_PROMPT = """Extract the core WE (Telecom Egypt) service/topic being asked about, fixing any spelling mistakes, and dropping unrelated specifics (like a singer's name, a person's name, or extra filler words) that a semantic search over WE's service pages wouldn't need.
Reply with ONLY the short core topic (1-4 words), nothing else. If the message is just small talk/a greeting with no WE topic, reply with exactly: NONE

Message: {query}
Core topic:"""


def get_gemini_client() -> genai.Client:
    global _client_gemini
    if _client_gemini is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. Copy .env.example to .env and fill it in."
            )
        _client_gemini = genai.Client(api_key=api_key)
    return _client_gemini


def normalize_query(query: str) -> str:
    """
    Ask Gemini to strip a raw customer message down to the core WE
    topic/keywords, correcting typos and removing specifics (artist
    names, etc.) that hurt semantic search recall. Falls back to the
    original query on any error so a hiccup here never breaks search.
    """
    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=QUERY_NORMALIZE_PROMPT.format(query=query),
        )
        cleaned = (response.text or "").strip()
        if not cleaned or cleaned.upper() == "NONE":
            return query
        return cleaned
    except Exception:
        return query


def generate_answer(query: str, top_k: int = 5) -> str:
    search_query = normalize_query(query)
    results = search(search_query, top_k=top_k)

    documents = results["documents"][0] if results["documents"] else []
    distances = results["distances"][0] if results.get("distances") else []

    # Only keep chunks that are actually close enough to be relevant --
    # otherwise a greeting or off-topic message would drag in unrelated
    # WE content as "context" and confuse the model.
    relevant_docs = [
        doc for doc, dist in zip(documents, distances) if dist <= RELEVANCE_THRESHOLD
    ]

    context = "\n\n".join(relevant_docs) if relevant_docs else "(no matching WE content found for this query)"
    prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{context}\n\nCustomer question: {query}"

    client = get_gemini_client()
    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt,
    )
    return response.text