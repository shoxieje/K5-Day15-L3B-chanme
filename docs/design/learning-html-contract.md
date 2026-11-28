# Hợp đồng triển khai HTML học lại — learning-v1

Trạng thái: thiết kế để triển khai, chưa có runtime hoặc HTML sản phẩm theo hợp đồng này. Nghiên cứu căn cứ: [Day13](../research/day13-root-md.md), [Day14](../research/day14-root-md.md). Kế hoạch: [bản chính](../plan-html-sau-bai-lab.md).

## 1. Phạm vi và điểm vào

Luồng mới `after_lab` đọc tất cả Markdown trực tiếp trong repo đầu vào. Luồng cũ `before_lab` giữ nguyên bộ lọc và cách hiểu đường dẫn hiện có. Không suy ra mode từ tên repo, file bài làm, model hay biến môi trường toàn cục.

Hợp đồng `answer(text) -> {"output": str}` giữ nguyên. Input mới là một dòng:

```text
@learning-v1 {"repo_path":"C:/path/to/completed-repo"}
```

Phân tích prefix trước logic lấy dòng đầu trong `agent.answer`. JSON phải đúng một object có `repo_path` chuỗi không rỗng, không nhận thêm khóa; sai JSON trả lỗi rõ, không rơi sang luồng cũ. Input đường dẫn thông thường tiếp tục gọi luồng cũ. Web tạo input bằng `json.dumps`, không ghép shell; `mode` có allowlist `before_lab|after_lab`, mặc định `before_lab` cho request cũ. UI đặt nhãn “Chuẩn bị lab” và “Hiểu bài đã làm”. CLI `python run.py` hiện có nhập được prefix một dòng, không sửa file khung.

Kết quả `after_lab` gồm tóm tắt trạng thái/thiếu nguồn và một dòng máy đọc:

```text
Trang học lại: output/learning-<snapshot-prefix>-<generation-id>.html
```

Web nhận cả marker cũ và marker mới theo mode. Output filename không chứa đường dẫn repo hay PII, generation ID tránh ghi đè bài người khác. Trạng thái job kỹ thuật `done/error` độc lập với trạng thái nội dung bên dưới.

## 2. Thu nhận nguồn xuyên suốt ứng dụng

- Truyền mode theo request: form → handler → ingestion → job → worker → answer. Không đổi `SKIP_FILES` toàn cục.
- `after_lab`: frontend folder picker gửi mọi file `.md` ở cấp gốc, kể cả `MISSION_ANSWERS.md`, `INSTRUCTOR_GUIDE.md`; backend áp dụng đúng cùng quy tắc nhưng tự kiểm lại. `before_lab` giữ nguyên bộ lọc cũ.
- ZIP/GitHub: kiểm path trước khi giải nén; cho phép bỏ đúng một lớp thư mục bọc archive. Chọn repo root trước rồi chỉ lấy Markdown con trực tiếp của root ấy. Từ chối path tuyệt đối, drive/UNC, `..`, symlink/reparse point và tên gây ghi đè/collision (bao gồm khác hoa/thường trên Windows). Giữ kiểm dung lượng nén/giải nén; file bị loại do giới hạn phải có lý do, không lặng lẽ bỏ.
- MVP `after_lab` nhận GitHub repo root; URL `/tree/...` vào subdir bị từ chối có giải thích, tránh nhầm root. Mở rộng chọn subdir là công việc sau. CLI cũng coi thư mục được chỉ định là root, không tự tìm repo cha.
- Ingestion tạo manifest trước khi lọc giới hạn; manifest của file đã tiếp nhận được đưa vào reader và đối chiếu, để không mất dấu file. Local reader liệt kê mọi Markdown trực tiếp trước khi xử lý.
- Không yêu cầu có Python hoặc README mới được nhận là đầu vào hợp lệ; có ít nhất một Markdown root là đủ để phân tích, kết quả có thể thiếu mục tiêu/rubric.
- Không lần theo liên kết file/URL trong Markdown. Không chạy lệnh hoặc code lab. Không chép PII và bí mật vào trace/model/HTML; chỉ giữ thông tin vai trò cần học, ví dụ “người làm”, “người duyệt”. Bộ lọc đọc trước `@tool` phải trả dữ liệu đã che để tracing không ghi raw.

