"""
EUEE Study App - Flask Backend
Ethiopian University Entrance Exam Study Platform
"""

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import anthropic
import json
import os
import zipfile
import tempfile
import base64
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ── Config ──────────────────────────────────────────────────────────────────
UPLOAD_FOLDER = Path("uploads")
DATA_FOLDER   = Path("data")
UPLOAD_FOLDER.mkdir(exist_ok=True)
DATA_FOLDER.mkdir(exist_ok=True)

NOTES_FILE    = DATA_FOLDER / "notes.json"
QUESTIONS_FILE = DATA_FOLDER / "questions.json"
PROGRESS_FILE  = DATA_FOLDER / "progress.json"

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ── Helpers ──────────────────────────────────────────────────────────────────
def load_json(path, default):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def extract_text_from_zip_pdf(filepath: str) -> str:
    """Our PDFs are ZIP archives containing .txt files — extract all text."""
    texts = []
    with zipfile.ZipFile(filepath, "r") as z:
        for name in sorted(z.namelist()):
            if name.endswith(".txt"):
                texts.append(z.read(name).decode("utf-8", errors="ignore"))
    return "\n".join(texts)

def extract_images_from_zip_pdf(filepath: str) -> list[dict]:
    """Extract base64-encoded JPEG images from ZIP-PDF for vision API calls."""
    images = []
    with zipfile.ZipFile(filepath, "r") as z:
        for name in sorted(z.namelist()):
            if name.lower().endswith((".jpg", ".jpeg", ".png")):
                data = z.read(name)
                images.append({
                    "name": name,
                    "b64": base64.standard_b64encode(data).decode(),
                    "media_type": "image/jpeg"
                })
    return images

