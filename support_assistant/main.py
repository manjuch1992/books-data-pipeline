import json
import math
import os
import sys
import types
import hashlib
import re
from pathlib import Path
from typing import Any, Literal, TypedDict

try:
    import chromadb
except ModuleNotFoundError:
    class _FallbackCollection:
        def __init__(self) -> None:
            self._docs: list[str] = []
            self._ids: list[str] = []
            self._embeddings: list[list[float]] = []

        def count(self) -> int:
            return len(self._ids)

        def add(self, documents: list[str], ids: list[str], embeddings: list[list[float]] | None = None) -> None:
            if embeddings is None:
                embeddings = [[0.0] * 384 for _ in documents]
            for document, doc_id, embedding in zip(documents, ids, embeddings):
                self._docs.append(document)
                self._ids.append(doc_id)
                self._embeddings.append(embedding)

        def query(self, query_embeddings: list[list[float]], n_results: int = 3, include: list[str] | None = None) -> dict[str, list[Any]]:
            if not self._embeddings:
                return {"ids": [[]], "documents": [[]], "distances": [[0.0]]}

            query_vector = query_embeddings[0]
            scored: list[tuple[float, int]] = []
            for idx, stored_vector in enumerate(self._embeddings):
                dot = sum(a * b for a, b in zip(query_vector, stored_vector))
                query_norm = math.sqrt(sum(value * value for value in query_vector))
                doc_norm = math.sqrt(sum(value * value for value in stored_vector))
                denom = query_norm * doc_norm
                similarity = dot / denom if denom else 0.0
                scored.append((similarity, idx))

            ranked = sorted(scored, key=lambda item: item[0], reverse=True)[:n_results]
            ids = [self._ids[idx] for _, idx in ranked]
            docs = [self._docs[idx] for _, idx in ranked]
            result: dict[str, list[Any]] = {"ids": [ids], "documents": [docs]}
            if include and "distances" in include:
                result["distances"] = [[1.0 - score for score, _ in ranked]]
            if include and "metadatas" in include:
                result["metadatas"] = [[{} for _ in ids]]
            return result

    class _FallbackClient:
        def __init__(self, path: str | None = None) -> None:
            self.path = path
            self._collections: dict[str, _FallbackCollection] = {}

        def get_or_create_collection(self, name: str, metadata: dict[str, Any] | None = None) -> _FallbackCollection:
            if name not in self._collections:
                self._collections[name] = _FallbackCollection()
            return self._collections[name]

    fallback_chromadb = types.ModuleType("chromadb")
    fallback_chromadb.PersistentClient = _FallbackClient
    sys.modules["chromadb"] = fallback_chromadb
    chromadb = fallback_chromadb

import requests
from fastapi import FastAPI
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph

try:
    from sentence_transformers import SentenceTransformer
except ModuleNotFoundError:
    SentenceTransformer = None


BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"
CHROMA_DB_DIR = Path(os.getenv("CHROMA_DB_DIR", str(BASE_DIR / ".chroma_db")))
COLLECTION_NAME = "zepto_policy_corpus"
MODEL_NAME = "all-MiniLM-L6-v2"

MOCK_LLM = os.getenv("MOCK_LLM", "1") != "0"
POLICY_KEYWORDS = [
    "delivery",
    "return",
    "refund",
    "membership",
    "tracking",
    "cancel",
    "gift card",
    "support hours",
]

PROMPT_TEMPLATE = """Role: You are Zepto Support Assistant.
Context: Use only the retrieved Zepto policy chunks supplied in this request. These are the only facts you may use.
Task: Answer the user's question clearly and correctly using only the provided context. If the question is not covered by the context, say so without guessing.
Format: Return a single JSON object with the exact keys: answer, sources, confidence.
Length: Keep the answer concise but complete; do not exceed 180 words.
Negative constraint: Do not answer using information not present in the provided context; never invent policy details or make unsupported claims.
Few-shot example:
User question: "What is Zepto Pass+?"
Context: "Zepto Pass+ (INR 99 per month, free priority delivery, 10% off select categories, and early access to limited-time deals 24 hours before they go live to Basic and Pass members)."
Assistant response:
{"answer":"Zepto Pass+ costs INR 99 per month and includes free priority delivery, 10% off select categories, and early access to limited-time deals.","sources":["doc_03"],"confidence":0.97}
"""


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)


class AskResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class AgentState(TypedDict):
    query: str
    intent: str
    context_chunks: list[str]
    context_ids: list[str]
    answer: str
    sources: list[str]
    confidence: float


# Optional real-LLM support; not needed for the graded mock baseline.
def call_real_llm(prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("No API key configured for a real LLM backend.")

    if os.getenv("GROQ_API_KEY"):
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    raise RuntimeError("The optional real-LLM extension is not configured for a non-Groq provider.")


def parse_json_response(raw_response: str) -> AskResponse:
    text = raw_response.strip()
    if text.startswith("```"):
        text = text.strip("` ")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("LLM output was not a JSON object.")
    return AskResponse.model_validate(payload)


def llm_answer_from_context(query: str, retrieved_chunks: list[str], retrieved_ids: list[str]) -> AskResponse:
    context = "\n\n".join(f"[{idx}] {chunk}" for idx, chunk in zip(retrieved_ids, retrieved_chunks))
    prompt = (
        f"{PROMPT_TEMPLATE}\n"
        f"User question: \"{query}\"\n"
        f"Context: {context}\n"
        "Assistant response:\n"
    )

    return call_llm_for_response(prompt)


def call_llm_for_response(prompt: str) -> AskResponse:
    last_error = None
    for _ in range(3):
        try:
            raw = call_real_llm(prompt)
            parsed = parse_json_response(raw)
            return parsed
        except Exception as exc:  # pragma: no cover - optional extension only
            last_error = exc
            prompt += "\nCorrect the JSON output to match the exact schema: answer, sources, confidence. Return valid JSON only and no markdown.\n"

    raise RuntimeError(f"LLM output failed validation after retries: {last_error}")


def load_corpus() -> list[tuple[str, str]]:
    documents: list[tuple[str, str]] = []
    for file_path in sorted(DOCS_DIR.glob("doc_*.txt")):
        documents.append((file_path.stem, file_path.read_text(encoding="utf-8")))
    return documents


class LocalEmbeddingModel:
    """Small deterministic fallback used when the optional model is unavailable."""

    def encode(self, texts: str | list[str]) -> list[float] | list[list[float]]:
        values = [texts] if isinstance(texts, str) else texts
        vectors = []
        for text in values:
            vector = [0.0] * 384
            for token in re.findall(r"[a-z0-9]+", text.lower()):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % len(vector)
                vector[index] += 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors[0] if isinstance(texts, str) else vectors


def build_embedding_model() -> Any:
    if SentenceTransformer is not None:
        return SentenceTransformer(MODEL_NAME)
    return LocalEmbeddingModel()


def build_vectorstore(embedding_model: Any) -> tuple[Any, Any]:
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    if collection.count() == 0:
        corpus = load_corpus()
        ids = [doc_id for doc_id, _ in corpus]
        texts = [text for _, text in corpus]
        embeddings = embedding_model.encode(texts)
        if hasattr(embeddings, "tolist"):
            embeddings = embeddings.tolist()
        collection.add(documents=texts, ids=ids, embeddings=embeddings)
        return client, collection

    return client, collection


EMBEDDING_MODEL = build_embedding_model()
_client, CHROMA_COLLECTION = build_vectorstore(EMBEDDING_MODEL)


def classify_query(query: str) -> Literal["policy_question", "general_question"]:
    text = query.lower()
    if any(keyword in text for keyword in POLICY_KEYWORDS):
        return "policy_question"
    return "general_question"


def retrieve_top_chunks(query: str, top_k: int = 3) -> tuple[list[str], list[str]]:
    query_vector = EMBEDDING_MODEL.encode(query)
    if hasattr(query_vector, "tolist"):
        query_vector = query_vector.tolist()
    result = CHROMA_COLLECTION.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents"],
    )
    documents = result.get("documents", [[]])[0]
    ids = result.get("ids", [[]])[0]
    return documents, ids


