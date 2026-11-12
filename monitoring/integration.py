"""Callback/timing adapter for Dev 5; leaves business results/exceptions intact."""
from contextlib import contextmanager
from time import perf_counter


class RequestTrace:
    def __init__(self,query_id,emit,metadata=None):
        self.query_id,self.emit=query_id,emit
        self.metadata=dict(metadata or {})

    def record(self,stage,event_type,status,metadata=None,duration_ms=None):
        event={'query_id':self.query_id,'stage':stage,'event_type':event_type,
               'status':status,'duration_ms':duration_ms,
               'masked_metadata':{**self.metadata,**(metadata or {})}}
        try:return self.emit(event)
        except Exception:return False

    @contextmanager
    def stage(self,stage,metadata=None):
        start=perf_counter()
        self.record(stage,'stage_started','STARTED',metadata)
        try:
            yield
        except Exception:
            self.record(stage,'stage_failed','ERROR',metadata,(perf_counter()-start)*1000)
            raise
        else:
            self.record(stage,'stage_completed','OK',metadata,(perf_counter()-start)*1000)
