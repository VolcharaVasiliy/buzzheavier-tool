# Changelog

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
