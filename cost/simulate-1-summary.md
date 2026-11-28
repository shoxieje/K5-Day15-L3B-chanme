# Tóm tắt mô phỏng simulate-1@20261128-145421

Do `python run.py simulate` sinh ra — không sửa tay. Chép bảng sang `cost/cost-estimate.md`.

| Persona | Số phiên mô phỏng | Lượt hỏi / phiên | Token vào / phiên | Token ra / phiên | Gọi model / phiên | Gọi công cụ / phiên |
|---|---:|---:|---:|---:|---:|---:|
| dung_it | 22 | 1 | 121218 | 5832 | 3.0 | 4.0 |
| dung_vua | 16 | 1 | 119168 | 7200 | 3.0 | 4.0 |
| dung_nhieu | 12 | 1 | 103720 | 7550 | 2.9 | 3.9 |

Tỉ lệ đạt dùng để tính: 9/20 (45%) — lượt run-2@20261128-145421

- Tự chọn: lượt run-N mới nhất đã chấm xong, chạy bằng đúng model đang đo (run-2.csv). Muốn dùng lượt khác (vd lượt 2): thêm `--rate-from eval/run-2.csv`.

| Model (giá) | Chi phí / phiên | Chi phí / task thành công | Chi phí / câu hỏi đạt | Chi phí / tháng — thấp (300 người) | Chi phí / tháng — cơ sở (700 người) | Chi phí / tháng — cao (1.000 người) | Chi phí / người / tháng (cơ sở) |
|---|---:|---:|---:|---:|---:|---:|---:|
| gemini-3.1-flash-lite (vào 0.25 · ra 1.5 $/1M) | $0.0391 | $0.0869 | $0.0869 | $104.67 | $244.23 | $348.90 | $0.3489 |
| gemini-3.8-flash (vào 1.5 · ra 7.5 $/1M) | $0.2247 | $0.4992 | $0.4992 | $599.46 | $1,398.74 | $1,998.21 | $2.00 |
| gemini-4-hydrogen (vào 1.5 · ra 7.5 $/1M) | $0.2247 | $0.4992 | $0.4992 | $599.46 | $1,398.74 | $1,998.21 | $2.00 |

- Chi phí / task thành công = chi phí / phiên ÷ tỉ lệ đạt. Chi phí / câu hỏi đạt = chi phí / phiên ÷ số lượt hỏi trung bình mỗi phiên (1.0) ÷ tỉ lệ đạt — tỉ lệ đạt đo theo từng câu thử.
- Token đo trên model: gemini-3.1-flash-lite. Giá tính theo từng model trong bảng — model khác bộ tách token thì số token thật có thể lệch; ghi rõ "đo trên model X, tính giá model Y" trong cost/cost-estimate.md.
- Phiên lỗi (không tính vào trung bình): 0/50.
