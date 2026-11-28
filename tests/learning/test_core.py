"""Bộ kiểm learning-v1 phần lõi: reader, validator, pipeline (model kịch bản), dispatch agent.
Dữ liệu tổng hợp trong thư mục tạm — không dùng data BTC. Chạy: python -m unittest discover -s tests/learning -t .
"""
import copy
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (os.path.join(ROOT, "codebase"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault("MODEL_PROVIDER", "fake")

import learning_schema as S  # noqa: E402
import root_markdown as R  # noqa: E402
import learning_model as L  # noqa: E402
import fixture_data as F  # noqa: E402


def make_repo(files, subdirs=None):
    d = tempfile.mkdtemp(prefix="learn-test-")
    for name, content in files.items():
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(os.path.join(d, name), mode, **({} if mode == "wb" else {"encoding": "utf-8", "newline": "\n"})) as f:
            f.write(content)
    for sub, files2 in (subdirs or {}).items():
        os.makedirs(os.path.join(d, sub), exist_ok=True)
        for name, content in files2.items():
            with open(os.path.join(d, sub, name), "w", encoding="utf-8") as f:
                f.write(content)
    return d


BASIC = {
    "README.md": "# Lab thử: chi phí trợ lý\n\nMục tiêu: giải thích chi phí mỗi câu trả lời đúng.\n"
                 "Bước 1: kiểm công thức trên 3 ca mẫu.\nBước 2: so sánh 2 cấu hình retry.\n",
    "RUBRIC.MD": "# Rubric\nC1: công thức có tử số và mẫu số.\nBáo cáo cần nêu giới hạn.\n",
    "MISSION_ANSWERS.md": "# Bài làm\nChúng tôi đã kiểm công thức trên 3 ca mẫu.\nChi phí retry 2 lần: 4.472 đ [simulated].\n"
                          "Chưa có lượt đo thứ hai.\n",
    "INSTRUCTOR_GUIDE.md": "# Hướng dẫn chấm\nĐáp án mẫu: chi phí khoảng 4.500 đ.\n",
}


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.dirs = []

    def tearDown(self):
        for d in self.dirs:
            shutil.rmtree(d, ignore_errors=True)

    def repo(self, files, subdirs=None):
        d = make_repo(files, subdirs)
        self.dirs.append(d)
        return d

    def test_root_only_all_md_kept(self):
        d = self.repo(BASIC, {"docs": {"deep.md": "# không đọc\n"}})
        with open(os.path.join(d, "notes.txt"), "w") as f:
            f.write("x")
        s = R.read_root_markdown(R.RepoRef(d))
        names = sorted(m["name"] for m in s.manifest)
        self.assertEqual(names, sorted(BASIC))                      # MISSION_ANSWERS + INSTRUCTOR_GUIDE giữ, RUBRIC.MD giữ
        self.assertTrue(all(m["read_status"] == "read" for m in s.manifest))
        self.assertEqual(s.out_of_scope_count, 2)                   # docs/ + notes.txt, không đọc
        self.assertNotIn("deep.md", json.dumps(s.manifest))

    def test_hash_lines_and_snapshot_deterministic(self):
        d = self.repo(BASIC)
        a, b = R.read_root_markdown(R.RepoRef(d)), R.read_root_markdown(R.RepoRef(d))
        self.assertEqual(a.snapshot_id, b.snapshot_id)
        import hashlib
        raw = open(os.path.join(d, "README.md"), "rb").read()
        m = next(x for x in a.manifest if x["name"] == "README.md")
        self.assertEqual(m["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(m["line_count"], 5)
        with open(os.path.join(d, "README.md"), "a", encoding="utf-8") as f:
            f.write("thêm\n")
        self.assertNotEqual(R.read_root_markdown(R.RepoRef(d)).snapshot_id, a.snapshot_id)

    def test_encoding_bom_empty(self):
        d = self.repo({"A.md": b"\xef\xbb\xbf# BOM\nok\n", "B.md": b"# bad \xff\xfe\n", "C.md": b""})
        s = R.read_root_markdown(R.RepoRef(d))
        st = {m["name"]: m for m in s.manifest}
        self.assertEqual(st["A.md"]["read_status"], "read")
        self.assertEqual(s.lines[st["A.md"]["source_id"]][0], "# BOM")
        self.assertEqual(st["B.md"]["read_status"], "unreadable")
        self.assertIsNone(st["B.md"]["line_count"])
        self.assertEqual(st["C.md"]["read_status"], "empty")
        self.assertEqual(st["C.md"]["line_count"], 0)

    def test_over_limit_and_long_line(self):
        d = self.repo({"BIG.md": "x\n" * (R.MAX_FILE_BYTES // 2 + 10), "LONG.md": "# t\n" + "y" * 20000 + "\nz\n"})
        s = R.read_root_markdown(R.RepoRef(d))
        st = {m["name"]: m for m in s.manifest}
        self.assertEqual(st["BIG.md"]["read_status"], "over_limit")
        chunks, ledger = R.make_chunks(s)
        failed = [l for l in ledger if l["status"] == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["start_line"], 2)
        self.assertTrue(any(i["code"] == "line_over_limit" for i in s.issues))
        covered = {no for c in chunks for no, _ in c["body"]}
        self.assertEqual(covered, {1, 3})                           # dòng dài không bị cắt âm thầm

    def test_symlink_excluded(self):
        d = self.repo(BASIC)
        try:
            os.symlink(os.path.join(d, "README.md"), os.path.join(d, "LINK.md"))
        except (OSError, NotImplementedError):
            self.skipTest("hệ điều hành không cho tạo symlink")
        s = R.read_root_markdown(R.RepoRef(d))
        self.assertEqual(next(m for m in s.manifest if m["name"] == "LINK.md")["read_status"], "excluded")

    def test_redaction_keeps_line_numbers(self):
        key = "AIza" + "B" * 30
        d = self.repo({"TEAM.md": "# Team\n| STT | Họ tên | MSSV | Email | GitHub | Vai trò |\n|---|---|---|---|---|---|\n"
                                  "| 1 | Nguyễn Văn Thử | 2A202600001 | thu@example.com | thu-gh | Người làm |\n"
                                  "Liên hệ Nguyễn Văn Thử qua thu-gh.\n"
                                  "GEMINI_API_KEY=" + key + "\nURL: https://my-agent.up.railway.app/ask\n"
                                  "**Họ tên:** Trần Thị Mẫu — MSSV: 2A202600002\n"})
        s = R.read_root_markdown(R.RepoRef(d))
        lines = s.lines["s1"]
        text = "\n".join(lines)
        self.assertEqual(len(lines), 8)
        for secret in ("Nguyễn Văn Thử", "2A202600001", "thu@example.com", "thu-gh", key, "railway.app", "Trần Thị Mẫu",
                       "2A202600002"):
            self.assertNotIn(secret, text)
        self.assertIn("Người làm", lines[3])                        # cột vai trò giữ lại
        self.assertTrue(s.manifest[0]["redacted_ranges"])
        self.assertNotIn("thu@example.com", repr(s))

    def test_display_label_and_repr_no_path(self):
        d = self.repo(BASIC)
        ref = R.RepoRef(d)
        self.assertNotIn(d, repr(ref))
        self.assertEqual(R.read_root_markdown(ref).display_label, "Lab thử: chi phí trợ lý")

    def test_ingest_manifest_mismatch_and_excluded(self):
        d = self.repo(BASIC)
        R.register_ingest_manifest(d, {"channel": "zip", "wrapper_stripped": True,
                                       "accepted": [{"name": "README.md", "sha256": "0" * 64, "bytes": 1},
                                                    {"name": "GONE.md", "sha256": "1" * 64, "bytes": 1}],
                                       "excluded": [{"name": "HUGE.md", "reason": "over_limit"}],
                                       "out_of_scope_count": 3})
        s = R.read_root_markdown(R.RepoRef(d))
        codes = [i["code"] for i in s.issues]
        self.assertEqual(codes.count("ingest_mismatch"), 2)
        self.assertEqual(next(m for m in s.manifest if m["name"] == "HUGE.md")["read_status"], "over_limit")

    def test_chunks_cover_all_lines_with_context(self):
        body = "# Tiêu đề\n\n## Phần A\n" + "".join("| c%d | %d |\n" % (i, i) for i in range(400))
        body = body.replace("| c0 | 0 |\n", "| cột | giá trị |\n|---|---|\n", 1)
        d = self.repo({"T.md": body})
        s = R.read_root_markdown(R.RepoRef(d))
        chunks, _ = R.make_chunks(s, chunk_chars=2000)
        self.assertGreater(len(chunks), 2)
        covered = [no for c in chunks for no, _ in c["body"]]
        self.assertEqual(sorted(covered), list(range(1, s.manifest[0]["line_count"] + 1)))
        self.assertEqual(len(covered), len(set(covered)))           # context không tăng coverage
        later = chunks[2]
        self.assertTrue(any(t.startswith("| cột") for _, t in later["context"]))   # header bảng lặp lại
        self.assertIn("[NGỮ CẢNH LẶP", R.chunk_text(later, 400))

    def test_missing_dir(self):
        s = R.read_root_markdown(R.RepoRef(os.path.join(tempfile.gettempdir(), "khong-ton-tai-xyz")))
        self.assertEqual(s.manifest, [])
        self.assertTrue(any(i["code"] == "read_failed" for i in s.issues))


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.lines, self.model = F.sample()

    def codes(self, model=None):
        return {i.code for i in S.check_model(model or self.model, self.lines)}

    def test_fixture_valid(self):
        self.assertEqual(S.check_model(self.model, self.lines), [])

    def test_extra_key_and_wrong_type(self):
        self.model["claims"][0]["verified"] = True
        self.model["requirements"][0]["fulfillment"] = "verified_pass"
        self.assertIn("shape", self.codes())

    def test_fabricated_quote(self):
        self.model["source_refs"][0]["quote"] = "câu này không có trong file"
        self.assertIn("quote_mismatch", self.codes())

    def test_ref_out_of_range_and_redacted(self):
        self.model["source_refs"][0]["end_line"] = 99
        self.model["source_refs"].append({"id": "r99", "source_id": "s3", "start_line": 7, "end_line": 7,
                                          "quote": "[đã che: pii]", "role": "student_submission"})
        c = self.codes()
        self.assertIn("bad_source_ref", c)
        self.assertIn("redacted_quote", c)

    def test_dangling_id(self):
        self.model["claims"][1]["evidence_ids"].append("e-khong-co")
        self.assertIn("dangling_id", self.codes())

    def test_dependency_cycle(self):
        self.model["workflow"]["graphs"][0]["dependency_edges"].append(
            {"id": "d9", "from": "n3", "to": "n1", "reason": "x", "source_ref_ids": [], "basis": "inferred"})
        self.assertIn("dependency_cycle", self.codes())

    def test_choice_not_in_options(self):
        self.model["interactions"][1]["payload"]["accepted_option_ids"] = ["zz"]
        self.assertIn("choice_accepted", self.codes())

    def test_reported_claim_needs_submission(self):
        self.model["claims"][2]["source_ref_ids"] = ["r3"]        # đề, không phải bài làm
        self.assertIn("claim_role", self.codes())

    def test_requirement_not_upgraded_by_instruction(self):
        q = self.model["requirements"][2]
        self.model["evidence"].append({"id": "e9", "description": "Đề có mục giới hạn.", "status": "reported_in_markdown",
                                       "context_ids": [], "data_origin": "not_applicable",
                                       "simulation_label_required": False, "source_ref_ids": ["r11"],
                                       "external_ref": None, "limitation": None})
        q["fulfillment"], q["evidence_ids"] = "reported_complete", ["e9"]
        self.assertIn("fulfillment_role", self.codes())

    def test_verified_language_rejected(self):
        self.model["claims"][2]["text"] = "Nhóm đã xác minh công thức trên 3 ca mẫu."
        self.assertIn("verified_language", self.codes())
        self.model["claims"][2]["text"] = "Kết quả chưa xác minh: nhóm ghi đã kiểm 3 ca mẫu."
        self.assertNotIn("verified_language", self.codes())

    def test_number_and_unit_must_match_source(self):
        self.model["claims"][1]["text"] = "Nhóm báo cáo chi phí 4.999 đ."
        self.assertIn("number_not_in_source", self.codes())
        self.model["claims"][1]["text"] = "Nhóm báo cáo chi phí 4.472 USD."
        self.assertIn("unit_mismatch", self.codes())

    def test_simulation_label_required(self):
        self.model["claims"][1]["simulation_label_required"] = False
        self.assertIn("simulation_label", self.codes())
        fixed, log, ok = S.prune(self.model, self.lines)
        self.assertTrue(ok)
        self.assertTrue(next(c for c in fixed["claims"] if c["id"] == "c2")["simulation_label_required"])

    def test_inference_premise_cycle(self):
        c2 = self.model["claims"][1]
        c2["kind"], c2["premise_ids"] = "inference", ["c4"]
        self.assertIn("premise_cycle", self.codes())

    def test_human_resolution_forbidden(self):
        self.model["conflicts"][0]["state"] = "resolved_by_human"
        self.model["conflicts"][0]["human_resolution_note"] = "model tự giải"
        self.assertIn("human_resolution", self.codes())

    def test_recorded_choice_from_rubric_rejected(self):
        self.model["decisions"][0]["recorded_choice_ref_ids"] = ["r10"]
        self.assertIn("recorded_choice", self.codes())

    def test_prune_cascades_and_downgrades(self):
        self.model["claims"][1]["text"] = "Nhóm báo cáo chi phí 9.999 đ."       # c2 lỗi → bị bỏ
        self.model["conflicts"][0]["left_ref_ids"] = ["r8"]                   # mâu thuẫn chạm đáp án i2
        fixed, log, ok = S.prune(self.model, self.lines)
        self.assertTrue(ok)
        self.assertEqual(S.check_model(fixed, self.lines), [])
        self.assertNotIn("c2", {c["id"] for c in fixed["claims"]})
        self.assertNotIn("m1", {m["id"] for m in fixed["measurements"]})     # measurement treo theo claim bị bỏ
        card = next(c for c in fixed["presentation"]["cards"] if c["id"] == "p2")
        self.assertNotIn("c2", card["claim_ids"])
        i2 = next(i for i in fixed["interactions"] if i["id"] == "i2")
        self.assertEqual(i2["type"], "teach_back")                         # hạ thành câu thảo luận

    def test_auto_gap_for_required_without_evidence(self):
        q = self.model["requirements"][2]
        self.model["gaps"] = [g for g in self.model["gaps"] if g["id"] != "g1"]
        for c in self.model["presentation"]["cards"]:
            c["gap_ids"] = [g for g in c["gap_ids"] if g != "g1"]
        q["gap_ids"] = []
        fixed, _, ok = S.prune(self.model, self.lines)
        self.assertTrue(ok)
        self.assertTrue(next(x for x in fixed["requirements"] if x["id"] == "q3")["gap_ids"])

    def test_content_state(self):
        cov = S.coverage(self.model["source_manifest"])
        self.assertEqual(S.content_state(self.model, cov, []), "draft_ready")   # k1 không chạm nguồn mục tiêu học
        self.model["conflicts"][0]["left_ref_ids"] = ["r1"]                     # mâu thuẫn chạm mục tiêu học chính
        self.assertEqual(S.content_state(self.model, cov, []), "incomplete")
        self.model["conflicts"] = []
        for q in self.model["requirements"]:
            q["conflict_ids"] = []
        self.assertEqual(S.content_state(self.model, cov, []), "draft_ready")
        self.assertEqual(S.content_state(self.model, cov, [{"code": "fake_model", "severity": "warning"}]), "incomplete")
        self.model["source_manifest"][0]["processed_ranges"] = []
        self.assertEqual(S.content_state(self.model, S.coverage(self.model["source_manifest"]), []), "incomplete")


# ------------------------------------------------------------------ model kịch bản
LINE_RE = re.compile(r"^(\d+): (.*)$")
REF_RE = re.compile(r"^(R\d+) \| (.+?):(\d+)-(\d+) \| (\w+) \| «(.*)»$")


class ScriptedModel:
    """Thay call_model: trả JSON theo bước (nhận diện qua system prompt). Có thể cài lỗi."""

    def __init__(self, broken_extract_first=0, synth_a_patch=None, repair_reply=None, fail_all_extract=False):
        self.calls = []
        self.broken_extract_first = broken_extract_first
        self.synth_a_patch = synth_a_patch
        self.repair_reply = repair_reply
        self.fail_all_extract = fail_all_extract

    def __call__(self, system, user, *, timeout=None):
        self.calls.append((system[:40], timeout))
        if system == L.EXTRACT_SYSTEM:
            return self.reply(self.extract(user))
        if system == L.SYNTH_A_SYSTEM:
            return self.reply(self.synth_a(user))
        if system == L.SYNTH_B_SYSTEM:
            return self.reply(self.synth_b(user))
        if system == L.REPAIR_SYSTEM:
            return self.reply(self.repair_reply if self.repair_reply is not None else '{"replace":{},"delete_ids":[]}')
        raise AssertionError("system lạ")

    @staticmethod
    def reply(text):
        return {"text": text if isinstance(text, str) else json.dumps(text, ensure_ascii=False), "model": "scripted",
                "tokens_in": 1, "tokens_out": 1}

    def extract(self, user):
        if self.fail_all_extract:
            return "không phải JSON"
        if self.broken_extract_first > 0:
            self.broken_extract_first -= 1
            return "{hỏng"
        fname = re.search(r"### FILE (\S+)", user).group(1)
        role = {"README.md": "assignment", "RUBRIC.MD": "rubric", "MISSION_ANSWERS.md": "student_submission",
                "INSTRUCTOR_GUIDE.md": "instructor_example"}.get(fname, "unknown")
        refs, notes = [], []
        for line in user.splitlines():
            m = LINE_RE.match(line)
            if not m or not m.group(2).strip() or m.group(2).startswith("#"):
                continue
            rid = "r%s" % m.group(1)
            refs.append({"id": rid, "start_line": int(m.group(1)), "end_line": int(m.group(1)), "quote": m.group(2),
                         "role": role})
            kind = {"assignment": "learning_goal", "rubric": "assessment", "student_submission": "reported_result",
                    "instructor_example": "instructor_example"}[role] if role != "unknown" else "background"
            notes.append({"id": "n" + m.group(1), "kind": kind, "text": m.group(2), "ref_ids": [rid],
                          "data_origin": "lab_simulated" if "simulated" in m.group(2) else "not_applicable"})
        refs.append({"id": "bad", "start_line": 1, "end_line": 1, "quote": "trích dẫn bịa", "role": role})
        return {"refs": refs, "notes": notes}

    @staticmethod
    def pool(user):
        out = {}
        for line in user.splitlines():
            m = REF_RE.match(line)
            if m:
                out[m.group(1)] = {"file": m.group(2), "role": m.group(5), "quote": m.group(6)}
        return out

    def synth_a(self, user):
        pool = self.pool(user)
        find = lambda word: next(r for r, v in pool.items() if word in v["quote"])
        goal, step1, rub, lim = find("Mục tiêu"), find("Bước 1"), find("tử số"), find("giới hạn")
        sub1, sub2, sub3 = find("đã kiểm"), find("4.472"), find("lượt đo")
        inst = find("Đáp án mẫu")
        a = {
            "requirements": [
                {"id": "Q1", "text": "Giải thích chi phí mỗi câu trả lời đúng.", "category": "learning_goal",
                 "source_ref_ids": [goal], "applicability": "required", "condition": None, "scope": "toàn bài",
                 "overrides": [], "fulfillment": "reported_partial", "evidence_ids": ["E2"], "gap_ids": ["G1"],
                 "conflict_ids": []},
                {"id": "Q2", "text": "Kiểm công thức trên 3 ca mẫu.", "category": "deliverable",
                 "source_ref_ids": [step1, rub], "applicability": "required", "condition": None, "scope": "bước 1",
                 "overrides": [], "fulfillment": "reported_complete", "evidence_ids": ["E1"], "gap_ids": [],
                 "conflict_ids": []},
                {"id": "Q3", "text": "Báo cáo cần nêu giới hạn.", "category": "assessment", "source_ref_ids": [lim],
                 "applicability": "required", "condition": None, "scope": "báo cáo", "overrides": [],
                 "fulfillment": "not_reported", "evidence_ids": [], "gap_ids": [], "conflict_ids": []},
            ],
            "contexts": [{"id": "X1", "artifact_label": "Mô hình chi phí", "part_label": None, "checkpoint_label": None,
                          "environment": "giả lập", "scope": "retry 2 lần", "source_ref_ids": [sub2]}],
            "claims": [
                {"id": "C1", "text": "Bài làm ghi đã kiểm công thức trên 3 ca mẫu.", "kind": "reported", "context_ids": [],
                 "data_origin": "not_applicable", "simulation_label_required": False, "source_ref_ids": [sub1],
                 "evidence_ids": ["E1"], "requirement_ids": ["Q2"], "premise_ids": [], "assumption": None},
                {"id": "C2", "text": "Bài làm ghi chi phí retry 2 lần là 4.472 đ.", "kind": "reported", "context_ids": ["X1"],
                 "data_origin": "lab_simulated", "simulation_label_required": False, "source_ref_ids": [sub2],
                 "evidence_ids": ["E2"], "requirement_ids": ["Q1"], "premise_ids": [], "assumption": None},
                {"id": "C3", "text": "Đáp án mẫu của giảng viên ghi khoảng 4.500 đ.", "kind": "document_observation",
                 "context_ids": [], "data_origin": "not_applicable", "simulation_label_required": False,
                 "source_ref_ids": [inst], "evidence_ids": [], "requirement_ids": [], "premise_ids": [], "assumption": None},
            ],
            "evidence": [
                {"id": "E1", "description": "Bài làm tự ghi đã kiểm 3 ca mẫu.", "status": "reported_in_markdown",
                 "context_ids": [], "data_origin": "not_applicable", "simulation_label_required": False,
                 "source_ref_ids": [sub1], "external_ref": None, "limitation": "Chưa đọc code."},
                {"id": "E2", "description": "Số 4.472 đ ghi trong bài làm, nhãn simulated.", "status": "reported_in_markdown",
                 "context_ids": ["X1"], "data_origin": "lab_simulated", "simulation_label_required": True,
                 "source_ref_ids": [sub2, sub3], "external_ref": None, "limitation": None},
            ],
            "measurements": [{"id": "M1", "claim_id": "C2", "evidence_ids": ["E2"], "context_id": "X1", "method": None,
                              "value": "4.472", "unit": "đ", "operator": "=", "source_ref_ids": [sub2], "conflict_ids": []}],
            "gaps": [{"id": "G1", "scope_ids": ["Q1"], "reason": "Chưa có lượt đo thứ hai.", "requested_evidence": "Lượt đo 2."}],
            "conflicts": [],
        }
        if self.synth_a_patch:
            self.synth_a_patch(a, pool)
        return a

    def synth_b(self, user):
        pool = self.pool(user)
        step1 = next(r for r, v in pool.items() if "Bước 1" in v["quote"])
        step2 = next(r for r, v in pool.items() if "Bước 2" in v["quote"])
        node = lambda i, label, ref, reqs: {"id": i, "label": label, "purpose": label, "inputs": [], "outputs": [],
                                            "kind": "required_step", "requirement_ids": reqs, "claim_ids": [],
                                            "source_ref_ids": [ref], "gap_ids": []}
        return {
            "workflow": {"graphs": [{"id": "W1", "label": "Thứ tự làm bài", "graph_kind": "learning_order", "context_ids": [],
                                     "nodes": [node("N1", "Kiểm công thức", step1, ["Q2"]),
                                               node("N2", "So sánh retry", step2, ["Q1"])],
                                     "dependency_edges": [{"id": "D1", "from": "N1", "to": "N2", "reason": "thứ tự đề",
                                                           "source_ref_ids": [step1], "basis": "explicit"}],
                                     "feedback_edges": []}]},
            "decisions": [],
            "interactions": [
                {"id": "I1", "type": "trace_flow", "title": "Đi qua các bước", "learning_goal_ids": ["Q1"],
                 "source_ref_ids": [step1], "basis": "hypothetical", "prompt": "Ví dụ giả định.", "feedback": "ok",
                 "gap_ids": [], "payload": {"graph_id": "W1", "token_label": "Ca mẫu", "steps": [
                     {"node_id": "N1", "before": "chưa kiểm", "after": "đã kiểm", "explanation": "bước đầu"},
                     {"node_id": "N2", "before": "đã kiểm", "after": "có so sánh", "explanation": "bước sau"}]}},
                {"id": "I2", "type": "teach_back", "title": "Tự giải thích", "learning_goal_ids": ["Q1", "Q2"],
                 "source_ref_ids": [step2], "basis": "source_backed", "prompt": "Giải thích chi phí.", "feedback": "tự đối chiếu",
                 "gap_ids": [], "payload": {"question": "Vì sao tính theo câu đúng?",
                                            "checklist": [{"point": "tử số khác mẫu số", "source_ref_ids": [step2]}],
                                            "hint_levels": ["Nghĩ về lần chạy lỗi."]}},
            ],
            "presentation": {"cards": [{"id": "P1", "title": "Bài toán", "claim_ids": ["C2"], "node_ids": ["N1"],
                                        "decision_ids": [], "evidence_ids": ["E2"], "speaker_prompts": ["Số này từ đâu?"],
                                        "source_ref_ids": [], "gap_ids": []}],
                             "questions": []},
            "gaps": [],
        }


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.d = make_repo(BASIC, {"src": {"x.md": "# không đọc"}})
        self._orig = L.call_model

    def tearDown(self):
        L.call_model = self._orig
        shutil.rmtree(self.d, ignore_errors=True)

    def run_with(self, scripted, limits=None):
        L.call_model = scripted
        model, meta, snap, budget = L.build_learning(R.RepoRef(self.d), limits or L.Limits(workers=2))
        self.assertEqual(S.check_model(model, snap.lines), [])          # luôn hợp lệ sau chốt
        return model, meta, budget

    def test_happy_path_reported_not_upgraded(self):
        model, meta, budget = self.run_with(ScriptedModel())
        self.assertFalse(meta["fake"])
        self.assertEqual(model["validation"]["coverage_summary"]["files_processed"], 4)
        self.assertIn(model["validation"]["content_state"], ("draft_ready", "incomplete"))
        claims = {c["id"]: c for c in model["claims"]}
        self.assertEqual(claims["C1"]["kind"], "reported")
        self.assertTrue(claims["C2"]["simulation_label_required"])        # nhãn giả lập được bật lại
        self.assertTrue(all(e["status"] != "verified" for e in model["evidence"]))
        self.assertTrue(any(i["code"] == "refs_dropped" for i in model["validation"]["issues"]))  # ref bịa bị loại
        self.assertEqual(model["validation"]["review_state"], "unreviewed")
        q3 = next(q for q in model["requirements"] if q["id"] == "Q3")
        self.assertTrue(q3["gap_ids"])                                    # tự thêm gap
        for _, timeout in L.call_model.calls:
            self.assertIsNotNone(timeout)
            self.assertLessEqual(timeout, L.Limits().deadline_s)

    def test_json_broken_first_then_ok(self):
        model, _, budget = self.run_with(ScriptedModel(broken_extract_first=1))
        self.assertEqual(model["validation"]["coverage_summary"]["files_processed"], 4)

    def test_json_broken_everywhere_incomplete(self):
        model, _, _ = self.run_with(ScriptedModel(fail_all_extract=True))
        self.assertNotEqual(model["validation"]["content_state"], "draft_ready")
        self.assertTrue(any(i["code"] == "chunk_failed" for i in model["validation"]["issues"]))
        self.assertEqual(model["validation"]["coverage_summary"]["lines_processed"], 0)

    def test_bad_synthesis_objects_dropped_and_repair_json_broken(self):
        def patch(a, pool):
            goal = next(r for r, v in pool.items() if "Mục tiêu" in v["quote"])
            a["claims"].append({"id": "C9", "text": "Nhóm đã xác minh hệ thống chạy đúng.", "kind": "reported",
                                "context_ids": [], "data_origin": "not_applicable", "simulation_label_required": False,
                                "source_ref_ids": [goal], "evidence_ids": [], "requirement_ids": [], "premise_ids": [],
                                "assumption": None})
            a["claims"].append({"id": "C8", "text": "Ref bịa.", "kind": "document_observation", "context_ids": [],
                                "data_origin": "unknown", "simulation_label_required": False,
                                "source_ref_ids": ["R9999"], "evidence_ids": [], "requirement_ids": [],
                                "premise_ids": [], "assumption": None})
            a["requirements"][2]["fulfillment"] = "reported_complete"   # Q3 không có evidence
        model, _, budget = self.run_with(ScriptedModel(synth_a_patch=patch, repair_reply="không phải JSON"))
        ids = {c["id"] for c in model["claims"]}
        self.assertNotIn("C9", ids)
        self.assertNotIn("C8", ids)
        self.assertEqual(next(q for q in model["requirements"] if q["id"] == "Q3")["fulfillment"], "not_reported")
        codes = {i["code"] for i in model["validation"]["issues"]}
        self.assertIn("repair_failed", codes)
        repairs = sum(1 for s, _ in L.call_model.calls if s == L.REPAIR_SYSTEM[:40])
        self.assertLessEqual(repairs, 2)

    def test_budget_exhausted(self):
        model, _, budget = self.run_with(ScriptedModel(), L.Limits(max_calls=2, workers=1))
        self.assertLessEqual(budget.calls, 2)
        self.assertNotEqual(model["validation"]["content_state"], "draft_ready")
        self.assertTrue(any(i["code"] == "budget_exhausted" for i in model["validation"]["issues"]))

    def test_deadline(self):
        model, _, budget = self.run_with(ScriptedModel(), L.Limits(deadline_s=10, min_call_s=20))
        self.assertEqual(budget.calls, 0)
        self.assertNotEqual(model["validation"]["content_state"], "draft_ready")

    def test_requirements_only_repo_has_no_reported_claims(self):
        shutil.rmtree(self.d)
        self.d = make_repo({"README.md": BASIC["README.md"], "RUBRIC.MD": BASIC["RUBRIC.MD"],
                            "MISSION_ANSWERS.md": "# Bài làm\nđã kiểm (chưa có)\n4.472 x\nlượt đo\n",
                            "INSTRUCTOR_GUIDE.md": BASIC["INSTRUCTOR_GUIDE.md"]})

        class OnlySpec(ScriptedModel):
            def extract(self, user):
                out = super().extract(user)
                for r in out["refs"]:
                    if r["role"] == "student_submission":
                        r["role"] = "instruction"                  # không có bài làm thật
                return out
        model, _, _ = self.run_with(OnlySpec())
        self.assertFalse([c for c in model["claims"] if c["kind"] == "reported"])
        self.assertTrue(all(q["fulfillment"] == "not_reported" for q in model["requirements"]))

    def test_fake_mode_labelled(self):
        L.call_model = self._orig                                  # MODEL_PROVIDER=fake trong môi trường test
        import ai
        if ai.MODEL_PROVIDER != "fake":
            self.skipTest("cần MODEL_PROVIDER=fake")
        model, meta, snap, budget = L.build_learning(R.RepoRef(self.d))
        self.assertTrue(meta["fake"])
        self.assertEqual(budget.calls, 1)
        self.assertNotEqual(model["validation"]["content_state"], "draft_ready")
        self.assertTrue(any(i["code"] == "fake_model" for i in model["validation"]["issues"]))
        self.assertEqual(S.check_model(model, snap.lines), [])


class AgentDispatchTests(unittest.TestCase):
    def test_parse_errors_do_not_fall_back(self):
        import agent
        for bad in ('@learning-v1 {"repo_path": ""}', '@learning-v1 {"repo_path": "x", "mode": "a"}',
                    "@learning-v1 {không phải json", '@learning-v1{"repo_path":"x"}', '@learning-v1 ["x"]',
                    '@learning-v1 {"repo_path": 3}'):
            out = agent.answer(bad)["output"]
            self.assertIn("Lỗi đầu vào @learning-v1", out, bad)
            self.assertNotIn("Trang đóng vai", out)
        out = agent.answer('@learning-v1 {"repo_path": "a"}\nthêm dòng')["output"]
        self.assertIn("đúng một dòng", out)

    def test_parse_ok(self):
        import agent
        self.assertEqual(agent.parse_learning_input('@learning-v1 {"repo_path":"C:/a b/\\"q\\""}'), 'C:/a b/"q"')

    def test_plain_path_keeps_cp2_flow(self):
        import agent
        import ai
        if ai.MODEL_PROVIDER != "fake":
            self.skipTest("cần MODEL_PROVIDER=fake")
        sample = os.path.join(ROOT, "deploy", "sample_labs", "sample-react-agent")
        if not os.path.isdir(sample):
            self.skipTest("không có sample lab")
        out = agent.answer(sample)["output"]
        self.assertIn("Trang đóng vai: output/", out)
        self.assertNotIn("Trang học lại", out)


if __name__ == "__main__":
    unittest.main()
