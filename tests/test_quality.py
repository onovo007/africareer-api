import unittest
from datetime import date
from unittest.mock import patch
from fastapi.testclient import TestClient
import api
import core
from quality import validate_cv_facts, DraftValidationError, primary_source, job_matches
from course_catalog import reviewed_courses

class QualityTests(unittest.TestCase):
    def test_missing_primary_sources_are_explicit(self):
        with patch.object(core, '_retrieve', return_value=('', [])), patch.object(core, 'safe_llm_call', return_value='Practical advice'):
            answer=core.career_guidance('I am a student')
        self.assertIn('no verified primary document', answer)

    def test_free_search_does_not_trust_generated_cost(self):
        with patch.object(core, 'reviewed_courses', return_value=[{'cost':'Free','url':'https://www.py4e.com/'}]), patch.object(core, 'verify_url', return_value=True), patch.object(core, 'safe_llm_call') as model:
            self.assertEqual(core.find_courses('Python','Beginner','Free only')[0]['cost'],'Free')
            model.assert_not_called()

    def test_live_failure_unsupported_metrics_rejected(self):
        for claim in ('Improved efficiency by 35%', 'Reached 1,000 beneficiaries'):
            with self.assertRaises(DraftValidationError):
                validate_cv_facts({'selected_achievements': [claim]}, 'Template used by 8 clinics; checked 240 reports; trained 18 staff')

    def test_feedback_is_not_factual_source(self):
        with patch.object(core, 'retrieve_career_guidance', return_value=''), patch.object(core, 'safe_llm_call', return_value='{"selected_achievements":["Improved efficiency 35%"]}'):
            with self.assertRaises(DraftValidationError):
                core.build_cv_from_resume('Worked with 8 clinics', 'Try saying improved efficiency 35%')

    def test_language_not_upgraded_and_supplied_numbers_preserved(self):
        with self.assertRaises(DraftValidationError):
            validate_cv_facts({'languages':['English (Native)']}, 'English fluent')
        cv={'selected_achievements':['Checked 240 reports and trained 18 staff']}
        self.assertEqual(validate_cv_facts(cv, 'Checked 240 reports and trained 18 staff'), cv)

    def test_quality_failure_is_clear_409_not_document(self):
        api.limiter.enabled=False
        with patch.object(core, 'build_cv_from_answers', side_effect=DraftValidationError('Unsupported numbers')):
            response=TestClient(api.app).post('/cv/from-answers',json={'answers':'I tutor maths'})
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.json()['detail'],'Unsupported numbers')

    def test_source_seed_and_spoofed_domain_rejected(self):
        self.assertIsNone(primary_source({'source':'UNICEF','text':'Youth Employment Guidelines'}))
        meta=dict(source_url='https://unicef.org.evil.example/doc',verified_primary=True,title='Skills',page=9,document_sha256='a'*64)
        self.assertIsNone(primary_source(meta))
        meta['source_url']='https://www.unicef.org/media/example.pdf'
        self.assertIn('page 9', primary_source(meta))

    def test_course_price_filter_and_expiry(self):
        now=date(2026,9,28)
        free=reviewed_courses('beginner python','Beginner','Free only',now)
        self.assertEqual([x['cost'] for x in free],['Free'])
        self.assertEqual(reviewed_courses('python','Beginner','Paid only',now),[])
        self.assertEqual(len(reviewed_courses('Excel','Intermediate','Free & Paid',now)),1)
        self.assertEqual(reviewed_courses('python','Beginner','Free only',date(2026,11,1)),[])
        self.assertEqual(core.classify_cost('Coursera','Free'),'Unverified cost')

    def test_job_mismatch_and_board_page_rejected(self):
        self.assertFalse(job_matches({'url':'https://example.com/jobs/123','title':'Public health remote Texas','content':'M&E officer'},'Officer','Kenya'))
        self.assertFalse(job_matches({'url':'https://example.com/search','title':'M&E Officer Kenya Remote Mid level'},'Officer','Kenya'))
        self.assertTrue(job_matches({'url':'https://example.com/jobs/123','title':'Monitoring and Evaluation Officer','content':'Kenya remote mid level public health'},'Monitoring and Evaluation Officer','Kenya','Mid level','Remote','Public health'))