Đặc biệt: bộ lọc upload hiện ở cả JavaScript và `_is_allowed_relpath` sẽ bỏ file bài làm trước khi reader chạy. Phải sửa cả hai cho mode mới, kèm kiểm tra đủ 6/15 file ở từng đường vào. Mọi metadata mode phải được gắn vào job, không dùng trạng thái UI lúc worker bắt đầu.

## 3. Snapshot, giới hạn và coverage

Manifest mỗi file gồm `source_id`, tên tương đối, SHA256 raw bytes tính tại máy, `line_count`, `read_status`, `processed_ranges`, `redacted_ranges`, `issues`. Không đưa raw bytes vào model/trace. Snapshot ID là hash từ danh sách đã sort theo tên chính xác + file hash; repo commit chỉ ghi nếu chính root có metadata Git, không lấy commit của repo Day15 cha.

Đọc UTF-8/UTF-8-BOM nghiêm ngặt; lỗi decode là `unreadable`, không dùng replacement rồi coi như đúng. File rỗng có `line_count=0`, `read_status=empty`, coverage hoàn tất nhưng không có nội dung. Dòng che bí mật giữ vị trí và được ghi trong manifest; claim đụng vùng che không được trích làm bằng chứng.

Giới hạn mặc định đề xuất, cần đo lại khi triển khai: tối đa 2 MiB Markdown tổng, 512 KiB/file, 16.000 ký tự/đoạn gửi model, 80 lời gọi model/job kể cả sửa, tối đa 2 vòng sửa toàn job, tổng thời gian job 20 phút. Đây là giới hạn kỹ thuật chọn cho MVP, không phải số chi phí đo được. Nếu một dòng vượt giới hạn đoạn thì ghi lỗi, không âm thầm cắt; nếu không đọc/analyze đủ thì trạng thái `incomplete`. Dùng deadline monotonic, timeout request không vượt thời gian còn lại (bổ sung tham số keyword tùy chọn cho `call_model`, giữ nguyên call hai tham số cũ); kiểm budget trước mỗi call. Job chờ lock chưa gọi model không tiêu ngân sách runtime, UI hiển thị queued và cho hủy trước khi chạy. Khi triển khai phải đo độ chờ của lock tracing hiện có, không hứa xử lý đồng thời nhiều repo.

Đọc mọi file trước, chia đoạn theo dòng, giữ original line offsets; phần overlap không tăng coverage. Ưu tiên ranh giới heading/đoạn văn; bảng và code fence quá dài được chia có heading/header/fence context lặp được đánh dấu context-only, không đổi dòng gốc. Không phát biểu từ một nửa công thức/bảng: đợi merge đủ đoạn hoặc ghi gap. Trích xuất từng đoạn thành record có ID, hợp nhất bằng code, chỉ gửi các record/nguồn liên quan vào bước tổng hợp. Tập dữ liệu trung gian quá lớn thì tổng hợp theo cụm requirement với coverage ledger, không loại bớt record để vừa context. `processed_ranges` chỉ cập nhật khi kết quả trích xuất qua kiểm schema và nguồn. Coverage hoàn tất khi hợp các khoảng phủ toàn bộ dòng có thể xử lý của mọi file, các dòng che có lý do rõ. Có redaction làm mất ý nghĩa một yêu cầu thì ghi gap, không tuyên bố bao phủ yêu cầu đó.

Lỗi HTTP/timeout, JSON, giới hạn hoặc file đổi hash trong lúc đọc: ghi lỗi có cấu trúc và giữ các record đã hợp lệ; không retry vô hạn. Giữ snapshot đã đọc trong bộ nhớ phiên, không đọc lại file mới để hợp thức nguồn cũ. Không đủ dữ liệu học tập thì chỉ xuất trang thông báo thiếu nguồn; không gọi đó là bài trình bày hoàn chỉnh.

Cache nội bộ nếu thêm sau phải khóa bằng snapshot + prompt_version + schema_version + model; chưa cần cache cho MVP. Mọi usage lấy từ API qua `call_model`, không ước lượng token; nếu API lỗi trước usage thì ghi chưa có usage, không diễn giải thành chi phí bằng 0.

## 4. Data contract

Model chỉ trả JSON. Runtime kiểm schema bằng code thư viện chuẩn và các invariant liên bảng; lưu schema/version trong artifact. Không để model viết CSS, JavaScript, Mermaid code hoặc công thức có thể thực thi.

