#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_knowledge.py — Chatbot Knowledge Base Seeder
====================================================
FILE:    seed_knowledge.py
PROJECT: MUTAAFI — AI-Powered Fitness & Nutrition Platform (CPCS 499)

WHAT THIS FILE DOES:
    Inserts hand-written fitness/nutrition knowledge entries into the
    Supabase chatbot_knowledge_base table.  For each entry it:
      1. Generates a 768-dimensional embedding vector via
         Google Gemini (gemini-embedding-001).
      2. Inserts the text + embedding into chatbot_knowledge_base
         so the RAG chatbot can retrieve it at query time.

HOW IT FITS IN THE PROJECT:
    This script is the MANUAL seeder — the developer adds entries to
    the knowledge_entries list, then runs the script once.  For bulk
    ingestion of meals and exercises, see ingest_meals_exercises.py.

HOW TO RUN:
    1. Add entries to the knowledge_entries list below.
    2. Ensure backend/.env has VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY,
       and GOOGLE_API_KEY.
    3. Run:  python seed_knowledge.py
"""


# ========================= IMPORTS ==========================
import os
from dotenv import load_dotenv
from supabase import create_client
from google import genai


# ===================== CONSTANTS & CONFIG =====================
# Load environment variables and create API clients.
load_dotenv()

# Supabase client (uses anon key — RLS must allow inserts)
supabase = create_client(
    os.getenv("VITE_SUPABASE_URL", ""),
    os.getenv("VITE_SUPABASE_ANON_KEY", "")
)

# Google Gemini client for generating embedding vectors
gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY", ""))

# ── Knowledge Base Entries ──
# Populate this list with new entries before running this script.
# Each entry requires: content_summary, source_title, source_url.
knowledge_entries = []


# ===================== HELPER FUNCTIONS =======================

def seed():
    """
    Iterate over knowledge_entries, embed each one, and insert
    into the chatbot_knowledge_base table.

    Parameters:
        None — reads from the module-level knowledge_entries list.

    Returns:
        None — progress is printed to stdout.

    When / why it is called:
        Invoked from the __main__ guard.  The developer fills
        knowledge_entries with new facts and runs the script to
        seed them into the database.
    """
    print(f"Seeding {len(knowledge_entries)} entries into chatbot_knowledge_base...\n")

    for i, entry in enumerate(knowledge_entries):
        text = entry["content_summary"]
        print(f"  [{i+1}/{len(knowledge_entries)}] Embedding: \"{text[:60]}...\"")

        # Generate a 768-dim embedding vector via Gemini
        result = gemini_client.models.embed_content(
            model='gemini-embedding-001',
            contents=text,
        )
        embedding = result.embeddings[0].values

        # Get today's date for the last_verified_date column
        from datetime import date
        today_str = str(date.today())

        # Insert the entry into Supabase
        supabase.table('chatbot_knowledge_base').insert({
            'content_summary': entry['content_summary'],
            'source_title': entry['source_title'],
            'source_url': entry['source_url'],
            'embedding_vector': embedding,
            'last_verified_date': today_str
        }).execute()

        print(f"         ✓ Inserted (vector length: {len(embedding)})")

    print(f"\n✅ Done! {len(knowledge_entries)} rows seeded into chatbot_knowledge_base.")


# ======================== ENTRY POINT ========================
if __name__ == '__main__':
    seed()
