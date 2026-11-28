"""Schema learning-v1 và validator bằng code (thư viện chuẩn) — docs/design/learning-html-contract.md §4–§6.

Không gọi model, không đọc file. Hai việc:
    check_model(model, lines_by_source)  → danh sách lỗi có cấu trúc (không sửa model)
    finalize(model, lines_by_source, ...) → bỏ object lỗi + tham chiếu treo (lặp tới ổn định), hạ cấp tương tác
                                            thiếu căn cứ, tự thêm gap cho yêu cầu bắt buộc thiếu bằng chứng,
                                            tính validation {content_state, issues, coverage_summary, review_state}.

Chốt semantic (hợp đồng §4): trích dẫn khớp chỉ chứng minh đoạn đó tồn tại. Validator kiểm thêm vai trò nguồn,
số/đơn vị xuất hiện trong nguồn, ngôn ngữ "đã xác minh", nhãn giả lập — vẫn cần người duyệt.
"""
import copy
import re

SCHEMA_VERSION = "learning-v1"
REDACT_MARK = "[đã che"          # mọi đoạn che đều bắt đầu bằng chuỗi này (root_markdown.py)

# ---- giới hạn độ dài (cấu hình MVP, không phải số đo) ----
MAX_TEXT = 1200
MAX_QUOTE = 400
MAX_ARRAY = 600
MAX_ID = 64

TOP_KEYS = ("schema_version", "repo_snapshot", "source_manifest", "source_refs", "requirements", "contexts",
            "claims", "evidence", "measurements", "workflow", "decisions", "interactions", "presentation",
            "gaps", "conflicts", "validation")

ROLES = ("assignment", "rule", "rubric", "instruction", "student_submission", "instructor_example", "background", "unknown")
REQ_CATEGORY = ("learning_goal", "deliverable", "constraint", "assessment")
APPLICABILITY = ("required", "optional", "conditional", "unresolved")
FULFILLMENT = ("not_reported", "reported_complete", "reported_partial", "reported_not_done", "conflicting")
CLAIM_KIND = ("required", "reported", "document_observation", "inference", "hypothetical")
EVIDENCE_STATUS = ("reported_in_markdown", "embedded_record_unverified", "referenced_unread", "missing", "conflicting")
DATA_ORIGIN = ("lab_simulated", "student_reported_measurement", "teaching_hypothetical", "unknown", "not_applicable")
OPERATORS = ("<", "<=", ">", ">=", "=")
GRAPH_KIND = ("learning_order", "system_flow", "decision_process")
NODE_KIND = ("required_step", "reported_step", "inferred_step")
BASIS_EDGE = ("explicit", "inferred")
CONFLICT_STATE = ("unresolved", "resolved_by_source", "resolved_by_human")
INTERACTION_TYPE = ("trace_flow", "order_dependencies", "choose_explain", "teach_back")
INTERACTION_BASIS = ("source_backed", "hypothetical")
READ_STATUS = ("read", "empty", "unreadable", "excluded", "over_limit", "changed")
SEVERITY = ("info", "warning", "error")
CONTENT_STATE = ("blocked", "incomplete", "draft_ready")
REVIEW_STATE = ("unreviewed", "needs_review")
REQUIREMENT_ROLES = ("assignment", "rule", "rubric", "instruction")

# ---- shape: field → kiểu. Kiểu: "str", "str?", "int", "int?", "bool", "ids", "strs", enum tuple, ("enum?", tuple),
#      ("list", shape), ("obj", shape), "any_obj" ----
RANGE = {"start_line": "int", "end_line": "int"}
ISSUE = {"id": "str", "code": "str", "severity": SEVERITY, "message": "str", "scope_ids": "ids"}
SHAPES = {
    "repo_snapshot": {"snapshot_id": "str", "display_label": "str", "revision": "str?"},
    "source_manifest": {"source_id": "str", "name": "str", "sha256": "str?", "line_count": "int?",
                        "read_status": READ_STATUS, "processed_ranges": ("list", RANGE),
                        "redacted_ranges": ("list", RANGE), "issues": "ids"},
    "source_refs": {"id": "str", "source_id": "str", "start_line": "int", "end_line": "int", "quote": "str", "role": ROLES},
    "requirements": {"id": "str", "text": "str", "category": REQ_CATEGORY, "source_ref_ids": "ids",
                     "applicability": APPLICABILITY, "condition": "str?", "scope": "str",
                     "overrides": ("list", {"requirement_id": "str", "source_ref_ids": "ids"}),
                     "fulfillment": FULFILLMENT, "evidence_ids": "ids", "gap_ids": "ids", "conflict_ids": "ids"},
    "contexts": {"id": "str", "artifact_label": "str?", "part_label": "str?", "checkpoint_label": "str?",
                 "environment": "str?", "scope": "str?", "source_ref_ids": "ids"},
    "claims": {"id": "str", "text": "str", "kind": CLAIM_KIND, "context_ids": "ids", "data_origin": DATA_ORIGIN,
               "simulation_label_required": "bool", "source_ref_ids": "ids", "evidence_ids": "ids",
               "requirement_ids": "ids", "premise_ids": "ids", "assumption": "str?"},
    "evidence": {"id": "str", "description": "str", "status": EVIDENCE_STATUS, "context_ids": "ids",
                 "data_origin": DATA_ORIGIN, "simulation_label_required": "bool", "source_ref_ids": "ids",
                 "external_ref": "str?", "limitation": "str?"},
    "measurements": {"id": "str", "claim_id": "str", "evidence_ids": "ids", "context_id": "str", "method": "str?",
                     "value": "str", "unit": "str?", "operator": ("enum?", OPERATORS), "source_ref_ids": "ids",
                     "conflict_ids": "ids"},
    "graph": {"id": "str", "label": "str", "graph_kind": GRAPH_KIND, "context_ids": "ids",
              "nodes": ("list", {"id": "str", "label": "str", "purpose": "str", "inputs": "strs", "outputs": "strs",
                                 "kind": NODE_KIND, "requirement_ids": "ids", "claim_ids": "ids",
                                 "source_ref_ids": "ids", "gap_ids": "ids"}),
              "dependency_edges": ("list", {"id": "str", "from": "str", "to": "str", "reason": "str",
                                            "source_ref_ids": "ids", "basis": BASIS_EDGE}),
              "feedback_edges": ("list", {"id": "str", "from": "str", "to": "str", "condition": "str",
                                          "stop_condition": "str", "source_ref_ids": "ids", "basis": BASIS_EDGE})},
    "decisions": {"id": "str", "question": "str", "requirement_ids": "ids", "source_ref_ids": "ids",
                  "options": ("list", {"id": "str", "label": "str", "rationale": "str", "source_ref_ids": "ids"}),
                  "recorded_choice_id": "str?", "recorded_choice_ref_ids": "ids", "gap_ids": "ids"},
    "interactions": {"id": "str", "type": INTERACTION_TYPE, "title": "str", "learning_goal_ids": "ids",
                     "source_ref_ids": "ids", "basis": INTERACTION_BASIS, "prompt": "str", "feedback": "str",
                     "gap_ids": "ids", "payload": "any_obj"},
    "cards": {"id": "str", "title": "str", "claim_ids": "ids", "node_ids": "ids", "decision_ids": "ids",
              "evidence_ids": "ids", "speaker_prompts": "strs", "source_ref_ids": "ids", "gap_ids": "ids"},
    "questions": {"id": "str", "prompt": "str", "learning_goal_ids": "ids",
                  "checklist": ("list", {"point": "str", "source_ref_ids": "ids"}), "source_ref_ids": "ids"},
    "gaps": {"id": "str", "scope_ids": "ids", "reason": "str", "requested_evidence": "str"},
    "conflicts": {"id": "str", "left_ref_ids": "ids", "right_ref_ids": "ids", "topic": "str", "state": CONFLICT_STATE,
                  "resolution_ref_ids": "ids", "human_resolution_note": "str?", "impact": "str"},
    "validation": {"content_state": CONTENT_STATE, "issues": ("list", ISSUE),
                   "coverage_summary": ("obj", {"files_total": "int", "files_processed": "int", "lines_total": "int",
                                                "lines_processed": "int", "redacted_lines": "int",
                                                "unresolved_issue_ids": "ids"}),
                   "review_state": REVIEW_STATE},
}
PAYLOAD_SHAPES = {
    "trace_flow": {"graph_id": "str", "token_label": "str",
                   "steps": ("list", {"node_id": "str", "before": "str", "after": "str", "explanation": "str"})},
    "order_dependencies": {"graph_id": "str", "node_ids": "ids", "edge_ids": "ids"},
    "choose_explain": {"options": ("list", {"id": "str", "label": "str", "feedback": "str", "source_ref_ids": "ids"}),
                       "accepted_option_ids": "ids", "explanation_prompt": "str"},
    "teach_back": {"question": "str", "checklist": ("list", {"point": "str", "source_ref_ids": "ids"}),
                   "hint_levels": "strs"},
}
# section (danh sách ở model) → shape
LIST_SECTIONS = ("source_refs", "requirements", "contexts", "claims", "evidence", "measurements", "decisions",
                 "interactions", "gaps", "conflicts")

