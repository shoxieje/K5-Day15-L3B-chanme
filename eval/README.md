# Hồ sơ đánh giá — một trang

> Điền ở guide bước 2.4 (mục 1–4, trước CP2) và 4.1 (mục 5–6, trước CP4). Ôn lại: ngày 9, ngày 14 · lab ngày 9. Chấm ở rubric R4, R5.
> Người ngoài nhóm đọc trang này phải hiểu được: nhóm đo cái gì, bằng gì, ra số nào. Trang slide "Đánh giá thế nào" lấy từ đây.

## 1. Dataset → xử lý

Dùng đề gốc trong thư mục labs/ và các biến thể được mô tả ở [data card](../data/DATA_CARD.md). Bộ đọc bỏ file bị loại trước khi gửi nội dung cho Gemini.

## 2. Bộ câu thử

20 câu gồm 9 thường, 5 khó, 6 từ chối. Có 12 câu từ dữ liệu thật và 8 câu tự viết. B10–B12 là câu tấn công: lệnh chèn trong README, key giả trong .env và file bài làm của học viên. B05–B09 kiểm giới hạn đọc, căn cứ thiếu và vòng sửa. B13, B19 và B20 kiểm các dạng đầu vào ngoài phạm vi.

## 3. Metric và cách chấm

Kiểm mọi nguồn và trích dẫn trên dòng gốc. Thành viên nhóm duyệt ba lỗi chính của mỗi lab trước khi xem output, sau đó so độ phủ theo danh sách đã chốt. Kiểm rò rỉ trên cả output chữ và HTML. Chuẩn đạt và ngưỡng từng metric ở [spec §7](../spec.md) và [metric spec](metric_spec.yaml). Chưa có kết quả chấm độc lập 5 output bởi người thứ hai.

## 4. Lệnh

`python run.py eval` → `eval/run-N.csv` + `traces/run-N.jsonl` · điền cột `pass` · `python run.py score eval/run-N.csv`

## 5. Đã chạy gì

| Lượt | Run ID | Model | Cấu hình (prompt / công cụ / thay đổi) | Đạt / tổng | % | Đạt chuẩn? |
|---|---|---|---|---|---|---|
| 1 | run-1@20261127-222935 | gemini-4-hydrogen | Đề lab có số dòng, kiểm nguồn, tối đa 2 vòng sửa | 8/20 | 40% | Chưa đạt |
| 2 | | | | __/__ | | |

Lượt chạy lại vì lỗi kỹ thuật, lượt sau CP4: ghi thêm dòng, không sửa dòng cũ.

## 6. Lỗi chính

7/20 câu gặp HTTP 402. Mười bài sinh được có trích dẫn khớp nhưng chưa đạt độ phủ lỗi chính. Cột `pass` do đội trưởng chấm và chốt theo metric_spec.yaml (Codex chỉ soạn lý do). Chưa có người thứ hai chấm lại. [Phân tích theo từng câu](report.md)
