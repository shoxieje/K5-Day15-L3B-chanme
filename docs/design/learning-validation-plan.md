# Kế hoạch kiểm chứng HTML học lại

Trạng thái: rubric và protocol đề xuất trước triển khai/thử người dùng; chưa có người thử, điểm, số cải thiện hay HTML runtime mới. Đây là bộ đánh giá riêng cho mục tiêu sau bài lab; không thay spec §7, metric hoặc benchmark CP2.

## 1. Hai cửa kiểm độc lập

- **Kỹ thuật/nội dung:** kiểm manifest, nguồn, kiểu dữ liệu, mode, tương tác, HTML offline theo §7 [hợp đồng](learning-html-contract.md). Tất cả ca bắt buộc phải qua; lỗi bịa nguồn/bài làm, mất Markdown, nâng transcript thành verified hoặc chạy script nguồn chặn phát hành bản dùng thử.
- **Hiểu bài:** phải có người thật tự giải thích. Agent hoàn thành code/test không được tự ghi người học đã hiểu. Mời 4 người ngoài nhóm triển khai (2 Day13, 2 Day14) để thử thăm dò nếu tuyển được; số 4 là lựa chọn thiết kế, không phải mẫu đủ để suy ra hiệu quả cả lớp.

## 2. Rubric hiểu bài, mỗi tiêu chí 0–2

| Tiêu chí | 0 | 1 | 2 |
|---|---|---|---|
| Mục tiêu/đầu ra | Nêu sai hoặc không nêu | Đúng mục tiêu chung nhưng thiếu đầu vào/đầu ra | Nêu đúng bài toán, đầu vào và kết quả cần quyết định |
| Workflow/nhân quả | Không mô tả được hoặc đảo phụ thuộc chính | Nêu bước đúng nhưng lý do/quan hệ còn thiếu | Giải thích được phụ thuộc và hệ quả khi một bước thay đổi |
| Quyết định/đánh đổi | Lặp đáp án không có lý do | Có lý do nhưng bỏ sót điều kiện hoặc phương án khác | So sánh lựa chọn bằng căn cứ và điều kiện áp dụng |
| Bằng chứng | Bịa hoặc nhận yêu cầu/mẫu là thành tích | Nêu nguồn nhưng chưa phân biệt mức xác minh | Nối claim với nguồn, nói rõ tự báo cáo/giả lập/chưa đọc |
| Giới hạn/biến thể | Không nhận ra giới hạn, không xử lý được biến thể | Nhận ra một phần nhưng lý giải còn yếu | Nêu giới hạn và trả lời biến thể với điều kiện, biết khi nào chưa đủ dữ liệu |

Tổng tối đa 10. Điểm là nhận xét của người chấm, không do HTML tự cấp. Chuẩn thăm dò đề xuất: sau học đạt ít nhất 8/10, không tiêu chí nào 0, không nhận nhầm bằng chứng thành verified. Người đã đạt ≥8 trước học cần giữ mức này và giải quyết biến thể mới, không ép phải tăng thêm hai điểm.

## 3. Protocol trước/sau

1. Ghi repo/snapshot, bài nào, nguồn bài làm có sẵn, mức từng dùng AI bằng câu hỏi tự báo cáo; dùng mã người thử, không ghi tên/MSSV trong repo.
2. Trước học: trình bày khoảng 3 phút không dùng HTML, trả lời một câu biến thể. Người chấm có rubric và nguồn gốc, không sửa câu trả lời cho người học.
3. Cho dùng HTML khoảng 10–15 phút. Ghi điểm do dự, phần phải mở gợi ý và lỗi hiểu sai. Các thời lượng là thiết kế thử, không phải thời lượng đã đo.
4. Sau học: đóng HTML, trình bày lại và trả lời một biến thể khác độ khó tương đương. Không dùng nguyên câu/đáp án trong HTML làm post-test.
5. Người chấm đối chiếu cùng rubric; nếu có người thứ hai, chấm độc lập ít nhất một bài mỗi Day trước khi trao đổi bất đồng. Không ghi đã chấm độc lập nếu chưa thực hiện.
6. Có thể kiểm lại sau 1–2 ngày với một biến thể khác để đánh giá khả năng nhớ lâu. Ghi rõ nếu chưa có follow-up.

Chuẩn bị cặp đề A/B và checklist từ nguồn trước phiên thử; đảo A/B cho người thử cùng Day nếu đủ người. Đề transfer giữ riêng khỏi nội dung HTML. Day13 hỏi thay điều kiện chi phí/pilot và cách đổi đề xuất; Day14 hỏi thay lỗi vận hành/điều kiện tải và nguồn cần kiểm. Đáp án mở cho phép nhiều lựa chọn có lý do.

## 4. Quyết định sau pilot

- Nếu 3/4 người đạt ngưỡng sau học, không có hiểu sai nghiêm trọng do HTML gây ra, tiếp tục thử trên mẫu lớn hơn; chỉ gọi là tín hiệu thăm dò.
- Người dưới ngưỡng trước học cần ghi riêng delta; mục tiêu thiết kế là tăng ít nhất 2 điểm, không dùng điểm trung bình để che người hiểu sai bằng chứng.
- Nếu dưới 3 người đạt hoặc HTML gây nhận nhầm số giả lập/thành tích/luồng hệ thống, sửa nội dung hoặc tương tác liên quan rồi thử lại với đề tương đương.
- Không đủ 4 người thì báo n thực, điểm từng tiêu chí và giới hạn; không dùng tỷ lệ mục tiêu như số đã đo. Không tuyển được người thì trạng thái “chưa kiểm chứng hiệu quả học” dù kỹ thuật đã đạt.

Các ngưỡng trên là quyết định thiết kế pilot, có thể được nhóm/TA điều chỉnh trước lượt đầu; khóa version và lý do trước khi xem kết quả. Sau chạy không đổi chuẩn để hợp thức số. Mục tiêu cuối là năng lực giải thích, không phải số lần bấm, điểm game hoặc mức tự tin tự báo cáo.

## 5. Artifact kết quả khi có triển khai

Lưu bộ ca mới và log kiểm kỹ thuật ở đường dẫn riêng, ví dụ `validation/learning-v1/`, có run ID/snapshot/template/model/prompt version. Log người dùng ẩn danh gồm pre/post từng tiêu chí, câu biến thể ID, nhận xét và hành vi quan sát; ghi thiếu dữ liệu bằng null cùng lý do, không điền 0 giả. Mọi gợi ý chấm của agent là bản nháp chờ TA. Báo cáo phân biệt đề xuất, đo được, suy luận và việc chưa làm.
