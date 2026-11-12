"""Exercise HTTP with the existing retrieval index, with OpenAI disabled."""
import json
import os
from pathlib import Path
from fastapi.testclient import TestClient
from .app import create_app
from .runtime import AgentService


def main():
    os.environ['LLM_PROVIDER']='disabled'
    service=AgentService()
    with TestClient(create_app(service,api_key='')) as client:
        greeting=client.post('/chat',json={'query':'Xin chào'})
        assert greeting.status_code==200 and not greeting.json()['retrieval_called']
        assert service.agent is None
        query='Điều kiện kết hôn theo Luật số 52/2014/QH13?'
        legal=client.post('/chat',json={'query':query})
        assert legal.status_code==200,legal.text
        result=legal.json()
        assert result['status']=='source_excerpts',result
        assert result['sources'] and not result['llm_called'] and not result['answer_generated']
        assert 'packed_request' not in result
        stream=client.post('/chat/stream',json={'query':query})
        assert stream.status_code==200
        events=stream.text.split('\n\n')
        rows=[json.loads(event.split('data: ',1)[1]) for event in events if event.startswith('event: result\n')]
        assert len(rows)==1 and rows[0]['status']=='source_excerpts'
        assert rows[0]['sources']==result['sources']
        assert 'event: done' in stream.text
    report={'passed':True,'cases':['greeting_without_model_load','legal_json_real_index','legal_sse_real_index'],
            'provider':'disabled','real_llm_calls':0,'source_ids':[s['source_id'] for s in result['sources']],
            'free_form_answers_validated':False}
    path=Path(__file__).resolve().parents[1]/'data/structure_v2/api/http_smoke.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':main()
