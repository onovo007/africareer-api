"""Manual synthetic model comparison. Never imported by the web service.
Run inside the configured runtime; no credentials or real user records are printed.
"""
import json,time,sys,os
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,'/app')
import openai,core

STUDENT='''Ama Test Example. Undergraduate BSc Statistics at Sample University Ghana, expected June 2027. No paid employment. Volunteer, Campus Learning Group, September 2025 to June 2026: Tutored 12 classmates in introductory statistics. Project, Survey Cleaning, March 2026: Cleaned 300 survey records in Excel. Skills: Excel intermediate; Python beginner; English fluent; French basic. Seeking a data analyst internship. No awards or publications.'''
PRO='''Daniel Test Example. Monitoring and Evaluation Officer, Community Health Example, Nairobi, January 2022 to August 2026. Coordinated monthly reporting across 8 clinics. Trained 25 staff on data quality checks. BSc Statistics, Sample University Kenya, completed 2021. Skills: Excel advanced; R intermediate; SQL beginner; English fluent; Kiswahili fluent. No measured improvement percentage or funding responsibility supplied.'''
PHD='''Daniel Test Example. MSc Epidemiology at Sample University Kenya, completed 2025. Dissertation used logistic regression on 1200 anonymised survey records to study immunisation uptake. No causal inference, publication or award. Two years as a research assistant cleaning survey data in R and conducting literature reviews; dates not supplied. Interested in equitable vaccination delivery in rural Kenya. No supervisor contacted, funding secured, offer received, fieldwork completed or ethics approval obtained.'''
UCAS='''Ama Test Example is applying for undergraduate statistics. Completed secondary school in Ghana in June 2026. Studied mathematics and economics. A statistics project involved cleaning 300 survey records in Excel and comparing missing values across columns. Learned to check data before interpreting a chart. Volunteered from September 2025 to June 2026, tutoring 12 classmates in introductory statistics. Prepared a practice quiz and explained averages with household spending examples. Learned to explain a method in different ways when classmates asked questions. Interested in how statistics can inform public health decisions. Excel intermediate, Python beginner. No prizes, research publications or university attendance.'''

# Keep retrieval identical across variants. This tests model behavior, not search quality.
core._retrieve=lambda *a,**k: ('',[])
core.retrieve_career_guidance=lambda *a,**k: ''
core.TAVILY_API_KEY=''
client=openai.OpenAI(timeout=60,max_retries=0)
all_results=[]
class Adapter:
 def __init__(self,model,document,log):self.model=model;self.document=document;self.log=log
 def invoke(self,messages):
  args={'model':self.model,'messages':[{'role':'system' if m.type=='system' else 'user','content':m.content} for m in messages], 'max_completion_tokens':6000 if self.document else 1800}
  if self.document:args['response_format']={'type':'json_object'}
  if self.model=='gpt-6-astra':args['reasoning_effort']='low'
  else:
   args['temperature']=0 if self.document else .3
   if self.model.startswith('gpt-6'):args['reasoning_effort']='none'
  start=time.monotonic()
  try:r=client.chat.completions.create(**args)
  except openai.APIStatusError as e:
   self.log.append({'error_code':e.code,'status':e.status_code,'seconds':round(time.monotonic()-start,2)});raise
  self.log.append({'model':r.model,'seconds':round(time.monotonic()-start,2),'usage':r.usage.model_dump(),'finish_reason':r.choices[0].finish_reason})
  return SimpleNamespace(content=r.choices[0].message.content)

cases=[
 ('budget_guidance','gpt-4o-mini',lambda:core.assistant_answer('I am a Ghanaian statistics student with five hours weekly and no course budget. Give a realistic four-week route toward a data analyst internship. I only know beginner Python and intermediate Excel. Cite only retrieved UNICEF, ILO, UNESCO or AfDB documents. Do not invent sources, free course prices or guaranteed employment. Use at most 350 words.')),
 ('french_guidance','gpt-4o-mini',lambda:core.assistant_answer('Je suis etudiante au Senegal, debutante en Python, avec trois heures par semaine et aucun budget. Proposez trois etapes concretes vers un stage en analyse de donnees, en 250 mots maximum. Ne pas inventer de references ni garantir un stage.','French')),
 ('resume_feedback','gpt-4o-mini',lambda:core.analyze_resume(PRO,'Nairobi, Kenya','Target NGO M&E roles. Identify evidence already present and gaps; do not invent outcome metrics. Suggest improved bullets without adding unsupported claims.')),
 ('student_cv','gpt-4.1-2025-04-14',lambda:core.draft_cv_from_answers(STUDENT,'Ama Test Example','ama.test@example.com | Accra, Ghana')),
 ('professional_cv','gpt-4.1-2025-04-14',lambda:core.draft_cv_from_resume(PRO,'Emphasize reporting and data-quality training. Preserve skill proficiency and supplied facts.')),
 ('undergraduate_ucas','gpt-4.1-2025-04-14',lambda:core.application_draft('Undergraduate program','Oxford','Statistics',UCAS,full_name='Ama Test Example',document_format='ucas')),
 ('phd_statement','gpt-4.1-2025-04-14',lambda:core.application_draft('PhD / Doctorate position','University of Cambridge','PhD in Public Health and Primary Care',PHD,'Proposed topic: access barriers to routine immunisation in rural Kenya. Do not invent a supervisor or institution-specific claims.',full_name='Daniel Test Example',document_format='statement')),
 ('phd_proposal','gpt-4.1-2025-04-14',lambda:core.application_draft('PhD / Doctorate position','Example University','Public Health',PHD,'Propose a feasible study of access barriers to immunisation in rural Kenya. Clearly distinguish plans from completed work. Include feasibility, ethics and limitations. Do not claim approvals, partnerships, a sample size or funding already exist.',full_name='Daniel Test Example',document_format='research_proposal',max_words=650)),
]
output=Path('/tmp/africareer-model-comparison.json')
for name,baseline,task in cases:
 for model in [baseline,'gpt-6-sol']+(['gpt-6-astra'] if name.startswith('phd_') else []):
  log=[];core._llm_client=lambda:Adapter(model,False,log);core._document_llm_client=lambda:Adapter(model,True,log)
  start=time.monotonic();entry={'case':name,'model':model,'reasoning':'low' if model=='gpt-6-astra' else 'none','calls':log}
  try:entry['output']=task();entry['status']='passed_pipeline'
  except Exception as e:entry['status']='failed_pipeline';entry['error']=str(e)[:1600]
  entry['seconds']=round(time.monotonic()-start,2);all_results.append(entry)
  output.write_text(json.dumps(all_results,ensure_ascii=False,indent=2),encoding='utf-8')
  print('EVAL_RESULT '+json.dumps({k:v for k,v in entry.items() if k not in ('output','calls')})+' calls='+str(len(log)),flush=True)
print('EVAL_COMPLETE '+str(output),flush=True)
