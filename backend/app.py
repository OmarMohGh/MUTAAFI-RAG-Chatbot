#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — MUTAAFI Flask API Server
===================================
FILE:    app.py
PROJECT: MUTAAFI — AI-Powered Fitness & Nutrition Platform 

WHAT THIS FILE DOES:
    Central Flask application that exposes ALL REST API endpoints for
    the MUTAAFI React frontend.  Major endpoint groups include:
      • Dashboard       — aggregated user stats + activity heatmap
      • Gallery         — browsable workout and meal catalogues
      • User Profile    — registration, login, profile updates
      • Meal Planning   — daily plan generation, swap, interact
      • Workout Planning— weekly plan generation, swap, accept
      • RAG Chatbot     — retrieval-augmented AI coach
      • Feedback/Contact— user submissions

HOW IT FITS IN THE PROJECT:
    This is the ENTRY POINT for the entire backend.  The React frontend
    calls these endpoints via Axios.  Business logic for meal and
    workout planning is delegated to meal_planner.py and
    workout_planner.py respectively.

ENVIRONMENT VARIABLES (loaded from backend/.env):
    VITE_SUPABASE_URL         — Supabase project URL
    VITE_SUPABASE_ANON_KEY    — Supabase anon/public key
    SUPABASE_SERVICE_ROLE_KEY — Supabase service role key (bypasses RLS)
    GOOGLE_API_KEY            — Google Gemini API key

HOW TO RUN:
    1. cd backend
    2. pip install -r requirements.txt
    3. python app.py
    Server starts at http://localhost:5000
