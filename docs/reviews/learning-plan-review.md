# Review kế hoạch HTML sau bài lab

Ngày: 28/11/2026. Reviewer: agent `review_plan`. Vòng 1: review kế hoạch ban đầu và các điểm tích hợp trong code hiện tại. Chưa chạy API, chưa sửa code, chưa đánh giá hiệu quả học thực tế. Nguồn dòng trong kế hoạch là snapshot trước khi tổng hợp nghiên cứu; mã finding ổn định để theo dõi xử lý.

Kết luận vòng 1: hướng sản phẩm và việc tách yêu cầu khỏi bằng chứng phù hợp mục tiêu. Kế hoạch cần chốt các hợp đồng dưới đây trước khi giao viết code. Các mục “blocking” chặn việc coi kế hoạch là sẵn sàng triển khai, không có nghĩa code hiện tại đã vi phạm một tính năng chưa được triển khai.

## Findings cần xử lý trước triển khai

### R1 — Blocking: bài làm bị loại trước khi đến reader mới

- Nguồn: `codebase/tools.py:18,42`; `codebase/web_server.py:105-114,147,1097-1112,1366,1422`; kế hoạch §3 mới chỉ chỉ định reader riêng.
- Vấn đề: frontend folder-upload và backend giải nén/upload cùng loại `MISSION_ANSWERS.md`, `INSTRUCTOR_GUIDE.md`. Reader mới không thể khôi phục file đã bị bỏ. Luồng ZIP/GitHub/folder có thể cho kết quả khác đọc thư mục local.
- Yêu cầu sửa kế hoạch: đưa `mode` đã validate từ UI tới bộ lọc upload, giải nén, worker và agent. Luồng `post_lab` nhận tất cả Markdown cấp gốc sau khi xử lý thư mục bọc; luồng CP2 giữ chính sách cũ. Chốt repo root thật, tránh coi một subfolder được chọn là repo gốc mà không báo phạm vi. Manifest ingestion phải giữ danh sách file bị bỏ, giới hạn dung lượng/số file và lý do, để không báo đã đọc đủ nếu upload bị cắt.
- Điều kiện đóng: có hợp đồng xuyên suốt các đường vào và ca kiểm chứng cùng một bộ Markdown qua local/folder/ZIP/GitHub cho cùng manifest (trừ provenance đường vào).

### R2 — Blocking: chưa chốt cách gọi luồng mới và cách lấy HTML

- Nguồn: `codebase/agent.py:124-126` chỉ lấy dòng đầu làm path; `codebase/web_server.py:302-320` gọi `answer(path)` và tìm chuỗi `Trang đóng vai: `; `codebase/web_server.py:443-477,1305-1310` chèn CSS/nav vào mọi HTML; kế hoạch §7 yêu cầu giữ hợp đồng nhưng chưa định nghĩa mode.
- Vấn đề: thêm schema mà không định nghĩa input/output khiến web, CLI và eval khó tương thích; đổi nhãn output có thể làm mất link tải. CSS cũ có thể làm hỏng template mới và link `/` không có ý nghĩa khi mở offline.
- Yêu cầu sửa: chốt cú pháp input hoặc API nội bộ rõ ràng, đường dẫn thuần mặc định CP2. Không dùng env mode toàn cục cho nhiều request. Trả `output: str` như cũ; nếu thêm metadata HTML thì giữ tương thích marker cũ hoặc cập nhật parser rõ ràng. Đặt output ID theo snapshot/mode/run, tránh basename ghi đè. HTML `post_lab` phải được phục vụ/tải nguyên byte, không qua enhancer legacy.
- Điều kiện đóng: có ví dụ CLI input, request web, output result, trạng thái lỗi, tên artifact và route/download; mọi khung bị khóa vẫn nguyên vẹn.

### R3 — Blocking: schema còn là danh sách tên; chưa đủ để bảo đảm một chuẩn đầu ra

