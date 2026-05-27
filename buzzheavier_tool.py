#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function

import argparse
import base64
import ctypes
import http.client
import json
import os
import queue
import re
import ssl
import subprocess
import sys
import time
import threading
import traceback
import shutil
from urllib.parse import urlencode, urlsplit, quote
try:
    import winreg
except ImportError:
    winreg = None

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR

VENDOR_DIR = os.path.join(BUNDLE_DIR, "vendor")
if os.path.isdir(VENDOR_DIR) and VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)

try:
    import requests
except ImportError:
    requests = None


DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "buzzheavier")
DEFAULT_UPLOAD_LOCATION = "eastern_europe"
DEFAULT_DOWNLOAD_THREADS = 8
DEFAULT_UPLOAD_WORKERS = 5
DOWNLOAD_RETRY_LIMIT = 4
UPLOAD_RETRY_LIMIT = 5
FIRST_BYTE_TIMEOUT_MULTI = 30
FIRST_BYTE_TIMEOUT_SINGLE = 45
NETWORK_IO_TIMEOUT = 12
DOWNLOAD_CHUNK_SIZE = 64 * 1024
UPLOAD_CHUNK_SIZE = 256 * 1024
UPLOAD_MIN_PART_SIZE = 5 * 1024 * 1024
UPLOAD_MAX_PART_SIZE = 100 * 1024 * 1024 * 1024
UPLOAD_MAX_PARTS = 10000
UPLOAD_MAX_FILE_SIZE = 1024 * 1024 * 1024 * 1024
USER_AGENT = "Buzzheavier Tool"
SPINNER_FRAMES = ["|", "/", "-", "\\"]
MENU_POINTER = ">"
PART_SUFFIX = ".part"
WRAPPING_QUOTES = "\"'“”‘’"
MIRROR_LATENCY_ATTEMPTS = 3
MIRROR_LATENCY_PATH = "/api/locations"

OFFICIAL_SITE_HOST = "buzzheavier.com"
SITE_HOSTS = [
    OFFICIAL_SITE_HOST,
    "bzzhr.co",
    "fuckingfast.net",
]
API_HOST = OFFICIAL_SITE_HOST
UPLOAD_HOST = "w." + OFFICIAL_SITE_HOST
UPLOAD_INIT_PATH = "/api/upload"
UPLOAD_PART_HEADER_LENGTH = "Upload-Length"
UPLOAD_PART_HEADER_NUMBER = "Upload-Part-Number"

SITE_HOST_LABELS = {
    "auto": "Auto",
    "buzzheavier.com": "buzzheavier.com",
    "bzzhr.co": "bzzhr.co",
    "fuckingfast.net": "fuckingfast.net",
}

SITE_HOST_MENU_ITEMS = [
    {"label": "Auto", "value": "auto", "hint": "Probe available mirror"},
    {"label": "buzzheavier.com", "value": "buzzheavier.com"},
    {"label": "bzzhr.co", "value": "bzzhr.co"},
    {"label": "fuckingfast.net", "value": "fuckingfast.net"},
]

UPLOAD_PART_SIZE_MENU_ITEMS = [
    {"label": "50 MiB", "value": "50MiB", "hint": "Balanced"},
    {"label": "100 MiB", "value": "100MiB", "hint": "Fewer parts"},
    {"label": "Auto", "value": "__auto__", "hint": "Size from file/workers"},
    {"label": "Custom value", "value": "__custom__", "hint": "Type manually"},
]

LOCATION_MAP = {
    "central": "3eb9t1559lkv",
    "central_europe": "3eb9t1559lkv",
    "western_europe": "m8sx6tb1ngx0",
    "west_europe": "m8sx6tb1ngx0",
    "europe_west": "m8sx6tb1ngx0",
    "euw": "m8sx6tb1ngx0",
    "europe": "m8sx6tb1ngx0",
    "west": "95542dt0et21",
    "western_us": "95542dt0et21",
    "us_west": "95542dt0et21",
    "east": "12brteedoy0f",
    "eastern_us": "12brteedoy0f",
    "us_east": "12brteedoy0f",
    "east_europe": "5urmb0o0baxx",
    "eastern_europe": "5urmb0o0baxx",
    "apac": "g65gmc5rfv2c",
    "asia_pacific": "g65gmc5rfv2c",
}

LOCATION_MENU_ITEMS = [
    {"label": "Eastern Europe", "value": "eastern_europe", "hint": "Default"},
    {"label": "Central Europe", "value": "central_europe"},
    {"label": "Western Europe", "value": "western_europe"},
    {"label": "US East", "value": "us_east"},
    {"label": "US West", "value": "us_west"},
    {"label": "APAC", "value": "apac"},
    {"label": "Custom location id or alias", "value": "__custom__", "hint": "Type manually"},
]

LOCATION_LABELS = {
    "eastern_europe": "Eastern Europe",
    "east_europe": "Eastern Europe",
    "central_europe": "Central Europe",
    "central": "Central Europe",
    "western_europe": "Western Europe",
    "west_europe": "Western Europe",
    "europe_west": "Western Europe",
    "euw": "Western Europe",
    "europe": "Western Europe",
    "us_east": "US East",
    "east": "US East",
    "eastern_us": "US East",
    "us_west": "US West",
    "west": "US West",
    "western_us": "US West",
    "apac": "APAC",
    "asia_pacific": "APAC",
}

LOCATION_ID_LABELS = {
    "5urmb0o0baxx": "Eastern Europe",
    "3eb9t1559lkv": "Central Europe",
    "m8sx6tb1ngx0": "Western Europe",
    "12brteedoy0f": "US East",
    "95542dt0et21": "US West",
    "g65gmc5rfv2c": "APAC",
}


class Ansi(object):
    RESET = "\x1b[0m"
    BOLD = "\x1b[1m"
    DIM = "\x1b[2m"
    RED = "\x1b[31m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    BLUE = "\x1b[34m"
    MAGENTA = "\x1b[35m"
    CYAN = "\x1b[36m"
    WHITE = "\x1b[37m"


class DownloadCancelled(Exception):
    pass


class UserInputUnavailable(Exception):
    pass


def enable_virtual_terminal():
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def supports_color():
    return has_console_handle(-11) or sys.stdout.isatty()


def has_console_handle(std_handle):
    if os.name != "nt":
        return False
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(std_handle)
        if handle in (0, -1):
            return False
        mode = ctypes.c_uint()
        return bool(kernel32.GetConsoleMode(handle, ctypes.byref(mode)))
    except Exception:
        return False


def color(text, code):
    if not supports_color():
        return text
    return code + text + Ansi.RESET


def clear_line():
    if supports_color():
        return "\r\x1b[2K"
    return "\r" + (" " * 160) + "\r"


def clear_screen():
    if os.name == "nt":
        os.system("cls")
    else:
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.flush()


def is_interactive_console():
    if os.name == "nt":
        return has_console_handle(-10) and has_console_handle(-11)
    return sys.stdin.isatty() and sys.stdout.isatty()


def color_bool(enabled):
    return color("ON", Ansi.GREEN + Ansi.BOLD) if enabled else color("OFF", Ansi.DIM)


def color_latency(ms):
    if ms is None:
        return color("failed", Ansi.RED + Ansi.BOLD)
    text = "{0:.0f} ms".format(ms)
    if ms <= 180:
        return color(text, Ansi.GREEN + Ansi.BOLD)
    if ms <= 450:
        return color(text, Ansi.YELLOW + Ansi.BOLD)
    return color(text, Ansi.RED + Ansi.BOLD)


def color_path(path):
    return color(path, Ansi.CYAN + Ansi.BOLD)


def shorten_text(text, max_len):
    if text is None:
        return ""
    text = str(text)
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3] + "..."


def print_banner():
    print(color("Buzzheavier Tool", Ansi.CYAN + Ansi.BOLD))
    print(color("Use arrows to choose, Enter to confirm, Esc to cancel.", Ansi.DIM))
    print("")


def safe_remove_file(path):
    if path and os.path.exists(path):
        os.remove(path)


def unwrap_drag_drop_value(value):
    if value is None:
        return None
    text = str(value).strip()
    while len(text) >= 2 and text[0] in WRAPPING_QUOTES and text[-1] in WRAPPING_QUOTES:
        text = text[1:-1].strip()
    return text


def is_retryable_download_error(exc):
    retryable = (
        TimeoutError,
        OSError,
        ssl.SSLError,
        http.client.HTTPException,
    )
    return isinstance(exc, retryable)


def is_retryable_upload_error(exc):
    retryable = (
        TimeoutError,
        OSError,
        ssl.SSLError,
        http.client.HTTPException,
    )
    if isinstance(exc, retryable):
        return True
    if requests is not None:
        return isinstance(exc, requests.RequestException)
    return False


def temp_download_path(output_file):
    return output_file + PART_SUFFIX


def can_read_single_key():
    return os.name == "nt" and has_console_handle(-10)


def safe_input(prompt, default=None, allow_empty=False):
    try:
        value = unwrap_drag_drop_value(input(prompt))
    except EOFError:
        if default is not None:
            return default
        if allow_empty:
            return ""
        raise UserInputUnavailable("Interactive input is not available in this console.")
    if value:
        return value
    if default is not None:
        return default
    if allow_empty:
        return ""
    return value


def read_single_key():
    if not can_read_single_key():
        return None
    import msvcrt

    while True:
        key = msvcrt.getwch()
        if key in ("\x00", "\xe0"):
            key2 = msvcrt.getwch()
            special = {
                "H": "up",
                "P": "down",
                "K": "left",
                "M": "right",
            }
            return special.get(key2)
        if key == "\r":
            return "enter"
        if key == "\x1b":
            return "esc"
        if key.lower() == "q":
            return "quit"
        return key


def choose_menu_option(title, items, selected_value=None):
    if not can_read_single_key():
        default_index = 0
        if selected_value is not None:
            for index, item in enumerate(items):
                if item["value"] == selected_value:
                    default_index = index
                    break
        print(title)
        for index, item in enumerate(items, 1):
            print("{0}) {1}".format(index, item["label"]))
        raw = safe_input("Choose [1-{0}]: ".format(len(items)), default=str(default_index + 1))
        selected = max(1, min(len(items), int(raw))) - 1
        return items[selected]["value"]

    selected = 0
    if selected_value is not None:
        for index, item in enumerate(items):
            if item["value"] == selected_value:
                selected = index
                break
    while True:
        clear_screen()
        print_banner()
        print(color(title, Ansi.WHITE + Ansi.BOLD))
        print("")
        for index, item in enumerate(items):
            active = index == selected
            pointer = color(MENU_POINTER, Ansi.YELLOW + Ansi.BOLD) if active else " "
            label = color(item["label"], Ansi.GREEN + Ansi.BOLD) if active else item["label"]
            hint = color(item.get("hint", ""), Ansi.DIM) if item.get("hint") else ""
            print("{0} {1} {2}".format(pointer, label, hint).rstrip())

        key = read_single_key()
        if key == "up":
            selected = (selected - 1) % len(items)
        elif key == "down":
            selected = (selected + 1) % len(items)
        elif key == "enter":
            return items[selected]["value"]
        elif key in ("esc", "quit"):
            raise DownloadCancelled("Cancelled by user.")


