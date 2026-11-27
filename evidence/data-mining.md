# Đào data — cách đếm và kết quả

> Repo chỉ chứa số đã tổng hợp. Chạy lại: `python evidence/count.py <đường dẫn tới data/preclass của repo đề>`.

## 1. Cách đếm

> Ghi trung thực: cách đếm được định nghĩa và chạy cùng lúc, 18:00 Thứ Sáu 27/11 (không viết trước khi chạy). Ngưỡng ở `hypothesis.md` viết trước khi chạy.

- Data dùng: `data/preclass/` BTC cấp (`events.csv`, `answers.csv`), 05/11 → 25/11/2026, Day01–Day13.
- Đếm gì:
  1. Trong các lần làm xong mini lab (`events.csv`, `type = lab_completed`, mỗi cặp học viên × `lab_key` lấy một lần), bao nhiêu lần có `skipped = true`.
  2. Trong học viên đã mở ít nhất một mini lab (`lab_opened`), bao nhiêu người bỏ qua ≥1 mini lab.
  3. Trong học viên có ≥1 dòng `answers.csv` với `nguon = thuc_hanh`, bao nhiêu người có ≥1 dòng `nguon = giai_thich` (tự giải thích).
- **Mẫu số:** (1) số lần làm xong mini lab · (2) số học viên mở mini lab · (3) số học viên làm bước thực hành. Không dùng 721 tài khoản.
- Script: `evidence/count.py`.

## 2. Đọc trước, đếm sau

Đã đọc README data, `column_dictionary.csv`, `event_types.csv` và vài dòng đầu mỗi file. Các kiểu hành vi thấy được: mở bài và video · trả lời câu hỏi trước/sau video · làm mini lab (có nút bỏ qua) · tự giải thích (rất ít dòng) · nhắn trợ giảng AI.

## 3. Kết quả

| Đếm gì | x / N | % | Ghi chú |
|---|---|---|---|
| Lần làm xong mini lab bị bấm bỏ qua | 99/442 | 22% | `skipped = true`; cùng 99 lần có `steps_done < steps` |
| Học viên bỏ qua ≥1 mini lab | 61/147 | 41% | trên học viên đã mở mini lab |
| Học viên làm bước thực hành có tự giải thích ≥1 lần | 18/113 | 16% | 84% chưa từng tự giải thích |

## 4. ≥5 ví dụ cụ thể

Còn thiếu: cần chọn 5 dòng mã đã ẩn danh (mã `L…`, `A…`) làm ví dụ trước CP3.

## 5. Giới hạn của data

Data là mini lab và câu hỏi trên trang pre-class, không phải bài lab chính trên lớp; data cho biết học viên bỏ qua phần thực hành và hiếm khi tự giải thích, không cho biết **vì sao**, và không có câu chữ học viên viết nên không có trích dẫn.
→ Kiểm lại bằng khảo sát lớp L3B và phỏng vấn 5 người (lý do bỏ qua: thiếu giờ hay đề khó hiểu).
