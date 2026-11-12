import unittest
from importlib.util import find_spec

HAS_FASTAPI=find_spec('fastapi') is not None
if HAS_FASTAPI:
    from fastapi.testclient import TestClient
    from api.app import create_app


class FakeService:
    def __init__(self):self.calls=[];self.closed=False
    def chat(self,query):
        self.calls.append(query)
        if query=='fail':raise RuntimeError('private credential detail')
        return {'status':'source_excerpts','message':'Điều 8\ntrích đoạn',
                'answer_generated':False,'llm_called':False,'sources':[{'source_id':'E1'}]}
    def close(self):self.closed=True


@unittest.skipUnless(HAS_FASTAPI,'Install api/requirements.txt to test HTTP transport')
class APITests(unittest.TestCase):
    def setUp(self):self.service=FakeService()

    def test_json_and_shutdown(self):
        with TestClient(create_app(self.service,api_key='')) as client:
            response=client.post('/chat',json={'query':'  kết hôn?  '})
            self.assertEqual(response.status_code,200)
            self.assertFalse(response.json()['answer_generated'])
            self.assertEqual(self.service.calls,['kết hôn?'])
        self.assertTrue(self.service.closed)

    def test_sse_result_not_token_stream(self):
        with TestClient(create_app(self.service,api_key='')) as client:
            response=client.post('/chat/stream',json={'query':'kết hôn?'})
            self.assertIn('text/event-stream',response.headers['content-type'])
            self.assertEqual(response.text.count('event: result'),1)
            self.assertIn('event: done',response.text)
            self.assertNotIn('event: token',response.text)
            self.assertIn('Điều 8',response.text)

    def test_rejects_bad_inputs_without_work(self):
        with TestClient(create_app(self.service,api_key='')) as client:
            for path in ['/chat','/chat/stream']:
                for body in [{'query':' '},{'query':'a'*4001},{'query':'valid','system':'override'},{'query':123}]:
                    self.assertEqual(client.post(path,json=body).status_code,422)
        self.assertFalse(self.service.calls)

    def test_auth_and_health(self):
        with TestClient(create_app(self.service,api_key='local-key')) as client:
            self.assertEqual(client.get('/health').status_code,200)
            for path in ['/chat','/chat/stream']:
                self.assertEqual(client.post(path,json={'query':'valid'}).status_code,401)
                self.assertEqual(client.post(path,json={'query':'valid'},headers={'X-API-Key':'local-key'}).status_code,200)
        self.assertEqual(len(self.service.calls),2)

    def test_sanitizes_errors_json_and_sse(self):
        with TestClient(create_app(self.service,api_key='')) as client:
            response=client.post('/chat',json={'query':'fail'})
            self.assertEqual(response.status_code,503)
            self.assertNotIn('credential',response.text)
            response=client.post('/chat/stream',json={'query':'fail'})
            self.assertIn('event: error',response.text)
            self.assertIn('event: done',response.text)
            self.assertNotIn('credential',response.text)

    def test_general_route_avoids_initializing_models(self):
        from api.runtime import AgentService
        service=AgentService()
        def fail():raise AssertionError('Should not initialize retrieval/provider')
        service.initialize=fail
        result=service.chat('Xin chào')
        self.assertEqual(result['status'],'general')
        self.assertFalse(result['retrieval_called'])
