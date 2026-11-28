# Day13 — nghiên cứu Markdown cấp gốc cho HTML học lại và thuyết trình

Ngày đọc: 28/11/2026. Phạm vi: `K5-L3B-Day13-A90-LaunchEconomics/`, chỉ các file Markdown trực tiếp ở cấp gốc. Đã đọc đầy đủ **6/6 file, 419 dòng**, không chạy bài lab, không mở file thư mục con hoặc URL. Đây là phân tích tài liệu và đề xuất thiết kế; chưa phải kiểm chứng kết quả chạy hay thử nghiệm học viên.

Mọi nguồn `FILE.md:a-b` trong tài liệu này đều tương đối với repo Day13 trên. Số dòng theo nội dung UTF-8 đọc bằng `splitlines()`, hash SHA256 tính từ byte gốc. Không đưa tên, MSSV, email hoặc tài khoản cá nhân trong `TEAM.md` vào báo cáo này; chỉ dùng vai trò/thành viên đánh số.

## 1. Snapshot và manifest

| File | Dòng | SHA256 | Vai trò sau khi đọc | Trạng thái |
|---|---:|---|---|---|
| CHECKPOINTS.md | 45 | `d0474d28e876a45a1244a212fada29a9a044d3c60215db2ba64a1455629a1252` | Mục tiêu, nhiệm vụ, sản phẩm, điều cần hiểu, tự kiểm CP1–CP5 | Đã đọc đủ |
| README.md | 93 | `9a0650cbf5b56546e1bac462764cb4909f5a973e5626947ebfc44746b1a38065` | Bối cảnh giả lập, mục tiêu, workflow, luật, danh mục tài liệu | Đã đọc đủ |
| RUBRIC.md | 29 | `f2914fe94afa232ec2406f313f70b207984cc199eea8733c8b4f1a02d31bb552` | Tiêu chí C1–C8, điểm, bằng chứng, điều kiện chấm | Đã đọc đủ |
| RULES.md | 29 | `40964dc9f2ae994f82280a137249e6ac2aca8e989477b202af1ef30fd6389881` | Quy định dùng AI, tính trung thực, dữ liệu, nộp bài | Đã đọc đủ |
| SUBMISSION.md | 88 | `cfb169514bf67db5a33c17a7620f4ae3682fc92d8dc65c6d2bc27b6b99655ca9` | Quy cách nộp, danh sách sản phẩm, deadline, checklist mẫu | Đã đọc đủ |
| TEAM.md | 135 | `0bf2ec8faa5c834a7babe89a261e9bdcf4ca6c6cfd1551b90ca37efc947421be` | Thông tin cá nhân, phân công, tự báo cáo đóng góp/kết quả, khoảng chưa hoàn tất | Đã đọc đủ; chỉ trích phần phi định danh |

Có `.git` riêng tại thư mục repo được cấp. Git HEAD đọc được: `011069c706c08d22de14aa38e65a32f1c58927b5`, nhánh `main`; `git status --short` không có thay đổi tại lúc kiểm tra. Các mã commit được ghi trong `TEAM.md:70,95,135` là tham chiếu lịch sử do tài liệu tự báo cáo, không thay cho HEAD đã đọc. Manifest hash là định danh nội dung đã thực sự đọc. `TEAM.md:8` ghi nhánh main nhưng chưa ghi một commit chốt duy nhất.

**Phân loại bản repo trong phạm vi nghiên cứu:** có đề bài và bài làm tự báo cáo, không phải starter thuần; đồng thời không đủ căn cứ xác nhận toàn bộ bài đã hoàn thành. `TEAM.md:64-71,83-95,107-115,127-135` ghi phần đã làm lẫn phần chưa làm. Các checkbox rỗng tại `SUBMISSION.md:76-88` thuộc checklist hướng dẫn, không tự được coi là trạng thái nộp thực tế.

## 2. Bài này cần người học hiểu gì?

Đây là bài nhóm thiết kế hồ sơ launch v0 cho trợ lý hoàn phí của một công ty giả định và bảo vệ kế hoạch pilot trước hội đồng Gate 2a. Toàn bộ dữ liệu lab là giả lập, không cần model/API thật (`README.md:1-5`; `RULES.md:5`). Bốn câu hỏi học tập là: có đáng chạy, nhân viên có dùng, xử lý lỗi thế nào, pilot có đủ sức đưa ra quyết định không (`README.md:9-14`).

