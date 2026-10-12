# Changelog

## 0.2.2

- Fixed uploads stalling and never finishing on slow links or big files: part transfers (multipart `PATCH` and single-part `PUT`) now pass `stream=True`, so `curl_cffi` applies a low-speed watchdog instead of a fixed 20-second total request timeout (parts taking longer than 20 s were aborted with `curl: (28)` and retried from scratch forever).
- Fixed `HTTP 413` on large files: auto-selected part size is capped at 100 MiB (the server rejects oversized parts, observed with 2 GiB).

## 0.2.1

- Fixed uploads broken by the `curl_cffi` switch: file-like upload bodies (multipart part reader and single-part reader) are now streamed via `content=`, because `curl_cffi` rejects them in `data=` with `TypeError: data must be dict/list/tuple, str, BytesIO or bytes`.
- App icon switched to the first variant (hex-arrow).

## 0.2.0

- Switched HTTP transfers to `curl_cffi` with Chrome impersonation to pass Cloudflare checks, keeping `requests` as a fallback.
- Fixed downloads looping in the resolve step: the standard redirect is tried first, and redirects that point to a page instead of a file are skipped.
- Metadata checks reject HTML responses, so a page is never saved as a file.
- Download token is refreshed between resolve retries.

## 0.1.0

- Initial source import.
- Added standalone Windows EXE build configuration.
- Added documentation for interactive, download, upload, and EXE build flows.
- Accepted quoted Windows drag-and-drop paths.
- Added mirror latency checks for automatic host selection.
- Added direct-download URL handling.
- Added interactive 50 MiB, 100 MiB, auto, and custom upload part-size choices.