- Nguồn: kế hoạch §6 (`source_manifest`, `requirements`, `submission_claims`, `workflow`, `interactions`); `codebase/tools.py:71-112` chỉ kiểm cấu trúc cũ, trích dẫn khớp và phần bắt buộc.
- Vấn đề: nguồn có thật không chứng minh khẳng định được nguồn hỗ trợ, và số trong báo cáo Markdown không chứng minh đã chạy thật. Không có enum trạng thái thì model có thể biến “đề yêu cầu” thành “đã hoàn thành”.
- Yêu cầu sửa: chốt trường bắt buộc, kiểu, enum, ID và quan hệ. Tách `source_role` (yêu cầu/giảng viên/bài làm), `claim_kind`, `evidence_status` và trạng thái xử lý. Tối thiểu phân biệt yêu cầu, lời người làm tự báo cáo, đoạn báo cáo có output nhúng, thiếu nguồn, suy luận, mâu thuẫn; không gắn “đã xác minh hệ thống chạy” chỉ từ Markdown. Chỉ định validator deterministic làm được gì và phần ngữ nghĩa cần reviewer/TA.
- Điều kiện đóng: có ví dụ model hợp lệ + invariants/negative cases và cách bỏ claim lỗi; không còn đường nào tự nâng trích dẫn đúng thành chứng nhận hoàn thành.

### R4 — Blocking: tương tác có thể tạo đáp án sai dù JSON hợp lệ

- Nguồn: kế hoạch §5 cho phép xếp luồng, thay tham số, chọn–giải thích; §6 chưa có schema component hoặc luật mở tương tác.
- Vấn đề: workflow có thể có vòng lặp và nhiều thứ tự hợp lệ; biến thể/công thức có thể do model suy đoán; đáp án bị xóa sau repair có thể để lựa chọn hoặc node dangling.
- Yêu cầu sửa: mỗi component cần contract riêng và gate. Xếp bước chỉ dùng tập phụ thuộc DAG đã kiểm, chấp nhận mọi thứ tự hợp lệ, hoặc tách vòng lặp thành bước mô tả. Numeric simulator chỉ dùng hàm được code whitelist cùng domain/units/đầu vào có nguồn; không dùng `eval` hoặc JS từ model. Choice phải có option ID, phản hồi riêng, căn cứ và điều kiện đúng rõ; nếu nguồn mâu thuẫn thì chuyển sang câu hỏi thảo luận không chấm. Repair phải revalidate toàn graph và mọi reference, vô hiệu hóa component lỗi thay vì giữ nút hoạt động với dữ liệu thiếu.
- Điều kiện đóng: schema và ca acceptance cho từng component MVP, cộng fallback khi chưa đủ căn cứ. Không cần triển khai tất cả loại trong MVP.

### R5 — Blocking: “đọc đủ tất cả” chưa có thuật toán kết thúc và coverage

- Nguồn: kế hoạch §3 yêu cầu đọc đủ và §6 giới hạn repair hai vòng; `codebase/ai.py:72` timeout 300 giây mỗi call; `web_server.py:305-310` serialize agent vì trace dùng trạng thái chung.
- Vấn đề: tài liệu lớn kéo theo nhiều call, dễ giữ lock lâu. Manifest đọc file đủ chưa chứng minh model đã xử lý đủ chunk. “Hai vòng sửa” chưa rõ toàn pipeline hay mỗi stage. Có thể hết ngân sách rồi vẫn dựng trang mang dáng hoàn chỉnh.
- Yêu cầu sửa: xác định snapshot bất biến, chunk bằng khoảng dòng có coverage, extraction theo chunk, reduce có ID trỏ về nguồn gốc, cơ chế xử lý heading/table bị chia. Đặt hữu hạn max calls/size/time và phạm vi repair. Lưu trạng thái mọi chunk: chưa xử lý/đã xử lý/lỗi; tổng hợp chỉ phần đạt. Phân biệt `ready_for_review`, `incomplete_sources`, `invalid_model`, lỗi kỹ thuật; bản thiếu nguồn phải hiển thị rõ và không coi là bản hoàn tất.
- Điều kiện đóng: có thuật toán hữu hạn, ngân sách mặc định là lựa chọn kỹ thuật ghi rõ, không giả token usage; kế hoạch kiểm budget exhaustion và file đổi giữa lần đọc.