HTML phải giúp người học nối **con số → quyết định → điều kiện kiểm chứng**, không chỉ nhớ các tiêu đề checkpoint. Căn cứ trực tiếp là yêu cầu tự giải thích tử số/mẫu số chi phí, cỡ mẫu hiệu dụng và lý do đề xuất cuối (`RULES.md:7-8`), cùng tiêu chí bảo vệ số bất lợi trong đề xuất (`RUBRIC.md:12,29`). Đây là suy luận thiết kế từ mục tiêu lab, chưa là kết quả đo hiệu quả học.

## 3. Bản đồ yêu cầu — bài làm tự báo cáo — bằng chứng

Quy ước mức bằng chứng: **yêu cầu đề** mô tả điều phải làm; **tự báo cáo** là khẳng định trong Markdown của nhóm; **đã quan sát trong phạm vi đọc** chỉ xác nhận đoạn văn hoặc phép tính hiển thị có trong tài liệu. Không có kết quả chạy độc lập trong nghiên cứu này.

| ID | Yêu cầu và căn cứ | Nội dung nhóm tự báo cáo ở cấp gốc | Bằng chứng và giới hạn |
|---|---|---|---|
| D13-A | Mô hình chi phí: ba kiểm thử A1; A2 đủ 9 dòng; A3 đủ 4 dòng; A4 chi phí cố định (`CHECKPOINTS.md:9-13`; `RUBRIC.md:7`) | Đã viết A1–A4; A1 đạt; A2 4.472 đ, A4 4.599 đ, có nhãn simulated (`TEAM.md:64-71`); A2 có biểu thức số tại dòng 92 | Đọc được biểu thức A2 và lời báo cáo; chưa đọc code, CSV, bảng A2/A3/A4, chưa kiểm việc chạy thật hay đúng công thức |
| D13-B | 9 kịch bản độ nhạy, một cặp, giới hạn 1/2/3 lần, review 100%; xếp hạng ba yếu tố (`CHECKPOINTS.md:17-21`; `RUBRIC.md:8`) | B3 giới hạn 2 lần cho tổng chi phí 6.901.220 đ; B4 11.743/12.415 đ [simulated] (`TEAM.md:83,93`) | Có số tự báo cáo, chưa có đủ bảng so sánh để xác minh tối ưu hoặc xếp hạng; không dựng đồ thị độ nhạy định lượng từ các số thiếu |
| D13-C | Hai người gắn nhãn độc lập 20 ca; đồng thuận ≥80%, khớp đáp án ≥16/20; bảng khắc phục đủ 5 loại (`CHECKPOINTS.md:25-29`; `RUBRIC.md:9`) | Đã soạn bảng khắc phục 5 ca và bộ nhãn người 1; còn thiếu người 2, đồng thuận, nhãn thống nhất (`TEAM.md:109,115,130`) | Trạng thái tài liệu nêu rõ chưa đủ. Không tính đồng thuận, không sinh bộ nhãn người 2 và không coi bảng khắc phục đã được kiểm |
| D13-D | Tính D1/D2 trước khi chọn cách chia; luật dừng tối thiểu ba, đủ bốn vế; xem cỡ mẫu hiệu dụng/cụm (`CHECKPOINTS.md:33-37`; `RUBRIC.md:10,14`) | Chia 20–20 theo nhân viên, MDE 6 điểm; power khoảng 0,64 nếu hiệu quả thật 5 điểm; 4 luật dừng (`TEAM.md:84-95`) | Kế hoạch tự báo cáo có đánh đổi power; chưa đọc YAML, công thức hoặc phép tính để xác minh. Cần phân biệt số nhân viên và số yêu cầu |
| D13-E | Ba chỉ số thử, thêm hai chỉ số, ≥6 event có trace_id, ≥2 rủi ro kinh tế, hồ sơ 7 mục (`CHECKPOINTS.md:41-45`; `RUBRIC.md:11`) | 12 event, hai chỉ số đề xuất; Go có điều kiện cho hai loại yêu cầu và nêu số bất lợi (`TEAM.md:107,127`) | Chưa có danh sách event hay toàn bộ hồ sơ trong root Markdown; chưa kiểm các chỉ số có thực sự tính được từ event |
| D13-REVIEW | Bảo vệ hồ sơ và chấm nhóm khác; đề xuất khớp bằng chứng, có phạm vi và pilot ra quyết định (`CHECKPOINTS.md:41-45`; `RUBRIC.md:12-14`) | Đã chuẩn bị câu hỏi và khung phiếu, chưa chấm chéo (`TEAM.md:128,130,134`) | Không có kết quả hội đồng đã diễn ra. Dàn thuyết trình phải là luyện tập; không mô tả như đã được phê duyệt |

