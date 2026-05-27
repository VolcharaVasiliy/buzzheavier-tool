# Buzzheavier Tool

Buzzheavier Tool is a standalone Windows executable and Python CLI for uploading files to and downloading files from Buzzheavier.

## Features

- Interactive terminal menu for upload and download workflows.
- Multi-threaded downloads with resume, retry, cancellation, and `*.part` staging.
- Multipart uploads with configurable workers and part size.
- Anonymous uploads and authenticated uploads with `--login-id`.
- Buzzheavier mirror selection with `--site-host auto`.
- Optional use of the current Windows system proxy.
- PyInstaller build script for a standalone Windows executable.

## Requirements

- Python 3.8 or newer.
- `requests` for network transfers.

Install dependencies when running from source:

```bat
python -m pip install -r requirements.txt
```

## Usage

Start the interactive menu:

```bat
python buzzheavier_tool.py
```

Download a file by URL or id:

```bat
python buzzheavier_tool.py --threads 8 --proxy off download <file-url-or-id>
```

Upload a file:

```bat
python buzzheavier_tool.py upload <file-path>
```

Upload with authentication and a target parent folder:

```bat
python buzzheavier_tool.py --proxy on upload <file-path> --login-id <token> --parent-id <dir-id>
```

Tune multipart upload concurrency:

```bat
python buzzheavier_tool.py upload <file-path> --upload-workers 5 --upload-part-size 25MiB
```

## Command Reference

Global options:

- `--threads <n>`: download worker count, default `8`.
- `--proxy off|on`: use the current Windows system proxy for this run.
- `--site-host auto|buzzheavier.com|bzzhr.co|fuckingfast.net`: Buzzheavier host or mirror.
- `--stay-open`: wait for input before closing the console.
- `--staged-upload`: upload under a temporary remote name and rename after success.

Download:

```bat
python buzzheavier_tool.py download <file-url-or-id> [-o <output-dir>] [-f <output-file>]
```

Upload:

```bat
python buzzheavier_tool.py upload <file-path> [--login-id <token>] [--parent-id <dir-id>] [--location-id <location>] [--note <text>] [--name <remote-name>]
```

Location aliases include `eastern_europe`, `central_europe`, `western_europe`, `us_east`, `us_west`, and `apac`.

## Build Windows EXE

Build a standalone console executable with PyInstaller:

```powershell
.\build_exe.ps1
```

The build script writes generated files to `build/` and `dist/`. The main executable is:

```text
dist\BuzzheavierTool.exe
```

Compiled binaries are intentionally not committed to Git. Use GitHub Releases for distributing `.exe` files.
