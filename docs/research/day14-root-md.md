# Nghiên cứu Markdown cấp gốc — Day14

Ngày đọc: 28/11/2026. Phạm vi: 15/15 file `.md` trực tiếp ở cấp gốc, 6.032 dòng, đã đọc toàn bộ bằng các đoạn có số dòng. Đây là nghiên cứu tài liệu tại snapshot cục bộ, không phải kiểm chứng triển khai, chấm bài hoặc đo hiệu quả học.

Repo nguồn: thư mục `K5-L3B-DAY14-<họ-tên>-<MSSV>-Deployment-Benchmark-Observability/` trong workspace. Git HEAD quan sát được: `a62d36859de1cbf0b6c40359405f6e1148ce3459`. Hash bên dưới xác định nội dung working tree đã đọc, không giả định mọi file đều trùng HEAD. Các dẫn `FILE.md:a-b` trong tài liệu này đều tương đối với repo Day14. Không đọc `.env`, code, JSON/CSV, ảnh hoặc Markdown thư mục con; không thực thi lệnh lab, gọi URL deploy, hay mở link ngoài.

## 1. Manifest và vai trò nguồn

| File | Dòng | Vai trò quan sát từ nội dung | SHA256 |
|---|---:|---|---|
| BENCHMARK_REPORT.md | 185 | Bài làm: số tự báo cáo, phân tích, đoạn log dán, liên kết bằng chứng ngoài phạm vi | `1c10c10529a56a1cca34eb0d7d062ea479dd54a9272229b546603b0a42dfff0f` |
| CHECKPOINTS.md | 131 | Lộ trình và yêu cầu riêng K5; yêu cầu sản phẩm và điều cần hiểu | `4bb79af827ba657f7243952815f7ba9a53308196129a1c152eefb62f4a17e860` |
| CODE_LAB.md | 1129 | Tutorial, bài tập, đoạn lời giải mẫu, cấu trúc và rubric cũ | `5c1b907fff6dfdd0e66100802f00a0c15b81ef2457a9b3a2f375ee086a099abd` |
| DAY14_DELIVERY_CHECKLIST.md | 261 | Mẫu bàn giao, checklist; một số chi tiết bị K5 thay thế | `702d83bd0d2fadfd0d1e6b8a9c9cff3775dd9f54fa6bd898323ae35829893129` |
| DEPLOYMENT.md | 71 | Bài làm tự báo cáo nền tảng, response dán, tên biến cấu hình và liên kết ảnh | `60385889972b2cbeaf7db56adca070a838f571634cf1d33a66a6dbe29f684b27` |
| INSTRUCTOR_GUIDE.md | 814 | Rubric/đáp án mẫu cho giảng viên, code ví dụ chấm, feedback mẫu; có phần bị thay thế | `7c432472d5f1cddb0a35706062047278a302d39aa1051ea876e188e1d897138c` |
| LEARNING_PATH.md | 501 | Câu chuyện và sơ đồ học, ví dụ minh họa, checklist chung; không phải tiến độ thật | `3df7c0f08287af81ac8a535ebe2b1f2b59e408d35198f8f4e74762c6dbca6be8` |
| MISSION_ANSWERS.md | 475 | Bài làm Part 1–6, giải thích, transcript dán và AI log tự báo cáo | `03dc110b6b973be6d6aa1f894865b41f8be1c2be3f0e6fcb21ba99b3d0080afe` |
| QUICK_REFERENCE.md | 793 | Cheat sheet, mẫu code và lệnh; không chứng minh đã chạy | `7fc358c6b3dcc7277207327703006014aa2ecf2e7e347aac7a99c33eeef84f25` |
| QUICK_START.md | 429 | Fast track và minh họa tiến độ; một số lệnh chưa theo K5 | `713b468809bb05981c4dd440f53ee937c2f2cb241b0388a7d311e147f927a884` |
| README.md | 145 | Mục tiêu, bản đồ repo, hướng dẫn ưu tiên cho K5 | `c1f2a5585d38945570780fe82193bdbd8224ee77f69e1eb4abbbcd4779f144df` |
| RUBRIC.md | 77 | Rubric K5, tổng điểm, bảng Part 3/6 thay thế và điều kiện đánh giá | `8832e916419101274c0ec1baaa4e7af8d2c183084d3a6e1ba2c3bca1af345107` |
| RULES.md | 34 | Quy tắc AI, liêm chính, dữ liệu, file không được sửa, deadline | `e6f1839bcd29682d03448d45865d8b9f430442f90b5214834d59d692cf18f672` |
| SUBMISSION.md | 69 | Cấu trúc nộp K5, cách gom bằng chứng, điều kiện bàn giao | `ee7f4c0d1ebb3cdae1f68f979409862004838332f57dc265fa43aff7bfe76b65` |
| TROUBLESHOOTING.md | 918 | Tình huống lỗi và cách xử lý mẫu; có chỉ dẫn xung đột với nguồn khác | `3a86f067c364f8efd2c56ad9a70c59f8229d33220dff395c1bb553b01cd88443` |

