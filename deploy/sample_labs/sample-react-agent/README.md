# Lab mẫu 1 — ReAct Tool-Calling Agent

## Mục tiêu học tập
Học viên xây dựng một ReAct agent dùng vòng lặp Thought → Action → Observation để tra cứu trạng thái đơn hàng và kiểm tra kho bằng công cụ Python.

## Bài 1 — Viết vòng lặp ReAct có giới hạn bước
- Tạo hàm `run_react(question, max_steps=6)` trong `agent.py`.
- Mỗi lượt gọi model trả về JSON có trường `action` và `action_input` hoặc `final_answer`.
- Bắt buộc kiểm tra `max_steps` để agent không lặp vô hạn khi model gọi sai công cụ liên tục.
- Bắt lỗi `json.JSONDecodeError` và lỗi thực thi tool rồi trả thông báo lỗi ngắn gọn về `Observation` thay vì làm crash chương trình.

## Bài 2 — Ghi trace và rà lỗi theo log
- Ghi từng bước `step`, `tool_name`, `latency_ms` và `error` vào danh sách `trace` trong `agent.py`.
- Khi agent trả lời sai, học viên phải mở `trace` để xem bước nào chọn sai công cụ hoặc nhận lỗi JSON trước khi sửa prompt.
- Không sửa prompt theo cảm tính khi chưa đối chiếu `trace`.