def format_worker_text(requested_workers, active_workers):
    if requested_workers is None or requested_workers == active_workers:
        return str(active_workers)
    return "{0} active ({1} requested)".format(active_workers, requested_workers)


def confirm_download_start(source_ref, filename, total, output_file, threads, use_proxy, selected_site_host="auto", resolved_site_host=None, source_label="File id"):
    if not can_read_single_key():
        print("Ready to download:")
        print("  {0}: {1}".format(source_label, source_ref))
        print("  Name: {0}".format(filename))
        print("  Size: {0}".format(fmt_bytes(total)))
        print("  Output: {0}".format(output_file))
        print("  Threads: {0}".format(threads))
        print("  Host: {0}".format(describe_site_host(selected_site_host, resolved_site_host)))
        print("  Proxy: {0}".format("on" if use_proxy else "off"))
        raw = safe_input("Start download? [Y/n]: ", default="y").lower()
        return raw not in ("n", "no")

    while True:
        clear_screen()
        print_banner()
        print(color("Download Preview", Ansi.WHITE + Ansi.BOLD))
        print("")
        print("  {0} {1}".format(color(source_label + ":", Ansi.YELLOW), source_ref))
        print("  {0} {1}".format(color("Name:", Ansi.YELLOW), filename))
        print("  {0} {1}".format(color("Size:", Ansi.YELLOW), fmt_bytes(total)))
        print("  {0} {1}".format(color("Output:", Ansi.YELLOW), color_path(output_file)))
        print("  {0} {1}".format(color("Threads:", Ansi.YELLOW), threads))
        print("  {0} {1}".format(color("Host:", Ansi.YELLOW), describe_site_host(selected_site_host, resolved_site_host)))
        print("  {0} {1}".format(color("Proxy:", Ansi.YELLOW), color_bool(use_proxy)))
        print("")
        print(color("[Enter] Start download", Ansi.GREEN + Ansi.BOLD))
        print(color("[Esc/Q] Cancel and return", Ansi.RED + Ansi.BOLD))
        key = read_single_key()
        if key == "enter":
            return True
        if key in ("esc", "quit"):
            return False


def describe_location(value):
    if not value:
        return "Auto"
    text = str(value)
    label = LOCATION_LABELS.get(text.lower()) or LOCATION_ID_LABELS.get(text)
    if label:
        return label
    return text


def choose_upload_location(default_value=DEFAULT_UPLOAD_LOCATION):
    if not can_read_single_key():
        return prompt_text("Location", default_value)
    selected = choose_menu_option("Upload Location", LOCATION_MENU_ITEMS, selected_value=default_value)
    if selected != "__custom__":
        return selected

    clear_screen()
    print_banner()
    print(color("Custom Location", Ansi.WHITE + Ansi.BOLD))
    print("")
    return prompt_text("Location id or alias")


def choose_site_host(default_value="auto"):
    if not can_read_single_key():
        return prompt_text("Service host", default_value)
    return choose_menu_option("Service Host", SITE_HOST_MENU_ITEMS, selected_value=default_value)


def choose_upload_part_size(default_value=None):
    if not can_read_single_key():
        raw = prompt_text("Part size (50MiB, 100MiB, custom, auto)", default_value or "50MiB", allow_empty=True)
        raw = unwrap_drag_drop_value(raw)
        if not raw or raw.lower() in ("auto", "a", "default"):
            return None
        return raw

    selected = choose_menu_option("Upload Part Size", UPLOAD_PART_SIZE_MENU_ITEMS, selected_value=default_value or "50MiB")
    if selected == "__auto__":
        return None
    if selected != "__custom__":
        return selected

    clear_screen()
    print_banner()
    print(color("Custom Part Size", Ansi.WHITE + Ansi.BOLD))
    print("")
    value = prompt_text("Part size, e.g. 25MiB or 75MiB")
    return unwrap_drag_drop_value(value)


def upload_target_text(login_id, parent_id):
    if not login_id:
        return "Anonymous upload"
    if parent_id:
        return "Folder {0}".format(parent_id)
    return "Account root"


def confirm_upload_start(path, file_size, login_id, parent_id, location_id, note, use_proxy, remote_name, requested_workers, active_workers, part_size, selected_site_host="auto", resolved_site_host=None):
    mode_text = "Authenticated" if login_id else "Anonymous"
    target_text = upload_target_text(login_id, parent_id)
    location_text = describe_location(location_id)
    note_text = note or "-"
    part_text = fmt_bytes(part_size) if part_size else "Auto"
    worker_text = format_worker_text(requested_workers, active_workers)
    if not can_read_single_key():
        print("Ready to upload:")
        print("  Name: {0}".format(remote_name))
        print("  Size: {0}".format(fmt_bytes(file_size)))
        print("  Source: {0}".format(path))
        print("  Mode: {0}".format(mode_text))
        print("  Target: {0}".format(target_text))
        print("  Location: {0}".format(location_text))
        print("  Workers: {0}".format(worker_text))
        print("  Part size: {0}".format(part_text))
        print("  Host: {0}".format(describe_site_host(selected_site_host, resolved_site_host)))
        print("  Note: {0}".format(note_text))
        print("  Proxy: {0}".format("on" if use_proxy else "off"))
        raw = safe_input("Start upload? [Y/n]: ", default="y").lower()
        return raw not in ("n", "no")

    while True:
        clear_screen()
        print_banner()
        print(color("Upload Preview", Ansi.WHITE + Ansi.BOLD))
        print("")
        print("  {0} {1}".format(color("Name:", Ansi.YELLOW), remote_name))
        print("  {0} {1}".format(color("Size:", Ansi.YELLOW), fmt_bytes(file_size)))
        print("  {0} {1}".format(color("Source:", Ansi.YELLOW), color_path(path)))
        print("  {0} {1}".format(color("Mode:", Ansi.YELLOW), mode_text))
        print("  {0} {1}".format(color("Target:", Ansi.YELLOW), target_text))
        print("  {0} {1}".format(color("Location:", Ansi.YELLOW), location_text))
        print("  {0} {1}".format(color("Workers:", Ansi.YELLOW), worker_text))
        print("  {0} {1}".format(color("Part size:", Ansi.YELLOW), part_text))
        print("  {0} {1}".format(color("Host:", Ansi.YELLOW), describe_site_host(selected_site_host, resolved_site_host)))
        print("  {0} {1}".format(color("Note:", Ansi.YELLOW), note_text))
        print("  {0} {1}".format(color("Proxy:", Ansi.YELLOW), color_bool(use_proxy)))
        print("")
        print(color("[Enter] Start upload", Ansi.GREEN + Ansi.BOLD))
        print(color("[Esc/Q] Cancel and return", Ansi.RED + Ansi.BOLD))
        key = read_single_key()
        if key == "enter":
            return True
        if key in ("esc", "quit"):
            return False


def get_proxy_url():
    for key in (
        "HTTPS_PROXY",
        "https_proxy",
        "HTTP_PROXY",
        "http_proxy",
    ):
        value = os.environ.get(key)
        if value:
            return value
    if os.name == "nt" and winreg is not None:
        proxy_url = get_windows_proxy_url()
        if proxy_url:
            return proxy_url
    return None


def get_windows_proxy_url():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
        if not proxy_enable:
            return None
        proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
        if not proxy_server:
            return None
        proxy_server = proxy_server.strip()
        if "=" in proxy_server:
            mapping = {}
            for part in proxy_server.split(";"):
                if "=" not in part:
                    continue
                name, value = part.split("=", 1)
                mapping[name.strip().lower()] = value.strip()
            proxy_server = mapping.get("https") or mapping.get("http") or proxy_server
        if "://" not in proxy_server:
            proxy_server = "http://" + proxy_server
        return proxy_server
    except Exception:
        return None


def make_proxy_tunnel_headers(proxy_parts):
    headers = {}
    if proxy_parts.username is not None:
        auth = "{0}:{1}".format(proxy_parts.username, proxy_parts.password or "")
        token = base64.b64encode(auth.encode("utf-8")).decode("ascii")
        headers["Proxy-Authorization"] = "Basic {0}".format(token)
    return headers


def build_conn(host, use_proxy=False):
    context = ssl.create_default_context()
    if not use_proxy:
        return http.client.HTTPSConnection(host, context=context, timeout=NETWORK_IO_TIMEOUT)

    proxy_url = get_proxy_url()
    if not proxy_url:
        return http.client.HTTPSConnection(host, context=context, timeout=NETWORK_IO_TIMEOUT)

    if "://" not in proxy_url:
        proxy_url = "http://" + proxy_url
    proxy_parts = urlsplit(proxy_url)
    proxy_host = proxy_parts.hostname
    proxy_port = proxy_parts.port or (443 if proxy_parts.scheme == "https" else 80)

    if proxy_parts.scheme == "https":
        conn = http.client.HTTPSConnection(proxy_host, proxy_port, context=context, timeout=NETWORK_IO_TIMEOUT)
    else:
        conn = http.client.HTTPConnection(proxy_host, proxy_port, timeout=NETWORK_IO_TIMEOUT)

    tunnel_headers = make_proxy_tunnel_headers(proxy_parts)
    conn.set_tunnel(host, 443, headers=tunnel_headers or None)
    return conn


def fmt_bytes(value):
    if value is None:
        return "--"
    value = float(value)
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024.0
        idx += 1
    if idx == 0:
        return "{0:.0f} {1}".format(value, units[idx])
    return "{0:.2f} {1}".format(value, units[idx])


def fmt_speed(bytes_per_sec):
    return "{0}/s".format(fmt_bytes(bytes_per_sec))


def fmt_transfer(done, total):
    if done is None:
        return "-- / --"
    if total is None:
        return fmt_bytes(done)
    if float(total) < (1024.0 ** 3):
        return "{0} / {1}".format(fmt_bytes(done), fmt_bytes(total))
    gib = 1024.0 ** 3
    return "{0:.2f} / {1:.2f} GiB".format(float(done) / gib, float(total) / gib)


def fmt_seconds(value):
    if value is None:
        return "--:--"
    value = int(max(0, value))
    hours, rem = divmod(value, 3600)
    mins, secs = divmod(rem, 60)
    if hours:
        return "{0:02d}:{1:02d}:{2:02d}".format(hours, mins, secs)
    return "{0:02d}:{1:02d}".format(mins, secs)