Mẫu trong file học phải được phân loại ở mức đoạn: `CODE_LAB.md:428-450`, `496-519`, `933-948`, `974-1009` là phần Solution; `INSTRUCTOR_GUIDE.md:36-43`, `61-72`, `361-371` chứa đáp án kỳ vọng. Không được biến chúng thành “cách bạn đã làm”. `QUICK_START.md:384-404` có checklist đánh dấu sẵn và con số 36% trong ví dụ, không phải tiến độ học viên.

## 2. Mục tiêu, quy tắc và độ ưu tiên

Mục tiêu của bài là chuyển agent chạy local thành dịch vụ có cấu hình, đóng gói, bảo vệ, khả năng vận hành, rồi đo tốc độ/chất lượng và quan sát khi chạy (`CODE_LAB.md:6-14`, `README.md:3`, `108-118`). Bản K5 là bài cá nhân và có lộ trình tại lớp riêng (`README.md:9-15`, `CHECKPOINTS.md:6-23`).

Các quy tắc cần giữ trong HTML:

- AI được hỗ trợ, nhưng học viên phải khai AI log và có thể phải giải thích bất kỳ đoạn code hoặc con số nào; cấm bịa số đo (`RULES.md:5-8`). Đây là căn cứ trực tiếp cho luyện “vì sao” và trình bày bằng chứng.
- Không thay script chấm và golden dataset để lấy kết quả; thay KB theo bài tập (`RULES.md:16-19`). HTML không sửa bài làm hoặc chạy lại thí nghiệm.
- Đầu ra gốc gồm ba Markdown bài làm, code Part 6, JSON, CSV và ảnh (`SUBMISSION.md:24-44`); chỉ ba Markdown nằm trong phạm vi nội dung bài làm đã đọc.
- Mẫu dữ liệu sử dụng mock LLM, không cần API key thật (`README.md:104`, `RULES.md:29`). Số token/chi phí trong bài không được diễn đạt như hóa đơn hay usage của model production thật.
- Tổng thô 120, quy đổi 100, đạt 70/100; Part 1–5 mỗi Part 8 điểm, Part 6 là 60, Part 7 là 20. Part 7 chia 4+5+4+3+4; K5 không có bonus (`RUBRIC.md:3-24,65-67`). HTML chỉ hiển thị bản đồ tiêu chí, không tự chốt điểm chính thức.

Thứ tự ưu tiên không dựa vào tên file một cách mù quáng. Có bằng chứng override cụ thể: `README.md:15-31` nói K5 khác tutorial/checklist ở những chỗ được liệt kê; `CHECKPOINTS.md:6-10` đổi thời lượng và thứ tự; `RUBRIC.md:3,24` thay bảng Part 3 và 6 nhưng vẫn dẫn instructor guide cho các Part khác. Lưu quan hệ `supersedes` theo từng quy tắc, không loại toàn bộ nội dung tài liệu cũ.

