# 🤖 MUTAAFI — RAG Chatbot Module

> **Retrieval-Augmented Generation (RAG) AI Coach for the MUTAAFI Fitness & Nutrition Platform**

Part of the **MUTAAFI** project — an AI-powered fitness and nutrition platform developed for CPCS 499 (Senior Project).

---

## 📌 Overview

The MUTAAFI RAG Chatbot is an intelligent, personalized AI fitness coach powered by **Google Gemini** and **pgvector** (Supabase). It answers user questions about fitness and nutrition by:

1. **Embedding** the user's query using `gemini-embedding-001` (768-dimensional vectors).
2. **Retrieving** the most semantically relevant documents from the `chatbot_knowledge_base` table via cosine similarity (pgvector).
3. **Filtering** retrieved documents for allergen safety based on the authenticated user's profile.
4. **Injecting** the user's profile context (goals, weight, height, allergies, calorie targets) into the prompt.
5. **Generating** a grounded, personalized response using `gemini-2.5-flash`.

---

## 🏗️ Architecture

```
User Question
     │
     ▼
┌────────────────────────────────────────────┐
│  Frontend (React + Vite)                   │
│  ├── AICoach.jsx          (Full-page chat) │
│  ├── GlobalChatOverlay.jsx (Floating chat) │
│  └── AdminKnowledgeBase.jsx (Admin panel)  │
└────────────────┬───────────────────────────┘
                 │  POST /api/chat
                 ▼
┌────────────────────────────────────────────┐
│  Backend (Flask — app.py)                  │
│  ├── /api/chat            (RAG endpoint)   │
│  └── /api/admin/knowledge (Knowledge CRUD) │
└───────┬─────────────┬──────────────────────┘
        │             │
        ▼             ▼
┌──────────────┐  ┌──────────────────────────┐
│ Google Gemini│  │ Supabase (PostgreSQL)     │
│ Embeddings & │  │ ├── chatbot_knowledge_base│
│ Generation   │  │ └── user_data (profiles)  │
└──────────────┘  └──────────────────────────┘
```

---

## 📁 Repository Structure

```
MUTAAFI-RAG-Chatbot/
│
├── backend/
│   ├── app.py                    # Flask API — /api/chat & /api/admin/knowledge endpoints
│   ├── seed_knowledge.py         # Manual knowledge base seeder (embed + insert)
│   ├── ingest_meals_exercises.py # Bulk ingest meals & exercises into knowledge base
│   ├── evaluate_ragas.py         # RAGAS evaluation script (full suite, disabled by default)
│   ├── run_limited_ragas.py      # RAGAS evaluation (limited 3-question version)
│   └── .env.example              # Environment variable template
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── AICoach.jsx           # Full-screen RAG chat interface
│       │   └── AdminKnowledgeBase.jsx # Admin panel to add knowledge entries
│       ├── components/
│       │   └── GlobalChatOverlay.jsx  # Floating chat widget (accessible app-wide)
│       └── supabaseClient.js          # Supabase client initialization
│
├── .gitignore
└── README.md
```

---

## ⚙️ Tech Stack

| Layer       | Technology                                              |
|-------------|---------------------------------------------------------|
| Frontend    | React 19, Vite, TailwindCSS, `react-markdown`           |
| Backend     | Python 3, Flask, Flask-CORS                             |
| AI / LLM    | Google Gemini 2.5 Flash (`gemini-2.5-flash`)            |
| Embeddings  | Google Gemini Embedding (`gemini-embedding-001`, 768-d) |
| Vector DB   | Supabase + pgvector (cosine similarity)                 |
| Auth        | Supabase Auth (JWT Bearer tokens)                       |
| Evaluation  | RAGAS framework (Faithfulness, Relevancy, Precision, Recall) |

---

## 🗄️ Supabase Schema

### `chatbot_knowledge_base` table

