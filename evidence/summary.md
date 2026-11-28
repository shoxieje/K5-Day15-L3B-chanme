# Tổng hợp bằng chứng pain

> Bằng chứng học viên bỏ qua bước thực hành. Ngưỡng đặt trước trong [hypothesis.md](hypothesis.md).

## 1. Nguồn đã dùng

| Nguồn | Đạt ngưỡng? | File |
|---|---|---|
| Đào data (x/N, %, cách đếm chạy lại được, ≥5 ví dụ) | ☑ Đạt | [`evidence/data-mining.md`](data-mining.md) · script [`evidence/count.py`](count.py) |
| Phỏng vấn (≥3 người ngoài nhóm, đúng người dùng) | ☐ Chưa (1/3 người) | [`evidence/interviews/P1.md`](interviews/P1.md) |
| Khảo sát (≥20 người ngoài nhóm, đúng người dùng) | ☐ Chưa có kết quả | `evidence/survey/` |

## 2. Số chính

- **Đào data** (pre-class 05–25/11, đếm mỗi cặp học viên × mini lab một lần, lấy lần hoàn tất cuối):
  - **99/442 lần hoàn tất mini lab (22%)** được ghi là bỏ qua. Ngưỡng ≥20%: **đạt**.
  - 61/147 học viên mở mini lab (41%) bỏ qua ít nhất một bài.
  - **18/113 học viên làm bước thực hành (16%)** từng có bước tự giải thích. Ngưỡng <1/3: **đạt**.
- **Phỏng vấn:** 1/3 người *(n nhỏ, không ghi %)*. Chưa có số lần/tháng và thời gian mỗi lần.
- **Khảo sát:** chưa có (n = 0).

| | Vai | Gặp pain? | Số lần / 1 tháng qua | Lần gần nhất mất | Đang xoay xở bằng |
|---|---|---|---|---|---|
| P1 | Học viên L3B ngoài nhóm | Có | Chưa hỏi | Chưa hỏi | Để công cụ viết hộ code |
| P2 | — | — | — | — | — |
| P3 | — | — | — | — | — |

## 3. ≥5 ví dụ nguyên văn (có nguồn, bỏ tên)

Trường `data` trích nguyên văn từ `data/preclass/events.csv`. Đã bỏ cột mã học viên.

1. `{"lab_key": "d01-lab-ban-la-llm", "skipped": true, "steps": 2, "steps_done": 1}` — events.csv dòng 1066
2. `{"lab_key": "d02-lab-cham-gate", "skipped": true, "steps": 3, "steps_done": 2}` — events.csv dòng 1869
3. `{"lab_key": "d04-lab-soi-system-prompt", "skipped": true, "steps": 3, "steps_done": 2}` — events.csv dòng 4079
4. `{"lab_key": "d03-lab-can-agentic-fit", "skipped": true, "steps": 1, "steps_done": 0}` — events.csv dòng 22282
5. `{"lab_key": "d05-lab-eval-spec", "skipped": true, "steps": 1, "steps_done": 0}` — events.csv dòng 34194

Thêm (diễn đạt lại, không phải nguyên văn): P1 cho biết đã để công cụ viết hộ vì dễ hơn. Xem [P1](interviews/P1.md).

## 4. Các nguồn có khớp nhau không

**Data nói:** 22% lần làm mini lab bị bỏ qua, và chỉ 16% học viên thực hành có tự giải thích. **Người dùng nói (P1):** bỏ qua phần tự làm, để công cụ viết hộ vì dễ hơn.

**Khớp về hành vi:** cả hai đều cho thấy học viên bỏ qua phần tự làm/tự giải thích. **Chưa kiểm được lý do:** data không cho biết vì sao (thiếu giờ, đề khó đọc hay muốn bỏ qua phần hiểu). Một phỏng vấn chưa đủ để chọn giữa các cách giải thích trong hypothesis.md.

## 5. Kết luận

- **Giả thuyết: đúng một phần.** Phần hành vi (bỏ qua bước thực hành, ít tự giải thích) được data xác nhận, vượt cả hai ngưỡng đặt trước. Phần nguyên nhân ("không biết trước bài gồm bước nào và lỗi nào hay gặp") chưa được kiểm chứng.
- **Chưa biết:** lý do bỏ qua, và học viên có giải thích được lỗi ở bài lab chính hay không (data chỉ có ở trang pre-class). Cần thêm P2–P3 (hỏi số lần/tháng và thời gian), cùng khảo sát ≥20 người.
- **Giới hạn trung thực:** cách đếm được viết cùng lúc với lần chạy. Chỉ có ngưỡng là viết trước (xem [data-mining.md](data-mining.md)).