**Số trong bảng trên là số tài liệu tự báo cáo, không phải kết quả nghiên cứu đo lại.** Mọi phép tính sử dụng cột `_simulated` cần giữ nhãn simulated theo luật bài (`README.md:55`; `RULES.md:18`); toàn bối cảnh dữ liệu còn phải được ghi là lab giả lập (`README.md:3`). Hai lớp nhãn này không được đánh đồng với dữ liệu ngoài thực tế.

## 4. Workflow và các phụ thuộc phải biểu diễn

Workflow nội dung đề bài, theo `CHECKPOINTS.md:7-45` và `README.md:25-30`:

```text
Trace/yêu cầu giả lập [nguồn nằm ngoài tập đọc]
   → A1 kiểm công thức
   → A2/A3/A4 mô hình chi phí và phạm vi
   → B độ nhạy, retry, review
   → rủi ro kinh tế + điều kiện chi phí

20 ca lỗi [nguồn nằm ngoài tập đọc]
   → 2 bộ nhãn độc lập → so nhãn/đồng thuận → quy tắc phân biệt
   → 5 cách khắc phục + event phát hiện + vai trò

D1 cỡ mẫu/cụm + D2 tách tác động + baseline an toàn
   → lựa chọn cách chia pilot → luật dừng

Chi phí + lỗi + pilot + event/chỉ số
   → hồ sơ launch v0 → Go / Go có điều kiện / No-go
   → bảo vệ trước hội đồng → ghi nhận duyệt chéo
```

Quan hệ phụ thuộc trực tiếp có căn cứ:

- A1 phải qua trước khi đi tiếp; nhiệm vụ sau dùng số nhiệm vụ trước (`README.md:54-56`).
- B gọi lại mô hình A; rủi ro E lấy số từ độ nhạy B (`CHECKPOINTS.md:18,42`).
- Hai bộ nhãn độc lập phải tồn tại trước khi so nhãn; không sửa bộ độc lập sau đó (`RULES.md:16`).
- Tính D1, trả lời D2 và baseline an toàn trước khi chọn cách chia/luật dừng (`CHECKPOINTS.md:34`).
- Hồ sơ cuối ghép các nhiệm vụ; phải có trạng thái bằng chứng và đề xuất (`CHECKPOINTS.md:41,45`).

Không biến lịch CP1–CP5 thành đồ thị phụ thuộc tuyệt đối: hai người làm C khi hai người còn lại hoàn thiện B (`CHECKPOINTS.md:26`), còn hồ sơ được điền dần từ đầu buổi (`CHECKPOINTS.md:42`; `TEAM.md:24,37`). Renderer cần hỗ trợ nhánh song song và hồ sơ tích lũy, không chỉ một chuỗi bắt buộc.

HTML phải có nhãn riêng **workflow theo đề** và **tiến độ tự báo cáo**. Trong tiến độ tự báo cáo, nhánh C dừng ở thiếu nhãn người 2 và nhánh hội đồng ở chuẩn bị phiếu; căn cứ `TEAM.md:115,130`. Không tô hoàn thành toàn bộ workflow.

## 5. Quyết định và câu hỏi người học cần tự trả lời

