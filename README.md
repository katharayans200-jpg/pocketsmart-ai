# PocketSmart AI — Smart Budget & Recommendation Assistant

A FastAPI web app that plans budgets and suggests products/services for **home interiors**, **parties** and **jewelry** (amounts in ₹), using Google Gemini. Built as an academic project.

## Features
- Register / login / logout (bcrypt-hashed passwords, signed session cookies), protected pages, per-user history
- **Home planner** – lights, ceiling fans, furniture, dining tables, other furniture; allocation per category
- **Party planner** – venue, catering, decorations, entertainment, miscellaneous; per-guest catering figure
- **Jewelry planner** – occasion, type, style, metal, colours, optional outfit image (JPG/JPEG/PNG) analysed by Gemini
- Budget maths done in **Python, not by the AI**: allocations add up exactly, every category is capped, totals/remaining are computed deterministically, and a plan can never exceed your budget
- AI output validated with Pydantic; bad/incomplete replies fall back to clearly labelled sample data
- **Demo mode** (no key, or `DEMO_MODE=true`, or Gemini unavailable) — always labelled "SAMPLE / not AI-generated"
- Shopping/service **search links** (Amazon, Flipkart, IKEA, Swiggy, Zomato, OYO, Google Maps, Tanishq, CaratLane, BlueStone)

> **Honesty notes.** Prices are *estimates* (AI or sample), never verified live prices. No ratings, reviews or stock levels are shown. `product_service.py` only builds search links; it is the single place to plug in real retailer APIs later. Links were not opened live while building this project — if a retailer changes its search URL, edit `app/services/product_service.py`. The PDF's fabricated "testimonials" were deliberately not included.

## Tech stack
Python 3.10+, FastAPI, Uvicorn, Pydantic, SQLAlchemy + SQLite, Jinja2, vanilla JS/CSS, `google-genai` (official Google Gen AI SDK), Pillow, bcrypt, python-dotenv, python-multipart.
(The PDF mentions Flask in its overview; this project uses FastAPI throughout.)

## Folder structure
```
PocketSmart-AI/
├── app/
│   ├── main.py  config.py  database.py  templating.py
│   ├── models/      user.py, recommendation.py          (SQLAlchemy tables)
│   ├── schemas/     auth, home, party, jewelry, plan, ai (Pydantic)
│   ├── routes/      auth, pages, home, party, jewelry, history
│   ├── services/    gemini_service, recommendation_service, budget_service,
│   │                product_service, prompts, sample_data
│   ├── utils/       deps, security, images, errors, numbers
│   └── templates/   base, index, login, register, dashboard, *_planner, history, recommendations, error
├── static/css/style.css   static/js/app.js
├── uploads/        (sanitised outfit images, created at runtime)
├── tests/          (pytest)
├── check_gemini.py (optional key/model connectivity check)
├── run.py  requirements.txt  requirements-dev.txt  .env.example  .gitignore
```
Architecture: browser → FastAPI route → `recommendation_service` (Python splits budget → Gemini suggests items → Pydantic validates → Python caps/totals) → saved to SQLite → JSON → `app.js` renders cards.

## Run it on Windows (PowerShell + VS Code)
Prerequisite: Python 3.10 or newer from python.org (tick "Add python.exe to PATH"). Check with `python --version`.

1. **Extract** `PocketSmart-AI.zip` (right-click → Extract All), e.g. into `C:\Projects\`.
2. **Open in VS Code:** `cd C:\Projects\PocketSmart-AI` then `code .` (or File → Open Folder). Open a terminal: *Terminal → New Terminal* (PowerShell).
3. **Create a virtual environment:**
   ```powershell
   python -m venv .venv
   ```
4. **Activate it:**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks scripts, run once: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, then activate again. You should see `(.venv)` in the prompt.
5. **Install dependencies:**
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
6. **Create your `.env`:**
   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```
7. **Fill in `.env`:** `GEMINI_API_KEY=` your key from Google AI Studio, `GEMINI_MODEL=` the model ID you chose there, and `SECRET_KEY=` any long random text. Generate one with:
   ```powershell
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Save the file. Never share or commit `.env`. (Without a key/model the app runs in labelled **demo mode**.)
8. *(Optional)* test your key: `python check_gemini.py` (add an image path to test image input too).
9. **Start the server:**
   ```powershell
   python run.py
   ```
   (equivalent: `uvicorn app.main:app --reload`). The SQLite database `pocketsmart.db` and its tables are created automatically on first start.
10. **Open** <http://127.0.0.1:8000> in your browser, register, and use the planners. The top bar shows "Demo mode" until Gemini is configured. Health check: <http://127.0.0.1:8000/health>.
11. **Stop** the server with `Ctrl + C`. Leave the venv with `deactivate`.

## Configuration (`.env`)
| Variable | Meaning |
|---|---|
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Both required for live AI |
| `DATABASE_URL` | default `sqlite:///./pocketsmart.db` |
| `SECRET_KEY` | signs session cookies (if empty, a temporary key is used and logins reset on restart) |
| `GEMINI_TIMEOUT_SECONDS` | default 60 |
| `DEMO_MODE` | `true` forces sample data |
| `MAX_UPLOAD_MB` | outfit image limit, default 5 |
| `HOST`, `PORT`, `RELOAD` | server settings |

## Routes
| Method | Path | Purpose |
|---|---|---|
| POST | `/register`, `/login`, `/logout` | auth (HTML forms) |
| GET | `/`, `/dashboard`, `/home-planner`, `/party-planner`, `/jewelry-planner`, `/history`, `/history/{id}` | pages (dashboard onward need login) |
| POST | `/generate-home`, `/generate-party` | JSON body → saved plan |
| POST | `/generate-jewelry` | multipart form with optional `outfit_image` |
| GET | `/recommendations/history`, `/recommendations/{id}`, `/recommendations/{id}/image` | your saved plans (other users' ids return 404) |
| GET | `/health` | status, no secrets |

Interactive API docs: `/docs`.

## Tests
```powershell
pip install -r requirements-dev.txt
python -m pytest
```
Tests use a temporary database and a **mocked** Gemini client — they never call the real API and need no key. To check your real key, use `python check_gemini.py`.

## Troubleshooting
- **`python` not found** – reinstall Python with "Add to PATH", reopen the terminal.
- **Activation blocked** – see step 4 (ExecutionPolicy).
- **Top bar says Demo mode** – `GEMINI_API_KEY` or `GEMINI_MODEL` is empty in `.env` (restart the server after editing).
- **"Gemini could not find the configured model"** – fix `GEMINI_MODEL` to the exact ID shown in AI Studio.
- **"Gemini rejected the API key"** – re-copy the key; no quotes or spaces.
- **Rate limit / timeout messages** – wait a minute; sample data is shown meanwhile and labelled as such.
- **Port 8000 in use** – set `PORT=8001` in `.env`.
- **Logged out after every restart** – set a fixed `SECRET_KEY`.
- **Reset the database** – stop the server and delete `pocketsmart.db`.
- Do not open the `.html` files directly; always use the running server.
