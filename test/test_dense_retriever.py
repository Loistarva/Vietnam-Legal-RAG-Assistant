# -*- coding: utf-8 -*-
"""
test/test_dense_retriever.py
Unit tests kiểm thử DenseRetriever và LegalVectorStore theo Data Contract Sprint 6.
Chạy kiểm thử: pytest test/test_dense_retriever.py -q
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from embedding.dense_retriever import (
    HAS_UNDERTHESEA,
    MODEL_SPECS,
    DenseRetriever,
    get_model_spec,
    load_dense_retrieval_config,
    preprocess_text,
)
from embedding.vector_store import (
    LegalVectorStore,
    index_metadata_path,
    is_effective_at,
    normalize_chunk_record,
)
from evaluation.evaluate_zero_shot import compute_rubric_scores, evaluate
from scripts.build_index import load_chunks_from_repo


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
            "embed_text_raw": "Chương II > Điều 8. Điều kiện kết hôn > Khoản 1: Nam từ đủ 20 tuổi trở lên nữ từ đủ 18 tuổi trở lên điều kiện kết hôn",
            "metadata": {
                "document_number": "52/2014/QH13",
                "document_title": "Luật Hôn nhân và gia đình",
                "article_number": "Điều 8",
                "clause_number": "Khoản 1",
                "validity_status": "Còn hiệu lực",
                "effective_from": "2015-01-01",
                "effective_to": None,
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
            "embed_text_raw": "Chương V > Điều 81. Việc trông nom, chăm sóc, nuôi dưỡng, giáo dục con sau khi ly hôn > Khoản 2: Vợ chồng thỏa thuận người trực tiếp nuôi con sau khi ly hôn",
            "metadata": {
                "document_number": "52/2014/QH13",
                "document_title": "Luật Hôn nhân và gia đình",
                "article_number": "Điều 81",
                "clause_number": "Khoản 2",
                "validity_status": "Không xác định",
                "effective_from": "2015-01-01",
                "effective_to": None,
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
            "embed_text_raw": "Điều 9. Điều kiện kết hôn: Nam từ 20 tuổi trở lên nữ từ 18 tuổi trở lên điều kiện kết hôn",
            "metadata": {
                "document_number": "22/2000/QH10",
                "document_title": "Luật Hôn nhân và gia đình 2000",
                "article_number": "Điều 9",
                "clause_number": "Khoản 1",
                "validity_status": "Hết hiệu lực",
                "effective_from": "2001-01-01",
                "effective_to": "2015-01-01",
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

    assert results[0]["rank"] == 1
    assert results[1]["rank"] == 2
    assert results[0]["score"] >= results[1]["score"]

    assert top1["chunk_id"] in gold_context_ids
    assert top1["parent_clause_id"] == "l_52_2014_qh13_art_8_clause_1"
    assert retriever_with_data.last_latency_ms["total_ms"] >= 0.0


def test_expired_documents_are_filtered_out(retriever_with_data):
    """Đảm bảo văn bản có validity_status == 'Hết hiệu lực' bị loại bỏ khi không có as_of_date."""
    results = retriever_with_data.search("điều kiện kết hôn nam 20 tuổi nữ 18 tuổi", top_k=5)
    returned_ids = [r["chunk_id"] for r in results]

    assert "l_22_2000_qh10_art_9_clause_1_chunk_1" not in returned_ids
    for item in results:
        assert item["metadata"]["validity_status"] != "Hết hiệu lực"


def test_empty_query_and_empty_store():
    """Store rỗng trả results: []; câu hỏi rỗng raise ValueError như BM25 và Hybrid (E14)."""
    empty_store = LegalVectorStore(collection_name="empty_col", dimension=64, storage_path=":memory:")
    retriever = DenseRetriever(vector_store=empty_store, use_mock=True)

    assert retriever.search("Câu hỏi bất kỳ", top_k=5) == []
    envelope = retriever.retrieve("Câu hỏi bất kỳ", top_k=5, query_id="Q_EMPTY")
    assert envelope == {"query_id": "Q_EMPTY", "retriever": "dense", "results": []}
    for query in ("", "   ", None):
        with pytest.raises(ValueError, match="rỗng"):
            retriever.search(query, top_k=5)  # type: ignore[arg-type]


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


# ====================================================================
# TEST MỚI: E2 - KIỂM TRA SỐ CHIỀU COLLECTION (DIMENSION MISMATCH)
# ====================================================================
def test_collection_dimension_mismatch_raises_value_error():
    """Mở collection đã tồn tại với số chiều khác cấu hình phải raise ValueError ngay lập tức."""
    store_768 = LegalVectorStore(
        collection_name="test_mismatch_collection",
        dimension=768,
        storage_path=":memory:",
    )
    # Tái sử dụng cùng Qdrant client để mở lại collection với dim=1024
    if store_768.client:
        with pytest.raises(ValueError, match="số chiều"):
            with patch("embedding.vector_store.QdrantClient", return_value=store_768.client):
                LegalVectorStore(
                    collection_name="test_mismatch_collection",
                    dimension=1024,
                    storage_path=":memory:",
                )


# ====================================================================
# TEST MỚI: E4 & H8 - TÁCH TỪ VÀ FAIL-FAST KHI THIẾU UNDERTHESEA
# ====================================================================
def test_underthesea_missing_fail_fast_raises_runtime_error():
    """Khi use_word_segmentation=True ở chế độ thật mà thiếu underthesea thì raise RuntimeError."""
    store = LegalVectorStore(collection_name="test_col_h8", dimension=64, storage_path=":memory:")
    with patch("embedding.dense_retriever.HAS_UNDERTHESEA", False):
        with pytest.raises(RuntimeError, match="underthesea"):
            DenseRetriever(
                vector_store=store,
                model_name="bkai-foundation-models/vietnamese-bi-encoder",
                use_mock=False,
                use_word_segmentation=True,
            )


def test_model_specs_and_text_fields():
    """Kiểm tra cấu hình chuẩn của BGE-M3 (raw, no seg) và BKAI (segmented)."""
    bge_spec = get_model_spec("BAAI/bge-m3")
    assert bge_spec["dimension"] == 1024
    assert bge_spec["use_word_segmentation"] is False
    assert bge_spec["text_field"] == "embed_text_raw"

    bkai_spec = get_model_spec("bkai-foundation-models/vietnamese-bi-encoder")
    assert bkai_spec["dimension"] == 768
    assert bkai_spec["use_word_segmentation"] is True
    assert bkai_spec["text_field"] == "embed_text_raw"

    # Bảng model chỉ lấy từ dense.supported_models của config; model lạ không được đoán theo tên
    assert set(MODEL_SPECS) == set(load_dense_retrieval_config()["supported_models"])
    with pytest.raises(ValueError, match="supported_models"):
        get_model_spec("some-org/bkai-unknown")

    # Kiểm tra tiền xử lý query
    store = LegalVectorStore(collection_name="test_specs_col", dimension=64, storage_path=":memory:")
    retriever_bge = DenseRetriever(vector_store=store, model_name="BAAI/bge-m3", use_mock=True)
    assert retriever_bge.use_word_segmentation is False
    assert retriever_bge._preprocess_query("Điều kiện kết hôn") == "Điều kiện kết hôn"


# ====================================================================
# TEST MỚI: E1 - TEMPORAL PRE-FILTERING THEO AS_OF_DATE
# ====================================================================
def test_temporal_filtering_as_of_date(sample_chunks):
    """
    Truy vấn với as_of_date:
    - as_of_date='2010-06-01' -> Luật 2000 có hiệu lực, Luật 2014 chưa có hiệu lực.
    - as_of_date='2026-10-15' -> Luật 2014 có hiệu lực, Luật 2000 đã hết hiệu lực.
    """
    store = LegalVectorStore(collection_name="test_temporal_col", dimension=64, storage_path=":memory:")
    retriever = DenseRetriever(vector_store=store, use_mock=True, use_word_segmentation=False)
    retriever.index_chunks(sample_chunks)

    # Thời điểm năm 2010: Luật 2000 còn hiệu lực (2001 -> 2015)
    hits_2010 = retriever.search("kết hôn", top_k=5, as_of_date="2010-06-01")
    ids_2010 = [h["chunk_id"] for h in hits_2010]
    assert "l_22_2000_qh10_art_9_clause_1_chunk_1" in ids_2010
    assert "l_52_2014_qh13_art_8_clause_1_chunk_1" not in ids_2010

    # Thời điểm năm 2026: Luật 2014 còn hiệu lực, Luật 2000 đã hết hiệu lực
    hits_2026 = retriever.search("kết hôn", top_k=5, as_of_date="2026-10-15")
    ids_2026 = [h["chunk_id"] for h in hits_2026]
    assert "l_52_2014_qh13_art_8_clause_1_chunk_1" in ids_2026
    assert "l_22_2000_qh10_art_9_clause_1_chunk_1" not in ids_2026


def _dated_chunk(i: int, effective_from: str, effective_to):
    return {
        "chunk_id": f"doc_{i}_art_1_clause_1_chunk_1",
        "parent_clause_id": f"doc_{i}_art_1_clause_1",
        "parent_id": f"doc_{i}_art_1_clause_1_parent_1",
        "chunk_text": f"Nội dung kết hôn số {i}",
        "embed_text": f"Điều 1 kết_hôn số {i}",
        "embed_text_raw": f"Điều 1 kết hôn số {i}",
        "validity_status": "Hết hiệu lực" if effective_to else "Còn hiệu lực",
        "effective_from": effective_from,
        "effective_to": effective_to,
    }


def test_qdrant_prefilters_as_of_date_and_returns_full_top_k():
    """Khi số chunk ngoài khoảng hiệu lực nhiều hơn top_k, Qdrant vẫn trả đủ top_k chunk hợp lệ (E1)."""
    chunks = [_dated_chunk(i, "2015-01-01", None) for i in range(80)]
    chunks += [_dated_chunk(100 + i, "2001-01-01", "2015-01-01") for i in range(5)]
    chunks.append(_dated_chunk(200, "", ""))
    store = LegalVectorStore(collection_name="test_prefilter_col", dimension=64, storage_path=":memory:")
    retriever = DenseRetriever(vector_store=store, use_mock=True)
    retriever.index_chunks(chunks)

    hits = retriever.search("kết hôn", top_k=6, as_of_date="2010-06-01")
    ids = {h["chunk_id"] for h in hits}
    assert len(hits) == 6
    assert ids == {f"doc_{i}_art_1_clause_1_chunk_1" for i in (100, 101, 102, 103, 104, 200)}

    hits_now = retriever.search("kết hôn", top_k=50, as_of_date="2026-10-29")
    assert len(hits_now) == 50
    assert all(is_effective_at(h["metadata"], "2026-10-29") for h in hits_now)


def test_parent_id_is_kept_in_record_and_hit():
    """normalize_chunk_record và kết quả Dense giữ parent_id của corpus (E6)."""
    chunk = _dated_chunk(1, "2015-01-01", None)
    assert normalize_chunk_record(chunk)["parent_id"] == "doc_1_art_1_clause_1_parent_1"
    store = LegalVectorStore(collection_name="test_parent_col", dimension=64, storage_path=":memory:")
    retriever = DenseRetriever(vector_store=store, use_mock=True)
    retriever.index_chunks([chunk])
    assert retriever.search("kết hôn", top_k=1)[0]["parent_id"] == "doc_1_art_1_clause_1_parent_1"


def test_store_raises_without_qdrant_client():
    """use_qdrant=True mà thiếu qdrant-client thì báo lỗi, không lặng lẽ dùng bộ nhớ trong (H8)."""
    with patch("embedding.vector_store.HAS_QDRANT", False):
        with pytest.raises(ImportError, match="qdrant-client"):
            LegalVectorStore(collection_name="x", dimension=64, storage_path=":memory:")
        store = LegalVectorStore(collection_name="x", dimension=64, use_qdrant=False)
        assert store.client is None


def test_persistent_store_checks_collection_and_metadata(tmp_path, sample_chunks):
    """Mở collection để truy vấn: tên sai báo lỗi, metadata lệch model báo lỗi; recreate dựng lại (E2)."""
    storage = str(tmp_path / "qdrant_storage")
    with pytest.raises(ValueError, match="không tồn tại"):
        LegalVectorStore(collection_name="missing", dimension=64, storage_path=storage)

    built = LegalVectorStore(collection_name="col", dimension=768, storage_path=storage, create_if_missing=True)
    built.client.close()
    # recreate xoá collection 768 chiều cũ thay vì báo lệch số chiều
    store = LegalVectorStore(collection_name="col", dimension=1024, storage_path=storage, recreate=True)
    DenseRetriever(vector_store=store, model_name="BAAI/bge-m3", use_mock=True).index_chunks(sample_chunks)
    store.client.close()

    meta_path = index_metadata_path(storage, "col")
    meta = {"model_name": "BAAI/bge-m3", "dimension": 1024, "use_word_segmentation": False, "corpus_sha256": "abc"}
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    reopened = LegalVectorStore(collection_name="col", dimension=1024, storage_path=storage)
    retriever = DenseRetriever(vector_store=reopened, model_name="BAAI/bge-m3", use_mock=True)
    assert retriever.verify_index(corpus_sha256="abc")["corpus_sha256"] == "abc"
    with pytest.raises(ValueError, match="corpus_sha256"):
        retriever.verify_index(corpus_sha256="other")
    with pytest.raises(ValueError, match="model_name"):
        DenseRetriever(vector_store=reopened, model_name="AITeamVN/Vietnamese_Embedding", use_mock=True)
    reopened.client.close()

    meta_path.unlink()
    no_meta = LegalVectorStore(collection_name="col", dimension=1024, storage_path=storage)
    with pytest.raises(ValueError, match="metadata"):
        DenseRetriever(vector_store=no_meta, model_name="BAAI/bge-m3", use_mock=True)
    no_meta.client.close()


@pytest.mark.skipif(not HAS_UNDERTHESEA, reason="cần underthesea")
def test_segmented_model_encodes_corpus_and_query_the_same_way(sample_chunks):
    """Model cần tách từ: cùng một chuỗi thì văn bản encode ở phía corpus và câu hỏi bằng nhau (E4)."""
    store = LegalVectorStore(collection_name="test_seg_col", dimension=64, storage_path=":memory:")
    retriever = DenseRetriever(
        vector_store=store, model_name="bkai-foundation-models/vietnamese-bi-encoder", use_mock=True
    )
    for chunk in sample_chunks:
        assert retriever.corpus_text(chunk) == retriever._preprocess_query(chunk["embed_text_raw"])
        assert "_" in retriever.corpus_text(chunk)


def test_is_effective_at_helper():
    """Kiểm tra chi tiết hàm is_effective_at."""
    active_doc = {"effective_from": "2015-01-01", "effective_to": None}
    assert is_effective_at(active_doc, "2026-01-01") is True
    assert is_effective_at(active_doc, "2014-12-31") is False

    historical_doc = {"effective_from": "2001-01-01", "effective_to": "2015-01-01"}
    assert is_effective_at(historical_doc, "2010-05-01") is True
    assert is_effective_at(historical_doc, "2015-01-01") is False
    assert is_effective_at(historical_doc, "2020-01-01") is False


# ====================================================================
# TEST MỚI: E12 - BUILD INDEX INPUT VALIDATION & FAIL-FAST
# ====================================================================
def test_build_index_load_chunks_raises_file_not_found():
    """Truyền file không tồn tại vào load_chunks_from_repo phải raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_chunks_from_repo("non_existent_corpus_file.jsonl")


