# Failure Analysis — Lab 18: Production RAG

**Nhóm:** Cá nhân  
**Thành viên:** Tiền Anh Kiệt — M1, M2, M3, M4, M5  
**Nguồn dữ liệu:** `reports/ragas_report.json`

---

## RAGAS Scores

Production pipeline đã chạy evaluation thành công với `evaluation_status="ok"` trên 20 câu hỏi. Naive baseline trong môi trường hiện tại không chạy được RAGAS do thiếu dependency `langchain_community.chat_models.vertexai`, nên baseline giữ score 0 và chỉ dùng làm mốc trạng thái môi trường.

| Metric | Naive Baseline | Production | Delta |
|--------|----------------|------------|-------|
| Faithfulness | 0.0000 | 0.5583 | +0.5583 |
| Answer Relevancy | 0.0000 | 0.5989 | +0.5989 |
| Context Precision | 0.0000 | 0.9375 | +0.9375 |
| Context Recall | 0.0000 | 0.8083 | +0.8083 |

**Nhận xét chính:** Retrieval đã tốt ở hai metric context (`precision=0.9375`, `recall=0.8083`), nhưng generation vẫn yếu ở `faithfulness` và `answer_relevancy`. Vì vậy lỗi lớn nhất nằm ở bước sinh câu trả lời và xử lý câu hỏi version-sensitive, không phải ở coverage retrieval tổng thể.

---

## Bottom-5 Failures

### #1 — Password rotation policy

- **Question:** Bao lâu phải đổi mật khẩu một lần?
- **Expected:** Chính sách hiện hành v2.0 yêu cầu đổi mật khẩu mỗi 120 ngày; chính sách 90 ngày đã bị thay thế.
- **Got:** Không tìm thấy.
- **Worst metric:** faithfulness
- **Average score:** 0.3333
- **Diagnosis:** Câu trả lời không grounded vào context dù corpus có tài liệu chính sách mật khẩu.
- **Error Tree:** Answer sai/thiếu → kiểm tra context/version policy → tài liệu v1/v2 dễ cạnh tranh → generation chọn câu trả lời fallback.
- **Suggested fix:** Boost metadata `is_current=true` cho `mat_khau_v2.md`, thêm prompt rule ưu tiên chính sách hiện hành, và yêu cầu answer trích dẫn số ngày nếu context có con số.

### #2 — Annual leave days

- **Question:** Nhân viên được nghỉ bao nhiêu ngày phép năm?
- **Expected:** Chính sách hiện hành v2024 là 15 ngày phép năm có lương; v2023 là 12 ngày nhưng đã bị thay thế.
- **Got:** Không tìm thấy.
- **Worst metric:** faithfulness
- **Average score:** 0.3750
- **Diagnosis:** Query cần phân biệt chính sách hiện hành với chính sách cũ.
- **Error Tree:** Answer không trả số ngày → context có nhiều loại nghỉ phép/version → rerank chưa ưu tiên `nghi_phep_nam_v2024.md` đủ mạnh → prompt không buộc chọn version mới nhất.
- **Suggested fix:** Thêm metadata `policy_type=annual_leave`, `effective_year=2024`, `is_current=true`; filter hoặc boost tài liệu hiện hành trước rerank.

### #3 — Seniority leave accrual

- **Question:** Thâm niên bao nhiêu năm thì được cộng thêm ngày phép?
- **Expected:** Theo v2024, từ 3 năm trở lên được cộng 1 ngày phép cho mỗi 3 năm; v2023 yêu cầu 5 năm.
- **Got:** Không tìm thấy.
- **Worst metric:** faithfulness
- **Average score:** 0.3958
- **Diagnosis:** Failure cùng nhóm với câu annual leave: câu hỏi nhạy version nhưng retrieval/generation chưa khóa vào bản hiện hành.
- **Error Tree:** Answer fallback → candidate context có thể chứa cả v2023/v2024 → thiếu current-version preference → model không tổng hợp được quy tắc thâm niên.
- **Suggested fix:** Enrichment trích xuất `version`, `effective_year`, `superseded_by`; rerank cộng điểm cho `is_current=true` khi query không chỉ định năm.

