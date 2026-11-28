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
- **Tỉ lệ đạt** dùng để tính: 8/20 (40%) — lượt `run-1` (**lượt 2 chưa chạy**, không kịp giờ)
- Đo token trên model gemini-4-hydrogen (10 phiên lượt thử), tính giá gemini-4-hydrogen và gemini-3.1-flash-lite

## 2. Kết quả mô phỏng

Lượt dùng: `simulate-try@20261127-222805` · **10 phiên** · seed 42. **Chưa đủ ≥50 phiên** theo yêu cầu: không kịp giờ trước CP4. Token trung bình mỗi phiên: 42.994 vào · 21.241 ra. Bảng dưới tính tay từ token đo được × giá ở trên, không phải từ `simulate-N-summary.md`.

| Model | Chi phí / phiên | Chi phí / task thành công | / tháng — thấp | / tháng — cơ sở | / tháng — cao | / người / tháng (cơ sở) |
|---|---|---|---|---|---|---|
| gemini-4-hydrogen | 0,2238 USD | 0,56 USD | 604 USD | 1.410 USD | 2.014 USD | 2,01 USD |
| gemini-3.1-flash-lite *(token đo trên Hydrogen, tự ước tính)* | 0,0426 USD | 0,11 USD | 115 USD | 268 USD | 383 USD | 0,38 USD |

Chi phí / task thành công = chi phí trung bình mỗi phiên ÷ tỉ lệ đạt — **không coi như đạt 100%**.

## 3. So với impact

- Impact / người / tháng (`spec.md` §2): ~40 phút tiết kiệm (4 buổi × 10 phút, *tự ước tính*)
- Chi phí / người / tháng (cơ sở, model gemini-4-hydrogen): 2,01 USD · Flash-Lite ~0,38 USD
- **Kết luận một dòng — đáng làm không:** chi phí thấp so với 40 phút/tháng, nhưng tỉ lệ đạt mới 40% nên **iterate**: chạy lượt 2, đo lại trên Flash-Lite trước khi mở rộng.

## 4. *(Muốn sâu hơn, không bắt buộc)*

- Bảng độ nhạy: model rẻ hơn · cache · cắt ngữ cảnh · giới hạn bước — mỗi cần gạt đổi chi phí bao nhiêu
- Chi phí ngoài model: hosting, lưu trữ, giờ công người duyệt
- Quy mô nào thì bài toán còn đáng làm