| Quyết định | Câu hỏi giải thích/biến thể | Căn cứ |
|---|---|---|
| Tính chi phí mỗi việc thành công | Vì sao lần chạy lỗi vẫn vào tử số nhưng không tăng mẫu số? Nếu chỉ tính token thì bỏ sót gì? | `CHECKPOINTS.md:9,12-13`; `RULES.md:8` |
| Chọn phạm vi yêu cầu | Vì sao thu hẹp phạm vi? Bằng chứng nào khiến một loại yêu cầu không đáng giao agent dù tăng retry? | `CHECKPOINTS.md:12`; `RUBRIC.md:13`; quyết định tự báo cáo tại `TEAM.md:127` |
| Chọn giới hạn retry | Tối ưu chi phí/việc thành công và tối ưu toàn công ty khác nhau thế nào? | `CHECKPOINTS.md:18,20`; kết quả tự báo cáo tại `TEAM.md:93` |
| Chọn ngưỡng dừng | Review 100% làm chi phí vượt ngưỡng dừng thì kế hoạch có tự dừng không? Cần xem thêm bằng chứng nào? | `TEAM.md:108`; yêu cầu luật dừng tại `CHECKPOINTS.md:35` |
| Chọn đơn vị chia pilot | Tổng yêu cầu lớn đã đủ chưa nếu số cụm ít? Mức power tự báo cáo ảnh hưởng kết luận thế nào? | `CHECKPOINTS.md:36-37`; `TEAM.md:84-85` |
| Ra quyết định Gate 2a | Khi có số bất lợi, vì sao Go có điều kiện/No-go có thể hợp lý hơn Go? | `RUBRIC.md:12,27-29`; `TEAM.md:127` |
| Nhận định tác động | Vì sao chỉ số quan sát được chưa chứng minh trợ lý làm chỉ số tăng? | `CHECKPOINTS.md:44`; `README.md:14` |

Các câu hỏi là đề xuất học tập, chưa phải đáp án chấm tự động. Câu mở cần checklist lý giải và nguồn, không chọn một câu trả lời máy sinh làm chân lý.

## 6. Luật và rubric cần giữ trong HTML

| Nhóm | Quy tắc cần phản ánh | Nguồn |
|---|---|---|
| Trung thực | Số do code nhóm hoặc tính tay có cách tính; không bịa số/nhãn/kết quả duyệt chéo | `RULES.md:7` |
| Hiểu bài | Từng người phải tự giải thích chi phí, cỡ mẫu hiệu dụng và đề xuất | `RULES.md:8` |
| Độc lập nhãn | Hai bộ nhãn độc lập, không thay sau khi so | `RULES.md:16` |
| Dữ liệu | Không sửa hai CSV nguồn, giữ nhãn simulated | `RULES.md:17-18` |
| Phạm vi quyết định | Gate 2a chỉ duyệt pilot, đề xuất Go/Go có điều kiện/No-go; không trình bày như đã launch production | `README.md:58`; `RUBRIC.md:27` |
| Trách nhiệm | Người phụ trách là vai trò có quyền quyết định, không ghi “cả đội” | `RUBRIC.md:28` |
| Điểm | 70 điểm C1–C5 do TA, 30 điểm C6–C8 do hội đồng; số lệch ≤2%; không có bonus của bài này | `RUBRIC.md:3,7-19` |
| Nộp | File đúng tên/chỗ, từng thành viên tự nộp link; mốc tại lớp khác deadline | `SUBMISSION.md:5,38-57,63-72`; `RUBRIC.md:24-25` |

Không diễn giải bảng rubric thành điểm nhóm đã đạt. Bộ chấm HTML chỉ là tự đối chiếu yêu cầu, kết quả cần người duyệt; chưa có phiếu hội đồng đọc được trong phạm vi root Markdown (`TEAM.md:130,134`).

## 7. Mâu thuẫn, điểm cần làm rõ và khoảng thiếu