### R6 — Blocking: “escape dữ liệu” chưa bao phủ JSON nhúng và metadata nhạy cảm

- Nguồn: kế hoạch §3/§6; `codebase/tracing.py:95-96,114-121` trace ghi input/output công cụ/model; `codebase/tools.py:20` regex chỉ nhận vài dạng key; reader mới sẽ đọc cả Markdown bài làm/TEAM.
- Vấn đề: escape HTML không bảo vệ JSON đặt trong `<script>` khỏi chuỗi đóng thẻ; metadata như tên thư mục, đường dẫn máy, repo có tên/MSSV cũng có thể xuất hiện trong HTML. Che bí mật sau gọi tool/model là quá muộn đối với trace.
- Yêu cầu sửa: redaction trước khi dữ liệu vào model và trước khi tool trả về cho decorator trace; trích dẫn render theo bản đã che với số dòng giữ nguyên. Định nghĩa cách nhúng dữ liệu an toàn (`application/json` cùng escaping `<`/`>`/`&` hoặc encoding tương đương), dùng `textContent`, không `innerHTML` dữ liệu; cấm URL/script do model tạo. Dùng display title trung tính, chỉ export nguồn cần thiết, không export full absolute path hoặc danh tính học viên. Bản nguồn raw/hash không đồng nghĩa raw text được đưa lên HTML.
- Điều kiện đóng: acceptance test có `</script>`, HTML event handler, URL scheme lạ và PII ở metadata/Markdown; không sửa tracing framework.

## Cải tiến cần chốt trong bản kế hoạch hoàn thiện

### R7 — Major: thiếu nguồn bài làm là giới hạn sản phẩm, không chỉ lỗi UI

- Nguồn: kế hoạch §3.7 và §5; nghiên cứu hai repo đang được thực hiện riêng.
- Root-only là phạm vi được người dùng yêu cầu và nên giữ. Tuy nhiên nếu bài làm ở thư mục con, HTML có thể chỉ giúp hiểu đề. Cần tên/trạng thái rõ: “hướng dẫn hiểu yêu cầu — chưa đủ bài làm” khác “trình bày bài làm có căn cứ”. Không ép yêu cầu cung cấp thêm nguồn để làm phần độc lập, cũng không tự mở rộng scope.
- Cần chỉ rõ ai bổ sung dữ liệu, ở đâu, điều kiện nào chuyển trạng thái; ví dụ người học bổ sung bản tổng hợp Markdown cấp gốc hoặc chọn nguồn ở phiên sau. Không hứa đã “trình bày bài hoàn thành” khi chưa có.

### R8 — Major: kế hoạch đo học còn thiếu tiêu chí nghiệm thu cụ thể

- Nguồn: kế hoạch §8 đã có pre/post và biến thể nhưng chưa có rubric mới hoặc ngưỡng quyết định.
- Đề xuất chốt rubric độc lập với CP2 gồm: mô tả mục tiêu, giải thích quan hệ workflow, biện minh quyết định, liên hệ bằng chứng, nhận biết giới hạn; mỗi tiêu chí có mô tả mức điểm. Dùng câu hỏi pre/post tương đương nhưng khác nội dung và ít nhất một người chấm có căn cứ nguồn. Ngưỡng pilot là mục tiêu thiết kế cần duyệt, không kết quả hiện có; số người thử nhỏ không đủ khái quát cả lớp.
- Phân biệt acceptance kỹ thuật có thể chạy ngay với hiệu quả giáo dục phải có người thử thật. Không chặn việc hoàn thành tài liệu vì chưa tuyển người thử, nhưng không gọi thiết kế đã được kiểm chứng.

### R9 — Minor: một HTML offline cần fallback lưu trạng thái và QA cụ thể

- Nguồn: kế hoạch §6 có ghi chú/tiến độ local và chế độ trình chiếu/in.
- Đề xuất mặc định lưu trong bộ nhớ; nếu dùng localStorage thì bắt lỗi và namespace theo snapshot/schema, không bảo đảm lưu bền trên `file://`. Có export/import ghi chú JSON riêng do người học chủ động thực hiện, ghi rõ file HTML nội dung vẫn là một artifact tự chứa. In không in đáp án ẩn hoặc ghi chú cá nhân ngoài ý muốn; keyboard focus, reduced motion và nguồn truy cập được bằng bàn phím.

