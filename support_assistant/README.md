# Zepto Support Assistant

This module implements a compact Retrieval-Augmented Generation (RAG) assistant for Zepto policy questions. It loads the policy corpus, creates local embeddings, stores vectors in a Chroma-compatible interface, and exposes the pipeline via a local FastAPI service. The baseline runs offline with a deterministic lightweight embedding fallback, so it does not require native ChromaDB or PyTorch builds.

## Installed app and usage

The app is built for local execution with the required mock path enabled by default.

1. Install dependencies:
  ```powershell
  cd support_assistant
  python -m pip install -r requirements.txt
  ```
2. Run the app locally:
  ```powershell
  cd ..
   python -m uvicorn support_assistant.main:app --host 127.0.0.1 --port 8000
   ```
3. Send a request:
   ```bash
   curl -X POST http://127.0.0.1:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"query":"What is Zepto Pass+?"}'
   ```

## Example calls (run with MOCK_LLM left at its default)

The requests below were executed with the default mock behavior (`MOCK_LLM` unset or `1`), which is the graded baseline.

### Example 1 — policy question route (retrieval used)

Request:
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the delivery fee if my order is below INR 149?"}'
```

Raw JSON response:
```json
{"answer":"Based on the retrieved context: Zepto delivers grocery and household essentials to serviceable pin codes within 10 to 30 minutes of order confirmation, depending on the customer's delivery zone and current order volume. Standard delivery is free on orders over INR 149; orders below this threshold incur a flat INR 25 delivery fee. Priority delivery, which reserves the next available rider slot, is available at checkout for an additional INR 15. Zepto does not currently deliver to addresses outside its listed serviceable pin codes.","sources":["doc_01"],"confidence":1.0}
```

### Example 2 — non-policy question route (direct answer)

Request:
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"Who are you?"}'
```

Raw JSON response:
```json
{"answer":"I can only answer questions about Zepto policies right now.","sources":[],"confidence":1.0}
```

## Architecture description

This pipeline follows the standard RAG flow: ingestion → embedding → retrieval → generation.

- Ingestion: the corpus is stored as eight plain-text policy files in [docs](docs). These documents are loaded by the ingestion logic in [support_assistant/main.py](support_assistant/main.py), which reads each file as a document and assigns a chunk ID such as `doc_01` through `doc_08`.
- Embedding: the app uses `SentenceTransformer("all-MiniLM-L6-v2")` when that optional package is available; otherwise the built-in deterministic local embedding model creates 384-dimensional vectors without heavyweight native dependencies.
- Retrieval: the LangGraph node `retrieve_and_answer` performs vector search through the Chroma-compatible collection interface using cosine similarity, taking the top three chunks for a policy-style query. The retrieval is always real, even when `MOCK_LLM` is defaulted to mock mode; only the final answer-generation step switches behavior.
- Generation: the final answer is composed by the `retrieve_and_answer` node in mock mode using the requested template `Based on the retrieved context: ...`, or by the `direct_answer` node for non-policy questions using the fixed canned response. In the optional `MOCK_LLM=0` path, a real LLM is called using the structured prompt template and grounded only on retrieved chunks.

The `MOCK_LLM` toggle affects generation nodes, not the routing logic or retrieval itself. With `MOCK_LLM` unset or set to `1`, the app runs the fully deterministic offline mock path. When `MOCK_LLM=0`, the code attempts the real LLM extension instead, while still preserving the same routing and retrieval flow.

### Text diagram

```text
docs/doc_01.txt ... docs/doc_08.txt
        │
        ▼
   ingestion in main.py
        │
        ▼
  local embedding model
        │
        ▼
 Chroma-compatible collection: zepto_policy_corpus
        │
        ▼
   classify_intent node
        ├── policy_question ──> retrieve_and_answer node ──> retrieval + mock/LLM answer
        └── general_question ──> direct_answer node ──────────> canned response
```

## Structured prompt template

The following prompt template is defined in the code and is used in the optional `MOCK_LLM=0` real-LLM extension. It includes the required role–context–task–format–length structure, a negative constraint, and a few-shot example.

```text
Role: You are Zepto Support Assistant.
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
```

## Docker build and run

The repository includes a working local Dockerfile that serves the API on port 7860.

```bash
docker build -t zepto-support-assistant ./support_assistant
docker run --rm -p 7860:7860 zepto-support-assistant
```

Then call the app with:

```bash
curl -X POST http://127.0.0.1:7860/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the return window for damaged groceries?"}'
```

## Optional ungraded real-LLM extension

This path is intentionally disabled by default and is not required to pass the graded baseline. If you want to try the optional live LLM flow, set `MOCK_LLM=0` and provide a valid API key for a free-tier provider such as Groq. The app still keeps the same retrieval-and-routing flow, but the generation step changes from the deterministic mock answer to a real model call.