VERIFIED_RE = re.compile(
    r"(?<!chưa )(?<!không )(?<!chưa được )(?<!không được )\bđã (?:được )?(?:xác minh|kiểm chứng|chứng nhận)"
    r"|(?<!un)(?<!not )(?<!never )\b(?:independently )?verified\b|\bđã chạy (?:lại )?và (?:xác minh|kiểm chứng)",
    re.IGNORECASE)
NUM_RE = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*(?![\w])")
UNITS = ("gb", "mb", "kb", "ms", "s", "%", "đ", "vnd", "usd", "rps", "req/s", "điểm", "lần", "token", "tokens")
SIM_HINT_RE = re.compile(r"simulated|giả lập|_simulated", re.IGNORECASE)
EXTERNAL_REF_RE = re.compile(r"^(?![A-Za-z]:)(?!/)(?!\\)[A-Za-z0-9_\-. /]+$")


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _numbers(text):
    """Số trong chuỗi, bỏ số 1 chữ số đứng riêng (thứ tự bước, 'Part 6') để giảm báo nhầm."""
    out = []
    for m in NUM_RE.finditer(text or ""):
        tok = m.group(0).rstrip(".,")
        if len(re.sub(r"\D", "", tok)) >= 2 or re.search(r"[.,]", tok):
            out.append((tok, m.end()))
    return out


def _unit_after(text, end):
    m = re.match(r"\s*(gb|mb|kb|ms|%|đ|vnd|usd|rps|req/s)\b", text[end:end + 8], re.IGNORECASE) or \
        re.match(r"\s*(%)", text[end:end + 3])
    return m.group(1).lower() if m else None


class Issue:
    """Lỗi kiểm có cấu trúc; object_id là ID object bị ảnh hưởng (None = toàn model)."""

    def __init__(self, code, message, object_id=None, severity="error", section=None):
        self.code, self.message, self.object_id, self.severity, self.section = code, message, object_id, severity, section

    def as_dict(self):
        return {"code": self.code, "message": self.message, "object_id": self.object_id,
                "severity": self.severity, "section": self.section}

    def __repr__(self):
        return "Issue(%s, %s, %s)" % (self.code, self.object_id, self.message[:80])


# ------------------------------------------------------------------ kiểm kiểu
def _check_value(spec, value, path, errs):
    if isinstance(spec, tuple) and spec and spec[0] in ("list", "obj", "enum?"):
        kind = spec[0]
        if kind == "enum?":
            if value is not None and value not in spec[1]:
                errs.append("%s: giá trị %r ngoài enum %s" % (path, value, "|".join(spec[1])))
            return
        if kind == "obj":
            _check_obj(spec[1], value, path, errs)
            return
        if not isinstance(value, list):
            errs.append("%s: phải là mảng" % path)
            return
        if len(value) > MAX_ARRAY:
            errs.append("%s: vượt %d phần tử" % (path, MAX_ARRAY))
        for i, v in enumerate(value):
            _check_obj(spec[1], v, "%s[%d]" % (path, i), errs)
        return
    if isinstance(spec, tuple):          # enum bắt buộc
        if value not in spec:
            errs.append("%s: giá trị %r ngoài enum %s" % (path, value, "|".join(spec)))
        return
    if spec in ("str", "str?"):
        if value is None and spec == "str?":
            return
        if not isinstance(value, str):
            errs.append("%s: phải là chuỗi" % path)
        elif spec == "str" and not value.strip():
            errs.append("%s: chuỗi rỗng" % path)
        elif len(value) > MAX_TEXT:
            errs.append("%s: dài quá %d ký tự" % (path, MAX_TEXT))
        return
    if spec in ("int", "int?"):
        if value is None and spec == "int?":
            return
        if not isinstance(value, int) or isinstance(value, bool):
            errs.append("%s: phải là số nguyên" % path)
        return
    if spec == "bool":
        if not isinstance(value, bool):
            errs.append("%s: phải là boolean" % path)
        return
    if spec in ("ids", "strs"):
        if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
            errs.append("%s: phải là mảng chuỗi không rỗng" % path)
        elif len(value) > MAX_ARRAY:
            errs.append("%s: vượt %d phần tử" % (path, MAX_ARRAY))
        elif spec == "ids" and len(set(value)) != len(value):
            errs.append("%s: ID lặp" % path)
        elif spec == "strs" and any(len(x) > MAX_TEXT for x in value):
            errs.append("%s: phần tử dài quá %d ký tự" % (path, MAX_TEXT))
        return
    if spec == "any_obj":
        if not isinstance(value, dict):
            errs.append("%s: phải là object" % path)
        return
    raise AssertionError("spec lạ %r" % (spec,))