"""


# ========================= IMPORTS ==========================
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
from google.genai import types


# ===================== CONSTANTS & CONFIG =====================
# Load environment variables from .env and initialise API clients.
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Allow frontend cross-origin requests

# Supabase client (anon key — subject to Row Level Security)
url: str = os.getenv("VITE_SUPABASE_URL", "")
key: str = os.getenv("VITE_SUPABASE_ANON_KEY", "")
supabase: Client = create_client(url, key)

# Google Gemini client for embeddings and generation
gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY", ""))


# ====================== ROUTES / ENDPOINTS ======================
# Organised by feature group: Health → Dashboard → Gallery →
# Feedback/Contact → User Profile → Meal Planning → RAG Chatbot →
# Workout Planning → Entry Point.
# =================================================================


# ─────────────────────────────────────────────────────────────
#  HEALTH CHECK
# ─────────────────────────────────────────────────────────────

@app.route('/api/health', methods=['GET'])
def health_check():
    """Return a simple JSON heartbeat so the frontend can verify connectivity."""
    return jsonify({"status": "healthy", "message": "Mutaafi backend is running"}), 200


# ─────────────────────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────────────────────
@app.route('/api/dashboard/<user_id>', methods=['GET'])
def get_dashboard(user_id):
    """
    Aggregate and return all dashboard stats for a user.

    Parameters:
        user_id (str): UUID of the authenticated user (from URL).

    Returns:
        JSON: workouts, meals, targets, BMI, weekly_active,
              and a 35-day activity_history heatmap.
    """
    try:
        auth_header = request.headers.get('Authorization')
        user_client = supabase
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            from supabase import create_client, ClientOptions
            user_client = create_client(url, key, options=ClientOptions(headers={'Authorization': f'Bearer {token}'}))

        # Fetch User Data
        user_res = user_client.table('user_data').select('*').eq('user_id', user_id).execute()
        user_data = user_res.data[0] if user_res.data else {}
        
        # Calculate BMI
        bmi = None
        if user_data.get('weight') and user_data.get('height'):
            height_m = user_data['height'] / 100
            bmi = round(user_data['weight'] / (height_m ** 2), 1)

        # Get today's workouts
        from datetime import date, timedelta
        today_str = str(date.today())
        workout_res = user_client.table('user_workout_schedule').select('*').eq('user_id', user_id).eq('plan_date', today_str).execute()
        workouts_total = len(workout_res.data)
        workouts_completed = len([w for w in workout_res.data if w.get('is_completed')])

        # Get today's meals
        meal_res = user_client.table('user_meal_plan').select('*, nutrition_data(*)').eq('user_id', user_id).eq('plan_date', today_str).execute()
        meals_total = len(meal_res.data)
        
        calories_eaten = 0
        protein_eaten = 0
        for mp in meal_res.data:
            if mp.get('is_completed') and mp.get('nutrition_data'):
                nut_data = mp['nutrition_data']
                if isinstance(nut_data, dict):
                    calories_eaten += nut_data.get('calories', 0)
                    protein_eaten += nut_data.get('protein', 0)

        # Calculate weekly_active (distinct completed workout dates this week)
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        active_res = user_client.table('user_workout_schedule').select(
            'plan_date'
        ).eq('user_id', user_id).eq('is_completed', True).gte(
            'plan_date', str(week_start)
        ).lte('plan_date', str(week_end)).execute()
        active_dates = set(r['plan_date'] for r in (active_res.data or []))
        weekly_active = len(active_dates)

        # Get activity history for heatmap (last 35 days)
        start_date = today - timedelta(days=35)
        
        activity_history = {}
        
        # Workouts history
        workout_hist_res = user_client.table('user_workout_schedule').select('plan_date, is_completed').eq('user_id', user_id).gte('plan_date', str(start_date)).execute()
        for w in (workout_hist_res.data or []):
            date_str = w.get('plan_date')
            if date_str:
                if date_str not in activity_history:
                    activity_history[date_str] = {'workouts_completed': 0, 'workouts_total': 0, 'meals_completed': 0, 'meals_total': 0}
                activity_history[date_str]['workouts_total'] += 1
                if w.get('is_completed'):
                    activity_history[date_str]['workouts_completed'] += 1

        # Meals history
        meal_hist_res = user_client.table('user_meal_plan').select('plan_date, is_completed').eq('user_id', user_id).gte('plan_date', str(start_date)).execute()
        for m in (meal_hist_res.data or []):
            date_str = m.get('plan_date')
            if date_str:
                if date_str not in activity_history:
                    activity_history[date_str] = {'workouts_completed': 0, 'workouts_total': 0, 'meals_completed': 0, 'meals_total': 0}
                activity_history[date_str]['meals_total'] += 1
                if m.get('is_completed'):
                    activity_history[date_str]['meals_completed'] += 1

        # Compile Data
        dashboard_data = {
            "workouts": {
                "total": workouts_total,
                "completed": workouts_completed
            },
            "meals": {
                "total": meals_total,
                "calories_eaten": calories_eaten,
                "protein_eaten": protein_eaten
            },
            "targets": {
                "calories": user_data.get('target_calories', 0),
                "protein": user_data.get('target_protein', 0)
            },
            "streak": 1,
            "bmi": bmi,
            "goal_type": user_data.get('goal_type', 'Maintenance'),
            "weekly_active": weekly_active,
            "activity_history": activity_history
        }

        return jsonify(dashboard_data), 200
    except Exception as e:
        print("Dashboard Fetch Error:", e)
        return jsonify({"error": str(e)}), 400

# ─────────────────────────────────────────────────────────────
#  GALLERY — Workout & Meal Catalogues
# ─────────────────────────────────────────────────────────────

@app.route('/api/gallery/workouts', methods=['GET'])
def get_workouts_gallery():
    """Return all exercises from workout_data for the Gallery page."""
    try:
        # Fetch all exercises from workout_data
        res = supabase.table('workout_data').select('*').execute()
        return jsonify(res.data), 200
    except Exception as e:
        print("Workout Gallery Fetch Error:", e)
        return jsonify({"error": str(e)}), 400

@app.route('/api/gallery/meals', methods=['GET'])
def get_meals_gallery():
    """Return all meals from nutrition_data for the Gallery page."""
    try:
        # Fetch all meals from nutrition_data
        res = supabase.table('nutrition_data').select('*').execute()
        return jsonify(res.data), 200
    except Exception as e:
        print("Meal Gallery Fetch Error:", e)
        return jsonify({"error": str(e)}), 400

# ─────────────────────────────────────────────────────────────
#  FEEDBACK & CONTACT
# ─────────────────────────────────────────────────────────────

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Accept a user feedback submission (rating + message) and store it."""
    try:
        data = request.json
        user_id = data.get('user_id')  # Optional — anonymous submissions allowed
        feedback_type = data.get('feedback_type')
        rating = data.get('rating')
        message = data.get('message')

        if not all([feedback_type, rating, message]):
            return jsonify({"error": "Missing required fields"}), 400

        # Use service role key to bypass RLS
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        service_client.table('feedback').insert({
            'user_id': user_id,
            'feedback_type': feedback_type,
            'rating': int(rating),
            'message': message
        }).execute()

        return jsonify({"status": "success", "message": "Feedback submitted"}), 201
    except Exception as e:
        print("Feedback Submission Error:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/api/contact', methods=['POST'])
def submit_contact():
    """Accept a contact form submission and store it."""
    try:
        data = request.json
        user_id = data.get('user_id')  # Can be None/null if not logged in
        name = data.get('name')
        email = data.get('email')
        subject = data.get('subject')
        message = data.get('message')

        if not all([name, email, subject, message]):
            return jsonify({"error": "Missing required fields"}), 400

        # Use service role key to bypass RLS
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        service_client.table('contact_messages').insert({
            'user_id': user_id,
            'name': name,
            'email': email,
            'subject': subject,
            'message': message
        }).execute()

        # [PLACEHOLDER] - Initialize Email Service here to send 'message' to support@mutaafi.com

        return jsonify({"status": "success", "message": "Message sent successfully"}), 201
    except Exception as e:
        print("Contact Submission Error:", e)
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────────────────────
#  AI CHATBOT COACH  RAG 
#  Using Google Gemini  for embeddings + generation
# ─────────────────────────────────────────────────────────────
# 
#
#   -- Step 1: Change embedding column from 1536 to 768 dimensions
#   ALTER TABLE chatbot_knowledge_base
#     ALTER COLUMN embedding_vector TYPE vector(768);
#
#   -- Step 2: Drop old function and recreate for 768-dim vectors
#   DROP FUNCTION IF EXISTS match_knowledge_docs;
#
#   CREATE OR REPLACE FUNCTION match_knowledge_docs(
#     query_embedding vector(768),
#     match_count int DEFAULT 3
#   )
#   RETURNS TABLE (
#     doc_id bigint,
#     content_summary text,
#     source_title text,
#     source_url text,
#     similarity float
#   )
#   LANGUAGE plpgsql
#   AS $$
#   BEGIN
#     RETURN QUERY
#     SELECT
#       kb.doc_id,
#       kb.content_summary,
#       kb.source_title,
#       kb.source_url,
#       1 - (kb.embedding_vector <=> query_embedding) AS similarity
#     FROM chatbot_knowledge_base kb
#     ORDER BY kb.embedding_vector <=> query_embedding
#     LIMIT match_count;
#   END;
#   $$;
# ─────────────────────────────────────────────────────────────

@app.route('/api/chat', methods=['POST'])
def chat_rag():
    """
    RAG chatbot endpoint.  Embeds the user query, retrieves relevant
    knowledge via pgvector, filters for allergy safety, injects user
    profile context, and generates a response via Gemini 2.5 Flash.

    Parameters (JSON body):
        message (str): The user's question.

    Returns:
        JSON: {reply, sources} on success.
    """
    try:
        data = request.json
        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({"error": "Message cannot be empty"}), 400

        # ── STEP A: Authenticate user  ──
        user_profile = None
        user_allergies = []

        auth_header = request.headers.get('Authorization')
        # DEBUG 1: Log whether Authorization header was received
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            print(f"[CHAT DEBUG 1] Authorization header RECEIVED. Token prefix: {token[:20]}...")
            try:
                user_response = supabase.auth.get_user(token)
                if user_response and user_response.user:
                    user_id = user_response.user.id
                    # DEBUG 2: Log decoded user ID
                    print(f"[CHAT DEBUG 2] JWT decoded OK. user_id = {user_id}")

                    # Fetch fresh profile from user_data (no caching)
                    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
                    service_client = create_client(url, service_key)

                    profile_res = service_client.table('user_data').select(
                        'name, age, weight, height, goal_type, activity_level, '
                        'allergies, target_calories, target_protein, gender'
                    ).eq('user_id', user_id).execute()

                    # DEBUG 3: Log profile fetch result
                    if profile_res.data:
                        user_profile = profile_res.data[0]
                        print(f"[CHAT DEBUG 3] Profile FOUND: {user_profile}")
                        user_allergies = user_profile.get('allergies') or []
                        # Handle if allergies is a string (comma-separated)
                        if isinstance(user_allergies, str):
                            user_allergies = [a.strip() for a in user_allergies.split(',') if a.strip()]
                        print(f"[CHAT DEBUG 3b] Allergies parsed: {user_allergies}")
                    else:
                        print(f"[CHAT DEBUG 3] Profile NOT FOUND for user_id={user_id}. Query returned: {profile_res.data}")
                else:
                    print(f"[CHAT DEBUG 2] JWT decode returned no user. Response: {user_response}")
            except Exception as auth_err:
                # Auth failed — continue as anonymous user
                print(f"[CHAT DEBUG 2] JWT decode FAILED with error: {auth_err}")
        else:
            print(f"[CHAT DEBUG 1] Authorization header MISSING. Raw header value: {auth_header}")

        # ── STEP B: Generate embedding using Gemini gemini-embedding-001 ──
        embedding_result = gemini_client.models.embed_content(
            model='gemini-embedding-001',
            contents=user_message,
        )
        query_embedding = embedding_result.embeddings[0].values

        # ── STEP C: Retrieve relevant docs via pgvector cosine similarity ──
        # Fetch extra candidates (10) to allow allergen post-filtering
        fetch_count = 10 if user_allergies else 3

        rpc_result = supabase.rpc('match_knowledge_docs', {
            'query_embedding': query_embedding,
            'match_count': fetch_count
        }).execute()

        retrieved_docs = rpc_result.data if rpc_result.data else []

        # ── STEP C.1: Allergy safety filter (post-retrieval) ──
        if user_allergies and retrieved_docs:
            safe_docs = []
            for doc in retrieved_docs:
                summary_lower = (doc.get('content_summary') or '').lower()
                has_allergen = any(
                    allergen.lower() in summary_lower
                    for allergen in user_allergies
                )
                if not has_allergen:
                    safe_docs.append(doc)
            retrieved_docs = safe_docs[:3]
        else:
            retrieved_docs = retrieved_docs[:3]

        # Build context from retrieved knowledge (include source_url for media sharing)
        context_parts = []
        sources = []
        for doc in retrieved_docs:
            title = doc.get('source_title', 'Unknown Source')
            content = doc.get('content_summary', '')
            link = doc.get('source_url', '')
            fact_block = f"Title: {title}\nContent: {content}"
            if link:
                fact_block += f"\nLink: {link}"
            context_parts.append(fact_block)
            sources.append(title)

        context_text = "\n\n".join(context_parts) if context_parts else "No relevant information found in the knowledge base."

        # ── STEP D: Construct the augmented prompt ──
        # Priority order: [1] Medical safety → [2] User profile → [3] Facts → [4] Question

        # [1] Medical condition safety redirect 
        medical_safety_rule = (
            "RULE — MEDICAL CONDITIONS (HIGHEST PRIORITY):\n"
            "If the user's question is about a specific medical condition, illness, "
            "injury, pregnancy, eating disorder, or any health situation that requires "
            "professional diagnosis or treatment, do NOT provide medical advice. "
            "Instead, respond warmly and recommend they consult a qualified healthcare "
            "professional (doctor, registered dietitian, or physical therapist depending "
            "on the context). You may still share general, non-prescriptive information "
            "from the verified facts if relevant, but always end with a clear "
            "recommendation to seek professional guidance. Never diagnose, never "
            "prescribe, and never suggest specific treatments or supplements for "
            "medical conditions.\n\n"
            "Examples:\n"
            "- User: \"I have diabetes, what should I eat?\"\n"
            "  → Acknowledge warmly, recommend a registered dietitian, mention that "
            "balanced meals with controlled carbohydrates are generally recommended "
            "but specifics should come from a healthcare professional.\n"
            "- User: \"I hurt my lower back, what exercises should I do?\"\n"
            "  → Express care, recommend a physiotherapist or doctor before starting "
            "exercises, offer to help suggest safe exercises once cleared by a professional.\n"
        )

        # [2] User profile injection 
        profile_block = ""
        if user_profile:
            name     = user_profile.get('name') or 'User'
            age      = user_profile.get('age') or 'unknown'
            weight   = user_profile.get('weight') or 'unknown'
            height   = user_profile.get('height') or 'unknown'
            goal     = user_profile.get('goal_type') or 'not set'
            activity = user_profile.get('activity_level') or 'not set'
            allergies_str = ', '.join(user_allergies) if user_allergies else 'None'
            target_cal  = user_profile.get('target_calories') or 'not calculated'
            target_prot = user_profile.get('target_protein') or 'not calculated'

            profile_block = (
                f"\nUSER PROFILE (personalize your answer using this data):\n"
                f"The user is {name}, {age} years old, {weight}kg, {height}cm.\n"
                f"Goal: {goal}. Activity level: {activity}.\n"
                f"Allergic to: {allergies_str}.\n"
                f"Daily targets (pre-calculated — do NOT recalculate these): "
                f"{target_cal} kcal, {target_prot}g protein.\n"
                f"Use this profile to personalize your answer. "
                f"Do not recalculate the targets — explain and contextualize them.\n"
            )

        # DEBUG 4: Log whether profile block was generated
        print(f"[CHAT DEBUG 4] user_profile is None: {user_profile is None}")
        print(f"[CHAT DEBUG 4] profile_block length: {len(profile_block)}")
        if profile_block:
            print(f"[CHAT DEBUG 4] profile_block content:\n{profile_block}")
        else:
            print(f"[CHAT DEBUG 4] profile_block is EMPTY — no personalization will be injected")

        system_instruction = (
            "You are Mutaafi Coach, an expert fitness and nutrition AI assistant. "
            "Answer the user's question using the verified facts provided below. "
            "Be concise, helpful, and encouraging. "
            "If the user requests a video, image, recipe link, or any media related to "
            "an exercise or meal, share the Link from the verified fact directly in your "
            "response. Format links as clickable markdown links. "
            "If the answer is not in the provided facts, politely say you don't have "
            "enough information on that topic yet.\n\n"
            f"{medical_safety_rule}"
            f"{profile_block}"
        )

        augmented_prompt = (
            f"{system_instruction}\n"
            f"--- VERIFIED FACTS ---\n{context_text}\n--- END OF FACTS ---\n\n"
            f"User Question: {user_message}"
        )

        # DEBUG 5: Log the full prompt sent to Gemini
        print(f"[CHAT DEBUG 5] === FULL AUGMENTED PROMPT ===")
        print(augmented_prompt)
        print(f"[CHAT DEBUG 5] === END PROMPT ===")

        # ── STEP E: Generate response using Gemini 2.5 Flash ──
        chat_response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=augmented_prompt
        )
        ai_reply = chat_response.text

        # DEBUG 6: Log Gemini's response
        print(f"[CHAT DEBUG 6] Gemini reply: {ai_reply[:300]}...")

        # Format source attribution
        source_label = ", ".join(set(sources)) if sources else ""

        return jsonify({
            "reply": ai_reply,
            "sources": source_label
        }), 200

    except Exception as e:
        print("Chat RAG Error:", e)
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"AI Coach error: {str(e)}"}), 500

