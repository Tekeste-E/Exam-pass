# EUEE Study Hub

Ethiopian University Entrance Exam Study Platform — Notes, MCQ Quiz, Progress Tracker, AI Tutor

## Project Structure

```
euee_app/
├── app.py                  ← Flask backend (all API routes)
├── requirements.txt        ← Python dependencies
├── .env                    ← Your API key (never commit this!)
├── templates/
│   └── index.html          ← Full frontend (HTML/CSS/JS)
├── uploads/                ← Uploaded PDFs stored here
└── data/
    ├── notes.json          ← AI-extracted chapter notes
    ├── questions.json      ← MCQ questions (auto + manual)
    └── progress.json       ← Student progress tracking
```

---

## Setup (5 minutes)

### 1. Install Python dependencies

```bash
pip install flask flask-cors anthropic
```

### 2. Set your Anthropic API key

Create a `.env` file:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Then load it before running:
```bash
# Linux/Mac
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# Windows
set ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 3. Run the server

```bash
python app.py
```

Open `http://localhost:5000` in your browser.

---

## Features

### 📚 Chapter Notes
- Click any subject in the sidebar
- If notes are uploaded, they display automatically
- Click **"Generate AI Notes"** on any chapter for instant AI notes
- Mark chapters as **Done** to track progress

### 📝 MCQ Quiz
- Select subject + chapter + number of questions
- **"From Past Papers"** mode uses uploaded questions
- **"AI Generated"** mode creates fresh questions via Claude
- Instant feedback with explanations after each answer
- Scores saved to progress tracker

### 📈 Progress Tracker
- Visual progress bars per subject
- Chapter-by-chapter completion status
- Best quiz scores and attempt counts

### 🤖 AI Tutor
- Ask any EUEE question in natural language
- Get structured explanations, key points, formulas, exam tips

### ⬆️ Upload PDFs
- Upload past paper or notes PDFs
- Claude automatically extracts chapter notes + generates 5 MCQs per chapter
- Also supports manually adding questions one by one

---

## Deploying to GitHub Pages (Frontend Only)

If you want to host the frontend on GitHub Pages without a backend:
1. Copy `templates/index.html` to your repo root as `index.html`
2. Change `const API = '';` to point to your deployed backend URL:
   ```js
   const API = 'https://your-backend.railway.app';
   ```

## Deploying Backend (Railway / Render / Fly.io)

### Railway (recommended, free tier)
```bash
npm install -g @railway/cli
railway login
railway init
railway up
railway variables set ANTHROPIC_API_KEY=sk-ant-your-key
```

### Render
- Connect GitHub repo
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Add env variable: `ANTHROPIC_API_KEY`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/api/subjects` | List all subjects |
| POST | `/api/upload-pdf` | Upload PDF → extract notes + questions |
| GET  | `/api/notes/<subject>` | All chapter notes for subject |
| GET  | `/api/notes/<subject>/<chapter>` | Single chapter notes |
| PUT  | `/api/notes/<subject>/<chapter>` | Edit chapter notes |
| GET  | `/api/notes/<subject>/download` | Download notes as .txt |
| GET  | `/api/questions/<subject>` | Get MCQ questions |
| POST | `/api/questions/<subject>/add` | Add manual question |
| POST | `/api/quiz/generate` | Generate fresh AI questions |
| POST | `/api/ai-notes` | On-demand AI explanation |
| GET  | `/api/progress` | Get all progress |
| POST | `/api/progress` | Save progress update |
| POST | `/api/progress/reset` | Reset all progress |

---

## Adding More Past Papers

Upload any past paper PDF through the app's **Upload PDFs** tab.
The PDF format must match the EUEE ZIP-PDF format (images + .txt files inside).

For standard PDFs, the backend handles text extraction automatically.

---

## Exam Info

- **Exam Date:** July 1, 2026
- **Target Score:** 500+ points
- **Subjects:** Biology (10 ch) · Chemistry (13 ch) · Physics (13 ch) · Mathematics (13 ch) · English (6 ch) · SAT/Aptitude (7 ch)
