import unittest,json
from unittest.mock import patch
import core
from job_verification import checked_posting,discovery_lead
class JobDiscoveryTests(unittest.TestCase):
 def search(self,html=None,error=False):
  r={'title':'Data Scientist','url':'https://employer.example/careers/123','content':'Public health remote role in Maryland'}
  with patch('core.web_job_search',side_effect=RuntimeError('offline') if error else None,return_value=[r,r]),patch('link_safety.public_target',return_value=('employer.example','8.8.8.8','/')),patch('link_safety.public_html',return_value=html):
   return core.find_jobs('Data Scientist','Public Health','Maryland','Any','Remote','Past week',False)
 def test_blocked_page_kept_without_verification_claim(self):
  r=self.search();self.assertEqual(len(r['results']),1);self.assertEqual(r['results'][0]['verification_level'],'discovery');self.assertIn('Posting date: not established',str(r));self.assertEqual(len(r['search_links']),2)
 def test_missing_metadata_kept_as_lead(self):
  self.assertEqual(self.search('<html>Job details</html>')['results'][0]['verification_level'],'discovery')
 def test_expired_post_not_downgraded(self):
  html='<script type="application/ld+json">'+json.dumps({'@type':'JobPosting','title':'Data Scientist','validThrough':'2020-01-01'})+'</script>'
  self.assertEqual(self.search(html)['results'],[])
 def test_provider_failure_has_useful_explicit_fallback(self):
  r=self.search(error=True);self.assertEqual(r['status'],'partial');self.assertTrue(r['warnings']);self.assertEqual(len(r['search_links']),2)
 def test_state_abbreviation_checked(self):
  html='<script type="application/ld+json">'+json.dumps({'@type':'JobPosting','title':'Data Scientist','hiringOrganization':{'name':'Example'},'jobLocation':{'address':{'addressRegion':'MD'}}})+'</script>'
  self.assertIsNotNone(checked_posting(html,'https://example.com/job/1','Data Scientist',location='Maryland'))
 def test_unrelated_lead_excluded(self):
  self.assertIsNone(discovery_lead({'url':'https://example.com/1','title':'Nurse','content':'Hospital'},'Data Scientist'))

class CoverageTests(unittest.TestCase):
 def test_parallel_channels_and_region_routing(self):
  from job_discovery import discover
  calls=[]
  def search(q,**kw):calls.append((q,kw));return []
  r,w,c=discover(search,'Nurse','','Nairobi','Any','Past week',True,['unicef.org'])
  self.assertEqual(len(c),4);self.assertTrue(any(x[1]['domains']==['brightermonday.co.ke','myjobmag.co.ke'] for x in calls))
  self.assertTrue(all(x[1]['time_range']=='week' for x in calls))
 def test_one_channel_failure_preserves_others(self):
  from job_discovery import discover
  def search(q,**kw):
   if kw['domains']:raise RuntimeError('offline')
   return [{'title':'Nurse','url':'https://hospital.example/job/1','content':'Kenya'}]
  r,w,c=discover(search,'Nurse','','Kenya','Any','',False,[])
  self.assertEqual(len(r),1);self.assertEqual(len(w),2)
 def test_tracking_duplicates_preserve_job_identifiers(self):
  from job_discovery import canonical_url
  self.assertEqual(canonical_url('https://example.com/job?id=1&utm_source=test#apply'),canonical_url('https://example.com/job?id=1'))
  self.assertNotEqual(canonical_url('https://example.com/job?id=1'),canonical_url('https://example.com/job?id=2'))
 def test_individual_vacancy_precedes_board_pages(self):
  from job_discovery import discover,is_search_page
  items=[{'title':'Nurse Jobs in Kenya','url':'https://example.com/jobs','content':'Nurse'}, {'title':'Registered Nurse','url':'https://hospital.example/job/123','content':'Kenya'}]
  r,w,c=discover(lambda *a,**k:items,'Nurse','','Kenya','Any','',False,[])
  self.assertEqual(r[0]['title'],'Registered Nurse')
  self.assertTrue(is_search_page('https://www.ziprecruiter.com/Jobs/Nurse/--in-Kenya'))
 def test_domain_diversity_and_candidate_budget(self):
  from job_discovery import discover
  items=[{'title':'Nurse','url':f'https://board.example/job/{i}','content':'Kenya'} for i in range(30)]
  items.append({'title':'Nurse','url':'https://hospital.example/job/1','content':'Kenya'})
  r,w,c=discover(lambda *a,**k:items,'Nurse','','Kenya','Any','',False,[])
  self.assertLessEqual(len(r),24);self.assertIn('hospital.example',r[4]['url'])
 def test_plural_role_match(self):
  from job_verification import mentions
  self.assertTrue(mentions('Data Scientists','Data Scientist'))

 def test_runtime_modules_in_container(self):
  import ast
  from pathlib import Path
  root=Path(__file__).resolve().parents[1]
  docker=(root/'Dockerfile').read_text()
  for file in ('core.py','job_verification.py','job_discovery.py'):
   for node in ast.walk(ast.parse((root/file).read_text(encoding='utf-8'))):
    if isinstance(node,ast.ImportFrom) and node.module and (root/(node.module+'.py')).exists():
     self.assertIn(node.module+'.py',docker)