# ====================================================================
# TEST MỚI: F6 - RUBRIC EVALUATOR CHO ZERO-SHOT
# ====================================================================
def test_rubric_scoring_relevance_and_faithfulness():
    """Kiểm tra logic chấm điểm theo Rubric: relevance, faithfulness, phạt luật hết hiệu lực."""
    # 1. Câu trả lời chuẩn xác
    res = compute_rubric_scores(
        question="Độ tuổi kết hôn là bao nhiêu?",
        prediction="Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên.",
        references=["Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên mới đủ điều kiện kết hôn."],
        category="ket_hon",
    )
    assert res["answer_relevance_score"] >= 4
    assert res["faithfulness_score"] >= 4
    assert res["answer_relevance"] >= 0.75
    assert res["faithfulness"] >= 0.75

    # 2. Phạt nặng viện dẫn luật hết hiệu lực cho câu hỏi hiện hành
    res_expired = compute_rubric_scores(
        question="Độ tuổi kết hôn hiện nay quy định thế nào?",
        prediction="Theo Luật Hôn nhân và gia đình năm 2000, nam từ hai mươi tuổi, nữ mười tám tuổi.",
        references=["Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên."],
        category="ket_hon",
    )
    assert res_expired["faithfulness_score"] == 1
    assert res_expired["faithfulness"] == 0.0

    # 3. Câu trả lời rỗng
    res_empty = compute_rubric_scores(
        question="Câu hỏi bất kỳ?",
        prediction="",
        references=["Đáp án mẫu."],
        category="ket_hon",
    )
    assert res_empty["answer_relevance_score"] == 1
    assert res_empty["faithfulness_score"] == 1
