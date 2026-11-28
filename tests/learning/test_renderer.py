"""Kiểm renderer HTML learning-v1 (codebase/learning_renderer.py). Chạy: python -m unittest tests.learning.test_renderer"""
import copy
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (os.path.join(ROOT, "codebase"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import fixture_data  # noqa: E402
import learning_renderer as R  # noqa: E402

SECTION_IDS = ["overview", "workflow", "walkthrough", "decisions", "evidence", "teachback", "presentation"]
NETWORK_PATTERNS = ["fetch(", "XMLHttpRequest", "WebSocket", "navigator.sendBeacon", "importScripts", "import(",
                    "<link ", "@import", 'src="http', 'href="http', "url(http", "serviceWorker", "eval(",
                    "new Function", ".innerHTML", "insertAdjacentHTML", "document.write"]


def render(model=None, meta=None):
    if model is None:
        _, model = fixture_data.sample()
    return R.build_learning_html(model, dict(meta or fixture_data.META))


def embedded(html_text):
    m = re.search(r'<script type="application/json" id="learning-data">(.*?)</script>', html_text, re.S)
    assert m, "thiếu learning-data"
    return json.loads(m.group(1))


def section_ids(html_text):
    return re.findall(r'<section id="([a-z]+)" class="lesson"', html_text)


def empty_model():
    _, m = fixture_data.sample()
    for k in ("source_manifest", "source_refs", "requirements", "contexts", "claims", "evidence", "measurements",
              "decisions", "interactions", "gaps", "conflicts"):
        m[k] = []
    m["workflow"] = {"graphs": []}
    m["presentation"] = {"cards": [], "questions": []}
    m["validation"] = {"content_state": "incomplete", "issues": [], "review_state": "unreviewed",
                       "coverage_summary": {"files_total": 0, "files_processed": 0, "lines_total": 0,
                                            "lines_processed": 0, "redacted_lines": 0, "unresolved_issue_ids": []}}
    return m


class RendererTest(unittest.TestCase):
    def setUp(self):
        self.html = render()

    def test_document_shell(self):
        h = self.html
        self.assertTrue(h.startswith("<!doctype html>"))
        self.assertIn('<html lang="vi">', h)
        self.assertIn('<meta charset="utf-8">', h)
        self.assertIn('name="viewport"', h)
        self.assertIn('<meta http-equiv="Content-Security-Policy" content="default-src &#x27;none&#x27;', h)
        csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', h).group(1)
        self.assertEqual(csp.replace("&#x27;", "'"), R.CSP)
        self.assertIn("<title>Lab mẫu: Đo chi phí trợ lý FAQ · Học lại bài lab</title>", h)
        self.assertEqual(section_ids(h), SECTION_IDS)
        for sid, title in R.SECTIONS:
            self.assertIn(">%s</h2>" % title, h)
        self.assertIn("<noscript>", h)
        self.assertEqual(R.TEMPLATE_VERSION, "learning-html-1")

    def test_title_escaped(self):
        _, m = fixture_data.sample()
        m["repo_snapshot"]["display_label"] = 'Bài <b>"x"</b> & y'
        h = render(m)
        self.assertIn("<title>Bài &lt;b&gt;&quot;x&quot;&lt;/b&gt; &amp; y · Học lại bài lab</title>", h)
        self.assertNotIn("<b>", h)

    def test_no_network_or_unsafe_primitives(self):
        for pat in NETWORK_PATTERNS:
            self.assertNotIn(pat, self.html, pat)
        self.assertIsNone(re.search(r"<a\s[^>]*href=\"(?!#)", self.html))
        self.assertNotIn("<form", self.html)
        self.assertNotIn("<iframe", self.html)
        self.assertNotIn("setTimeout('", self.html)
        self.assertNotIn('setTimeout("', self.html)

    def test_escaping_and_embedded_json(self):
        h = self.html
        self.assertNotIn("</script><script>alert(1)</script>", h)
        self.assertNotIn("<img src=x onerror", h)
        self.assertNotIn("<script>alert", h)
        data = embedded(h)
        _, model = fixture_data.sample()
        self.assertEqual(data["model"], model)
        self.assertEqual(data["meta"]["generation_id"], "deadbeef")
        self.assertEqual(len(re.findall(r"<script", h)), 2)
        self.assertEqual(len(re.findall(r"</script>", h)), 2)
        raw = re.search(r'id="learning-data">(.*?)</script>', h, re.S).group(1)
        for ch in "<>&  ":
            self.assertNotIn(ch, raw)

    def test_json_for_script_escapes_separators(self):
        s = R.json_for_script({"a": "x y z</script>&"})
        self.assertNotIn(" ", s)
        self.assertNotIn(" ", s)
        self.assertNotIn("<", s)
        self.assertEqual(json.loads(s)["a"], "x y z</script>&")

    def test_status_banners(self):
        h = self.html  # fixture: incomplete
        self.assertIn("Bản nháp chưa đủ nguồn", h)
        self.assertIn("Chưa được người duyệt xem", h)
        self.assertIn("Đã xử lý 3/3 file · 21/21 dòng · 1 dòng đã che", h)
        self.assertIn("0123456789ab", h)
        self.assertNotIn(R.FAKE_TEXT, h)
        _, m = fixture_data.sample()
        m["validation"]["content_state"] = "draft_ready"
        h2 = render(m)
        self.assertIn("Sẵn sàng để người duyệt xem — không có nghĩa bài đã hoàn thành hay bạn đã hiểu", h2)
        self.assertNotIn("Bản nháp chưa đủ nguồn", h2)

    def test_fake_banner(self):
        meta = dict(fixture_data.META, fake=True)
        self.assertIn(R.FAKE_TEXT, render(meta=meta))
        _, m = fixture_data.sample()
        m["validation"]["issues"].append({"id": "iss-fake", "code": "fake_model", "severity": "warning",
                                          "message": "fake", "scope_ids": []})
        self.assertIn(R.FAKE_TEXT, render(m))

    def test_blocked_page(self):
        _, m = fixture_data.sample()
        m["validation"]["content_state"] = "blocked"
        m["validation"]["issues"].append({"id": "iss-x", "code": "structure", "severity": "error",
                                          "message": "lỗi cấu trúc <thử>", "scope_ids": []})
        h = render(m)
        self.assertIn("Không dựng được bài học", h)
        self.assertIn("Vì sao chưa có bài học", h)
        self.assertIn("lỗi cấu trúc &lt;thử&gt;", h)
        self.assertIn("README.md", h)
        self.assertEqual(section_ids(h), [])
        self.assertNotIn("Chế độ trình bày", h)
        self.assertNotIn("Giải thích chi phí mỗi câu trả lời đúng", h)  # không có nội dung bài học
        self.assertEqual(len(re.findall(r"<script", h)), 1)  # chỉ JSON, không có JS tương tác
        self.assertIn("Chưa được người duyệt xem", h)
        for pat in NETWORK_PATTERNS:
            self.assertNotIn(pat, h, pat)

    def test_empty_model_shows_all_sections_with_missing(self):
        h = render(empty_model())
        self.assertEqual(section_ids(h), SECTION_IDS)
        for sid in SECTION_IDS:
            self.assertIn(R.EMPTY[sid][0], h, sid)
            self.assertIn(R.EMPTY[sid][1], h, sid)
        self.assertIn("Bản nháp chưa đủ nguồn", h)
        self.assertEqual(embedded(h)["model"], empty_model())

    def test_missing_optional_containers_do_not_crash(self):
        m = empty_model()
        del m["workflow"]
        del m["presentation"]
        h = R.build_learning_html(m, {})
        self.assertEqual(section_ids(h), SECTION_IDS)
        self.assertIn("learning-html-1", h)

    def test_same_template_two_models(self):
        _, m2 = fixture_data.sample()
        m2["repo_snapshot"]["display_label"] = "Lab khác: Triển khai agent"
        m2["repo_snapshot"]["snapshot_id"] = "f" * 64
        m2["workflow"]["graphs"] = m2["workflow"]["graphs"][1:]
        h1, h2 = self.html, render(m2)
        self.assertEqual(section_ids(h1), section_ids(h2))
        self.assertIn("Lab khác: Triển khai agent", h2)
        self.assertNotIn("Lab khác", h1)
        self.assertIn("Thứ tự làm bài theo đề", h1)
        self.assertNotIn("Thứ tự làm bài theo đề", h2)
        js1 = re.search(r"<script>\n(.*?)</script>", h1, re.S).group(1)
        js2 = re.search(r"<script>\n(.*?)</script>", h2, re.S).group(1)
        self.assertEqual(js1, js2)  # cùng template, chỉ dữ liệu khác

    def test_fallback_and_labels_present(self):
        h = self.html
        self.assertIn("Giải thích chi phí mỗi câu trả lời đúng và quyết định pilot.", h)
        # nhãn bắt buộc có trong template JS
        for label in ("Đề bài", "Bài làm tự báo cáo", "Ví dụ/hướng dẫn giảng viên", "Chưa rõ vai trò",
                      "Chưa có nội dung bài làm", "Tự báo cáo: một phần", "Ghi trong Markdown, chưa xác minh",
                      "Nguồn được nhắc tới — chưa đọc", "Số liệu giả lập (simulated)", "Giả định minh họa",
                      "Ví dụ giả định — không phải replay code", "Tương tác này chưa hỗ trợ trong bản MVP",
                      "Bài làm ghi nhận lựa chọn: ", "Bài làm chưa ghi nhận lựa chọn",
                      "Lưu ghi chú trên thiết bị này", "Xóa dữ liệu đã lưu", "Xuất ghi chú (.json)",
                      "In kèm đáp án đã mở", "In kèm ghi chú", "In mục đang xem", "In tất cả mục",
                      "Tắt hiệu ứng", "Tôi đã trả lời xong", "Cần gợi ý", "Xem phản hồi", "Chế độ trình bày",
                      "Bài làm được tài liệu ghi nhận", "Yêu cầu — chưa có nội dung bài làm",
                      "Chưa giải quyết — cần người học/TA xác nhận", "learning-notes-1"):
            self.assertIn(label, h, label)
        # localStorage chỉ dùng trong try/catch, khóa gồm snapshot + template version
        self.assertIn("'learning-v1:' + SNAP + ':' + TV", h)


if __name__ == "__main__":
    unittest.main()
