# -*- coding: utf-8 -*-
"""
test/test_dense_retriever.py
Unit tests kiểm thử DenseRetriever và LegalVectorStore theo Data Contract Sprint 6.
Chạy kiểm thử: pytest test/test_dense_retriever.py -q
"""
from __future__ import annotations

import pytest

from embedding.dense_retriever import DenseRetriever
from embedding.vector_store import LegalVectorStore


@pytest.fixture()
def sample_chunks():
    return [
        {
            "document_id": "l_52_2014_qh13",
            "article_id": "l_52_2014_qh13_art_8",
            "clause_id": "l_52_2014_qh13_art_8_clause_1",
            "chunk_id": "l_52_2014_qh13_art_8_clause_1_chunk_1",
            "parent_clause_id": "l_52_2014_qh13_art_8_clause_1",
            "chunk_text": "Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên mới đủ điều kiện kết hôn.",
            "embed_text": "Chương II > Điều 8. Điều kiện kết hôn > Khoản 1: Nam từ đủ 20 tuổi trở_lên nữ từ đủ 18 tuổi trở_lên điều_kiện kết_hôn",
            "metadata": {
                "document_number": "52/2014/QH13",
                "document_title": "Luật Hôn nhân và gia đình",
                "article_number": "Điều 8",
                "clause_number": "Khoản 1",
                "validity_status": "Còn hiệu lực",
                "source_url": "https://vbpl.vn/tw/Pages/vbpq-toanvan.aspx?ItemID=36870",
            },
        },
        {
            "document_id": "l_52_2014_qh13",
            "article_id": "l_52_2014_qh13_art_81",
            "clause_id": "l_52_2014_qh13_art_81_clause_2",
            "chunk_id": "l_52_2014_qh13_art_81_clause_2_chunk_1",
            "parent_clause_id": "l_52_2014_qh13_art_81_clause_2",
            "chunk_text": "Vợ, chồng thỏa thuận về người trực tiếp nuôi con, nghĩa vụ, quyền của mỗi bên sau khi ly hôn đối với con.",
            "embed_text": "Chương V > Điều 81. Việc trông nom, chăm sóc, nuôi dưỡng, giáo dục con sau khi ly hôn > Khoản 2: Vợ chồng thỏa_thuận người trực_tiếp nuôi con sau khi ly_hôn",
            "metadata": {
                "document_number": "52/2014/QH13",
                "document_title": "Luật Hôn nhân và gia đình",
                "article_number": "Điều 81",
                "clause_number": "Khoản 2",
                "validity_status": "Không xác định",
                "source_url": "https://vbpl.vn/tw/Pages/vbpq-toanvan.aspx?ItemID=36870",
            },
        },
        {
            "document_id": "l_22_2000_qh10",
            "article_id": "l_22_2000_qh10_art_9",
            "clause_id": "l_22_2000_qh10_art_9_clause_1",
            "chunk_id": "l_22_2000_qh10_art_9_clause_1_chunk_1",
            "parent_clause_id": "l_22_2000_qh10_art_9_clause_1",
            "chunk_text": "Nam từ hai mươi tuổi trở lên, nữ từ mười tám tuổi trở lên mới được kết hôn (Luật cũ năm 2000).",
            "embed_text": "Điều 9. Điều kiện kết hôn: Nam từ 20 tuổi trở_lên nữ từ 18 tuổi trở_lên điều_kiện kết_hôn",
            "metadata": {
                "document_number": "22/2000/QH10",
                "document_title": "Luật Hôn nhân và gia đình 2000",
                "article_number": "Điều 9",
                "clause_number": "Khoản 1",
                "validity_status": "Hết hiệu lực",
                "source_url": "https://vbpl.vn/",
            },
        },
    ]


@pytest.fixture()
def retriever_with_data(sample_chunks):
    store = LegalVectorStore(
        collection_name="test_legal_chunks",
        dimension=64,
        storage_path=":memory:",
    )
    retriever = DenseRetriever(
        vector_store=store,
        use_mock=True,
        use_word_segmentation=False,
    )
    retriever.index_chunks(sample_chunks)
    return retriever