## 3. Bản đồ yêu cầu – bài làm – bằng chứng

Trạng thái dùng trong bảng: **đề** = yêu cầu; **tự báo cáo** = khẳng định của người làm; **transcript dán** = có đoạn kết quả trong Markdown, chưa xác minh nguồn chạy; **tham chiếu chưa đọc** = file ngoài root-only. Không có hàng nào là chứng nhận đã chạy lại.

| ID | Điều cần hiểu / yêu cầu | Nguồn đề | Nội dung bài làm quan sát được | Phần chưa xác minh |
|---|---|---|---|---|
| D14-R1 | Vì sao chạy trên laptop chưa đủ cho production; ≥5 anti-pattern và so sánh có giải thích | CHECKPOINTS.md:34-40; INSTRUCTOR_GUIDE.md:24-43 | Sáu anti-pattern và bảng giải thích, transcript HTTP 200 (MISSION_ANSWERS.md:10-67) | Code develop/production được dẫn chưa đọc; các giải thích không tự trở thành kiến thức đã kiểm chứng |
| D14-R2 | Đóng gói; cache layer; multi-stage; số image size đo được; sơ đồ services và test qua proxy | CHECKPOINTS.md:42-48; INSTRUCTOR_GUIDE.md:47-59 | Câu trả lời, hai bộ số image size và sơ đồ nhiều service (MISSION_ANSWERS.md:73-145) | Hai bộ dung lượng không tương đương; không thấy transcript test qua Nginx ngay trong mục 2.4; code/Dockerfile chưa đọc |
| D14-R3 | Auth, rate limit, cost guard bảo vệ ba loại rủi ro khác nhau | CHECKPOINTS.md:50-56; RUBRIC.md:48-51 | Transcript 401/200/429, mô tả Redis budget và công thức chi phí (MISSION_ANSWERS.md:179-285) | Không đọc implementation; cách kiểm ngân sách được mô tả không chứng minh bảo vệ đồng thời/race-free |
| D14-R4 | Health khác readiness; giữ state qua nhiều instance; tắt an toàn | CHECKPOINTS.md:58-72 | Giải thích health/ready/shutdown, transcript 5 request và 10 message qua 3 instance (MISSION_ANSWERS.md:291-356) | Transcript là nội dung dán; không kiểm script/test hay Redis thực tế |
| D14-R5 | Ráp Part 6 trong đúng thư mục, PASS 12/12 và tiêu chí K5 | CHECKPOINTS.md:66-72; RUBRIC.md:36-63 | Transcript tự báo cáo 12/12 và 43/43, image 69 MB (MISSION_ANSWERS.md:360-464) | Chưa chạy script hoặc đọc code; PASS trong tài liệu không chứng minh service hiện tại đạt; image Part 6 khác image Part 2 |
| D14-R6 | Deploy chính agent Part 6 lên một nền tảng; Redis/env; 4 HTTP checks; so sánh nền tảng và mô tả Cloud Run | CHECKPOINTS.md:74-85; RUBRIC.md:26-34 | Khẳng định chọn Railway, so sánh config, mô tả CI/CD; response dán trong deployment (MISSION_ANSWERS.md:149-173; DEPLOYMENT.md:6-66) | Không gọi URL, xem ảnh hoặc kiểm cấu hình. Bảng so sánh là lời giải thích của bài làm |
| D14-R7 | Load test nhiều mức, tail latency, SLO; không suy tốc độ từ average | CHECKPOINTS.md:88-111; INSTRUCTOR_GUIDE.md:354-361 | Bảng concurrency, 3 mức slow rate, SLO và phân tích (BENCHMARK_REPORT.md:11-52) | JSON nguồn chưa đọc; diễn giải nguyên nhân queueing là giả thuyết của tác giả, không được nâng thành chứng minh |
| D14-R8 | So sánh accuracy/tokens/cost per correct; sửa KB; không regression; quality gate | CHECKPOINTS.md:103-112; INSTRUCTOR_GUIDE.md:363-371 | Tự báo cáo 1/23 → 21/23 → 23/23, chi phí và lý do sửa KB (BENCHMARK_REPORT.md:56-78) | Chưa đọc JSON, dataset, CI hoặc branch protection; một job fail không chứng minh merge đã bị chặn trong cấu hình repo |
| D14-R9 | Đọc dashboard; nối log–trace; ít nhất hai alert và giải thích giới hạn hạ tầng | CHECKPOINTS.md:114-131; INSTRUCTOR_GUIDE.md:373-413 | Link ảnh, trả lời metric, bảng chaos, span/log dán và phân tích (BENCHMARK_REPORT.md:82-145) | Không xem ảnh/rules/log gốc; thời gian firing là tự báo cáo, không dùng làm hằng số mô phỏng |
| D14-R10 | So sánh scale 1/3 có điều kiện đo; nộp bằng chứng khớp report | CHECKPOINTS.md:118-131; SUBMISSION.md:31-53,66-67 | Bảng endpoint/Aggregated, RPS/p95/failure và giải thích giới hạn tải (BENCHMARK_REPORT.md:149-166) | CSV/Locust chưa đọc; mô hình nguyên nhân cần tách khỏi số liệu bảng |
| D14-R11 | Giải thích vai trò AI và tự kiểm | RULES.md:5-8; SUBMISSION.md:64 | Bốn hàng AI log mô tả nội dung trợ giúp và tự kiểm (MISSION_ANSWERS.md:468-475) | Có log không chứng minh người học đã hiểu; cần buổi tự trình bày |

