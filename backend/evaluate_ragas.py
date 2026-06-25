#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluate_ragas.py — RAG Chatbot Quality Evaluation (RAGAS Framework)
======================================================================
FILE:    evaluate_ragas.py
PROJECT: MUTAAFI — AI-Powered Fitness & Nutrition Platform (CPCS 499)

WHAT THIS FILE DOES:
    Evaluates the quality of the RAG (Retrieval-Augmented Generation)
    chatbot using the RAGAS evaluation framework.  It:
      1. Sends 8 fitness/nutrition questions through the live RAG pipeline
         (embed → retrieve → generate).
      2. Collects the answers and retrieved contexts.
      3. Runs RAGAS metrics: Faithfulness, Answer Relevancy,
         Context Precision, and Context Recall.
      4. Prints individual and aggregate scores.

HOW IT FITS IN THE PROJECT:
    This is an offline evaluation script used to benchmark the
    chatbot implemented in app.py's /api/chat endpoint.  It
    replicates the same retrieval + generation pipeline so the
    metrics reflect real system behaviour.

STATUS:
    The entire script body is currently DISABLED (wrapped in a
    multi-line string) because it requires heavy dependencies
    (ragas, langchain, datasets) and rate-limited Gemini API calls.
    Unwrap the docstring to re-enable.

HOW TO RUN (when enabled):
    1. pip install ragas langchain-google-genai datasets nest_asyncio
    2. Ensure backend/.env has VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY,
       and GOOGLE_API_KEY.
    3. Unwrap the triple-quoted string delimiters at lines 39 and 133.
    4. Run:  python evaluate_ragas.py
    NOTE: Execution takes 15-20 minutes due to rate-limit sleeps.
"""

# ═══════════════════════════════════════════════════════════════
# The code below is wrapped in a multi-line string to disable
# execution.  Remove the opening and closing triple-quotes
# (lines immediately below and at the end) to re-enable.
# ═══════════════════════════════════════════════════════════════

"""
import os
import time
import nest_asyncio
import pandas as pd
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv()

# Set up Langchain Google GenAI
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from datasets import Dataset
from supabase import create_client

from google import genai

# Ragas expects llm and embeddings objects.
# We will use rate-limited wrappers to avoid 429 errors (5 req / min)

class RateLimitedChat(ChatGoogleGenerativeAI):
    def _generate(self, *args, **kwargs):
        print("[RateLimitedChat] Waiting 15 seconds to avoid 429...")
        time.sleep(15)
        return super()._generate(*args, **kwargs)
        
    async def _agenerate(self, *args, **kwargs):
        print("[RateLimitedChat] Waiting 15 seconds to avoid 429...")
        time.sleep(15)
        return await super()._agenerate(*args, **kwargs)

os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")

llm = RateLimitedChat(model="gemini-2.5-flash", temperature=0)
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

supabase_url = os.getenv("VITE_SUPABASE_URL", "")
supabase_key = os.getenv("VITE_SUPABASE_ANON_KEY", "")
supabase = create_client(supabase_url, supabase_key)
gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

questions = [
    "How much protein should I eat per day to build muscle?",
    "What is a calorie deficit and how do I calculate mine?",
    "What are the best food sources of protein?",
    "What muscles does a squat target?",
    "How many rest days should I take per week?",
    "What is progressive overload and why does it matter?",
    "What should I eat on a workout day versus a rest day?",
    "What is the best workout split for someone trying to lose weight?"
]

ground_truths = [
    ["For active individuals aiming to build muscle, the recommended intake is 1.6-2.2g of protein per kg of body weight."],
    ["A calorie deficit is when you consume fewer calories than you burn. A 500 calorie deficit leads to roughly 0.5kg of fat loss per week."],
    ["Good sources of protein include chicken, fish, eggs, dairy, tofu, and legumes."],
    ["Squats primarily target the quadriceps, glutes, and hamstrings."],
    ["You should take 1-2 rest days weekly, ensuring 48-72 hours of rest between training the same muscle group."],
    ["Progressive overload is gradually increasing training stress (like adding weight or reps) over time so the body continues to adapt."],
    ["The provided facts do not explicitly specify dietary differences between workout and rest days."],
    ["The provided facts recommend strength training all major muscle groups at least 2 days per week along with maintaining a calorie deficit."]
]

def get_rag_response(query):
    # Retrieve
    result = gemini_client.models.embed_content(
        model='gemini-embedding-001',
        contents=query,
    )
    query_embedding = result.embeddings[0].values

    rpc_result = supabase.rpc('match_knowledge_docs', {
        'query_embedding': query_embedding,
        'match_count': 3
    }).execute()
    
    retrieved_docs = rpc_result.data if rpc_result.data else []
    contexts = [doc.get('content_summary', '') for doc in retrieved_docs]
    context_text = "\\n\\n".join(contexts) if contexts else "No relevant information found in the knowledge base."
    
    # Generate
    system_instruction = (
        "You are Mutaafi Coach, an expert fitness and nutrition AI assistant. "
        "Answer the user's question using the verified facts provided below. "
        "Be concise, helpful, and encouraging. "
        "If the answer is not in the provided facts, politely say you don't have "
        "enough information on that topic yet.\\n"
    )
    augmented_prompt = f"{system_instruction}\\n--- VERIFIED FACTS ---\\n{context_text}\\n--- END OF FACTS ---\\n\\nUser Question: {query}"
    
    print(f"Generating answer for: {query}")
    time.sleep(15) # Rate limit before generating
    chat_response = gemini_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=augmented_prompt
    )
    return contexts, chat_response.text

data = {"question": [], "answer": [], "contexts": [], "ground_truth": []}

print("Running pipeline to collect QA pairs...")
for i, q in enumerate(questions):
    ctxs, ans = get_rag_response(q)
    data["question"].append(q)
    data["answer"].append(ans)
    data["contexts"].append(ctxs)
    data["ground_truth"].append(ground_truths[i][0])
    print(f"Collected QA for Q{i+1}", flush=True)

dataset = Dataset.from_dict(data)

print("\\nStarting RAGAS Evaluation... (This will take a while due to rate limits)")
metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

# We must limit concurrency to avoid rate limits
result = evaluate(
    dataset,
    metrics=metrics,
    llm=llm,
    embeddings=embeddings,
    raise_exceptions=False,
    max_workers=1
)

print("\\n\\n=== RAGAS EVALUATION RESULTS ===")
print(result)

df = result.to_pandas()
print("\\n=== INDIVIDUAL SCORES ===")
print(df[["question", "faithfulness", "answer_relevancy", "context_precision", "context_recall"]].to_markdown(index=False))
"""