Các khóa top-level bắt buộc (mảng rỗng được phép khi có gap giải thích):

| Khóa | Nội dung |
|---|---|
| `schema_version` | Chuỗi cố định `learning-v1` |
| `repo_snapshot` | snapshot ID, display label đã loại PII, revision tùy chọn |
| `source_manifest` | Manifest ở §3, do code cấp, model không được sửa |
| `source_refs` | `{id, source_id, start_line, end_line, quote, role}` |
| `requirements` | `{id, text, category, source_ref_ids, applicability, condition, scope, overrides, fulfillment, evidence_ids, gap_ids, conflict_ids}` |
| `contexts` | `{id,artifact_label,part_label,checkpoint_label,environment,scope,source_ref_ids}` |
| `claims` | `{id, text, kind, context_ids, data_origin, simulation_label_required, source_ref_ids, evidence_ids, requirement_ids, premise_ids, assumption}` |
| `evidence` | `{id, description, status, context_ids, data_origin, simulation_label_required, source_ref_ids, external_ref, limitation}` |
| `measurements` | `{id,claim_id,evidence_ids,context_id,method,value,unit,operator,source_ref_ids,conflict_ids}` |
| `workflow` | `{graphs}`; graph là object có shape bên dưới |
| `decisions` | `{id, question, requirement_ids, source_ref_ids, options, recorded_choice_id, recorded_choice_ref_ids, gap_ids}` |
| `interactions` | Union có discriminator `type`, mô tả tại §5 |
| `presentation` | `{cards, questions}`; mỗi card liên kết claim/node/decision/evidence bằng ID |
| `gaps` | `{id, scope_ids, reason, requested_evidence}` |
| `conflicts` | `{id, left_ref_ids, right_ref_ids, topic, state, resolution_ref_ids, human_resolution_note, impact}` |
| `validation` | Do code cấp: `{content_state, issues, coverage_summary, review_state}` |

Trong schema triển khai, mọi object có khóa cố định, từ chối khóa lạ và sai kiểu; ID duy nhất trong namespace, không dùng text làm khóa. Giới hạn độ dài/mảng từ cấu hình, vượt thì báo thay vì cắt im lặng. Các trường null chỉ cho phép nơi ghi rõ tùy chọn.

Enums và quy tắc:

