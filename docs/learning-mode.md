# Chế độ "Hiểu bài đã làm" (after_lab, learning-v1)

Hợp đồng chuẩn: [design/learning-html-contract.md](design/learning-html-contract.md). Tài liệu này chỉ hướng dẫn chạy và nêu giới hạn đã biết.

## Dùng để làm gì

Học viên đã làm xong lab (thường có AI hỗ trợ) nhưng chưa giải thích được bài. Agent đọc **mọi file `.md` trực tiếp ở cấp gốc** của repo bài làm (không đọc thư mục con, code, CSV, ảnh; không mở link, không chạy lệnh), rồi dựng **một file HTML tự chứa** mở offline gồm bảy mục cố định:

1. Bài của tôi giải quyết gì? · 2. Toàn cảnh workflow · 3. Hiểu từng bước · 4. Quyết định quan trọng · 5. Kết quả, bằng chứng và rubric · 6. Thử giải thích lại · 7. Luyện thuyết trình.

Mỗi ý có nguồn `FILE.md:dòng` mở tại chỗ. Đề yêu cầu, ví dụ giảng viên, bài làm tự báo cáo, bản ghi dán chưa xác minh, nguồn chưa đọc, phần thiếu và mâu thuẫn được gắn nhãn riêng; số giả lập giữ nhãn `simulated`. Không có trạng thái "đã xác minh": chỉ đọc Markdown thì không xác minh được code hay kết quả chạy. Mọi trang là **bản nháp chờ người duyệt**, không phải điểm chính thức.

Tương tác MVP: `trace_flow` (theo dấu một dữ liệu/request qua workflow), `choose_explain` (chọn + viết lý do trước khi xem phản hồi riêng cho từng lựa chọn), `teach_back` (tự trả lời, mở checklist tự đối chiếu; không chấm tự luận). Câu chọn thiếu căn cứ hoặc bị mâu thuẫn chưa giải quyết tác động được tự hạ thành câu thảo luận.

## Chạy

**Dòng lệnh** — `python run.py`, rồi gõ đúng một dòng:

```text
@learning-v1 {"repo_path":"C:/duong/dan/toi/repo-bai-lab"}
```

Đường dẫn tương đối tính từ `LABS_DIR` (mặc định thư mục repo này), giống luồng cũ. Kết quả in tóm tắt trạng thái và dòng `Trang học lại: output/learning-<snapshot12>-<gen8>.html`. Gõ đường dẫn thường (không prefix) vẫn chạy luồng CP2 "Chuẩn bị lab" như trước. JSON sai/thừa khóa trả lỗi rõ, không rơi sang luồng cũ.

**Web** — `python codebase/web_server.py --port 8795`, mở `http://127.0.0.1:8795`. Mỗi form (lab mẫu, link GitHub gốc repo, ZIP/thư mục) có lựa chọn **"Chuẩn bị lab"** (mặc định, luồng cũ) hoặc **"Hiểu bài đã làm"**. Ở chế độ mới, trình duyệt và server cùng giữ mọi `.md` cấp gốc (kể cả `MISSION_ANSWERS.md`, `INSTRUCTOR_GUIDE.md`); link GitHub `/tree/...` bị từ chối. Trang kết quả có "Mở trang học lại" (xem nguyên bản, không qua lớp CSS/nav cũ, kèm CSP chặn mạng) và "Tải HTML" (tải đúng byte của file). Job đang chờ có nút hủy.

**Model**: dùng `call_model` hiện có (`.env`: `MODEL_PROVIDER`, `MODEL_NAME`, key). `MODEL_PROVIDER=fake` cho trang **minh họa** có biểu ngữ "CHẾ ĐỘ GIẢ", luôn ở trạng thái chưa đủ — không dùng làm bằng chứng.

## Trạng thái trang

- `blocked`: không có Markdown đọc được hoặc lỗi cấu trúc — chỉ trang giải thích.
- `incomplete`: chưa phân tích đủ dòng/file, hết ngân sách, model giả, thiếu mục tiêu học có nguồn, hoặc mâu thuẫn chưa giải quyết chạm mục tiêu học chính — phần hợp lệ vẫn xem được, có nhãn bản nháp.
- `draft_ready`: đã phân tích đủ, invariant đạt — **sẵn sàng để người duyệt xem**, không có nghĩa bài đã xong hay người học đã hiểu.

## Giới hạn kỹ thuật (cấu hình MVP, không phải số đo)

2 MiB Markdown/tổng, 512 KiB/file, 16.000 ký tự/đoạn gửi model, 80 lời gọi model/job (kể cả sửa và thử lại JSON), tối đa 2 vòng sửa toàn job, 20 phút/job, 4 lời gọi trích xuất song song. Mỗi lời gọi trích xuất/tổng hợp được thử lại tối đa 1 lần khi JSON lỗi hoặc HTTP lỗi (tính vào 80 lời gọi). Vượt giới hạn → ghi issue và trạng thái `incomplete`, không cắt im lặng. Token lấy từ `usageMetadata` của API qua `@model_call`.

## Kiểm tra

```text
python -m unittest discover -s tests/learning -t .        # bộ kiểm riêng của chế độ mới (model giả/kịch bản)
python scripts/check_learning.py parity <repo> [<repo>…]  # local / ZIP / folder cho cùng manifest + hash
python scripts/check_learning.py html output/learning-….html --repo <repo>   # kiểm tĩnh, offline, không lộ PII
python scripts/check_learning.py browser output/learning-….html --shots <dir> # Chrome headless: lỗi JS, request mạng, thao tác
python run.py check                                       # chuẩn CP2 không đổi
```

## Che dữ liệu nhạy cảm

Trước khi dữ liệu vào model, trace hay HTML: che key/token/mật khẩu trong URL, email, MSSV, số điện thoại, URL GitHub tài khoản và URL deploy cá nhân, giá trị sau nhãn "Họ tên/MSSV/Email…", ô bảng thuộc cột định danh (Họ tên, MSSV, Email, GitHub…), và các tên/tài khoản suy ra từ đó ở mọi chỗ khác. Số dòng giữ nguyên; trích dẫn chạm vùng che không được dùng làm bằng chứng. Tên trang lấy từ tiêu đề `#` của README đã che, không lấy tên thư mục. **Giới hạn**: tên người chỉ xuất hiện đơn lẻ (ví dụ chỉ tên gọi) mà không có ở bảng/nhãn định danh thì có thể không bị che; người duyệt cần xem trước khi chia sẻ.

## Chưa làm / ngoài MVP

Xếp phụ thuộc (`order_dependencies`) hiển thị tĩnh; mô phỏng số/slider; chọn thư mục con GitHub; giải quyết mâu thuẫn bởi người; cache; hosting công khai. Hiệu quả học **chưa được kiểm chứng với người học** — xem [design/learning-validation-plan.md](design/learning-validation-plan.md).
