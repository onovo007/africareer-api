"""
AfriCareer AI - FastAPI backend.

Exposes the core engine (core.py) as a JSON/DOCX API for the Next.js front end.
Run locally:   uvicorn api:app --reload --port 8000
Docs:          http://localhost:8000/docs

Env vars: OPENAI_API_KEY, PINECONE_API_KEY, TAVILY_API_KEY (optional),
          API_AUTH_TOKEN (optional gate), FRONTEND_ORIGIN (CORS; comma-separated).
"""
import io
import os

from fastapi import FastAPI, Header, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

import core

app = FastAPI(title="AfriCareer AI API", version="1.0.0")

_origins = [o.strip() for o in os.getenv("FRONTEND_ORIGIN", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "").strip()


def require_auth(x_api_key: str = Header(default="")):
    """Optional API-key gate. If API_AUTH_TOKEN is set, callers must send X-API-Key."""
    if API_AUTH_TOKEN and x_api_key != API_AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _docx_response(data: bytes, filename: str) -> Response:
    return Response(content=data, media_type=DOCX_MIME,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ----------------------------------------------------------------- request models
class GuidanceIn(BaseModel):
    answers: str
    language: str = "English"


class AssistantIn(BaseModel):
    question: str
    language: str = "English"


class ResumeAnalysisIn(BaseModel):
    resume_text: str
    city: str = ""
    additional_info: str = ""
    language: str = "English"


class CvFromResumeIn(BaseModel):
    resume_text: str
    feedback: str = ""


class CvFromAnswersIn(BaseModel):
    answers: str
    full_name: str = ""
    contact_line: str = ""


class CoverLetterIn(BaseModel):
    resume_text: str
    position: str
    company: str
    city: str = ""


class MotivationIn(BaseModel):
    category: str            # "Undergraduate program" | "PhD / Doctorate position" | "Scholarship"
    school: str
    programme: str
    background: str
    prog_info: str = ""
    full_name: str = ""
    contact_line: str = ""


class CoursesIn(BaseModel):
    interest: str
    level: str = "Beginner"
    cost_pref: str = "Free & Paid"


class JobsIn(BaseModel):
    role: str
    discipline: str = ""
    location: str = ""
    experience: str = ""
    work_mode: str = ""
    period: str = ""
    include_ngo: bool = True


class OpportunitiesIn(BaseModel):
    opp_type: str            # "Scholarship" | "PhD / Doctorate" | "Undergraduate / Masters"
    field: str
    region: str = ""


class EventIn(BaseModel):
    event: str
    user_name: str = ""
    country: str = ""
    language: str = "English"
    details: str = ""


# ------------------------------------------------------------------------ routes
@app.get("/health")
def health():
    return {"status": "ok", "service": "africareer-api", "tavily": bool(core.TAVILY_API_KEY),
            "supabase": bool(core.SUPABASE_URL and core.SUPABASE_KEY)}


@app.post("/event")
def event(body: EventIn):
    # Public (browser posts analytics); best-effort, never blocks.
    return {"ok": core.log_event(body.event, body.user_name, body.country, body.language, body.details)}


@app.post("/extract-text", dependencies=[Depends(require_auth)])
async def extract_text(file: UploadFile = File(...)):
    """Extract plain text from an uploaded PDF/DOCX/TXT (for the resume/CV flows)."""
    name = (file.filename or "").lower()
    raw = await file.read()
    try:
        if name.endswith(".txt"):
            text = raw.decode("utf-8", errors="ignore")
        elif name.endswith(".pdf"):
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(raw))
            text = "".join((p.extract_text() or "") for p in reader.pages)
        elif name.endswith(".docx"):
            from docx import Document
            text = "\n".join(p.text for p in Document(io.BytesIO(raw)).paragraphs)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type (use PDF, DOCX, or TXT)")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")
    return {"text": text}


@app.post("/career-guidance", dependencies=[Depends(require_auth)])
def career_guidance(body: GuidanceIn):
    return {"text": core.career_guidance(body.answers, body.language)}


@app.post("/assistant", dependencies=[Depends(require_auth)])
def assistant(body: AssistantIn):
    return {"text": core.assistant_answer(body.question, body.language)}


@app.post("/analyze-resume", dependencies=[Depends(require_auth)])
def analyze_resume(body: ResumeAnalysisIn):
    return {"text": core.analyze_resume(body.resume_text, body.city, body.additional_info, body.language)}


@app.post("/cv/from-resume", dependencies=[Depends(require_auth)])
def cv_from_resume(body: CvFromResumeIn):
    return _docx_response(core.build_cv_from_resume(body.resume_text, body.feedback), "AfriCareer_CV.docx")


@app.post("/cv/from-answers", dependencies=[Depends(require_auth)])
def cv_from_answers(body: CvFromAnswersIn):
    return _docx_response(core.build_cv_from_answers(body.answers, body.full_name, body.contact_line),
                          "AfriCareer_CV.docx")


@app.post("/cover-letter", dependencies=[Depends(require_auth)])
def cover_letter(body: CoverLetterIn):
    return _docx_response(core.build_cover_letter(body.resume_text, body.position, body.company, body.city),
                          "AfriCareer_CoverLetter.docx")


@app.post("/motivation-letter", dependencies=[Depends(require_auth)])
def motivation_letter(body: MotivationIn):
    return _docx_response(
        core.build_motivation_letter(body.category, body.school, body.programme, body.background,
                                     body.prog_info, body.full_name, body.contact_line),
        "AfriCareer_Motivation_Letter.docx")


@app.post("/courses", dependencies=[Depends(require_auth)])
def courses(body: CoursesIn):
    return {"results": core.find_courses(body.interest, body.level, body.cost_pref)}


@app.post("/jobs", dependencies=[Depends(require_auth)])
def jobs(body: JobsIn):
    return {"results": core.find_jobs(body.role, body.discipline, body.location, body.experience,
                                      body.work_mode, body.period, body.include_ngo)}


@app.post("/opportunities", dependencies=[Depends(require_auth)])
def opportunities(body: OpportunitiesIn):
    return {"results": core.find_opportunities(body.opp_type, body.field, body.region)}