1. **Ngưỡng dừng chi phí và chính sách review:** người rà soát ghi ngưỡng >8.000 đ có thể kích hoạt khi review 100% đạt 11.743 đ [simulated], đề xuất sửa nhưng chưa sửa YAML (`TEAM.md:108`). Đây là xung đột do tài liệu tự báo cáo, chưa kiểm YAML. HTML cần hiện “cần đối chiếu kế hoạch hiện tại”, không tự sửa ngưỡng.
2. **Giả định hoàn thành đầu vào không đúng với mọi mục:** thiếu nhãn người 2, đồng thuận và duyệt chéo (`TEAM.md:115,130`). HTML có thể hỗ trợ hiểu phần đã có nhưng phải giữ trạng thái chưa đủ của C và hội đồng.
3. **Mục tiêu độc lập vs bài làm dùng AI:** TEAM báo dùng AI viết code/hồ sơ và có kiểm bằng chương trình, nhưng chưa ghi nhận tự kiểm tay hoặc phê duyệt ngoài thực tế ở một phần (`TEAM.md:64-66,83-87`). Không suy từ code chạy thành công ra người học đã hiểu hoặc có phê duyệt.
4. **Ngưỡng cụm:** đề nêu ít nhất 20 cụm mỗi nhóm hoặc ghi rõ đánh đổi (`CHECKPOINTS.md:37`); TEAM tự báo chia 20–20 theo nhân viên và power 0,64 ở một hiệu quả khác MDE (`TEAM.md:85`). Cần giải thích sự khác nhau giữa đủ số cụm và đủ sức thống kê, không gắn nhãn “pilot chắc chắn đủ power”. Chưa có đủ công thức/đầu vào để tính lại.
5. **Số nguồn bị giới hạn:** tất cả sản phẩm chấm C1–C8 đều có nguồn quan trọng ngoài cấp gốc (`RUBRIC.md:7-14`). Đọc root-only không cho phép xác nhận độc lập trạng thái đạt của bất cứ C1–C8.
6. **Quy định giờ:** mốc tại lớp không là deadline (`CHECKPOINTS.md:3`; `SUBMISSION.md:66-71`). Không báo nộp muộn dựa vào giờ checkpoint.
7. **Không có mâu thuẫn bonus cần chặn:** rubric ghi quy tắc chung bonus tối đa 10 nhưng nói rõ bài này không dùng (`RUBRIC.md:19,23`). Parser cần nhận ngoại lệ tường minh, không đưa “bonus 10” vào mục tiêu Day13.

## 8. Đề xuất tương tác bám bài

Các mục sau là **đề xuất thiết kế cần thử**, không phải hiệu quả đã được chứng minh.

| Component | Tương tác và phản hồi | Nguồn nội dung | Giới hạn triển khai |
|---|---|---|---|
| `cost_flow` | Đưa thẻ “lần chạy lỗi/thành công” vào luồng tử số/mẫu số; dự đoán điều gì đổi khi thêm retry. Phản hồi giải thích mẫu số chỉ tăng khi yêu cầu thành công | `CHECKPOINTS.md:12-13`; `RULES.md:8` | Dùng ví dụ giả lập có nhãn; công thức đầy đủ và số các thành phần nằm ngoài phạm vi, không giả vờ tái hiện bảng chi phí thật |
| `dependency_order` | Xếp bước “gắn nhãn độc lập → so nhãn → thống nhất quy tắc”; cho phép B chạy song song với C | `CHECKPOINTS.md:26`; `RULES.md:16` | Kiểm cạnh phụ thuộc, không ép một thứ tự duy nhất cho toàn lab |
| `stop_rule_builder` | Ghép NẾU – TRONG – THÌ – KHÔNG THÌ, chọn vai trò có quyền dừng; đối chiếu xung đột ngưỡng/review tự báo cáo | `CHECKPOINTS.md:35`; `RUBRIC.md:14,28`; `TEAM.md:108` | Không tự thay YAML; nêu là luyện tập xử lý xung đột |
| `decision_tradeoff` | Chọn Go/Go có điều kiện/No-go rồi chỉ ra bằng chứng thuận, bất lợi, phần còn thiếu và điều kiện tiếp theo | `RUBRIC.md:12-14,27-29`; `TEAM.md:127` | Cả ba quyết định có thể hợp lý tùy lập luận; không chấm “Go có điều kiện” là đáp án duy nhất chỉ vì TEAM đã chọn |
| `evidence_match` | Nối một claim với mức bằng chứng: đề yêu cầu, TEAM tự báo cáo, file chưa đọc; hiện lý do phân loại | `README.md:74-78`; `TEAM.md:91-95,115,130` | Dạy phân biệt nguồn và sự thật; không thưởng cho claim thiếu nguồn |
| `teach_back` | Người học tự nói 2–3 phút về chi phí, pilot và điều kiện Go; mở checklist giải thích sau khi tự trả lời | `RULES.md:8`; `CHECKPOINTS.md:41,44`; `RUBRIC.md:12-14` | Thời lượng 2–3 phút là lựa chọn thiết kế, không phải yêu cầu gốc; chưa có bộ chấm lời nói |

Ưu tiên MVP Day13: `cost_flow`, `decision_tradeoff`, `teach_back`; các tương tác còn lại thêm khi phần nội dung đã có nguồn đủ. Nếu thiếu dữ liệu cho mô phỏng số, vẫn dùng tình huống định tính có nhãn giả lập hoặc chỉ hiện câu hỏi tự giải thích, không bịa bảng đo.

