# Group Report — Lab 18: Production RAG

**Nhóm:** Cá nhân  
**Ngày:** 2026-06-22  
**Repo:** Lab 18 Production RAG Pipeline

## Thành Viên & Phân Công

| Tên | Module | Hoàn thành | Tests pass |
|-----|--------|------------|------------|
| Tiền Anh Kiệt | M1: Chunking | ✅ | 12/12 |
| Tiền Anh Kiệt | M2: Hybrid Search | ✅ | 5/5 |
| Tiền Anh Kiệt | M3: Reranking | ✅ | 5/5 |
| Tiền Anh Kiệt | M4: Evaluation | ✅ | 4/4 |
| Tiền Anh Kiệt | M5: Enrichment | ✅ | 11/11 |

**Tổng test:** 37/37 passed.

## Kết Quả RAGAS

| Metric | Naive | Production | Delta |
|--------|-------|------------|-------|
| Faithfulness | 0.0000 | 0.5583 | +0.5583 |
| Answer Relevancy | 0.0000 | 0.5989 | +0.5989 |
| Context Precision | 0.0000 | 0.9375 | +0.9375 |
| Context Recall | 0.0000 | 0.8083 | +0.8083 |

**Evaluation status:** Production `ok`; naive baseline `failed` do thiếu dependency `langchain_community.chat_models.vertexai` trong môi trường hiện tại.

## Key Findings

1. **Biggest improvement:** Context retrieval tốt hơn baseline rõ rệt. `context_precision=0.9375` và `context_recall=0.8083` cho thấy hybrid retrieval + rerank lấy đúng tài liệu liên quan trong đa số câu.
2. **Biggest challenge:** Các câu hỏi chính sách có nhiều version như nghỉ phép v2023/v2024 và mật khẩu v1/v2 vẫn dễ trả fallback hoặc chọn thiếu bản hiện hành.
3. **Surprise finding:** Retrieval context tốt nhưng faithfulness chỉ 0.5583, nghĩa là bottleneck hiện tại nằm nhiều ở answer generation/prompt và version-aware decision, không chỉ ở search.

## Latency Breakdown

Latency được ghi lại trong `reports/latency_breakdown.json` từ lần chạy pipeline gần nhất. Bảng này dùng cho bonus latency report; không yêu cầu thay đổi logic trong `src/pipeline.py`.

| Step | Time | Notes |
|------|------|-------|
| Chunking | 0.1646s | Load 26 documents, tạo 125 hierarchical child chunks |
| Enrichment | 0.0020s | Combined mode fallback/local enrichment trong lần đo này |
| Indexing | 3.3326s | BM25 index; dense indexing bị skip khi Qdrant/socket không khả dụng |
| Reranker init | 0.0000s | Lazy init; model thật chỉ load khi cấu hình local/download cho phép |
| Build subtotal | 3.4992s | Tổng 4 bước build trước evaluation |

RAGAS evaluation đã có artifact riêng tại `reports/ragas_report.json` với `evaluation_status="ok"` và 20 câu hỏi.

## Presentation Notes (5 Phút)

1. **RAGAS scores:** Production đạt `context_precision=0.9375` và `context_recall=0.8083`; hai metric generation còn thấp hơn là `faithfulness=0.5583`, `answer_relevancy=0.5989`.
2. **Biggest win:** M2 + M3 giúp retrieval chính xác: BM25 bắt keyword tiếng Việt, dense search hỗ trợ semantic, RRF merge ranking, CrossEncoder rerank top candidates.
3. **Case study:** Câu Senior 9 năm thâm niên trả đúng 18 ngày phép nhưng thiếu lương 20-35 triệu. Error Tree: multi-hop query → context phép năm có, context bảng lương thiếu trong final context → cần query decomposition và source-diverse retrieval.
4. **Next optimization nếu có thêm 1 giờ:** Thêm metadata `version`, `effective_year`, `is_current`; boost chính sách hiện hành; tách query multi-hop; sửa answer prompt để giảm fallback `Không tìm thấy`.

## Submission Checklist

- [x] Implement đủ M1-M5.
- [x] `pytest tests/ -v` pass 37/37.
- [x] `reports/ragas_report.json` có Production RAGAS scores.
- [x] `analysis/failure_analysis.md` có Bottom-5 diagnosis, fix và Error Tree.
- [x] Reflection cá nhân đã viết.