def parse_size_bytes(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([kmgt]?i?b?)?$", text)
    if not match:
        raise ValueError("Invalid size value: {0}".format(value))
    number = float(match.group(1))
    suffix = (match.group(2) or "").lower()
    multipliers = {
        "": 1,
        "b": 1,
        "k": 1024,
        "kb": 1024,
        "kib": 1024,
        "m": 1024 ** 2,
        "mb": 1024 ** 2,
        "mib": 1024 ** 2,
        "g": 1024 ** 3,
        "gb": 1024 ** 3,
        "gib": 1024 ** 3,
        "t": 1024 ** 4,
        "tb": 1024 ** 4,
        "tib": 1024 ** 4,
    }
    if suffix not in multipliers:
        raise ValueError("Invalid size suffix: {0}".format(value))
    return int(number * multipliers[suffix])


def resolve_upload_part_size(file_size, requested_size=None, requested_workers=None):
    if file_size <= 0:
        raise RuntimeError("File must not be empty.")
    if file_size > UPLOAD_MAX_FILE_SIZE:
        raise RuntimeError("File exceeds upload limit: {0}".format(fmt_bytes(UPLOAD_MAX_FILE_SIZE)))

    if requested_size is None:
        worker_target = max(1, int(requested_workers or 1))
        size = (file_size + worker_target - 1) // worker_target
    else:
        size = parse_size_bytes(requested_size)

    size = max(UPLOAD_MIN_PART_SIZE, min(UPLOAD_MAX_PART_SIZE, size))
    total_parts = (file_size + size - 1) // size
    if total_parts > UPLOAD_MAX_PARTS:
        min_size = (file_size + UPLOAD_MAX_PARTS - 1) // UPLOAD_MAX_PARTS
        min_size = max(UPLOAD_MIN_PART_SIZE, min(UPLOAD_MAX_PART_SIZE, min_size))
        if requested_size is not None and size < min_size:
            raise RuntimeError(
                "Part size is too small for this file. Need at least {0} to stay within {1} parts.".format(
                    fmt_bytes(min_size), UPLOAD_MAX_PARTS
                )
            )
        size = min_size
        total_parts = (file_size + size - 1) // size
    return size, total_parts


def parse_url_or_id(value):
    value = value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlsplit(value)
        path = parsed.path.strip("/")
        if not path:
            raise ValueError("Could not extract file id from URL")
        return path.split("/")[0]
    return value


def parse_filename_from_headers(headers, fallback):
    disposition = headers.get("Content-Disposition") or headers.get("content-disposition")
    if disposition:
        match = re.search(r"filename\*=(?:UTF-8'')?\"?([^\";]+)\"?", disposition, re.IGNORECASE)
        if match:
            from urllib.parse import unquote
            return os.path.basename(unquote(match.group(1)))
        match = re.search(r"filename=\"?([^\";]+)\"?", disposition, re.IGNORECASE)
        if match:
            return os.path.basename(match.group(1))
    return fallback


def request_json(host, method, path, headers=None, body=None, use_proxy=False):
    ensure_requests_available()
    response = None
    try:
        response = requests.request(
            method,
            "https://{0}{1}".format(host, path),
            headers=headers or {},
            data=body,
            proxies=get_requests_proxies(use_proxy),
            timeout=(8, NETWORK_IO_TIMEOUT),
            allow_redirects=True,
            stream=False,
        )
        return response.status_code, response.reason, response.headers, response.content
    finally:
        if response is not None:
            response.close()


def parse_api_result(raw):
    data = json.loads(raw.decode("utf-8"))
    if isinstance(data, dict) and "error" in data and data.get("error") is not None:
        raise RuntimeError(data["error"])
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def auth_headers(login_id=None):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if login_id:
        headers["Authorization"] = "Bearer {0}".format(login_id)
    return headers


def encode_upload_note(note):
    if not note:
        return None
    if len(note) > 500:
        raise RuntimeError("Note too long, max 500 chars")
    return base64.b64encode(note.encode("utf-8")).decode("ascii")


def response_message(response):
    try:
        data = response.json()
        if isinstance(data, dict):
            payload = data.get("data")
            if isinstance(payload, dict) and payload.get("message"):
                return payload.get("message")
            if data.get("error"):
                return data.get("error")
            if data.get("message"):
                return data.get("message")
    except Exception:
        pass
    text = response.text or ""
    return text.strip()


def response_is_downloadable(response):
    content_type = (response.headers.get("Content-Type") or response.headers.get("content-type") or "").lower()
    disposition = response.headers.get("Content-Disposition") or response.headers.get("content-disposition") or ""
    if "attachment" in disposition.lower() or "filename" in disposition.lower():
        return True
    if response.status_code == 206:
        return True
    if content_type.startswith("text/html") or "application/xhtml" in content_type:
        return False
    return response.status_code == 200


def resolve_location(value):
    if not value:
        return None
    lower = value.lower()
    if lower in LOCATION_MAP:
        return LOCATION_MAP[lower]
    return value


def parse_proxy_mode(value):
    if value is None:
        return False
    value = value.strip().lower()
    return value in ("1", "true", "on", "yes", "y")


def normalize_site_host(value):
    if not value:
        return "auto"
    value = str(value).strip().lower()
    if value in ("auto", "default"):
        return "auto"
    if value not in SITE_HOSTS:
        raise ValueError("Unsupported site host: {0}".format(value))
    return value


def site_upload_host(site_host):
    return "w.{0}".format(site_host)


def describe_site_host(selected_site_host, resolved_site_host=None):
    selected = normalize_site_host(selected_site_host)
    if selected == "auto":
        if resolved_site_host:
            return "Auto -> {0}".format(resolved_site_host)
        return "Auto"
    return selected


def measure_site_host_latency(site_host, use_proxy=False, attempts=MIRROR_LATENCY_ATTEMPTS, announce=False):
    ensure_requests_available()
    samples = []
    errors = []
    for attempt in range(1, attempts + 1):
        response = None
        try:
            started = time.perf_counter()
            response = requests.get(
                "https://{0}{1}".format(site_host, MIRROR_LATENCY_PATH),
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                proxies=get_requests_proxies(use_proxy),
                timeout=(4, 6),
                allow_redirects=True,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if response.status_code >= 400:
                raise RuntimeError("HTTP {0} {1}".format(response.status_code, response.reason))
            data = json.loads(response.content.decode("utf-8"))
            if not isinstance(data, dict):
                raise RuntimeError("Invalid API response")
            samples.append(elapsed_ms)
        except Exception as exc:
            errors.append("{0}: {1}".format(type(exc).__name__, exc))
        finally:
            if response is not None:
                response.close()
    best_ms = min(samples) if samples else None
    result = {
        "host": site_host,
        "samples": samples,
        "best_ms": best_ms,
        "ok": bool(samples),
        "error": errors[-1] if errors else None,
    }
    if announce:
        sample_text = ", ".join("{0:.0f}".format(v) for v in samples) if samples else "failed"
        finish_line(
            "Mirror {0}: best {1} [{2}]".format(site_host, color_latency(best_ms), sample_text),
            None,
        )
    return result


def probe_site_host(site_host, use_proxy=False):
    return measure_site_host_latency(site_host, use_proxy=use_proxy, attempts=1).get("ok", False)


def resolve_site_host(selected_site_host="auto", use_proxy=False):
    selected = normalize_site_host(selected_site_host)
    if selected != "auto":
        return selected
    finish_line("Measuring mirror latency ({0} tries each)...".format(MIRROR_LATENCY_ATTEMPTS), Ansi.CYAN if supports_color() else None)
    results = [
        measure_site_host_latency(site_host, use_proxy=use_proxy, attempts=MIRROR_LATENCY_ATTEMPTS, announce=True)
        for site_host in SITE_HOSTS
    ]
    successful = [item for item in results if item["ok"]]
    if successful:
        selected_result = min(successful, key=lambda item: item["best_ms"])
        finish_line(
            "Selected mirror: {0} ({1})".format(selected_result["host"], color_latency(selected_result["best_ms"])),
            Ansi.GREEN + Ansi.BOLD if supports_color() else None,
        )
        return selected_result["host"]
    finish_line("All mirror probes failed, falling back to {0}.".format(OFFICIAL_SITE_HOST), Ansi.YELLOW if supports_color() else None)
    return OFFICIAL_SITE_HOST


def clipboard_copy(text):
    try:
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "Set-Clipboard -Value @'\n{0}\n'@".format(text),
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return result.returncode == 0
    except Exception:
        return False


def make_temp_remote_name(name):
    suffix = ".uploading"
    max_len = 500 - len(suffix)
    if len(name) > max_len:
        name = name[:max_len]
    return name + suffix


def get_console_width(default=120):
    try:
        return max(60, shutil.get_terminal_size(fallback=(default, 25)).columns)
    except Exception:
        return default


def print_status(kind, percent, speed, eta, elapsed, extra="", done=None, total=None, width=30):
    console_width = get_console_width()
    spinner_raw = SPINNER_FRAMES[int(time.time() * 10) % len(SPINNER_FRAMES)]
    kind_raw = str(kind).upper()
    pct_raw = "{0:3d}%".format(int(percent))
    transfer_raw = fmt_transfer(done, total)
    speed_raw = fmt_speed(speed)
    eta_raw = "ETA {0}".format(fmt_seconds(eta))
    elapsed_raw = "elapsed {0}".format(fmt_seconds(elapsed))
    extra_raw = extra or ""
    bar_inner = 40

    def visible_len(bar_width_value, extra_value):
        filled_value = int(round(bar_width_value * percent / 100.0))
        filled_value = max(0, min(bar_width_value, filled_value))
        bar_value = "[" + ("#" * filled_value) + ("-" * (bar_width_value - filled_value)) + "]"
        raw_parts = [spinner_raw, kind_raw, pct_raw, bar_value, transfer_raw, speed_raw, eta_raw, elapsed_raw]
        if extra_value:
            raw_parts.append(extra_value)
        return len(" ".join(raw_parts))

    while visible_len(bar_inner, extra_raw) > console_width and len(extra_raw) > 10:
        extra_raw = shorten_text(extra_raw, len(extra_raw) - 1)
    while visible_len(bar_inner, extra_raw) > console_width and bar_inner > 18:
        bar_inner -= 1
    while visible_len(bar_inner, extra_raw) > console_width and len(extra_raw) > 0:
        extra_raw = shorten_text(extra_raw, max(0, len(extra_raw) - 1))

    filled = int(round(bar_inner * percent / 100.0))
    filled = max(0, min(bar_inner, filled))
    bar = "[" + ("#" * filled) + ("-" * (bar_inner - filled)) + "]"
    kind_value = str(kind).lower()
    if kind_value == "connect":
        kind_code = Ansi.YELLOW + Ansi.BOLD
    elif kind_value == "finalizing":
        kind_code = Ansi.CYAN + Ansi.BOLD
    else:
        kind_code = Ansi.WHITE + Ansi.BOLD
    kind_text = color(kind_raw, kind_code)
    pct_text = color(pct_raw, Ansi.YELLOW + Ansi.BOLD)
    bar_text = color(bar, Ansi.GREEN)
    speed_text = color(speed_raw, Ansi.MAGENTA + Ansi.BOLD)
    transfer_text = color(transfer_raw, Ansi.CYAN + Ansi.BOLD)
    eta_text = color(eta_raw, Ansi.BLUE)
    elapsed_text = color(elapsed_raw, Ansi.DIM)
    spinner_text = color(spinner_raw, Ansi.CYAN + Ansi.BOLD)
    parts = [spinner_text, kind_text, pct_text, bar_text, transfer_text, speed_text, eta_text, elapsed_text]
    if extra_raw:
        parts.append(color(extra_raw, Ansi.WHITE))
    sys.stdout.write(clear_line() + " ".join(parts))
    sys.stdout.flush()


def print_progress_header(filename, output_file, threads, use_proxy, resolved_site_host=None):
    finish_line("File: {0}".format(filename), Ansi.CYAN + Ansi.BOLD if supports_color() else None)
    finish_line(
        "Target: {0} | Threads: {1} | Host: {2} | Proxy: {3}".format(
            output_file,
            threads,
            resolved_site_host or OFFICIAL_SITE_HOST,
            "on" if use_proxy else "off",
        ),
        Ansi.DIM if supports_color() else None,
    )


def print_upload_header(path, file_size, login_id, parent_id, location_id, use_proxy, remote_name, requested_workers, active_workers, part_size, resolved_site_host=None):
    finish_line("File: {0}".format(remote_name), Ansi.CYAN + Ansi.BOLD if supports_color() else None)
    finish_line("Source: {0}".format(path), Ansi.DIM if supports_color() else None)
    finish_line(
        "Target: {0} | Location: {1} | Workers: {2} | Host: {3} | Proxy: {4}".format(
            upload_target_text(login_id, parent_id),
            describe_location(location_id),
            format_worker_text(requested_workers, active_workers),
            resolved_site_host or OFFICIAL_SITE_HOST,
            "on" if use_proxy else "off",
        ),
        Ansi.DIM if supports_color() else None,
    )
    finish_line(
        "Size: {0} | Part size: {1}".format(fmt_bytes(file_size), fmt_bytes(part_size)),
        Ansi.DIM if supports_color() else None,
    )


def finish_line(message, code=None):
    sys.stdout.write(clear_line())
    if code and supports_color():
        sys.stdout.write(code + message + Ansi.RESET + "\n")
    else:
        sys.stdout.write(message + "\n")
    sys.stdout.flush()


def fetch_download_token(file_id, use_proxy=False, site_host=OFFICIAL_SITE_HOST):
    ensure_requests_available()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "identity",
    }
    for mode, label in choose_host_connection_attempts(site_host, use_proxy):
        try:
            response = requests.get(
                "https://{0}/{1}".format(site_host, file_id),
                headers=headers,
                proxies=get_requests_proxies(mode),
                timeout=(8, NETWORK_IO_TIMEOUT),
            )
            if response.status_code == 200:
                html = response.text
                match = re.search(r'download\?t=([^"\'&\\#]+)', html)
                if match:
                    return match.group(1)
        except Exception:
            pass
    return None


def request_download_redirect(file_id, use_alt, token=None, use_proxy=False, site_host=OFFICIAL_SITE_HOST):
    ensure_requests_available()
    suffix = "/{0}/download".format(quote(file_id))
    params = []
    if token:
        params.append("t={0}".format(token))
    if use_alt:
        params.append("alt=true")
    if params:
        suffix += "?" + "&".join(params)
    headers = {
        "User-Agent": USER_AGENT,
        "hx-current-url": "https://{0}/{1}".format(site_host, file_id),
        "hx-request": "true",
        "referer": "https://{0}/{1}".format(site_host, file_id),
        "Accept-Encoding": "identity",
    }
    response = requests.get(
        "https://{0}{1}".format(site_host, suffix),
        headers=headers,
        proxies=get_requests_proxies(use_proxy),
        timeout=(8, NETWORK_IO_TIMEOUT),
        allow_redirects=False,
        stream=False,
    )
    try:
        return response.status_code, response.reason, response.headers
    finally:
        response.close()


def choose_proxy_modes(preferred_use_proxy):
    if preferred_use_proxy:
        return [True, False]
    return [False, True]


def choose_connection_attempts(preferred_use_proxy):
    for mode in choose_proxy_modes(preferred_use_proxy):
        yield mode, ("proxy" if mode else "direct")


def choose_host_connection_attempts(host, preferred_use_proxy):
    for mode, label in choose_connection_attempts(preferred_use_proxy):
        yield mode, label


def get_requests_proxies(use_proxy=False):
    if not use_proxy:
        return None
    proxy_url = get_proxy_url()
    if not proxy_url:
        return None
    return {
        "http": proxy_url,
        "https": proxy_url,
    }


def ensure_requests_available():
    if requests is None:
        raise RuntimeError("The requests package is required for transfers. Install it with: python -m pip install -r requirements.txt")


def resolve_download_target(file_id, use_proxy=False, site_host=OFFICIAL_SITE_HOST):
    token = fetch_download_token(file_id, use_proxy=use_proxy, site_host=site_host)
    if token:
        finish_line(
            "Found download token: {0}".format(token),
            Ansi.GREEN if supports_color() else None,
        )
    last_error = None
    for attempt in range(1, 6):
        for mode in choose_proxy_modes(use_proxy):
            try:
                label = "proxy" if mode else "direct"
                finish_line(
                    "Resolving file id: {0} [{1} alt try {2}]".format(file_id, label, attempt),
                    Ansi.CYAN if supports_color() else None,
                )
                status, reason, headers = request_download_redirect(file_id, True, token=token, use_proxy=mode, site_host=site_host)
                redirect = headers.get("Hx-Redirect") or headers.get("Location")
                if status not in (200, 204, 301, 302, 303, 307, 308) or not redirect:
                    last_error = "Unexpected redirect response via {0}: HTTP {1} {2}".format(label, status, reason)
                    continue

                parts = urlsplit(redirect)
                if not parts.scheme or not parts.netloc:
                    last_error = "Invalid redirect URL via {0}: {1}".format(label, redirect)
                    continue

                if parts.netloc == "fafda.to":
                    last_error = "Advertisement redirect via {0}".format(label)
                    continue

                return redirect
            except Exception as exc:
                last_error = "{0} via {1}: {2}".format(type(exc).__name__, "proxy" if mode else "direct", exc)
        time.sleep(0.35 * attempt)

    for attempt in range(1, 3):
        for mode in choose_proxy_modes(use_proxy):
            try:
                label = "proxy" if mode else "direct"
                finish_line(
                    "Fallback resolving file id: {0} [{1} std try {2}]".format(file_id, label, attempt),
                    Ansi.YELLOW if supports_color() else None,
                )
                status, reason, headers = request_download_redirect(file_id, False, token=token, use_proxy=mode, site_host=site_host)
                redirect = headers.get("Hx-Redirect") or headers.get("Location")
                if status not in (200, 204, 301, 302, 303, 307, 308) or not redirect:
                    last_error = "Unexpected standard response via {0}: HTTP {1} {2}".format(label, status, reason)
                    continue

                parts = urlsplit(redirect)
                if not parts.scheme or not parts.netloc:
                    last_error = "Invalid standard redirect via {0}: {1}".format(label, redirect)
                    continue

                return redirect
            except Exception as exc:
                last_error = "{0} via {1}: {2}".format(type(exc).__name__, "proxy" if mode else "direct", exc)
        time.sleep(0.5 * attempt)

    raise RuntimeError("Could not resolve downloadable URL for {0}. Last error: {1}".format(file_id, last_error))


def direct_url_metadata(redirect, use_proxy=False):
    ensure_requests_available()
    redirect_parts = urlsplit(redirect)
    last_error = None
    for mode, label in choose_host_connection_attempts(redirect_parts.netloc, use_proxy):
        for method in ("HEAD", "GET"):
            response = None
            try:
                headers = {"User-Agent": USER_AGENT}
                if method == "GET":
                    headers["Range"] = "bytes=0-0"
                response = requests.request(
                    method,
                    redirect,
                    headers=headers,
                    proxies=get_requests_proxies(mode),
                    timeout=(8, NETWORK_IO_TIMEOUT),
                    allow_redirects=True,
                    stream=(method == "GET"),
                )
                if response.status_code not in (200, 206):
                    last_error = "Unexpected metadata response via {0}: HTTP {1} {2}".format(label, response.status_code, response.reason)
                    continue

                total = response.headers.get("Content-Length")
                if response.status_code == 206:
                    content_range = response.headers.get("Content-Range")
                    if content_range and "/" in content_range:
                        total = content_range.rsplit("/", 1)[-1]
                total = int(total) if total and str(total).isdigit() else None
                fallback_name = os.path.basename(redirect_parts.path.rstrip("/")) or "download"
                filename = parse_filename_from_headers(response.headers, fallback_name)
                return redirect_parts, filename, total
            except Exception as exc:
                last_error = "{0} via {1}: {2}".format(type(exc).__name__, label, exc)
            finally:
                try:
                    response.close()
                except Exception:
                    pass

    raise RuntimeError("Could not determine metadata for downloadable URL: {0}. Last error: {1}".format(redirect, last_error))


def resolve_direct_download_url(url, use_proxy=False):
    ensure_requests_available()
    redirect_parts = urlsplit(url)
    if not redirect_parts.scheme or not redirect_parts.netloc:
        raise RuntimeError("Invalid direct URL: {0}".format(url))
    last_error = None
    for mode, label in choose_host_connection_attempts(redirect_parts.netloc, use_proxy):
        response = None
        try:
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"},
                proxies=get_requests_proxies(mode),
                timeout=(8, NETWORK_IO_TIMEOUT),
                allow_redirects=True,
                stream=True,
            )
            if response.status_code not in (200, 206):
                last_error = "HTTP {0} {1} via {2}".format(response.status_code, response.reason, label)
                continue
            if response_is_downloadable(response):
                return response.url
            last_error = "URL returned a page, not a file, via {0}".format(label)
        except Exception as exc:
            last_error = "{0} via {1}: {2}".format(type(exc).__name__, label, exc)
        finally:
            if response is not None:
                response.close()
    raise RuntimeError("Direct URL is not downloadable: {0}. Last error: {1}".format(url, last_error))


