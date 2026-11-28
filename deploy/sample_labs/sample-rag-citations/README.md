# Lab mẫu 2 — RAG có trích dẫn nguồn & Đánh giá Retrieval

## Mục tiêu học tập
Xây dựng pipeline RAG trả lời câu hỏi nội quy dựa trên tài liệu đã chia đoạn, bắt buộc đính kèm mã đoạn nguồn và đo Recall@k trước khi chỉnh prompt.

## Bài 1 — Truy xuất đoạn văn và kiểm tra trích dẫn
- Dùng `retrieve_top_k(query, docs, k=3)` trong `retriever.py` để lấy tối đa 3 đoạn liên quan nhất.
- Mỗi câu khẳng định trong câu trả lời phải kèm mã nguồn `[doc_id:chunk_id]` tồn tại trong top-k đã truy xuất.
- Nếu top-k không chứa thông tin để trả lời, hệ thống phải trả lời rõ "Không có trong tài liệu", tuyệt đối không tự suy đoán.

## Bài 2 — Đo chất lượng retrieval trên tập kiểm thử cố định
- Chạy `evaluate_recall_at_k(eval_set, docs, k=3)` trong `eval_rag.py` trên cùng một tập câu hỏi chuẩn (tối thiểu 20 câu).
- So sánh ít nhất 2 kích thước chunk khác nhau trên cùng tập câu hỏi trước khi kết luận cấu hình nào tốt hơn.
- Không thay đổi đồng thời cả kích thước chunk, bộ lọc và prompt trong cùng một lần thí nghiệm.
