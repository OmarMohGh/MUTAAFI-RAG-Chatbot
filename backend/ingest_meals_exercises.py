#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest_meals_exercises.py — Knowledge Base Bulk Ingestion
===========================================================
FILE:    ingest_meals_exercises.py
PROJECT: MUTAAFI — AI-Powered Fitness & Nutrition Platform (CPCS 499)

WHAT THIS FILE DOES:
    Populates the chatbot_knowledge_base table with dense text
    summaries + 768-dim embedding vectors for every row in:
      - nutrition_data  (meals)
      - workout_data    (exercises)

    This enables the RAG chatbot to answer questions like
    "How do I cook Caesar Salad?" or "What's a good chest exercise
    with a barbell?".

HOW IT FITS IN THE PROJECT:
    After the raw meal and exercise data is loaded into Supabase,
    this script converts each row into a searchable knowledge entry.
    The /api/chat endpoint in app.py then retrieves these entries
    via pgvector cosine similarity at query time.

IDEMPOTENCY:
    The script is SAFE TO RE-RUN.  It deletes any existing row with
    the same source_title before inserting, so re-runs never create
    duplicates.  The source tables (nutrition_data, workout_data)
    are NEVER modified.

HOW TO RUN:
    1. Ensure backend/.env has VITE_SUPABASE_URL,
       SUPABASE_SERVICE_ROLE_KEY, and GOOGLE_API_KEY.
    2. Run:  python ingest_meals_exercises.py
    NOTE: Takes several minutes due to 1-second rate-limit sleeps.