| Column              | Type           | Description                             |
|---------------------|----------------|-----------------------------------------|
| `doc_id`            | `bigint` (PK)  | Auto-incrementing primary key           |
| `content_summary`   | `text`         | The knowledge entry text                |
| `source_title`      | `text`         | Human-readable source label             |
| `source_url`        | `text`         | Optional link to the original source    |
| `embedding_vector`  | `vector(768)`  | Gemini embedding for semantic search    |
| `last_verified_date`| `date`         | When the entry was last verified        |

### `match_knowledge_docs` — pgvector RPC function

```sql
CREATE OR REPLACE FUNCTION match_knowledge_docs(
  query_embedding vector(768),
  match_count int DEFAULT 3
)
RETURNS TABLE (
  doc_id bigint,
  content_summary text,
  source_title text,
  source_url text,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    kb.doc_id,
    kb.content_summary,
    kb.source_title,
    kb.source_url,
    1 - (kb.embedding_vector <=> query_embedding) AS similarity
  FROM chatbot_knowledge_base kb
  ORDER BY kb.embedding_vector <=> query_embedding
  LIMIT match_count;
END;
$$;
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- A [Supabase](https://supabase.com) project with the `chatbot_knowledge_base` table and `match_knowledge_docs` function created (see schema above)
- A [Google AI Studio](https://aistudio.google.com) API key with access to Gemini models

---

### 1. Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

# Install dependencies
pip install flask flask-cors python-dotenv supabase google-genai

# Configure environment
cp .env.example .env
# → Fill in your keys in .env

# Run the Flask server
python app.py
# Server starts at http://localhost:5000
```

#### Backend Environment Variables (`.env`)

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
GOOGLE_API_KEY=your_google_api_key
```

---

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# → Add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY

# Run the dev server
npm run dev
# App starts at http://localhost:5173
```

> **Note:** The frontend calls the backend at `http://127.0.0.1:5000`. Make sure the Flask server is running before starting the frontend.

---

### 3. Seed the Knowledge Base

**Option A — Manual seeder** (add individual facts):

```bash
cd backend
# Edit seed_knowledge.py → fill the knowledge_entries list
python seed_knowledge.py
```

**Option B — Bulk ingest** (from Supabase meal/exercise tables):

```bash
cd backend
python ingest_meals_exercises.py
```

---

## 📡 API Endpoints

### `POST /api/chat`

RAG chatbot endpoint. Embeds the query, retrieves relevant knowledge, and generates a personalized response.

**Request Headers:**
```
Content-Type: application/json
Authorization: Bearer <supabase_jwt>   (optional, enables personalization)
```

**Request Body:**
```json
{ "message": "How much protein should I eat to build muscle?" }
```

**Response:**
```json
{
  "reply": "For muscle building, aim for 1.6–2.2g of protein per kg of body weight...",
  "sources": "Exercise Guide: Squats, Nutrition 101"
}
```

---

### `POST /api/admin/knowledge`

Admin-only endpoint to add a new knowledge entry with auto-generated embeddings.

**Request Headers:**
```
Content-Type: application/json
Authorization: Bearer <admin_jwt>   (must be admin@mutaafi.com)
```

**Request Body:**
```json
{
  "content_summary": "Squats primarily target the quadriceps, glutes, and hamstrings.",
  "source_title": "Exercise Guide: Squats",
  "source_url": "https://mutaafi.com/guides/squats"
}
```

---

## 📊 RAG Evaluation (RAGAS)

This module includes two evaluation scripts using the [RAGAS](https://docs.ragas.io) framework:

| Script                  | Description                                          |
|-------------------------|------------------------------------------------------|
| `evaluate_ragas.py`     | Full 8-question suite (disabled by default)          |
| `run_limited_ragas.py`  | Lightweight 3-question version (active)              |

**Metrics evaluated:**
- **Faithfulness** — Does the answer stay grounded in the retrieved context?
- **Answer Relevancy** — Is the answer relevant to the question?
- **Context Precision** — Are the retrieved documents precise?
- **Context Recall** — Are all relevant documents retrieved?

**To run:**
```bash
pip install ragas langchain-google-genai datasets nest_asyncio
python run_limited_ragas.py
```

> ⚠️ Evaluation uses rate-limited Gemini API calls and may take 5–20 minutes to complete.

---


