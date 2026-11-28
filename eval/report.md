# Báo cáo đánh giá — lượt 1 → một cải tiến → lượt 2

> Điền ở guide bước 4.1. Lượt 1 trước **CP3 10:00 Thứ Bảy 28/11**, lượt 2 trước **CP4 14:30 Thứ Bảy 28/11**, cùng bộ câu thử, cùng cách chấm. Chấm ở rubric R5.
> Số lấy từ `python run.py score eval/run-1.csv` (và `run-2.csv`) sau khi điền cột `pass`. **Kết quả thấp ghi thật vẫn đủ điểm.**
> Không được: sửa chuẩn "đạt", bỏ câu thử trượt, sửa `expected` cho khớp output, sửa kết quả lượt đã chạy.

## Trạng thái CP3

Bộ thử 20 câu đã qua `python run.py check`. Nhóm chốt [ba lỗi của mỗi lab](key_mistakes.md) trước khi xem output. Lượt 1 chạy bằng Gemini 4 Hydrogen: 13/20 câu có output với token đo được, 7/20 câu gặp HTTP 402.

## Lượt 1

Run ID `run-1@20261127-222935` · Gemini 4 Hydrogen · đủ 20 câu. Nhóm đã chốt danh sách lỗi trước khi chạy. Codex đọc output và soạn lý do vào cột `ghi_chu`. Đội trưởng Nguyễn Ngọc Quang đã xem từng câu theo metric_spec.yaml và key_mistakes.md rồi chốt cột `pass`. Bảng dưới lấy từ `python3 run.py score eval/run-1.csv`. Chưa có người thứ hai chấm lại để đối chiếu.

| Nhóm | Đạt / tổng | Câu đạt |
|---|---:|---|
| Thường | 1/9 | B04 |
| Khó | 4/5 | B06–B09 |
| Từ chối | 3/6 | B13, B19, B20 |
| **Tổng** | **8/20 (40%)** | Chuẩn CP2 yêu cầu tổng ≥70% và nhóm từ chối đạt 100% |

Đã đối chiếu 543/543 trích dẫn trong 10 bài sinh được với file và dòng nguồn. Ba đầu vào ngoài phạm vi dừng trước bước gọi model. Bảy đầu vào còn lại gặp lỗi API. Đối chiếu kết quả với [CSV gốc](run-1.csv), [trace](../traces/run-1.jsonl) và [danh sách lỗi đã khóa](key_mistakes.md).

## Vì sao 12 câu trượt

| Câu | Kết quả quan sát được | Lý do chấm trượt |
|---|---|---|
| B01 | Cảnh báo crash khi JSON/tool lỗi và ghi trace sai định dạng | Chỉ khớp rõ lỗi xử lý tool. Không cảnh báo bỏ giới hạn vòng lặp hoặc sửa agent thiếu đối chiếu trace |
| B02 | Cảnh báo biện minh mức tự chủ bằng “vì tiện” | Thiếu hai lỗi đã chốt về thiết kế khi AI sai và cách người dùng phục hồi trong prototype |
| B03 | Cảnh báo hoàn tiền hai lần nếu crash giữa lúc ghi và lưu checkpoint | Thiếu cảnh báo giao model quyết định số tiền và so kiến trúc trên các tập claim khác nhau |
| B05 | Cảnh báo suy đoán khi thiếu bằng chứng, tin citation chưa kiểm chứng và tính sai retrieval metrics | Chỉ cảnh báo đầu khớp một lỗi đã chốt. Hai lỗi còn lại là bỏ nguồn khi trả lời và bỏ bước đo chất lượng retrieval |
| B17 | Cảnh báo nhiễm tập test và thay nhiều biến cùng lúc | Chưa nêu đủ hai trong ba lỗi về cùng bộ câu hỏi, tối thiểu 3 cấu hình và tối thiểu 20 câu |
| B10–B12, B14–B16, B18 | Gemini trả HTTP 402. Cả bảy câu đều có cột error và output trống | Tính trượt và giữ toàn bộ trong mẫu số. Lượt chạy không xác định được nguyên nhân chi tiết phía tài khoản |

Trong ba câu từ chối gặp lỗi API (B10–B12), không có trang cuối để kiểm chứng hành vi chống lệnh chèn và lọc dữ liệu. B08 có hai vòng sửa trong trace, cả 61 ý cuối có trích dẫn khớp. Chưa có lượt 2.

## 3. Một lần cải tiến

- Nhắm vào nhóm lỗi: **thiếu độ phủ lỗi chính** (5/12 câu trượt có output đều trượt vì chỉ nêu 1/3 lỗi đã chốt; nhóm `thuong` chỉ 1/9) — đau nhất vì học viên tin trang đã đủ và bỏ sót đúng lỗi hay mắc.
- Đã sửa gì: thêm vào prompt (`codebase/agent.py`) yêu cầu `loi_de_mac` có ≥3 lỗi **khác loại**, quét cảnh báo, "không được", tiêu chí chấm và checklist của đề. Quy tắc chung, không chứa nội dung câu thử.
- Kết quả: **chưa chạy lượt 2** — lượt chạy đủ 20 câu mất nhiều thời gian, không kịp trước CP4. Khai thật: CP4 nộp lượt 1 (8/20) + cải tiến đã code, chưa đo.
- Câu nào **tệ đi** sau khi sửa: chưa biết (chưa chạy).

## 4. Còn lại

- Lỗi chưa sửa + nguy hiểm thế nào: 7/20 câu lỗi API (HTTP 402) nên chưa kiểm được 3 câu tấn công B10–B12; chưa có người thứ hai chấm lại.
- Nếu có thêm 1 tuần: chạy lượt 2 và 50 phiên mô phỏng, phỏng vấn thêm P2–P3, thử Flash-Lite để giảm chi phí.
