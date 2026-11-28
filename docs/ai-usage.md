# Khai báo dùng AI

README của nhóm có mục "Dùng AI vào việc gì" (2–3 dòng, bắt buộc). Ghi chi tiết vào bảng dưới đây.

> Luật của đề: dùng AI để làm bài thoải mái, nhưng **ai không giải thích được phần có tên mình thì phần đó nhận 0 điểm**. Khai thiếu không bị trừ; giấu mới bị.

| Việc | Công cụ AI | AI làm gì | Người kiểm/sửa gì | Ai phụ trách |
|---|---|---|---|---|
| Code bản chạy thử | Claude | Viết khung `tools.py`, `agent.py` chạy model giả | Nhóm đọc, chạy `python run.py` kiểm | |
| Prompt / thiết kế lời gọi mô hình | | | | |
| Đào data (viết script đếm, gợi ý nhãn) | Claude | Viết `evidence/count.py` đếm trên data pre-class | Kiểm tay __ dòng, khớp __ | |
| Rà câu hỏi phỏng vấn / khảo sát | | Chỉ rà câu dẫn dắt | | |
| Viết câu thử (benchmark) | Claude | Soạn nháp 13 câu thử + metric spec | Mỗi câu thử có `source`; câu thử AI viết được ghi rõ | |
| Sinh data `synthetic` (nếu có) | | | Seed __ · kiểm tay __ dòng | |
| Chấm điểm lượt 1 | Codex | Kiểm trích dẫn bằng code, soạn lý do đạt/trượt từng câu theo danh sách lỗi nhóm đã chốt | Đội trưởng xem từng câu và chốt cột `pass`. Chưa có người thứ hai chấm lại | |
| Slide, văn bản | Claude · Gemini (Antigravity CLI) | Soạn nháp spec §4, data card, canvas; rà lại bản CP1 | Nhóm duyệt từng phần | |

CP3: Codex nối Gemini, chuẩn bị đầu vào B14–B20, chạy kiểm cấu trúc, đếm lại CSV BTC và soạn phần bằng chứng, spec, bảng chi phí. Danh sách lỗi chính do nhóm chốt trước lượt chạy.

**Không dùng AI để:** tạo người được phỏng vấn, trích dẫn, câu trả lời khảo sát; sửa kết quả các lượt đã chạy (`eval/run-*.csv`, `cost/simulate-*.csv`, `traces/`).