def _check_obj(shape, obj, path, errs):
    if not isinstance(obj, dict):
        errs.append("%s: phải là object" % path)
        return
    extra = sorted(set(obj) - set(shape))
    missing = sorted(set(shape) - set(obj))
    if extra:
        errs.append("%s: khóa lạ %s" % (path, ", ".join(extra)))
    if missing:
        errs.append("%s: thiếu khóa %s" % (path, ", ".join(missing)))
    for k, spec in shape.items():
        if k in obj:
            _check_value(spec, obj[k], "%s.%s" % (path, k), errs)


def shape_errors(section, obj):
    """Lỗi kiểu của một object thuộc section (dùng cả cho bản vá từ model)."""
    errs = []
    shape = SHAPES["graph" if section == "graphs" else section]
    _check_obj(shape, obj, section, errs)
    if section == "interactions" and isinstance(obj, dict) and obj.get("type") in PAYLOAD_SHAPES:
        _check_obj(PAYLOAD_SHAPES[obj["type"]], obj.get("payload"), "interactions.payload", errs)
    if isinstance(obj, dict) and isinstance(obj.get("id"), str):
        if len(obj["id"]) > MAX_ID or not re.fullmatch(r"[A-Za-z0-9_.:-]+", obj["id"]):
            errs.append("%s.id: ID chỉ gồm chữ/số/_.:- và ≤%d ký tự" % (section, MAX_ID))
    if section == "source_refs" and isinstance(obj, dict) and isinstance(obj.get("quote"), str) \
            and len(obj["quote"]) > MAX_QUOTE:
        errs.append("source_refs.quote: dài quá %d ký tự" % MAX_QUOTE)
    return errs


# ------------------------------------------------------------------ chỉ mục
class Index:
    def __init__(self, model):
        self.model = model
        self.by_id = {}           # id → (section, obj)
        self.dupes = []
        self.graph_of = {}        # node/edge id → graph id

        def add(section, obj):
            oid = obj.get("id") if isinstance(obj, dict) else None
            if not isinstance(oid, str):
                return
            if oid in self.by_id:
                self.dupes.append(oid)
            else:
                self.by_id[oid] = (section, obj)

        for sec in LIST_SECTIONS:
            for o in model.get(sec) or []:
                add(sec, o)
        for g in (model.get("workflow") or {}).get("graphs") or []:
            add("graphs", g)
            if not isinstance(g, dict):
                continue
            for n in g.get("nodes") or []:
                add("nodes", n)
                if isinstance(n, dict) and isinstance(n.get("id"), str):
                    self.graph_of[n["id"]] = g.get("id")
            for e in (g.get("dependency_edges") or []):
                add("dependency_edges", e)
                if isinstance(e, dict) and isinstance(e.get("id"), str):
                    self.graph_of[e["id"]] = g.get("id")
            for e in (g.get("feedback_edges") or []):
                add("feedback_edges", e)
                if isinstance(e, dict) and isinstance(e.get("id"), str):
                    self.graph_of[e["id"]] = g.get("id")
        pres = model.get("presentation") or {}
        for c in pres.get("cards") or []:
            add("cards", c)
        for q in pres.get("questions") or []:
            add("questions", q)
        self.sources = {m.get("source_id"): m for m in model.get("source_manifest") or [] if isinstance(m, dict)}

    def sec(self, oid):
        return self.by_id.get(oid, (None, None))[0]

    def get(self, oid):
        return self.by_id.get(oid, (None, None))[1]

    def is_(self, oid, *sections):
        return self.sec(oid) in sections

    def refs(self, ids):
        return [self.get(r) for r in ids or [] if self.is_(r, "source_refs")]

    def quotes(self, ids):
        return " ".join(r.get("quote", "") for r in self.refs(ids))