## Theo dõi đóng findings

| ID | Vòng 1 | Cách kiểm khi nhận bản tổng hợp |
|---|---|---|
| R1 | Mở | Đọc hợp đồng ingestion/mode và acceptance các đường vào |
| R2 | Mở | Đọc ví dụ input/output/artifact/web integration |
| R3 | Mở | Đọc schema, enum, evidence policy và invariants |
| R4 | Mở | Đọc component contracts, feedback/gating/repair |
| R5 | Mở | Đọc chunk coverage, budget và trạng thái lỗi |
| R6 | Mở | Đọc redaction, embedding, metadata/trace policy |
| R7 | Mở | Đối chiếu giới hạn nguồn với nghiên cứu Day13/Day14 |
| R8 | Mở | Đọc rubric pilot mới và ranh giới kết luận |
| R9 | Mở | Đọc offline state và QA fallback |

Vòng cuối sẽ đối chiếu bản tổng hợp và hai tài liệu nghiên cứu; chỉ đóng finding khi tài liệu chứa quyết định đủ cụ thể, không coi một lời hứa “sẽ kiểm” là đã xử lý.

## Vòng 2 — đối chiếu hợp đồng learning-v1

Đã đọc toàn bộ `docs/design/learning-html-contract.md` bản đầu và nghiên cứu Day13. Review này đánh giá tính đầy đủ của thiết kế, không chứng nhận runtime đã chạy. Trạng thái dưới đây thay cho bảng vòng 1; “resolved” nghĩa yêu cầu đã có quyết định đủ cụ thể trong tài liệu.

| ID | Trạng thái vòng 2 | Căn cứ và phần còn lại |
|---|---|---|
| R1 | Resolved ở thiết kế | Contract §2, §7 đã mode-specific frontend/backend ingestion, root, manifest và parity checks. Cần triển khai theo đúng hợp đồng |
| R2 | Resolved ở thiết kế | Contract §1, §6, §7 có prefix, mode per-request, marker, generation ID, preview/download raw bypass enhancer |
| R3 | Open | Contract §4 đã tách vai trò/claim/evidence, nhưng một số trường bắt buộc trong văn xuôi chưa có trong bảng schema; xem R3a bên dưới |
| R4 | Open | Contract §5 đã gate/whitelist, nhưng references graph/edge chưa có đích ID và shape chưa đủ; xem R4a |
| R5 | Partially resolved | Contract §3 có ngân sách hữu hạn, coverage, immutable snapshot, lỗi và không retry vô hạn; cần chốt manifest enum/nullable và heading/table context để implement thống nhất |
| R6 | Resolved ở thiết kế | Contract §2, §3, §6 có redaction trước trace/model, display label không PII, JSON embedding, textContent và tests injection; việc thực thi vẫn cần kiểm khi coding |
| R7 | Partially resolved | Contract §4, §6 đã phân biệt draft_ready với hoàn thành bài; cần per-requirement trạng thái bài làm và nguồn cho trạng thái này |
| R8 | Open | Contract không thay rubric pilot; bản chính cần chốt tiêu chí, mức điểm và quy tắc diễn giải kết quả |
| R9 | Resolved ở thiết kế | Contract §6 đã memory default, localStorage fallback, schema import, ghi chú private, keyboard controls và raw offline artifact |

### R3a — các trường và trạng thái cần bổ sung trực tiếp vào schema

