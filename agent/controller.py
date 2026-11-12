"""Prepare evidence or a static clarification; never invent retrieval confidence."""
from dataclasses import asdict
from .routing import route_query
from .context_packing import BudgetExceeded


class LegalAgent:
    def __init__(self,search_pipeline,packer,known_numbers=()):
        self.search_pipeline,self.packer=search_pipeline,packer
        self.known_numbers=known_numbers

    def prepare(self,query):
        decision=route_query(query,self.known_numbers)
        base={'route':asdict(decision),'answer_generated':False,'llm_called':False}
        if decision.kind!='legal':
            return {**base,'status':decision.kind,'message':decision.message,'retrieval_called':False}
        try:
            self.packer.check_query(query)
        except BudgetExceeded:
            return {**base,'status':'clarify','reason':'request_too_large','retrieval_called':False,
                    'message':'Câu hỏi vượt ngân sách đầu vào. Bạn có thể rút gọn hoặc tách thành từng vấn đề không?'}
        evidence=self.search_pipeline.search(query)
        if not evidence['evidence']:
            return {**base,'status':'clarify','reason':'no_eligible_evidence','retrieval_called':True,
                    'message':'Mình chưa tìm thấy căn cứ trong nguồn được phép truy xuất. Bạn có thể nêu rõ vấn đề hoặc số hiệu văn bản cần tra cứu?',
                    'applied_policy':evidence['applied_policy']}
        try:
            packed=self.packer.pack(query,evidence)
        except BudgetExceeded:
            return {**base,'status':'clarify','reason':'request_too_large','retrieval_called':True,
                    'message':'Câu hỏi vượt ngân sách đầu vào. Bạn có thể rút gọn hoặc tách thành từng vấn đề không?'}
        if packed['status']!='ready':
            return {**base,'status':'clarify','reason':'whole_evidence_does_not_fit','retrieval_called':True,
                    'message':'Ngữ cảnh đầy đủ chưa vừa ngân sách hiện tại. Bạn muốn tập trung vào Điều hoặc vấn đề cụ thể nào?'}
        return {**base,'status':'ready_for_source_selection','retrieval_called':True,
                'packed_request':packed,'applied_policy':evidence['applied_policy'],
                'confidence_policy':'no_calibrated_legal_confidence_threshold',
                'semantic_legal_accuracy_verified':False}
