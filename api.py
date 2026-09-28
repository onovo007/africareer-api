"""
AfriCareer AI - FastAPI backend.

Exposes the core engine (core.py) as a JSON/DOCX API for the Next.js front end.
Run locally:   uvicorn api:app --reload --port 8000
Docs:          http://localhost:8000/docs

Env vars: OPENAI_API_KEY, PINECONE_API_KEY, TAVILY_API_KEY (optional),
          API_AUTH_TOKEN (optional gate), FRONTEND_ORIGIN (CORS; comma-separated).
"""
import json
import io
import os
import secrets
import zipfile
from uuid import UUID, uuid4
from feedback_store import save_feedback
from cv_schema import CV, checked_cv
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Depends, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel as PydanticBaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool
from guards import RequestSizeLimit

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

import core
from quality import DraftValidationError
from evidence import references
from applications import application_rules, check_sections, render_application

class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(str_max_length=20000, str_strip_whitespace=True)

    @field_validator("*", mode="after")
    @classmethod
    def required_text(cls, value, info):
        if isinstance(value, str) and cls.model_fields[info.field_name].is_required() and not value.strip():
            raise ValueError("This field cannot be blank")
        return value

app = FastAPI(title="AfriCareer AI API", version="2.0.0")


# ---- Rate limiting -------------------------------------------------------------
# Use the server-resolved peer address. Only trusted proxy middleware may rewrite it;
# accepting an arbitrary X-Forwarded-For header lets clients bypass limits.
def _client_ip(request: Request):
    return get_remote_address(request)