def probe_range_support(redirect_parts, use_proxy=False):
    ensure_requests_available()
    last_error = None
    for mode, label in choose_host_connection_attempts(redirect_parts.netloc, use_proxy):
        response = None
        try:
            headers = {
                "User-Agent": USER_AGENT,
                "Range": "bytes=0-0",
            }
            response = requests.get(
                redirect_parts.geturl(),
                headers=headers,
                proxies=get_requests_proxies(mode),
                timeout=(8, NETWORK_IO_TIMEOUT),
                allow_redirects=True,
                stream=False,
            )
            return response.status_code == 206
        except Exception as exc:
            last_error = "{0} via {1}: {2}".format(type(exc).__name__, label, exc)
        finally:
            if response is not None:
                response.close()
    if last_error:
        finish_line("Range probe fallback used after error: {0}".format(last_error), Ansi.YELLOW if supports_color() else None)
    return False


def fetch_remote_range(redirect_parts, start_byte, end_byte, use_proxy=False):
    ensure_requests_available()
    last_error = None
    for mode, label in choose_host_connection_attempts(redirect_parts.netloc, use_proxy):
        response = None
        try:
            headers = {
                "User-Agent": USER_AGENT,
                "Range": "bytes={0}-{1}".format(start_byte, end_byte),
            }
            response = requests.get(
                redirect_parts.geturl(),
                headers=headers,
                proxies=get_requests_proxies(mode),
                timeout=(8, NETWORK_IO_TIMEOUT),
                allow_redirects=True,
                stream=False,
            )
            data = response.content
            if response.status_code != 206:
                raise RuntimeError("Validation range request failed: HTTP {0} {1}".format(response.status_code, response.reason))
            return data
        except Exception as exc:
            last_error = "{0} via {1}: {2}".format(type(exc).__name__, label, exc)
        finally:
            if response is not None:
                response.close()
    raise RuntimeError("Validation range request failed for {0}-{1}. Last error: {2}".format(start_byte, end_byte, last_error))


