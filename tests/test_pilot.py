import io
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import api
import core


class PilotTests(unittest.TestCase):
    def setUp(self):
        api.limiter.enabled = False
        self.client = TestClient(api.app)

    def test_feedback_validation_and_acknowledgement(self):
        self.assertEqual(self.client.post('/feedback', json={'rating': 'invalid'}).status_code, 422)
        with patch.object(api, 'save_feedback', return_value=False):
            self.assertEqual(self.client.post('/feedback', json={'rating': 'down'}).status_code, 503)
        with patch.object(api, 'save_feedback', return_value=True) as event:
            self.assertTrue(self.client.post('/feedback', json={'rating': 'up'}).json()['ok'])
            self.assertEqual(event.call_count, 1)

    def test_empty_and_oversized_input(self):
        self.assertEqual(self.client.post('/assistant', json={'question': '  '}).status_code, 422)
        self.assertEqual(self.client.post('/assistant', json={'question': 'x' * 20001}).status_code, 422)
        self.assertEqual(self.client.post('/assistant', content=b'x' * 131073).status_code, 413)

    def test_upload_bounds(self):
        self.assertEqual(self.client.post('/extract-text', files={'file': ('cv.txt', b'x' * (5 * 1024 * 1024 + 1))}).status_code, 413)
        self.assertEqual(self.client.post('/extract-text', files={'file': ('cv.txt', b'')}).status_code, 400)
        self.assertEqual(self.client.post('/extract-text', files={'file': ('cv.exe', b'abc')}).status_code, 400)
        self.assertEqual(self.client.post('/extract-text', files={'file': ('cv.txt', b'Analyst with Excel skills')}).json()['text'], 'Analyst with Excel skills')

    def test_provider_failure_is_not_successful_document(self):
        with patch.object(core, 'build_cv_from_answers', side_effect=RuntimeError('secret-provider-detail')):
            response = self.client.post('/cv/from-answers', json={'answers': 'I studied accounting.'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret-provider-detail', response.text)

    def test_llm_error_does_not_become_document_content(self):
        from unittest.mock import Mock
        llm = Mock()
        llm.invoke.side_effect = Exception('private-key-detail')
        with patch.object(core, '_llm_client', return_value=llm):
            with self.assertRaises(RuntimeError) as caught:
                core.safe_llm_call('Write a CV')
        self.assertNotIn('private-key-detail', str(caught.exception))

    def test_admin_denies_missing_or_wrong_token(self):
        with patch.object(api, 'ADMIN_TOKEN', 'test-admin-secret'):
            self.assertEqual(self.client.get('/admin/metrics').status_code, 401)
            self.assertEqual(self.client.get('/admin/metrics', headers={'X-Admin-Token': 'wrong'}).status_code, 401)

    def test_real_docx_round_trip(self):
        from docx import Document
        doc = Document(); doc.add_paragraph('A synthetic CV for testing')
        stream = io.BytesIO(); doc.save(stream)
        response = self.client.post('/extract-text', files={'file': ('test.docx', stream.getvalue())})
        self.assertEqual(response.status_code, 200)
        self.assertIn('synthetic CV', response.json()['text'])

    def test_forwarded_header_cannot_choose_rate_limit_identity(self):
        from starlette.requests import Request
        request = Request({'type': 'http', 'client': ('203.0.113.8', 1234),
                           'headers': [(b'x-forwarded-for', b'1.2.3.4')]})
        self.assertEqual(api._client_ip(request), '203.0.113.8')

    def test_resume_tail_reaches_analysis_prompt(self):
        resume = 'Experience. ' * 600 + 'FINAL QUALIFICATION'
        with patch.object(core, 'retrieve_career_guidance', return_value=''), patch.object(core, 'safe_llm_call', return_value='review') as llm:
            core.analyze_resume(resume)
            self.assertIn('FINAL QUALIFICATION', llm.call_args.args[0])
            self.assertNotIn('ATS Compatibility Score (1-100)', llm.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
