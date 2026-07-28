#!/usr/bin/env python3
"""
FTP Downloader - Download files and directories from FTP servers.

Supports:
  - Single file download
  - Recursive directory download
  - File pattern matching (glob-style)
  - Authentication (username/password)
  - Active/Passive transfer mode
  - TLS/SSL (FTPS) connections
  - Resume partial downloads (REST + APPE)
  - Progress reporting
  - Dry-run mode (list only, no download)
  - Overwrite/skip/sync policies

Usage:
  python ftp_download.py --host <host> [options] <remote_path> [<local_path>]

Examples:
  # Download a single file
  python ftp_download.py --host ftp.example.com /pub/file.zip ./file.zip

  # Download a directory recursively
  python ftp_download.py --host ftp.example.com -r /pub/data/ ./data/

  # Use authentication + passive mode
  python ftp_download.py --host ftp.example.com -u user -p pass --passive /pub/file.zip

  # Download files matching a pattern
  python ftp_download.py --host ftp.example.com -r --pattern "*.csv" /pub/reports/ ./reports/

  # FTPS (explicit TLS)
  python ftp_download.py --host ftp.example.com --tls explicit -u user -p pass -r /data/ ./data/

  # Dry-run: list files that would be downloaded
  python ftp_download.py --host ftp.example.com -r --dry-run /pub/data/

  # Resume partial downloads
  python ftp_download.py --host ftp.example.com --resume /pub/bigfile.zip ./bigfile.zip

Author: WorkBuddy Skill (ftp_download)
License: MIT
"""