def validate_existing_file(output_file, redirect_parts, total, use_proxy=False):
    if total is None or not os.path.exists(output_file):
        return False

    current_size = os.path.getsize(output_file)
    if current_size != total:
        return False

    sample = min(1024, total)
    ranges = [(0, sample - 1)]
    if total > sample:
        ranges.append((total - sample, total - 1))

    with open(output_file, "rb") as fp:
        for start_byte, end_byte in ranges:
            fp.seek(start_byte)
            local_chunk = fp.read((end_byte - start_byte) + 1)
            remote_chunk = fetch_remote_range(redirect_parts, start_byte, end_byte, use_proxy=use_proxy)
            if local_chunk != remote_chunk:
                return False
    return True


def prepare_download_targets(output_file, redirect_parts, total, use_proxy=False):
    temp_file = temp_download_path(output_file)
    final_exists = os.path.exists(output_file)
    temp_exists = os.path.exists(temp_file)

    if final_exists and total is not None and os.path.getsize(output_file) == total:
        finish_line(
            "Validating existing file: {0}".format(output_file),
            Ansi.CYAN if supports_color() else None,
        )
        if validate_existing_file(output_file, redirect_parts, total, use_proxy=use_proxy):
            finish_line("Already downloaded: {0}".format(output_file), Ansi.GREEN + Ansi.BOLD if supports_color() else None)
            finish_line("Bytes: {0}".format(fmt_bytes(total)), Ansi.CYAN if supports_color() else None)
            return output_file, None, True

        finish_line(
            "Existing file is incomplete or corrupted, restarting download.",
            Ansi.YELLOW if supports_color() else None,
        )
        safe_remove_file(output_file)
        final_exists = False

    if final_exists and not temp_exists:
        os.replace(output_file, temp_file)
        temp_exists = True

    if temp_exists and total is not None:
        temp_size = os.path.getsize(temp_file)
        if temp_size == total:
            finish_line(
                "Validating unfinished temp file: {0}".format(temp_file),
                Ansi.CYAN if supports_color() else None,
            )
            if validate_existing_file(temp_file, redirect_parts, total, use_proxy=use_proxy):
                os.replace(temp_file, output_file)
                finish_line("Recovered completed download: {0}".format(output_file), Ansi.GREEN + Ansi.BOLD if supports_color() else None)
                finish_line("Bytes: {0}".format(fmt_bytes(total)), Ansi.CYAN if supports_color() else None)
                return output_file, None, True
            safe_remove_file(temp_file)
        elif temp_size > total:
            safe_remove_file(temp_file)

    return output_file, temp_file, False


def read_stream_with_retries(
    redirect_parts,
    path,
    temp_file,
    start_byte,
    end_byte,
    total,
    threads,
    downloaded,
    lock,
    stop_event,
    status_state,
    use_proxy=False,
):
    ensure_requests_available()
    current_start = start_byte
    attempts = 0
    while not stop_event.is_set():
        last_error = None
        for mode, label in choose_host_connection_attempts(redirect_parts.netloc, use_proxy):
            response = None
            try:
                with lock:
                    status_state["phase"] = "connect"
                    if attempts:
                        status_state["note"] = "{0} r{1}/{2}".format(label, attempts, DOWNLOAD_RETRY_LIMIT)
                    else:
                        status_state["note"] = label
                req_headers = {"User-Agent": USER_AGENT}
                if total is not None:
                    if end_byte is not None:
                        req_headers["Range"] = "bytes={0}-{1}".format(current_start, end_byte)
                response = requests.get(
                    redirect_parts.geturl(),
                    headers=req_headers,
                    proxies=get_requests_proxies(mode),
                    timeout=(8, NETWORK_IO_TIMEOUT),
                    allow_redirects=True,
                    stream=True,
                )
                if threads > 1 and total is not None and response.status_code != 206:
                    raise RuntimeError("Range download failed: HTTP {0} {1}".format(response.status_code, response.reason))
                if threads == 1 and response.status_code not in (200, 206):
                    raise RuntimeError("Download failed: HTTP {0} {1}".format(response.status_code, response.reason))

                with open(temp_file, "r+b", buffering=0) as fp:
                    if total is not None:
                        fp.seek(current_start)
                    saw_data = False
                    for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        if stop_event.is_set():
                            return
                        if not chunk:
                            continue
                        if total is not None and end_byte is not None:
                            remaining = end_byte - current_start + 1
                            if remaining <= 0:
                                return
                            if len(chunk) > remaining:
                                chunk = chunk[:remaining]
                        with lock:
                            status_state["phase"] = "download"
                            status_state["note"] = label
                        saw_data = True
                        fp.write(chunk)
                        current_start += len(chunk)
                        with lock:
                            downloaded[0] += len(chunk)
                        if total is not None and end_byte is not None and current_start > end_byte:
                            return
                    if total is not None and end_byte is not None and current_start <= end_byte:
                        raise RuntimeError("Connection closed before range finished.")
                    if not saw_data and current_start == start_byte:
                        raise RuntimeError("No bytes received from server.")
                return
            except Exception as exc:
                last_error = exc
                if not is_retryable_download_error(exc):
                    raise
            finally:
                if response is not None:
                    response.close()

        attempts += 1
        if attempts > DOWNLOAD_RETRY_LIMIT or stop_event.is_set():
            raise last_error
        with lock:
            status_state["phase"] = "connect"
            status_state["note"] = "r{0}/{1} {2}".format(
                attempts, DOWNLOAD_RETRY_LIMIT, fmt_bytes(current_start)
            )
        time.sleep(min(5, attempts))