"""


# ========================= IMPORTS ==========================
import os
import sys
import time
from datetime import date
from dotenv import load_dotenv
from supabase import create_client
from google import genai


# ===================== CONSTANTS & CONFIG =====================
# Force UTF-8 stdout on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Load environment variables from .env
load_dotenv()

# Supabase client (service role key to bypass RLS)
SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "")
SERVICE_KEY  = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
supabase = create_client(SUPABASE_URL, SERVICE_KEY)

# Google Gemini client for generating embedding vectors
gemini   = genai.Client(api_key=os.getenv("GOOGLE_API_KEY", ""))

# Today's date string for the last_verified_date column
TODAY = str(date.today())


# ==================== HELPER FUNCTIONS =======================
# Text synthesis functions that convert DB rows into dense
# natural-language summaries, plus embed and upsert utilities.
# =============================================================

def synthesize_meal_text(meal: dict) -> str:
    """
    Build a dense text string from a nutrition_data row.

    Parameters:
        meal (dict): A single row from nutrition_data with keys like
                     meal_name, tags, allergies, calories, protein, etc.

    Returns:
        str: A natural-language summary suitable for embedding.

    Called by:
        ingest() — for each meal in the catalogue.
    """
    name       = meal.get('meal_name', 'Unknown Meal')
    tags       = ', '.join(meal.get('tags') or []) or 'None'
    allergens  = meal.get('allergies', '') or 'None'
    calories   = meal.get('calories', 0)
    protein    = meal.get('protein', 0)
    carbs      = meal.get('carbs', 0)
    fats       = meal.get('fats', 0)
    ingredients = meal.get('ingredients', '') or 'Not specified'
    prep_steps  = meal.get('preparation_steps', '') or meal.get('prep_steps', '') or 'Not specified'

    # Handle ingredients if it's a list
    if isinstance(ingredients, list):
        ingredients = ', '.join(ingredients)
    # Handle prep_steps if it's a list
    if isinstance(prep_steps, list):
        prep_steps = ' '.join(prep_steps)

    return (
        f"Meal: {name}. "
        f"Tags: {tags}. "
        f"Allergens: {allergens}. "
        f"Calories: {calories} kcal. "
        f"Protein: {protein}g, Carbs: {carbs}g, Fat: {fats}g. "
        f"Ingredients: {ingredients}. "
        f"Preparation: {prep_steps}."
    )


def synthesize_exercise_text(exercise: dict) -> str:
    """
    Build a dense text string from a workout_data row.

    Parameters:
        exercise (dict): A single row from workout_data with keys like
                         name, muscle_group, equipment, difficulty_level, etc.

    Returns:
        str: A natural-language summary suitable for embedding.

    Called by:
        ingest() — for each exercise in the catalogue.
    """
    name            = exercise.get('name', 'Unknown Exercise')
    muscle_group    = exercise.get('muscle_group', 'Unknown')
    specific_muscle = exercise.get('specific_muscle', '')
    equipment       = exercise.get('equipment', 'None')
    difficulty      = exercise.get('difficulty_level', 'Unknown')
    gym_required    = exercise.get('gym', False)

    return (
        f"Exercise: {name}. "
        f"Muscle group: {muscle_group}"
        f"{' — ' + specific_muscle if specific_muscle else ''}. "
        f"Equipment: {equipment}. "
        f"Difficulty: {difficulty}. "
        f"Requires gym: {'Yes' if gym_required else 'No'}."
    )


def embed_text(text: str) -> list:
    """
    Generate a 768-dim embedding using gemini-embedding-001.

    Parameters:
        text (str): The text to embed.

    Returns:
        list[float]: 768-dimensional embedding vector.

    Called by:
        ingest() — for each meal and exercise summary.
    """
    result = gemini.models.embed_content(
        model='gemini-embedding-001',
        contents=text,
    )
    return result.embeddings[0].values


def upsert_knowledge(source_title: str, content_summary: str,
                     source_url: str, embedding: list):
    """
    Delete any existing row with the same source_title, then insert.
    This makes the script idempotent — safe to re-run.

    Parameters:
        source_title    (str):  Unique identifier (e.g. "Meal: Caesar Salad").
        content_summary (str):  The dense text summary.
        source_url      (str):  Image or video URL for the item.
        embedding       (list): 768-dim vector from embed_text().

    Returns:
        None — row is inserted into chatbot_knowledge_base.

    Called by:
        ingest() — for each meal and exercise.
    """
    # Delete existing row (ignore if not found)
    supabase.table('chatbot_knowledge_base').delete().eq(
        'source_title', source_title
    ).execute()

    # Insert new row
    supabase.table('chatbot_knowledge_base').insert({
        'content_summary':    content_summary,
        'source_title':       source_title,
        'source_url':         source_url or '',
        'embedding_vector':   embedding,
        'last_verified_date': TODAY,
    }).execute()


# ===================== MAIN INGESTION ========================
# The ingest() function orchestrates the full pipeline:
#   1. Fetch all meals from nutrition_data
#   2. Fetch all exercises from workout_data
#   3. Synthesize text, embed, and upsert each meal
#   4. Synthesize text, embed, and upsert each exercise
# =============================================================

def ingest():
    """
    Run the full knowledge base ingestion pipeline.

    Parameters:
        None — all configuration comes from module-level constants.

    Returns:
        None — progress and summary are printed to stdout.

    When / why it is called:
        Run manually after new meals or exercises are added to the
        database, so the chatbot can answer questions about them.
    """
    print("")
    print("=" * 60)
    print("  MUTAAFI Knowledge Base Ingestion")
    print("  Meals + Exercises → chatbot_knowledge_base")
    print("=" * 60)
    print("")

    # ── Step 1: Fetch all meals ──
    print("[1/4] Fetching meals from nutrition_data...")
    meals_res = supabase.table('nutrition_data').select('*').execute()
    meals = meals_res.data or []
    print(f"       Found {len(meals)} meals.")
    print("")

    # ── Step 2: Fetch all exercises ──
    print("[2/4] Fetching exercises from workout_data...")
    exercises_res = supabase.table('workout_data').select('*').execute()
    exercises = exercises_res.data or []
    print(f"       Found {len(exercises)} exercises.")
    print("")

    total = len(meals) + len(exercises)
    count = 0
    errors = 0

    # ── Step 3: Ingest meals ──
    print(f"[3/4] Ingesting {len(meals)} meals...")
    for meal in meals:
        count += 1
        name = meal.get('meal_name', 'Unknown')
        source_title = f"Meal: {name}"
        content = synthesize_meal_text(meal)
        source_url = meal.get('image_url', '')

        try:
            print(f"  [{count}/{total}] {source_title}")
            embedding = embed_text(content)
            upsert_knowledge(source_title, content, source_url, embedding)
            print(f"           ✓ OK (vector: {len(embedding)} dims)")
        except Exception as e:
            errors += 1
            print(f"           ✗ ERROR: {e}")

        # Rate limit guard: 1 second between API calls
        time.sleep(1)

    # ── Step 4: Ingest exercises ──
    print("")
    print(f"[4/4] Ingesting {len(exercises)} exercises...")
    for exercise in exercises:
        count += 1
        name = exercise.get('name', 'Unknown')
        source_title = f"Exercise: {name}"
        content = synthesize_exercise_text(exercise)
        source_url = exercise.get('video_url', '')

        try:
            print(f"  [{count}/{total}] {source_title}")
            embedding = embed_text(content)
            upsert_knowledge(source_title, content, source_url, embedding)
            print(f"           ✓ OK (vector: {len(embedding)} dims)")
        except Exception as e:
            errors += 1
            print(f"           ✗ ERROR: {e}")

        # Rate limit guard: 1 second between API calls
        time.sleep(1)

    # ── Summary ──
    print("")
    print("=" * 60)
    print("  INGESTION COMPLETE")
    print("=" * 60)
    print(f"  Meals ingested    : {len(meals)}")
    print(f"  Exercises ingested: {len(exercises)}")
    print(f"  Total rows        : {total}")
    print(f"  Errors            : {errors}")
    print(f"  Date              : {TODAY}")
    print("=" * 60)
    print("")

    if errors == 0:
        print("  ✅ All rows successfully ingested into chatbot_knowledge_base.")
    else:
        print(f"  ⚠️  {errors} rows failed. Check errors above and re-run.")
        print("     Re-running is safe (idempotent — no duplicates).")
    print("")


# ======================== ENTRY POINT ========================
if __name__ == '__main__':
    ingest()