- `source_refs.role`: `assignment|rule|rubric|instruction|student_submission|instructor_example|background|unknown`; phân loại theo đoạn, không gắn một vai trò cứng cho cả file.
- Checkpoint được map vào instruction; loại yêu cầu bên trong vẫn theo category của requirement. `source_refs` có khoảng dòng 1-based nằm trong manifest và quote không rỗng khớp nguyên văn đoạn đã che (chuẩn hóa whitespace cho phép, không sửa số/đơn vị). Mỗi quote có giới hạn độ dài; nguồn không đủ trong một đoạn thì nhiều refs.
- `requirements.category`: `learning_goal|deliverable|constraint|assessment`; `applicability`: `required|optional|conditional|unresolved`. Conditional có biểu thức điều kiện bằng văn bản kèm nguồn, không chạy code.
- `condition` là chuỗi hoặc null; `scope` chuỗi chỉ lớp/phiên bản/phạm vi áp dụng có nguồn, unknown được ghi rõ. `overrides` là mảng `{requirement_id,source_ref_ids}`: liên kết riêng từng requirement bị thay thế với nguồn chứng minh override đúng cặp; không xóa bản cũ, không suy ưu tiên từ tên file. `fulfillment`: `not_reported|reported_complete|reported_partial|reported_not_done|conflicting`. Đây là trạng thái tự báo cáo từng yêu cầu, không có enum `verified_pass`. Mỗi trạng thái ngoài not_reported phải có evidence; thiếu/mâu thuẫn liên kết gap/conflict. Như vậy bản trang draft_ready không tô tất cả bài làm thành hoàn tất.
- `claims.kind`: `required|reported|document_observation|inference|hypothetical`. “Tài liệu ghi kết quả X” là `reported`; “đã chạy và xác minh X” không được sinh trong MVP chỉ đọc Markdown.
- `evidence.status`: `reported_in_markdown|embedded_record_unverified|referenced_unread|missing|conflicting`. Embedded log/bảng là điều có trong tài liệu, chưa là chứng nhận chạy thật. `external_ref` chỉ là tên file tương đối đã làm sạch hoặc null, không tự tải.
- `data_origin`: `lab_simulated|student_reported_measurement|teaching_hypothetical|unknown|not_applicable`. Xuất xứ dữ liệu độc lập với evidence status: số giả lập trong TEAM vừa là lab_simulated vừa là reported_in_markdown. Nhãn theo nguồn, không đoán số không nhãn là số đo. `premise_ids` là mảng claim ID (có thể rỗng); `assumption` là chuỗi hoặc null, bắt buộc khác null cho hypothetical.
- Inference bắt buộc premise_ids không rỗng, mọi ID tồn tại, quan hệ premise không có chu trình; không coi hai claim viện dẫn lẫn nhau là bằng chứng.
- `simulation_label_required` boolean được đặt true khi nguồn quy định nhãn hoặc origin là lab_simulated/teaching_hypothetical. Giữ nhãn trong mọi bảng, thẻ trình bày và feedback dẫn claim đó; dẫn xuất từ dữ liệu simulated kế thừa nhãn. Không để model chép số vào text khác nhằm né nhãn; semantic review kiểm các số trong toàn artifact.
- Claim factual phải có source refs và kiểm tra nguồn hỗ trợ đúng ý; `inference` có premise IDs và nhãn suy luận; `hypothetical` có nhãn giả định và không được dùng làm bằng chứng bài làm.
- `recorded_choice_id` có thể null: không có lựa chọn được bài làm ghi nhận thì giữ unknown. Model không tự gán lựa chọn đúng của đề thành lựa chọn học viên đã làm.
- Conflict `state`: `unresolved|resolved_by_source|resolved_by_human`. Source resolution phải có chỉ dẫn ưu tiên thực sự; `human_resolution_note` chuỗi hoặc null, chỉ nhập bởi người ngoài bước model. Khi resolved_by_human bắt buộc note và nguồn quyết định, MVP chưa có UI giải quyết nên model/code không tự sinh trạng thái này. Instructor guide không tự có quyền cao hơn rubric K5.
- `workflow.graphs[]`: `{id, label, graph_kind, context_ids, nodes, dependency_edges, feedback_edges}`; `graph_kind=learning_order|system_flow|decision_process`. Các graph cùng dùng template nhưng không tự nối edge xuyên graph. Day14 production agent và benchmark demo phải có graph system_flow riêng; không trộn topology chỉ vì cùng repo.
- Node: `{id, label, purpose, inputs, outputs, kind, requirement_ids, claim_ids, source_ref_ids, gap_ids}`. `kind`: `required_step|reported_step|inferred_step`. Inputs/outputs là mảng text đã kiểm, không artifact được khẳng định tồn tại nếu chưa thấy. Node kế thừa fulfillment/gaps của requirement, hiển thị chưa hoàn tất ngay tại bước.
- Dependency edge `{id,from,to,reason,source_ref_ids,basis}` có `basis=explicit|inferred`; inferred hiển thị suy luận. Feedback edge `{id,from,to,condition,stop_condition,source_ref_ids,basis}`; condition/stop_condition chuỗi không rỗng có căn cứ hoặc nhãn giả định. Mọi endpoint thuộc cùng graph. Dependency graph không chu trình; vòng phản hồi nằm trong feedback_edges.

Shape các mục còn lại:

- `decisions.options[]`: `{id,label,rationale,source_ref_ids}`. `recorded_choice_id` null hoặc ID thuộc đúng options và `recorded_choice_ref_ids` trỏ nguồn student_submission ghi lựa chọn đó; null thì refs rỗng. Đây không phải đáp án dùng chấm, câu quyết định mở dùng teach_back.
- `presentation.cards[]`: `{id,title,claim_ids,node_ids,decision_ids,evidence_ids,speaker_prompts,source_ref_ids,gap_ids}`. Speaker prompts là mảng câu hỏi/gợi ý, không lời nhận thành tích. Card không chứa claim text mới ngoài các claim đã kiểm. Mỗi card có ít nhất một ID nội dung hoặc gap.
- `presentation.questions[]`: `{id,prompt,learning_goal_ids,checklist,source_ref_ids}`. Checklist là mảng `{point,source_ref_ids}`, chỉ mở sau khi tự trả lời. Đây là câu ôn tập, không dùng làm đề đo transfer giữ kín.
- Manifest `read_status=read|empty|unreadable|excluded|over_limit|changed`; SHA256/số dòng được phép null duy nhất khi không thể đọc, phải có issue, coverage không hoàn tất. `processed_ranges/redacted_ranges` là mảng `{start_line,end_line}`; redaction details chỉ ghi loại, không ghi nội dung bị che.
- Chunk ledger nội bộ `{source_id,start_line,end_line,status,issue_ids}`, status `pending|processed|failed`; không cần xuất raw/chunk model reply vào HTML.
- Issue: `{id,code,severity,message,scope_ids}`, severity `info|warning|error`; message đã che. Validation.content_state theo §6; `review_state=unreviewed|needs_review`, renderer không có nút biến review thành chứng nhận đạt. Review của TA là quy trình ngoài MVP.
- `coverage_summary`: `{files_total,files_processed,lines_total,lines_processed,redacted_lines,unresolved_issue_ids}` do code tính; riêng coverage nội dung không đồng nghĩa độ phủ rubric. Required requirement nào chưa có content/evidence phải có gap.
- Context chứa các label/environment/scope chuỗi hoặc null khi chưa biết; context_ids trỏ IDs tồn tại, có thể rỗng cho câu hoàn toàn chung. `measurements` giữ ngữ cảnh số qua context_id bắt buộc; value là chuỗi số đúng như nguồn (không tự đổi GB/MB), method/unit là chuỗi hoặc null, operator tách riêng (`<|<=|>|>=|=|null`). Không đặt số tự báo cáo lên chart hoặc dùng chấm nếu thiếu đơn vị/ngữ cảnh cần thiết; giữ text và gap. Hai số chỉ coi cùng phép đo nếu artifact, method, environment, scope và operator khớp; khác scope thì trình bày cạnh nhau, không tự bình quân. Claim số kế thừa origin/nhãn từ evidence; unresolved conflict làm vô hiệu đáp án/simulator phụ thuộc số đó. Không suy Gate 80%, 85%, 100% là cùng loại chỉ vì đều là accuracy.

Ví dụ quan hệ tối thiểu cho fixture triển khai: nguồn tổng hợp một dòng “Báo cáo cần nêu giới hạn.” → source `s1`, ref `r1` role rubric → requirement `q1` category assessment, fulfillment not_reported, gap `g1` → claim `c1` kind required, origin not_applicable, evidence rỗng → card dẫn `c1` và `g1`. Không tạo reported_complete hoặc observed result từ nguồn này. Fixture thứ hai thêm một dòng student_submission “Chưa có lượt đo thứ hai.” → evidence reported_in_markdown → requirement reported_partial; HTML giữ gap. Đây là dữ liệu tổng hợp để viết test sau, không phải phát hiện Day13/14.

Chốt semantic: nguồn/trích dẫn khớp chỉ chứng minh đoạn đó tồn tại. Validator không tự chứng minh đoạn ấy suy ra claim đúng. Bước kiểm nội dung đối chiếu claim–source, phát hiện số/đơn vị/điều kiện không khớp; người duyệt vẫn cần xem trước khi dùng như tài liệu chia sẻ. `review_state` mặc định `unreviewed`, model không được đổi thành đã duyệt.

## 5. Hợp đồng tương tác

Mỗi interaction có `id`, `type`, `title`, `learning_goal_ids`, `source_ref_ids`, `basis`, `prompt`, `feedback`, `gap_ids`. `basis=source_backed|hypothetical`, hypothetical phải hiện giả định. Chỉ bật khi các field/invariant của loại đó đạt. Thiếu căn cứ hoặc conflict unresolved tác động đáp án thì hạ thành câu hỏi thảo luận, không cho điểm đúng/sai.

| Type | Payload bắt buộc | Cách kiểm và phản hồi |
|---|---|---|
| `trace_flow` | graph ID, token label, danh sách `{node_id,before,after,explanation}` | Bước thuộc graph, trạng thái có căn cứ/nhãn giả định; nút trước/sau và danh sách text tương đương sơ đồ |
| `order_dependencies` | node IDs, dependency edge IDs | Chấp nhận mọi thứ tự tô-pô hợp lệ; feedback chỉ ra edge bị vi phạm. Vòng phản hồi tách riêng, không ép thành thứ tự tuyến tính |
| `choose_explain` | options `{id,label,feedback,source_ref_ids}`, `accepted_option_ids`, explanation prompt | ID đáp án nằm trong options; chấp nhận nhiều đáp án nếu nguồn cho phép. Nhập lý do trước khi mở feedback. Nếu không có đáp án xác định, chuyển `teach_back` |
| `teach_back` | question, checklist `{point,source_ref_ids}`, hint levels | Câu tự luận không tự chấm đúng/sai. Chỉ ghi người học đã thử; checklist mở sau khi trả lời hoặc chọn “cần gợi ý” |