@app.route('/api/admin/knowledge', methods=['POST'])
def add_knowledge():
    """Admin-only: add a new knowledge base entry with auto-embedding."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Unauthorized"}), 401

        token = auth_header.split(' ')[1]
        
        # Verify the user is the admin using the global supabase client
        try:
            user_response = supabase.auth.get_user(token)
        except Exception as e:
            return jsonify({"error": f"Auth validation failed: {str(e)}"}), 401

        if not user_response or not user_response.user:
            return jsonify({"error": "Unauthorized: Invalid user session"}), 401
            
        user_email = user_response.user.email
        if not user_email or user_email.lower() != 'admin@mutaafi.com':
            return jsonify({"error": f"Forbidden: Admin access required (Email: {user_email})"}), 403

        data = request.json
        content_summary = data.get('content_summary')
        source_title = data.get('source_title', 'Admin Entry')
        source_url = data.get('source_url', '')

        if not content_summary:
            return jsonify({"error": "content_summary is required"}), 400

        # Generate embedding
        embedding_result = gemini_client.models.embed_content(
            model='gemini-embedding-001',
            contents=content_summary,
        )
        embedding = embedding_result.embeddings[0].values
        
        from datetime import date
        today_str = str(date.today())

        # Insert into Supabase
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)
        
        service_client.table('chatbot_knowledge_base').insert({
            'content_summary': content_summary,
            'source_title': source_title,
            'source_url': source_url,
            'embedding_vector': embedding,
            'last_verified_date': today_str
        }).execute()

        return jsonify({"status": "success", "message": "Knowledge entry added"}), 201

    except Exception as e:
        print("Add Knowledge Error:", e)
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────────────────────
#  MEAL PLANNER — AI-Powered Daily Plan Generation
# ─────────────────────────────────────────────────────────────
from meal_planner import generate_daily_plan, swap_single_meal, log_interaction

@app.route('/api/meal-plan/generate', methods=['POST'])
def generate_meal_plan():
    """Generate a full daily meal plan for the authenticated user."""
    try:
        data = request.json
        user_id = data.get('user_id')
        excluded_ids = data.get('excluded_ids', [])

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        # Use service role key for server-side operations
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        plan = generate_daily_plan(user_id, service_client, excluded_ids)
        return jsonify(plan), 200

    except ValueError as e:
        print("Meal Plan Generation Error:", e)
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        print("Meal Plan Generation Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/meal-plan/swap', methods=['POST'])
def swap_meal():
    """Swap a single meal in the plan for the given slot."""
    try:
        data = request.json
        user_id = data.get('user_id')
        slot_name = data.get('slot_name')
        excluded_meal_ids = data.get('excluded_meal_ids', [])

        if not user_id or not slot_name:
            return jsonify({"error": "user_id and slot_name are required"}), 400

        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        new_meal = swap_single_meal(user_id, slot_name, excluded_meal_ids, service_client)

        if new_meal:
            return jsonify({"new_meal": new_meal}), 200
        else:
            return jsonify({"error": "No alternative meals available for this slot"}), 404

    except Exception as e:
        print("Meal Swap Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/meal-plan/interact', methods=['POST'])
def log_meal_interaction():
    """Log a user interaction with a meal (eaten, swapped, saved, rejected, viewed)."""
    try:
        data = request.json
        user_id = data.get('user_id')
        meal_id = data.get('meal_id')
        action_type = data.get('action_type')
        explicit_rating = data.get('explicit_rating')

        if not all([user_id, meal_id, action_type]):
            return jsonify({"error": "user_id, meal_id, and action_type are required"}), 400

        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        if action_type == 'unsaved':
            service_client.table('user_meal_interactions').delete().eq('user_id', user_id).eq('meal_id', meal_id).eq('action_type', 'saved').execute()
            return jsonify({"status": "success", "message": "Interaction 'saved' removed"}), 200

        log_interaction(
            user_id=user_id,
            meal_id=meal_id,
            action_type=action_type,
            client=service_client,
            explicit_rating=explicit_rating,
        )

        return jsonify({"status": "success", "message": f"Interaction '{action_type}' logged"}), 201

    except Exception as e:
        print("Interaction Logging Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/meal-plan/interactions/<user_id>', methods=['GET'])
def get_user_interactions(user_id):
    """Fetch all (or filtered) meal interactions for a given user."""
    try:
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)
        
        action_type = request.args.get('action_type')
        query = service_client.table('user_meal_interactions').select('*').eq('user_id', user_id)
        if action_type:
            query = query.eq('action_type', action_type)
            
        res = query.execute()
        return jsonify(res.data), 200
    except Exception as e:
        print("Get Interactions Error:", e)
        return jsonify({"error": str(e)}), 400


@app.route('/api/meal-plan/accept', methods=['POST'])
def accept_meal_plan():
    """Save the accepted daily meal plan into user_meal_plan."""
    try:
        data = request.json
        user_id = data.get('user_id')
        plan_date = data.get('plan_date')
        slots = data.get('slots')

        if not user_id or not plan_date or not slots:
            return jsonify({"error": "Missing user_id, plan_date, or slots"}), 400

        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        # Delete any existing plan for this user on this date
        service_client.table('user_meal_plan').delete().eq('user_id', user_id).eq('plan_date', plan_date).execute()

        inserts = []
        for slot in slots:
            if slot.get('meal') and slot['meal'].get('meal_id'):
                inserts.append({
                    'user_id': user_id,
                    'plan_date': plan_date,
                    'slot_name': slot['slot_name'],
                    'meal_id': slot['meal']['meal_id'],
                    'is_completed': False
                })

        if inserts:
            res = service_client.table('user_meal_plan').insert(inserts).execute()
        return jsonify({"message": "Plan accepted successfully"}), 200
    except Exception as e:
        print("Accept Plan Error:", e)
        return jsonify({"error": str(e)}), 400

@app.route('/api/meal-plan/active/<user_id>', methods=['GET'])
def get_active_plan(user_id):
    """Fetch today's accepted meal plan with nutrition data joined."""
    try:
        plan_date = request.args.get('date')
        if not plan_date:
            return jsonify({"error": "Missing date parameter"}), 400
            
        auth_header = request.headers.get('Authorization')
        user_client = supabase
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            from supabase import create_client, ClientOptions
            user_client = create_client(url, key, options=ClientOptions(headers={'Authorization': f'Bearer {token}'}))
            
        res = user_client.table('user_meal_plan').select('*, nutrition_data(*)').eq('user_id', user_id).eq('plan_date', plan_date).execute()
        return jsonify(res.data), 200
    except Exception as e:
        print("Get Active Plan Error:", e)
        return jsonify({"error": str(e)}), 400