def test_dense_search_output_schema_and_ground_truth(retriever_with_data):
    """Kiểm tra kết quả trả về đúng schema Sprint 6, bảo toàn parent_clause_id và tìm đúng Top-1."""
    query = "Nam nữ đủ bao nhiêu tuổi thì đủ điều kiện kết hôn?"
    gold_context_ids = ["l_52_2014_qh13_art_8_clause_1_chunk_1"]

    envelope = retriever_with_data.retrieve(query=query, top_k=2, query_id="Q_DEV_001")
    assert envelope["query_id"] == "Q_DEV_001"
    assert envelope["retriever"] == "dense"
    results = envelope["results"]

    assert len(results) == 2
    top1 = results[0]

    # Kiểm tra các trường bắt buộc của Contract Sprint 6
    required_keys = {
        "chunk_id",
        "document_id",
        "article_id",
        "clause_id",
        "parent_clause_id",
        "rank",
        "score",
        "chunk_text",
        "metadata",
    }
    assert required_keys.issubset(top1.keys())
    assert "text" not in top1, "Không được dùng trường 'text' thay cho 'chunk_text'."

    # Thứ hạng bắt đầu từ 1 và sắp xếp giảm dần theo score
    assert results[0]["rank"] == 1
    assert results[1]["rank"] == 2
    assert results[0]["score"] >= results[1]["score"]

    # Ground truth hit (Strict Match & Parent Match)
    assert top1["chunk_id"] in gold_context_ids
    assert top1["parent_clause_id"] == "l_52_2014_qh13_art_8_clause_1"
    assert retriever_with_data.last_latency_ms["total_ms"] >= 0.0


def test_expired_documents_are_filtered_out(retriever_with_data):
    """Đảm bảo văn bản có validity_status == 'Hết hiệu lực' bị loại bỏ trước khi trả kết quả."""
    results = retriever_with_data.search("điều kiện kết hôn nam 20 tuổi nữ 18 tuổi", top_k=5)
    returned_ids = [r["chunk_id"] for r in results]

    assert "l_22_2000_qh10_art_9_clause_1_chunk_1" not in returned_ids
    for item in results:
        assert item["metadata"]["validity_status"] != "Hết hiệu lực"


def test_empty_query_and_empty_store():
    """Kiểm tra xử lý kết quả rỗng (trả về results: [])."""
    empty_store = LegalVectorStore(collection_name="empty_col", dimension=64, storage_path=":memory:")
    retriever = DenseRetriever(vector_store=empty_store, use_mock=True)

    assert retriever.search("Câu hỏi bất kỳ", top_k=5) == []
    envelope = retriever.retrieve("   ", top_k=5, query_id="Q_EMPTY")
    assert envelope == {"query_id": "Q_EMPTY", "retriever": "dense", "results": []}


@pytest.mark.parametrize("invalid_k", [0, -1, -10, "5", None, True])
def test_invalid_top_k_raises_value_error(retriever_with_data, invalid_k):
    """Kiểm tra xử lý top_k sai kiểu hoặc <= 0."""
    with pytest.raises(ValueError):
        retriever_with_data.search("Điều kiện kết hôn", top_k=invalid_k)  # type: ignore[arg-type]


def test_missing_embed_text_or_chunk_text_rejected():
    """Đảm bảo hợp đồng dữ liệu từ chối chunk thiếu embed_text hoặc dùng text thay cho chunk_text."""
    store = LegalVectorStore(collection_name="invalid_col", dimension=64, storage_path=":memory:")
    retriever = DenseRetriever(vector_store=store, use_mock=True)

    bad_chunk_missing_embed = [
        {
            "chunk_id": "l_52_2014_qh13_art_1_clause_1_chunk_1",
            "parent_clause_id": "l_52_2014_qh13_art_1_clause_1",
            "chunk_text": "Nội dung hợp lệ",
        }
    ]
    with pytest.raises(ValueError, match="embed_text"):
        retriever.index_chunks(bad_chunk_missing_embed)

    bad_chunk_using_text = [
        {
            "chunk_id": "l_52_2014_qh13_art_1_clause_1_chunk_1",
            "parent_clause_id": "l_52_2014_qh13_art_1_clause_1",
            "text": "Dùng sai tên trường text",
            "embed_text": "Chương I > Điều 1: Nội dung",
        }
    ]
    with pytest.raises(ValueError, match="chunk_text"):
        retriever.index_chunks(bad_chunk_using_text)