## 4. Workflow phải biểu diễn

### 4.1 Luồng học và tạo sản phẩm K5

```text
Chuẩn bị → nhận diện dev/prod → đóng gói
  → auth/rate/budget → reliability/state
  → ráp Part 6 + kiểm 12 tiêu chí
  → deploy Part 6 + kiểm public endpoint
  → benchmark local (v1/v2, tải, quality)
  → stack quan sát + trace/chaos/scale
  → đối chiếu report với artifacts → bàn giao
```

Nguồn thứ tự: `CHECKPOINTS.md:12-23`; sản phẩm/ý cần hiểu: `34-131`. Thứ tự này là lộ trình giảng dạy. Không tự suy mọi mũi tên là phụ thuộc thực thi: benchmark dùng app riêng trong `06-lab-complete/benchmark-observability/develop/`, có thể học local, không phải mặc định đo agent Part 6 đã deploy (`CHECKPOINTS.md:91`, `README.md:60-64`).

### 4.2 Luồng xử lý một request (mô hình theo hướng dẫn, chưa kiểm code)

`input → verify API key → check rate limit → check budget → LLM → record cost → response`, có nhánh từ chối 401/429/402; state của giới hạn/budget lưu Redis. Nguồn trực tiếp: `CODE_LAB.md:745-791`, `RUBRIC.md:48-55`. Đây là lõi tốt cho tương tác theo dấu request; không trộn JWT của Part 4 vào yêu cầu API key của Part 6.

Health/readiness và SIGTERM thuộc luồng vận hành song song, không phải các bước bắt buộc trong mọi request (`CODE_LAB.md:720-743,793-805`, `CHECKPOINTS.md:71`). Đồ thị cần phân biệt cạnh dữ liệu, phụ thuộc, điều kiện và sự kiện vận hành.

### 4.3 Vòng quan sát và cải tiến

`chọn cấu hình → đo load/eval → đọc kết quả → tìm nguyên nhân bằng metrics/trace/log → sửa có phạm vi → đo lại cùng chuẩn → quyết định triển khai`. Căn cứ: `CODE_LAB.md:895-1074`, `CHECKPOINTS.md:102-112`. Trình bày hai trục tốc độ/vận hành và chất lượng độc lập: đổi v2 về v1 có thể không làm alert hạ tầng firing (`CODE_LAB.md:1054-1056`, `BENCHMARK_REPORT.md:114-121`).

