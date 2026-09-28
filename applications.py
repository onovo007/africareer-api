"""Application-specific structure and deterministic length checks."""
import io
import re
from datetime import date
from docx import Document
from docx.shared import Pt, Cm
from quality import DraftValidationError

UCAS_URL='https://www.ucas.com/applying/applying-to-university/writing-your-personal-statement/how-to-write-your-personal-statement-for-2026-entry-onwards'
CAMBRIDGE_URL='https://www.postgraduate.study.cam.ac.uk/courses/directory/cvphpdhpc/apply'
FORMATS=('letter','statement','ucas','research_proposal')
# Paraphrased labels: use the official portal for the exact question wording.
UCAS_HEADINGS=['Motivation for the subject','Preparation through education','Preparation outside education']
PROPOSAL_HEADINGS=['Research question and rationale','Relevant preparation','Proposed methods','Feasibility and ethics','Research fit and next steps']

def application_rules(category, school, programme, document_format='auto', max_characters=None, max_words=None):
    known_cambridge='cambridge' in school.lower() and 'public health and primary care' in programme.lower() and 'phd' in category.lower()
    known_oxford='oxford' in school.lower() and category=='Undergraduate program'
    fmt=document_format
    if fmt=='auto':
        fmt='ucas' if known_oxford else 'statement' if known_cambridge else 'letter'
    if fmt not in FORMATS:
        raise DraftValidationError('Choose a supported document format.')
    if known_oxford and fmt!='ucas':
        raise DraftValidationError('Oxford undergraduate UCAS applications need three statement answers. Select UCAS format.')
    if known_cambridge and fmt=='letter':
        raise DraftValidationError('This Cambridge programme requires a statement of interest, not an addressed letter. Select statement format.')
    cap=4000 if fmt=='ucas' else 2500 if known_cambridge and fmt=='statement' else None
    if cap and date.today()>date(2026,10,28):
        raise DraftValidationError('This application preset needs a fresh official-page review before it can generate a document.')
    if max_characters:
        cap=min(cap,max_characters) if cap else max_characters
    return dict(format=fmt,max_characters=cap,max_words=max_words,
                headings=UCAS_HEADINGS if fmt=='ucas' else PROPOSAL_HEADINGS if fmt=='research_proposal' else ['Statement'] if fmt=='statement' else ['Letter'],
                requirements_url=UCAS_URL if fmt=='ucas' else CAMBRIDGE_URL if known_cambridge else '',
                requirements_reviewed_on='2026-09-28' if fmt=='ucas' or known_cambridge else None,
                checklist=['Review every personal claim against your records.','Check the programme’s current instructions and AI/authorship policy.']+
                (['UCAS: paste each answer into its matching question; the three answers share the character allowance.'] if fmt=='ucas' else [])+
                (['Complete the separate proposed-supervisors field; confirm research fit with a real potential supervisor.','Check references, transcripts and any separate Gates research proposal.'] if known_cambridge else []))

def check_sections(sections,rules):
    if not isinstance(sections,list) or len(sections)!=len(rules['headings']):
        raise DraftValidationError('The draft did not match the required sections. Please retry.')
    output=[]
    for heading,section in zip(rules['headings'],sections):
        body=section.get('text') if isinstance(section,dict) else None
        if not isinstance(body,str) or not body.strip():
            raise DraftValidationError('An application section is empty. Add relevant background and retry.')
        body=body.strip()
        # Models sometimes repeat the UI heading inside the answer body.
        body=re.sub(r'^\s*(?:#{1,6}\s*)?'+re.escape(heading)+r'\s*[:\n]+\s*','',body,flags=re.I)
        if rules['format']=='ucas' and len(body)<350:
            raise DraftValidationError('Each UCAS answer must contain at least 350 characters. Add specific examples and retry.')
        output.append(dict(heading=heading,text=body,characters=len(body),words=len(body.split())))
    # Count exactly the exported prose, including paragraph separators for single-document formats.
    total_chars=sum(s['characters'] for s in output)+(2*(len(output)-1) if rules['format']!='ucas' else 0)
    total_words=sum(s['words'] for s in output)
    if rules['max_characters'] and total_chars>rules['max_characters']:
        raise DraftValidationError(f"Draft has {total_chars} characters; limit is {rules['max_characters']}. Shorten the draft before download.")
    if rules['max_words'] and total_words>rules['max_words']:
        raise DraftValidationError(f"Draft has {total_words} words; limit is {rules['max_words']}. Shorten the draft before download.")
    return output,dict(characters=total_chars,words=total_words)

def render_application(draft):
    rules=draft['rules']
    sections,counts=check_sections(draft['sections'],rules)
    doc=Document()
    doc.styles['Normal'].font.name='Calibri'
    doc.styles['Normal'].font.size=Pt(11)
    for section in doc.sections:
        section.top_margin=section.bottom_margin=Cm(2)
        section.left_margin=section.right_margin=Cm(2.3)
    for s in sections:
        # Headings are navigation labels in multi-section drafts, never counted as answers.
        if len(sections)>1:
            doc.add_heading(s['heading'],level=1)
        for paragraph in s['text'].split('\n\n'):
            doc.add_paragraph(paragraph)
    stream=io.BytesIO(); doc.save(stream)
    return stream.getvalue()