1. `requirements.applicability=conditional` yêu cầu điều kiện có nguồn, nhưng shape requirements chưa có `condition` hoặc `condition_source_ref_ids`.
2. `claims.kind=inference` yêu cầu `premise_ids`, nhưng shape claims chưa có trường này. Cần định nghĩa premise trỏ tới claim/requirement/evidence nào và cấm chu trình suy luận.
3. `conflicts.state=resolved_by_human` yêu cầu ghi chú do người nhập, nhưng shape chưa có human resolution record và cờ ownership. Không cho model tự tạo human resolution.
4. `decisions.options` chưa có shape; `recorded_choice_id` cần trỏ option hợp lệ và có `recorded_choice_source_ref_ids` từ bài làm. Không được dùng nguồn rubric để chứng minh lựa chọn đã được thực hiện.
5. `presentation.cards/questions`, `source_manifest.read_status/issues`, `validation.review_state/issues/coverage_summary` cần có shape, enum và owner. File chưa đọc/lỗi encoding cần hash nullable được giải thích; không tạo hash giả.
6. Nghiên cứu Day13 §3/§10 cho thấy cần `data_origin` độc lập `evidence.status`: số có thể thuộc lab giả lập và đồng thời là tự báo cáo chưa xác minh. Phải ghi thuộc tính ở cấp claim/evidence, không chỉ một nhãn toàn page; có trường nguồn chứng minh nhãn simulated.
7. Per-requirement `submission_status` cần tối thiểu tách chưa có thông tin, tự báo đã hoàn thành, tự báo chưa hoàn thành, có record nhúng nhưng chưa xác minh, mâu thuẫn. Đây không phải tiến độ học viên xem trang, không phải điểm rubric. Trạng thái có căn cứ riêng và do reducer theo source quyết định; người học bấm “đã hiểu” không được đổi completion của repo.
8. Định nghĩa rõ role checkpoint là `instruction` hoặc thêm enum `checkpoint`; mục tiêu không phải tăng enum mà để extractor và validator dùng cùng quy ước.

### R4a — các ID và payload còn thiếu

1. `trace_flow` yêu cầu graph ID nhưng workflow shape hiện chỉ `{nodes,dependency_edges,feedback_edges}`, chưa có graph ID/kind. Cần nhiều graph hoặc một cấu trúc có các graph riêng cho instructional sequence và runtime flow; văn xuôi yêu cầu không trộn nhưng schema chưa thể hiện.
2. `order_dependencies` yêu cầu dependency edge IDs nhưng edge shape chưa có `id`.
3. Feedback edge nói có condition/stop nhưng chưa có schema hoặc source refs của điều kiện. Thiếu điều kiện nguồn thì phải là inferred/hypothetical có nhãn.
4. Mọi interaction payload phải có tên khóa chuẩn (ví dụ `graph_id`, `steps`, `options`, `accepted_option_ids`, `hint_levels`), kiểu và nullable rules. “Graph ID, token label” trong bảng chưa phải shape để coding agent triển khai thống nhất.
5. Empty `accepted_option_ids` cần fallback xác định; accepted IDs phải độc nhất, thuộc options và có source support; feedback cho từng option không dùng feedback chung thay thế.

### Điểm nên chốt thêm cho R5

Nêu `read_status` và `analysis_status` riêng để manifest phản ánh đọc được toàn file nhưng model xử lý chưa hết. Ghi `processed_ranges` theo source lines thật, context header lặp lại không tính coverage. Nếu chunk bắt đầu giữa bảng hoặc code fence, gửi thêm context không tính coverage hoặc chia lại ở biên hợp lệ, thay vì mất nghĩa. Nên có giới hạn thời gian job ngoài max calls vì call hiện tại có thể timeout 300 giây; con số là cấu hình kỹ thuật dự kiến, không số đo chi phí.

## Vòng 3 — contract sau sửa và đối chiếu hai nghiên cứu

Đã đọc lại contract sau khi bổ sung `contexts`, `measurements`, `overrides`, shapes/enum, payload tên chuẩn và deadline. Đã đọc toàn bộ báo cáo nghiên cứu Day13 và Day14. Không review lại code runtime vì chưa có triển khai mới.