## 5. Xung đột và giới hạn phải xuất hiện trong mô hình

| ID | Mâu thuẫn / khác phạm vi | Nguồn | Cách xử lý trong HTML |
|---|---|---|---|
| D14-C1 | Tutorial đi Part 1→7, K5 chuyển deploy sau Final Project và CP8 sau lớp | CODE_LAB.md:35-45; LEARNING_PATH.md:266-297; CHECKPOINTS.md:6-23 | Resolved bằng override có nguồn; dùng thứ tự CP cho K5, vẫn giữ số Part để tra cứu |
| D14-C2 | `app/` ở gốc vs code ở `06-lab-complete/` | DAY14_DELIVERY_CHECKLIST.md:71-89,187; README.md:17; SUBMISSION.md:22 | Resolved bằng quy định K5; không hướng người học chuyển code |
| D14-C3 | Part 6 có bảng legacy 100 điểm trong tutorial và bảng instructor cộng 80 dù tiêu đề 60; K5 là 60 | CODE_LAB.md:881-891; INSTRUCTOR_GUIDE.md:192-331; RUBRIC.md:3,24,36-63 | Dùng bảng K5 theo override, lưu bảng cũ là superseded; không cộng ba bảng |
| D14-C4 | History/bonus và Cloud Run optional ở tài liệu cũ; K5 không bonus, history không tính điểm, Cloud Run mô tả 1 điểm | INSTRUCTOR_GUIDE.md:82-87,203,629-634; RUBRIC.md:34,61-67 | Dùng quy tắc K5 theo phạm vi; mở rộng không được biến thành bắt buộc |
| D14-C5 | JSON query, đường dẫn JWT, port/endpoint, stateless test kill instance và self-test GET /ask khác nhau | CODE_LAB.md:90-95,375-377,600-622; DAY14_DELIVERY_CHECKLIST.md:207-209; README.md:19-31 | Dùng correction README cho các bài được chỉ rõ; không tái phát lỗi cũ trong mini game |
| D14-C6 | Instructor ghi implement JWT nhưng K5 chỉ chạy mẫu/lấy token | INSTRUCTOR_GUIDE.md:108; CHECKPOINTS.md:8,53 | Gắn override hành động, giữ mục tiêu hiểu flow; không tự giao thêm công việc code |
| D14-C7 | Kích thước cùng tag trong bài làm: `docker images` 1.67 GB/240 MB; `inspect` 426.32 MB/57.41 MB | MISSION_ANSWERS.md:94-113 | Unresolved: không gộp thành một tỷ lệ “đã xác minh”; giữ hai số theo nguồn đo, hỏi lại cách đo/phiên bản. Image Part 6 69 MB là artifact khác (dòng 387), không coi là mâu thuẫn cùng image |
| D14-C8 | Accuracy gate: bảng report ghi ≥80%; SLO và giải thích sau ghi ≥85%; lượt sửa cuối cần 100% | BENCHMARK_REPORT.md:17,66,119; CODE_LAB.md:972,1004; CHECKPOINTS.md:107 | Tách ngưỡng mục tiêu/CI/final run; discrepancy 80/85 chưa biết cấu hình thực. Không tự đổi số hoặc chấm fail/pass |
| D14-C9 | Tài liệu debug đề nghị in key hoặc lộ biến môi trường; luật cấm lộ bí mật | TROUBLESHOOTING.md:463-467,839-848; RULES.md:27-34 | Nội dung được đọc nhưng không được tái hiện key thật; giữ mục tiêu chẩn đoán và chỉ ra chỉ dẫn có rủi ro, không chạy lệnh |
| D14-C10 | Trouble guide nói Redis URL có `/0` có thể sai nhưng tutorial cấu hình `/0`; mẫu shutdown `sys.exit` khác lời hướng dẫn giữ handler Uvicorn | TROUBLESHOOTING.md:581-589,678-687; CODE_LAB.md:712,795-805 | Ghi xung đột kỹ thuật và nguồn; không dùng chi tiết chưa giải quyết làm đáp án đúng duy nhất. Mục tiêu lab readiness/shutdown vẫn có nguồn K5 |
| D14-C11 | Báo cáo dùng `<` ở bảng SLO nhưng `≤` ở bảng kết quả | BENCHMARK_REPORT.md:15-16,27 | Không ảnh hưởng các số hàng hiện tại nhưng phải giữ toán tử trong schema; chưa chốt điều kiện đúng ở biên |