def download_with_ranges(redirect_parts, filename, total, output_file, threads, use_proxy=False, resolved_site_host=None):
    if not output_file:
        output_file = filename
    if not os.path.isabs(output_file):
        output_file = os.path.join(DEFAULT_DOWNLOAD_DIR, output_file)

    out_dir = os.path.dirname(output_file)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    output_file, temp_file, already_done = prepare_download_targets(output_file, redirect_parts, total, use_proxy=use_proxy)
    if already_done:
        return output_file
    if temp_file is None:
        raise RuntimeError("Temporary download path was not prepared.")

    if os.path.exists(temp_file):
        current_size = os.path.getsize(temp_file)
    else:
        current_size = 0

    if total is not None and current_size > total:
        safe_remove_file(temp_file)
        current_size = 0

    with open(temp_file, "ab" if current_size else "wb") as fp:
        pass

    path = redirect_parts.path or "/"
    if redirect_parts.query:
        path += "?" + redirect_parts.query

    total = int(total) if total is not None else None
    threads = max(1, int(threads))
    if total is None or threads == 1:
        threads = 1
    elif not probe_range_support(redirect_parts, use_proxy=use_proxy):
        threads = 1
    elif current_size > 0:
        threads = 1

    use_hotkeys = can_read_single_key()
    thread_plan = []
    if threads >= 10:
        thread_plan = [threads, 6, 1]
    elif threads > 1:
        thread_plan = [threads, 1]
    else:
        thread_plan = [1]
    plan_index = 0
    threads = thread_plan[plan_index]
    print_progress_header(filename, output_file, threads, use_proxy, resolved_site_host=resolved_site_host)

    while True:
        start_time = time.time()
        downloaded = [current_size]
        errors = []
        lock = threading.Lock()
        stop_event = threading.Event()
        cancel_event = threading.Event()
        status_state = {"phase": "connect", "note": ""}

        def monitor():
            while not stop_event.is_set():
                with lock:
                    done = downloaded[0]
                    phase = status_state["phase"]
                    note = status_state["note"]
                elapsed = time.time() - start_time
                speed = (done - current_size) / elapsed if elapsed > 0 else 0
                percent = int(done * 100 / total) if total else 0
                eta = int((total - done) / speed) if total and speed > 0 else None
                kind = "connect" if phase == "connect" else "download"
                extra_parts = []
                if note:
                    extra_parts.append("[{0}]".format(note))
                if use_hotkeys:
                    extra_parts.append("[Q]")
                print_status(kind, percent, speed, eta, elapsed, " ".join(extra_parts), done=done, total=total)
                no_progress_timeout = FIRST_BYTE_TIMEOUT_MULTI if threads > 1 else FIRST_BYTE_TIMEOUT_SINGLE
                if done == current_size and elapsed >= no_progress_timeout:
                    with lock:
                        errors.append(RuntimeError("No data received for {0} seconds.".format(no_progress_timeout)))
                    stop_event.set()
                    return
                if use_hotkeys:
                    try:
                        import msvcrt
                        if msvcrt.kbhit():
                            key = read_single_key()
                            if key in ("quit", "esc"):
                                cancel_event.set()
                                stop_event.set()
                                return
                    except Exception:
                        pass
                time.sleep(0.1)

        def worker(start_byte, end_byte):
            try:
                read_stream_with_retries(
                    redirect_parts,
                    path,
                    temp_file,
                    start_byte,
                    end_byte,
                    total,
                    threads,
                    downloaded,
                    lock,
                    stop_event,
                    status_state,
                    use_proxy=use_proxy,
                )
            except Exception as exc:
                with lock:
                    errors.append(exc)
                stop_event.set()

        monitor_thread = threading.Thread(target=monitor)
        monitor_thread.daemon = True
        monitor_thread.start()

        if threads == 1:
            if total is not None:
                start_byte = current_size
                if start_byte >= total:
                    stop_event.set()
                else:
                    worker(start_byte, total - 1)
            else:
                worker(current_size, 0)
        else:
            ranges = []
            chunk = max(1, total // threads)
            start = 0
            for index in range(threads):
                end = total - 1 if index == threads - 1 else start + chunk - 1
                ranges.append((start, end))
                start = end + 1

            workers = []
            for start_byte, end_byte in ranges:
                t = threading.Thread(target=worker, args=(start_byte, end_byte))
                t.daemon = True
                workers.append(t)
                t.start()

            for t in workers:
                t.join()

        stop_event.set()
        monitor_thread.join()

        if cancel_event.is_set():
            safe_remove_file(temp_file)
            finish_line("Download cancelled. Partial file removed.", Ansi.YELLOW + Ansi.BOLD if supports_color() else None)
            raise DownloadCancelled("Download cancelled by user.")

        if errors:
            current_size = os.path.getsize(temp_file) if os.path.exists(temp_file) else 0
            if threads > 1:
                with lock:
                    status_state["phase"] = "connect"
                    next_threads = thread_plan[plan_index + 1] if plan_index + 1 < len(thread_plan) else 1
                    status_state["note"] = "{0}t".format(next_threads)
                if plan_index + 1 < len(thread_plan):
                    next_threads = thread_plan[plan_index + 1]
                    finish_line(
                        "No stable first byte yet. Falling back from {0} threads to {1}...".format(threads, next_threads),
                        Ansi.YELLOW if supports_color() else None,
                    )
                    plan_index += 1
                    threads = thread_plan[plan_index]
                    continue
            safe_remove_file(temp_file)
            raise errors[0]
        break

    if total is not None and os.path.getsize(temp_file) < total:
        safe_remove_file(temp_file)
        raise RuntimeError("Download ended before file was fully written.")

    os.replace(temp_file, output_file)
    sys.stdout.write(clear_line())
    finish_line("Downloaded: {0}".format(output_file), Ansi.GREEN + Ansi.BOLD if supports_color() else None)
    finish_line("Bytes: {0}".format(fmt_bytes(total if total is not None else downloaded[0])), Ansi.CYAN if supports_color() else None)
    return output_file


def download_file(file_id_or_url, output_dir, output_path=None, threads=DEFAULT_DOWNLOAD_THREADS, use_proxy=False, site_host="auto"):
    file_id_or_url = unwrap_drag_drop_value(file_id_or_url)
    output_dir = unwrap_drag_drop_value(output_dir)
    output_path = unwrap_drag_drop_value(output_path)
    if not file_id_or_url:
        raise RuntimeError("File URL or id is required.")

    source_label = "File id"
    resolved_site_host = None
    if file_id_or_url.startswith("http://") or file_id_or_url.startswith("https://"):
        source_label = "URL"
        try:
            redirect = resolve_direct_download_url(file_id_or_url, use_proxy=use_proxy)
        except Exception as direct_exc:
            file_id = parse_url_or_id(file_id_or_url)
            resolved_site_host = resolve_site_host(site_host, use_proxy=use_proxy)
            finish_line(
                "Direct URL fallback failed: {0}".format(direct_exc),
                Ansi.YELLOW if supports_color() else None,
            )
            redirect = resolve_download_target(file_id, use_proxy=use_proxy, site_host=resolved_site_host)
            source_label = "File id"
            file_id_or_url = file_id
    else:
        file_id = parse_url_or_id(file_id_or_url)
        resolved_site_host = resolve_site_host(site_host, use_proxy=use_proxy)
        redirect = resolve_download_target(file_id, use_proxy=use_proxy, site_host=resolved_site_host)

    redirect_parts, filename, total = direct_url_metadata(redirect, use_proxy=use_proxy)
    progress_host = resolved_site_host or redirect_parts.netloc
    if output_path:
        final_path = output_path
    else:
        output_dir = output_dir or DEFAULT_DOWNLOAD_DIR
        final_path = os.path.join(output_dir, filename)
    if not confirm_download_start(file_id_or_url, filename, total, final_path, threads, use_proxy, selected_site_host=site_host, resolved_site_host=resolved_site_host, source_label=source_label):
        finish_line("Download cancelled before start.", Ansi.YELLOW + Ansi.BOLD if supports_color() else None)
        raise DownloadCancelled("Download cancelled before start.")
    return download_with_ranges(redirect_parts, filename, total, final_path, threads, use_proxy=use_proxy, resolved_site_host=progress_host)


def fetch_root_directory_id(login_id, use_proxy=False, site_host=OFFICIAL_SITE_HOST):
    headers = auth_headers(login_id)
    last_error = None
    for mode, label in choose_host_connection_attempts(site_host, use_proxy):
        try:
            status, reason, _headers, raw = request_json(site_host, "GET", "/api/fs", headers=headers, use_proxy=mode)
            if status >= 400:
                last_error = "HTTP {0} {1} via {2}".format(status, reason, label)
                continue
            data = parse_api_result(raw)
            return data["id"]
        except Exception as exc:
            last_error = "{0} via {1}: {2}".format(type(exc).__name__, label, exc)
    raise RuntimeError("Failed to fetch root directory. Last error: {0}".format(last_error))


def rename_remote_item(login_id, item_id, new_name, use_proxy=False, site_host=OFFICIAL_SITE_HOST):
    body = json.dumps({"name": new_name}).encode("utf-8")
    headers = auth_headers(login_id)
    headers["Content-Type"] = "application/json"
    last_error = None
    for mode, label in choose_host_connection_attempts(site_host, use_proxy):
        try:
            status, reason, _headers, raw = request_json(
                site_host,
                "PATCH",
                "/api/fs/{0}".format(quote(item_id)),
                headers=headers,
                body=body,
                use_proxy=mode,
            )
            if status >= 400:
                last_error = "HTTP {0} {1} via {2}\n{3}".format(status, reason, label, raw.decode("utf-8", "ignore"))
                continue
            return parse_api_result(raw)
        except Exception as exc:
            last_error = "{0} via {1}: {2}".format(type(exc).__name__, label, exc)
    raise RuntimeError("Rename failed: {0}".format(last_error))


class UploadProgressReader(object):
    def __init__(self, path, lock, state, cancel_event, mode_label):
        self._path = path
        self._lock = lock
        self._state = state
        self._cancel_event = cancel_event
        self._mode_label = mode_label
        self._size = os.path.getsize(path)
        self._fp = open(path, "rb")

    def __len__(self):
        return self._size

    def tell(self):
        return self._fp.tell()

    def close(self):
        try:
            self._fp.close()
        except Exception:
            pass

    def read(self, size=-1):
        if self._cancel_event.is_set():
            raise DownloadCancelled("Upload cancelled by user.")
        if size is None or size <= 0 or size > UPLOAD_CHUNK_SIZE:
            size = UPLOAD_CHUNK_SIZE
        chunk = self._fp.read(size)
        if chunk:
            with self._lock:
                self._state["phase"] = "upload"
                self._state["note"] = self._mode_label
                self._state["sent"] += len(chunk)
        return chunk


class MultipartUploadPartReader(object):
    def __init__(self, path, start_offset, part_length, lock, state, part_index, cancel_event, note_label):
        self._fp = open(path, "rb")
        self._fp.seek(start_offset)
        self._part_length = part_length
        self._remaining = part_length
        self._lock = lock
        self._state = state
        self._part_index = part_index
        self._cancel_event = cancel_event
        self._note_label = note_label
        self._closed = False

    def close(self):
        self._closed = True
        try:
            self._fp.close()
        except Exception:
            pass

    def read(self, size=-1):
        if self._closed:
            return b""
        if self._cancel_event.is_set():
            raise DownloadCancelled("Upload cancelled by user.")
        if self._remaining <= 0:
            self._closed = True
            return b""
        if size is None or size <= 0 or size > UPLOAD_CHUNK_SIZE:
            size = UPLOAD_CHUNK_SIZE
        size = min(size, self._remaining)
        chunk = self._fp.read(size)
        if not chunk:
            self._closed = True
            return b""
        self._remaining -= len(chunk)
        with self._lock:
            if not self._closed:
                self._state["phase"] = "upload"
                self._state["note"] = self._note_label
                current = self._state["part_progress"][self._part_index]
                self._state["part_progress"][self._part_index] = min(self._part_length, current + len(chunk))
        return chunk


def delete_remote_item(login_id, item_id, use_proxy=False, site_host=OFFICIAL_SITE_HOST):
    headers = auth_headers(login_id)
    last_error = None
    for mode, label in choose_host_connection_attempts(site_host, use_proxy):
        try:
            status, reason, _headers, raw = request_json(
                site_host,
                "DELETE",
                "/api/fs/{0}".format(quote(item_id)),
                headers=headers,
                use_proxy=mode,
            )
            if status >= 400:
                last_error = "HTTP {0} {1} via {2}\n{3}".format(status, reason, label, raw.decode("utf-8", "ignore"))
                continue
            return parse_api_result(raw) if raw else None
        except Exception as exc:
            last_error = "{0} via {1}: {2}".format(type(exc).__name__, label, exc)
    raise RuntimeError("Delete failed: {0}".format(last_error))


def begin_multipart_upload(file_name, login_id=None, parent_id=None, location_id=None, note=None, use_proxy=False, site_host=OFFICIAL_SITE_HOST):
    ensure_requests_available()
    payload = {"name": file_name}
    if parent_id:
        payload["parentId"] = parent_id
    if location_id:
        payload["locationId"] = resolve_location(location_id)
    encoded_note = encode_upload_note(note)
    if encoded_note:
        payload["note"] = encoded_note

    headers = auth_headers(login_id)
    headers["Content-Type"] = "application/json"
    last_error = None
    for mode, label in choose_host_connection_attempts(site_host, use_proxy):
        response = None
        try:
            response = requests.post(
                "https://{0}{1}".format(site_host, UPLOAD_INIT_PATH),
                headers=headers,
                json=payload,
                proxies=get_requests_proxies(mode),
                timeout=(8, NETWORK_IO_TIMEOUT),
                allow_redirects=True,
            )
            if response.status_code >= 400:
                last_error = "HTTP {0} {1} via {2}: {3}".format(
                    response.status_code,
                    response.reason,
                    label,
                    response_message(response),
                )
                continue
            data = parse_api_result(response.content)
            if not isinstance(data, dict) or not data.get("id") or not data.get("location"):
                raise RuntimeError("Multipart init returned incomplete data.")
            return data
        except Exception as exc:
            last_error = "{0} via {1}: {2}".format(type(exc).__name__, label, exc)
        finally:
            if response is not None:
                response.close()
    raise RuntimeError("Failed to initialize multipart upload. Last error: {0}".format(last_error))


def complete_multipart_upload(upload_id, login_id=None, use_proxy=False, site_host=OFFICIAL_SITE_HOST):
    headers = auth_headers(login_id)
    last_error = None
    for mode, label in choose_host_connection_attempts(site_host, use_proxy):
        try:
            status, reason, _headers, raw = request_json(
                site_host,
                "POST",
                "{0}/{1}".format(UPLOAD_INIT_PATH, quote(upload_id)),
                headers=headers,
                use_proxy=mode,
            )
            if status >= 400:
                last_error = "HTTP {0} {1} via {2}\n{3}".format(status, reason, label, raw.decode("utf-8", "ignore"))
                continue
            return parse_api_result(raw)
        except Exception as exc:
            last_error = "{0} via {1}: {2}".format(type(exc).__name__, label, exc)
    raise RuntimeError("Failed to finalize multipart upload. Last error: {0}".format(last_error))


def upload_progress_total(state, file_size=None):
    completed = int(state.get("completed_bytes", 0))
    inflight = sum(state.get("part_progress", []))
    current = completed + inflight
    phase = state.get("phase", "")
    display = int(state.get("display_sent", 0))
    if file_size is not None:
        cap = file_size if phase in ("finalizing", "done") else max(0, file_size - 1)
        current = min(current, cap)
        display = min(max(display, current), cap)
    else:
        display = max(display, current)
    state["display_sent"] = display
    return display


def rollback_part_progress(state, lock, part_index):
    with lock:
        state["part_progress"][part_index] = 0


def upload_part_with_retries(
    upload_url,
    path,
    start_offset,
    part_length,
    part_number,
    total_parts,
    login_id,
    use_proxy,
    lock,
    state,
    stop_event,
    cancel_event,
):
    ensure_requests_available()
    upload_host = urlsplit(upload_url).netloc
    last_error = None
    part_index = part_number - 1
    for attempt in range(1, UPLOAD_RETRY_LIMIT + 1):
        if stop_event.is_set() or cancel_event.is_set():
            raise DownloadCancelled("Upload cancelled by user.")
        rollback_part_progress(state, lock, part_index)
        for mode, label in choose_host_connection_attempts(upload_host, use_proxy):
            response = None
            reader = None
            try:
                note_label = "{0} p{1}/{2}".format(label, part_number, total_parts)
                with lock:
                    state["phase"] = "connect"
                    state["note"] = note_label
                headers = {
                    "User-Agent": USER_AGENT,
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(part_length),
                    UPLOAD_PART_HEADER_LENGTH: str(part_length),
                    UPLOAD_PART_HEADER_NUMBER: str(part_number),
                }
                if login_id:
                    headers["Authorization"] = "Bearer {0}".format(login_id)
                reader = MultipartUploadPartReader(path, start_offset, part_length, lock, state, part_index, cancel_event, note_label)
                response = requests.patch(
                    upload_url,
                    headers=headers,
                    data=reader,
                    proxies=get_requests_proxies(mode),
                    timeout=(8, NETWORK_IO_TIMEOUT),
                    allow_redirects=False,
                )
                if cancel_event.is_set():
                    raise DownloadCancelled("Upload cancelled by user.")
                if response.status_code in (200, 201, 204):
                    with lock:
                        state["phase"] = "upload"
                        state["note"] = note_label
                        state["completed_bytes"] = int(state.get("completed_bytes", 0)) + part_length
                        state["part_progress"][part_index] = 0
                    return
                message = response_message(response)
                if response.status_code == 410:
                    raise RuntimeError("Upload session expired while sending part {0}.".format(part_number))
                if response.status_code == 413:
                    raise RuntimeError("Upload part {0} is too large for the server.".format(part_number))
                if 500 <= response.status_code < 600:
                    last_error = RuntimeError("Server error on part {0} via {1}: HTTP {2} {3} {4}".format(part_number, label, response.status_code, response.reason, message))
                    continue
                raise RuntimeError("Upload part {0} failed via {1}: HTTP {2} {3} {4}".format(part_number, label, response.status_code, response.reason, message))
            except DownloadCancelled:
                raise
            except Exception as exc:
                if not is_retryable_upload_error(exc) and not isinstance(exc, RuntimeError):
                    raise
                last_error = exc
            finally:
                if reader is not None:
                    reader.close()
                if response is not None:
                    response.close()
        if attempt < UPLOAD_RETRY_LIMIT:
            time.sleep(min(5, attempt))
    rollback_part_progress(state, lock, part_index)
    raise last_error


def upload_once_legacy(path, login_id=None, parent_id=None, location_id=None, note=None, name=None, use_proxy=False, site_host=OFFICIAL_SITE_HOST):
    ensure_requests_available()
    if not os.path.isfile(path):
        raise RuntimeError("File not found: {0}".format(path))

    file_size = os.path.getsize(path)
    file_name = name or os.path.basename(path)
    location_id = resolve_location(location_id)

    query = []
    if location_id:
        query.append(("locationId", location_id))
    if note:
        if len(note) > 500:
            raise RuntimeError("Note too long, max 500 chars")
        note_b64 = base64.urlsafe_b64encode(note.encode("utf-8")).decode("ascii")
        query.append(("note", note_b64))
    query_string = ("?" + urlencode(query)) if query else ""

    if login_id:
        if not parent_id:
            parent_id = fetch_root_directory_id(login_id, use_proxy=use_proxy, site_host=site_host)
        path_url = "/{0}/{1}{2}".format(quote(parent_id), quote(file_name), query_string)
    else:
        path_url = "/{0}{1}".format(quote(file_name), query_string)

    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/octet-stream",
        "Content-Length": str(file_size),
    }
    if login_id:
        headers["Authorization"] = "Bearer {0}".format(login_id)
    print_upload_header(path, file_size, login_id, parent_id, location_id, use_proxy, file_name, 1, 1, file_size, resolved_site_host=site_host)
    use_hotkeys = can_read_single_key()
    last_error = None

    upload_host = site_upload_host(site_host)
    for mode, label in choose_host_connection_attempts(upload_host, use_proxy):
        lock = threading.Lock()
        stop_event = threading.Event()
        cancel_event = threading.Event()
        state = {"phase": "connect", "note": label, "sent": 0}
        start_time = time.time()
        response = None
        reader = None
        data = None

        def monitor():
            while not stop_event.is_set():
                with lock:
                    sent = state["sent"]
                    phase = state["phase"]
                    note_text = state["note"]
                elapsed = time.time() - start_time
                speed = sent / elapsed if elapsed > 0 else 0
                percent = int(sent * 100 / file_size) if file_size else 100
                eta = int((file_size - sent) / speed) if file_size and speed > 0 else None
                display_kind = "connect" if phase == "connect" else "upload"
                if sent >= file_size and display_kind == "upload":
                    display_kind = "connect"
                    note_text = "{0} ack".format(note_text).strip()
                extra_parts = []
                if note_text:
                    extra_parts.append("[{0}]".format(note_text))
                if use_hotkeys:
                    extra_parts.append("[Q]")
                print_status(
                    display_kind,
                    percent,
                    speed,
                    eta,
                    elapsed,
                    " ".join(extra_parts),
                    done=sent,
                    total=file_size,
                )
                if use_hotkeys:
                    try:
                        import msvcrt
                        if msvcrt.kbhit():
                            key = read_single_key()
                            if key in ("quit", "esc"):
                                cancel_event.set()
                                stop_event.set()
                                return
                    except Exception:
                        pass
                time.sleep(0.1)

        monitor_thread = threading.Thread(target=monitor)
        monitor_thread.daemon = True
        monitor_thread.start()
        try:
            reader = UploadProgressReader(path, lock, state, cancel_event, label)
            response = requests.put(
                "https://{0}{1}".format(upload_host, path_url),
                headers=headers,
                data=reader,
                proxies=get_requests_proxies(mode),
                timeout=(8, NETWORK_IO_TIMEOUT),
                allow_redirects=False,
            )
            if cancel_event.is_set():
                raise DownloadCancelled("Upload cancelled by user.")
            raw = response.content
            if response.status_code >= 400:
                raise RuntimeError("Upload failed via {0}: HTTP {1} {2}\n{3}".format(label, response.status_code, response.reason, raw.decode("utf-8", "ignore")))
            data = parse_api_result(raw)
        except DownloadCancelled:
            sys.stdout.write(clear_line())
            finish_line("Upload cancelled by user.", Ansi.YELLOW + Ansi.BOLD if supports_color() else None)
            raise
        except Exception as exc:
            last_error = exc
        finally:
            stop_event.set()
            monitor_thread.join()
            if reader is not None:
                reader.close()
            if response is not None:
                response.close()

        if data is not None:
            sys.stdout.write(clear_line())
            finish_line("Uploaded: {0}".format(path), Ansi.GREEN + Ansi.BOLD if supports_color() else None)
            finish_line("Remote id: {0}".format(data.get("id")), Ansi.CYAN if supports_color() else None)
            finish_line("Remote name: {0}".format(data.get("name")), Ansi.CYAN if supports_color() else None)
            if data.get("id"):
                public_url = "https://{0}/{1}".format(site_host, data["id"])
                direct_url = "https://{0}/{1}/download".format(site_host, data["id"])
                finish_line("File page: {0}".format(public_url), Ansi.YELLOW + Ansi.BOLD if supports_color() else None)
                finish_line("Direct download: {0}".format(direct_url), Ansi.YELLOW if supports_color() else None)
                if clipboard_copy(public_url):
                    finish_line("Copied page link to clipboard.", Ansi.GREEN if supports_color() else None)
            return data

    raise last_error