# ------------------------------------------------------------------ kiểm toàn model
def check_model(model, lines_by_source):
    """Trả danh sách Issue. lines_by_source: {source_id: [dòng đã che]} — snapshot đã đọc trong phiên."""
    issues = []
    add = lambda code, msg, oid=None, sev="error", sec=None: issues.append(Issue(code, msg, oid, sev, sec))

    if not isinstance(model, dict):
        return [Issue("structure", "model phải là object")]
    extra = sorted(set(model) - set(TOP_KEYS))
    missing = sorted(set(TOP_KEYS) - set(model))
    if extra:
        add("structure", "khóa top-level lạ: " + ", ".join(extra))
    if missing:
        add("structure", "thiếu khóa top-level: " + ", ".join(missing))
        return issues
    if model["schema_version"] != SCHEMA_VERSION:
        add("structure", "schema_version phải là " + SCHEMA_VERSION)
    for sec in ("repo_snapshot", "validation"):
        for e in shape_errors(sec, model[sec]):
            add("structure", e, None, "error", sec)
    for m in model["source_manifest"] if isinstance(model["source_manifest"], list) else []:
        for e in shape_errors("source_manifest", m):
            add("structure", e, None, "error", "source_manifest")
    for sec in LIST_SECTIONS:
        if not isinstance(model[sec], list):
            add("structure", "%s phải là mảng" % sec)
            continue
        for o in model[sec]:
            for e in shape_errors(sec, o):
                add("shape", e, o.get("id") if isinstance(o, dict) else None, "error", sec)
    wf = model["workflow"]
    if not isinstance(wf, dict) or set(wf) != {"graphs"} or not isinstance(wf.get("graphs"), list):
        add("structure", "workflow phải là {graphs: [...]}")
    else:
        for g in wf["graphs"]:
            for e in shape_errors("graphs", g):
                add("shape", e, g.get("id") if isinstance(g, dict) else None, "error", "graphs")
    pres = model["presentation"]
    if not isinstance(pres, dict) or set(pres) != {"cards", "questions"}:
        add("structure", "presentation phải là {cards, questions}")
    else:
        for sec in ("cards", "questions"):
            if not isinstance(pres[sec], list):
                add("structure", "presentation.%s phải là mảng" % sec)
                continue
            for o in pres[sec]:
                for e in shape_errors(sec, o):
                    add("shape", e, o.get("id") if isinstance(o, dict) else None, "error", sec)
    if any(i.code == "structure" for i in issues):
        return issues

    shape_bad = {i.object_id for i in issues if i.code == "shape"}
    ix = Index(model)
    for d in ix.dupes:
        add("duplicate_id", "ID lặp: " + d, d)

    def ok(o):
        return isinstance(o, dict) and o.get("id") not in shape_bad

    def need(oid, ids, *sections, field="ids"):
        for r in ids or []:
            if not ix.is_(r, *sections):
                add("dangling_id", "%s trỏ tới ID không tồn tại hoặc sai loại: %s" % (field, r), oid)

    def refs_ok(oid, ids, field="source_ref_ids"):
        need(oid, ids, "source_refs", field=field)

    def verified_lang(oid, *texts):
        for t in texts:
            if isinstance(t, str) and VERIFIED_RE.search(t):
                add("verified_language", "Không được khẳng định đã xác minh khi chỉ đọc Markdown: «%s»" % t[:120], oid)

    def numbers_supported(oid, text, support):
        sup = norm(support)
        for tok, end in _numbers(text):
            if tok not in sup and tok.replace(",", ".") not in sup and tok.replace(".", ",") not in sup:
                add("number_not_in_source", "Số %s không có trong nguồn được dẫn" % tok, oid)
                continue
            unit = _unit_after(text, end)
            if unit:
                pat = re.escape(tok) + r"\s*" + re.escape(unit)
                if not re.search(pat, sup, re.IGNORECASE) and re.search(re.escape(tok) + r"\s*(gb|mb|kb|ms|%|đ|usd)",
                                                                       sup, re.IGNORECASE):
                    add("unit_mismatch", "Số %s đi với đơn vị %s nhưng nguồn ghi đơn vị khác" % (tok, unit), oid)

    # -- source refs
    for r in model["source_refs"]:
        if not ok(r):
            continue
        src = ix.sources.get(r["source_id"])
        if not src or src.get("read_status") != "read":
            add("bad_source_ref", "source_id %s không thuộc file đã đọc" % r["source_id"], r["id"])
            continue
        lines = lines_by_source.get(r["source_id"])
        a, b = r["start_line"], r["end_line"]
        if lines is None or not (1 <= a <= b <= len(lines)):
            add("bad_source_ref", "dòng %s-%s ngoài file (%s dòng)" % (a, b, len(lines or [])), r["id"])
            continue
        if REDACT_MARK in r["quote"]:
            add("redacted_quote", "trích dẫn chạm vùng đã che", r["id"])
            continue
        if not norm(r["quote"]) or norm(r["quote"]) not in norm(" ".join(lines[a - 1:b])):
            add("quote_mismatch", "trích dẫn không khớp nguyên văn dòng %d-%d" % (a, b), r["id"])

    # -- gaps
    for gp in model["gaps"]:
        if ok(gp):
            for s in gp["scope_ids"]:
                if s not in ix.by_id and s not in ix.sources:
                    add("dangling_id", "gap.scope_ids trỏ ID không tồn tại: " + s, gp["id"])

    # -- conflicts
    for c in model["conflicts"]:
        if not ok(c):
            continue
        refs_ok(c["id"], c["left_ref_ids"], "left_ref_ids")
        refs_ok(c["id"], c["right_ref_ids"], "right_ref_ids")
        refs_ok(c["id"], c["resolution_ref_ids"], "resolution_ref_ids")
        if not c["left_ref_ids"] or not c["right_ref_ids"]:
            add("conflict_refs", "mâu thuẫn cần nguồn cả hai phía", c["id"])
        if c["state"] == "resolved_by_human" or c["human_resolution_note"] is not None:
            add("human_resolution", "MVP không có bước người giải quyết: model/code không được tạo resolved_by_human "
                                    "hoặc human_resolution_note", c["id"])
        if c["state"] == "resolved_by_source" and not c["resolution_ref_ids"]:
            add("conflict_resolution", "resolved_by_source cần nguồn chỉ dẫn ưu tiên", c["id"])

    # -- contexts
    for cx in model["contexts"]:
        if ok(cx):
            refs_ok(cx["id"], cx["source_ref_ids"])

    # -- evidence
    for ev in model["evidence"]:
        if not ok(ev):
            continue
        refs_ok(ev["id"], ev["source_ref_ids"])
        need(ev["id"], ev["context_ids"], "contexts", field="context_ids")
        verified_lang(ev["id"], ev["description"], ev["limitation"])
        if ev["status"] in ("reported_in_markdown", "embedded_record_unverified", "conflicting") and not ev["source_ref_ids"]:
            add("evidence_refs", "bằng chứng %s cần nguồn trong Markdown" % ev["status"], ev["id"])
        if ev["status"] == "referenced_unread" and not ev["external_ref"]:
            add("evidence_external", "referenced_unread cần external_ref", ev["id"])
        if ev["status"] == "missing" and not ev["limitation"]:
            add("evidence_missing", "bằng chứng missing cần limitation giải thích", ev["id"])
        if ev["external_ref"] is not None and (not EXTERNAL_REF_RE.match(ev["external_ref"]) or ".." in ev["external_ref"]
                                              or re.match(r"(?i)^[a-z][a-z0-9+.-]*:", ev["external_ref"])):
            add("evidence_external", "external_ref phải là tên file tương đối đã làm sạch", ev["id"])
        if ev["data_origin"] in ("lab_simulated", "teaching_hypothetical") and not ev["simulation_label_required"]:
            add("simulation_label", "dữ liệu %s phải giữ nhãn giả lập" % ev["data_origin"], ev["id"])
        numbers_supported(ev["id"], ev["description"], ix.quotes(ev["source_ref_ids"]))

    # -- requirements
    for q in model["requirements"]:
        if not ok(q):
            continue
        refs_ok(q["id"], q["source_ref_ids"])
        need(q["id"], q["evidence_ids"], "evidence", field="evidence_ids")
        need(q["id"], q["gap_ids"], "gaps", field="gap_ids")
        need(q["id"], q["conflict_ids"], "conflicts", field="conflict_ids")
        if not q["source_ref_ids"]:
            add("requirement_refs", "yêu cầu cần nguồn đề/rubric", q["id"])
        elif not any(r.get("role") in REQUIREMENT_ROLES + ("instructor_example",) for r in ix.refs(q["source_ref_ids"])):
            add("requirement_role", "yêu cầu phải dẫn đoạn đề/luật/rubric/hướng dẫn, không chỉ bài làm", q["id"])
        if q["applicability"] == "conditional" and not (q["condition"] or "").strip():
            add("requirement_condition", "yêu cầu conditional cần condition", q["id"])
        for ov in q["overrides"]:
            if ov["requirement_id"] == q["id"] or not ix.is_(ov["requirement_id"], "requirements"):
                add("dangling_id", "override trỏ yêu cầu không hợp lệ: " + ov["requirement_id"], q["id"])
            if not ov["source_ref_ids"]:
                add("override_refs", "override cần nguồn chứng minh đúng cặp", q["id"])
            refs_ok(q["id"], ov["source_ref_ids"], "overrides.source_ref_ids")
        f = q["fulfillment"]
        if f != "not_reported":
            if not q["evidence_ids"]:
                add("fulfillment_evidence", "fulfillment %s cần evidence" % f, q["id"])
            else:
                ev_refs = [r for e in q["evidence_ids"] if ix.is_(e, "evidence") for r in ix.refs(ix.get(e)["source_ref_ids"])]
                if not any(r.get("role") == "student_submission" for r in ev_refs):
                    add("fulfillment_role", "trạng thái tự báo cáo phải dựa trên đoạn bài làm (student_submission), "
                                            "không dựa trên đề/mẫu giảng viên", q["id"])
        if f in ("reported_partial", "reported_not_done") and not q["gap_ids"]:
            add("fulfillment_gap", "fulfillment %s cần gap" % f, q["id"])
        if f == "conflicting" and not q["conflict_ids"]:
            add("fulfillment_conflict", "fulfillment conflicting cần conflict", q["id"])

    # -- claims
    claims = {c["id"]: c for c in model["claims"] if ok(c)}
    for c in claims.values():
        refs_ok(c["id"], c["source_ref_ids"])
        need(c["id"], c["evidence_ids"], "evidence", field="evidence_ids")
        need(c["id"], c["requirement_ids"], "requirements", field="requirement_ids")
        need(c["id"], c["context_ids"], "contexts", field="context_ids")
        need(c["id"], c["premise_ids"], "claims", field="premise_ids")
        verified_lang(c["id"], c["text"])
        roles = {r.get("role") for r in ix.refs(c["source_ref_ids"])}
        k = c["kind"]
        if k in ("required", "reported", "document_observation") and not c["source_ref_ids"]:
            add("claim_refs", "claim %s cần nguồn" % k, c["id"])
        if k == "reported" and "student_submission" not in roles:
            add("claim_role", "claim reported phải dẫn đoạn bài làm (student_submission)", c["id"])
        if k == "required" and not roles & set(REQUIREMENT_ROLES):
            add("claim_role", "claim required phải dẫn đoạn đề/luật/rubric/hướng dẫn", c["id"])
        if k == "inference" and not c["premise_ids"]:
            add("claim_premise", "inference cần premise_ids", c["id"])
        if c["id"] in c["premise_ids"]:
            add("claim_premise", "claim không được tự làm premise", c["id"])
        if k == "hypothetical" and not (c["assumption"] or "").strip():
            add("claim_assumption", "hypothetical cần assumption", c["id"])
        if c["data_origin"] in ("lab_simulated", "teaching_hypothetical") and not c["simulation_label_required"]:
            add("simulation_label", "claim %s phải giữ nhãn giả lập" % c["data_origin"], c["id"])
        if any(ix.get(e)["simulation_label_required"] for e in c["evidence_ids"] if ix.is_(e, "evidence")) \
                and not c["simulation_label_required"]:
            add("simulation_label", "claim dẫn bằng chứng giả lập phải kế thừa nhãn", c["id"])
        if k not in ("hypothetical",):
            support = ix.quotes(c["source_ref_ids"]) + " " + " ".join(
                ix.quotes(ix.get(e)["source_ref_ids"]) + " " + ix.get(e)["description"]
                for e in c["evidence_ids"] if ix.is_(e, "evidence"))
            if k == "inference":
                support += " " + " ".join(claims[p]["text"] for p in c["premise_ids"] if p in claims)
            numbers_supported(c["id"], c["text"], support)
    # premise DAG
    state = {}

    def visit(cid, stack):
        state[cid] = 1
        for p in claims[cid]["premise_ids"]:
            if p not in claims:
                continue
            if state.get(p) == 1:
                add("premise_cycle", "chu trình premise: " + " → ".join(stack + [p]), cid)
            elif not state.get(p):
                visit(p, stack + [p])
        state[cid] = 2

    for cid in claims:
        if not state.get(cid):
            visit(cid, [cid])

    # -- measurements
    for m in model["measurements"]:
        if not ok(m):
            continue
        if not ix.is_(m["claim_id"], "claims"):
            add("dangling_id", "measurement.claim_id không tồn tại", m["id"])
        if not ix.is_(m["context_id"], "contexts"):
            add("dangling_id", "measurement.context_id không tồn tại", m["id"])
        need(m["id"], m["evidence_ids"], "evidence", field="evidence_ids")
        need(m["id"], m["conflict_ids"], "conflicts", field="conflict_ids")
        refs_ok(m["id"], m["source_ref_ids"])
        if not re.fullmatch(r"-?\d+(?:[.,]\d+)*", m["value"]):
            add("measurement_value", "value phải là chuỗi số đúng như nguồn", m["id"])
        elif m["value"] not in norm(ix.quotes(m["source_ref_ids"])):
            add("number_not_in_source", "giá trị %s không có trong nguồn được dẫn" % m["value"], m["id"])
        if not m["source_ref_ids"]:
            add("measurement_refs", "measurement cần nguồn", m["id"])
        c = claims.get(m["claim_id"])
        evs = [ix.get(e) for e in m["evidence_ids"] if ix.is_(e, "evidence")]
        if c and any(e["simulation_label_required"] for e in evs) and not c["simulation_label_required"]:
            add("simulation_label", "claim của số đo giả lập phải kế thừa nhãn", m["claim_id"])

    # -- workflow
    for g in (model["workflow"]["graphs"]):
        if not ok(g):
            continue
        need(g["id"], g["context_ids"], "contexts", field="context_ids")
        node_ids = {n["id"] for n in g["nodes"] if isinstance(n, dict)}
        if not node_ids:
            add("graph_empty", "graph không có node", g["id"])
        for n in g["nodes"]:
            refs_ok(n["id"], n["source_ref_ids"])
            need(n["id"], n["requirement_ids"], "requirements", field="requirement_ids")
            need(n["id"], n["claim_ids"], "claims", field="claim_ids")
            need(n["id"], n["gap_ids"], "gaps", field="gap_ids")
            roles = {r.get("role") for r in ix.refs(n["source_ref_ids"])}
            if n["kind"] == "required_step" and not (n["requirement_ids"] or roles & set(REQUIREMENT_ROLES)):
                add("node_basis", "required_step cần requirement hoặc nguồn đề", n["id"])
            if n["kind"] == "reported_step" and not ("student_submission" in roles or any(
                    claims.get(x, {}).get("kind") == "reported" for x in n["claim_ids"])):
                add("node_basis", "reported_step cần nguồn bài làm hoặc claim reported", n["id"])
            verified_lang(n["id"], n["purpose"])
        adj = {nid: [] for nid in node_ids}
        for e in g["dependency_edges"]:
            refs_ok(e["id"], e["source_ref_ids"])
            if e["from"] not in node_ids or e["to"] not in node_ids:
                add("edge_endpoint", "edge %s nối node ngoài graph" % e["id"], e["id"])
                continue
            if e["from"] == e["to"]:
                add("dependency_cycle", "edge tự vòng", e["id"])
                continue
            if e["basis"] == "explicit" and not e["source_ref_ids"]:
                add("edge_basis", "edge explicit cần nguồn", e["id"])
            adj[e["from"]].append(e["to"])
        for e in g["feedback_edges"]:
            refs_ok(e["id"], e["source_ref_ids"])
            if e["from"] not in node_ids or e["to"] not in node_ids:
                add("edge_endpoint", "feedback edge %s nối node ngoài graph" % e["id"], e["id"])
            if e["basis"] == "explicit" and not e["source_ref_ids"]:
                add("edge_basis", "feedback edge explicit cần nguồn", e["id"])
        if _has_cycle(adj):
            add("dependency_cycle", "dependency graph có chu trình (vòng phản hồi phải nằm trong feedback_edges)", g["id"])

    # -- decisions
    for d in model["decisions"]:
        if not ok(d):
            continue
        refs_ok(d["id"], d["source_ref_ids"])
        need(d["id"], d["requirement_ids"], "requirements", field="requirement_ids")
        need(d["id"], d["gap_ids"], "gaps", field="gap_ids")
        opt_ids = [o["id"] for o in d["options"]]
        if len(set(opt_ids)) != len(opt_ids):
            add("duplicate_id", "option ID lặp trong decision", d["id"])
        if len(opt_ids) < 2:
            add("decision_options", "decision cần ít nhất 2 phương án", d["id"])
        for o in d["options"]:
            refs_ok(d["id"], o["source_ref_ids"], "options.source_ref_ids")
        if d["recorded_choice_id"] is None:
            if d["recorded_choice_ref_ids"]:
                add("recorded_choice", "recorded_choice_id null thì recorded_choice_ref_ids phải rỗng", d["id"])
        else:
            if d["recorded_choice_id"] not in opt_ids:
                add("recorded_choice", "recorded_choice_id không thuộc options", d["id"])
            refs = ix.refs(d["recorded_choice_ref_ids"])
            if not refs or any(r.get("role") != "student_submission" for r in refs):
                add("recorded_choice", "lựa chọn đã ghi nhận phải dẫn đoạn bài làm (student_submission)", d["id"])

    # -- interactions
    goal_ids = {q["id"] for q in model["requirements"] if ok(q) and q["category"] == "learning_goal"}
    for it in model["interactions"]:
        if not ok(it):
            continue
        refs_ok(it["id"], it["source_ref_ids"])
        need(it["id"], it["gap_ids"], "gaps", field="gap_ids")
        for gid in it["learning_goal_ids"]:
            if gid not in goal_ids:
                add("learning_goal", "learning_goal_ids phải trỏ requirement category learning_goal: " + gid, it["id"])
        if it["basis"] == "source_backed" and not it["source_ref_ids"] and not it["gap_ids"]:
            add("interaction_basis", "tương tác source_backed cần nguồn hoặc gap", it["id"])
        verified_lang(it["id"], it["feedback"], it["prompt"])
        p = it["payload"]
        if it["type"] == "trace_flow":
            g = ix.get(p["graph_id"]) if ix.is_(p["graph_id"], "graphs") else None
            if not g:
                add("dangling_id", "trace_flow.graph_id không tồn tại", it["id"])
                continue
            gnodes = {n["id"] for n in g["nodes"]}
            if not p["steps"]:
                add("trace_steps", "trace_flow cần ít nhất 1 bước", it["id"])
            seq = [s["node_id"] for s in p["steps"]]
            for s in seq:
                if s not in gnodes:
                    add("trace_steps", "bước trỏ node ngoài graph: " + s, it["id"])
            anc = _ancestors(g)
            fb_to = {e["to"] for e in g["feedback_edges"]}
            for i in range(len(seq)):
                for j in range(i + 1, len(seq)):
                    if seq[j] in anc.get(seq[i], set()) and seq[j] not in fb_to:
                        add("trace_order", "trace_flow đi ngược dependency (%s sau %s) mà không có vòng phản hồi"
                            % (seq[j], seq[i]), it["id"])
            for s in p["steps"]:
                verified_lang(it["id"], s["explanation"], s["after"])
        elif it["type"] == "order_dependencies":
            g = ix.get(p["graph_id"]) if ix.is_(p["graph_id"], "graphs") else None
            if not g:
                add("dangling_id", "order_dependencies.graph_id không tồn tại", it["id"])
                continue
            gnodes = {n["id"] for n in g["nodes"]}
            edges = {e["id"]: e for e in g["dependency_edges"]}
            if not set(p["node_ids"]) <= gnodes:
                add("order_nodes", "node_ids phải thuộc graph", it["id"])
            for eid in p["edge_ids"]:
                e = edges.get(eid)
                if not e or e["from"] not in p["node_ids"] or e["to"] not in p["node_ids"]:
                    add("order_edges", "edge %s không thuộc dependency_edges của graph/node_ids" % eid, it["id"])
        elif it["type"] == "choose_explain":
            opts = [o["id"] for o in p["options"]]
            if len(opts) < 2 or len(set(opts)) != len(opts):
                add("choice_options", "choose_explain cần ≥2 option ID duy nhất", it["id"])
            if not p["accepted_option_ids"] or not set(p["accepted_option_ids"]) <= set(opts):
                add("choice_accepted", "accepted_option_ids phải không rỗng và thuộc options", it["id"])
            for o in p["options"]:
                refs_ok(it["id"], o["source_ref_ids"], "options.source_ref_ids")
                verified_lang(it["id"], o["feedback"])
        elif it["type"] == "teach_back":
            if not p["checklist"]:
                add("teach_checklist", "teach_back cần checklist", it["id"])
            for c in p["checklist"]:
                refs_ok(it["id"], c["source_ref_ids"], "checklist.source_ref_ids")

    # -- presentation
    pres = model["presentation"]
    for c in pres["cards"]:
        if not ok(c):
            continue
        need(c["id"], c["claim_ids"], "claims", field="claim_ids")
        need(c["id"], c["node_ids"], "nodes", field="node_ids")
        need(c["id"], c["decision_ids"], "decisions", field="decision_ids")
        need(c["id"], c["evidence_ids"], "evidence", field="evidence_ids")
        need(c["id"], c["gap_ids"], "gaps", field="gap_ids")
        refs_ok(c["id"], c["source_ref_ids"])
        if not (c["claim_ids"] or c["node_ids"] or c["decision_ids"] or c["evidence_ids"] or c["gap_ids"]):
            add("card_empty", "card cần ít nhất một ID nội dung hoặc gap", c["id"])
        verified_lang(c["id"], c["title"], *c["speaker_prompts"])
        support = " ".join([claims[x]["text"] for x in c["claim_ids"] if x in claims]
                           + [ix.get(x)["description"] for x in c["evidence_ids"] if ix.is_(x, "evidence")]
                           + [ix.quotes(ix.get(x)["source_ref_ids"]) for x in c["claim_ids"] + c["evidence_ids"]
                              if ix.get(x)]
                           + [ix.quotes(c["source_ref_ids"])])
        numbers_supported(c["id"], c["title"] + " " + " ".join(c["speaker_prompts"]), support)
    for q in pres["questions"]:
        if not ok(q):
            continue
        refs_ok(q["id"], q["source_ref_ids"])
        for gid in q["learning_goal_ids"]:
            if gid not in goal_ids:
                add("learning_goal", "learning_goal_ids phải trỏ requirement learning_goal: " + gid, q["id"])
        if not q["checklist"]:
            add("question_checklist", "câu hỏi cần checklist", q["id"])
        for c in q["checklist"]:
            refs_ok(q["id"], c["source_ref_ids"], "checklist.source_ref_ids")
    return issues


