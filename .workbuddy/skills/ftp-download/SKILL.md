---
name: ftp-download
description: "FTP file downloader. Download files and directories from FTP/FTPS servers with support for recursive directory download, file pattern matching, resume of partial downloads, sync mode, dry-run listing, and TLS encryption. Trigger when downloading from an FTP server, fetching files via FTP, mirroring an FTP directory, or listing remote FTP contents. Keywords: FTP download, FTPS, recursive FTP, FTP sync, FTP resume, retrieve files from FTP."
agent_created: true
executable: false
---

# FTP Download

## Overview

Download files and directories from FTP/FTPS servers using a bundled Python script
(`scripts/ftp_download.py`) that requires **zero external dependencies** — it uses
only the Python standard library (`ftplib`, `argparse`, `fnmatch`, `os`, `pathlib`).

## When to Use

Trigger this skill when any of the following are requested:

- "Download a file from FTP server X"
- "Download all files from FTP directory /pub/data/"
- "Mirror an FTP directory recursively"
- "Download only CSV files from the FTP server"
- "List files on an FTP server (dry run)"
- "Resume a partially downloaded FTP file"
- "Sync local directory with FTP remote"
- "Connect to FTPS server and download"

## Quick Reference

### Script Location

```
{SKILL_DIR}/scripts/ftp_download.py
```

### Python Runtime

Use the managed Python:

```
C:\Users\viaco\.workbuddy\binaries\python\versions\3.13.12\python.exe
```

On Linux/macOS, use system `python3`.

### Basic Syntax

```bash
python ftp_download.py --host <host> [options] <remote_path> [<local_path>]
```

## Workflow

### Step 1: Determine Download Parameters

Collect or infer the following information before running the script:

| Parameter    | Required | Default              | Notes                                      |
|--------------|----------|----------------------|--------------------------------------------|
| `--host`     | Yes      | —                    | FTP server hostname or IP                   |
| `--port`     | No       | 21 (990 for implicit TLS) | FTP port                               |
| `-u`         | No       | anonymous            | Username                                    |
| `-p`         | No       | anonymous email      | Password                                    |
| `--tls`      | No       | off                  | `explicit` (AUTH TLS on 21) or `implicit` (TLS on 990) |
| `--passive`  | No       | True                 | Use passive mode (recommended)              |
| `--active`   | No       | —                    | Use active mode instead of passive          |
| `--timeout`  | No       | 30                   | Socket timeout in seconds                   |
| `-r`         | No       | False                | Recursively download directories             |
| `--pattern`  | No       | * (all)              | Glob filter, e.g. `*.csv` (requires `-r`)   |
| `--policy`   | No       | overwrite            | `overwrite` / `skip` / `resume` / `sync`    |
| `--resume`   | No       | —                    | Shortcut for `--policy resume`              |
| `--dry-run`  | No       | False                | List files without downloading               |
| `-q`         | No       | False                | Suppress progress output                     |
| `remote_path`| Yes      | —                    | Remote file or directory path                |
| `local_path` | No       | `.` (current dir)    | Local destination path                       |

### Step 2: Execute the Download

Run the script using the managed Python runtime. The script handles:

- **Single file**: Pass a file path as `remote_path`; `local_path` can be a file or directory.
- **Directory (recursive)**: Add `-r` flag; all files in the directory tree are downloaded,
  preserving the remote directory structure locally.
- **Pattern matching**: Use `--pattern "*.csv"` with `-r` to filter by filename.
- **Dry run**: Use `--dry-run` to list files that would be downloaded without actually downloading.

### Step 3: Verify Results

The script prints a summary to stderr showing files downloaded, skipped, failed,
total bytes, elapsed time, and average speed. Check exit codes:

| Exit Code | Meaning                          |
|-----------|----------------------------------|
| 0         | Success                          |
| 1         | Connection failure               |
| 2         | Some files failed to download    |
| 3         | FTP permission error             |
| 4         | FTP temporary error              |
| 130       | Interrupted by user (Ctrl+C)     |

## Common Usage Patterns

### Download a Single File

```bash
python ftp_download.py --host ftp.example.com /pub/file.zip ./file.zip
```

### Download with Authentication

```bash
python ftp_download.py --host ftp.example.com -u myuser -p mypass /pub/file.zip
```

### Recursive Directory Download

```bash
python ftp_download.py --host ftp.example.com -r /pub/data/ ./data/
```

### Download Only Matching Files (Pattern)

```bash
python ftp_download.py --host ftp.example.com -r --pattern "*.csv" /pub/reports/ ./reports/
```

### FTPS (Explicit TLS)

```bash
python ftp_download.py --host ftp.example.com --tls explicit -u user -p pass -r /data/ ./data/
```

### Resume Partial Downloads

```bash
python ftp_download.py --host ftp.example.com --resume /pub/bigfile.zip ./bigfile.zip
```

### Sync Local Directory with Remote (Skip Unchanged)

```bash
python ftp_download.py --host ftp.example.com -r --policy sync /pub/data/ ./data/
```

### Dry Run (List Files Only)

```bash
python ftp_download.py --host ftp.example.com -r --dry-run /pub/data/
```

### Active Mode (Behind Firewall/NAT)

```bash
python ftp_download.py --host ftp.example.com --active -r /pub/data/ ./data/
```

## Overwrite Policies

| Policy      | Behavior                                                         |
|-------------|------------------------------------------------------------------|
| `overwrite` | Always download, overwriting local file (default)                |
| `skip`      | Skip if local file exists                                        |
| `resume`    | Resume download from partial file (uses REST command)            |
| `sync`      | Download only if file size differs; skip if sizes match          |

## Error Handling

- **Permission denied** (`error_perm`): Logged as `[FAIL]`, download continues to next file.
- **Temporary errors** (`error_temp`): Logged as `[FAIL]`, download continues.
- **Connection failure**: Script exits with code 1.
- **Interrupted (Ctrl+C)**: Script exits with code 130, partial files may remain.
- **MLSD not supported**: Automatically falls back to `LIST` + parse.

## 用户提示
可以使用迅雷下载ftp 的资源，支持断点续传，且下载速度一般会更快。
## Notes

- The script uses Python's standard `ftplib` — no `pip install` needed.
- Passive mode is the default (recommended for most NAT/firewall setups).
- For FTPS implicit mode, port defaults to 990 if not specified.
- Progress output goes to stderr; file list in dry-run mode goes to stdout.
- Directory structure is preserved: remote `/pub/data/sub/file.txt` downloads to
  `local_base/data/sub/file.txt` (relative path preserved).