## 9. Dàn thuyết trình từ chính bài này

Đây là khung học viên điền lời của mình, không viết sẵn thành lời khẳng định thành tích:

1. Bài toán và bốn câu hỏi cần quyết định; bối cảnh giả lập (`README.md:3,9-18`).
2. Dữ liệu đi qua mô hình chi phí, độ nhạy, phân loại lỗi và pilot thế nào (`CHECKPOINTS.md:9-44`).
3. Nhóm tự báo cáo kết quả nào, nguồn là gì, đã kiểm đến đâu (`TEAM.md:71,91-95,114`).
4. Quyết định đề xuất, số bất lợi, tradeoff power và review (`TEAM.md:85,108,127`).
5. Phần chưa hoàn thành và điều kiện cần trước khi khẳng định đạt (`TEAM.md:115,130`).
6. Câu phản biện: thay retry/phạm vi/cách chia pilot sẽ đổi quyết định nào, cần số nào để trả lời (`CHECKPOINTS.md:12,20,36,44`).

## 10. Khuyến nghị cho kiến trúc chung

- **Tách contract và submission:** README/rubric/luật định nghĩa bài; TEAM có đóng góp và kết quả tự báo cáo xen với phân công. Không phân vai cả file một lần rồi dùng mọi dòng cùng mức bằng chứng (`TEAM.md:54-71` là ví dụ giao thoa).
- **Hỗ trợ completion từng mục:** bài có thể hoàn thành một phần, HTML không bị buộc vào hai trạng thái toàn bộ đạt/trượt (`TEAM.md:115,130`).
- **Hỗ trợ biểu đồ phụ thuộc và tích lũy:** có công việc song song và hồ sơ cập nhật cuốn chiếu (`CHECKPOINTS.md:26,42`).
- **Quyết định không luôn có đáp án đóng:** rubric thưởng đề xuất nhất quán với số, kể cả No-go; phản hồi tập trung lý do và bằng chứng (`RUBRIC.md:12,29`).
- **Có nhãn mô phỏng và mức xác minh độc lập:** nguồn giả lập và bằng chứng tự báo cáo là hai thuộc tính khác nhau; không gom vào một nhãn “chưa chắc” (`README.md:3`; `RULES.md:18`; `TEAM.md:87`).
- **Chế độ root-only phải hữu dụng nhưng trung thực:** tận dụng TEAM để trình bày những gì được ghi nhận; hiển thị nguồn con cần bổ sung thay vì dừng toàn bộ hoặc bịa xác minh.

Ngoại lệ Day13 cần giữ: nhóm/hội đồng Gate 2a, chi phí hiệu quả thay vì token đơn thuần, cỡ mẫu cụm, nhãn độc lập, hồ sơ nhiều thành phần và ranh giới chỉ duyệt pilot. Không ép Day14 phải có các khái niệm này chỉ để dùng chung template. Kiến trúc chung phải nằm ở mục tiêu → workflow → quyết định → bằng chứng → giới hạn → luyện trình bày; tên module, đơn vị và luật đặc thù là dữ liệu.

## 11. Nguồn chưa đọc cần ghi trong HTML

Các đường dẫn dưới đây được tài liệu gốc nhắc tới, **chưa kiểm sự tồn tại hoặc nội dung** trong nghiên cứu root-only:

- `src/lab13.py`, `src/logix_runs.csv`, `src/logix_requests.csv`: phép tính và dữ liệu (`RULES.md:7,17`; `SUBMISSION.md:38`).
- `docs/du_lieu_va_cong_thuc.md`: định nghĩa cột và sáu công thức (`README.md:18`).
- `docs/Lab13_Huong_dan_chi_tiet_buoi_chieu.md`, tài liệu đề bài DOCX: hướng dẫn, 20 ca lỗi (`CHECKPOINTS.md:5,26`).
- Sáu file hồ sơ và các báo cáo trong `report/team/`: sản phẩm chính, bằng chứng nộp và phản hồi hội đồng (`SUBMISSION.md:44-57`).

Nếu sau này người dùng cho phép bổ sung nguồn, reader bổ sung cần ghi manifest mới và mức xác minh mới. Không đưa phép đọc bổ sung vào reader root-only một cách ngầm định.