Các tuyên bố mạnh như “scale infinitely” (`LEARNING_PATH.md:392-395`), số thời gian/retention trong ví dụ (`QUICK_START.md:353-376`), hoặc danh hiệu hoàn thành không phải kết quả nghiên cứu học viên. Không đưa chúng vào phần kết luận thành tích.

## 6. Tương tác nên triển khai và căn cứ

Các mục dưới là đề xuất thiết kế từ nội dung đã đọc, chưa có thử nghiệm hiệu quả với người học.

| ID | Mục tiêu học | Tương tác | Phản hồi / bằng chứng cần thấy | Nguồn |
|---|---|---|---|---|
| D14-I1 | Phân biệt auth, tốc độ và tiền | Theo dấu một request qua ba cổng; thay key, số request, budget | Chỉ ra cổng dừng, mã HTTP, lý do; ví dụ tự dựng ghi nhãn giả lập, không gọi API | CHECKPOINTS.md:52-55; CODE_LAB.md:745-791 |
| D14-I2 | Hiểu health vs readiness | Tắt Redis trong mô hình, chọn probe đổi trạng thái và cách xử lý | Process còn sống khác sẵn sàng nhận việc; không mô phỏng restart mọi instance như đáp án đúng | CHECKPOINTS.md:63,71; MISSION_ANSWERS.md:293-297 |
| D14-I3 | Hiểu state khi scale | Chuyển thẻ hội thoại giữa các instance; chọn RAM hoặc Redis | Nếu là ví dụ minh họa ghi rõ; nối về transcript bài làm, không nói đã tái hiện test | CODE_LAB.md:557-585; MISSION_ANSWERS.md:301-356 |
| D14-I4 | Không đánh giá bằng average | So sánh các snapshot slow rate trong report; người học đoán avg/p95/p99 thay đổi | Hiện đúng các hàng tự báo cáo và nhãn chưa kiểm JSON; không nội suy số đo mới | BENCHMARK_REPORT.md:40-52; INSTRUCTOR_GUIDE.md:354-361 |
| D14-I5 | Phân biệt chất lượng với vận hành | Hai bảng trạng thái: hạ tầng xanh nhưng phiên bản v1 trả lời kém; chọn tín hiệu cần bổ sung | Giải thích vì sao dashboard hạ tầng chưa đủ và eval phải riêng | CODE_LAB.md:1054-1056; BENCHMARK_REPORT.md:114-121 |
| D14-I6 | Nối metrics–trace–log | Từ cảnh báo chậm chọn trace, chọn span, đối chiếu trường `trace_id` | Kiểm quan hệ trong đoạn log dán; không cộng duration các span lồng nhau như thời gian nối tiếp | BENCHMARK_REPORT.md:125-143; INSTRUCTOR_GUIDE.md:380-385 |
| D14-I7 | Trình bày quyết định bằng bằng chứng | Bốc câu “thêm 3 instance có chắc nhanh gấp 3?” rồi tự trả lời trước khi mở gợi ý | Dùng bảng scale, nêu điều kiện tải, tách số liệu tự báo cáo và giả thuyết nguyên nhân | BENCHMARK_REPORT.md:149-166; RULES.md:7-8 |

