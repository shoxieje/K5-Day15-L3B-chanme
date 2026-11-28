# Kiến trúc học lại chung từ Day13 và Day14

Ngày 28/11/2026. Căn cứ: [nghiên cứu Day13](day13-root-md.md), [nghiên cứu Day14](day14-root-md.md), tổng 21 Markdown/6.451 dòng tại hai snapshot ghi trong manifest. Hai nghiên cứu do các agent trong phiên Codex thực hiện; chưa có lượt nghiên cứu chạy bằng Claude. Tài liệu này là bản bàn giao để Claude hoặc lập trình viên tiếp tục triển khai, không gán kết quả cho một model chưa dùng.

## 1. Quyết định sản phẩm

Giữ bảy mục HTML cố định và các component được code dựng. Đơn vị nội dung chung là **mục tiêu → yêu cầu → workflow → quyết định → bài làm tự báo cáo → bằng chứng/giới hạn → tự giải thích**. Dữ liệu quyết định nhãn bước, quan hệ, loại tương tác và câu hỏi; không tạo template riêng bằng prompt cho mỗi Day.

Học viên có thể bắt đầu từ một repo “đã làm”, nhưng HTML phải cho phép bài mới hoàn thành một phần. Day13 ghi thiếu nhãn người 2 và duyệt chéo (`TEAM.md:115,130`); Day14 có transcript và bảng số nhưng artifact nguồn nằm ngoài root (`SUBMISSION.md:24-44`). Không dùng một cờ “xong” cho cả repo.

## 2. Cấu trúc chung có căn cứ ở cả hai bài

Mọi file:dòng ở cột Day thuộc repo tương ứng, không phải repo Day15.

| Cấu trúc cần biểu diễn | Day13 | Day14 | Quyết định kiến trúc |
|---|---|---|---|
| Nghĩa vụ tự giải thích | RULES.md:7-8: giải thích chi phí, cỡ mẫu và đề xuất | RULES.md:5-8: giải thích code/con số và khai AI log | Teach-back + dàn thuyết trình gắn bằng chứng; không chỉ đưa đáp án |
| Yêu cầu so với bài làm | CHECKPOINTS.md:7-45 và TEAM.md:64-135 | CHECKPOINTS.md:34-131 và ba báo cáo bài làm | Requirement, claim, evidence tách nhau và liên kết ID |
| Quan hệ giữa các bước | A1 trước bước tiếp, B dùng A; B/C có thể song song (README.md:54-56; CHECKPOINTS.md:18,26) | Thứ tự K5 khác số Part; request flow là luồng khác (CHECKPOINTS.md:12-23; CODE_LAB.md:745-791) | Nhiều graph có loại, dependency và feedback riêng |
| Quyết định cần lý giải | Phạm vi, retry, pilot, Go/No-go (RUBRIC.md:12-14,27-29) | Auth/rate/budget, state, scale, quality gate (CHECKPOINTS.md:52-71,102-112) | Quyết định đóng dùng lựa chọn; quyết định mở dùng checklist lập luận |
| Số liệu cần giữ ngữ cảnh | Dữ liệu giả lập và số TEAM tự báo cáo (README.md:3; RULES.md:18; TEAM.md:71,93) | Kết quả tự báo cáo khác image/phương pháp và threshold (MISSION_ANSWERS.md:94-113,387; BENCHMARK_REPORT.md:17,66,119) | Origin độc lập mức xác minh; measurement gắn artifact/method/scope/unit/operator |
| Bằng chứng chưa đọc | Báo cáo, CSV/code ở thư mục con (SUBMISSION.md:38-57) | JSON/CSV/code/ảnh (SUBMISSION.md:24-44) | Chỉ hiện tham chiếu chưa đọc; không tự mở rộng nguồn |
| Quy tắc theo phạm vi | Bonus chung có ngoại lệ không dùng (RUBRIC.md:19,23) | K5 override từng phần (README.md:15-31; RUBRIC.md:3,24) | Override theo cặp quy tắc và nguồn, giữ bản cũ để tra |
| Mâu thuẫn chưa giải quyết | Review 100% vs ngưỡng dừng do TEAM tự báo cáo (TEAM.md:108) | Image size, gate 80/85, toán tử biên (nghiên cứu Day14 §5 C7/C8/C11) | Hiện conflict; không lấy một bên làm đáp án duy nhất |

## 3. Nội dung bảy mục HTML

| Mục | Day13 | Day14 |
|---|---|---|
| Bài giải quyết gì | Pilot trợ lý hoàn phí có đáng thử và ra quyết định được không | Đưa agent từ local tới dịch vụ và đo chất lượng/vận hành |
| Toàn cảnh workflow | Nhánh chi phí, lỗi, pilot cùng hội tụ hồ sơ Gate 2a | Lộ trình học K5; graph request Part6; graph benchmark riêng |
| Hiểu từng bước | Tử số/mẫu số, nhãn độc lập, cỡ mẫu và luật dừng | Đóng gói, auth/rate/budget, state, probe và đo |
| Quyết định | Đánh đổi phạm vi/retry/review và Go/No-go có lý do | Chọn cơ chế vận hành và tín hiệu đo phù hợp |
| Bài làm và bằng chứng | Kết quả TEAM tự báo cáo, nhãn simulated, mục còn thiếu | Transcript/report chưa kiểm chứng, ngữ cảnh số và conflict |
| Tự giải thích | Giải thích chi phí, pilot, số bất lợi và hạn chế | Giải thích một request, readiness, scale/quality |
| Luyện trình bày | Đề xuất → bằng chứng thuận/bất lợi → điều kiện pilot | Kiến trúc → quyết định → số báo cáo → giới hạn xác minh |

