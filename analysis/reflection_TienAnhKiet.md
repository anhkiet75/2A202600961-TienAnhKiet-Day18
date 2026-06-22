# Reflection — Tiền Anh Kiệt

**Module phụ trách:** M1, M2, M3, M4, M5  
**Ngày:** 2026-06-22

## Phần 1: Mapping Bài Giảng

| Lecture Concept | Module | Hàm cụ thể | Observation |
|-----------------|--------|------------|-------------|
| Semantic chunking | M1 | `chunk_semantic()` | Nhóm câu theo similarity khi model có sẵn; fallback lexical giúp chạy offline và tránh treo khi chưa tải model. |
| Hierarchical chunking | M1 + Pipeline | `chunk_hierarchical()`, `run_query()` | Pipeline retrieve child chunk nhưng giữ `parent_id` để trả parent context, đúng pattern retrieve child → return parent. |
| Structure-aware chunking | M1 | `chunk_structure_aware()` | Markdown headers được giữ trong chunk và metadata `section`, giúp reviewer truy vết policy section. |
| BM25 + Dense fusion | M2 | `BM25Search.search()`, `DenseSearch.search()`, `reciprocal_rank_fusion()` | BM25 bắt keyword tiếng Việt tốt; RRF merge BM25/dense ranking và gắn `method="hybrid"`. |
| Cross-encoder reranking | M3 | `CrossEncoderReranker.rerank()` | CrossEncoder thật chỉ load khi bật `USE_LOCAL_MODELS=1` hoặc `ALLOW_MODEL_DOWNLOAD=1`; mặc định lexical fallback để tests nhanh và ổn định. |
| RAGAS 4 metrics | M4 | `evaluate_ragas()`, `failure_analysis()` | Production report có `evaluation_status="ok"` với context precision 0.9375 và context recall 0.8083; failure analysis tập trung vào bottleneck generation/versioning. |
| Contextual enrichment | M5 | `contextual_prepend()`, `_enrich_single_call()` | Enriched text thêm summary/questions/context/metadata để retrieval dễ match hơn; combined mode gom enrichment trong 1 call/chunk. |

## Phần 2: Khó Khăn & Cách Giải Quyết

- **Lỗi gặp phải:** `PermissionError: [Errno 1] Operation not permitted` khi `pytest_rerunfailures` bind socket `127.0.0.1` trong sandbox.
- **Cách debug:** Chạy lại pytest trực tiếp trong môi trường phù hợp; xác nhận lỗi xảy ra ở plugin setup, không phải implementation.
- **Lỗi gặp phải:** Test/pipeline bị chậm vì `SentenceTransformer` và `CrossEncoder` có thể tải model từ Hugging Face.
- **Cách debug:** Thêm guard `USE_LOCAL_MODELS=1` và `ALLOW_MODEL_DOWNLOAD=1`; mặc định dùng lexical fallback để local tests chạy ổn định.
- **Lỗi gặp phải:** `No module named 'qdrant_client'` hoặc thiếu dependency RAGAS khi môi trường không đủ package.
- **Cách debug:** Giữ fallback BM25/RAGAS có trạng thái rõ ràng, không crash pipeline và không nhầm lỗi evaluator với lỗi retrieval.
- **Lỗi phân tích:** Production retrieval có context metrics cao nhưng answer metrics thấp.
- **Cách debug:** Đọc Bottom-5 trong `reports/ragas_report.json`; phân nhóm lỗi thành version-sensitive policy, generation fallback và multi-hop context loss.

## Phần 3: Action Plan Cho Project

## Project: Internal Policy RAG Assistant

### Hiện Tại

- RAG pipeline hiện tại: markdown/PDF documents → chunking → BM25/dense search → rerank → grounded answer → RAGAS eval.
- Known issues: version-sensitive policy retrieval còn dễ nhầm tài liệu cũ/mới; multi-hop query có thể thiếu một source trong final context; answer prompt còn fallback `Không tìm thấy` quá sớm.

### Plan Áp Dụng

1. [ ] Chunking strategy: dùng hierarchical chunking làm default vì child chunk giúp retrieval chính xác, parent context giúp answer đủ ngữ cảnh.
2. [ ] Search: dùng hybrid BM25 + dense; BM25 bắt keyword tiếng Việt tốt, dense xử lý semantic/paraphrase tốt.
3. [ ] Reranking: bật `BAAI/bge-reranker-v2-m3` khi model đã cache local; fallback lexical chỉ dùng cho dev/offline.
4. [ ] Evaluation: dùng RAGAS cho faithfulness, answer relevancy, context precision, context recall; thêm fallback report khi evaluator lỗi.
5. [ ] Enrichment: dùng combined single-call mode để tạo summary/questions/context/metadata với chi phí 1 API call mỗi chunk.
6. [ ] Version control: thêm metadata `policy_type`, `effective_year`, `is_current`, `superseded_by` để boost tài liệu hiện hành như v2024 hoặc password v2.0.
7. [ ] Multi-hop: tách câu hỏi thành sub-query theo intent rồi merge context bằng RRF, bảo đảm context đa nguồn.

### Timeline

- Tuần 1: Cài Qdrant, cache embedding/reranker models, chạy full pipeline local.
- Tuần 2: Thêm metadata version/current và filter/rerank theo chính sách hiện hành.
- Tuần 3: Chạy RAGAS thật với `OPENAI_API_KEY`, phân tích bottom-10 failures.
- Tuần 4: Tối ưu latency, query decomposition và viết report so sánh baseline vs production.

## Tự Đánh Giá

| Tiêu chí | Tự chấm (1-5) | Lý do |
|----------|---------------|-------|
| Hiểu bài giảng | 5 | Map được 5 module vào concept lecture và đo bằng RAGAS. |
| Code quality | 4 | Có fallback/lazy loading để test ổn định; còn cần tối ưu prompt generation. |
| Problem solving | 5 | Debug được dependency/model download/RAGAS failure và phân tích Bottom-5. |
| Readiness | 4 | Tests pass đầy đủ; bước tiếp theo là cải thiện faithfulness và answer relevancy. |