Tên field payload chính thức (ngoài common fields chỉ có `payload`):

- `trace_flow.payload={graph_id,token_label,steps}`; mỗi step `{node_id,before,after,explanation}`, steps không rỗng và node thuộc graph_id. Thứ tự không được đi ngược dependency mà không thể hiện nhánh/vòng; không giả một edge không có trong graph.
- `order_dependencies.payload={graph_id,node_ids,edge_ids}`; IDs unique/tồn tại, edges thuộc dependency_edges của graph đó và endpoints thuộc node_ids.
- `choose_explain.payload={options,accepted_option_ids,explanation_prompt}`; options là shape ở bảng §5, accepted IDs unique, không rỗng và thuộc options; không có căn cứ cho tập đáp án thì hạ teach_back.
- `teach_back.payload={question,checklist,hint_levels}`; hint_levels là mảng chuỗi đã kiểm nguồn, checklist không rỗng. Common `feedback` là chuỗi gợi ý chung, feedback từng option là chuỗi riêng có refs. Common `learning_goal_ids` phải trỏ requirement category learning_goal; `source_ref_ids`/`gap_ids` có thể rỗng chỉ khi trạng thái/nhãn minh họa giải thích được.

MVP dùng `trace_flow`, `choose_explain`, `teach_back` khi đủ căn cứ. `order_dependencies` là bổ sung sau khi graph có căn cứ đủ rõ. Bộ mô phỏng số/sliders để sau: chỉ triển khai công thức allowlist đã viết bằng code, nêu đơn vị/phạm vi/giả định; tuyệt đối không `eval` chuỗi model. Với Day13 nếu chưa có công thức/CSV đủ nguồn, dùng đánh đổi định tính hoặc câu hỏi tự giải thích về số tự báo cáo.

Không coi lời giải thích nhập vào là được xác minh bởi HTML offline. Không đưa câu hỏi biến thể dùng đo hiệu quả vào đáp án ôn tập trước lượt kiểm tra.

## 6. Template và trạng thái xuất bản

Thứ tự cố định: `overview → workflow → walkthrough → decisions → evidence → teachback → presentation`. Mục rỗng hiển thị phần thiếu và hành động bổ sung, không biến mất. Đánh nhãn riêng workflow theo yêu cầu và workflow được bài làm ghi nhận. Nguồn hiển thị file:dòng và đoạn trích đã che, mở tại chỗ.

`content_state` do code tính:

- `blocked`: không có nguồn đọc được hoặc lỗi an toàn/cấu trúc chưa khắc phục; chỉ trang giải thích lỗi, không bài học.
- `incomplete`: chưa đọc/phân tích đủ hoặc thiếu/mâu thuẫn ảnh hưởng mục tiêu học chính; các phần hợp lệ xem được, có nhãn bản nháp và danh sách chưa rõ.
- `draft_ready`: nguồn đã xử lý đủ, invariant đạt, mục tiêu học có nội dung có nguồn; gap nhỏ vẫn hiện. Nghĩa là sẵn sàng người duyệt, không phải bài làm đã hoàn thành hay người học đã hiểu.

Kiểm semantic có issue chưa xử lý trên claim thì loại claim khỏi bài và ghi gap; không nhét claim lỗi vào chú thích rồi dùng làm đáp án. Tối đa hai vòng sửa chỉ gửi record lỗi + nguồn cần thiết, kiểm lại toàn bộ liên kết sau sửa. Không còn nội dung đủ học thì `blocked`.

Một file HTML UTF-8 đầy đủ do template dựng, CSS/JS nội tuyến, không font/CDN/fetch/service worker bên ngoài. Text qua escape hoặc DOM `textContent`; JSON nhúng phải encode `<`/`</script>` an toàn, URL không cho `javascript:`/`data:` thực thi. SVG diagram do renderer tạo từ graph đã kiểm, có danh sách text dự phòng. Không nhúng raw Markdown/code HTML.