def upload_multipart_once(path, login_id=None, parent_id=None, location_id=None, note=None, name=None, use_proxy=False, workers=DEFAULT_UPLOAD_WORKERS, part_size=None, site_host=OFFICIAL_SITE_HOST):
    ensure_requests_available()
    if not os.path.isfile(path):
        raise RuntimeError("File not found: {0}".format(path))

    file_size = os.path.getsize(path)
    file_name = name or os.path.basename(path)
    if login_id and not parent_id:
        parent_id = fetch_root_directory_id(login_id, use_proxy=use_proxy, site_host=site_host)

    resolved_part_size, total_parts = resolve_upload_part_size(file_size, part_size, requested_workers=workers)
    worker_count = max(1, min(int(workers or 1), total_parts))

    session = begin_multipart_upload(
        file_name,
        login_id=login_id,
        parent_id=parent_id,
        location_id=location_id,
        note=note,
        use_proxy=use_proxy,
        site_host=site_host,
    )
    upload_id = session["id"]
    upload_url = session["location"]

    print_upload_header(path, file_size, login_id, parent_id, location_id, use_proxy, file_name, workers, worker_count, resolved_part_size, resolved_site_host=site_host)

    use_hotkeys = can_read_single_key()
    lock = threading.Lock()
    stop_event = threading.Event()
    cancel_event = threading.Event()
    errors = []
    start_time = time.time()
    state = {
        "phase": "connect",
        "note": "init",
        "completed_bytes": 0,
        "display_sent": 0,
        "part_progress": [0] * total_parts,
    }

    def monitor():
        while not stop_event.is_set():
            with lock:
                sent = upload_progress_total(state, file_size)
                phase = state["phase"]
                note_text = state["note"]
            elapsed = time.time() - start_time
            speed = sent / elapsed if elapsed > 0 else 0
            percent = int(sent * 100 / file_size) if file_size else 100
            eta = int((file_size - sent) / speed) if file_size and speed > 0 and phase not in ("finalizing", "done") else None
            if phase == "connect":
                display_kind = "connect"
            elif phase == "finalizing":
                display_kind = "finalizing"
            else:
                display_kind = "upload"
            extra_parts = []
            if note_text:
                extra_parts.append("[{0}]".format(note_text))
            if use_hotkeys:
                extra_parts.append("[Q]")
            print_status(
                display_kind,
                percent,
                speed,
                eta,
                elapsed,
                " ".join(extra_parts),
                done=sent,
                total=file_size,
            )
            if use_hotkeys:
                try:
                    import msvcrt
                    if msvcrt.kbhit():
                        key = read_single_key()
                        if key in ("quit", "esc"):
                            cancel_event.set()
                            stop_event.set()
                            return
                except Exception:
                    pass
            time.sleep(0.1)

    job_queue = queue.Queue()
    for part_number in range(1, total_parts + 1):
        start_offset = (part_number - 1) * resolved_part_size
        part_length = min(resolved_part_size, file_size - start_offset)
        job_queue.put((part_number, start_offset, part_length))

    def worker():
        while not stop_event.is_set():
            try:
                part_number, start_offset, part_length = job_queue.get_nowait()
            except queue.Empty:
                return
            try:
                upload_part_with_retries(
                    upload_url,
                    path,
                    start_offset,
                    part_length,
                    part_number,
                    total_parts,
                    login_id,
                    use_proxy,
                    lock,
                    state,
                    stop_event,
                    cancel_event,
                )
            except Exception as exc:
                with lock:
                    errors.append(exc)
                stop_event.set()
                return
            finally:
                job_queue.task_done()

    monitor_thread = threading.Thread(target=monitor)
    monitor_thread.daemon = True
    monitor_thread.start()

    workers_list = []
    for _ in range(worker_count):
        t = threading.Thread(target=worker)
        t.daemon = True
        workers_list.append(t)
        t.start()

    for t in workers_list:
        t.join()

    if cancel_event.is_set():
        stop_event.set()
        monitor_thread.join()
        sys.stdout.write(clear_line())
        finish_line("Upload cancelled by user.", Ansi.YELLOW + Ansi.BOLD if supports_color() else None)
        raise DownloadCancelled("Upload cancelled by user.")

    if errors:
        stop_event.set()
        monitor_thread.join()
        raise errors[0]

    with lock:
        state["phase"] = "finalizing"
        state["note"] = "server commit"
        state["completed_bytes"] = file_size
        state["part_progress"] = [0] * total_parts
        state["display_sent"] = file_size
    try:
        data = complete_multipart_upload(upload_id, login_id=login_id, use_proxy=use_proxy, site_host=site_host)
    finally:
        stop_event.set()
        monitor_thread.join()
    sys.stdout.write(clear_line())
    finish_line("Uploaded: {0}".format(path), Ansi.GREEN + Ansi.BOLD if supports_color() else None)
    finish_line("Remote id: {0}".format(data.get("id")), Ansi.CYAN if supports_color() else None)
    finish_line("Remote name: {0}".format(data.get("name")), Ansi.CYAN if supports_color() else None)
    if data.get("id"):
        public_url = "https://{0}/{1}".format(site_host, data["id"])
        direct_url = "https://{0}/{1}/download".format(site_host, data["id"])
        finish_line("File page: {0}".format(public_url), Ansi.YELLOW + Ansi.BOLD if supports_color() else None)
        finish_line("Direct download: {0}".format(direct_url), Ansi.YELLOW if supports_color() else None)
        if clipboard_copy(public_url):
            finish_line("Copied page link to clipboard.", Ansi.GREEN if supports_color() else None)
    return data


