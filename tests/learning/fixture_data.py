"""Dữ liệu tổng hợp cho bộ kiểm learning-v1 — KHÔNG lấy từ repo/data BTC. Một lab giả định nhỏ:
README (đề), RUBRIC (rubric), REPORT (bài làm tự báo cáo, có số giả lập và một dòng chứa markup độc hại).

sample() → (lines_by_source, model) hợp lệ theo codebase/learning_schema.py.
"""
import copy

LINES = {
    "s1": [  # README.md
        "# Lab mẫu: Đo chi phí trợ lý FAQ",
        "",
        "Mục tiêu: giải thích được chi phí mỗi câu trả lời đúng và quyết định có pilot hay không.",
        "Toàn bộ dữ liệu là giả lập (simulated), không gọi model thật.",
        "Bước 1: kiểm công thức chi phí trên 3 ca mẫu trước khi làm bước sau.",
        "Bước 2: tính chi phí cho 2 cấu hình retry và so sánh.",
        "Bước 3: viết đề xuất Go / Go có điều kiện / No-go kèm số bất lợi.",
        "Nếu chi phí vượt ngưỡng 8.000 đ thì phải quay lại bước 2 với cấu hình khác.",
        "Request đi qua: kiểm khóa → giới hạn tốc độ → ngân sách → trả lời.",
        "Sai khóa trả 401, vượt tốc độ trả 429.",
    ],
    "s2": [  # RUBRIC.md
        "# Rubric",
        "C1 (20 điểm): công thức chi phí đúng, có tử số và mẫu số.",
        "C2 (20 điểm): đề xuất nhất quán với số, kể cả No-go.",
        "Báo cáo cần nêu giới hạn.",
    ],
    "s3": [  # REPORT.md
        "# Báo cáo nhóm",
        "Chúng tôi đã kiểm công thức trên 3 ca mẫu, cả 3 ca khớp.",
        "Chi phí mỗi câu đúng với retry 2 lần: 4.472 đ [simulated].",
        "Chưa có lượt đo thứ hai.",
        "Đề xuất: Go có điều kiện cho nhóm câu hỏi đơn giản.",
        "Ghi chú thử: </script><script>alert(1)</script> <img src=x onerror=alert(1)> javascript:alert(1)",
        "[đã che: pii]",
    ],
}

MANIFEST = [
    {"source_id": "s1", "name": "README.md", "sha256": "a" * 64, "line_count": 10, "read_status": "read",
     "processed_ranges": [{"start_line": 1, "end_line": 10}], "redacted_ranges": [], "issues": []},
    {"source_id": "s2", "name": "RUBRIC.md", "sha256": "b" * 64, "line_count": 4, "read_status": "read",
     "processed_ranges": [{"start_line": 1, "end_line": 4}], "redacted_ranges": [], "issues": []},
    {"source_id": "s3", "name": "REPORT.md", "sha256": "c" * 64, "line_count": 7, "read_status": "read",
     "processed_ranges": [{"start_line": 1, "end_line": 7}], "redacted_ranges": [{"start_line": 7, "end_line": 7}],
     "issues": ["iss-redact-s3"]},
]


def ref(i, sid, a, b, quote, role):
    return {"id": i, "source_id": sid, "start_line": a, "end_line": b, "quote": quote, "role": role}


def node(i, label, kind, refs, reqs=(), claims=(), gaps=(), purpose="", inputs=(), outputs=()):
    return {"id": i, "label": label, "purpose": purpose or label, "inputs": list(inputs), "outputs": list(outputs),
            "kind": kind, "requirement_ids": list(reqs), "claim_ids": list(claims), "source_ref_ids": list(refs),
            "gap_ids": list(gaps)}