def _has_cycle(adj):
    color = {}

    def dfs(u):
        color[u] = 1
        for v in adj.get(u, []):
            if color.get(v) == 1 or (not color.get(v) and dfs(v)):
                return True
        color[u] = 2
        return False

    return any(not color.get(u) and dfs(u) for u in adj)


def _ancestors(g):
    """node → tập node phải xảy ra trước (theo dependency_edges)."""
    parents = {}
    for e in g.get("dependency_edges") or []:
        parents.setdefault(e["to"], set()).add(e["from"])
    memo = {}

    def anc(n, seen=()):
        if n in memo:
            return memo[n]
        out = set()
        for p in parents.get(n, ()):
            if p in seen:
                continue
            out.add(p)
            out |= anc(p, seen + (n,))
        memo[n] = out
        return out

    return {n["id"]: anc(n["id"]) for n in g.get("nodes") or []}


# ------------------------------------------------------------------ chốt model
ID_LIST_FIELDS = ("source_ref_ids", "evidence_ids", "gap_ids", "conflict_ids", "context_ids", "requirement_ids",
                  "premise_ids", "claim_ids", "node_ids", "decision_ids", "learning_goal_ids", "left_ref_ids",
                  "right_ref_ids", "resolution_ref_ids", "recorded_choice_ref_ids", "scope_ids", "edge_ids")