# ── Subject metadata ─────────────────────────────────────────────────────────
SUBJECTS = {
    "biology": {
        "name": "Biology", "icon": "🧬", "color": "#3fb950",
        "chapters": 10, "target": 85,
        "chapter_titles": [
            "Concept of Biology, Biotechnology & Applications",
            "Cell Biology",
            "Classification, Plants and Animals",
            "Biochemical Molecules, Human Biology & Health",
            "Microorganisms",
            "Heredity and Genetics",
            "Environment, Ecology & Climate Change",
            "Enzymes",
            "Energy Transformation",
            "Evolution"
        ]
    },
    "chemistry": {
        "name": "Chemistry", "icon": "⚗️", "color": "#ffa657",
        "chapters": 13, "target": 80,
        "chapter_titles": [
            "Atomic Structure & Periodic Classification",
            "Chemical Bonding",
            "Chemical Kinetics & Stoichiometry",
            "Physical States of Matter",
            "Chemical Equilibrium",
            "Solutions",
            "Inorganic Compounds",
            "Organic Compounds",
            "Polymers",
            "Electrochemistry",
            "Metals and Nonmetals",
            "Chemistry and Industry",
            "Environmental Chemistry"
        ]
    },
    "physics": {
        "name": "Physics", "icon": "⚡", "color": "#58a6ff",
        "chapters": 13, "target": 80,
        "chapter_titles": [
            "Application of Physics",
            "Vectors",
            "Kinematics",
            "Force, Work and Energy",
            "Simple Machines",
            "Temperature and Thermometry",
            "Elasticity & Static Equilibrium",
            "Fluid Statics & Bulk Matter",
            "Waves, Sound, EM Waves & Optics",
            "Electrostatics & Electric Circuits",
            "Electromagnetism",
            "Electronics",
            "Nuclear Physics"
        ]
    },
    "mathematics": {
        "name": "Mathematics", "icon": "📐", "color": "#bc8cff",
        "chapters": 13, "target": 80,
        "chapter_titles": [
            "Number Systems",
            "Solving Equations",
            "Relations, Functions & Types of Functions",
            "Set Theory",
            "Geometry and Measurements",
            "Coordinate Geometry",
            "Matrices and Determinants",
            "Vectors and Transformation of Plane",
            "Statistics and Probability",
            "Sequences and Series",
            "Introduction to Calculus",
            "Linear Programming",
            "Mathematical Applications in Business"
        ]
    },
    "english": {
        "name": "English", "icon": "📖", "color": "#f0a500",
        "chapters": 6, "target": 90,
        "chapter_titles": [
            "Grammar: Parts of Speech",
            "Grammar: Verbs, Tenses & Agreement",
            "Grammar: Questions, Comparisons & Quantifiers",
            "Communication Section",
            "Writing Section",
            "Comprehension Section"
        ]
    },
    "aptitude": {
        "name": "SAT / Aptitude", "icon": "🧠", "color": "#f85149",
        "chapters": 7, "target": 85,
        "chapter_titles": [
            "Classification Items",
            "Analytical & Logical Reasoning",
            "Antonyms",
            "Synonyms",
            "Reading Comprehension",
            "Analogy",
            "Quantitative Reasoning"
        ]
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTES — Pages
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return jsonify({"status": "EUEE Study Hub API is running", "version": "1.0"})


# ═══════════════════════════════════════════════════════════════════════════════
#  API — Subject metadata
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/subjects")
def api_subjects():
    return jsonify(SUBJECTS)


# ═══════════════════════════════════════════════════════════════════════════════
#  API — PDF Upload & AI Extraction
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/upload-pdf", methods=["POST"])
def upload_pdf():
    """
    Accepts a PDF (actually ZIP) upload, extracts text + images,
    then calls Claude to generate structured notes AND MCQ questions
    for each chapter, saving results to data/notes.json and data/questions.json.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file       = request.files["file"]
    subject_id = request.form.get("subject", "").lower().replace(" ", "_")

    if subject_id not in SUBJECTS:
        return jsonify({"error": f"Unknown subject: {subject_id}"}), 400

    # Save upload
    save_path = UPLOAD_FOLDER / f"{subject_id}_{file.filename}"
    file.save(str(save_path))

    # Extract content
    try:
        text   = extract_text_from_zip_pdf(str(save_path))
        images = extract_images_from_zip_pdf(str(save_path))
    except Exception as e:
        return jsonify({"error": f"Could not read file: {e}"}), 400

    subject_meta = SUBJECTS[subject_id]

    # ── Ask Claude to produce notes + questions ──────────────────────────────
    system_prompt = """You are an expert Ethiopian high school teacher preparing students
for the Ethiopian University Entrance Examination (EUEE).
Given the subject content outline, produce:
1. Rich chapter notes (key concepts, definitions, bullet points, formulas)
2. 5 MCQ past-paper-style questions per chapter with 4 options and the correct answer

Respond ONLY with valid JSON — no markdown, no preamble. Format:
{
  "subject": "<subject name>",
  "chapters": [
    {
      "chapter_number": 1,
      "title": "<chapter title>",
      "notes": {
        "summary": "<2-3 sentence overview>",
        "key_concepts": ["concept 1", "concept 2", ...],
        "definitions": {"term": "definition", ...},
        "formulas": ["formula 1", ...],
        "key_points": ["point 1", "point 2", ...]
      },
      "questions": [
        {
          "id": "ch1_q1",
          "question": "...",
          "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
          "answer": "A",
          "explanation": "Brief explanation"
        }
      ]
    }
  ]
}"""

    user_content = [
        {
            "type": "text",
            "text": f"Subject: {subject_meta['name']}\n\nChapter outline from the official EUEE content document:\n\n{text[:8000]}\n\nGenerate detailed notes and 5 MCQ questions for EACH chapter listed. Use the chapter titles: {json.dumps(subject_meta['chapter_titles'])}"
        }
    ]

    # Attach up to 3 images for visual context
    for img in images[:3]:
        user_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": img["media_type"],
                "data": img["b64"]
            }
        })

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}]
    )

    raw = response.content[0].text.strip()
    # Strip any accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Claude returned invalid JSON: {e}", "raw": raw[:500]}), 500

    # Persist notes
    notes = load_json(NOTES_FILE, {})
    questions = load_json(QUESTIONS_FILE, {})

    notes[subject_id] = result.get("chapters", [])
    questions[subject_id] = []
    for ch in result.get("chapters", []):
        for q in ch.get("questions", []):
            q["chapter_number"] = ch["chapter_number"]
            q["chapter_title"]  = ch["title"]
            questions[subject_id].append(q)

    save_json(NOTES_FILE, notes)
    save_json(QUESTIONS_FILE, questions)

    return jsonify({
        "success": True,
        "subject": subject_id,
        "chapters_processed": len(result.get("chapters", [])),
        "questions_generated": len(questions[subject_id])
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  API — Notes
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/notes/<subject_id>")
def get_notes(subject_id):
    notes = load_json(NOTES_FILE, {})
    if subject_id not in notes:
        return jsonify({"error": "Notes not yet generated. Upload the PDF first."}), 404
    return jsonify(notes[subject_id])

@app.route("/api/notes/<subject_id>/<int:chapter_num>")
def get_chapter_notes(subject_id, chapter_num):
    notes = load_json(NOTES_FILE, {})
    chapters = notes.get(subject_id, [])
    for ch in chapters:
        if ch.get("chapter_number") == chapter_num:
            return jsonify(ch)
    return jsonify({"error": "Chapter not found"}), 404

@app.route("/api/notes/<subject_id>/<int:chapter_num>", methods=["PUT"])
def update_chapter_notes(subject_id, chapter_num):
    """Allow admin/teacher to edit notes manually."""
    notes = load_json(NOTES_FILE, {})
    chapters = notes.get(subject_id, [])
    body = request.json or {}
    for i, ch in enumerate(chapters):
        if ch.get("chapter_number") == chapter_num:
            chapters[i].update(body)
            notes[subject_id] = chapters
            save_json(NOTES_FILE, notes)
            return jsonify({"success": True})
    return jsonify({"error": "Chapter not found"}), 404

@app.route("/api/notes/<subject_id>/download")
def download_notes(subject_id):
    """Generate a plain-text notes file for offline use."""
    notes = load_json(NOTES_FILE, {})
    if subject_id not in notes:
        return jsonify({"error": "No notes found"}), 404

    subject_name = SUBJECTS.get(subject_id, {}).get("name", subject_id)
    lines = [f"{'='*60}", f"  EUEE NOTES — {subject_name.upper()}", f"{'='*60}\n"]

    for ch in notes[subject_id]:
        n = ch.get("notes", {})
        lines.append(f"\n{'─'*50}")
        lines.append(f"CHAPTER {ch['chapter_number']}: {ch['title']}")
        lines.append(f"{'─'*50}")
        lines.append(f"\nSUMMARY\n{n.get('summary','')}")

        if n.get("key_concepts"):
            lines.append("\nKEY CONCEPTS")
            for kc in n["key_concepts"]:
                lines.append(f"  • {kc}")

        if n.get("definitions"):
            lines.append("\nDEFINITIONS")
            for term, defn in n["definitions"].items():
                lines.append(f"  {term}: {defn}")

        if n.get("formulas"):
            lines.append("\nFORMULAS")
            for f in n["formulas"]:
                lines.append(f"  {f}")

        if n.get("key_points"):
            lines.append("\nKEY POINTS")
            for kp in n["key_points"]:
                lines.append(f"  ✓ {kp}")

    text = "\n".join(lines)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
    tmp.write(text)
    tmp.close()
    return send_from_directory(os.path.dirname(tmp.name),
                                os.path.basename(tmp.name),
                                as_attachment=True,
                                download_name=f"{subject_name}_EUEE_Notes.txt")


# ═══════════════════════════════════════════════════════════════════════════════
#  API — Questions / Quiz
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/questions/<subject_id>")
def get_questions(subject_id):
    questions = load_json(QUESTIONS_FILE, {})
    chapter = request.args.get("chapter", type=int)
    qs = questions.get(subject_id, [])
    if chapter:
        qs = [q for q in qs if q.get("chapter_number") == chapter]
    return jsonify(qs)

@app.route("/api/questions/<subject_id>/add", methods=["POST"])
def add_question(subject_id):
    """Manually add a past-paper question."""
    questions = load_json(QUESTIONS_FILE, {})
    body = request.json or {}
    required = ["question", "options", "answer"]
    for field in required:
        if field not in body:
            return jsonify({"error": f"Missing field: {field}"}), 400
    if subject_id not in questions:
        questions[subject_id] = []
    body["id"] = f"manual_{len(questions[subject_id])+1}_{int(datetime.now().timestamp())}"
    questions[subject_id].append(body)
    save_json(QUESTIONS_FILE, questions)
    return jsonify({"success": True, "id": body["id"]})

@app.route("/api/quiz/generate", methods=["POST"])
def generate_quiz():
    """Use Claude to generate fresh MCQ questions for any chapter on-demand."""
    body = request.json or {}
    subject_id  = body.get("subject")
    chapter_num = body.get("chapter_number", 1)
    count       = min(body.get("count", 5), 15)

    if subject_id not in SUBJECTS:
        return jsonify({"error": "Unknown subject"}), 400

    subject_meta = SUBJECTS[subject_id]
    chapter_titles = subject_meta["chapter_titles"]
    chapter_title  = chapter_titles[chapter_num - 1] if chapter_num <= len(chapter_titles) else "Unknown"

    notes = load_json(NOTES_FILE, {})
    chapter_notes = ""
    for ch in notes.get(subject_id, []):
        if ch.get("chapter_number") == chapter_num:
            n = ch.get("notes", {})
            chapter_notes = json.dumps(n)
            break

    prompt = f"""Generate {count} EUEE-style multiple choice questions for:
Subject: {subject_meta['name']}
Chapter {chapter_num}: {chapter_title}

Context notes: {chapter_notes[:2000] if chapter_notes else 'Use your knowledge of the Ethiopian curriculum.'}

Return ONLY valid JSON array:
[
  {{
    "id": "gen_ch{chapter_num}_q1",
    "question": "...",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "answer": "A",
    "explanation": "..."
  }}
]"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        qs = json.loads(raw)
    except json.JSONDecodeError:
        return jsonify({"error": "AI returned invalid JSON"}), 500

    return jsonify(qs)


# ═══════════════════════════════════════════════════════════════════════════════
#  API — AI Notes (on-demand for any topic)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/ai-notes", methods=["POST"])
def ai_notes():
    """Generate AI notes for a specific topic the student asks about."""
    body   = request.json or {}
    topic  = body.get("topic", "")
    subject = body.get("subject", "")

    if not topic:
        return jsonify({"error": "Provide a topic"}), 400

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""You are an EUEE tutor. Explain this topic clearly for a Grade 12 Ethiopian student:

Subject: {subject}
Topic: {topic}

Format your response as JSON only:
{{
  "topic": "{topic}",
  "summary": "2-3 sentence overview",
  "key_points": ["point 1", "point 2", ...],
  "definitions": {{"term": "definition"}},
  "formulas": ["formula if applicable"],
  "exam_tips": ["tip 1", "tip 2"]
}}"""
        }]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return jsonify(json.loads(raw))
    except json.JSONDecodeError:
        return jsonify({"error": "AI error", "raw": raw[:300]}), 500


# ═══════════════════════════════════════════════════════════════════════════════
#  API — Progress Tracker
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/progress", methods=["GET"])
def get_progress():
    return jsonify(load_json(PROGRESS_FILE, {}))

@app.route("/api/progress", methods=["POST"])
def update_progress():
    """
    Body: { subject, chapter_number, completed (bool), quiz_score (0-100) }
    """
    body    = request.json or {}
    subject = body.get("subject")
    chapter = body.get("chapter_number")
    if not subject or not chapter:
        return jsonify({"error": "subject and chapter_number required"}), 400

    progress = load_json(PROGRESS_FILE, {})
    if subject not in progress:
        progress[subject] = {}
    key = str(chapter)
    if key not in progress[subject]:
        progress[subject][key] = {}

    if "completed" in body:
        progress[subject][key]["completed"] = body["completed"]
    if "quiz_score" in body:
        # Keep best score
        existing = progress[subject][key].get("best_score", 0)
        progress[subject][key]["best_score"] = max(existing, body["quiz_score"])
        progress[subject][key]["attempts"]   = progress[subject][key].get("attempts", 0) + 1
    progress[subject][key]["last_updated"] = datetime.now().isoformat()

    save_json(PROGRESS_FILE, progress)
    return jsonify({"success": True, "progress": progress[subject][key]})

@app.route("/api/progress/reset", methods=["POST"])
def reset_progress():
    save_json(PROGRESS_FILE, {})
    return jsonify({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  Run
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
