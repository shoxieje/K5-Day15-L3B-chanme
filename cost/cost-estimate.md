# Chi phí khi dùng thật

> Điền ở guide bước 4.2, nộp ở CP4 14:30 Thứ Bảy 28/11. Ôn lại: ngày 13, ngày 1, ngày 14 · lab ngày 13, lab ngày 14. Chấm ở rubric R6.
> Số **không điền tay**: điền `cost/personas.yaml` → `python run.py simulate` → chép bảng trong `cost/simulate-N-summary.md` vào đây.
> Lúc build dùng gói miễn phí vẫn tính theo **giá gói trả phí** — đây là chi phí cho lúc đưa vào dùng thật.

## Lượt thử CP3

Mười phiên hoàn tất, seed 42, mỗi phiên chuẩn bị một bài lab. Cả 10 phiên đều gọi Gemini 4 Hydrogen thành công. Tính theo giá Hydrogen trong bảng của BTC, trung bình **0,2238 USD/phiên**. Đây là chi phí mô phỏng theo bảng giá, chưa đối chiếu hóa đơn. Lượt chính thức từ 50 phiên thuộc CP4.

Kết quả từ lượt `simulate-try@20261127-222805`, đo trên Gemini 4 Hydrogen.

| Phiên | Persona | Token vào | Token ra |
|---|---|---:|---:|
| S001 | dung_vua | 38631 | 20014 |
| S002 | dung_vua | 47778 | 16660 |
| S003 | dung_it | 15727 | 12670 |
| S004 | dung_it | 15727 | 15071 |
| S005 | dung_nhieu | 58646 | 35990 |
| S006 | dung_vua | 38631 | 15779 |
| S007 | dung_it | 47778 | 16397 |
| S008 | dung_it | 53532 | 38606 |
| S009 | dung_it | 97762 | 28779 |
| S010 | dung_vua | 15727 | 12444 |

## 1. Đầu vào

- **Persona** (`cost/personas.yaml`): dung_it 50% × 4 phiên/tháng · dung_vua 30% × 10 · dung_nhieu 20% × 20 → trung bình **9 phiên/người/tháng**. Nguồn: *(tự ước tính)*
- **Số người dùng thật** 3 kịch bản: thấp 300 · cơ sở 700 · cao 1.000. Nguồn: *(tự ước tính)*
- **Giá** (further-reading/model-prices.md, xem 25/11/2026, USD/1M token): gemini-4-hydrogen 1,50 / 7,50 · gemini-3.1-flash-lite 0,25 / 1,50
- **Tỉ lệ đạt** dùng để tính: 9/20 (45%) — lượt `run-2@20261128-145421` (lượt 2)
- Đo token trên model gemini-3.1-flash-lite (50 phiên), tính giá gemini-3.1-flash-lite, gemini-3.8-flash và gemini-4-hydrogen

## 2. Kết quả mô phỏng

Lượt mô phỏng: `cost/simulate-1.csv` · run ID `simulate-1@20261128-145421` · **50 phiên** · seed 42 · 0 phiên lỗi. Đo token trên **gemini-3.1-flash-lite**, tính giá cả ba model (bảng chép từ `cost/simulate-1-summary.md`).

| Model | Chi phí / phiên | Chi phí / task thành công | / tháng — thấp | / tháng — cơ sở | / tháng — cao | / người / tháng (cơ sở) |
|---|---|---|---|---|---|---|
| **gemini-3.1-flash-lite** (0,25 / 1,50) | 0,0391 USD | **0,0869 USD** | 104,67 USD | 244,23 USD | 348,90 USD | 0,35 USD |
| gemini-3.8-flash (1,50 / 7,50, giá từ 01/01/2027) | 0,2247 USD | 0,4992 USD | 599,46 USD | 1.398,74 USD | 1.998,21 USD | 2,00 USD |
| gemini-4-hydrogen (1,50 / 7,50) | 0,2247 USD | 0,4992 USD | 599,46 USD | 1.398,74 USD | 1.998,21 USD | 2,00 USD |

Token trung bình mỗi phiên (theo persona): ~104–121 nghìn vào, ~5,8–7,6 nghìn ra, ~3 lần gọi model, ~4 lần gọi công cụ. Dòng 3.8 Flash và Hydrogen dùng token đo trên Flash-Lite (đo trên model X, tính giá model Y). Đối chiếu: một lần chạy thật Day11 trên gemini-3.8-flash tốn 0,2452 USD, 145 giây, 62.813 / 20.131 token.

Chi phí / task thành công = chi phí trung bình mỗi phiên ÷ tỉ lệ đạt — **không coi như đạt 100%**.

## 3. So với impact

- Impact / người / tháng (`spec.md` §2): ~40 phút tiết kiệm (4 buổi × 10 phút, *tự ước tính*)
- Chi phí / người / tháng (cơ sở, model gemini-3.1-flash-lite): 0,35 USD · gemini-3.8-flash / Hydrogen: 2,00 USD
- **Kết luận một dòng — đáng làm không:** chi phí rất thấp (0,35 USD/người/tháng với Flash-Lite) so với ~40 phút tiết kiệm/tháng, nhưng tỉ lệ đạt mới 45% (thường 0/9) nên **iterate**: giữ Flash-Lite cho phần chặn/từ chối, cần prompt hoặc model mạnh hơn cho độ phủ lỗi chính.

## 4. *(Muốn sâu hơn, không bắt buộc)*

- Bảng độ nhạy: model rẻ hơn · cache · cắt ngữ cảnh · giới hạn bước — mỗi cần gạt đổi chi phí bao nhiêu
- Chi phí ngoài model: hosting, lưu trữ, giờ công người duyệt
- Quy mô nào thì bài toán còn đáng làm