def _strip_ids(obj, alive):
    """Bỏ ID treo trong mọi mảng *_ids (đệ quy)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ID_LIST_FIELDS and isinstance(v, list):
                obj[k] = [x for x in v if x in alive]
            else:
                _strip_ids(v, alive)
    elif isinstance(obj, list):
        for v in obj:
            _strip_ids(v, alive)


def _drop(model, bad):
    """Bỏ các object có ID trong bad (mọi section, node/edge trong graph, card/question)."""
    for sec in LIST_SECTIONS:
        model[sec] = [o for o in model[sec] if not (isinstance(o, dict) and o.get("id") in bad)]
    graphs = []
    for g in model["workflow"]["graphs"]:
        if g.get("id") in bad:
            continue
        g["nodes"] = [n for n in g["nodes"] if n.get("id") not in bad]
        nid = {n["id"] for n in g["nodes"]}
        g["dependency_edges"] = [e for e in g["dependency_edges"]
                                 if e.get("id") not in bad and e["from"] in nid and e["to"] in nid]
        g["feedback_edges"] = [e for e in g["feedback_edges"]
                               if e.get("id") not in bad and e["from"] in nid and e["to"] in nid]
        graphs.append(g)
    model["workflow"]["graphs"] = graphs
    for sec in ("cards", "questions"):
        model["presentation"][sec] = [o for o in model["presentation"][sec] if o.get("id") not in bad]


def _alive_ids(model):
    ix = Index(model)
    return set(ix.by_id) | set(ix.sources)


def _repair_local(model, ix):
    """Sửa cục bộ an toàn (chỉ hạ cấp, không nâng): trả danh sách ghi chú info."""
    notes = []
    goal_ids = {q["id"] for q in model["requirements"] if q["category"] == "learning_goal"}
    for q in model["requirements"]:
        if q["fulfillment"] != "not_reported" and not q["evidence_ids"]:
            q["fulfillment"] = "not_reported"
            notes.append(("downgrade_fulfillment", "Hạ fulfillment về not_reported vì không còn bằng chứng", q["id"]))
        if q["fulfillment"] == "conflicting" and not q["conflict_ids"]:
            q["fulfillment"] = "reported_partial"
            notes.append(("downgrade_fulfillment", "Không còn conflict liên kết: hạ về reported_partial", q["id"]))
    for c in model["claims"]:
        if c["kind"] == "inference" and not c["premise_ids"]:
            pass  # để validator bỏ
        if c["data_origin"] in ("lab_simulated", "teaching_hypothetical") and not c["simulation_label_required"]:
            c["simulation_label_required"] = True
            notes.append(("simulation_label", "Tự bật nhãn giả lập theo data_origin", c["id"]))
        if not c["simulation_label_required"] and SIM_HINT_RE.search(ix.quotes(c["source_ref_ids"])):
            c["simulation_label_required"] = True
            notes.append(("simulation_label", "Nguồn có nhãn simulated/giả lập: bật nhãn cho claim", c["id"]))
        evs = [ix.get(e) for e in c["evidence_ids"] if ix.is_(e, "evidence")]
        if any(e["simulation_label_required"] for e in evs) and not c["simulation_label_required"]:
            c["simulation_label_required"] = True
            notes.append(("simulation_label", "Kế thừa nhãn giả lập từ bằng chứng", c["id"]))
    for e in model["evidence"]:
        if e["data_origin"] in ("lab_simulated", "teaching_hypothetical") and not e["simulation_label_required"]:
            e["simulation_label_required"] = True
            notes.append(("simulation_label", "Tự bật nhãn giả lập theo data_origin", e["id"]))
        if not e["simulation_label_required"] and SIM_HINT_RE.search(ix.quotes(e["source_ref_ids"])):
            e["simulation_label_required"] = True
            notes.append(("simulation_label", "Nguồn có nhãn simulated/giả lập: bật nhãn", e["id"]))
    claims = {c["id"]: c for c in model["claims"]}
    for m in model["measurements"]:
        c = claims.get(m["claim_id"])
        evs = [ix.get(e) for e in m["evidence_ids"] if ix.is_(e, "evidence")]
        if c and any(e["simulation_label_required"] for e in evs) and not c["simulation_label_required"]:
            c["simulation_label_required"] = True
            notes.append(("simulation_label", "Kế thừa nhãn giả lập từ số đo", c["id"]))
    for it in model["interactions"]:
        it["learning_goal_ids"] = [g for g in it["learning_goal_ids"] if g in goal_ids]
    for q in model["presentation"]["questions"]:
        q["learning_goal_ids"] = [g for g in q["learning_goal_ids"] if g in goal_ids]
    for d in model["decisions"]:
        if d["recorded_choice_id"] is not None and d["recorded_choice_id"] not in {o["id"] for o in d["options"]}:
            d["recorded_choice_id"], d["recorded_choice_ref_ids"] = None, []
            notes.append(("recorded_choice", "Bỏ lựa chọn ghi nhận không thuộc options", d["id"]))
        if d["recorded_choice_id"] is None:
            d["recorded_choice_ref_ids"] = []
    return notes


def _downgrade_choices(model, ix):
    """choose_explain thiếu căn cứ hoặc bị conflict unresolved tác động → teach_back thảo luận (không chấm)."""
    notes = []
    conflict_refs = set()
    for c in model["conflicts"]:
        if c["state"] == "unresolved":
            conflict_refs |= set(c["left_ref_ids"]) | set(c["right_ref_ids"])
    for it in model["interactions"]:
        if it["type"] != "choose_explain":
            continue
        p = it["payload"]
        opts = {o["id"]: o for o in p["options"]}
        accepted = [a for a in p["accepted_option_ids"] if a in opts]
        reason = None
        if len(opts) < 2:
            reason = "ít hơn 2 phương án"
        elif not accepted:
            reason = "không có đáp án được nguồn xác định"
        elif any(not opts[a]["source_ref_ids"] for a in accepted):
            reason = "đáp án được chấp nhận thiếu nguồn"
        elif conflict_refs & {r for o in opts.values() for r in o["source_ref_ids"]} | (conflict_refs & set(it["source_ref_ids"])):
            reason = "nguồn của đáp án đang có mâu thuẫn chưa giải quyết"
        if reason:
            it["type"] = "teach_back"
            it["payload"] = {
                "question": p.get("explanation_prompt") or it["prompt"],
                "checklist": [{"point": "%s — %s" % (o["label"], o["feedback"]), "source_ref_ids": o["source_ref_ids"]}
                              for o in opts.values()] or [{"point": it["feedback"], "source_ref_ids": it["source_ref_ids"]}],
                "hint_levels": ["Câu này được chuyển thành câu thảo luận (%s): không có đáp án đúng/sai duy nhất." % reason],
            }
            notes.append(("downgraded_interaction", "choose_explain → teach_back: " + reason, it["id"]))
    return notes


def _auto_gaps(model):
    """Yêu cầu bắt buộc chưa có bằng chứng phải có gap (code tự thêm, mô tả cố định)."""
    notes = []
    existing = _alive_ids(model)
    for q in model["requirements"]:
        if q["applicability"] == "required" and not q["evidence_ids"] and not q["gap_ids"]:
            gid = "gap-auto-" + q["id"]
            n = 1
            while gid in existing:
                n += 1
                gid = "gap-auto-%s-%d" % (q["id"], n)
            existing.add(gid)
            model["gaps"].append({"id": gid, "scope_ids": [q["id"]],
                                  "reason": "Markdown cấp gốc chưa có nội dung bài làm cho yêu cầu này.",
                                  "requested_evidence": "Bổ sung đoạn bài làm hoặc bằng chứng ở Markdown cấp gốc rồi sinh lại."})
            q["gap_ids"].append(gid)
            notes.append(("auto_gap", "Tự thêm gap cho yêu cầu bắt buộc chưa có bằng chứng", q["id"]))
        if q["fulfillment"] in ("reported_partial", "reported_not_done") and not q["gap_ids"]:
            gid = "gap-auto-" + q["id"]
            if gid not in existing:
                existing.add(gid)
                model["gaps"].append({"id": gid, "scope_ids": [q["id"]],
                                      "reason": "Bài làm tự báo cáo chưa hoàn tất yêu cầu này.",
                                      "requested_evidence": "Xem phần còn thiếu trong bài làm."})
                q["gap_ids"].append(gid)
    return notes


def _empty_sections(model):
    for sec in LIST_SECTIONS:
        if not isinstance(model.get(sec), list):
            model[sec] = []
    if not isinstance(model.get("workflow"), dict) or not isinstance(model["workflow"].get("graphs"), list):
        model["workflow"] = {"graphs": []}
    if not isinstance(model.get("presentation"), dict):
        model["presentation"] = {"cards": [], "questions": []}
    for k in ("cards", "questions"):
        if not isinstance(model["presentation"].get(k), list):
            model["presentation"][k] = []


def prune(model, lines_by_source, max_iter=12):
    """Bỏ object lỗi lặp tới ổn định. Trả (model mới, danh sách (code, message, object_id, severity))."""
    model = copy.deepcopy(model)
    _empty_sections(model)
    log = []
    for _ in range(max_iter):
        ix = Index(model)
        for n in _repair_local(model, ix) + _downgrade_choices(model, ix):
            log.append(n + ("info",))
        issues = check_model(model, lines_by_source)
        struct = [i for i in issues if i.code == "structure"]
        if struct:
            for i in struct:
                log.append((i.code, i.message, None, "error"))
            return model, log, False
        bad = {i.object_id for i in issues if i.severity == "error" and i.object_id}
        # lỗi trong node/edge: bỏ đúng node/edge; graph có chu trình: bỏ cả graph
        if not bad:
            for n in _auto_gaps(model):
                log.append(n + ("info",))
            if not check_model(model, lines_by_source):
                return model, log, True
            continue
        for i in issues:
            if i.severity == "error" and i.object_id in bad:
                log.append((i.code, i.message, i.object_id, "error"))
        _drop(model, bad)
        _strip_ids(model, _alive_ids(model))
    return model, log, not any(i.severity == "error" for i in check_model(model, lines_by_source))


def prune_unused_refs(model):
    """Chỉ giữ source_refs được dẫn (giảm kích thước HTML, không xuất trích dẫn thừa)."""
    used = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ID_LIST_FIELDS and isinstance(v, list):
                    used.update(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk({k: v for k, v in model.items() if k not in ("source_refs", "source_manifest", "validation")})
    model["source_refs"] = [r for r in model["source_refs"] if r["id"] in used]
    return model


def coverage(manifest):
    files_total = len(manifest)
    lines_total = sum(m["line_count"] or 0 for m in manifest)
    lines_processed = sum(min(m["line_count"] or 0, _union_len(m["processed_ranges"])) for m in manifest)
    redacted = sum(_union_len(m["redacted_ranges"]) for m in manifest)
    files_processed = sum(1 for m in manifest if m["read_status"] in ("read", "empty")
                          and _union_len(m["processed_ranges"]) >= (m["line_count"] or 0))
    return {"files_total": files_total, "files_processed": files_processed, "lines_total": lines_total,
            "lines_processed": lines_processed, "redacted_lines": redacted}


def _union_len(ranges):
    pts = sorted((r["start_line"], r["end_line"]) for r in ranges)
    total, cur_s, cur_e = 0, None, None
    for s, e in pts:
        if cur_e is None or s > cur_e + 1:
            if cur_e is not None:
                total += cur_e - cur_s + 1
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s + 1
    return total


def content_state(model, cov, pipeline_issues):
    """blocked / incomplete / draft_ready (hợp đồng §6). pipeline_issues: dict issue (code, severity)."""
    readable = sum(1 for m in model["source_manifest"] if m["read_status"] == "read")
    if readable == 0 or any(i["code"] in ("structure", "safety") and i["severity"] == "error" for i in pipeline_issues):
        return "blocked"
    goals = [q for q in model["requirements"] if q["category"] == "learning_goal" and q["source_ref_ids"]]
    if not model["requirements"] and not model["claims"]:
        return "blocked"
    blocking_codes = {"fake_model", "budget_exhausted", "deadline", "chunk_failed", "synthesis_failed",
                      "file_changed", "ingest_mismatch", "line_over_limit", "read_failed"}
    if (cov["files_processed"] < cov["files_total"] or cov["lines_processed"] < cov["lines_total"] or not goals
            or any(i["code"] in blocking_codes for i in pipeline_issues)
            or any(c["state"] == "unresolved" and any(r in {x for q in goals for x in q["source_ref_ids"]}
                                                       for r in c["left_ref_ids"] + c["right_ref_ids"])
                   for c in model["conflicts"])):
        return "incomplete"
    return "draft_ready"
