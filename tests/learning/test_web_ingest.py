"""Kiểm phần web của after_lab ("Hiểu bài đã làm"): mode theo request, ingestion ZIP/folder, manifest,
marker, hàng đợi/hủy, preview/download raw. Chỉ dùng fixture tổng hợp trong bộ nhớ / thư mục tạm.

Chạy: python -m unittest discover -s tests/learning -t .
"""
import hashlib
import http.client
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

os.environ["MODEL_PROVIDER"] = "fake"
ROOT = Path(__file__).resolve().parents[2]
CODEBASE = ROOT / "codebase"
if str(CODEBASE) not in sys.path:
    sys.path.insert(0, str(CODEBASE))

import web_server  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402

LEARN_NAME = "learning-0123456789ab-89abcdef.html"


def make_zip(entries):
    """entries: list[(name, bytes)] hoặc (ZipInfo, bytes)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return buf.getvalue()


def symlink_info(name):
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = (0o120777 << 16)
    return info


def wait_for(pred, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.02)
    return pred()


class TmpDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="test-web-ingest-"))
        self.dest = self.tmp / "lab"
        self.dest.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def disk_names(self, root=None):
        root = root or self.dest
        return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


class ZipAfterLabTests(TmpDirCase):
    def _repo_zip(self):
        return make_zip([
            ("repo-abc123/README.md", b"# De bai\n"),
            ("repo-abc123/MISSION_ANSWERS.md", b"# Bai lam\n"),
            ("repo-abc123/INSTRUCTOR_GUIDE.md", b"# Huong dan\n"),
            ("repo-abc123/rubric.MD", b"# Rubric\n"),
            ("repo-abc123/sub/deep.md", b"# Sau\n"),
            ("repo-abc123/main.py", b"print(1)\n"),
        ])

    def test_after_lab_keeps_answer_and_guide_files(self):
        m = web_server._ingest_zip_after_lab(self._repo_zip(), self.dest, channel="zip")
        names = {a["name"] for a in m["accepted"]}
        self.assertEqual(names, {"README.md", "MISSION_ANSWERS.md", "INSTRUCTOR_GUIDE.md", "rubric.MD"})
        self.assertTrue(m["wrapper_stripped"])
        self.assertEqual(m["channel"], "zip")
        self.assertEqual(m["excluded"], [])
        self.assertEqual(m["out_of_scope_count"], 2)  # sub/deep.md + main.py
        self.assertEqual(self.disk_names(), sorted(names))

    def test_before_lab_zip_still_drops_answer_files(self):
        written = web_server._safe_extract_zip(self._repo_zip(), self.dest)
        disk = self.disk_names()
        self.assertNotIn("MISSION_ANSWERS.md", disk)
        self.assertNotIn("INSTRUCTOR_GUIDE.md", disk)
        self.assertIn("README.md", disk)
        self.assertIn("main.py", disk)
        self.assertIn("sub/deep.md", disk)
        self.assertEqual(written, len(disk))

    def test_wrapper_stripped_exactly_once(self):
        data = make_zip([("outer/inner/README.md", b"x"), ("outer/inner/NOTES.md", b"y")])
        m = web_server._ingest_zip_after_lab(data, self.dest)
        self.assertTrue(m["wrapper_stripped"])
        self.assertEqual(m["accepted"], [])
        self.assertEqual(m["out_of_scope_count"], 2)
        self.assertEqual(self.disk_names(), [])
        err = web_server._no_root_markdown_error(m)
        self.assertIn("gốc repo", str(err))

    def test_no_wrapper_when_multiple_top_levels(self):
        data = make_zip([("README.md", b"x"), ("docs/a.md", b"y")])
        m = web_server._ingest_zip_after_lab(data, self.dest)
        self.assertFalse(m["wrapper_stripped"])
        self.assertEqual([a["name"] for a in m["accepted"]], ["README.md"])
        self.assertEqual(m["out_of_scope_count"], 1)

    def test_unsafe_paths_reject_whole_archive(self):
        bad_names = ["../x.md", "/etc/x.md", "C:/x.md", "wrap/../../x.md", "//server/share/x.md", "wrap/C:x.md"]
        for bad in bad_names:
            with self.subTest(bad=bad):
                data = make_zip([("wrap/README.md", b"ok"), (bad, b"evil")])
                with self.assertRaises(ValueError) as ctx:
                    web_server._ingest_zip_after_lab(data, self.dest)
                self.assertIn("từ chối toàn bộ", str(ctx.exception))
                self.assertEqual(self.disk_names(), [])  # không giải nén gì trước khi kiểm xong
        for raw in ["\\\\server\\share\\x.md", "\\x.md", "C:\\x.md", "c:x.md", "a\\..\\b.md"]:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    web_server._archive_entry_parts(raw)
        self.assertEqual(web_server._archive_entry_parts("a\\b.md"), ("a", "b.md"))

    def test_symlink_entry_excluded(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("wrap/README.md", b"ok")
            zf.writestr(symlink_info("wrap/link.md"), b"README.md")
        m = web_server._ingest_zip_after_lab(buf.getvalue(), self.dest)
        self.assertEqual(m["excluded"], [{"name": "link.md", "reason": "symlink"}])
        self.assertEqual([a["name"] for a in m["accepted"]], ["README.md"])
        self.assertFalse((self.dest / "link.md").exists())

    def test_case_insensitive_collision_excludes_all_members(self):
        data = make_zip([("w/A.md", b"one"), ("w/a.md", b"two"), ("w/README.md", b"ok")])
        m = web_server._ingest_zip_after_lab(data, self.dest)
        self.assertEqual(
            m["excluded"], [{"name": "A.md", "reason": "collision"}, {"name": "a.md", "reason": "collision"}]
        )
        self.assertEqual([a["name"] for a in m["accepted"]], ["README.md"])
        self.assertEqual(self.disk_names(), ["README.md"])

    def test_over_limit_per_file(self):
        limit = web_server.LEARNING_MAX_FILE_BYTES
        data = make_zip([("w/big.md", b"a" * (limit + 1)), ("w/edge.md", b"b" * limit)])
        m = web_server._ingest_zip_after_lab(data, self.dest)
        self.assertEqual(m["excluded"], [{"name": "big.md", "reason": "over_limit"}])
        self.assertEqual([(a["name"], a["bytes"]) for a in m["accepted"]], [("edge.md", limit)])

    def test_over_total_limit(self):
        chunk = 500 * 1024  # 5 × 500 KiB > 2 MiB
        data = make_zip([(f"w/f{i}.md", bytes([65 + i]) * chunk) for i in range(1, 6)])
        m = web_server._ingest_zip_after_lab(data, self.dest)
        self.assertEqual([a["name"] for a in m["accepted"]], ["f1.md", "f2.md", "f3.md", "f4.md"])
        self.assertEqual(m["excluded"], [{"name": "f5.md", "reason": "over_total_limit"}])
        self.assertLessEqual(sum(a["bytes"] for a in m["accepted"]), web_server.LEARNING_MAX_TOTAL_BYTES)

    def test_manifest_sha256_matches_raw_bytes(self):
        payloads = {"README.md": "Tiếng Việt\r\n# Đề\n".encode("utf-8"), "NOTES.md": b"\xef\xbb\xbfbom\n"}
        data = make_zip([(f"w/{k}", v) for k, v in payloads.items()])
        m = web_server._ingest_zip_after_lab(data, self.dest)
        for entry in m["accepted"]:
            raw = payloads[entry["name"]]
            self.assertEqual(entry["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(entry["bytes"], len(raw))
            self.assertEqual((self.dest / entry["name"]).read_bytes(), raw)


class FolderUploadTests(TmpDirCase):
    ITEMS = [
        ("lab/README.md", b"# De"),
        ("lab/MISSION_ANSWERS.md", b"# Bai lam"),
        ("lab/INSTRUCTOR_GUIDE.md", b"# HD"),
        ("lab/sub/x.md", b"# nested"),
        ("lab/main.py", b"print(1)"),
        ("lab/.hidden.md", b"hidden"),
    ]

    def test_after_lab_keeps_root_md_drops_nested(self):
        written, m = web_server._ingest_folder_upload("after_lab", self.ITEMS, "lab", self.dest)
        self.assertEqual(written, 3)
        self.assertEqual(m["channel"], "folder")
        self.assertEqual(
            sorted(a["name"] for a in m["accepted"]), ["INSTRUCTOR_GUIDE.md", "MISSION_ANSWERS.md", "README.md"]
        )
        self.assertEqual(m["out_of_scope_count"], 3)
        self.assertEqual(self.disk_names(), ["INSTRUCTOR_GUIDE.md", "MISSION_ANSWERS.md", "README.md"])
        for a in m["accepted"]:
            raw = dict(self.ITEMS)["lab/" + a["name"]]
            self.assertEqual(a["sha256"], hashlib.sha256(raw).hexdigest())

    def test_after_lab_root_only_stripped_when_equal_to_lab_name(self):
        written, m = web_server._ingest_folder_upload("after_lab", [("other/README.md", b"x")], "lab", self.dest)
        self.assertEqual(written, 0)
        self.assertEqual(m["out_of_scope_count"], 1)

    def test_before_lab_unchanged(self):
        written, m = web_server._ingest_folder_upload("before_lab", self.ITEMS, "lab", self.dest)
        self.assertIsNone(m)
        disk = self.disk_names()
        self.assertEqual(written, len(disk))
        self.assertNotIn("MISSION_ANSWERS.md", disk)
        self.assertNotIn("INSTRUCTOR_GUIDE.md", disk)
        self.assertIn("README.md", disk)
        self.assertIn("sub/x.md", disk)
        self.assertIn("main.py", disk)


class ModeTests(unittest.TestCase):
    def test_allowlist(self):
        self.assertEqual(web_server._parse_mode(None), "before_lab")
        self.assertEqual(web_server._parse_mode([]), "before_lab")
        self.assertEqual(web_server._parse_mode(["before_lab"]), "before_lab")
        self.assertEqual(web_server._parse_mode(["after_lab"]), "after_lab")
        for bad in (["bogus"], [""], ["AFTER_LAB"], ["before_lab;after_lab"]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                web_server._parse_mode(bad)

    def test_no_module_mode_state(self):
        self.assertFalse(hasattr(web_server, "MODE") or hasattr(web_server, "CURRENT_MODE"))


class RunAgentTests(unittest.TestCase):
    def test_after_lab_input_is_json_and_marker_parsed(self):
        lab_dir = Path(tempfile.gettempdir()) / 'chanme up "quoted" \\ back' / "repo name"
        captured = []

        def fake_answer(text):
            captured.append(text)
            return {"output": f"# Tóm tắt {lab_dir}\nnguồn: {lab_dir}\nTrang học lại: output/{LEARN_NAME}\n"}

        with mock.patch.object(web_server, "answer", fake_answer):
            md, page_url, summary = web_server._run_agent(lab_dir, "repo-hien-thi", "t:1", "after_lab")
        self.assertEqual(len(captured), 1)
        self.assertTrue(captured[0].startswith("@learning-v1 "))
        payload = json.loads(captured[0][len("@learning-v1 "):])
        self.assertEqual(payload, {"repo_path": str(lab_dir)})
        self.assertNotIn("\n", captured[0])
        self.assertEqual(page_url, f"/output/{LEARN_NAME}")
        self.assertNotIn(str(lab_dir), md)
        self.assertIn("repo-hien-thi", md)
        self.assertIn("elapsed_s", summary)

    def test_after_lab_rejects_wrong_or_unsafe_marker(self):
        lab_dir = Path(tempfile.gettempdir()) / "x"
        for out in (
            "Trang đóng vai: output/roleplay.html",           # marker của mode khác
            "Trang học lại: output/../secret.html",            # traversal
            "Trang học lại: output/roleplay.html",             # không phải tên learning-*
            "Trang học lại: /etc/learning-0123456789ab-89abcdef.html",
        ):
            with self.subTest(out=out), mock.patch.object(web_server, "answer", lambda t, o=out: {"output": o}):
                _, page_url, _ = web_server._run_agent(lab_dir, "x", "t:2", "after_lab")
                self.assertEqual(page_url, "")

    def test_before_lab_passes_plain_path(self):
        lab_dir = Path(tempfile.gettempdir()) / "plain lab"
        captured = []

        def fake_answer(text):
            captured.append(text)
            return {"output": f"# Be The Agent · {lab_dir}\n\nTrang đóng vai: output/plain-lab.html"}

        with mock.patch.object(web_server, "answer", fake_answer):
            md, page_url, _ = web_server._run_agent(lab_dir, "plain-lab", "t:3", "before_lab")
        self.assertEqual(captured, [str(lab_dir)])
        self.assertEqual(page_url, "/output/plain-lab.html")
        self.assertNotIn(str(lab_dir), md)

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            web_server._run_agent(Path("x"), "x", "t", "bogus")


def _fake_answer_recorder(calls):
    def fake_answer(text):
        calls.append(text)
        if text.startswith("@learning-v1 "):
            return {"output": f"ok\nTrang học lại: output/{LEARN_NAME}"}
        return {"output": "ok\nTrang đóng vai: output/roleplay-demo.html"}
    return fake_answer


class JobTests(unittest.TestCase):
    def _wait_status(self, job_id, statuses, timeout=5.0):
        ok = wait_for(lambda: web_server._JOBS[job_id]["status"] in statuses, timeout)
        self.assertTrue(ok, f"job {job_id} status={web_server._JOBS[job_id]['status']}")

    def test_two_jobs_different_modes_do_not_interfere(self):
        calls = []
        with mock.patch.object(web_server, "answer", _fake_answer_recorder(calls)):
            a = web_server._start_job(Path("/tmp/a-lab"), "a", "t:a", mode="after_lab")
            b = web_server._start_job(Path("/tmp/b-lab"), "b", "t:b", mode="before_lab")
            self._wait_status(a, {"done"})
            self._wait_status(b, {"done"})
        ja, jb = web_server._JOBS[a], web_server._JOBS[b]
        self.assertEqual((ja["mode"], jb["mode"]), ("after_lab", "before_lab"))
        self.assertEqual(ja["page_url"], f"/output/{LEARN_NAME}")
        self.assertEqual(ja["download_url"], f"/download/{LEARN_NAME}")
        self.assertEqual(jb["page_url"], "/output/roleplay-demo.html")
        self.assertEqual(jb["download_url"], "")
        self.assertIn(str(Path("/tmp/b-lab")), calls)
        learning_calls = [c for c in calls if c.startswith("@learning-v1 ")]
        self.assertEqual(len(learning_calls), 1)
        self.assertEqual(json.loads(learning_calls[0][13:])["repo_path"], str(Path("/tmp/a-lab")))
        page = web_server._render_job_page(dict(ja))
        self.assertIn("Mở trang học lại", page)
        self.assertIn("Tải HTML", page)
        self.assertNotIn("Gemini", page)
        self.assertNotIn("đóng vai", page)
        self.assertIn("Hiểu bài đã làm", page)

    def test_job_stays_queued_until_lock_and_can_be_cancelled(self):
        calls = []
        cleanup = Path(tempfile.mkdtemp(prefix="test-cancel-"))
        (cleanup / "README.md").write_text("x", encoding="utf-8")
        with mock.patch.object(web_server, "answer", _fake_answer_recorder(calls)):
            web_server._AGENT_LOCK.acquire()
            try:
                jid = web_server._start_job(cleanup, "c", "t:c", cleanup_dir=cleanup, mode="after_lab")
                time.sleep(0.2)
                self.assertEqual(web_server._JOBS[jid]["status"], "queued")
                self.assertIsNone(web_server._JOBS[jid]["started_at"])
                page = web_server._render_job_page(dict(web_server._JOBS[jid]))
                self.assertIn(f"/job/{jid}/cancel", page)
                self.assertIn("Hủy job", page)
                self.assertEqual(web_server._cancel_job(jid), "cancelled")
                self.assertEqual(web_server._cancel_job(jid), "not_cancellable")
                self.assertFalse(cleanup.exists())
            finally:
                web_server._AGENT_LOCK.release()
            time.sleep(0.3)
        self.assertEqual(web_server._JOBS[jid]["status"], "cancelled")
        self.assertEqual(calls, [])  # answer() không được gọi
        self.assertEqual(web_server._cancel_job("khong-ton-tai"), "not_found")

    def test_running_job_cannot_be_cancelled(self):
        gate = threading.Event()
        started = threading.Event()

        def slow_answer(text):
            started.set()
            gate.wait(5)
            return {"output": "Trang đóng vai: output/x.html"}

        with mock.patch.object(web_server, "answer", slow_answer):
            jid = web_server._start_job(Path("/tmp/r"), "r", "t:r", mode="before_lab")
            self.assertTrue(started.wait(5))
            self.assertEqual(web_server._JOBS[jid]["status"], "running")
            self.assertEqual(web_server._cancel_job(jid), "not_cancellable")
            gate.set()
            self._wait_status(jid, {"done"})


class QuietHandler(web_server.Handler):
    def log_message(self, fmt, *args):
        pass


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp(prefix="test-output-"))
        self.patcher = mock.patch.object(web_server, "OUTPUT_DIR", self.out.resolve())
        self.patcher.start()
        self.token = "tok-" + os.urandom(8).hex()
        self.learning_bytes = (
            "<!doctype html><html><head><meta charset=\"utf-8\"></head><body>\r\n<h1>Học lại</h1>"
            f"<p>{self.token}</p>\n</body></html>"
        ).encode("utf-8") + b"\n\xe2\x80\xa8tail"
        (self.out / LEARN_NAME).write_bytes(self.learning_bytes)
        (self.out / "roleplay-demo.html").write_text("<h1>Vai</h1><p>old</p>", encoding="utf-8")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.patcher.stop()
        shutil.rmtree(self.out, ignore_errors=True)

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp, data

    def test_learning_preview_is_raw_with_csp(self):
        resp, data = self.request("GET", f"/output/{LEARN_NAME}")
        self.assertEqual(resp.status, 200)
        self.assertEqual(data, self.learning_bytes)
        self.assertNotIn(b"bta-bar", data)
        self.assertEqual(resp.getheader("Content-Security-Policy"), web_server.LEARNING_CSP)
        self.assertEqual(resp.getheader("X-Content-Type-Options"), "nosniff")

    def test_download_is_attachment_and_checksum_identical(self):
        resp, data = self.request("GET", f"/download/{LEARN_NAME}")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Disposition"), f'attachment; filename="{LEARN_NAME}"')
        self.assertEqual(hashlib.sha256(data).hexdigest(), hashlib.sha256((self.out / LEARN_NAME).read_bytes()).hexdigest())

    def test_traversal_and_non_learning_downloads_404(self):
        for path in (
            "/download/roleplay-demo.html",
            "/download/learning-0123-89abcdef.html",
            f"/download/..%2F{LEARN_NAME}",
            f"/download/../output/{LEARN_NAME}",
            "/download/..%5C..%5Ccodebase%5Cweb_server.py",
            "/output/..%2F..%2Fcodebase%2Fagent.py",
            "/output/missing.html",
            f"/download/{LEARN_NAME.upper()}",
        ):
            with self.subTest(path=path):
                resp, _ = self.request("GET", path)
                self.assertEqual(resp.status, 404)

    def test_old_roleplay_page_keeps_enhancer(self):
        resp, data = self.request("GET", "/output/roleplay-demo.html")
        self.assertEqual(resp.status, 200)
        self.assertIn(b"bta-bar", data)
        self.assertIsNone(resp.getheader("Content-Security-Policy"))

    def test_home_lists_modes_and_page_kinds(self):
        resp, data = self.request("GET", "/")
        page = data.decode("utf-8")
        self.assertEqual(resp.status, 200)
        self.assertIn('name="mode" value="before_lab" checked', page)
        self.assertIn('value="after_lab"', page)
        self.assertIn("Chuẩn bị lab", page)
        self.assertIn("Hiểu bài đã làm", page)
        self.assertIn("Trang học lại", page)
        self.assertIn("Trang đóng vai", page)
        self.assertEqual(page.count("<legend>Mục đích sử dụng</legend>"), 3)

    def _post_form(self, path, fields):
        body = "&".join(f"{k}={v}" for k, v in fields.items()).encode("utf-8")
        return self.request("POST", path, body=body, headers={"Content-Type": "application/x-www-form-urlencoded"})

    def test_bogus_mode_is_400(self):
        resp, data = self._post_form("/generate-sample", {
            "csrf_token": web_server._make_csrf_token(), "mode": "bogus", "sample": "x",
        })
        self.assertEqual(resp.status, 400)
        self.assertIn("Chế độ không hợp lệ", data.decode("utf-8"))

    def test_github_after_lab_rejects_tree_url(self):
        resp, data = self._post_form("/generate-github", {
            "csrf_token": web_server._make_csrf_token(), "mode": "after_lab",
            "github_url": "https://github.com/owner/repo/tree/main/sub",
        })
        self.assertEqual(resp.status, 400)
        self.assertIn("chỉ nhận link gốc repo", data.decode("utf-8"))

    def _multipart(self, fields, files):
        boundary = "----testboundary" + os.urandom(6).hex()
        out = io.BytesIO()
        for k, v in fields:
            out.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8"))
        for field, fname, data in files:
            out.write(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{fname}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n".encode("utf-8")
            )
            out.write(data + b"\r\n")
        out.write(f"--{boundary}--\r\n".encode("utf-8"))
        return out.getvalue(), f"multipart/form-data; boundary={boundary}"

    def test_upload_zip_after_lab_registers_manifest_with_same_repo_path(self):
        registered = []
        calls = []
        zip_bytes = make_zip([("repo-x/README.md", b"# De"), ("repo-x/MISSION_ANSWERS.md", b"# Lam")])
        body, ctype = self._multipart(
            [("csrf_token", web_server._make_csrf_token()), ("mode", "after_lab")],
            [("archive", "repo-x.zip", zip_bytes)],
        )
        with mock.patch.object(web_server, "register_ingest_manifest", lambda p, m: registered.append((p, m))), \
                mock.patch.object(web_server, "answer", _fake_answer_recorder(calls)):
            resp, _ = self.request("POST", "/generate-upload", body=body, headers={"Content-Type": ctype})
            self.assertEqual(resp.status, 303)
            job_id = resp.getheader("Location").rsplit("/", 1)[1]
            self.assertTrue(wait_for(lambda: web_server._JOBS[job_id]["status"] == "done"))
        self.assertEqual(len(registered), 1)
        repo_path, manifest = registered[0]
        self.assertEqual(manifest["channel"], "zip")
        self.assertEqual(sorted(a["name"] for a in manifest["accepted"]), ["MISSION_ANSWERS.md", "README.md"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(json.loads(calls[0][len("@learning-v1 "):]), {"repo_path": repo_path})
        self.assertEqual(web_server._JOBS[job_id]["mode"], "after_lab")

    def test_upload_without_mode_keeps_before_lab(self):
        calls = []
        zip_bytes = make_zip([("lab/README.md", b"# De"), ("lab/main.py", b"print(1)")])
        body, ctype = self._multipart(
            [("csrf_token", web_server._make_csrf_token())], [("archive", "lab.zip", zip_bytes)]
        )
        with mock.patch.object(web_server, "answer", _fake_answer_recorder(calls)):
            resp, _ = self.request("POST", "/generate-upload", body=body, headers={"Content-Type": ctype})
            self.assertEqual(resp.status, 303)
            job_id = resp.getheader("Location").rsplit("/", 1)[1]
            self.assertTrue(wait_for(lambda: web_server._JOBS[job_id]["status"] == "done"))
        self.assertEqual(web_server._JOBS[job_id]["mode"], "before_lab")
        self.assertEqual(len(calls), 1)
        self.assertFalse(calls[0].startswith("@learning-v1"))

    def test_upload_after_lab_without_root_md_is_400(self):
        zip_bytes = make_zip([("a/b/README.md", b"# De")])
        body, ctype = self._multipart(
            [("csrf_token", web_server._make_csrf_token()), ("mode", "after_lab")],
            [("archive", "nested.zip", zip_bytes)],
        )
        resp, data = self.request("POST", "/generate-upload", body=body, headers={"Content-Type": ctype})
        self.assertEqual(resp.status, 400)
        self.assertIn("Markdown", data.decode("utf-8"))

    def test_cancel_endpoint_requires_csrf(self):
        calls = []
        with mock.patch.object(web_server, "answer", _fake_answer_recorder(calls)):
            web_server._AGENT_LOCK.acquire()
            try:
                jid = web_server._start_job(Path("/tmp/q"), "q", "t:q", mode="before_lab")
                time.sleep(0.1)
                resp, _ = self._post_form(f"/job/{jid}/cancel", {"csrf_token": "sai"})
                self.assertEqual(resp.status, 403)
                self.assertEqual(web_server._JOBS[jid]["status"], "queued")
                resp, _ = self._post_form(f"/job/{jid}/cancel", {"csrf_token": web_server._make_csrf_token()})
                self.assertEqual(resp.status, 303)
                self.assertEqual(web_server._JOBS[jid]["status"], "cancelled")
            finally:
                web_server._AGENT_LOCK.release()
            time.sleep(0.2)
        self.assertEqual(calls, [])
        self.assertEqual(web_server._JOBS[jid]["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
