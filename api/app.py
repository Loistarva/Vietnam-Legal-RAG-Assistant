"""JSON and final-result SSE; no unvalidated token streaming."""
import hmac
import json
import os
from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, StringConstraints
from starlette.concurrency import run_in_threadpool
from agent.source_generation import ProviderUnavailable, InvalidProviderOutput


class ChatRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query:Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=4000)]


def create_app(service=None,api_key=None):
    if service is None:
        from .runtime import AgentService
        service=AgentService()
    key=os.environ.get('LEGAL_RAG_API_KEY','') if api_key is None else api_key
    @asynccontextmanager
    async def lifespan(app):
        yield
        if hasattr(service,'close'):
            await run_in_threadpool(service.close)
    app=FastAPI(title='Vietnam Legal Evidence API',lifespan=lifespan)
    def authorize(x_api_key:str|None=Header(default=None)):
        if key and not hmac.compare_digest((x_api_key or '').encode(),key.encode()):
            raise HTTPException(401,'Invalid API key')
    def invoke(query):
        try:
            return service.chat(query)
        except (ProviderUnavailable,InvalidProviderOutput):
            return {'status':'provider_unavailable','answer_generated':False,
                    'message':'Dịch vụ mô hình hiện không khả dụng.'}
        except Exception:
            raise HTTPException(503,'Legal evidence service unavailable') from None
    @app.get('/health')
    def health():
        return {'status':'ok','readiness':'lazy_initialization'}
    @app.post('/chat',dependencies=[Depends(authorize)])
    def chat(body:ChatRequest):
        return invoke(body.query)
    @app.post('/chat/stream',dependencies=[Depends(authorize)])
    def stream(body:ChatRequest):
        def events():
            yield 'event: status\ndata: {"status":"processing"}\n\n'
            try:
                result=invoke(body.query)
                yield 'event: result\ndata: '+json.dumps(result,ensure_ascii=False)+'\n\n'
            except HTTPException:
                yield 'event: error\ndata: {"status":"service_unavailable"}\n\n'
            yield 'event: done\ndata: {}\n\n'
        return StreamingResponse(events(),media_type='text/event-stream',
                                 headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
    return app