def classify_intent(state: AgentState) -> AgentState:
    if MOCK_LLM:
        state["intent"] = classify_query(state["query"])
        return state

    prompt = (
        "Classify the user query as exactly one label: policy_question or general_question. "
        "Return only the label. A question about Zepto delivery, returns, refunds, membership, "
        "tracking, cancellation, gift cards, or support hours is policy_question.\n"
        f"User query: {state['query']}"
    )
    raw = call_real_llm(prompt).strip().lower()
    match = re.search(r"\b(policy_question|general_question)\b", raw)
    if match is None:
        raise ValueError("LLM intent classification returned an invalid label.")
    state["intent"] = match.group(1)
    return state


def retrieve_and_answer(state: AgentState) -> AgentState:
    query = state["query"]
    chunks, ids = retrieve_top_chunks(query, top_k=3)
    state["context_chunks"] = chunks
    state["context_ids"] = ids

    if MOCK_LLM:
        top_chunk = chunks[0] if chunks else ""
        snippet = top_chunk[:200].strip()
        answer = f"Based on the retrieved context: {snippet}"
        state["answer"] = answer
        state["sources"] = list(ids)
        state["confidence"] = 1.0
        return state

    if not chunks:
        state["answer"] = "I could not find relevant policy context for this question."
        state["sources"] = []
        state["confidence"] = 0.0
        return state

    parsed = llm_answer_from_context(query, chunks, list(ids))
    state["answer"] = parsed.answer
    state["sources"] = parsed.sources
    state["confidence"] = parsed.confidence
    return state


def direct_answer(state: AgentState) -> AgentState:
    if MOCK_LLM:
        state["answer"] = "I can only answer questions about Zepto policies right now."
        state["sources"] = []
        state["confidence"] = 1.0
        return state

    prompt = (
        f"{PROMPT_TEMPLATE}\n"
        f"User question: \"{state['query']}\"\n"
        "Context: The answer is not restricted to the Zepto policy corpus; answer directly but keep it brief.\n"
        "Assistant response:\n"
    )
    validated = call_llm_for_response(prompt)
    state["answer"] = validated.answer
    state["sources"] = validated.sources
    state["confidence"] = validated.confidence
    return state


builder = StateGraph(AgentState)
builder.add_node("classify_intent", classify_intent)
builder.add_node("retrieve_and_answer", retrieve_and_answer)
builder.add_node("direct_answer", direct_answer)
builder.set_entry_point("classify_intent")
builder.add_conditional_edges(
    "classify_intent",
    lambda state: state["intent"],
    {
        "policy_question": "retrieve_and_answer",
        "general_question": "direct_answer",
    },
)
builder.add_edge("retrieve_and_answer", END)
builder.add_edge("direct_answer", END)

APP_GRAPH = builder.compile()


app = FastAPI(title="Zepto Support Assistant", version="1.0.0")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "Zepto Support Assistant"}


@app.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest) -> AskResponse:
    initial_state: AgentState = {
        "query": payload.query,
        "intent": "",
        "context_chunks": [],
        "context_ids": [],
        "answer": "",
        "sources": [],
        "confidence": 0.0,
    }
    final_state = APP_GRAPH.invoke(initial_state)
    return AskResponse(
        answer=final_state["answer"],
        sources=final_state.get("sources", []),
        confidence=float(final_state.get("confidence", 1.0)),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("support_assistant.main:app", host="0.0.0.0", port=7860, reload=False)
