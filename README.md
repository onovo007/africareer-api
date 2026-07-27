# AfriCareer AI - Backend API

Framework-agnostic engine (`core.py`) + FastAPI service (`api.py`) for the Phase 3
Next.js/React front end. All the intelligence from the Streamlit app lives here:
CV / cover-letter / motivation-letter generation, RAG guidance, and verified
course / job / opportunity search. The Streamlit pilot keeps running untouched.

## Run locally
```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # fill in your keys
uvicorn api:app --reload --port 8000
```
Open interactive docs at `http://localhost:8000/docs`.

## Endpoints
| Method | Path | Body -> Response |
|---|---|---|
| GET  | `/health` | service status |
| POST | `/extract-text` | file (PDF/DOCX/TXT) -> `{text}` |
| POST | `/career-guidance` | `{answers, language}` -> `{text}` |
| POST | `/assistant` | `{question, language}` -> `{text}` |
| POST | `/analyze-resume` | `{resume_text, city, additional_info}` -> `{text}` |
| POST | `/cv/from-resume` | `{resume_text, feedback}` -> **.docx** |
| POST | `/cv/from-answers` | `{answers, full_name, contact_line}` -> **.docx** |
| POST | `/cover-letter` | `{resume_text, position, company, city}` -> **.docx** |
| POST | `/motivation-letter` | `{category, school, programme, background, prog_info, full_name, contact_line}` -> **.docx** |
| POST | `/courses` | `{interest, level, cost_pref}` -> `{results:[...]}` |
| POST | `/jobs` | `{role, discipline, location, experience, work_mode, period, include_ngo}` -> `{results:[...]}` |
| POST | `/opportunities` | `{opp_type, field, region}` -> `{results:[...]}` |

## Security
- Set `API_AUTH_TOKEN` and every request must send `X-API-Key: <token>` (recommended for production).
- Set `FRONTEND_ORIGIN` to your Vercel/domain URL(s) so only your front end can call it.
- Secrets go in the host dashboard (Render/Railway), never in git.

## Deploy (Render example)
1. Push this folder to a GitHub repo (e.g. `africareer-api`).
2. Render -> New -> Web Service -> connect the repo -> it detects the `Dockerfile`.
3. Add env vars: `OPENAI_API_KEY`, `PINECONE_API_KEY`, `TAVILY_API_KEY`, `API_AUTH_TOKEN`, `FRONTEND_ORIGIN`.
4. Deploy. The Next.js app calls `https://<your-api>.onrender.com`.

Reuses the same Pinecone index (`africareer-kb`), so the knowledge base you already
built (frameworks, best-practice notes, uploaded PDFs) works immediately.