import argparse
import fnmatch
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# ftplib is part of the Python standard library — no external deps required.
from ftplib import FTP, FTP_TLS, error_perm, error_temp, error_reply


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class ProgressReporter:
    """Print download progress to stderr (so stdout stays clean for machine use)."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._last_pct = -1

    def file_start(self, remote_path: str, size: int | None):
        if not self.verbose:
            return
        size_str = _human_size(size) if size else "?"
        print(f"[DOWNLOAD] {remote_path}  ({size_str})", file=sys.stderr)

    def file_progress(self, remote_path: str, downloaded: int, total: int | None):
        if not self.verbose or total is None or total <= 0:
            return
        pct = int(downloaded * 100 / total)
        # Only print on every 5% change to avoid flooding
        if pct != self._last_pct and pct % 5 == 0:
            self._last_pct = pct
            bar = _progress_bar(pct)
            print(f"\r  {bar} {pct}%  ({_human_size(downloaded)}/{_human_size(total)})",
                  end="", file=sys.stderr, flush=True)

    def file_done(self, remote_path: str, success: bool, elapsed: float, size: int):
        if not self.verbose:
            return
        status = "OK" if success else "FAIL"
        speed = _human_size(size / elapsed) if elapsed > 0 and success else "-"
        print(f"\r  [{'OK' if success else 'FAIL'}] {remote_path}  "
              f"{_human_size(size)} in {elapsed:.1f}s ({speed}/s)"
              + " " * 20, file=sys.stderr)
        self._last_pct = -1

    def summary(self, total_files: int, total_bytes: int, elapsed: float,
                skipped: int = 0, failed: int = 0):
        if not self.verbose:
            return
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"  Downloaded: {total_files} files ({_human_size(total_bytes)})", file=sys.stderr)
        if skipped:
            print(f"  Skipped:    {skipped} files", file=sys.stderr)
        if failed:
            print(f"  Failed:     {failed} files", file=sys.stderr)
        print(f"  Time:       {elapsed:.1f}s", file=sys.stderr)
        if elapsed > 0:
            print(f"  Avg speed:  {_human_size(total_bytes / elapsed)}/s", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)


def _human_size(n: int | None) -> str:
    """Format byte count as human-readable string."""
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0
    return f"{n:.1f} PB"


def _progress_bar(pct: int, width: int = 24) -> str:
    filled = int(width * pct / 100)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _ensure_local_dir(local_path: str):
    """Create parent directory for local_path if it doesn't exist."""
    parent = os.path.dirname(local_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _should_download(remote_path: str, local_path: str,
                     size_remote: int | None,
                     policy: str) -> tuple[bool, str, int]:
    """
    Decide whether to download a file based on the overwrite policy.

    Returns: (should_download, reason, resume_offset)
    """
    if not os.path.exists(local_path):
        return True, "new file", 0

    local_size = os.path.getsize(local_path)

    if policy == "overwrite":
        return True, "overwrite", 0

    if policy == "skip":
        return False, "skip (exists)", 0

    if policy == "resume":
        if size_remote is not None and local_size < size_remote:
            return True, f"resume from {local_size}", local_size
        if size_remote is not None and local_size == size_remote:
            return False, "skip (complete)", 0
        # size unknown — re-download to be safe
        return True, "resume (size unknown)", 0

    if policy == "sync":
        if size_remote is not None and local_size != size_remote:
            return True, f"sync (size differs: {local_size} -> {size_remote})", 0
        return False, "skip (in sync)", 0

    # Default: overwrite
    return True, "overwrite (default)", 0


# ---------------------------------------------------------------------------
# FTP Connection
# ---------------------------------------------------------------------------

def connect(host: str, port: int, user: str | None, password: str | None,
            tls: str | None, passive: bool, timeout: float) -> FTP:
    """
    Establish an FTP/FTPS connection and log in.

    Args:
        host: FTP server hostname or IP.
        port: FTP port (default 21).
        user: Username (None for anonymous).
        password: Password (None for anonymous).
        tls: None = plain FTP; "explicit" = FTPS (AUTH TLS); "implicit" = implicit TLS on 990.
        passive: True for passive mode, False for active.
        timeout: Socket timeout in seconds.

    Returns:
        Connected and logged-in FTP (or FTP_TLS) instance.
    """
    if tls == "implicit":
        # Implicit TLS — typically on port 990
        ftp = FTP_TLS(timeout=timeout)
        ftp.connect(host, port or 990)
        ftp.prot_p()  # Protect data connection
    elif tls == "explicit":
        # Explicit TLS — upgrade plain FTP to TLS
        ftp = FTP_TLS(timeout=timeout)
        ftp.connect(host, port or 21)
        ftp.login(user or "anonymous", password or "")
        ftp.prot_p()  # Protect data connection
    else:
        # Plain FTP
        ftp = FTP(timeout=timeout)
        ftp.connect(host, port or 21)
        ftp.login(user or "anonymous", password or "")

    ftp.set_pasv(passive)
    return ftp


# ---------------------------------------------------------------------------
# File Listing
# ---------------------------------------------------------------------------

def list_files(ftp: FTP, remote_dir: str, recursive: bool,
               pattern: str | None = None) -> list[dict]:
    """
    List files in remote_dir, optionally recursing into subdirectories.

    Returns a list of dicts:
      {"path": "/remote/dir/file.txt", "size": 12345, "is_dir": False}
    """
    results: list[dict] = []
    _walk_ftp(ftp, remote_dir, recursive, pattern, results)
    return results


def _walk_ftp(ftp: FTP, current_dir: str, recursive: bool,
              pattern: str | None, results: list[dict]):
    """Recursively walk FTP directory tree."""
    try:
        entries = _mlsd_or_list(ftp, current_dir)
    except error_perm:
        # Permission denied — skip
        return

    for name, facts in entries:
        if name in (".", ".."):
            continue
        full_path = f"{current_dir.rstrip('/')}/{name}"

        is_dir = facts.get("type", "") == "dir" or name.endswith("/")
        size = facts.get("size")
        if isinstance(size, str):
            try:
                size = int(size)
            except ValueError:
                size = None

        if is_dir:
            if recursive:
                _walk_ftp(ftp, full_path, recursive, pattern, results)
        else:
            if pattern is None or fnmatch.fnmatch(name, pattern):
                results.append({"path": full_path, "size": size, "is_dir": False})


def _mlsd_or_list(ftp: FTP, path: str) -> list[tuple[str, dict]]:
    """
    Try MLSD first (structured), fall back to LIST + parse.

    Returns list of (name, facts_dict) tuples.
    """
    # Try MLSD (modern, structured)
    try:
        lines = []
        ftp.mlsd(path, lines.append) if hasattr(ftp, "mlsd") else None
        # In Python 3.x, ftp.mlsd returns a generator
        entries = list(ftp.mlsd(path))
        return [(name, facts) for name, facts in entries]
    except (error_perm, AttributeError):
        pass

    # Fall back to LIST (legacy)
    lines = []
    ftp.cwd(path)
    ftp.retrlines("LIST", lines.append)
    ftp.cwd("/")

    entries = []
    for line in lines:
        parsed = _parse_list_line(line)
        if parsed:
            entries.append(parsed)
    return entries


def _parse_list_line(line: str) -> tuple[str, dict] | None:
    """Parse a UNIX-style LIST line into (name, facts)."""
    parts = line.split()
    if len(parts) < 9:
        return None
    # UNIX format: drwxr-xr-x 2 user group 4096 Jan 1 12:00 dirname
    perms = parts[0]
    name = " ".join(parts[8:])
    is_dir = perms.startswith("d")
    size_str = parts[4]
    try:
        size = int(size_str)
    except ValueError:
        size = None
    return (name, {"type": "dir" if is_dir else "file", "size": size})


# ---------------------------------------------------------------------------
# Download Operations
# ---------------------------------------------------------------------------

def download_file(ftp: FTP, remote_path: str, local_path: str,
                  resume_offset: int = 0,
                  reporter: ProgressReporter | None = None) -> int:
    """
    Download a single file from FTP.

    Args:
        ftp: Connected FTP instance.
        remote_path: Path on the FTP server.
        local_path: Local destination path.
        resume_offset: Byte offset to resume from (0 = from start).
        reporter: Optional progress reporter.

    Returns:
        Number of bytes downloaded.

    Raises:
        Exception on download failure.
    """
    _ensure_local_dir(local_path)

    mode = "ab" if resume_offset > 0 else "wb"

    if resume_offset > 0:
        ftp.voidcmd("TYPE I")
        ftp.sendcmd(f"REST {resume_offset}")

    downloaded = resume_offset

    def _write_block(data: bytes):
        nonlocal downloaded
        local_file.write(data)
        downloaded += len(data)
        if reporter:
            reporter.file_progress(remote_path, downloaded, _file_size)

    _file_size = None
    try:
        # Try to get file size first
        try:
            ftp.voidcmd("TYPE I")
            _file_size = ftp.size(remote_path)
        except (error_perm, OSError):
            _file_size = None
    except Exception:
        _file_size = None

    if reporter:
        reporter.file_start(remote_path, _file_size)

    start_time = time.time()

    with open(local_path, mode) as local_file:
        if resume_offset > 0:
            ftp.retrbinary(f"RETR {remote_path}", _write_block, rest=resume_offset)
        else:
            ftp.retrbinary(f"RETR {remote_path}", _write_block)

    elapsed = time.time() - start_time
    if reporter:
        reporter.file_done(remote_path, True, elapsed, downloaded)

    return downloaded


def download_many(ftp: FTP, files: list[dict], local_base: str,
                  remote_base: str, policy: str,
                  reporter: ProgressReporter | None = None) -> dict:
    """
    Download multiple files.

    Args:
        ftp: Connected FTP instance.
        files: List of file dicts from list_files().
        local_base: Local base directory.
        remote_base: Remote base directory (stripped from paths to create relative local paths).
        policy: Overwrite policy: "overwrite", "skip", "resume", "sync".
        reporter: Progress reporter.

    Returns:
        Dict with summary: {downloaded, skipped, failed, total_bytes}
    """
    summary = {"downloaded": 0, "skipped": 0, "failed": 0, "total_bytes": 0}

    for f in files:
        remote_path = f["path"]
        size_remote = f.get("size")

        # Compute relative path
        rel_path = remote_path
        if remote_base and remote_path.startswith(remote_base):
            rel_path = remote_path[len(remote_base):].lstrip("/")
        local_path = os.path.join(local_base, rel_path.replace("/", os.sep))

        should, reason, resume_offset = _should_download(
            remote_path, local_path, size_remote, policy
        )

        if not should:
            if reporter and reporter.verbose:
                print(f"  [SKIP] {remote_path}  ({reason})", file=sys.stderr)
            summary["skipped"] += 1
            continue

        try:
            # If resuming, the file already exists with partial data
            # If overwriting, remove existing file first
            if os.path.exists(local_path) and resume_offset == 0:
                os.remove(local_path)

            bytes_downloaded = download_file(
                ftp, remote_path, local_path, resume_offset, reporter
            )
            summary["downloaded"] += 1
            summary["total_bytes"] += bytes_downloaded
        except (error_perm, error_temp, error_reply) as e:
            summary["failed"] += 1
            if reporter and reporter.verbose:
                print(f"  [FAIL] {remote_path}  ({e})", file=sys.stderr)
        except OSError as e:
            summary["failed"] += 1
            if reporter and reporter.verbose:
                print(f"  [FAIL] {remote_path}  ({e})", file=sys.stderr)

    return summary


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ftp_download",
        description="Download files and directories from an FTP server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Connection options
    conn = parser.add_argument_group("Connection")
    conn.add_argument("--host", required=True, help="FTP server hostname or IP")
    conn.add_argument("--port", type=int, default=21, help="FTP port (default: 21)")
    conn.add_argument("-u", "--user", default=None, help="Username (default: anonymous)")
    conn.add_argument("-p", "--password", default=None, help="Password (default: anonymous@example.com)")
    conn.add_argument("--tls", choices=["explicit", "implicit"], default=None,
                      help="TLS mode: explicit (AUTH TLS on 21) or implicit (TLS on 990)")
    conn.add_argument("--passive", action="store_true", default=True,
                      help="Use passive mode (default: True)")
    conn.add_argument("--active", dest="passive", action="store_false",
                      help="Use active mode instead of passive")
    conn.add_argument("--timeout", type=float, default=30.0,
                      help="Socket timeout in seconds (default: 30)")

    # Download options
    dl = parser.add_argument_group("Download")
    dl.add_argument("-r", "--recursive", action="store_true",
                    help="Download directories recursively")
    dl.add_argument("--pattern", default=None,
                    help='Glob pattern to filter files (e.g. "*.csv"). Only applies with -r.')
    dl.add_argument("--policy", choices=["overwrite", "skip", "resume", "sync"],
                    default="overwrite",
                    help="Overwrite policy for existing local files (default: overwrite)")
    dl.add_argument("--resume", dest="policy", action="store_const", const="resume",
                    help="Shortcut for --policy resume")
    dl.add_argument("--dry-run", action="store_true",
                    help="List files that would be downloaded, but do not download")

    # Output
    out = parser.add_argument_group("Output")
    out.add_argument("-q", "--quiet", action="store_true",
                     help="Suppress progress output")
    out.add_argument("-v", "--verbose", action="store_true", default=True,
                     help="Show detailed progress (default)")

    # Positional arguments
    parser.add_argument("remote_path", help="Remote file or directory path on the FTP server")
    parser.add_argument("local_path", nargs="?", default=".",
                        help="Local destination path (default: current directory)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    reporter = ProgressReporter(verbose=not args.quiet)

    # Connect
    if reporter.verbose:
        print(f"[CONNECT] {args.host}:{args.port} "
              f"(TLS={args.tls or 'off'}, passive={args.passive})", file=sys.stderr)

    try:
        ftp = connect(
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            tls=args.tls,
            passive=args.passive,
            timeout=args.timeout,
        )
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}", file=sys.stderr)
        sys.exit(1)

    start_time = time.time()

    try:
        # Determine if remote_path is a file or directory
        is_dir = False
        try:
            # Try CWD to the path — if it works, it's a directory
            ftp.cwd(args.remote_path)
            ftp.cwd("/")
            is_dir = True
        except error_perm:
            is_dir = False

        if is_dir or args.recursive:
            # Directory download
            if reporter.verbose:
                mode = "recursive" if args.recursive else "directory"
                print(f"[LIST] {args.remote_path} ({mode}, pattern={args.pattern or '*'})",
                      file=sys.stderr)

            files = list_files(ftp, args.remote_path, recursive=args.recursive,
                               pattern=args.pattern)

            if not files:
                if reporter.verbose:
                    print("[INFO] No files found matching criteria.", file=sys.stderr)
                sys.exit(0)

            if reporter.verbose:
                total_size = sum(f.get("size", 0) or 0 for f in files)
                print(f"[FOUND] {len(files)} files, total {_human_size(total_size)}",
                      file=sys.stderr)

            if args.dry_run:
                if reporter.verbose:
                    print(f"\n{'=' * 60}", file=sys.stderr)
                    print("  DRY RUN — no files will be downloaded", file=sys.stderr)
                    print(f"{'=' * 60}\n", file=sys.stderr)
                for f in files:
                    print(f"  {f['path']}  ({_human_size(f.get('size'))})")
                sys.exit(0)

            local_base = args.local_path
            remote_base = args.remote_path

            result = download_many(
                ftp, files, local_base, remote_base,
                policy=args.policy, reporter=reporter
            )

            elapsed = time.time() - start_time
            reporter.summary(
                total_files=result["downloaded"],
                total_bytes=result["total_bytes"],
                elapsed=elapsed,
                skipped=result["skipped"],
                failed=result["failed"],
            )

            if result["failed"] > 0:
                sys.exit(2)

        else:
            # Single file download
            if reporter.verbose:
                print(f"[FILE] {args.remote_path}", file=sys.stderr)

            # Determine local path
            if os.path.isdir(args.local_path):
                local_file = os.path.join(args.local_path,
                                          os.path.basename(args.remote_path))
            else:
                local_file = args.local_path

            # Get remote file size
            try:
                ftp.voidcmd("TYPE I")
                remote_size = ftp.size(args.remote_path)
            except (error_perm, OSError):
                remote_size = None

            should, reason, resume_offset = _should_download(
                args.remote_path, local_file, remote_size, args.policy
            )

            if not should:
                if reporter.verbose:
                    print(f"  [SKIP] {reason}", file=sys.stderr)
                sys.exit(0)

            if args.dry_run:
                print(f"  {args.remote_path}  ({_human_size(remote_size)}) -> {local_file}")
                sys.exit(0)

            if os.path.exists(local_file) and resume_offset == 0:
                os.remove(local_file)

            bytes_downloaded = download_file(
                ftp, args.remote_path, local_file, resume_offset, reporter
            )

            elapsed = time.time() - start_time
            reporter.summary(
                total_files=1,
                total_bytes=bytes_downloaded,
                elapsed=elapsed,
            )

    except error_perm as e:
        print(f"[ERROR] FTP permission error: {e}", file=sys.stderr)
        sys.exit(3)
    except error_temp as e:
        print(f"[ERROR] FTP temporary error: {e}", file=sys.stderr)
        sys.exit(4)
    except KeyboardInterrupt:
        print("\n[ABORT] Download interrupted by user.", file=sys.stderr)
        sys.exit(130)
    finally:
        try:
            ftp.quit()
        except Exception:
            try:
                ftp.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