| ID | Trạng thái sau sửa | Bằng chứng đóng ở thiết kế |
|---|---|---|
| R1 | Resolved | Contract §2 và §7: mode đi xuyên frontend/backend, giữ Markdown bài làm, manifest cho mọi đường vào |
| R2 | Resolved | Contract §1/§6/§7: prefix một dòng, dispatch tương thích, marker riêng, raw download, ID không ghi đè |
| R3 | Resolved | Contract §4: field điều kiện/premise/human note; source role, evidence status, data origin và simulation label riêng; per-requirement fulfillment; context số và override theo từng cặp có nguồn |
| R4 | Resolved | Contract §4–§5: graph/edge IDs, graph_kind và context; union payload field chuẩn; premise DAG, options/accepted IDs và downgrade khi thiếu căn cứ |
| R5 | Resolved | Contract §3/§4: coverage line ledger, read_status và chunk status riêng, context-only khi chia bảng/fence, max calls/repair/size cùng deadline 20 phút |
| R6 | Resolved | Contract §2/§3/§6: che trước trace/model, metadata, encode JSON script, textContent và injection acceptance |
| R7 | Resolved | Nghiên cứu Day13 §3/§7, Day14 §3/§5 và contract §4/§6: có evidence tự báo cáo, phần thiếu/xung đột, fulfillment không phải verified pass; draft_ready không phải bài hoàn thành |
| R8 | Chờ bản chính/common | Chưa có rubric pilot cụ thể trong các tài liệu đã đọc ở vòng này; cần đối chiếu lần cuối khi tổng hợp xong |
| R9 | Resolved | Contract §6: memory mặc định, fallback storage, namespace, kiểm import, reduced motion, print và ghi chú private |

Các nghiên cứu đã đưa ra ngoại lệ cần thiết cho thiết kế: Day13 có nhánh song song, số simulated và quyết định mở; Day14 có override K5 từng phần, nhiều hệ thống/ảnh đo/phương pháp và ngưỡng khác nhau. Contract đã phản ánh chúng bằng graph/context, provenance, origin, fulfillment và measurement scope. Không còn blocker kỹ thuật R1–R6 ở mức kế hoạch tại vòng 3. Nhận định này không thay cho test triển khai hoặc thử nghiệm học viên.

## Review cuối — hoàn tất kế hoạch

Đã đọc bản chính cập nhật, `common-learning-architecture.md`, `learning-validation-plan.md`, hợp đồng learning-v1 và hai nghiên cứu. **R1–R9 đều resolved ở mức thiết kế; không còn finding blocking để bàn giao triển khai.** R8 được đóng bởi validation plan §1–§5: rubric 5 tiêu chí 0–2, điều kiện ≥8/10 không tiêu chí 0, cặp đề pre/post và transfer khác câu ôn tập, người chấm, pilot thăm dò 4 người, cách xử lý người đã đạt từ đầu và giới hạn không đủ mẫu. Các ngưỡng đều được ghi rõ là lựa chọn thiết kế, chưa phải kết quả.

| ID | Trạng thái cuối | Tài liệu quyết định |
|---|---|---|
| R1 | Closed — design | Contract §2, §7 |
| R2 | Closed — design | Contract §1, §6, §7 |
| R3 | Closed — design | Contract §4; common architecture §2–§3 |
| R4 | Closed — design | Contract §4–§5; common architecture §4 |
| R5 | Closed — design | Contract §3–§4 |
| R6 | Closed — design | Contract §2–§3, §6–§7 |
| R7 | Closed — design | Contract §4/§6; common architecture §1/§5; nghiên cứu hai Day |
| R8 | Closed — design | Learning validation plan §1–§5; bản chính §8 |
| R9 | Closed — design | Contract §6–§7 |

Phần còn lại thuộc giai đoạn triển khai, không được báo là đã làm: reader/model/renderer mới, hai HTML offline, kiểm thử code/browser và pilot người học. Root-only vẫn không xác minh code/CSV/deployment; mâu thuẫn nguồn nghiên cứu vẫn cần giữ trong HTML, việc đóng review không giải quyết thay các mâu thuẫn đó. Schema chuẩn hóa cấu trúc nhưng chất lượng sư phạm còn là giả thuyết cần thử.

Bản chính và common architecture ghi đúng rằng nghiên cứu do các agent Codex thực hiện, chưa chạy Claude; tài liệu có thể giao Claude tiếp tục triển khai. Không có thay đổi code hoặc chuẩn eval CP2 trong công việc review này.