Tôn trọng reduced-motion; mọi animation có thể tắt. Print mặc định chỉ in nội dung đang chọn, không tự in ghi chú cá nhân hoặc đáp án chưa mở. Người học có nút chọn rõ việc in thêm đáp án/ghi chú. Namespace lưu tiến độ gồm snapshot + schema_version, nhập ghi chú khác snapshot phải cảnh báo và không tự gắn vào bài hiện tại.

Màn trình bày có trước/sau, mục lục, ghi chú, phím mũi tên/Escape chỉ khi không focus ô nhập; responsive và in ra thứ tự mục rõ. Theo dõi tiến độ trong bộ nhớ phiên mặc định. Tùy chọn lưu thiết bị có nhãn, nút xóa; nếu localStorage không dùng được dưới file:// thì hoạt động trong bộ nhớ và cho export/import ghi chú JSON đã kiểm schema. Ghi chú không nằm trong artifact chia sẻ trừ khi người dùng chủ động xuất.

Web preview `learning-v1` trả file nguyên bản, không đi qua `_enhance_roleplay_html`. Thêm download trả raw bytes với `Content-Disposition: attachment`, giới hạn file trong output root. File tải về phải mở và tương tác được khi tắt mạng; checksum nội dung tải bằng file đã sinh. Preview/download không tự chia sẻ với lớp. Public hosting/auth là hạng mục riêng ngoài MVP, không khẳng định endpoint khó đoán bảo vệ dữ liệu riêng.

## 7. Trình tự sửa code và kiểm tra

1. `root_markdown.py`: manifest, chuẩn hóa nguồn/che bí mật, chunks/coverage, path guard; unit checks với Markdown tổng hợp không chứa dữ liệu BTC.
2. `learning_model.py`: extraction và synthesis có nguồn, merge record, schema validation, conflict/evidence logic, budget. `call_model` và tracing hiện có được giữ. Fake mode tạo dữ liệu hợp lệ có nhãn minh họa, không trả output CP2 vào parser mới.
3. `learning_renderer.py` + template assets nội bộ: union component, status, offline/readable/keyboard/presentation/download. Cùng renderer cho cả hai repo.
4. `agent.py`: dispatch prefix/mode, marker mới, dùng module mới. Đường dẫn input cũ vẫn tới `read_lab` cũ.
5. `web_server.py`: mode end-to-end, mode-specific ingestion cả frontend/backend, manifest handoff, marker/preview/download. Route upload cũ không thay đổi ý nghĩa khi thiếu mode.
6. Tài liệu và changelog spec §10; thêm bộ kiểm mới trong `tests/learning/` và kịch bản `scripts/check_learning.py`, không sửa chuẩn CP2 hoặc CSV cũ. HTML thử từ repo thật ở `output/` (ignored), không commit repo nguồn.

Các ca nghiệm thu bắt buộc khi triển khai:

- Cùng root qua local/ZIP/GitHub-root/folder upload giữ cùng tập Markdown và hash, trừ normalization archive đã quy định; hai file bài làm/giảng viên được giữ ở after_lab và vẫn bị lọc ở before_lab.
- 6/6 và 15/15 file có manifest coverage, nếu file thay đổi kiểm inventory mới; dài/quá giới hạn/lỗi encoding/symlink/secret/collision đều có outcome đúng.
- Root chỉ có đề: sinh phần học đề có nhãn và gaps, không tạo số/claim đã làm. Root có báo cáo: giữ `reported`, không tự upgraded thành verified.
- Rubric–instructor conflict, 401/200/429, số/đơn vị, conditional requirement, quote đúng nhưng claim sai: có kiểm semantic và hành vi hạ cấp rõ.
- Source ref bịa, dangling ID, dependency cycle, answer option không tồn tại, fake mode, JSON lỗi cả lượt đầu/vòng sửa, timeout/budget: không sinh nội dung sai dưới nhãn ready.
- File HTML không tạo request mạng, mọi tương tác dùng được bằng bàn phím; `<script>`/`</script>` trong nguồn không chạy; raw download mở offline không có nav/CSS bị chèn bởi enhancer.
- Hai job khác mode không ảnh hưởng nhau, file output không ghi đè; request cũ và các lệnh `python run.py check`/score vẫn dùng chuẩn cũ.

Đây là kế hoạch kiểm thử; chưa có ca nào ở trên được tuyên bố đã chạy cho runtime mới.