Mục bài làm có nhãn động: “Bài làm được tài liệu ghi nhận” khi có claim tự báo cáo; “Yêu cầu — chưa có nội dung bài làm” khi không có. Mọi card nhắc số kế thừa nhãn giả lập/tự báo cáo và nguồn. Không viết thay câu “tôi đã xác minh” nếu chỉ có transcript.

## 4. Tương tác MVP được chọn

Các lựa chọn sau là giả thuyết thiết kế cần thử với người học, không phải kết luận về hiệu quả.

- **Theo dấu workflow (`trace_flow`)**: Day13 theo một yêu cầu giả lập đi qua chi phí thành công/thất bại, giải thích vì sao mẫu số khác số lần gọi. Day14 theo một request qua key/rate/budget và nhánh bị từ chối. Dữ liệu ví dụ tự dựng có nhãn giả định; không giả đã replay code.
- **Chọn và giải thích (`choose_explain`)**: chỉ dùng câu có căn cứ cho tập đáp án. Day13 phân biệt yêu cầu, tự báo cáo và bằng chứng chưa đọc; Day14 chọn tín hiệu health/readiness hoặc chất lượng/vận hành. Hỏi lý do trước rồi mở feedback riêng.
- **Tự giảng (`teach_back`)**: Day13 bảo vệ Go/Go có điều kiện/No-go bằng số thuận/bất lợi; cả ba có thể hợp lý. Day14 giải thích vì sao ba instance không mặc nhiên nhanh gấp ba. Không tự chấm lời tự luận.

Xếp phụ thuộc, builder luật dừng, metrics–trace–log, chart/sliders định lượng là backlog sau MVP. Không cần làm cả bảy tương tác Day14 hoặc mọi gợi ý Day13 ngay. Chưa đủ công thức và nguồn đo thì không xây mô phỏng số; bảng số tự báo cáo có thể hiện để tự đối chiếu cùng ngữ cảnh.

## 5. Các trường hợp giới hạn và xử lý

1. **Chỉ có đề:** dựng phần hiểu yêu cầu và câu hỏi học, ghi thiếu bài làm ở từng mục. Học viên có thể tự bổ sung một Markdown tổng hợp ở gốc rồi sinh lại snapshot mới; agent không tự tạo bằng chứng thay họ.
2. **Bài làm tự báo cáo thiếu:** giữ nội dung có nguồn và trạng thái từng requirement. Không chặn đọc phần đã có, cũng không vẽ toàn bộ workflow thành hoàn tất.
3. **Nhiều phiên bản tài liệu:** giải override từng cặp bằng nguồn tường minh. Không đủ căn cứ thì giữ hai nguồn và hạ câu hỏi xuống thảo luận.
4. **Nhiều hệ thống trong một lab:** dùng context và graph riêng. Part6 agent deploy không mặc nhiên là service benchmark; không suy metrics của một service chứng minh service còn lại.
5. **Tài liệu dài:** đọc và phân tích từng chunk có coverage, giới hạn budget minh bạch; incomplete khác draft_ready.
6. **Nhiều phương án hợp lý:** đánh giá lập luận bằng checklist, không tối ưu trò chơi thành chọn phương án giống bài đã nộp.

Không hứa kiến trúc này phù hợp mọi lab sau hai ví dụ. Lab thiếu rubric, thiếu bài làm, chủ yếu hình ảnh hoặc yêu cầu thực hành không thể diễn đạt bằng Markdown là ca mở rộng cần nghiên cứu thêm.

## 6. Bàn giao triển khai

Hợp đồng chi tiết và các quyết định đã chốt nằm trong [learning-html-contract.md](../design/learning-html-contract.md). Hợp đồng này là nguồn chuẩn cho field/enum và cách tích hợp, thay cho tên component ý tưởng trong từng báo cáo nghiên cứu. Không dùng danh sách ý tưởng ở nghiên cứu như yêu cầu làm hết MVP.

Thứ tự: reader/manifest → extraction/validation → renderer → dispatch agent → ingestion/web/download → kiểm kỹ thuật trên hai snapshot → thử với người học. Hai HTML offline là tiêu chí nghiệm thu của giai đoạn triển khai, chưa là artifact đã tạo ở giai đoạn hoàn thiện kế hoạch.

Tài liệu đánh giá mục tiêu mới: [learning-validation-plan.md](../design/learning-validation-plan.md). Review: [learning-plan-review.md](../reviews/learning-plan-review.md). Không dùng chuẩn mới sửa số CP2/CP3.
