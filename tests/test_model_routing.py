import os,unittest
from unittest.mock import patch,Mock
from types import SimpleNamespace
import core

class ModelRoutingTests(unittest.TestCase):
 def tearDown(self):core._configured_llm.cache_clear()
 def test_sol_and_astra_use_supported_parameters(self):
  core._configured_llm.cache_clear()
  with patch.object(core,'ChatOpenAI') as constructor:
   core._configured_llm('gpt-6-sol',True)
   self.assertEqual(constructor.call_args.kwargs['reasoning_effort'],'none')
   self.assertEqual(constructor.call_args.kwargs['temperature'],0)
   core._configured_llm('gpt-6-astra',True)
   self.assertEqual(constructor.call_args.kwargs['reasoning_effort'],'low')
   self.assertIsNone(constructor.call_args.kwargs['temperature'])
   self.assertEqual(constructor.call_args.kwargs['max_retries'],0)
 def test_rollback_models_remain_supported(self):
  core._configured_llm.cache_clear()
  with patch.dict(os.environ,{'GENERAL_MODEL':'gpt-4o-mini','DOCUMENT_MODEL':'gpt-4.1-2025-04-14','DOCTORAL_MODEL':'gpt-4.1-2025-04-14'}),patch.object(core,'ChatOpenAI') as constructor:
   core._llm_client()
   self.assertEqual(constructor.call_args.kwargs['model'],'gpt-4o-mini')
   self.assertNotIn('reasoning_effort',constructor.call_args.kwargs)
 def test_explicit_doctoral_fields_select_request_local_model(self):
  def audit(prompt,facts,generate,*args,**kwargs):
   generate('Draft');generate('Audit')
   return {'sections':[{'text':'Draft'}]}
  with patch.object(core,'audited_draft',side_effect=audit),patch.object(core,'check_sections',return_value=([],{})),patch.object(core,'safe_llm_call') as call,patch.dict(os.environ,{'DOCTORAL_MODEL':'gpt-6-astra'}):
   core.application_draft('PhD / Doctorate position','Example','Public Health','Facts')
   self.assertEqual([c.kwargs['model'] for c in call.call_args_list],['gpt-6-astra']*2)
   call.reset_mock()
   core.application_draft('Undergraduate program','Example','Statistics','My mentor has a PhD')
   self.assertNotIn('model',call.call_args.kwargs)
 def test_truncated_response_fails_closed(self):
  client=Mock();client.invoke.return_value=SimpleNamespace(content='partial',response_metadata={'finish_reason':'length'})
  with patch.object(core,'_llm_client',return_value=client),self.assertRaises(RuntimeError):core.safe_llm_call('Question')

if __name__=='__main__':unittest.main()
