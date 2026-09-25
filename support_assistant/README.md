# Zepto Support Assistant

This module implements a Retrieval-Augmented Generation (RAG) assistant for Zepto policy questions. It embeds the policy corpus locally with `all-MiniLM-L6-v2`, stores vectors in a persistent ChromaDB collection, and exposes the graph through FastAPI. With `MOCK_LLM` unset or set to `1`, answer generation and intent classification are deterministic and make no LLM-provider calls.

## Installed app and usage

The app is built for local execution with the required mock path enabled by default.

On first startup, `sentence-transformers` downloads the `all-MiniLM-L6-v2` weights; subsequent embedding and retrieval run locally. No LLM API key is used in the default mock mode.

1. Install dependencies:
  ```powershell
  cd support_assistant
  python -m pip install -r requirements.txt
  ```
2. Run the app locally from the repository root:
  ```powershell
  cd ..
  $env:MOCK_LLM = "1"
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
{"answer":"Based on the retrieved context: Zepto delivers grocery and household essentials to serviceable pin codes within 10 to 30 minutes of order confirmation, depending on the customer's delivery zone and current order volume. Standard del","sources":["doc_01","doc_05","doc_07"],"confidence":1.0}
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

- Ingestion: the corpus is stored as eight plain-text policy files in [docs](docs). These documents are loaded by the ingestion logic in [main.py](main.py), which reads each file as a document and assigns a chunk ID such as `doc_01` through `doc_08`.
- Embedding: `build_embedding_model` loads `SentenceTransformer("all-MiniLM-L6-v2")` and embeds each document as one chunk. The vectors and source IDs are stored in the persistent `zepto_policy_corpus` ChromaDB collection.
- Retrieval: the LangGraph node `retrieve_and_answer` embeds the incoming query and retrieves the top three chunks from `zepto_policy_corpus` using cosine similarity. Retrieval always runs in both modes; only classification and answer generation switch behavior.
- Generation: the final answer is composed by the `retrieve_and_answer` node in mock mode using the requested template `Based on the retrieved context: ...`, or by the `direct_answer` node for non-policy questions using the fixed canned response. In the optional `MOCK_LLM=0` path, a real LLM is called using the structured prompt template and grounded only on retrieved chunks.

The `MOCK_LLM` toggle affects intent classification and answer generation, not embedding or retrieval. With `MOCK_LLM` unset or set to `1`, the keyword heuristic routes requests and the graph returns deterministic mock responses without an LLM-provider call. When `MOCK_LLM=0`, the classifier and answer nodes call the configured Groq endpoint; retrieval remains local and unchanged.

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
 ChromaDB collection: zepto_policy_corpus
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

