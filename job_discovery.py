"""Bounded, parallel discovery across independent vacancy search channels."""
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from job_verification import mentions

EMPLOYER_DOMAINS=['myworkdayjobs.com','jobs.lever.co','job-boards.greenhouse.io','boards.greenhouse.io',
                  'jobs.smartrecruiters.com','jobs.ashbyhq.com','careers.icims.com','oraclecloud.com']
REGIONS=[
 (r'\b(nigeria|lagos|abuja|ibadan|port harcourt)\b',['jobberman.com','myjobmag.com']),
 (r'\b(kenya|nairobi|mombasa|kisumu)\b',['brightermonday.co.ke','myjobmag.co.ke']),
 (r'\b(south africa|johannesburg|cape town|durban|pretoria)\b',['myjobmag.co.za','careers24.com']),
 (r'\b(ghana|accra|kumasi)\b',['myjobmagghana.com','jobberman.com.gh']),
]

def canonical_url(url):
    try:
        p=urlsplit(url)
        if p.scheme!='https' or not p.hostname or p.username or p.password:return None
        query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True)
               if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid')]
        return urlunsplit((p.scheme,p.netloc.lower().removeprefix('www.'),p.path.rstrip('/') or '/',urlencode(sorted(query)),''))
    except ValueError:return None

def is_search_page(url,title=''):
    p=urlsplit(url);path=p.path.lower();host=(p.hostname or '').removeprefix('www.')
    if host=='ziprecruiter.com' and path.startswith('/jobs/'):return True
    if 'remoterocketship.com' in host and '/jobs/' in path:return True
    return (path in ('','/','/jobs','/careers','/vacancies') or
            any(x in path for x in ('/search','-jobs.html','/jobs-at/','/jobs/page/','/skills/')) or
            bool(re.search(r'\bjobs (in|near|available|–|\|)|\bjobs, employment',title,re.I)))

def vacancy_candidate(result,work_mode=''):
    title=result.get('title','');path=urlsplit(result.get('url','')).path.lower()
    if any(x in path for x in ('/news/','/blog/','/hire/','/job-descriptions/','/career-advice/')):return False
    if re.search(r'^(how to|hire the best|guide to)|job description[s]? [0-9]{4}|step.by.step guide',title,re.I):return False
    text=title+' '+result.get('content','')
    if work_mode=='Remote' and not is_search_page(result.get('url',''),title):
        if re.search(r'\b(no remote|not remote|remote\s+(?:job\s*)?:\s*(?:no|false)|remote (?:work )?(?:is )?not (?:available|permitted)|on.site only)\b',text,re.I):return False
    return True

def relevance(result,role,discipline,location,work_mode):
    title=result.get('title','');text=title+' '+result.get('content',result.get('snippet',''))
    return (8*mentions(title,role)+3*bool(discipline and mentions(text,discipline))+
            3*bool(location and mentions(text,location))+
            2*bool(work_mode and work_mode!='Any' and mentions(text,work_mode)))

def discover(search,role,discipline,location,work_mode,period,include_ngo,ngo_domains):
    mode=work_mode if work_mode!='Any' else ''
    exact=' '.join(x for x in (role,discipline,location,mode,'vacancy apply') if x)
    broad=' '.join(x for x in (role,location,mode,'job responsibilities qualifications apply') if x)
    regional=next((domains for pattern,domains in REGIONS if re.search(pattern,location,re.I)),None)
    channels=[('Web vacancies',exact,None),('Employer recruitment sites',exact,EMPLOYER_DOMAINS),
              ('Regional job boards' if regional else 'Additional vacancy discovery',broad,regional)]
    if include_ngo:channels.append(('NGO and international organisations',exact,ngo_domains))
    recency={'Past 24 hours':'day','Past week':'week','Past month':'month'}.get(period,'')
    def run(channel):
        label,query,domains=channel
        try:return label,search(query,time_range=recency,domains=domains,max_results=10),None
        except RuntimeError:return label,[],label+' search could not complete.'
    with ThreadPoolExecutor(max_workers=4) as pool: batches=list(pool.map(run,channels))
    unique={};warnings=[];coverage=[]
    for label,items,error in batches:
        coverage.append({'channel':label,'status':'unavailable' if error else 'searched','returned':len(items)})
        if error:warnings.append(error)
        for item in items:
            key=canonical_url(item.get('url',''))
            if not key:continue
            if key not in unique:unique[key]={**item,'discovery_channels':[label]}
            elif label not in unique[key]['discovery_channels']:unique[key]['discovery_channels'].append(label)
    candidates=[r for r in unique.values() if vacancy_candidate(r,work_mode) and mentions(r.get('title','')+' '+r.get('content',''),role)]
    candidates.sort(key=lambda r:(is_search_page(r['url'],r.get('title','')),-relevance(r,role,discipline,location,mode)))
    # Reserve room for other publishers; never let one aggregator consume the batch.
    counts=Counter();chosen=[];overflow=[]
    for r in candidates:
        host=(urlsplit(r['url']).hostname or '').removeprefix('www.')
        if counts[host]>=4:overflow.append(r);continue
        chosen.append(r);counts[host]+=1
    chosen=(chosen+overflow)[:24]
    return chosen,warnings,coverage
