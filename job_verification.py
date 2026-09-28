"""Validate published JobPosting metadata; exclude unknown filters and expired posts."""
import json,re
from datetime import datetime,timezone,timedelta
from html import unescape
from html.parser import HTMLParser
from quality import job_matches
from urllib.parse import urlencode,urlparse

def search_links(role,discipline='',location='',work_mode='',**ignored):
 keywords=' '.join(x.strip() for x in (role,discipline,work_mode if work_mode!='Any' else '') if x.strip())
 return [dict(title='Search Indeed',url='https://www.indeed.com/jobs?'+urlencode({'q':keywords,'l':location}),source='indeed.com'),
         dict(title='Search LinkedIn',url='https://www.linkedin.com/jobs/search/?'+urlencode({'keywords':keywords,'location':location}),source='linkedin.com')]

def mentions(text,criterion):
 text=' '+re.sub(r'[^a-z0-9]+',' ',text.lower())+' '
 terms=re.findall(r'[a-z0-9]+',criterion.lower())
 aliases={'maryland':['maryland','md'],'kenya':['kenya','ke'],'nigeria':['nigeria','ng'],
          'united states':['united states','usa','us'],'united kingdom':['united kingdom','uk']}
 if criterion.lower() in aliases:return any(' '+x+' ' in text for x in aliases[criterion.lower()])
 return all(' '+t+' ' in text or ' '+t+'s ' in text or (t.endswith('s') and ' '+t[:-1]+' ' in text) for t in terms if t not in ('and','or','in','the','years'))

def discovery_lead(result,role,location='',experience='',work_mode='',discipline='',period='',page_read=False):
 title=' '.join(str(result.get('title','')).split())
 snippet=' '.join(str(result.get('content','')).split())
 text=title+' '+snippet
 if not mentions(text,role):return None
 if re.search(r'\b(no longer accepting applications|position (?:has been |is )filled|job (?:has )?expired|vacancy closed)\b',text,re.I):return None
 parsed=urlparse(result['url'])
 if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:return None
 from job_discovery import is_search_page
 board=is_search_page(result['url'],title)
 criteria={'Location':location,'Experience':experience,'Work mode':work_mode,'Discipline':discipline}
 noted=[f'{key}: {value} '+('(mentioned in search text)' if mentions(text,value) else '(not established)')
        for key,value in criteria.items() if value and not value.lower().startswith('any')]
 if period and period!='Any time':noted.append('Posting date: not established; search recency is not a vacancy date')
 return dict(title=title or 'Job search lead',url=result['url'],source=parsed.hostname,
             snippet=snippet[:500],verification_level='board_search' if board else 'discovery',
             filter_notes=noted,verification=('Search results page, not an individual vacancy. ' if board else 'Search-index lead; current opening and eligibility are not confirmed. ')+
             ('Page readable, but complete matching metadata was not available.' if page_read else 'Source page could not be independently read; it may require sign-in or block automated access.'))

def explicitly_unavailable(html,role,work_mode='',now=None):
 # Ignore script templates: translation dictionaries may contain closure messages.
 visible=VisibleJobText();visible.feed(html)
 text=' '.join(' '.join(visible.parts).split())
 if re.search(r'\b(job not found|this (?:job|position|posting|vacancy) (?:is |has been |may have been )?(?:closed|removed|filled|no longer available)|no longer accepting applications)\b',text,re.I):return True
 now=now or datetime.now(timezone.utc);parser=JobSchemaParser();parser.feed(html)
 relevant=[]
 for script in parser.scripts:
  try:data=json.loads(script)
  except (ValueError,TypeError):continue
  for job in records(data):
   if not mentions(str(job.get('title','')),role):continue
   end=timestamp(job.get('validThrough'))
   mode=str(job.get('jobLocationType','')).upper()
   relevant.append(bool(end and end<now) or (work_mode=='On-site' and mode=='TELECOMMUTE') or (work_mode=='Remote' and mode in ('ON_SITE','ONSITE')))
 return bool(relevant) and all(relevant)

class VisibleJobText(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.hidden=0
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style','template'):self.hidden+=1
 def handle_endtag(self,tag):
  if tag in ('script','style','template'):self.hidden=max(0,self.hidden-1)
 def handle_data(self,data):
  if not self.hidden:self.parts.append(data)

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
   if location and not mentions(location_scope,location):continue
   if work_mode=='Remote' and not remote:continue
   if work_mode=='On-site' and (remote or not job.get('jobLocation')):continue
   description=unescape(re.sub('<[^>]+>',' ',str(job.get('description',''))))
   content=' '.join([description,str(job.get('experienceRequirements','')),loc,eligibility,'Remote' if remote else ''])
   mode='' if work_mode in ('Any','Remote','On-site') else work_mode
   if not job_matches({'url':url,'title':str(title),'content':content},role,'',experience,mode,discipline):continue
   return dict(title=str(title),company=str(org['name']),posted_on=job.get('datePosted'),checked_at=now.isoformat(),
               snippet=' '.join(description.split())[:240],verification='Posting details checked against source-page structured data. Confirm the vacancy remains open and review all eligibility requirements before applying.')
 return None