MVP nên dùng I1, I2, I5 và một bài tự trình bày dựa trên I7; các tương tác khác là mở rộng. Đây là ưu tiên thiết kế, không thay trọng số rubric. Mỗi tương tác có một câu “vì sao”, một phản hồi theo lựa chọn và một nguồn; không coi bấm đúng hoặc đọc lời giải là đã hiểu.

## 7. Kiến trúc chung rút ra và ngoại lệ

Đề xuất đơn vị nội dung dùng chung: **mục tiêu → yêu cầu → bước/quan hệ → quyết định → khẳng định bài làm → bằng chứng → giới hạn → câu hỏi tự giải thích**. Day14 có đủ căn cứ cho từng lớp: mục tiêu ở `CODE_LAB.md:6-14`, yêu cầu/điều cần hiểu ở `CHECKPOINTS.md:34-131`, bài làm ở ba Markdown, rubric ở `RUBRIC.md`, nghĩa vụ giải thích ở `RULES.md:5-8`.

Các trường schema tối thiểu Day14 yêu cầu:

- `source_role` theo đoạn; `authority_scope`, `supersedes` và nguồn xác lập override.
- `claim_status`: đề yêu cầu / mẫu minh họa / tác giả báo cáo / transcript dán / tham chiếu chưa đọc / xung đột. Không có trạng thái “verified runtime” từ root-only.
- `artifact_id`, `part_id`, `checkpoint_id`, `environment`, `measurement_method`, `unit`, `threshold_operator`: tránh lẫn image Part 2/6, Part 6/benchmark stack, MB/bytes, 80/85/100 và `<`/`≤`.
- `workflow_edge.type`: thứ tự học, phụ thuộc kỹ thuật, dữ liệu, điều kiện, vòng cải tiến. Không dùng một đồ thị tuyến tính để trộn tất cả.
- `interaction.evidence_refs`, `feedback_by_choice`, `simulation_label`; không cho model sinh JavaScript tùy ý.

Ngoại lệ phải giữ trong HTML chung: một bài có nhiều hệ thống minh họa, nhiều thứ tự Part/CP, tài liệu bị override từng phần, và số đo tự báo cáo chưa có file gốc. Mục “bài làm của tôi” phải có nhãn mức bằng chứng; phần chuẩn bị thuyết trình gồm câu “đây là số ghi trong báo cáo; tôi cần đối chiếu file gốc trước khi khẳng định”.

## 8. Đề bài triển khai và kiểm thử từ nghiên cứu này

1. Fixture root-only gồm tất cả 15 file; check tổng dòng/hash và coverage từng chunk. Nội dung nhạy cảm được che trước model, vẫn giữ line mapping.
2. Test extraction nhận đủ CP/Part mapping, đặc biệt CP5=Part6, CP6=Part3 và CP7/CP8 cùng Part7.
3. Test precedence giải quyết C1–C6 bằng nguồn override, nhưng C7–C8/C10–C11 không được âm thầm resolve.
4. Test evidence ngăn lời giải mẫu, checklist đánh dấu sẵn, transcript dán và link file con thành “đã xác minh”.
5. Test renderer hiện cùng mục chuẩn nhưng phân biệt artifact/context; source popover chỉ trích đoạn cần thiết, không lộ PII/secret/URL deployment cá nhân.
6. Test tương tác cổng request và probe có phản hồi riêng, keyboard được, hoạt động offline; không phát sinh lệnh thực thi ngoài HTML.
7. Kiểm bằng người: yêu cầu học viên giải thích workflow và một biến thể chưa gặp bằng lời mình, dẫn lại bằng chứng, nhận ra chỗ chưa kiểm. Chưa có kết quả thử nghiệm này tại thời điểm nghiên cứu.

Root-only đủ để tạo bản học lại có căn cứ và bản nháp thuyết trình. Root-only chưa đủ để xác nhận code/triển khai/điểm số hoặc khẳng định người học đã hiểu. Việc mở rộng đọc artifacts là một chế độ riêng được chỉ định rõ, không tự mở rộng phạm vi ở bước nghiên cứu này.
