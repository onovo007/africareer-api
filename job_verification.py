"""Validate published JobPosting metadata; exclude unknown filters and expired posts."""
import json,re
from datetime import datetime,timezone,timedelta
from html import unescape
from html.parser import HTMLParser
from quality import job_matches

class JobSchemaParser(HTMLParser):
 def __init__(self):super().__init__();self.capture=False;self.buffer=[];self.scripts=[]
 def handle_starttag(self,tag,attrs):
  if tag=='script' and dict(attrs).get('type','').lower()=='application/ld+json':self.capture=True;self.buffer=[]
 def handle_data(self,data):
  if self.capture:self.buffer.append(data)
 def handle_endtag(self,tag):
  if tag=='script' and self.capture:self.scripts.append(''.join(self.buffer));self.capture=False

def records(value):
 if isinstance(value,list):
  for x in value:yield from records(x)
 elif isinstance(value,dict):
  if value.get('@type')=='JobPosting' or (isinstance(value.get('@type'),list) and 'JobPosting' in value['@type']):yield value
  yield from records(value.get('@graph',[]))

def timestamp(value):
 try:
  parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
  return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
 except (ValueError,TypeError):return None

def checked_posting(html,url,role,location='',experience='',work_mode='',discipline='',period='',now=None):
 now=now or datetime.now(timezone.utc);parser=JobSchemaParser();parser.feed(html)
 for script in parser.scripts:
  try:data=json.loads(script)
  except (ValueError,TypeError):continue
  for job in records(data):
   title=job.get('title');org=job.get('hiringOrganization',{})
   if not title or not isinstance(org,dict) or not org.get('name'):continue
   end=timestamp(job.get('validThrough'))
   if job.get('validThrough') and (not end or end<now):continue
   posted=timestamp(job.get('datePosted'))
   days={'Past 24 hours':1,'Past week':7,'Past month':30}.get(period)
   if days and (not posted or posted>now or posted<now-timedelta(days=days)):continue
   loc=json.dumps(job.get('jobLocation',{}),ensure_ascii=False)
   remote=str(job.get('jobLocationType','')).upper()=='TELECOMMUTE'
   eligibility=json.dumps(job.get('applicantLocationRequirements',{}),ensure_ascii=False)
   # A country in the company description does not establish workplace eligibility.
   location_scope=eligibility if remote and job.get('applicantLocationRequirements') else loc
   if location and not job_matches({'url':url,'title':location_scope},location):continue
   if work_mode=='Remote' and not remote:continue
   if work_mode=='On-site' and (remote or not job.get('jobLocation')):continue
   description=unescape(re.sub('<[^>]+>',' ',str(job.get('description',''))))
   content=' '.join([description,str(job.get('experienceRequirements','')),loc,eligibility,'Remote' if remote else ''])
   mode='' if work_mode in ('Any','Remote','On-site') else work_mode
   if not job_matches({'url':url,'title':str(title),'content':content},role,'',experience,mode,discipline):continue
   return dict(title=str(title),company=str(org['name']),posted_on=job.get('datePosted'),checked_at=now.isoformat(),
               snippet=' '.join(description.split())[:240],verification='Posting details checked against source-page structured data. Confirm the vacancy remains open and review all eligibility requirements before applying.')
 return None
