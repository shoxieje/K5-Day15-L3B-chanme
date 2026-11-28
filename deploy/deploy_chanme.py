"""Deploy Be The Agent (chanme) lên VPS Ubuntu phía sau Cloudflare Tunnel.

Ví dụ:
    python deploy/deploy_chanme.py --ssh ubuntu@<VPS_IP> --key ~/.ssh/<key>
    python deploy/deploy_chanme.py --no-secrets   # chỉ cập nhật code, giữ nguyên /etc/chanme/chanme.env
    python deploy/deploy_chanme.py --dry-run      # xem trước lệnh sẽ chạy

Có thể đặt sẵn biến môi trường CHANME_VPS_SSH và CHANME_VPS_KEY để không cần gõ lặp lại.
Không bao giờ in API key / secrets ra màn hình; file secrets tạm trên VPS bị shred sau khi cài.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SERVER = os.environ.get("CHANME_VPS_SSH", "")
DEFAULT_KEY = Path(os.environ.get("CHANME_VPS_KEY", "")) if os.environ.get("CHANME_VPS_KEY") else None

CODEBASE_FILES = (
    "agent.py",
    "ai.py",
    "tools.py",
    "tracing.py",
    "web_server.py",
)


def ssh_options(key: Path | None) -> list[str]:
    return [
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        *(["-i", str(key), "-o", "IdentitiesOnly=yes"] if key else []),
    ]


def ssh_tool(name: str) -> str:
    tool = shutil.which(name) or shutil.which(name + ".exe")
    if not tool:
        raise SystemExit(f"Không tìm thấy {name} trong PATH.")
    return tool


def ssh_run(target: str, key: Path, command: str, dry: bool = False, check: bool = True) -> int:
    print("  $ ssh", target, "...")
    if dry:
        print("   ", command)
        return 0
    return subprocess.run([ssh_tool("ssh"), *ssh_options(key), target, command], check=check).returncode


def scp_run(target: str, key: Path, sources: list[str], dry: bool = False) -> int:
    print("  $ scp", *[Path(s).name for s in sources], f"{target}:~")
    if dry:
        return 0
    return subprocess.run([ssh_tool("scp"), "-r", *ssh_options(key), *sources, f"{target}:"], check=True).returncode


def build_bundle(out: Path) -> int:
    (out / "codebase").mkdir(parents=True, exist_ok=True)
    count = 0
    for name in CODEBASE_FILES:
        src = ROOT / "codebase" / name
        shutil.copy2(src, out / "codebase" / name)
        count += 1
    samples_src = ROOT / "deploy" / "sample_labs"
    if samples_src.is_dir():
        shutil.copytree(samples_src, out / "deploy" / "sample_labs")
        count += sum(1 for p in (out / "deploy" / "sample_labs").rglob("*") if p.is_file())
    # Chuẩn hóa line endings LF cho script Linux và systemd unit
    for fname in ("install.sh", "chanme.service"):
        text = (ROOT / "deploy" / fname).read_text(encoding="utf-8").replace("\r\n", "\n")
        (out / fname).write_text(text, encoding="utf-8", newline="\n")
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ssh", metavar="USER@HOST", default=DEFAULT_SERVER, help="VPS SSH target (hoặc đặt biến CHANME_VPS_SSH)")
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY, help="SSH private key (hoặc đặt biến CHANME_VPS_KEY)")
    parser.add_argument("--secrets", type=Path, default=ROOT / ".env", help="File .env chứa GEMINI_API_KEY (mặc định .env)")
    parser.add_argument("--no-secrets", action="store_true", help="Không gửi file secrets (giữ nguyên /etc/chanme/chanme.env)")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in thao tác, không deploy")
    args = parser.parse_args()

    if not args.ssh:
        raise SystemExit("Thiếu địa chỉ VPS: truyền --ssh USER@HOST hoặc đặt biến môi trường CHANME_VPS_SSH.")
    if args.key and not args.key.is_file():
        raise SystemExit(f"Không tìm thấy SSH key: {args.key}")
    secrets_file = None if args.no_secrets else (args.secrets if args.secrets.is_file() else None)

    with tempfile.TemporaryDirectory() as work:
        bundle_dir = Path(work) / "chanmebundle"
        nfiles = build_bundle(bundle_dir)
        print(f"Bundle: {nfiles} files")
        sources = [str(bundle_dir)]
        remote_secret = ""
        if secrets_file:
            # Copy secrets vào file tạm tên cố định với LF để không chạm vào .env gốc
            tmp_secret = Path(work) / "chanme.secrets"
            tmp_secret.write_text(
                secrets_file.read_text(encoding="utf-8-sig").replace("\r\n", "\n"),
                encoding="utf-8",
                newline="\n",
            )
            sources.append(str(tmp_secret))
            remote_secret = " ~/chanme.secrets"

        ssh_run(args.ssh, args.key, "rm -rf ~/chanmebundle ~/chanme.secrets", args.dry_run, check=False)
        scp_run(args.ssh, args.key, sources, args.dry_run)
        cmd = (
            f"sudo bash ~/chanmebundle/install.sh ~/chanmebundle{remote_secret}; "
            "status=$?; rm -rf ~/chanmebundle ~/chanme.secrets; exit $status"
        )
        ssh_run(args.ssh, args.key, cmd, args.dry_run, check=True)
    print("Deploy hoàn tất." if not args.dry_run else "Dry run xong.")


if __name__ == "__main__":
    main()