# ─────────────────────────────────────────────────────────────
#  MEAL PLAN COMPLETION
# ─────────────────────────────────────────────────────────────

@app.route('/api/meal-plan/complete', methods=['POST'])
def complete_meal_plan():
    """Mark ALL meals for a given date as completed."""
    try:
        data = request.json
        user_id = data.get('user_id')
        plan_date = data.get('plan_date')
        
        if not user_id or not plan_date:
            return jsonify({"error": "Missing user_id or plan_date"}), 400
            
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)
        
        # Mark all meals for this date as completed
        res = service_client.table('user_meal_plan').update({'is_completed': True}).eq('user_id', user_id).eq('plan_date', plan_date).execute()
        return jsonify({"message": "Plan marked as completed", "data": res.data}), 200
    except Exception as e:
        print("Complete Plan Error:", e)
        return jsonify({"error": str(e)}), 400

@app.route('/api/meal-plan/complete-meal', methods=['POST'])
def complete_single_meal():
    """Toggle completion of a single meal in today's plan."""
    try:
        data = request.json
        user_id = data.get('user_id')
        plan_date = data.get('plan_date')
        slot_name = data.get('slot_name')
        is_completed = data.get('is_completed', True)

        if not user_id or not plan_date or not slot_name:
            return jsonify({"error": "Missing user_id, plan_date, or slot_name"}), 400

        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        res = service_client.table('user_meal_plan').update(
            {'is_completed': is_completed}
        ).eq('user_id', user_id).eq('plan_date', plan_date).eq('slot_name', slot_name).execute()

        return jsonify({"status": "success", "data": res.data}), 200
    except Exception as e:
        print("Complete Single Meal Error:", e)
        return jsonify({"error": str(e)}), 400

