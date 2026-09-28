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
