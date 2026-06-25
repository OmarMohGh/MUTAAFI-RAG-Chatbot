import os
import time
import asyncio
import nest_asyncio
import pandas as pd
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv()

# Set up Langchain Google GenAI
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas.run_config import RunConfig
from datasets import Dataset
from supabase import create_client

from google import genai

class RateLimitedChat(ChatGoogleGenerativeAI):
    def _generate(self, *args, **kwargs):
        print("[RateLimitedChat] Waiting 15 seconds to avoid 429...", flush=True)
        time.sleep(15)
        return super()._generate(*args, **kwargs)
        
    async def _agenerate(self, *args, **kwargs):
        print("[RateLimitedChat] Waiting 15 seconds to avoid 429 (async)...", flush=True)
        await asyncio.sleep(15)
        return await super()._agenerate(*args, **kwargs)

os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")

llm = RateLimitedChat(model="gemini-2.5-flash", temperature=0)
embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

supabase_url = os.getenv("VITE_SUPABASE_URL", "")
supabase_key = os.getenv("VITE_SUPABASE_ANON_KEY", "")
supabase = create_client(supabase_url, supabase_key)
gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

questions = [
    "How much protein should I eat per day to build muscle?",
    "What is a calorie deficit and how do I calculate mine?",
    "What are the best food sources of protein?"
]

ground_truths = [
    ["For active individuals aiming to build muscle, the recommended intake is 1.6-2.2g of protein per kg of body weight."],
    ["A calorie deficit is when you consume fewer calories than you burn. A 500 calorie deficit leads to roughly 0.5kg of fat loss per week."],
    ["Good sources of protein include chicken, fish, eggs, dairy, tofu, and legumes."]
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
    context_text = "\n\n".join(contexts) if contexts else "No relevant information found in the knowledge base."
    
    # Generate
    system_instruction = (
        "You are Mutaafi Coach, an expert fitness and nutrition AI assistant. "
        "Answer the user's question using the verified facts provided below. "
        "Be concise, helpful, and encouraging. "
        "If the answer is not in the provided facts, politely say you don't have "
        "enough information on that topic yet.\n"
    )
    augmented_prompt = f"{system_instruction}\n--- VERIFIED FACTS ---\n{context_text}\n--- END OF FACTS ---\n\nUser Question: {query}"
    
    print(f"Generating answer for: {query}", flush=True)
    time.sleep(15) # Rate limit before generating
    chat_response = gemini_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=augmented_prompt
    )
    return contexts, chat_response.text

data = {"question": [], "answer": [], "contexts": [], "ground_truth": []}

print("Running pipeline to collect QA pairs...", flush=True)
for i, q in enumerate(questions):
    ctxs, ans = get_rag_response(q)
    data["question"].append(q)
    data["answer"].append(ans)
    data["contexts"].append(ctxs)
    data["ground_truth"].append(ground_truths[i][0])
    print(f"Collected QA for Q{i+1}", flush=True)

dataset = Dataset.from_dict(data)

print("\nStarting RAGAS Evaluation... (This will take a while due to rate limits)", flush=True)
metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

# We must limit concurrency to avoid rate limits
run_config = RunConfig(max_workers=1, max_retries=10)

result = evaluate(
    dataset,
    metrics=metrics,
    llm=llm,
    embeddings=embeddings,
    raise_exceptions=False,
    run_config=run_config
)

print("\n\n=== RAGAS EVALUATION RESULTS ===", flush=True)
print(result, flush=True)

df = result.to_pandas()
print("\n=== INDIVIDUAL SCORES ===", flush=True)
print(df[["question", "faithfulness", "answer_relevancy", "context_precision", "context_recall"]].to_markdown(index=False), flush=True)