# ─────────────────────────────────────────────────────────────
#  USER PROFILE — Target Calculation & Profile Management
# ─────────────────────────────────────────────────────────────

@app.route('/api/calculate-targets', methods=['POST'])
def calculate_targets():
    """
    Calculate daily calorie and protein targets using
    the Mifflin-St Jeor equation + activity multiplier.

    Parameters (JSON body):
        age, height, weight, gender, activity_level, goal_type.

    Returns:
        JSON: {target_calories, target_protein}.
    """
    try:
        data = request.json

        # ── Input parsing ──
        try:
            age = int(data.get('age'))
            height_cm = float(data.get('height'))
            weight_kg = float(data.get('weight'))
        except (TypeError, ValueError):
            return jsonify({"error": "Age, height, and weight must be valid numbers."}), 400

        gender = data.get('gender')
        activity_level = data.get('activity_level', 'Sedentary')
        goal = data.get('goal_type', 'Maintenance')

        # ── Server-side range validation ──
        if weight_kg <= 0 or weight_kg < 20 or weight_kg > 300:
            return jsonify({"error": "Please enter a valid weight between 20 and 300 kg."}), 400

        if height_cm <= 0 or height_cm < 50 or height_cm > 250:
            return jsonify({"error": "Please enter a valid height between 50 and 250 cm."}), 400

        if age <= 0 or age < 10 or age > 80:
            return jsonify({"error": "Please enter a valid age between 10 and 80."}), 400

        # 1. BMR Calculation (Mifflin-St Jeor)
        if gender.lower() == 'male':
            bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
        else:
            bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

        # 2. Activity Multiplier
        activity_multipliers = {
            'Sedentary (Little to no exercise)': 1.2,
            'Lightly active (1-3 days/week)': 1.375,
            'Moderately active (3-5 days/week)': 1.55,
            'Very active (6-7 days/week)': 1.725,
            'Extra active (Physical job)': 1.9
        }
        
        # Fallback to lightly active if unknown string
        multiplier = activity_multipliers.get(activity_level, 1.375)
        tdee = bmr * multiplier

        # 3. Goal Adjustment & Protein
        target_calories = tdee
        
        if goal == 'Weight Loss' or 'Loss' in goal:
            target_calories -= 500  # 500 deficit
            target_protein = weight_kg * 2.2 # Higher protein to preserve muscle
        elif goal == 'Muscle Gain' or 'Gain' in goal:
            target_calories += 500  # 500 surplus
            target_protein = weight_kg * 2.0
        else:
            # Maintenance
            target_protein = weight_kg * 1.8
            
        return jsonify({
            "target_calories": int(target_calories),
            "target_protein": int(target_protein)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ─────────────────────────────────────────────────────────────
#  WORKOUT TRACKING — Today's Workout Page
# ─────────────────────────────────────────────────────────────

@app.route('/api/workout/today/<user_id>', methods=['GET'])
def get_todays_workout(user_id):
    """Fetch today's scheduled workout exercises with exercise details."""
    try:
        from datetime import date
        today_str = str(date.today())

        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        # Get today's schedule rows
        schedule_res = service_client.table('user_workout_schedule').select(
            '*, workout_data(name, image_url, muscle_group, equipment, specific_muscle, video_url, difficulty_level)'
        ).eq('user_id', user_id).eq('plan_date', today_str).execute()

        exercises = schedule_res.data or []

        # Get the active plan for metadata (schedule_type badge)
        plan_res = service_client.table('workout_plans').select(
            'schedule_type, days_available'
        ).eq('user_id', user_id).eq('is_active', True).order(
            'created_at', desc=True
        ).limit(1).execute()
        plan_data = plan_res.data[0] if plan_res.data else {}

        # Get the day label from split templates
        day_label = ''
        if plan_data.get('days_available'):
            # today's weekday in JS style: 0=Sunday
            import datetime
            js_weekday = (date.today().weekday() + 1) % 7  # Python Mon=0 -> JS Sun=0
            template_res = service_client.table('workout_split_templates').select(
                'day_label'
            ).eq('days_available', plan_data['days_available']).eq(
                'week_day', js_weekday
            ).limit(1).execute()
            if template_res.data:
                day_label = template_res.data[0].get('day_label', '')

        # Get most recent performance history for each exercise (weight, sets, reps)
        last_history = {}  # { exercise_id: { weight, sets, reps } }
        if exercises:
            exercise_ids = list(set(e['exercise_id'] for e in exercises))
            for eid in exercise_ids:
                hist_res = service_client.table('user_workout_schedule').select(
                    'weight_lifted, sets_performed, reps_performed'
                ).eq('user_id', user_id).eq('exercise_id', eid).eq(
                    'is_completed', True
                ).order(
                    'plan_date', desc=True
                ).limit(1).execute()
                if hist_res.data:
                    row = hist_res.data[0]
                    last_history[eid] = {
                        'weight': row.get('weight_lifted'),
                        'sets':   row.get('sets_performed'),
                        'reps':   row.get('reps_performed'),
                    }

        # Build the response
        result_exercises = []
        for ex in exercises:
            wd = ex.get('workout_data') or {}
            hist = last_history.get(ex['exercise_id'], {})
            result_exercises.append({
                'schedule_id':     ex['schedule_id'],
                'exercise_id':     ex['exercise_id'],
                'sets':            ex.get('sets'),
                'reps':            ex.get('reps'),
                'is_completed':    ex.get('is_completed', False),
                'weight_lifted':   ex.get('weight_lifted'),
                'sets_performed':  ex.get('sets_performed'),
                'reps_performed':  ex.get('reps_performed'),
                'cardio_minutes':  ex.get('cardio_minutes'),
                'is_cardio':       ex.get('cardio_minutes') is not None,
                'last_weight':     hist.get('weight'),
                'last_sets':       hist.get('sets'),
                'last_reps':       hist.get('reps'),
                'name':            wd.get('name', ''),
                'image_url':       wd.get('image_url', ''),
                'muscle_group':    wd.get('muscle_group', ''),
                'equipment':       wd.get('equipment', ''),
                'specific_muscle': wd.get('specific_muscle', ''),
                'video_url':       wd.get('video_url', ''),
            })

        return jsonify({
            'exercises': result_exercises,
            'schedule_type': plan_data.get('schedule_type', ''),
            'day_label': day_label,
            'date': today_str,
        }), 200

    except Exception as e:
        print("Today's Workout Fetch Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/workout/finish', methods=['POST'])
def finish_workout():
    """Mark all of today's exercises as complete and save weight values."""
    try:
        data = request.json
        user_id = data.get('user_id')
        exercises = data.get('exercises', [])  # [{schedule_id, weight_lifted}, ...]

        if not user_id or not exercises:
            return jsonify({"error": "user_id and exercises are required"}), 400

        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        # Update each exercise row
        for ex in exercises:
            update_data = {'is_completed': True}
            if ex.get('weight_lifted') is not None:
                update_data['weight_lifted'] = ex['weight_lifted']
            if ex.get('sets_performed') is not None:
                update_data['sets_performed'] = ex['sets_performed']
            if ex.get('reps_performed') is not None:
                update_data['reps_performed'] = ex['reps_performed']
            service_client.table('user_workout_schedule').update(
                update_data
            ).eq('schedule_id', ex['schedule_id']).execute()

        # Calculate weekly_active for this user (distinct completed plan_dates this week)
        from datetime import date, timedelta
        today = date.today()
        # Get start of week (Monday)
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        active_res = service_client.table('user_workout_schedule').select(
            'plan_date'
        ).eq('user_id', user_id).eq('is_completed', True).gte(
            'plan_date', str(week_start)
        ).lte('plan_date', str(week_end)).execute()

        # Count distinct dates
        active_dates = set(r['plan_date'] for r in (active_res.data or []))
        weekly_active = len(active_dates)

        return jsonify({
            "message": "Workout completed!",
            "weekly_active": weekly_active,
        }), 200

    except Exception as e:
        print("Finish Workout Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/workout/complete-exercise', methods=['POST'])
def complete_single_exercise():
    """Mark a single exercise as complete and save its weight."""
    try:
        data = request.json
        schedule_id = data.get('schedule_id')
        weight_lifted = data.get('weight_lifted')
        sets_performed = data.get('sets_performed')
        reps_performed = data.get('reps_performed')
        is_completed = data.get('is_completed', True)

        if not schedule_id:
            return jsonify({"error": "schedule_id is required"}), 400

        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        update_data = {'is_completed': is_completed}
        if weight_lifted is not None:
            update_data['weight_lifted'] = weight_lifted
        if sets_performed is not None:
            update_data['sets_performed'] = sets_performed
        if reps_performed is not None:
            update_data['reps_performed'] = reps_performed

        service_client.table('user_workout_schedule').update(
            update_data
        ).eq('schedule_id', schedule_id).execute()

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print("Complete Exercise Error:", e)
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  WORKOUT PDF EXPORT — Full 7-Day Plan
# ─────────────────────────────────────────────────────────────

@app.route('/api/workout/full-plan/<user_id>', methods=['GET'])
def get_full_workout_plan(user_id):
    """Fetch the full 7-day workout plan for PDF export."""
    try:
        from datetime import date, timedelta

        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        # 1. Get active plan metadata
        plan_res = service_client.table('workout_plans').select(
            'plan_id, schedule_type, days_available, plan_mode'
        ).eq('user_id', user_id).eq('is_active', True).order(
            'created_at', desc=True
        ).limit(1).execute()

        if not plan_res.data:
            return jsonify({"error": "No active workout plan found"}), 404

        plan_data = plan_res.data[0]
        active_plan_id = plan_data.get('plan_id')
        days_available = plan_data.get('days_available')

        # 2. Get split templates for day labels (week_day: 0=Sun … 6=Sat)
        template_res = service_client.table('workout_split_templates').select(
            'week_day, day_label'
        ).eq('days_available', days_available).order('week_day').execute()

        day_labels = {}
        for t in (template_res.data or []):
            day_labels[t['week_day']] = t['day_label']

        # 3. Compute current week range (Sunday → Saturday)
        today = date.today()
        js_weekday = (today.weekday() + 1) % 7  # 0=Sun
        week_start = today - timedelta(days=js_weekday)

        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday',
                     'Thursday', 'Friday', 'Saturday']

        # 4. Fetch exercises for the active plan only
        week_end = week_start + timedelta(days=6)
        schedule_res = service_client.table('user_workout_schedule').select(
            '*, workout_data(name, image_url, muscle_group, equipment, specific_muscle)'
        ).eq('user_id', user_id).eq(
            'plan_id', active_plan_id
        ).gte(
            'plan_date', str(week_start)
        ).lte('plan_date', str(week_end)).order('plan_date').execute()

        # Group exercises by date
        exercises_by_date = {}
        for ex in (schedule_res.data or []):
            d = ex.get('plan_date')
            if d not in exercises_by_date:
                exercises_by_date[d] = []
            exercises_by_date[d].append(ex)

        # 5. Build the weekly plan structure
        weekly_plan = []
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            day_str = str(day_date)
            label = day_labels.get(i, 'Rest')

            day_exercises = []
            for ex in exercises_by_date.get(day_str, []):
                wd = ex.get('workout_data') or {}
                day_exercises.append({
                    'name':            wd.get('name', ''),
                    'muscle_group':    wd.get('muscle_group', ''),
                    'specific_muscle': wd.get('specific_muscle', ''),
                    'equipment':       wd.get('equipment', ''),
                    'sets':            ex.get('sets'),
                    'reps':            ex.get('reps'),
                    'is_completed':    ex.get('is_completed', False),
                    'weight_lifted':   ex.get('weight_lifted'),
                    'cardio_minutes':  ex.get('cardio_minutes'),
                    'is_cardio':       ex.get('cardio_minutes') is not None,
                })

            weekly_plan.append({
                'day_name':  day_names[i],
                'day_label': label,
                'date':      day_str,
                'is_rest':   label == 'Rest' and len(day_exercises) == 0,
                'exercises': day_exercises,
            })

        # 6. User name is provided by the frontend from auth metadata
        #    (user_data table does not store the user's name)

        return jsonify({
            'schedule_type': plan_data.get('schedule_type', ''),
            'plan_mode':     plan_data.get('plan_mode', 'ai'),
            'weekly_plan':   weekly_plan,
        }), 200

    except Exception as e:
        print("Full Workout Plan Fetch Error:", e)
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  WORKOUT PLANNER — AI-Powered Weekly Plan Generation
# ─────────────────────────────────────────────────────────────
from workout_planner import generate_workout_plan, swap_exercise, accept_plan

@app.route('/api/workout/generate-plan', methods=['POST'])
def generate_workout():
    """Generate a full weekly workout plan using RF model or manual day selection."""
    try:
        data = request.json
        user_id        = data.get('user_id')
        mode           = data.get('mode', 'ai')       # 'ai' or 'manual'
        days_available = data.get('days_available')     # required when mode='manual'

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        if mode == 'manual' and not days_available:
            return jsonify({"error": "days_available is required for manual mode"}), 400

        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        plan = generate_workout_plan(user_id, service_client, mode=mode, manual_days=days_available)
        return jsonify(plan), 200

    except ValueError as e:
        print("Workout Plan Generation Error:", e)
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        print("Workout Plan Generation Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/workout/swap-exercise', methods=['POST'])
def swap_workout_exercise():
    """Swap a single exercise in the plan (stateless)."""
    try:
        data = request.json
        muscle_group      = data.get('muscle_group')
        specific_muscle   = data.get('specific_muscle')
        experience_level  = data.get('experience_level', 'Beginner')
        equipment_access  = data.get('equipment_access', 'gym')
        used_exercise_ids = data.get('used_exercise_ids', [])

        if not muscle_group:
            return jsonify({"error": "muscle_group is required"}), 400

        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        new_exercise = swap_exercise(
            muscle_group, specific_muscle, experience_level,
            equipment_access, used_exercise_ids, service_client
        )

        if new_exercise:
            return jsonify({"new_exercise": new_exercise}), 200
        else:
            return jsonify({"error": "No alternative exercises available"}), 404

    except Exception as e:
        print("Workout Swap Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/workout/accept-plan', methods=['POST'])
def accept_workout_plan():
    """Accept a generated workout plan and save to schedule."""
    try:
        data = request.json
        user_id     = data.get('user_id')
        plan_id     = data.get('plan_id')
        weekly_plan = data.get('weekly_plan')

        if not all([user_id, plan_id, weekly_plan]):
            return jsonify({"error": "Missing user_id, plan_id, or weekly_plan"}), 400

        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        result = accept_plan(user_id, plan_id, weekly_plan, service_client)
        return jsonify(result), 200

    except Exception as e:
        print("Accept Workout Plan Error:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/api/workout/interact', methods=['POST'])
def log_workout_interaction():
    """Log a user interaction with a workout exercise (rated, swapped, disliked)."""
    try:
        data = request.json
        user_id         = data.get('user_id')
        exercise_id     = data.get('exercise_id')
        action_type     = data.get('action_type')
        explicit_rating = data.get('explicit_rating')
        plan_id         = data.get('plan_id')

        if not all([user_id, exercise_id, action_type]):
            return jsonify({"error": "user_id, exercise_id, and action_type are required"}), 400

        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", key)
        service_client = create_client(url, service_key)

        # Build preference score
        pref_map = {"rated": 1, "swapped": -1, "disliked": -1}
        preference_score = pref_map.get(action_type, 0)

        record = {
            "user_id":          user_id,
            "exercise_id":      exercise_id,
            "plan_id":          plan_id,
            "action_type":      action_type,
            "explicit_rating":  explicit_rating,
            "preference_score": preference_score,
            "is_implicit":      action_type not in ("rated",),
        }

        service_client.table('user_workout_interactions').insert(record).execute()

        return jsonify({"status": "success", "message": f"Interaction '{action_type}' logged"}), 201

    except Exception as e:
        print("Workout Interaction Error:", e)
        return jsonify({"error": str(e)}), 500



# ======================== ENTRY POINT ========================
if __name__ == '__main__':
    app.run(debug=True, port=5000)