limiter = Limiter(key_func=_client_ip, default_limits=["30/minute", "300/hour"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestSizeLimit)

# CORS is added AFTER the limiter so it remains the OUTERMOST middleware and 429
# responses still carry the CORS headers the browser needs in order to read them.
def cors_origins(value):
    # Legacy deployments used '*'; never let that override the explicit default.
    return [o.strip().rstrip('/') for o in value.split(',') if o.strip() and '*' not in o] or ['https://africareer.quantiuminsights.com']

_origins = cors_origins(os.getenv("FRONTEND_ORIGIN", "https://africareer.quantiuminsights.com"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["https://africareer.quantiuminsights.com"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "").strip()
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()


def require_auth(x_api_key: str = Header(default="")):
    """Optional API-key gate. If API_AUTH_TOKEN is set, callers must send X-API-Key."""
    if API_AUTH_TOKEN and not secrets.compare_digest(x_api_key, API_AUTH_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def require_admin(x_admin_token: str = Header(default="")):
    """Admin gate for the usage dashboard. Requires ADMIN_TOKEN to be set and matched."""
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin dashboard not configured (set ADMIN_TOKEN)")
    if not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid admin token")


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
    document_format: Literal['auto','letter','statement','ucas','research_proposal'] = 'auto'
    max_characters: int | None = Field(default=None, ge=200, le=20000)
    max_words: int | None = Field(default=None, ge=50, le=4000)


class ApplicationExportIn(MotivationIn):
    sections: list[dict[str, str]] = Field(min_length=1, max_length=5)
    confirmed: bool = False


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
    event: str = Field(min_length=1, max_length=60)
    user_name: str = Field(default="", max_length=100)
    country: str = ""
    language: str = "English"
    details: str = ""


class FeedbackIn(BaseModel):
    request_id: UUID = Field(default_factory=uuid4)
    rating: Literal["up", "down"]
    tool: str = ""           # which tool the feedback is about (career_guidance, assistant, ...)
    comment: str = Field(default="", max_length=1000)
    user_name: str = Field(default="", max_length=100)
    country: str = ""
    language: str = "English"


@app.exception_handler(RuntimeError)
async def provider_error(request: Request, error: RuntimeError):
    return JSONResponse(status_code=503, content={"detail": "The generation service is temporarily unavailable. Please try again shortly."})


@app.exception_handler(DraftValidationError)
async def draft_error(request: Request, error: DraftValidationError):
    return JSONResponse(status_code=409, content={"detail": str(error)})


# ------------------------------------------------------------------------ routes
@app.get("/health")
@limiter.exempt
def health():
    return {"status": "ok", "service": "africareer-api", "release": "pilot-remediation-20260928", "tavily": bool(core.TAVILY_API_KEY),
            "supabase": bool(core.SUPABASE_URL and core.SUPABASE_KEY)}


@app.post("/event")
def event(body: EventIn):
    # Public (browser posts analytics); best-effort, never blocks.
    return {"ok": core.log_event(body.event, body.user_name, body.country, body.language, body.details)}


@app.post("/feedback")
def feedback(body: FeedbackIn):
    payload={'request_id':str(body.request_id),'rating':body.rating,'tool':body.tool[:80],
             'comment':body.comment,'participant_id':body.user_name,'country':body.country,'language':body.language}
    if not save_feedback(core.SUPABASE_URL,core.SUPABASE_KEY,payload):
        raise HTTPException(status_code=503,detail='Feedback was not confirmed saved. Please retry.')
    return {'ok':True,'request_id':str(body.request_id)}


@app.get("/admin/metrics", dependencies=[Depends(require_admin)])
def admin_metrics():
    """Aggregated usage metrics for the admin dashboard (requires X-Admin-Token)."""
    return core.admin_metrics()


@app.post("/extract-text", dependencies=[Depends(require_auth)])
async def extract_text(file: UploadFile = File(...)):
    """Extract plain text from an uploaded PDF/DOCX/TXT (for the resume/CV flows)."""
    name = (file.filename or "").lower()
    raw = await file.read(5 * 1024 * 1024 + 1)
    await file.close()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Maximum file size is 5 MB")
    if not raw:
        raise HTTPException(status_code=400, detail="File is empty")
    return await run_in_threadpool(_extract_document, name, raw)


def _extract_document(name, raw):
    try:
        if name.endswith(".txt"):
            text = raw.decode("utf-8", errors="ignore")
        elif name.endswith(".pdf"):
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(raw))
            if len(reader.pages) > 30:
                raise HTTPException(status_code=400, detail="Maximum PDF length is 30 pages")
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
        elif name.endswith(".docx"):
            from docx import Document
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if sum(entry.file_size for entry in archive.infolist()) > 20 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Expanded document is too large")
            from docx.table import Table
            document=Document(io.BytesIO(raw))
            def block_text(container):
                values=[]
                for block in container.iter_inner_content():
                    if isinstance(block,Table):
                        for row in block.rows:
                            values.append(' | '.join(' '.join(block_text(cell)) for cell in row.cells))
                    else:values.append(block.text)
                return values
            text = "\n".join(block_text(document))
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type (use PDF, DOCX, or TXT)")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Could not read file. Try a text-based PDF, DOCX or UTF-8 TXT.")
    if not text.strip():
        raise HTTPException(status_code=400, detail="No readable text. Try a text-based document.")
    if len(text) > 20000:
        raise HTTPException(status_code=413, detail="Document contains too much text; use a shorter résumé.")
    return {"text": text}


@app.post("/career-guidance", dependencies=[Depends(require_auth)])
def career_guidance(body: GuidanceIn):
    return core.career_guidance(body.answers, body.language, include_evidence=True)


@app.post("/assistant", dependencies=[Depends(require_auth)])
def assistant(body: AssistantIn):
    return core.assistant_answer(body.question, body.language, include_evidence=True)


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
    return _docx_response(core.build_motivation_letter(**body.model_dump()), "AfriCareer_Application_Draft.docx")


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


@app.get('/knowledge')
def knowledge():
    return {'sources': references(), 'scope': 'Reviewed short reference notes, not a complete document corpus.'}


@app.post('/application-draft', dependencies=[Depends(require_auth)])
def application_draft(body: MotivationIn):
    return core.application_draft(**body.model_dump())


@app.post('/application-document', dependencies=[Depends(require_auth)])
def application_document(body: ApplicationExportIn):
    if not body.confirmed:
        raise HTTPException(status_code=422, detail='Confirm that you reviewed the draft before downloading.')
    # Recompute rules from inputs; never trust a client-supplied count or limit.
    rules=application_rules(body.category,body.school,body.programme,body.document_format,body.max_characters,body.max_words)
    sections,counts=check_sections(body.sections,rules)
    # Applicant edits are their words. Deterministic gates still apply; this export
    # does not claim a fresh model/human factual audit of those edits.
    from quality import validate_cv_facts
    validate_cv_facts({'sections':[{'text':x['text']} for x in sections]}, '\n'.join([body.background,body.prog_info,body.full_name,body.contact_line,body.school,body.programme]))
    return _docx_response(render_application({'rules':rules,'sections':sections}), 'AfriCareer_Application_Draft.docx')


class CvDraftIn(BaseModel):
    source: Literal['answers','resume']
    content: str
    feedback: str=''
    full_name: str=''
    contact_line: str=''

class CvExportIn(BaseModel):
    cv: CV
    supplied_facts: str
    confirmed: bool=False

@app.post('/cv/draft', dependencies=[Depends(require_auth)])
def cv_draft(body: CvDraftIn):
    if body.source=='answers':
        cv=core.draft_cv_from_answers(body.content,body.full_name,body.contact_line)
        facts='\n'.join([body.content,body.full_name,body.contact_line])
    else:
        cv=core.draft_cv_from_resume(body.content,body.feedback)
        facts=body.content
    return {'cv':cv,'supplied_facts':facts,'review_notice':'Compare the draft with your original facts. Automated checks can miss errors. Edits require your review before export.'}

@app.post('/cv/document', dependencies=[Depends(require_auth)])
def cv_document(body: CvExportIn):
    if not body.confirmed:
        raise HTTPException(status_code=422,detail='Confirm that you reviewed your CV before downloading.')
    from quality import validate_cv_facts
    cv=checked_cv(body.cv.model_dump())
    validate_cv_facts(cv,body.supplied_facts)
    return _docx_response(core.generate_premium_cv_docx(json.dumps(cv)),'AfriCareer_Reviewed_CV.docx')