### #4 — Multi-hop leave and salary

- **Question:** Một nhân viên Senior có 9 năm thâm niên được nghỉ bao nhiêu ngày phép năm và lương trong khoảng nào?
- **Expected:** 18 ngày phép; lương Senior P3-P4 là 20-35 triệu VNĐ/tháng.
- **Got:** Trả đúng 18 ngày phép nhưng thiếu khoảng lương Senior.
- **Worst metric:** answer_relevancy
- **Average score:** 0.4583
- **Diagnosis:** Multi-hop retrieval chưa giữ đủ cả chính sách nghỉ phép và bảng lương trong final context.
- **Error Tree:** Câu hỏi gồm hai intent → context phép năm đủ → context lương thiếu hoặc bị rerank rớt khỏi top-k → answer chỉ giải quyết một nửa câu hỏi.
- **Suggested fix:** Tách query thành sub-queries (`nghỉ phép thâm niên`, `lương Senior P3-P4`) rồi merge context bằng RRF; tăng final context diversity theo source file.

### #5 — Minimum password length

- **Question:** Mật khẩu phải có tối thiểu bao nhiêu ký tự?
- **Expected:** Chính sách hiện hành v2.0 yêu cầu tối thiểu 12 ký tự; v1.0 là 8 ký tự nhưng đã bị thay thế.
- **Got:** Không tìm thấy.
- **Worst metric:** faithfulness
- **Average score:** 0.5000
- **Diagnosis:** Password policy versioning chưa được xử lý nhất quán.
- **Error Tree:** Answer fallback → password docs có v1/v2 → query không nói version → pipeline cần mặc định chọn bản hiện hành nhưng chưa có rule metadata.
- **Suggested fix:** Tạo version-aware retrieval rule cho nhóm tài liệu policy: nếu query không nêu version, ưu tiên bản có `is_current=true`.

---

## Diagnostic Summary

| Error group | Evidence | Primary fix |
|-------------|----------|-------------|
| Version-sensitive policy | 4/5 worst failures liên quan chính sách cũ/mới | Metadata `version`, `effective_year`, `is_current` + boost current docs |
| Generation fallback | Nhiều câu trả `Không tìm thấy` dù context metrics cao | Prompt bắt buộc trích xuất answer từ context trước khi fallback |
| Multi-hop context loss | Câu Senior trả phép đúng nhưng thiếu lương | Query decomposition + source-diverse context selection |
| Faithfulness below target | Faithfulness 0.5583 thấp hơn context metrics | Grounded answer prompt, citation, lower temperature |

## Case Study

**Question:** Một nhân viên Senior có 9 năm thâm niên được nghỉ bao nhiêu ngày phép năm và lương trong khoảng nào?

**Walkthrough:**
1. Câu hỏi có hai phần: tính ngày phép theo thâm niên và tra khoảng lương Senior.
2. Pipeline trả đúng ngày phép 18 ngày, chứng tỏ retrieval/generation cho policy nghỉ phép hoạt động.
3. Pipeline thiếu khoảng lương 20-35 triệu, chứng tỏ context lương không vào final reranked context hoặc bị prompt bỏ qua.
4. Fix nên nằm ở retrieval orchestration: tách câu hỏi multi-hop thành nhiều sub-query, giữ context đa nguồn, rồi mới rerank/generate.

## Next Optimization If Given One More Hour

1. Thêm metadata version/current trong M5 enrichment cho tài liệu chính sách.
2. Boost tài liệu hiện hành trong M2/M3 khi query không chỉ định năm hoặc version.
3. Tách multi-hop query thành 2-3 sub-query trước RRF.
4. Sửa prompt answer để không fallback `Không tìm thấy` khi context có số liệu trực tiếp.