MODEL = {
    "schema_version": "learning-v1",
    "repo_snapshot": {"snapshot_id": "0123456789abcdef" * 4, "display_label": "Lab mẫu: Đo chi phí trợ lý FAQ",
                      "revision": None},
    "source_manifest": MANIFEST,
    "source_refs": [
        ref("r1", "s1", 3, 3, "giải thích được chi phí mỗi câu trả lời đúng và quyết định có pilot hay không", "assignment"),
        ref("r2", "s1", 4, 4, "Toàn bộ dữ liệu là giả lập (simulated)", "rule"),
        ref("r3", "s1", 5, 5, "kiểm công thức chi phí trên 3 ca mẫu trước khi làm bước sau", "instruction"),
        ref("r4", "s1", 6, 6, "tính chi phí cho 2 cấu hình retry và so sánh", "instruction"),
        ref("r5", "s1", 7, 7, "viết đề xuất Go / Go có điều kiện / No-go kèm số bất lợi", "instruction"),
        ref("r6", "s1", 8, 8, "Nếu chi phí vượt ngưỡng 8.000 đ thì phải quay lại bước 2", "rule"),
        ref("r7", "s1", 9, 9, "kiểm khóa → giới hạn tốc độ → ngân sách → trả lời", "instruction"),
        ref("r8", "s1", 10, 10, "Sai khóa trả 401, vượt tốc độ trả 429.", "instruction"),
        ref("r9", "s2", 2, 2, "công thức chi phí đúng, có tử số và mẫu số", "rubric"),
        ref("r10", "s2", 3, 3, "đề xuất nhất quán với số, kể cả No-go", "rubric"),
        ref("r11", "s2", 4, 4, "Báo cáo cần nêu giới hạn.", "rubric"),
        ref("r12", "s3", 2, 2, "Chúng tôi đã kiểm công thức trên 3 ca mẫu, cả 3 ca khớp.", "student_submission"),
        ref("r13", "s3", 3, 3, "Chi phí mỗi câu đúng với retry 2 lần: 4.472 đ [simulated].", "student_submission"),
        ref("r14", "s3", 4, 4, "Chưa có lượt đo thứ hai.", "student_submission"),
        ref("r15", "s3", 5, 5, "Đề xuất: Go có điều kiện cho nhóm câu hỏi đơn giản.", "student_submission"),
        ref("r16", "s3", 6, 6, "</script><script>alert(1)</script> <img src=x onerror=alert(1)> javascript:alert(1)",
            "student_submission"),
    ],
    "requirements": [
        {"id": "q1", "text": "Giải thích chi phí mỗi câu trả lời đúng và quyết định pilot.", "category": "learning_goal",
         "source_ref_ids": ["r1"], "applicability": "required", "condition": None, "scope": "toàn bài",
         "overrides": [], "fulfillment": "reported_partial", "evidence_ids": ["e2"], "gap_ids": ["g2"], "conflict_ids": []},
        {"id": "q2", "text": "Kiểm công thức chi phí trên 3 ca mẫu trước bước sau.", "category": "deliverable",
         "source_ref_ids": ["r3", "r9"], "applicability": "required", "condition": None, "scope": "bước 1",
         "overrides": [], "fulfillment": "reported_complete", "evidence_ids": ["e1"], "gap_ids": [], "conflict_ids": []},
        {"id": "q3", "text": "Báo cáo cần nêu giới hạn.", "category": "assessment", "source_ref_ids": ["r11"],
         "applicability": "required", "condition": None, "scope": "báo cáo", "overrides": [],
         "fulfillment": "not_reported", "evidence_ids": [], "gap_ids": ["g1"], "conflict_ids": []},
        {"id": "q4", "text": "Quay lại bước 2 nếu chi phí vượt ngưỡng.", "category": "constraint", "source_ref_ids": ["r6"],
         "applicability": "conditional", "condition": "chi phí vượt ngưỡng 8.000 đ", "scope": "bước 2–3",
         "overrides": [], "fulfillment": "not_reported", "evidence_ids": [], "gap_ids": [], "conflict_ids": []},
    ],
    "contexts": [
        {"id": "x1", "artifact_label": "Mô hình chi phí", "part_label": "Bước 2", "checkpoint_label": None,
         "environment": "dữ liệu giả lập", "scope": "retry 2 lần", "source_ref_ids": ["r4"]},
    ],
    "claims": [
        {"id": "c1", "text": "Báo cáo cần nêu giới hạn.", "kind": "required", "context_ids": [],
         "data_origin": "not_applicable", "simulation_label_required": False, "source_ref_ids": ["r11"],
         "evidence_ids": [], "requirement_ids": ["q3"], "premise_ids": [], "assumption": None},
        {"id": "c2", "text": "Nhóm báo cáo chi phí mỗi câu đúng với retry 2 lần là 4.472 đ.", "kind": "reported",
         "context_ids": ["x1"], "data_origin": "lab_simulated", "simulation_label_required": True,
         "source_ref_ids": ["r13"], "evidence_ids": ["e2"], "requirement_ids": ["q1"], "premise_ids": [], "assumption": None},
        {"id": "c3", "text": "Nhóm báo cáo đã kiểm công thức trên 3 ca mẫu và cả 3 ca khớp.", "kind": "reported",
         "context_ids": [], "data_origin": "not_applicable", "simulation_label_required": False,
         "source_ref_ids": ["r12"], "evidence_ids": ["e1"], "requirement_ids": ["q2"], "premise_ids": [], "assumption": None},
        {"id": "c4", "text": "Vì chưa có lượt đo thứ hai, so sánh hai cấu hình retry còn dang dở.", "kind": "inference",
         "context_ids": ["x1"], "data_origin": "not_applicable", "simulation_label_required": False,
         "source_ref_ids": ["r14", "r4"], "evidence_ids": [], "requirement_ids": ["q1"], "premise_ids": ["c2"],
         "assumption": None},
        {"id": "c5", "text": "Giả sử một yêu cầu bị từ chối ở cổng ngân sách thì không gọi model.", "kind": "hypothetical",
         "context_ids": [], "data_origin": "teaching_hypothetical", "simulation_label_required": True,
         "source_ref_ids": ["r7"], "evidence_ids": [], "requirement_ids": [], "premise_ids": [],
         "assumption": "Ví dụ minh họa dựng để học luồng, không phải kết quả chạy."},
        {"id": "c6", "text": "Bài làm có một dòng ghi chú chứa markup lạ.", "kind": "document_observation",
         "context_ids": [], "data_origin": "not_applicable", "simulation_label_required": False,
         "source_ref_ids": ["r16"], "evidence_ids": [], "requirement_ids": [], "premise_ids": [], "assumption": None},
    ],
    "evidence": [
        {"id": "e1", "description": "Báo cáo tự ghi đã kiểm 3 ca mẫu.", "status": "reported_in_markdown",
         "context_ids": [], "data_origin": "not_applicable", "simulation_label_required": False,
         "source_ref_ids": ["r12"], "external_ref": None, "limitation": "Chưa đọc code hay bảng tính để đối chiếu."},
        {"id": "e2", "description": "Số chi phí 4.472 đ ghi trong báo cáo, gắn nhãn simulated.", "status": "reported_in_markdown",
         "context_ids": ["x1"], "data_origin": "lab_simulated", "simulation_label_required": True,
         "source_ref_ids": ["r13"], "external_ref": None, "limitation": "Chưa có lượt đo thứ hai."},
        {"id": "e3", "description": "Bảng tính chi phí được nhắc tới nhưng nằm ngoài Markdown cấp gốc.",
         "status": "referenced_unread", "context_ids": ["x1"], "data_origin": "unknown", "simulation_label_required": False,
         "source_ref_ids": [], "external_ref": "src/cost_table.csv", "limitation": "Chưa đọc file này."},
    ],
    "measurements": [
        {"id": "m1", "claim_id": "c2", "evidence_ids": ["e2"], "context_id": "x1", "method": "tự báo cáo trong Markdown",
         "value": "4.472", "unit": "đ", "operator": "=", "source_ref_ids": ["r13"], "conflict_ids": []},
    ],
    "workflow": {"graphs": [
        {"id": "w1", "label": "Thứ tự làm bài theo đề", "graph_kind": "learning_order", "context_ids": [],
         "nodes": [
             node("n1", "Kiểm công thức (3 ca)", "required_step", ["r3"], reqs=["q2"], claims=["c3"],
                  purpose="Bảo đảm công thức đúng trước khi dùng số", inputs=["3 ca mẫu"], outputs=["công thức đã kiểm"]),
             node("n2", "Tính chi phí 2 cấu hình retry", "required_step", ["r4"], reqs=["q1"], claims=["c2", "c4"],
                  gaps=["g2"], purpose="So sánh chi phí", inputs=["công thức đã kiểm"], outputs=["bảng chi phí"]),
             node("n3", "Viết đề xuất Go/No-go", "required_step", ["r5"], reqs=["q1"],
                  purpose="Ra quyết định có số bất lợi", inputs=["bảng chi phí"], outputs=["đề xuất"]),
         ],
         "dependency_edges": [
             {"id": "d1", "from": "n1", "to": "n2", "reason": "Bước sau dùng công thức đã kiểm", "source_ref_ids": ["r3"],
              "basis": "explicit"},
             {"id": "d2", "from": "n2", "to": "n3", "reason": "Đề xuất dựa trên số chi phí", "source_ref_ids": [],
              "basis": "inferred"},
         ],
         "feedback_edges": [
             {"id": "f1", "from": "n3", "to": "n2", "condition": "chi phí vượt ngưỡng 8.000 đ",
              "stop_condition": "có cấu hình dưới ngưỡng hoặc quyết định No-go", "source_ref_ids": ["r6"],
              "basis": "explicit"},
         ]},
        {"id": "w2", "label": "Luồng xử lý một request", "graph_kind": "system_flow", "context_ids": [],
         "nodes": [
             node("n4", "Kiểm khóa", "required_step", ["r7", "r8"], outputs=["401 nếu sai khóa"]),
             node("n5", "Giới hạn tốc độ", "required_step", ["r7", "r8"], outputs=["429 nếu vượt"]),
             node("n6", "Kiểm ngân sách", "required_step", ["r7"]),
             node("n7", "Trả lời", "required_step", ["r7"]),
         ],
         "dependency_edges": [
             {"id": "d3", "from": "n4", "to": "n5", "reason": "Thứ tự cổng", "source_ref_ids": ["r7"], "basis": "explicit"},
             {"id": "d4", "from": "n5", "to": "n6", "reason": "Thứ tự cổng", "source_ref_ids": ["r7"], "basis": "explicit"},
             {"id": "d5", "from": "n6", "to": "n7", "reason": "Thứ tự cổng", "source_ref_ids": ["r7"], "basis": "explicit"},
         ],
         "feedback_edges": []},
    ]},
    "decisions": [
        {"id": "dc1", "question": "Đề xuất gì trước hội đồng?", "requirement_ids": ["q1"], "source_ref_ids": ["r5", "r10"],
         "options": [
             {"id": "o1", "label": "Go", "rationale": "Khi số thuận lợi đủ mạnh", "source_ref_ids": ["r5"]},
             {"id": "o2", "label": "Go có điều kiện", "rationale": "Giới hạn phạm vi khi còn số bất lợi", "source_ref_ids": ["r5"]},
             {"id": "o3", "label": "No-go", "rationale": "Rubric chấp nhận No-go nếu nhất quán với số", "source_ref_ids": ["r10"]},
         ],
         "recorded_choice_id": "o2", "recorded_choice_ref_ids": ["r15"], "gap_ids": []},
    ],
    "interactions": [
        {"id": "i1", "type": "trace_flow", "title": "Theo dấu một request", "learning_goal_ids": ["q1"],
         "source_ref_ids": ["r7", "r8"], "basis": "hypothetical", "prompt": "Một request giả định đi qua các cổng.",
         "feedback": "Mỗi cổng có lý do dừng riêng.", "gap_ids": [],
         "payload": {"graph_id": "w2", "token_label": "Request minh họa", "steps": [
             {"node_id": "n4", "before": "Có khóa", "after": "Khóa hợp lệ", "explanation": "Sai khóa sẽ trả 401."},
             {"node_id": "n5", "before": "Khóa hợp lệ", "after": "Trong giới hạn", "explanation": "Vượt tốc độ trả 429."},
             {"node_id": "n6", "before": "Trong giới hạn", "after": "Còn ngân sách", "explanation": "Hết ngân sách thì dừng."},
             {"node_id": "n7", "before": "Còn ngân sách", "after": "Có câu trả lời", "explanation": "Mới gọi model ở bước này."},
         ]}},
        {"id": "i2", "type": "choose_explain", "title": "Mã lỗi khi sai khóa", "learning_goal_ids": ["q1"],
         "source_ref_ids": ["r8"], "basis": "source_backed", "prompt": "Request mang khóa sai sẽ nhận mã nào?",
         "feedback": "Đề ghi rõ mã cho từng cổng.", "gap_ids": [],
         "payload": {"options": [
             {"id": "a1", "label": "401", "feedback": "Đúng: đề ghi sai khóa trả 401.", "source_ref_ids": ["r8"]},
             {"id": "a2", "label": "429", "feedback": "429 là mã khi vượt tốc độ, không phải sai khóa.", "source_ref_ids": ["r8"]},
             {"id": "a3", "label": "200", "feedback": "200 nghĩa là đã qua mọi cổng.", "source_ref_ids": []},
         ], "accepted_option_ids": ["a1"], "explanation_prompt": "Vì sao bạn chọn mã này?"}},
        {"id": "i3", "type": "teach_back", "title": "Bảo vệ đề xuất", "learning_goal_ids": ["q1"],
         "source_ref_ids": ["r5", "r10"], "basis": "source_backed",
         "prompt": "Giải thích vì sao Go có điều kiện có thể hợp lý, và khi nào No-go hợp lý hơn.",
         "feedback": "Không có đáp án duy nhất: đối chiếu lập luận với checklist.", "gap_ids": ["g2"],
         "payload": {"question": "Bạn bảo vệ đề xuất thế nào trước hội đồng?",
                     "checklist": [
                         {"point": "Nêu số bất lợi kèm nhãn giả lập", "source_ref_ids": ["r5", "r13"]},
                         {"point": "Rubric chấp nhận No-go nếu nhất quán với số", "source_ref_ids": ["r10"]},
                     ],
                     "hint_levels": ["Bắt đầu từ số chi phí đã báo cáo.", "Nêu điều kiện nào khiến bạn đổi đề xuất."]}},
    ],
    "presentation": {
        "cards": [
            {"id": "p1", "title": "Bài toán", "claim_ids": [], "node_ids": [], "decision_ids": [], "evidence_ids": [],
             "speaker_prompts": ["Bài này cần quyết định điều gì?"], "source_ref_ids": ["r1"], "gap_ids": ["g1"]},
            {"id": "p2", "title": "Số chi phí đã báo cáo", "claim_ids": ["c2"], "node_ids": ["n2"], "decision_ids": [],
             "evidence_ids": ["e2"], "speaker_prompts": ["Số 4.472 đ đến từ đâu và vì sao là giả lập?"],
             "source_ref_ids": [], "gap_ids": ["g2"]},
            {"id": "p3", "title": "Đề xuất và giới hạn", "claim_ids": ["c4"], "node_ids": ["n3"], "decision_ids": ["dc1"],
             "evidence_ids": [], "speaker_prompts": ["Điều gì khiến bạn đổi đề xuất?"], "source_ref_ids": [], "gap_ids": []},
        ],
        "questions": [
            {"id": "qq1", "prompt": "Vì sao chi phí nên tính trên mỗi câu trả lời đúng?", "learning_goal_ids": ["q1"],
             "checklist": [{"point": "Tử số và mẫu số khác nhau", "source_ref_ids": ["r9"]}], "source_ref_ids": ["r9"]},
        ],
    },
    "gaps": [
        {"id": "g1", "scope_ids": ["q3"], "reason": "Báo cáo chưa có mục giới hạn.", "requested_evidence": "Thêm mục giới hạn."},
        {"id": "g2", "scope_ids": ["q1", "n2"], "reason": "Chưa có lượt đo thứ hai.", "requested_evidence": "Kết quả cấu hình retry thứ hai."},
    ],
    "conflicts": [
        {"id": "k1", "left_ref_ids": ["r6"], "right_ref_ids": ["r13"], "topic": "Ngưỡng 8.000 đ và cấu hình đã chọn",
         "state": "unresolved", "resolution_ref_ids": [], "human_resolution_note": None,
         "impact": "Chưa rõ cấu hình cuối có phải quay lại bước 2 hay không."},
    ],
    "validation": {"content_state": "incomplete",
                   "issues": [{"id": "iss-redact-s3", "code": "redacted", "severity": "info",
                               "message": "Đã che 1 dòng loại pii.", "scope_ids": ["s3"]}],
                   "coverage_summary": {"files_total": 3, "files_processed": 3, "lines_total": 21, "lines_processed": 21,
                                        "redacted_lines": 1, "unresolved_issue_ids": []},
                   "review_state": "unreviewed"},
}

META = {"generation_id": "deadbeef", "generated_at": "2026-11-28T12:00:00", "model": "fixture",
        "prompt_version": "fixture", "template_version": "learning-html-1", "fake": False}


def sample():
    return copy.deepcopy(LINES), copy.deepcopy(MODEL)