def upload_once(path, login_id=None, parent_id=None, location_id=None, note=None, name=None, use_proxy=False, workers=DEFAULT_UPLOAD_WORKERS, part_size=None, site_host=OFFICIAL_SITE_HOST):
    return upload_multipart_once(
        path,
        login_id=login_id,
        parent_id=parent_id,
        location_id=location_id,
        note=note,
        name=name,
        use_proxy=use_proxy,
        workers=workers,
        part_size=part_size,
        site_host=site_host,
    )


def upload_file(path, login_id=None, parent_id=None, location_id=None, note=None, name=None, use_proxy=False, staged=False, workers=DEFAULT_UPLOAD_WORKERS, part_size=None, site_host="auto"):
    path = unwrap_drag_drop_value(path)
    name = unwrap_drag_drop_value(name)
    parent_id = unwrap_drag_drop_value(parent_id)
    location_id = unwrap_drag_drop_value(location_id)
    part_size = unwrap_drag_drop_value(part_size)
    if not os.path.isfile(path):
        raise RuntimeError("File not found: {0}".format(path))
    file_size = os.path.getsize(path)
    remote_name = name or os.path.basename(path)
    temp_name = None
    resolved_part_size, total_parts = resolve_upload_part_size(file_size, part_size, requested_workers=workers)
    requested_workers = max(1, int(workers or 1))
    worker_count = max(1, min(requested_workers, total_parts))
    resolved_site_host = resolve_site_host(site_host, use_proxy=use_proxy)

    if not confirm_upload_start(
        path,
        file_size,
        login_id,
        parent_id,
        location_id,
        note,
        use_proxy,
        remote_name,
        requested_workers,
        worker_count,
        resolved_part_size,
        selected_site_host=site_host,
        resolved_site_host=resolved_site_host,
    ):
        finish_line("Upload cancelled before start.", Ansi.YELLOW + Ansi.BOLD if supports_color() else None)
        raise DownloadCancelled("Upload cancelled before start.")

    if login_id and staged:
        temp_name = make_temp_remote_name(remote_name)

    attempt_name = temp_name or remote_name
    last_error = None
    data = None
    for attempt in range(1, 4):
        try:
            data = upload_once(
                path,
                login_id=login_id,
                parent_id=parent_id,
                location_id=location_id,
                note=note,
                name=attempt_name,
                use_proxy=use_proxy,
                workers=worker_count,
                part_size=resolved_part_size,
                site_host=resolved_site_host,
            )
            break
        except Exception as exc:
            last_error = exc
            time.sleep(0.5 * attempt)

    if data is None:
        raise last_error

    if login_id and staged and temp_name and remote_name != temp_name:
        try:
            renamed = rename_remote_item(login_id, data["id"], remote_name, use_proxy=use_proxy, site_host=resolved_site_host)
            data = renamed if renamed is not None else data
            finish_line("Finalized upload name: {0}".format(remote_name), Ansi.GREEN if supports_color() else None)
        except Exception as exc:
            finish_line(
                "Warning: upload finished but rename failed: {0}: {1}".format(type(exc).__name__, exc),
                Ansi.YELLOW if supports_color() else None,
            )

    return data


def prompt_text(label, default=None, allow_empty=False):
    if default is not None:
        prompt = "{0} [{1}]: ".format(label, default)
    else:
        prompt = "{0}: ".format(label)
    while True:
        value = safe_input(prompt, default=default, allow_empty=allow_empty)
        if value or default is not None or allow_empty:
            return value


def prompt_yes_no(label, default=False):
    suffix = "[Y/n]" if default else "[y/N]"
    raw = safe_input("{0} {1}: ".format(label, suffix), default=("y" if default else "n")).lower()
    if not raw:
        return default
    return raw in ("y", "yes", "1", "true", "on")


def interactive_prompt():
    choice = choose_menu_option(
        "Main Menu",
        [
            {"label": "Download file", "value": "download", "hint": "Get file by URL or id"},
            {"label": "Upload file", "value": "upload", "hint": "Send local file to Buzzheavier"},
        ],
    )
    clear_screen()
    print_banner()
    if choice == "download":
        print(color("Download Setup", Ansi.WHITE + Ansi.BOLD))
        print("")
        file_ref = prompt_text("File URL or id")
        out_dir = prompt_text("Output dir", DEFAULT_DOWNLOAD_DIR)
        threads_raw = prompt_text("Threads", str(DEFAULT_DOWNLOAD_THREADS))
        site_host = choose_site_host("auto")
        use_proxy = prompt_yes_no("Proxy on?", False)
        threads = int(threads_raw) if threads_raw else DEFAULT_DOWNLOAD_THREADS
        download_file(file_ref, out_dir, threads=threads, use_proxy=use_proxy, site_host=site_host)
        maybe_pause(True)
        return 0
    if choice == "upload":
        print(color("Upload Setup", Ansi.WHITE + Ansi.BOLD))
        print("")
        path = prompt_text("Local file path")
        auth = prompt_yes_no("Authenticated upload?", False)
        login_id = prompt_text("Login id") if auth else None
        parent_id = prompt_text("Parent folder id [optional]", "", allow_empty=True) or None
        note = prompt_text("Note [optional]", "", allow_empty=True) or None
        location = choose_upload_location(DEFAULT_UPLOAD_LOCATION)
        upload_workers_raw = prompt_text("Upload workers", str(DEFAULT_UPLOAD_WORKERS))
        part_size = choose_upload_part_size("50MiB")
        site_host = choose_site_host("auto")
        use_proxy = prompt_yes_no("Proxy on?", False)
        upload_workers = int(upload_workers_raw) if upload_workers_raw else DEFAULT_UPLOAD_WORKERS
        upload_file(path, login_id=login_id, parent_id=parent_id, location_id=location, note=note, use_proxy=use_proxy, workers=upload_workers, part_size=part_size, site_host=site_host)
        maybe_pause(True)
        return 0
    raise RuntimeError("Unknown menu choice: {0}".format(choice))


def build_parser():
    parser = argparse.ArgumentParser(description="Buzzheavier upload/download tool")
    parser.add_argument("--threads", type=int, default=DEFAULT_DOWNLOAD_THREADS, help="Download threads (default: 8)")
    parser.add_argument("--proxy", choices=["off", "on"], default="off", help="Use system proxy for this run")
    parser.add_argument("--site-host", choices=["auto", "buzzheavier.com", "bzzhr.co", "fuckingfast.net"], default="auto", help="Buzzheavier site host or mirror (default: auto)")
    parser.add_argument("--stay-open", action="store_true", help="Pause before exit so the window stays open")
    parser.add_argument("--staged-upload", action="store_true", help="Upload with a temporary name and rename after success")
    sub = parser.add_subparsers(dest="command")

    dl = sub.add_parser("download", help="Download a file")
    dl.add_argument("file", help="File URL or file id")
    dl.add_argument("-o", "--output-dir", default=DEFAULT_DOWNLOAD_DIR, help="Destination directory")
    dl.add_argument("-f", "--output-file", default=None, help="Explicit output file path")

    ul = sub.add_parser("upload", help="Upload a file")
    ul.add_argument("path", help="Local file path")
    ul.add_argument("--login-id", default=None, help="Bearer login id for authenticated upload")
    ul.add_argument("--parent-id", default=None, help="Parent directory id for authenticated upload")
    ul.add_argument("--location-id", default=None, help="Storage location id or alias (central, west, east)")
    ul.add_argument("--note", default=None, help="Optional note")
    ul.add_argument("--name", default=None, help="Remote file name override")
    ul.add_argument("--upload-workers", type=int, default=DEFAULT_UPLOAD_WORKERS, help="Multipart upload workers (default: 5)")
    ul.add_argument("--upload-part-size", default=None, help="Multipart upload part size, e.g. 5MiB, 25MB, 100M")

    return parser


def maybe_pause(stay_open):
    if not stay_open:
        return
    try:
        print("")
        input("Press Enter to close...")
    except Exception:
        pass


def main(argv=None):
    enable_virtual_terminal()
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        code = interactive_prompt()
        return code

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "download":
        download_file(
            unwrap_drag_drop_value(args.file),
            unwrap_drag_drop_value(args.output_dir),
            unwrap_drag_drop_value(args.output_file),
            threads=args.threads,
            use_proxy=(args.proxy == "on"),
            site_host=args.site_host,
        )
        maybe_pause(args.stay_open)
        return 0
    if args.command == "upload":
        upload_file(
            unwrap_drag_drop_value(args.path),
            login_id=unwrap_drag_drop_value(args.login_id),
            parent_id=unwrap_drag_drop_value(args.parent_id),
            location_id=unwrap_drag_drop_value(args.location_id),
            note=unwrap_drag_drop_value(args.note),
            name=unwrap_drag_drop_value(args.name),
            use_proxy=(args.proxy == "on"),
            staged=args.staged_upload,
            workers=args.upload_workers,
            part_size=unwrap_drag_drop_value(args.upload_part_size),
            site_host=args.site_host,
        )
        maybe_pause(args.stay_open)
        return 0

    parser.print_help()
    maybe_pause(args.stay_open)
    return 0


if __name__ == "__main__":
    try:
        code = main()
        maybe_pause("--stay-open" in sys.argv)
        sys.exit(code)
    except DownloadCancelled:
        maybe_pause("--stay-open" in sys.argv)
        sys.exit(1)
    except UserInputUnavailable as exc:
        finish_line("Error: {0}".format(exc), Ansi.RED + Ansi.BOLD if supports_color() else None)
        maybe_pause("--stay-open" in sys.argv)
        sys.exit(1)
    except Exception as exc:
        try:
            finish_line("Error: {0}: {1}".format(type(exc).__name__, exc), Ansi.RED + Ansi.BOLD if supports_color() else None)
            tb = traceback.format_exc()
            if tb:
                sys.stdout.write(tb + "\n")
        except Exception:
            print("Error: {0}: {1}".format(type(exc).__name__, exc))
        maybe_pause("--stay-open" in sys.argv)
        sys.exit(1)
