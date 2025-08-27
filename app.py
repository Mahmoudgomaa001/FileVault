import os
import re
import json
import uuid
import base64
import socket
import mimetypes
import secrets
import random
import unicodedata
import requests
import shutil
import hashlib
import zipfile
from io import BytesIO
from pathlib import Path
from datetime import datetime
from typing import Optional

from flask import (
    Flask, request, session, redirect, url_for, send_from_directory, send_file,
    render_template_string, abort, jsonify, Response, make_response
)
from flask_socketio import SocketIO
import qrcode
from qrcode.constants import ERROR_CORRECT_H

# -----------------------------
# Islamic Dhikr (Remembrance)
# -----------------------------


# -----------------------------
# Friendly IDs
# -----------------------------
# -----------------------------
# Friendly IDs
# -----------------------------
# -----------------------------
# Friendly IDs
# -----------------------------
USER_ICONS = ["🦄","🦆","🐙","🐢","🦊","🐼","🐧","🐸","🐝","🐠"]
ADJECTIVES = ["happy","brave","silly","gentle","fuzzy","quiet","wild","clever","bright","swift","lucky"]
ANIMALS = ["duck","unicorn","panda","fox","tiger","whale","otter","koala","cat","owl"]

def generate_name() -> str:
    # e.g. lucky-duck-042
    return f"{random.choice(ADJECTIVES)}-{random.choice(ANIMALS)}-{random.randint(0,999):03d}"

def get_user_icon(user_id: str) -> str:
    return USER_ICONS[hash(user_id) % len(USER_ICONS)]

# -----------------------------
# Config
# -----------------------------
PORT = int(os.getenv("PORT", "5000"))
APP_SECRET = os.environ.get("APP_SECRET", "change-me")
ROOT_DIR = Path(os.environ.get("ROOT_DIR", "./shared")).resolve()
ALLOWED_UPLOAD_EXT = None  # e.g. {"txt","png","jpg","pdf"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024 * 1024  # 10GB
SESSION_COOKIE_NAME = "qrfiles_sess"
# Pending admin-claim tokens (QR-based transfer)
admin_claim_tokens: dict[str, dict] = {}



# Load adhkar and translations from JSON file
def load_adhkar():
    ROOT_DIR = Path(__file__).parent.resolve()  # project root (where gpt_v11.py lives)
    file_path = ROOT_DIR / "static" / "adhkar.json"
    if not file_path.exists():
        raise FileNotFoundError(f"Adhkar file not found at: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["adhkar"]


ISLAMIC_DHIKR = load_adhkar()


def get_random_dhikr():
    return random.choice(ISLAMIC_DHIKR)


# Ngrok URL (can be set via environment variable or auto-detected)
NGROK_URL = os.environ.get("NGROK_URL", "").strip()

# Persistent device <-> folder mapping
DEVICE_COOKIE_NAME = "qr_device"
DEVICE_MAP_FILE = ROOT_DIR / ".device_map.json"
USERS_FILE = ROOT_DIR / ".users.json"  # folder -> {public, admin_device, salt, password_hash, prefs}

ROOT_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = APP_SECRET
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["SESSION_COOKIE_NAME"] = SESSION_COOKIE_NAME
app.config["LOGIN_TOKENS"] = {}  # pc_token -> folder

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# In-memory pending sessions for QR login
pending_sessions: dict[str, dict] = {}

mimetypes.init()

# -----------------------------
# Favicon + brand assets
# -----------------------------
FAVICON_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" width="128" height="128">
  <defs>
    <!-- Gradient fill -->
    <linearGradient id="shieldGradient" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#3b82f6"/>
      <stop offset="100%" stop-color="#8b5cf6"/>
    </linearGradient>
  </defs>

  <!-- Half-shield with gradient + white border -->
  <path d="M320 64C324.6 64 329.2 65 333.4 66.9L521.8 146.8C543.8 156.1 560.2 177.8 560.1 204C559.6 303.2 518.8 484.7 346.5 567.2C329.8 575.2 310.4 575.2 293.7 567.2C121.3 484.7 80.6 303.2 80.1 204C80 177.8 96.4 156.1 118.4 146.8L306.7 66.9C310.9 65 315.4 64 320 64zM320 130.8L320 508.9C458 442.1 495.1 294.1 496 205.5L320 130.9z"
        fill="url(#shieldGradient)"
        stroke="white"
        stroke-width="25"
        stroke-linejoin="round"/>
</svg>

"""

def ensure_favicon_assets():
    base = Path(__file__).parent.resolve() / "static"
    base.mkdir(parents=True, exist_ok=True)

    fav_svg = base / "favicon.svg"
    if not fav_svg.exists():
        try:
            tmp = fav_svg.with_suffix(".svg.tmp")
            tmp.write_text(FAVICON_SVG, encoding="utf-8")
            tmp.replace(fav_svg)
            print(f"[assets] Wrote favicon.svg -> {fav_svg}")
        except Exception as e:
            print("[assets] favicon write failed:", e)

    # Minimal PWA manifest using SVG icons (offline-friendly)
    manifest = {
        "name": "GomaaFileVault",
        "short_name": "FileVault",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffe6f2",
        "theme_color": "#ff4fa3",
        "icons": [
            {"src": "/static/favicon.svg", "sizes": "any", "type": "image/svg+xml"}
        ],
        "share_target": {
            "action": "/share-receiver",
            "method": "POST",
            "enctype": "multipart/form-data",
            "params": {
                "files": [
                    {
                        "name": "files",
                        "accept": ["*/*"]
                    }
                ]
            }
        }
    }
    manifest_path = base / "site.webmanifest"
    try:
        tmp = manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(manifest_path)
        print(f"[assets] Wrote site.webmanifest -> {manifest_path}")
    except Exception as e:
        print("[assets] manifest write failed:", e)

# Call this during startup (after ensure_static_assets)
try:
    ensure_favicon_assets()
except Exception as e:
    print("Brand assets error:", e)


mimetypes.add_type("font/woff2", ".woff2")  # make sure .woff2 served correctly


# -----------------------------
# Device map persistence
# -----------------------------
def load_device_map() -> dict:
    try:
        if DEVICE_MAP_FILE.exists():
            return json.loads(DEVICE_MAP_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print("Device map load failed:", e)
    return {}

def save_device_map(mapdata: dict):
    try:
        DEVICE_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = DEVICE_MAP_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(mapdata, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(DEVICE_MAP_FILE)
    except Exception as e:
        print("Device map save failed:", e)

app.config["DEVICE_MAP"] = load_device_map()

# -----------------------------
# Users (privacy + prefs)
# -----------------------------
def _load_json_file(p: Path, default: dict) -> dict:
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Load {p.name} failed:", e)
    return default.copy()

def _save_json_file(p: Path, data: dict):
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        print(f"Save {p.name} failed:", e)

def load_users() -> dict:
    data = _load_json_file(USERS_FILE, {})
    return data

def save_users(data: dict):
    _save_json_file(USERS_FILE, data)

def get_user_cfg(folder: str) -> dict:
    users = app.config.setdefault("USERS", load_users())
    if folder not in users:
        users[folder] = {
            "public": True,
            "admin_device": None,
            "salt": None,
            "password_hash": None,
            "prefs": {}
        }
        save_users(users)
    return users[folder]

def set_privacy(folder: str, public: bool, password: Optional[str]=None):
    users = app.config.setdefault("USERS", load_users())
    cfg = users.setdefault(folder, {"public": True, "admin_device": None, "salt": None, "password_hash": None, "prefs": {}})
    cfg["public"] = bool(public)
    if not public:
        if password:
            salt = os.urandom(16)
            cfg["salt"] = salt.hex()
            cfg["password_hash"] = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
    else:
        cfg["salt"] = None
        cfg["password_hash"] = None
    save_users(users)

def verify_password(folder: str, password: str) -> bool:
    cfg = get_user_cfg(folder)
    if not cfg.get("password_hash") or not cfg.get("salt"):
        return False
    salt = bytes.fromhex(cfg["salt"])
    h = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
    return secrets.compare_digest(h, cfg["password_hash"])

def save_pref(folder: str, key: str, value):
    cfg = get_user_cfg(folder)
    prefs = cfg.setdefault("prefs", {})
    prefs[key] = value
    save_users(app.config["USERS"])

# -----------------------------
# Device folder with admin assignment
# -----------------------------
def ensure_unique_folder_name() -> str:
    users_map = app.config.setdefault("USERS", load_users())
    used = set(users_map.keys()) | {info["folder"] for info in app.config["DEVICE_MAP"].values()}
    for _ in range(1000):
        name = generate_name()
        if name not in used and not (ROOT_DIR / name).exists():
            return name
    return f"user-{secrets.token_hex(4)}"

def get_or_create_device_folder(req) -> tuple[str, str]:
    device_id = req.cookies.get(DEVICE_COOKIE_NAME)
    if device_id and device_id in app.config["DEVICE_MAP"]:
        folder = app.config["DEVICE_MAP"][device_id]["folder"]
        (ROOT_DIR / folder).mkdir(parents=True, exist_ok=True)
        cfg = get_user_cfg(folder)
        if not cfg.get("admin_device"):
            cfg["admin_device"] = device_id
            save_users(app.config["USERS"])
        return device_id, folder
    device_id = secrets.token_urlsafe(12)
    folder = ensure_unique_folder_name()
    (ROOT_DIR / folder).mkdir(parents=True, exist_ok=True)
    app.config["DEVICE_MAP"][device_id] = {"folder": folder, "created": datetime.utcnow().isoformat() + "Z"}
    save_device_map(app.config["DEVICE_MAP"])
    cfg = get_user_cfg(folder)
    if not cfg.get("admin_device"):
        cfg["admin_device"] = device_id
        save_users(app.config["USERS"])
    return device_id, folder

# -----------------------------
# Helpers
# -----------------------------

# -----------------------------
# Accounts API (admin-only)
# -----------------------------
# -----------------------------
# Accounts API (admin-only)
# -----------------------------
def is_admin_device_of(folder: str) -> bool:
    cfg = get_user_cfg(folder)
    did = request.cookies.get(DEVICE_COOKIE_NAME)
    return bool(did and did == cfg.get("admin_device"))

@app.route("/api/accounts", methods=["GET"])
def api_accounts_list():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401
    did = request.cookies.get(DEVICE_COOKIE_NAME)
    if not did:
        return jsonify({"ok": False, "error": "device not recognized"}), 400
    users = app.config.setdefault("USERS", load_users())
    device_map = app.config["DEVICE_MAP"]
    default_folder = (device_map.get(did) or {}).get("folder")

    accounts = []
    for folder, cfg in users.items():
        if cfg.get("admin_device") == did:
            accounts.append({
                "folder": folder,
                "public": cfg.get("public", True),
                "is_default": (folder == default_folder)
            })
    accounts.sort(key=lambda a: a["folder"])
    return jsonify({"ok": True, "accounts": accounts, "default": default_folder})

@app.route("/api/accounts/create", methods=["POST"])
def api_accounts_create():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401

    current_folder = session.get("folder")
    if not is_admin_device_of(current_folder):
        return jsonify({"ok": False, "error": "only admin device can create accounts"}), 403

    data = request.get_json(silent=True) or {}
    name_raw = (data.get("name") or "").strip()
    make_default = bool(data.get("make_default", True))

    if name_raw:
        # Allow lowercase letters, digits, hyphens; ensure starts with [a-z0-9]
        name = sanitize_filename(name_raw.lower())
        if not re.fullmatch(r"[a-z0-9][a-z0-9\-]{1,200}", name):
            return jsonify({"ok": False, "error": "bad name (use a-z, 0-9, -)"}), 400
        if (ROOT_DIR / name).exists():
            return jsonify({"ok": False, "error": "folder exists"}), 400
    else:
        name = ensure_unique_folder_name()

    try:
        (ROOT_DIR / name).mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        return jsonify({"ok": False, "error": "folder exists"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    did = request.cookies.get(DEVICE_COOKIE_NAME)
    uc = get_user_cfg(name)
    uc["admin_device"] = did
    uc.setdefault("public", True)
    uc.setdefault("prefs", {})
    save_users(app.config["USERS"])

    if make_default:
        app.config["DEVICE_MAP"][did] = {"folder": name, "created": datetime.utcnow().isoformat() + "Z"}
        save_device_map(app.config["DEVICE_MAP"])
        session["folder"] = name
        session["icon"] = get_user_icon(name)

    return jsonify({"ok": True, "folder": name, "switched": make_default, "browse_url": url_for("browse", subpath=name)}), 201

@app.route("/api/accounts/switch", methods=["POST"])
def api_accounts_switch():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401
    data = request.get_json(silent=True) or {}
    folder = (data.get("folder") or "").strip()
    make_default = bool(data.get("make_default", True))
    if not folder:
        return jsonify({"ok": False, "error": "folder required"}), 400

    users = app.config.setdefault("USERS", load_users())
    if folder not in users:
        return jsonify({"ok": False, "error": "no such account"}), 404

    did = request.cookies.get(DEVICE_COOKIE_NAME)
    if users[folder].get("admin_device") != did:
        return jsonify({"ok": False, "error": "only admin device can switch to this account"}), 403

    (ROOT_DIR / folder).mkdir(parents=True, exist_ok=True)
    session["folder"] = folder
    session["icon"] = get_user_icon(folder)

    if make_default:
        app.config["DEVICE_MAP"][did] = {"folder": folder, "created": datetime.utcnow().isoformat() + "Z"}
        save_device_map(app.config["DEVICE_MAP"])

    return jsonify({"ok": True, "folder": folder, "browse_url": url_for("browse", subpath=folder)})

@app.route("/api/accounts/rename", methods=["POST"])
def api_accounts_rename():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401

    data = request.get_json(silent=True) or {}
    old_name = data.get("old_name", "").strip()
    new_name_raw = data.get("new_name", "").strip()

    if not old_name or not new_name_raw:
        return jsonify({"ok": False, "error": "Old and new names are required"}), 400

    if not is_admin_device_of(old_name):
        return jsonify({"ok": False, "error": "Only the admin can rename this account"}), 403

    new_name = sanitize_filename(new_name_raw.lower())
    if not re.fullmatch(r"[a-z0-9][a-z0-9\-]{1,200}", new_name):
        return jsonify({"ok": False, "error": "Invalid new name (use a-z, 0-9, -)"}), 400

    old_path = safe_path(old_name)
    new_path = safe_path(new_name)

    if not old_path.exists() or not old_path.is_dir():
        return jsonify({"ok": False, "error": "Old account folder not found"}), 404

    if new_path.exists():
        return jsonify({"ok": False, "error": "An account with the new name already exists"}), 409

    try:
        shutil.move(str(old_path), str(new_path))

        users = app.config.setdefault("USERS", load_users())
        if old_name in users:
            users[new_name] = users.pop(old_name)
            save_users(users)

        device_map = app.config["DEVICE_MAP"]
        updated_device_map = False
        for device_id, info in device_map.items():
            if info.get("folder") == old_name:
                info["folder"] = new_name
                updated_device_map = True
        if updated_device_map:
            save_device_map(device_map)

        if session.get("folder") == old_name:
            session["folder"] = new_name
            session["icon"] = get_user_icon(new_name)

        return jsonify({"ok": True, "message": "Account renamed successfully"})

    except Exception as e:
        if new_path.exists() and not old_path.exists():
            shutil.move(str(new_path), str(old_path))
        return jsonify({"ok": False, "error": f"An error occurred: {e}"}), 500

def get_user_by_token(token):
    """Find a user by their API token"""
    if not token:
        return None

    users = app.config.setdefault("USERS", load_users())

    # Search through all users and their tokens
    for folder, user_data in users.items():
        tokens = user_data.get("tokens", {})
        for token_id, token_info in tokens.items():
            if token_info.get("token") == token:
                # Return user data with folder included
                return {"folder": folder, "icon": user_data.get("icon"), **user_data}

    return None

@app.route("/api/accounts/token", methods=["POST"])
def api_accounts_token():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401

    data = request.get_json(silent=True) or {}
    folder = (data.get("folder") or "").strip()
    if not folder:
        folder = session.get("folder", "")
        if not folder:
            return jsonify({"ok": False, "error": "folder required"}), 400

    users = app.config.setdefault("USERS", load_users())
    if folder not in users:
        return jsonify({"ok": False, "error": "no such account"}), 404

    did = request.cookies.get(DEVICE_COOKIE_NAME)
    if users[folder].get("admin_device") != did:
        return jsonify({"ok": False, "error": "only admin device can generate tokens"}), 403

    # Check if a permanent token already exists
    user_cfg = users[folder]
    tokens = user_cfg.setdefault("tokens", {})
    existing = next((info for info in tokens.values() if info.get("expires") is None), None)

    if existing:
        return jsonify({
            "ok": True,
            "token": existing["token"],
            "message": "Permanent token already exists"
        })

    # Otherwise generate one new permanent token
    token = secrets.token_urlsafe(32)
    token_id = str(uuid.uuid4())
    tokens[token_id] = {
        "token": token,
        "created": datetime.utcnow().isoformat() + "Z",
        "name": data.get("name", "API Token"),
        "expires": None
    }
    save_users(users)

    return jsonify({
        "ok": True,
        "token": token,
        "token_id": token_id,
        "message": "Permanent token created successfully"
    })

def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

def get_ngrok_url() -> Optional[str]:
    global NGROK_URL
    if NGROK_URL:
        return NGROK_URL
    try:
        response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=1)
        tunnels = response.json().get("tunnels", [])
        for tunnel in tunnels:
            if tunnel.get("proto") == "https":
                NGROK_URL = tunnel.get("public_url", "").strip()
                if NGROK_URL:
                    print(f"Auto-detected ngrok URL: {NGROK_URL}")
                    return NGROK_URL
        for tunnel in tunnels:
            if tunnel.get("proto") == "http":
                NGROK_URL = tunnel.get("public_url", "").strip()
                if NGROK_URL:
                    print(f"Auto-detected ngrok URL: {NGROK_URL}")
                    return NGROK_URL
    except Exception:
        pass
    return None

def make_qr_png_b64(data: str) -> str:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=8,
        border=4
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def is_authed() -> bool:
    return session.get("authed", False) is True

def safe_path(path: Optional[str]) -> Path:
    base = ROOT_DIR
    p = (base / (path or "")).resolve()
    if base not in p.parents and p != base:
        abort(403)
    return p

def sanitize_filename(filename: str) -> str:
    name = os.path.basename(filename or "").strip()
    name = unicodedata.normalize("NFC", name)
    name = "".join(ch for ch in name if ch >= " " and ch != "\x7f")
    illegal = '<>:"\\|?*\n\r\t'
    name = name.replace("/", "_").replace("\\", "_")
    for ch in illegal:
        name = name.replace(ch, "_")
    name = name.strip().strip(".")
    if not name:
        name = "file"
    if len(name) > 200:
        base, ext = os.path.splitext(name)
        name = base[:200 - len(ext)] + ext
    return name

def human_size(n: Optional[int]) -> str:
    if n is None: return "-"
    units = ["B","KB","MB","GB","TB"]
    sr = 0; f = float(n)
    while f >= 1024 and sr < len(units)-1:
        f /= 1024.0; sr += 1
    return f"{f:.2f} {units[sr]}"

def human_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%b %d")

def guess_mime(p: Path) -> str:
    mime, _ = mimetypes.guess_type(p.name)
    return mime or "application/octet-stream"

def path_rel(p: Path) -> str:
    return p.relative_to(ROOT_DIR).as_posix()

def get_file_meta(p: Path) -> dict:
    rel = path_rel(p)
    mime = guess_mime(p)
    return {
        "name": p.name,
        "rel": rel,
        "is_dir": p.is_dir(),
        "mime": mime,
        "size": p.stat().st_size if p.is_file() else 0,
        "size_h": human_size(p.stat().st_size) if p.is_file() else "-",
        "mtime": int(p.stat().st_mtime),
        "mtime_h": human_time(p.stat().st_mtime),
        "raw_url": url_for("raw", path=rel),
        "download_url": url_for("download", path=rel),
    }

def get_stats(folder: Path) -> dict:
    files = 0
    dirs = 0
    size = 0
    for p in folder.rglob("*"):
        try:
            if p.is_file():
                files += 1
                size += p.stat().st_size
            elif p.is_dir():
                dirs += 1
        except Exception:
            pass
    return {"files": files, "dirs": dirs, "size_h": human_size(size)}

def first_segment(rel: str) -> Optional[str]:
    rel = (rel or "").strip().strip("/")
    if not rel: return None
    return rel.split("/", 1)[0]

def has_folder_access(folder: str) -> bool:
    cfg = get_user_cfg(folder)
    if cfg.get("public", True): return True
    device_id = request.cookies.get(DEVICE_COOKIE_NAME)
    if device_id and device_id == cfg.get("admin_device"): return True
    access_ok = session.get("access_ok", {})
    if isinstance(access_ok, dict) and access_ok.get(folder) is True:
        return True
    return False

def enforce_access_or_redirect(folder: str):
    if has_folder_access(folder):
        return None
    next_url = request.full_path or request.path
    return redirect(url_for("unlock", folder=folder, next=next_url))

# -----------------------------
# Range streaming for /raw
# -----------------------------
def send_partial_file(p: Path, mime: str):
    size = p.stat().st_size
    range_header = request.headers.get("Range", None)
    if not range_header:
        return send_file(p, mimetype=mime, conditional=True)
    m = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not m:
        return send_file(p, mimetype=mime, conditional=True)
    start = int(m.group(1))
    end = m.group(2)
    end = int(end) if end else size - 1
    if start >= size:
        return Response(status=416, headers={"Content-Range": f"bytes */{size}"})
    length = end - start + 1
    def stream():
        with p.open("rb") as f:
            f.seek(start)
            remaining = length
            chunk = 1024 * 1024
            while remaining > 0:
                data = f.read(min(chunk, remaining))
                if not data: break
                remaining -= len(data)
                yield data
    rv = Response(stream(), status=206, mimetype=mime, direct_passthrough=True)
    rv.headers.add("Content-Range", f"bytes {start}-{end}/{size}")
    rv.headers.add("Accept-Ranges", "bytes")
    rv.headers.add("Content-Length", str(length))
    return rv

# -----------------------------
# Templates (UI)
# -----------------------------
BASE_HTML = """
<!doctype html>
<html lang="en">
<head>

<script>
  (function(){try{var t=localStorage.getItem('theme')||''; if(t&&t!=='dark') document.documentElement.classList.add(t);}catch(e){}})();
</script>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
  <meta name="apple-mobile-web-app-capable" content="yes"/>
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"/>
  <title>FileVault</title>

<link rel="icon" href="/static/favicon.svg" type="image/svg+xml" />
<link rel="manifest" href="/static/site.webmanifest" />
<meta name="theme-color" content="#0F172A" id="themeColorMeta" />
<link rel="stylesheet" href="/static/fonts.css" />
<link rel="stylesheet" href="/static/vendor/fontawesome/css/all.min.css" />
<link rel="stylesheet" href="/static/vendor/fontawesome/css/fa-shims.css" />


  <style>
    * { margin:0; padding:0; box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
    :root {
      --primary:#3B82F6; --primary-dark:#2563EB; --secondary:#8B5CF6; --success:#10B981; --danger:#EF4444; --warning:#F59E0B;
      --bg-primary:#0F172A; --bg-secondary:#1E293B; --bg-tertiary:#334155; --text-primary:#F8FAFC; --text-secondary:#CBD5E1; --text-muted:#64748B;
      --border:#334155; --shadow:rgba(0,0,0,0.5); --header-height:60px; --mobile-padding:.75rem; --desktop-padding:1.5rem;
      --dhikr-bg: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    :root.light {
      --bg-primary:#f7fafc; --bg-secondary:#ffffff; --bg-tertiary:#e5e7eb; --text-primary:#0f172a; --text-secondary:#334155; --text-muted:#64748b;
      --border:#e5e7eb; --shadow:rgba(0,0,0,0.12);
      --dhikr-bg: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    :root.barbie {
  --primary:#ff4fa3;
  --primary-dark:#f12783;
  --secondary:#ff7ac8;
  --success:#ff9ad5;
  --danger:#ff497a;
  --warning:#ffb6e1;

  --bg-primary:#ffe6f2;
  --bg-secondary:#fff0f7;
  --bg-tertiary:#ffd6ea;

  --text-primary:#5b0440;
  --text-secondary:#8a2664;
  --text-muted:#a34a7c;

  --border:#ffc0dd;
  --shadow:rgba(255, 116, 183, 0.25);
  --dhikr-bg: linear-gradient(135deg, #ff8ccf 0%, #ff4fa3 100%);
}
    html, body, a, button, .file-card { touch-action: manipulation; }
    body { font-family:'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background:var(--bg-primary); color:var(--text-primary); min-height:100vh; position:relative; overflow-x:hidden; }

    /* Dhikr Banner */
    .dhikr-banner {
      background: var(--dhikr-bg);
      padding: 1rem;
      text-align: center;
      position: fixed;
      top: var(--header-height);
      left: 0;
      right: 0;
      z-index: 900;
      box-shadow: 0 2px 10px rgba(0,0,0,0.2);
      animation: slideDown 0.5s ease;
      cursor: pointer;
      transition: all 0.3s ease;
    }
    @keyframes slideDown { from { transform: translateY(-100%); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    .dhikr-banner:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.3); transform: scale(1.01); }
    .dhikr-content { display: flex; align-items: center; justify-content: center; gap: 0.5rem; flex-wrap: wrap; }
    .dhikr-arabic { font-family: 'Amiri', serif; font-size: 1.5rem; font-weight: 700; color: #ffffff; text-shadow: 2px 2px 4px rgba(0,0,0,0.2); animation: pulse 2s ease-in-out infinite; }
    @keyframes pulse { 0%, 100% { transform: scale(1);} 50% { transform: scale(1.05);} }
    .dhikr-translation { font-size: 0.9rem; color: rgba(255,255,255,0.9); font-style: italic; }
    .dhikr-icon { font-size: 1.2rem; color: rgba(255,255,255,0.8); animation: rotate 4s linear infinite; }
    @keyframes rotate { from { transform: rotate(0deg);} to { transform: rotate(360deg);} }
    .dhikr-refresh { position: absolute; right: 1rem; top: 50%; transform: translateY(-50%); background: rgba(255,255,255,0.2); border: none; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.3s ease; color: white; }
    .dhikr-refresh:hover { background: rgba(255,255,255,0.3); transform: translateY(-50%) rotate(180deg); }

    body.with-dhikr .container { padding-top: calc(var(--header-height) + 60px + var(--mobile-padding)); }

    .header { background:rgba(30,41,59,.98); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); border-bottom:1px solid var(--border); position:fixed; top:0; left:0; right:0; z-index:1000; height:var(--header-height); }
    :root.light .header { background:rgba(255,255,255,.98); }
    .header-content { max-width:1400px; margin:0 auto; padding:0 var(--mobile-padding); height:100%; display:flex; justify-content:space-between; align-items:center; gap:.5rem; }
    .logo { display:flex; align-items:center; gap:.5rem; font-size:1.125rem; font-weight:700; background:linear-gradient(135deg,var(--primary),var(--secondary)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; white-space:nowrap; text-decoration:none; }
    .nav-menu { display:flex; gap:.5rem; align-items:center; }
    .user-badge { display:none; padding:.375rem .75rem; background:var(--bg-tertiary); border-radius:2rem; font-size:.75rem; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .container { max-width:1400px; margin:0 auto; padding:calc(var(--header-height) + var(--mobile-padding)) var(--mobile-padding) var(--mobile-padding); min-height:100vh; }
    .card { background:var(--bg-secondary); border:1px solid var(--border); border-radius:.75rem; padding:var(--mobile-padding); margin-bottom:var(--mobile-padding); animation:fadeIn .3s ease; }
    @keyframes fadeIn { from{opacity:0; transform:translateY(10px);} to{opacity:1; transform:translateY(0);} }
    .toolbar { display:flex; flex-direction:column; gap:.75rem; margin-bottom:1rem; background:var(--bg-secondary); padding:var(--mobile-padding); border-radius:.75rem; border:1px solid var(--border); }
    .toolbar-row { display:flex; gap:.5rem; align-items:center; flex-wrap:wrap; }
    .search-box { flex:1; min-width:150px; position:relative; }
    .search-input { width:100%; padding:.625rem 2.5rem .625rem .875rem; background:var(--bg-primary); border:1px solid var(--border); border-radius:.5rem; color:var(--text-primary); font-size:.875rem; }
    .search-input:focus { outline:none; border-color:var(--primary); box-shadow:0 0 0 3px rgba(59,130,246,.1); }
    .search-icon { position:absolute; right:.875rem; top:50%; transform:translateY(-50%); color:var(--text-muted); pointer-events:none; }
    .view-controls { display:flex; gap:.25rem; padding:.25rem; background:var(--bg-primary); border-radius:.5rem; }
    .view-btn { flex:1; padding:.5rem; background:transparent; border:none; color:var(--text-muted); cursor:pointer; border-radius:.375rem; font-size:.875rem; transition:all .2s; display:flex; align-items:center; justify-content:center; gap:.25rem; }
    .view-btn.active { background:var(--primary); color:white; }
    .btn { padding:.5rem .875rem; border-radius:.5rem; font-weight:600; cursor:pointer; transition:all .2s; border:none; display:inline-flex; align-items:center; justify-content:center; gap:.375rem; font-size:.8125rem; white-space:nowrap; text-decoration:none; color:inherit; }
    .btn:active { transform:scale(.97); }
    .btn-primary { background:var(--primary); color:#fff; }
    .btn-secondary { background:var(--bg-tertiary); color:var(--text-primary); }
    .btn-danger { background:var(--danger); color:#fff; }
    .btn-success { background:var(--success); color:#fff; }

    /* Toggle */
    .toggle-container { display:flex; align-items:center; gap:.75rem; padding:.75rem; background:var(--bg-tertiary); border-radius:.5rem; }
    .toggle-switch { position:relative; width:56px; height:28px; background:var(--bg-primary); border:2px solid var(--border); border-radius:14px; cursor:pointer; transition:all .3s; }
    .toggle-switch.active { background:var(--primary); border-color:var(--primary); }
    .toggle-switch .slider { position:absolute; top:2px; left:2px; width:20px; height:20px; background:white; border-radius:50%; transition:all .3s; }
    .toggle-switch.active .slider { transform:translateX(28px); }
    .toggle-label { font-size:.875rem; font-weight:600; user-select:none; cursor:pointer; }

    /* Upload */
    .upload-section { margin-bottom:1.5rem; }
    .upload-area { border:2px dashed var(--primary); border-radius:.75rem; padding:1.5rem 1rem; text-align:center; background:linear-gradient(135deg, rgba(59,130,246,.05), rgba(139,92,246,.05)); cursor:pointer; min-height:120px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:.25rem; position:relative; }
    .upload-area.dragover { background:linear-gradient(135deg, rgba(59,130,246,.15), rgba(139,92,246,.15)); border-color:var(--success); }
    .upload-input { position:absolute; width:100%; height:100%; inset:0; opacity:0; cursor:pointer; }
    .upload-icon { font-size:2rem; color:var(--primary); }
    .upload-text { font-size:.875rem; font-weight:700; }
    .upload-subtext { font-size:.75rem; color:var(--text-muted); }
    .progress-container { margin-top:1rem; max-height:300px; overflow-y:auto; }
    .progress-item { background:var(--bg-secondary); border-radius:.5rem; padding:.75rem; margin-bottom:.5rem; border:1px solid var(--border); animation:slideIn .3s ease; }
    @keyframes slideIn { from{opacity:0; transform:translateX(-10px);} to{opacity:1; transform:translateX(0);} }
    .progress-item.completed { border-color:var(--success); background:rgba(16,185,129,.1); }
    .progress-item.error { border-color:var(--danger); background:rgba(239,68,68,.1); }
    .progress-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:.5rem; gap:.5rem; }
    .progress-info { flex:1; min-width:0; }
    .progress-filename { font-size:.75rem; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-bottom:.25rem; }
    .progress-stats { display:flex; gap:.5rem; font-size:.625rem; color:var(--text-muted); }
    .progress-actions { display:flex; align-items:center; gap:.25rem; }
    .progress-percent { font-size:.75rem; font-weight:700; min-width:35px; text-align:right; }
    .progress-cancel { width:28px; height:28px; border-radius:50%; background:var(--bg-tertiary); border:none; color:var(--text-muted); cursor:pointer; display:flex; align-items:center; justify-content:center; font-size:.75rem; }
    .progress-bar { height:4px; background:var(--bg-tertiary); border-radius:2px; overflow:hidden; }
    .progress-fill { height:100%; background:linear-gradient(90deg, var(--primary), var(--secondary)); border-radius:2px; width:0%; transition:width .25s ease; }


    /* File grid */
    .file-grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap:.75rem; margin-top:1rem; }
    .file-grid.list-view { grid-template-columns: 1fr; gap:.5rem; }
    .file-card { background:var(--bg-secondary); border:1px solid var(--border); border-radius:.75rem; overflow:hidden; transition:all .2s ease; cursor:pointer; }
    .file-card:active { transform:scale(.98); }
    .file-card.selected { border-color: var(--primary); background: color-mix(in srgb, var(--bg-secondary) 80%, var(--primary)); }
    .file-select-checkbox { display: none; position: absolute; top: 8px; left: 8px; z-index: 5; width: 18px; height: 18px; accent-color: var(--primary); }
    .select-mode .file-select-checkbox { display: block; }
    .list-view .file-card { display:flex; align-items:center; padding:.75rem; gap:.75rem; }
    .file-preview { height:120px; background:var(--bg-tertiary); display:flex; align-items:center; justify-content:center; overflow:hidden; position:relative; }
    .list-view .file-preview { width:48px; height:48px; border-radius:.5rem; flex-shrink:0; }
    .file-preview img, .file-preview video { width:100%; height:100%; object-fit:cover; }
    .file-info { padding:.75rem; }
    .list-view .file-info { flex:1; padding:0; min-width:0; }
    .file-name { font-size:.85rem; font-weight:700; margin-bottom:.25rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .file-meta { font-size:.7rem; color:var(--text-muted); margin-bottom:.5rem; }
    .list-view .file-meta { margin-bottom:0; }
    .file-actions { display:flex; gap:.375rem; }
    .btn-icon { width:34px; height:34px; padding:0; border-radius:.375rem; display:inline-flex; align-items:center; justify-content:center; }

    /* Toasts */
    .toast-container { position:fixed; top:calc(var(--header-height) + 70px + .5rem); right:.5rem; z-index:3000; max-width:calc(100vw - 1rem); }
    .toast { background:var(--bg-secondary); border:1px solid var(--border); border-radius:.5rem; padding:.75rem; margin-bottom:.5rem; display:flex; align-items:center; gap:.75rem; min-width:250px; max-width:350px; box-shadow:0 4px 12px var(--shadow); animation:toastIn .3s ease; }
    .toast.success { border-left:3px solid var(--success); }
    .toast.error { border-left:3px solid var(--danger); }
    .toast.warning { border-left:3px solid var(--warning); }
    .toast.info { border-left:3px solid var(--primary); }
    @keyframes toastIn { from{opacity:0; transform:translateX(100%);} to{opacity:1; transform:translateX(0);} }

    /* Modal */
    .modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,.8); backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); z-index:2000; padding:1rem; overflow-y:auto; }
    .modal.active { display:flex; align-items:center; justify-content:center; }
    .modal-content { background:var(--bg-secondary); border-radius:1rem; max-width:900px; width:100%; max-height:90vh; overflow:hidden; display:flex; flex-direction:column; animation:modalSlide .25s ease; }
    @keyframes modalSlide { from{opacity:0; transform:translateY(20px);} to{opacity:1; transform:translateY(0);} }
    .modal-header { padding:1rem; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }
    .modal-title { font-size:1rem; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .modal-close { width:28px; height:28px; border-radius:50%; background:var(--bg-tertiary); border:none; color:var(--text-primary); cursor:pointer; display:flex; align-items:center; justify-content:center; transition: transform 0.3s ease, background 0.3s ease;}
    .modal-close:hover { background: var(--danger); transform: rotate(90deg); }
    .modal-body { padding:1rem; overflow:auto; display:flex; flex-direction:column; gap:.75rem; }
    .preview-holder { display:flex; align-items:center; justify-content:center; background:var(--bg-tertiary); border:1px solid var(--border); border-radius:.5rem; min-height:240px; }
    .preview-holder img, .preview-holder video, .preview-holder audio, .preview-holder embed, .preview-holder iframe { max-width:100%; max-height:65vh; }
    .modal-footer { padding:1rem; border-top:1px solid var(--border); display:flex; gap:.5rem; justify-content:flex-end; }
    .form-input { margin-top: 5px; width: 100%; padding: 0.625rem 0.875rem; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 0.5rem; color: var(--text-primary); font-size: 0.875rem; }
    .form-input:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1); }
    .qr-box { display:flex; align-items:center; justify-content:center; padding:16px; background:#fff; border-radius:12px; }

    /* Stats */
    .stats-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:.75rem; margin-bottom:1rem; }
    .stat-card { background:linear-gradient(135deg,var(--bg-secondary), rgba(59,130,246,.05)); border:1px solid var(--border); border-radius:.75rem; padding:.875rem; display:flex; align-items:center; gap:.75rem; }
    .stat-icon { width:36px; height:36px; border-radius:.5rem; display:flex; align-items:center; justify-content:center; font-size:1rem; flex-shrink:0; }
    .stat-info { flex:1; min-width:0; }
    .stat-label { font-size:.625rem; color:var(--text-muted); margin-bottom:.125rem; }
    .stat-value { font-size:1rem; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

    /* FAB */
    .fab-container { position:fixed; bottom:1.5rem; right:1.5rem; z-index:999; }
    .fab { width:56px; height:56px; border-radius:50%; background:linear-gradient(135deg,var(--primary),var(--primary-dark)); color:white; border:none; cursor:pointer; box-shadow:0 4px 12px rgba(59,130,246,.4); display:flex; align-items:center; justify-content:center; font-size:1.25rem; }
    .fab:active { transform:scale(.95); }
    .fab-menu { position:absolute; bottom:70px; right:0; background:var(--bg-secondary); border:1px solid var(--border); border-radius:.75rem; padding:.5rem; box-shadow:0 4px 12px var(--shadow); display:none; min-width:180px; }
    .fab-menu.active { display:block; animation:fadeIn .2s ease; }
    .fab-menu-item { padding:.625rem .875rem; border-radius:.5rem; cursor:pointer; display:flex; align-items:center; gap:.75rem; font-size:.875rem; color:var(--text-primary); border:none; background:transparent; width:100%; text-align:left; }

    @media (min-width: 768px) {
      .user-badge { display:block; }
      body.with-dhikr .container { padding-top: calc(var(--header-height) + 70px + var(--desktop-padding)); }
      .container { padding:calc(var(--header-height) + var(--desktop-padding)) var(--desktop-padding) var(--desktop-padding); }
      .toolbar { flex-direction:row; justify-content:space-between; align-items:center; }
      .file-grid { grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap:1rem; }
      .file-preview { height:150px; }
      .stats-grid { grid-template-columns: repeat(4, 1fr); }
      .modal { padding:2rem; }
      .toast-container { top:calc(var(--header-height) + 70px + 1rem); right:1rem; }
    }
    @media (min-width: 1024px) { .file-grid { grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); } }
  </style>
</head>
<body class="{% if authed %}with-dhikr{% endif %}">
  <header class="header">
    <div class="header-content">
      <a class="logo" href="{{ url_for('home') }}" title="My Files">
        <i class="fas fa-shield-alt"></i><span>FileVault</span>
      </a>
      <nav class="nav-menu">
        <a class="btn btn-secondary" href="{{ url_for('home') }}" title="My Files"><i class="fas fa-home"></i></a>
        <div class="user-badge">{{ icon or "📁" }} {{ user_label }}</div>
{% if authed %}
  {% if is_admin %}
    <button class="btn btn-secondary btn-icon" id="accountsBtn" title="Accounts"><i class="fas fa-user-gear"></i></button>
    <button class="btn btn-secondary btn-icon" id="settingsBtn" title="Settings"><i class="fas fa-gear"></i></button>
  {% endif %}
  <button class="btn btn-success btn-icon" id="myQRBtn" title="My QR"><i class="fas fa-qrcode"></i></button>
  <button id="themeBtn" class="btn btn-secondary btn-icon" title="Toggle theme"><i class="fas fa-moon"></i></button>
  <a href="{{ url_for('logout') }}" class="btn btn-danger btn-icon" title="Logout"><i class="fas fa-sign-out-alt"></i></a>
{% endif %}
      </nav>
    </div>
  </header>

  {% if authed %}
  <div class="dhikr-banner" id="dhikrBanner">
    <div class="dhikr-content">
      <span class="dhikr-icon">✨</span>
      <span class="dhikr-arabic" id="dhikrArabic">{{ dhikr }}</span>
      <span class="dhikr-icon">🌟</span>
    </div>
    <button class="dhikr-refresh" onclick="changeDhikr()" title="Change Dhikr">
      <i class="fas fa-sync-alt"></i>
    </button>
  </div>
  {% endif %}

  <div class="toast-container" id="toastContainer"></div>

  <div class="container">
    {{ body|safe }}
  </div>

  <!-- Preview Modal -->
  <div class="modal" id="previewModal">
    <div class="modal-content">
      <div class="modal-header">
        <div class="modal-title" id="pvTitle">Preview</div>
        <button class="modal-close" onclick="closeModal('previewModal')" aria-label="Close"><i class="fas fa-times"></i></button>
      </div>
      <div class="modal-body">
        <div class="preview-container" style="position:relative;">
          <div class="preview-holder" id="pvMedia">Loading…</div>
          <button class="nav-arrow nav-prev" id="pvPrevBtn" style="position:absolute; left:10px; top:50%; transform:translateY(-50%); background:rgba(0,0,0,0.5); color:white; border:none; border-radius:50%; width:40px; height:40px; display:flex; align-items:center; justify-content:center; cursor:pointer;"><i class="fas fa-chevron-left"></i></button>
          <button class="nav-arrow nav-next" id="pvNextBtn" style="position:absolute; right:10px; top:50%; transform:translateY(-50%); background:rgba(0,0,0,0.5); color:white; border:none; border-radius:50%; width:40px; height:40px; display:flex; align-items:center; justify-content:center; cursor:pointer;"><i class="fas fa-chevron-right"></i></button>
        </div>
        <div class="row" style="gap:.5rem; align-items:center; margin-top:10px;">
          <button class="btn btn-primary" id="pvOpenBtn"><i class="fas fa-up-right-from-square"></i> Open</button>
          <a class="btn btn-secondary" id="pvDownloadBtn"><i class="fas fa-download"></i> Download</a>
          <button class="btn btn-secondary" id="pvCopyBtn" style="display:none;"><i class="fas fa-copy"></i> Copy Text</button>
          <button class="btn btn-secondary" id="pvShareBtn"><i class="fas fa-share"></i> Share</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Settings Modal -->
  <div class="modal" id="settingsModal">
    <div class="modal-content" style="max-width:520px;">
      <div class="modal-header">
        <div class="modal-title">Settings</div>
        <button class="modal-close" onclick="closeModal('settingsModal')" aria-label="Close"><i class="fas fa-times"></i></button>
      </div>
      <div class="modal-body" id="settingsBody">
        <div class="toggle-container">
          <span class="toggle-label">Public</span>
          <div class="toggle-switch" id="privacyToggle">
            <div class="slider"></div>
          </div>
          <span class="toggle-label">Private</span>
        </div>
        <div style="margin-top:.75rem;">
          <label class="form-label">Password (set/change when switching to Private)</label>
          <input type="password" id="privacyPassword" class="form-input" placeholder="New password">
        </div>
        <div class="toggle-container" style="margin-top: 1rem;">
          <span class="toggle-label" title="If enabled, anyone with access can delete files.">Anyone can delete</span>
          <div class="toggle-switch" id="allowDeleteToggle">
            <div class="slider"></div>
          </div>
        </div>
        <div style="margin-top:1.5rem;">
          <label class="form-label">API Token</label>
          <div class="row" style="gap:.5rem; margin-top:.5rem;">
            <input type="text" id="apiTokenInput" class="form-input" placeholder="Token will appear here" readonly style="flex:1;">
            <button class="btn btn-primary" id="generateTokenBtn"><i class="fas fa-key"></i> Generate Token</button>
            <button class="btn btn-secondary" id="shareTokenBtn" style="display:none;"><i class="fas fa-share"></i> Share</button>
          </div>
          <div style="margin-top:.5rem; color:var(--text-muted); font-size:.85rem;">Generate a non-expiring token for API access.</div>
        </div>
        <div style="margin-top:.75rem; color:var(--text-muted); font-size:.85rem;">Only the first device (admin) can change privacy.</div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeModal('settingsModal')">Close</button>
        <button class="btn btn-primary" id="saveSettingsBtn"><i class="fas fa-save"></i> Save</button>
      </div>
    </div>
  </div>

  <!-- Token Share Modal -->
  <div class="modal" id="tokenShareModal">
    <div class="modal-content" style="max-width:520px;">
      <div class="modal-header">
        <div class="modal-title">Share Access Token</div>
        <button class="modal-close" onclick="closeModal('tokenShareModal')" aria-label="Close"><i class="fas fa-times"></i></button>
      </div>
      <div class="modal-body" id="tokenShareBody">
        <div class="qr-box"><div style="color:#222;">Loading…</div></div>
        <div class="row" style="justify-content:space-between; margin-top:.75rem;">
          <div style="font-size:.85rem; color:var(--text-secondary); word-break:break-all;" id="tokenShareLink"></div>
          <button class="btn btn-secondary" id="copyTokenShareBtn"><i class="fas fa-link"></i> Copy</button>
        </div>
        <div style="margin-top:1rem; color:var(--text-muted); font-size:.85rem;">
          <p>Scan this QR code or share the link to allow others to access your server even after restarts.</p>
          <p>This token does not expire and provides full access to your files.</p>
        </div>
      </div>
    </div>
  </div>

  <!-- My QR Modal -->
  <div class="modal" id="myQRModal">
    <div class="modal-content" style="max-width:400px;">
      <div class="modal-header">
        <div class="modal-title">My QR</div>
        <button class="modal-close" onclick="closeModal('myQRModal')" aria-label="Close"><i class="fas fa-times"></i></button>
      </div>
      <div class="modal-body" id="myQRBody">
        <div class="qr-box"><div style="color:#222;">Loading…</div></div>
        <div class="row" style="justify-content:space-between; margin-top:.75rem;">
          <div style="font-size:.85rem; color:var(--text-secondary); word-break:break-all;" id="myQRLink"></div>
          <button class="btn btn-secondary" id="copyQRBtn"><i class="fas fa-link"></i> Copy</button>
        </div>
      </div>
    </div>
  </div>

<!-- Move Modal -->
<div class="modal" id="moveModal">
  <div class="modal-content" style="max-width:520px;">
    <div class="modal-header">
      <div class="modal-title">Move Items</div>
      <button class="modal-close" onclick="closeModal('moveModal')" aria-label="Close"><i class="fas fa-times"></i></button>
    </div>
    <div class="modal-body">
      <p>Select destination folder:</p>
      <div id="folderTree" style="height: 300px; overflow-y: auto; border: 1px solid var(--border); padding: .5rem; border-radius: .5rem; background: var(--bg-primary);">
        Loading...
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="closeModal('moveModal')">Cancel</button>
      <button class="btn btn-primary" id="confirmMoveBtn"><i class="fas fa-people-carry"></i> Move Here</button>
    </div>
  </div>
</div>

<!-- Accounts Modal -->
<div class="modal" id="accountsModal">
  <div class="modal-content" style="max-width:620px;">
    <div class="modal-header">
      <div class="modal-title">Accounts</div>
      <button class="modal-close" onclick="closeModal('accountsModal')" aria-label="Close"><i class="fas fa-times"></i></button>
    </div>
    <div class="modal-body" id="accountsBody">Loading…</div>
    <div class="modal-footer" style="flex-wrap:wrap; gap:.5rem;">
      <input type="text" id="accCreateNameInput" class="form-input" placeholder="Custom name (optional) e.g. lucky-duck-042" style="flex:1; min-width:220px;">
      <button class="btn btn-primary" id="accCreateBtn"><i class="fas fa-user-plus"></i> Create & Switch</button>
    </div>
  </div>
</div>

<!-- Transfer Admin Modal -->
<div class="modal" id="transferAdminModal">
  <div class="modal-content" style="max-width:520px;">
    <div class="modal-header">
      <div class="modal-title" id="transferTitle">Transfer Admin</div>
      <button class="modal-close" onclick="closeModal('transferAdminModal')" aria-label="Close"><i class="fas fa-times"></i></button>
    </div>
    <div class="modal-body" id="transferBody">
      <div class="qr-box"><div style="color:#222;">Generating…</div></div>
      <div class="row" style="justify-content:space-between; margin-top:.75rem;">
        <div style="font-size:.85rem; color:var(--text-secondary); word-break:break-all;" id="transferLink"></div>
        <button class="btn btn-secondary" id="transferCopyBtn"><i class="fas fa-link"></i> Copy</button>
      </div>
      <div style="margin-top:.5rem; color:var(--text-muted); font-size:.85rem;">
        Scan this QR from the new device to become the admin of this account. The scanning device will be logged into the account and set as default.
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="closeModal('transferAdminModal')">Close</button>
    </div>
  </div>
</div>

<!-- Rename Account Modal -->
<div class="modal" id="renameAccountModal">
  <div class="modal-content" style="max-width:520px;">
    <div class="modal-header">
      <h3 class="modal-title">Rename Account</h3>
      <button class="modal-close" onclick="closeModal('renameAccountModal')"><i class="fas fa-times"></i></button>
    </div>
    <div class="modal-body">
      <p>Renaming account: <strong id="renameAccountOldName"></strong></p>
      <div class="form-group">
        <label class="form-label">New Account Name</label>
        <input type="text" id="renameAccountInput" class="form-input" placeholder="Enter new name" autocomplete="off">
        <input type="hidden" id="renameAccountHiddenOldName">
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="closeModal('renameAccountModal')">Cancel</button>
      <button class="btn btn-primary" id="confirmRenameBtn"><i class="fas fa-save"></i> Rename</button>
    </div>
  </div>
</div>

{{SHARE_MODAL_HTML|safe}}

</div>

  <script src="/static/socket.io.min.js"></script>
  <script>
    if (typeof io === 'undefined') {
      var s = document.createElement('script');
      s.src = '/socket.io/socket.io.js';
      document.head.appendChild(s);
    }
  </script>

<script>
  // ACCOUNTS (admin)
  async function openAccounts(){
    try {
      const r = await fetch('/api/accounts', {cache:'no-store'});
      const j = await r.json();
      if(!j.ok){ showToast(j.error || 'Failed to load accounts', 'error'); return; }

      const items = (j.accounts || []).map(a => {
        const badge = a.is_default ? '<span style="font-size:.75rem; background:var(--success); color:white; padding:.125rem .375rem; border-radius:.375rem; margin-left:.5rem;">default</span>' : '';
        const privacy = a.public ? '<span style="color:var(--text-muted); font-size:.8rem;">public</span>' : '<span style="color:var(--warning); font-size:.8rem;">private</span>';
        return `
          <div class="card" style="display:flex; align-items:center; justify-content:space-between; gap:.5rem;">
            <div style="min-width:0;">
              <div style="font-weight:700; overflow:hidden; text-overflow:ellipsis;">${safeHTML(a.folder)} ${badge}</div>
              <div style="color:var(--text-muted); font-size:.8rem;">${privacy}</div>
            </div>
            <div style="display:flex; gap:.5rem;">
              <button class="btn btn-primary" onclick="switchAccount('${a.folder.replace(/'/g,"\\'")}', true)"><i class="fas fa-right-left"></i> Switch</button>
              <button class="btn btn-secondary" onclick="openRenameModal('${a.folder.replace(/'/g,"\\'")}')"><i class="fas fa-pencil-alt"></i> Rename</button>
              <button class="btn btn-secondary" onclick="openTransferAdmin('${a.folder.replace(/'/g,"\\'")}')"><i class="fas fa-key"></i> Transfer Admin</button>
            </div>
          </div>`;
      }).join('') || '<div class="card" style="color:var(--text-muted);">No accounts yet.</div>';

      document.getElementById('accountsBody').innerHTML = `
        <div style="margin-bottom:.5rem; color:var(--text-secondary);">Switching also sets it as default for this device.</div>
        ${items}
      `;

      // Button binds
      document.getElementById('accCreateBtn')?.addEventListener('click', createAccountAndSwitch);

      openModal('accountsModal');
    } catch(e){
      showToast('Failed to load accounts', 'error');
    }
  }
  document.getElementById('accountsBtn')?.addEventListener('click', openAccounts);

  async function createAccountAndSwitch(){
    const name = (document.getElementById('accCreateNameInput')?.value || '').trim();
    try {
      const r = await fetch('/api/accounts/create', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({name, make_default:true})
      });
      const j = await r.json();
      if(j.ok){
        closeModal('accountsModal');
        showToast('Account created and switched', 'success');
        setTimeout(()=> window.location = j.browse_url, 300);
      } else {
        showToast(j.error || 'Failed to create', 'error');
      }
    } catch(e){
      showToast('Failed to create', 'error');
    }
  }

  async function switchAccount(folder, makeDefault=true){
    try {
      const r = await fetch('/api/accounts/switch', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({folder, make_default: makeDefault})
      });
      const j = await r.json();
      if(j.ok){
        closeModal('accountsModal');
        showToast('Switched', 'success');
        setTimeout(()=> window.location = j.browse_url, 200);
      } else {
        showToast(j.error || 'Failed to switch', 'error');
      }
    } catch(e){
      showToast('Failed to switch', 'error');
    }
  }

  // TRANSFER ADMIN (QR)
  async function openTransferAdmin(folder){
    try {
      const r = await fetch('/api/accounts/transfer_admin_start', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({folder})
      });
      const j = await r.json();
      if(j.ok){
        document.getElementById('transferTitle').textContent = `Transfer Admin: ${folder}`;
        document.getElementById('transferBody').innerHTML = `
          <div class="qr-box"><img src="data:image/png;base64,${j.b64}" alt="QR" style="image-rendering:pixelated; image-rendering:crisp-edges;"/></div>
          <div class="row" style="justify-content:space-between; margin-top:.75rem;">
            <div style="font-size:.85rem; color:var(--text-secondary); word-break:break-all;" id="transferLink">${j.url}</div>
            <button class="btn btn-secondary" id="transferCopyBtn"><i class="fas fa-link"></i> Copy</button>
          </div>
          <div style="margin-top:.5rem; color:var(--text-muted); font-size:.85rem;">
            Scan this QR from the new device to become the admin of this account. The scanning device will be logged in and set as default.
          </div>
        `;
        document.getElementById('transferCopyBtn')?.addEventListener('click', ()=> copyLink(j.url));
        openModal('transferAdminModal');
      } else {
        showToast(j.error || 'Failed to start transfer', 'error');
      }
    } catch(e){
      showToast('Failed to start transfer', 'error');
    }
  }

    function openRenameModal(oldName) {
        document.getElementById('renameAccountOldName').textContent = oldName;
        document.getElementById('renameAccountHiddenOldName').value = oldName;
        document.getElementById('renameAccountInput').value = '';
        openModal('renameAccountModal');
        setTimeout(()=> document.getElementById('renameAccountInput').focus(), 50);
    }

    async function confirmRename() {
        const oldName = document.getElementById('renameAccountHiddenOldName').value;
        const newName = document.getElementById('renameAccountInput').value.trim();

        if (!newName) {
            showToast('Please enter a new name.', 'warning');
            return;
        }

        try {
            const r = await fetch('/api/accounts/rename', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ old_name: oldName, new_name: newName })
            });
            const j = await r.json();
            if (j.ok) {
                showToast('Account renamed!', 'success');
                closeModal('renameAccountModal');
                openAccounts();
                const currentFolder = {{ session.get('folder', '')|tojson }};
                if (currentFolder === oldName) {
                    setTimeout(()=> window.location.href = window.location.pathname.replace('/b/' + oldName, '/b/' + newName), 300);
                }
            } else {
                showToast(j.error || 'Rename failed.', 'error');
            }
        } catch (e) {
            showToast('An error occurred during rename.', 'error');
        }
    }
</script>

  <script>
    'use strict';

    let selectModeActive = false;
    let selectedFiles = new Set();
    let lastSelectedIndex = -1;

    function handleSelectionChange(){
        selectedFiles = new Set(Array.from(document.querySelectorAll('.file-select-checkbox:checked')).map(cb => cb.dataset.rel));

        document.querySelectorAll('.file-card').forEach(card => {
            const cb = card.querySelector('.file-select-checkbox');
            if(cb && selectedFiles.has(cb.dataset.rel)){
                card.classList.add('selected');
                cb.checked = true;
            } else {
                card.classList.remove('selected');
                if(cb) cb.checked = false;
            }
        });

        const bulkToolbar = document.getElementById('bulkActionsToolbar');
        if (bulkToolbar) {
            if(selectedFiles.size > 0){
                bulkToolbar.style.display = 'flex';
                document.getElementById('selectionCount').textContent = `${selectedFiles.size} selected`;
            } else {
                bulkToolbar.style.display = 'none';
                if (selectModeActive) {
                    toggleSelectMode(false);
                }
            }
        }
    }

    function toggleSelectMode(forceState) {
        selectModeActive = (forceState === undefined) ? !selectModeActive : forceState;
        document.body.classList.toggle('select-mode', selectModeActive);

        if (!selectModeActive) {
            // Clear selection when exiting mode
            document.querySelectorAll('.file-select-checkbox:checked').forEach(cb => {
                cb.checked = false;
            });
            handleSelectionChange();
        }
    }

    // Dhikr data
    const dhikrList = {{ dhikr_list|tojson }};

async function changeDhikr() {
  try {
    const response = await fetch('/api/dhikr');
    const data = await response.json();

    if (data.dhikr) {
      const dhikrEl = document.getElementById('dhikrArabic');
      const banner = document.getElementById('dhikrBanner');

      if (dhikrEl) {
        dhikrEl.textContent = data.dhikr;
      }
      if (banner) {
        banner.style.animation = 'none';
        setTimeout(() => { banner.style.animation = 'slideDown 0.5s ease'; }, 10);
      }
    }
  } catch (e) {
    if (Array.isArray(dhikrList) && dhikrList.length > 0) {
      const randomDhikr = dhikrList[Math.floor(Math.random() * dhikrList.length)];
      const dhikrEl = document.getElementById('dhikrArabic');
      if (dhikrEl) {
        dhikrEl.textContent = randomDhikr.dhikr;
      }
    }
  }
}


    setInterval(changeDhikr, 30000);


  // THEME + PREFS

  const root = document.documentElement;

  async function savePref(key, value){
    try { await fetch('/api/prefs', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key, value})}); } catch(e){}
  }

  function updateThemeBtnIcon(t){
    const btn = document.getElementById('themeBtn');
    if(!btn) return;
    btn.innerHTML = t === 'barbie' ? '<i class="fas fa-heart"></i>'
                  : t === 'light' ? '<i class="fas fa-sun" style=" color: yellow; "></i>'
                  : '<i class="fas fa-moon"></i>';
  }

  function applyTheme(t, opts={save:true}){
    root.classList.remove('light','barbie');
    if(t && t !== 'dark') root.classList.add(t);
    if(opts.save){
      try { localStorage.setItem('theme', t); } catch(e){}
      savePref('theme', t);
    }
    updateThemeBtnIcon(t || 'dark');
  }

  function getStartupTheme(){
    try { const t = localStorage.getItem('theme'); if(t) return t; } catch(e){}
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }

  function toggleTheme(){
    const seq = ['dark','light','barbie'];
    const cur = root.classList.contains('barbie') ? 'barbie'
              : root.classList.contains('light') ? 'light'
              : (localStorage.getItem('theme') || 'dark');
    const next = seq[(seq.indexOf(cur) + 1) % seq.length];
    applyTheme(next, {save:true});
  }

  document.getElementById('themeBtn')?.addEventListener('click', toggleTheme);

  (async ()=>{
    try {
      const r = await fetch('/api/prefs');
      const j = await r.json();
      const saved = j?.prefs?.theme;
      if(saved){ applyTheme(saved, {save:false}); }
      else { applyTheme(getStartupTheme(), {save:false}); }
    } catch(e){
      applyTheme(getStartupTheme(), {save:false});
    }
  })();

     // TOASTS
    function showToast(message, type='info'){
      const container = document.getElementById('toastContainer'); if(!container) return;
      const toast = document.createElement('div'); toast.className = `toast ${type}`;
      const icon = {success:'fa-check-circle', error:'fa-times-circle', warning:'fa-exclamation-triangle', info:'fa-info-circle'}[type] || 'fa-info-circle';
      toast.innerHTML = `<i class="fas ${icon}"></i><div class="toast-message">${message}</div>`;
      container.appendChild(toast);
      setTimeout(()=>{ toast.style.opacity='0'; setTimeout(()=>toast.remove(), 300); }, 3000);
      changeDhikr();
    }

    // MODALS
    function openModal(id){ const m = document.getElementById(id); if(m){ m.classList.add('active'); } }
    function closeModal(id){
      const m = document.getElementById(id);
      if(m){
        m.classList.remove('active');

        // Remove keyboard event listener when preview modal is closed
        if (id === 'previewModal') {
          document.removeEventListener('keydown', handlePreviewKeydown);
        }
      }
    }
    document.addEventListener('click', (e)=>{ if(e.target.classList.contains('modal')) e.target.classList.remove('active'); });
    document.addEventListener('keydown', (e)=>{
      // Check if the preview modal is active and has its own keydown handler
      const previewModalActive = document.getElementById('previewModal')?.classList.contains('active');

      // If we're in the preview modal, let the specific handler manage keyboard events
      if (previewModalActive && (e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key === 'Escape')) {
        // Don't process these keys in the global handler when preview is active
        return;
      }

      if (e.key === 'a' && (e.ctrlKey || e.metaKey)) {
        if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') {
            return;
        }
        e.preventDefault();
        if (!selectModeActive) {
            toggleSelectMode(true);
        }
        document.querySelectorAll('.file-card:not([style*="display: none"]) .file-select-checkbox').forEach(cb => {
            cb.checked = true;
        });
        handleSelectionChange();
      }

      if(e.key === 'Escape'){
        if (selectModeActive) {
            toggleSelectMode(false);
        } else {
            document.querySelectorAll('.modal.active').forEach(m=>{
              closeModal(m.id);
            });
        }
      }
    });

    // VIEW MODE + PREF
    let currentView = localStorage.getItem('fileView') || 'list';
    async function setView(view){
      currentView = view; localStorage.setItem('fileView', view);
      const grid = document.getElementById('fileGrid'); if(grid){ grid.classList.toggle('list-view', view === 'list'); }
      document.querySelectorAll('.view-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.view === view));
      applySort();
      savePref('view', view);
    }

    // SEARCH
    function searchFiles(){
      const q = (document.getElementById('searchInput')?.value || '').toLowerCase();
      document.querySelectorAll('.file-card').forEach(card=>{
        const name = (card.dataset.name || '').toLowerCase();
        card.style.display = name.includes(q) ? '' : 'none';
      });
    }

    // SORTING
    function getSortPrefs(){
      return {
        by: localStorage.getItem('sortBy') || 'date',
        dir: localStorage.getItem('sortDir') || 'desc',
        foldersFirst: localStorage.getItem('foldersFirst') !== 'false'
      };
    }
    function setSortPrefs(by, dir, foldersFirst){
      if(by) localStorage.setItem('sortBy', by);
      if(dir) localStorage.setItem('sortDir', dir);
      if(typeof foldersFirst === 'boolean') localStorage.setItem('foldersFirst', String(foldersFirst));
    }
    function applySort(){
      const grid = document.getElementById('fileGrid'); if(!grid) return;
      const prefs = getSortPrefs();
      const cards = Array.from(grid.children).filter(el => el.classList?.contains('file-card'));
      const withIndex = cards.map((el, idx) => ({el, idx}));
      const cmp = (a, b) => {
        const ad = a.el.dataset, bd = b.el.dataset;
        const aDir = ad.isDir === '1', bDir = bd.isDir === '1';
        if(prefs.foldersFirst && aDir !== bDir) return aDir ? -1 : 1;

        let av, bv;
        switch(prefs.by){
          case 'size': av = parseInt(ad.size || '0', 10); bv = parseInt(bd.size || '0', 10); break;
          case 'type': av = (ad.mime || '').toLowerCase(); bv = (bd.mime || '').toLowerCase(); break;
          case 'date': av = parseInt(ad.mtime || '0', 10); bv = parseInt(bd.mtime || '0', 10); break;
          case 'name':
          default: av = (ad.name || '').toLowerCase(); bv = (bd.name || '').toLowerCase(); break;
        }
        let result = 0;
        if(av < bv) result = -1;
        else if(av > bv) result = 1;
        else result = a.idx - b.idx;
        return prefs.dir === 'asc' ? result : -result;
      };
      withIndex.sort(cmp);
      withIndex.forEach(({el}) => grid.appendChild(el));
      const sortBy = document.getElementById('sortBy'); if(sortBy) sortBy.value = prefs.by;
      const sortDir = document.getElementById('sortDir'); if(sortDir) sortDir.dataset.dir = prefs.dir, sortDir.innerHTML = prefs.dir === 'asc' ? '<i class="fas fa-arrow-up-wide-short"></i>' : '<i class="fas fa-arrow-down-wide-short"></i>';
      const ff = document.getElementById('foldersFirst'); if(ff) ff.checked = prefs.foldersFirst;
    }

    // UPLOADS
    const activeXHRs = new Map();

    function initUploadArea(){
      const area = document.getElementById('uploadArea');
      const input = document.getElementById('uploadInput');
      if(!area || !input) return;

      ['dragenter','dragover','dragleave','drop'].forEach(ev=>{
        area.addEventListener(ev, e=>{ e.preventDefault(); e.stopPropagation(); }, false);
        document.addEventListener(ev, e=>{ e.preventDefault(); e.stopPropagation(); }, false);
      });
      area.addEventListener('dragenter', ()=> area.classList.add('dragover'));
      area.addEventListener('dragleave', ()=> area.classList.remove('dragover'));
      area.addEventListener('drop', e=>{
        area.classList.remove('dragover');
        const files = e.dataTransfer.files; if(files?.length) handleNewFiles(files);
      });

      input.addEventListener('change', e=>{
        const files = e.target.files; if(files?.length){ handleNewFiles(files); }
        input.value = '';
      }, false);
    }

    function handleNewFiles(files){
      const arr = Array.from(files || []);
      if(!arr.length) return;
      const container = document.getElementById('progressContainer');
      if(container) container.innerHTML = '';
      for(const f of arr){
        const id = `up-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        uploadSingleFile({file:f, id});
      }
    }

    function createProgressElement(filename, id){
      const div = document.createElement('div');
      div.className = 'progress-item';
      div.dataset.uploadId = id;
      div.innerHTML = `
        <div class="progress-header">
          <div class="progress-info">
            <div class="progress-filename">${filename}</div>
            <div class="progress-stats"><span class="stat-speed">0 B/s</span><span class="stat-eta">Starting…</span></div>
          </div>
          <div class="progress-actions">
            <span class="progress-percent">0%</span>
            <button class="progress-cancel" title="Cancel upload"><i class="fas fa-times"></i></button>
          </div>
        </div>
        <div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div>
      `;
      div.querySelector('.progress-cancel').addEventListener('click', ()=> cancelUpload(id));
      return div;
    }

    function formatSpeed(bps){
      if(!bps || !isFinite(bps)) return "0 B/s";
      const units = ['B/s','KB/s','MB/s','GB/s']; let u=0; let s=bps;
      while(s>=1024 && u<units.length-1){ s/=1024; u++; }
      return `${s.toFixed(u?1:0)} ${units[u]}`;
    }
    function formatETA(sec){
      if(!isFinite(sec) || sec<=0) return '...';
      if(sec<60) return `${Math.round(sec)}s`;
      const m = Math.floor(sec/60), s=Math.round(sec%60);
      return `${m}m ${s}s`;
    }

    function updateProgress(element, data){
      if(!element) return;
      element.querySelector('.progress-fill').style.width = `${data.percent}%`;
      element.querySelector('.progress-percent').textContent = `${Math.round(data.percent)}%`;
      element.querySelector('.stat-speed').textContent = formatSpeed(data.speed);
      element.querySelector('.stat-eta').textContent = data.percent >= 100 ? 'Done' : formatETA(data.eta);
    }
    function markProgressComplete(element, success){
      if(!element) return;
      element.classList.add(success ? 'completed' : 'error');
      const btn = element.querySelector('.progress-cancel'); if(btn){ btn.disabled = true; btn.style.opacity = .5; }
      setTimeout(()=>{ element.remove(); }, 900);
    }

    function uploadSingleFile(item){
      const {file, id} = item;
      const container = document.getElementById('progressContainer');
      const row = createProgressElement(file.name, id);
      container?.appendChild(row);

      const form = new FormData();
      form.append('dest', window.currentPath || '');
      form.append('file', file, file.name);

      const xhr = new XMLHttpRequest();
      activeXHRs.set(id, xhr);

      const start = Date.now();
      xhr.upload.addEventListener('progress', e=>{
        if(e.lengthComputable){
          const percent = (e.loaded/e.total) * 100;
          const seconds = Math.max(0.25, (Date.now()-start)/1000);
          const speed = e.loaded/seconds;
          const eta = (e.total-e.loaded) / Math.max(speed, 1);
          updateProgress(row, {percent, speed, eta});
        }
      });
      xhr.addEventListener('load', ()=>{
        activeXHRs.delete(id);
        try {
          const j = JSON.parse(xhr.responseText || '{}');
          if(xhr.status >= 200 && xhr.status < 300 && j.ok){
            markProgressComplete(row, true);
            showToast(`Uploaded: ${file.name}`, 'success');
          } else {
            markProgressComplete(row, false);
            showToast(`Failed: ${file.name}`, 'error');
          }
        } catch(e){
          if(xhr.status >= 200 && xhr.status < 300){
            markProgressComplete(row, true);
            showToast(`Uploaded: ${file.name}`, 'success');
          } else {
            markProgressComplete(row, false);
            showToast(`Failed: ${file.name}`, 'error');
          }
        }
      });
      xhr.addEventListener('error', ()=>{
        activeXHRs.delete(id);
        markProgressComplete(row, false);
        showToast(`Failed: ${file.name}`, 'error');
      });
      xhr.addEventListener('abort', ()=>{
        activeXHRs.delete(id);
        row.remove();
      });

      xhr.open('POST', '{{ url_for("api_upload") }}');
      xhr.send(form);
    }

    function cancelUpload(id){
      const xhr = activeXHRs.get(id);
      if(xhr){ xhr.abort(); activeXHRs.delete(id); }
      const el = document.querySelector(`[data-upload-id="${id}"]`);
      if(el){ el.remove(); }
    }

    // SHARE / COPY
    function shareFile(rel){
      const rawUrl = `${window.location.origin}{{ url_for('raw') }}?path=${encodeURIComponent(rel)}`;
      if(navigator.share && /mobile|android|iphone/i.test(navigator.userAgent)){
        navigator.share({title:'Shared File', url:rawUrl}).catch(()=> copyLink(rawUrl));
      } else {
        copyLink(rawUrl);
      }
    }
    function copyLink(url){
      try {
        if(navigator.clipboard){
          navigator.clipboard.writeText(url)
            .then(() => showToast('Link copied!', 'success'))
            .catch(err => {
              console.error('Clipboard API error:', err);
              fallbackCopy();
            });
        } else {
          fallbackCopy();
        }
        
        function fallbackCopy() {
          try {
            const i = document.createElement('input');
            i.value = url;
            i.style.position = 'fixed';
            i.style.opacity = '0';
            document.body.appendChild(i);
            i.select();
            const successful = document.execCommand('copy');
            document.body.removeChild(i);
            
            if (successful) {
              showToast('Link copied!', 'success');
            } else {
              showToast('Failed to copy link', 'error');
            }
          } catch (err) {
            console.error('Fallback copy error:', err);
            showToast('Failed to copy link', 'error');
          }
        }
      } catch (e) {
        console.error('Copy error:', e);
        showToast('Failed to copy link', 'error');
      }
    }

    // PREVIEW (pointerup to avoid double-tap; throttle duplicates)
    let lastPreviewAt = 0;
    let _pvTextCache = '';
    function handleCardOpenEvent(e){
      const card = e.target.closest('.file-card'); if(!card) return;

      if (e.target.closest('.file-actions')) return;

      if (selectModeActive) {
        const allCards = Array.from(document.querySelectorAll('.file-card:not([style*="display: none"])'));
        const currentIndex = allCards.indexOf(card);
        const checkbox = card.querySelector('.file-select-checkbox');
        if (!checkbox) return;

        if (e.shiftKey && lastSelectedIndex !== -1) {
            const start = Math.min(lastSelectedIndex, currentIndex);
            const end = Math.max(lastSelectedIndex, currentIndex);
            // First, uncheck everything to handle complex shift-click scenarios
            allCards.forEach(c => {
                const cb = c.querySelector('.file-select-checkbox');
                if(cb) cb.checked = false;
            });
            // Then, check the items in the range
            allCards.forEach((c, index) => {
                if (index >= start && index <= end) {
                    const cb = c.querySelector('.file-select-checkbox');
                    if(cb) cb.checked = true;
                }
            });
        } else {
            checkbox.checked = !checkbox.checked;
        }

        lastSelectedIndex = currentIndex;
        handleSelectionChange();
        return;
      }

      const now = Date.now();
      if(now - lastPreviewAt < 250) return;
      lastPreviewAt = now;

      const isDir = card.dataset.isDir === '1';
      const rel = card.dataset.rel, name = card.dataset.name, mime = card.dataset.mime, raw = card.dataset.raw, dl = card.dataset.dl;
      if(isDir){ window.location = "{{ url_for('browse') }}/" + rel; }
      else { openPreview(rel, name, mime, raw, dl); }
    }

    let selectedDestination = '';
    function renderFolderTree(nodes, level = 0) {
        let html = '';
        for (const node of nodes) {
            html += `
                <div class="folder-tree-item" data-path="${node.path}" style="padding-left: ${level * 20}px;">
                    <i class="fas fa-folder"></i> ${node.name}
                </div>
            `;
            if (node.children && node.children.length > 0) {
                html += renderFolderTree(node.children, level + 1);
            }
        }
        return html;
    }
    async function openMoveModal() {
        if (selectedFiles.size === 0) {
            showToast('Please select files to move.', 'warning');
            return;
        }
        openModal('moveModal');
        const folderTreeDiv = document.getElementById('folderTree');
        folderTreeDiv.innerHTML = 'Loading...';

        try {
            const response = await fetch('/api/folders');
            const data = await response.json();
            if (data.ok) {
                folderTreeDiv.innerHTML = renderFolderTree(data.tree);
                selectedDestination = ''; // Reset selection
                document.getElementById('confirmMoveBtn').disabled = true;

                document.querySelectorAll('.folder-tree-item').forEach(item => {
                    item.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const destinationPath = item.dataset.path;
                        for (const sourcePath of selectedFiles) {
                            if (sourcePath === destinationPath || destinationPath.startsWith(sourcePath + '/')) {
                                showToast('Cannot move a folder into itself.', 'error');
                                item.classList.add('invalid');
                                setTimeout(()=> item.classList.remove('invalid'), 500);
                                return;
                            }
                        }
                        document.querySelectorAll('.folder-tree-item').forEach(i => i.classList.remove('selected'));
                        item.classList.add('selected');
                        selectedDestination = destinationPath;
                        document.getElementById('confirmMoveBtn').disabled = false;
                    });
                });
            } else {
                folderTreeDiv.innerHTML = `Error: ${data.error || 'Could not load folders.'}`;
            }
        } catch (error) {
            folderTreeDiv.innerHTML = 'Error loading folders.';
        }
    }
    async function confirmMove() {
        if (selectedDestination === '' || selectedDestination === null) {
            showToast('Please select a destination folder.', 'warning');
            return;
        }

        const sources = Array.from(selectedFiles);
        try {
            const r = await fetch('/api/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sources, destination: selectedDestination })
            });
            const j = await r.json();
            if (j.ok) {
                showToast('Items moved successfully!', 'success');
                if(j.errors && j.errors.length > 0){
                    j.errors.forEach(err => showToast(`Error moving ${err.path}: ${err.error}`, 'error'));
                }
                // The socket events will handle the removal of old cards and addition of new ones.
                // We just need to clear the selection.
                toggleSelectMode(false); // This will clear selection and hide toolbar
            } else {
                showToast(j.error || 'Move failed.', 'error');
            }
        } catch (e) {
            showToast('An error occurred during the move.', 'error');
        }
        closeModal('moveModal');
    }
    async function confirmBulkDelete() {
        if (selectedFiles.size === 0) { return; }
        if (!confirm(`Are you sure you want to delete ${selectedFiles.size} item(s)?`)) { return; }

        const sources = Array.from(selectedFiles);
        try {
            const r = await fetch('{{ url_for("api_delete") }}', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ files: sources })
            });
            const j = await r.json();
            if (j.ok) {
                showToast(`${j.deleted.length} item(s) deleted.`, 'success');
                toggleSelectMode(false); // This will clear selection and hide toolbar
            } else {
                showToast(j.error || 'Delete failed.', 'error');
            }
        } catch (e) {
            showToast('An error occurred during deletion.', 'error');
        }
    }

    // PWA SHARE HANDLING
    let selectedShareDestination = '';
    let currentPendingFile = null;

    async function checkForPendingShares(){
        try {
            const r = await fetch('/api/pending_shares');
            const j = await r.json();
            if(j.ok && j.files && j.files.length > 0){
                if (!document.getElementById('shareModal').classList.contains('active')) {
                    currentPendingFile = j.files[0];
                    openShareModal(currentPendingFile);
                }
            }
        } catch(e) {
            console.error('Failed to check for pending shares', e);
        }
    }

    async function openShareModal(file) {
        if (!file) return;
        document.getElementById('shareFileName').textContent = file.name;

        const folderTreeDiv = document.getElementById('shareFolderTree');
        folderTreeDiv.innerHTML = 'Loading...';
        openModal('shareModal');

        try {
            const response = await fetch('/api/folders');
            const data = await response.json();
            if (data.ok) {
                folderTreeDiv.innerHTML = renderFolderTree(data.tree);
                selectedShareDestination = '';
                const confirmBtn = document.getElementById('confirmShareBtn');
                if(confirmBtn) confirmBtn.disabled = true;

                document.querySelectorAll('#shareFolderTree .folder-tree-item').forEach(item => {
                    item.addEventListener('click', (e) => {
                        e.stopPropagation();
                        document.querySelectorAll('#shareFolderTree .folder-tree-item').forEach(i => i.classList.remove('selected'));
                        item.classList.add('selected');
                        selectedShareDestination = item.dataset.path;
                        if(confirmBtn) confirmBtn.disabled = false;
                    });
                });
            } else {
                folderTreeDiv.innerHTML = `Error: ${data.error || 'Could not load folders.'}`;
            }
        } catch (error) {
            folderTreeDiv.innerHTML = 'Error loading folders.';
        }
    }

    async function confirmShare() {
        if (!currentPendingFile || selectedShareDestination === '') {
            showToast('Please select a destination folder.', 'warning');
            return;
        }

        try {
            const r = await fetch('/api/commit_share', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: currentPendingFile.id, destination: selectedShareDestination })
            });
            const j = await r.json();
            if (j.ok) {
                showToast(`File '${j.meta.name}' saved successfully!`, 'success');
            } else {
                showToast(j.error || 'Share failed.', 'error');
            }
        } catch (e) {
            showToast('An error occurred during the share.', 'error');
        }
        closeModal('shareModal');
        currentPendingFile = null;

        setTimeout(checkForPendingShares, 500);
    }

    async function bulkDownload() {
        if (selectedFiles.size === 0) { return; }
        const sources = Array.from(selectedFiles);
        try {
            const r = await fetch('/api/download_zip', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ files: sources })
            });

            if (r.ok) {
                const blob = await r.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = r.headers.get('Content-Disposition')?.split('filename=')[1]?.replace(/"/g, '') || 'download.zip';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
            } else {
                const j = await r.json();
                showToast(j.error || 'Download failed.', 'error');
            }
        } catch (e) {
            showToast('An error occurred during download.', 'error');
        }
    }

    function initBulkActions(){
        document.getElementById('bulkMoveBtn')?.addEventListener('click', openMoveModal);
        document.getElementById('confirmMoveBtn')?.addEventListener('click', confirmMove);
        document.getElementById('bulkDeleteBtn')?.addEventListener('click', confirmBulkDelete);
        document.getElementById('bulkDownloadBtn')?.addEventListener('click', bulkDownload);
        document.getElementById('deselectAllBtn')?.addEventListener('click', () => toggleSelectMode(false));
    }

    function initFileGrid() {
        const grid = document.getElementById('fileGrid');
        if (!grid) return;

        let pressTimer = null;
        let startX, startY;
        let isLongPress = false;

        grid.addEventListener('pointerdown', (e) => {
            if (e.button !== 0) return;
            const card = e.target.closest('.file-card');
            if (!card || e.target.closest('.file-actions')) return;

            startX = e.clientX;
            startY = e.clientY;
            isLongPress = false;

            pressTimer = setTimeout(() => {
                isLongPress = true;
                pressTimer = null;

                toggleSelectMode(true);
                const checkbox = card.querySelector('.file-select-checkbox');
                if (checkbox) {
                    checkbox.checked = true;
                    handleSelectionChange();
                }
                if (navigator.vibrate) navigator.vibrate(50);

            }, 500);
        });

        grid.addEventListener('pointermove', (e) => {
            if (!pressTimer) return;
            if (Math.abs(e.clientX - startX) > 10 || Math.abs(e.clientY - startY) > 10) {
                clearTimeout(pressTimer);
                pressTimer = null;
            }
        });

        grid.addEventListener('pointerup', (e) => {
            if (pressTimer) {
                clearTimeout(pressTimer);
                pressTimer = null;
            }

            if (isLongPress) {
                // If it was a long press, we've already handled the selection.
                // We just need to prevent the browser from firing a 'click' event,
                // which would toggle the selection off again.
                e.preventDefault();
            } else {
                // Otherwise, it's a normal click/tap, so open the file or select it.
                handleCardOpenEvent(e);
            }
        });

        if (!window.PointerEvent) {
            grid.addEventListener('click', handleCardOpenEvent);
        }

        document.getElementById('pvPrevBtn')?.addEventListener('click', () => navigateToFile('prev'));
        document.getElementById('pvNextBtn')?.addEventListener('click', () => navigateToFile('next'));
    }


    // PREVIEW modal
    let currentFileIndex = -1;
    let filesList = [];

    function isTextLike(mime){
      if(!mime) return false;
      mime = mime.toLowerCase();
      return mime.startsWith('text/') || ['application/json','application/xml','application/javascript','application/x-javascript'].includes(mime);
    }

    function loadFilesList() {
      // Get all file cards from the grid
      const fileCards = document.querySelectorAll('.file-card');
      filesList = [];

      fileCards.forEach(card => {
        if(card.dataset.isDir !== '1') { // Only include files, not directories
          filesList.push({
            rel: card.dataset.rel,
            name: card.dataset.name,
            mime: card.dataset.mime,
            raw: card.dataset.raw,
            dl: card.dataset.dl
          });
        }
      });
    }



// The buggy global keydown listener below was removed to fix a TypeError.
// It was attempting to access properties on `pvModal` which could be null
// on pages where the preview modal does not exist (e.g., the login page),
// causing a "Cannot read properties of null (reading 'classList')" error.
// The correct keyboard handling for the preview modal is managed by the
// `handlePreviewKeydown` function, which is dynamically added and removed.


    function openPreview(rel, name, mime, rawUrl, downloadUrl){
      console.log('Opening preview for:', name);

      // Always reload the files list to ensure it's up to date
      loadFilesList();
      console.log('Files list loaded, length:', filesList.length);

      // Find current file index
      currentFileIndex = filesList.findIndex(file => file.rel === rel);
      console.log('Current file index:', currentFileIndex);

      document.getElementById('pvTitle').textContent = name;
      const box = document.getElementById('pvMedia');
      box.innerHTML = 'Loading…';

      const copyBtn = document.getElementById('pvCopyBtn');
      copyBtn.style.display = 'none';
      _pvTextCache = '';

      document.getElementById('pvOpenBtn').onclick = ()=> window.open(rawUrl, '_blank');
      const dl = document.getElementById('pvDownloadBtn'); dl.href = downloadUrl; dl.setAttribute('download', name);
      document.getElementById('pvShareBtn').onclick = ()=> shareFile(rel);

      // Update navigation buttons visibility
      updateNavButtons();

      // First remove any existing keyboard event listener to prevent duplicates
      document.removeEventListener('keydown', handlePreviewKeydown);

      // Use setTimeout to ensure the event listener is added after the modal is fully opened
      setTimeout(() => {
        // Then add keyboard event listener
        document.addEventListener('keydown', handlePreviewKeydown);
        console.log('Preview keyboard navigation enabled');
      }, 100);

      // Add a click event listener to the modal to ensure focus
      const modal = document.getElementById('previewModal');
      if (modal) {
        modal.addEventListener('click', function(e) {
          // Only handle clicks on the modal background, not its contents
          if (e.target === modal) {
            // Refocus the modal to ensure keyboard events work
            modal.focus();
          }
        });
      }

      if(mime.startsWith('image/')){
        box.innerHTML = `<img src="${rawUrl}" alt="${name}">`;
      } else if(mime.startsWith('video/')){
        box.innerHTML = `<video src="${rawUrl}" controls preload="metadata" style="max-width:100%;"></video>`;
      } else if(mime.startsWith('audio/')){
        box.innerHTML = `<audio src="${rawUrl}" controls preload="metadata" style="width:100%;"></audio>`;
      } else if(mime === 'application/pdf'){
        box.innerHTML = `<embed src="${rawUrl}" type="application/pdf" style="width:100%; height:65vh;">`;
      } else if(isTextLike(mime)){
        box.innerHTML = `<pre style="white-space:pre-wrap; padding:.75rem; width:100%; max-height:65vh; overflow:auto;">Loading…</pre>`;
        fetch(rawUrl, {cache:'no-store'}).then(r=>r.text()).then(t=>{
          _pvTextCache = t;
          box.querySelector('pre').textContent = t;
          copyBtn.style.display = 'inline-flex';
          copyBtn.onclick = ()=>{
            if(navigator.clipboard){ navigator.clipboard.writeText(_pvTextCache).then(()=> showToast('Copied to clipboard','success')); }
            else { const i=document.createElement('textarea'); i.value=_pvTextCache; document.body.appendChild(i); i.select(); document.execCommand('copy'); i.remove(); showToast('Copied!','success'); }
          };
        }).catch(()=>{ box.querySelector('pre').textContent = 'Cannot preview'; });
      } else {
        box.innerHTML = `<div style="padding:.75rem; text-align:center;">No inline preview available. Use Open or Download.</div>`;
      }
      openModal('previewModal');
    }

    function updateNavButtons() {
      const prevBtn = document.getElementById('pvPrevBtn');
      const nextBtn = document.getElementById('pvNextBtn');

      if (filesList.length <= 1) {
        // Hide both buttons if there's only one file or no files
        prevBtn.style.display = 'none';
        nextBtn.style.display = 'none';
        return;
      }

      // Show/hide previous button based on current index
      prevBtn.style.display = currentFileIndex > 0 ? 'flex' : 'none';

      // Show/hide next button based on current index
      nextBtn.style.display = currentFileIndex < filesList.length - 1 ? 'flex' : 'none';
    }

    function navigateToFile(direction) {
      console.log('Navigating', direction, 'Current index:', currentFileIndex, 'Files list length:', filesList.length);

      // Reload the files list to ensure it's up to date
      loadFilesList();

      if (filesList.length <= 1) {
        console.log('Cannot navigate: not enough files');
        return;
      }

      let newIndex = currentFileIndex;
      if (direction === 'prev' && currentFileIndex > 0) {
        newIndex = currentFileIndex - 1;
        console.log('Moving to previous file, new index:', newIndex);
      } else if (direction === 'next' && currentFileIndex < filesList.length - 1) {
        newIndex = currentFileIndex + 1;
        console.log('Moving to next file, new index:', newIndex);
      } else {
        console.log('Cannot navigate further in this direction');
        return; // Can't navigate further
      }

      const file = filesList[newIndex];
      if (!file) {
        console.error('File not found at index:', newIndex);
        return;
      }

      console.log('Navigating to file:', file.name, 'Data:', file);

      // Use setTimeout to ensure the event handling is complete before opening the new preview
      setTimeout(() => {
        openPreview(file.rel, file.name, file.mime, file.raw, file.dl);
      }, 10);
    }



    // Handle keyboard navigation in preview modal
    function handlePreviewKeydown(e) {
      console.log('Keydown event detected:', e.key, e.keyCode);

      // Only process if preview modal is open
      const previewModal = document.getElementById('previewModal');
      if (!previewModal || !previewModal.classList.contains('active')) {
        console.log('Preview modal not active, removing listener');
        document.removeEventListener('keydown', handlePreviewKeydown);
        return;
      }

      // Left arrow key - previous file
      if (e.key === 'ArrowLeft' || e.keyCode === 37) {
        console.log('Left arrow pressed - navigating to previous file');
        e.preventDefault();
        e.stopPropagation();
        navigateToFile('prev');
      }
      // Right arrow key - next file
      else if (e.key === 'ArrowRight' || e.keyCode === 39) {
        console.log('Right arrow pressed - navigating to next file');
        e.preventDefault();
        e.stopPropagation();
        navigateToFile('next');
      }
      // Escape key - close modal
      else if (e.key === 'Escape' || e.keyCode === 27) {
        console.log('Escape pressed - closing preview modal');
        e.preventDefault();
        closeModal('previewModal');
      }
    }

    // DELETE
    function deleteFile(rel){
      if(!confirm('Delete this item?')) return;
      fetch('{{ url_for("api_delete") }}', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({files:[rel]})})
        .then(r=>r.json()).then(j=>{
          if(j.ok){ showToast('Deleted', 'success'); setTimeout(()=> location.reload(), 400); }
          else showToast(j.error || 'Delete failed', 'error');
        }).catch(()=> showToast('Delete failed', 'error'));
    }

    // NEW FOLDER
    function showNewFolderModal(){ openModal('newFolderModal'); setTimeout(()=> document.getElementById('folderNameInput')?.focus(), 50); }
    async function createNewFolder(){
      const name = (document.getElementById('folderNameInput')?.value || '').trim();
      if(!name){ showToast('Enter folder name', 'warning'); return; }
      try{
        const r = await fetch('{{ url_for("api_mkdir") }}', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({dest: window.currentPath || '', name})});
        const j = await r.json();
        if(j.ok){ showToast('Folder created', 'success'); closeModal('newFolderModal'); setTimeout(()=> location.reload(), 300); }
        else showToast(j.error || 'Failed', 'error');
      }catch(e){ showToast('Failed', 'error'); }
    }

    // CLIPBOARD TEXT
    function openClipModal(){ openModal('clipModal'); document.getElementById('clipTextInput')?.focus(); }
    async function saveClipboardText(){
      const ta = document.getElementById('clipTextInput');
      const nameInput = document.getElementById('clipNameInput');
      const text = (ta?.value || '').trim();
      let fname = (nameInput?.value || '').trim();
      if(!text){ showToast('Enter some text', 'warning'); return; }
      if(!fname){
        const now = new Date();
        const pad = (n)=> String(n).padStart(2,'0');
        fname = `clip-${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}.txt`;
      } else if(!/.txt$/i.test(fname)){
        fname += '.txt';
      }

      try {
        const r = await fetch('{{ url_for("api_cliptext") }}', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ dest: window.currentPath || '', name: fname, text })
        });
        const j = await r.json();
        if(j.ok){
          showToast('Text saved', 'success');
          closeModal('clipModal');
          setTimeout(()=> location.reload(), 300);
        } else {
          showToast(j.error || 'Failed to save', 'error');
        }
      } catch(e){
        showToast('Failed to save', 'error');
      }
    }

    // SORT controls bindings
    function initSortControls(){
      const sortBy = document.getElementById('sortBy');
      const sortDir = document.getElementById('sortDir');
      const ff = document.getElementById('foldersFirst');
      const prefs = getSortPrefs();
      if(sortBy){ sortBy.value = prefs.by; sortBy.addEventListener('change', ()=>{ setSortPrefs(sortBy.value, null, null); applySort(); }); }
      if(sortDir){
        sortDir.dataset.dir = prefs.dir;
        sortDir.innerHTML = prefs.dir === 'asc' ? '<i class="fas fa-arrow-up-wide-short"></i>' : '<i class="fas fa-arrow-down-wide-short"></i>';
        sortDir.addEventListener('click', ()=>{
          const cur = sortDir.dataset.dir === 'asc' ? 'desc' : 'asc';
          setSortPrefs(null, cur, null);
          sortDir.dataset.dir = cur;
          sortDir.innerHTML = cur === 'asc' ? '<i class="fas fa-arrow-up-wide-short"></i>' : '<i class="fas fa-arrow-down-wide-short"></i>';
          applySort();
        });
      }
      if(ff){ ff.checked = prefs.foldersFirst; ff.addEventListener('change', ()=>{ setSortPrefs(null, null, ff.checked); applySort(); }); }
    }

// SOCKET (live update without reload)
function initSocket(){
  try {
    const socket = io({reconnection:true, reconnectionAttempts:5, reconnectionDelay:1000});

    socket.on('file_update', (msg)=> {
      // Server emits:
      //  - on add: {action:'added', dir:'<parent_rel>', meta:{...}}
      //  - on delete: {action:'deleted', dir:'<parent_rel>', rel:'<path>'}
      const cur = window.currentPath || '';
      if (!msg || typeof msg !== 'object') return;

      if (msg.dir === cur) {
        if (msg.action === 'added' && msg.meta) {
          upsertFileCard(msg.meta);
          showToast(`Added: ${msg.meta.name}`, 'success');
        } else if (msg.action === 'deleted' && msg.rel) {
          removeFileCard(msg.rel);
          showToast('Deleted', 'warning');
        }
      } else {
        // Optional: notify if update happened in another folder
        // showToast(`Update in ${msg.dir || 'root'}`, 'info');
      }

      // Keep your dhikr shuffle if you like
      try { changeDhikr(); } catch(e){}
    });

    socket.on('share_ready', (msg)=> {
        const folder = {{ session.get('folder', '')|tojson }};
        if(msg && msg.folder === folder){
            showToast('Received a shared file!', 'info');
            checkForPendingShares();
        }
    });

  } catch(e){
    console.warn('Socket init failed', e);
  }
}
function safeHTML(s){
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function qsCardByRel(rel){
  const grid = document.getElementById('fileGrid');
  if(!grid) return null;
  const esc = (window.CSS && CSS.escape) ? CSS.escape(rel) : String(rel).replace(/"/g,'\\"');
  return grid.querySelector(`.file-card[data-rel="${esc}"]`);
}
function renderFileCard(meta){
  const isDir = !!meta.is_dir;
  const mime = (meta.mime || '').toLowerCase();
  let preview = '';
  if(isDir){
    preview = `<div class="file-icon-large" style="font-size:2rem;opacity:.6;">📁</div>`;
  } else if(mime.startsWith('image/')){
    preview = `<img src="${meta.raw_url}" alt="${safeHTML(meta.name)}" loading="lazy" />`;
  } else if(mime.startsWith('video/')){
    preview = `<div class="file-icon-large" style="font-size:2rem;opacity:.6;">🎬</div>`;
  } else if(mime.startsWith('audio/')){
    preview = `<div class="file-icon-large" style="font-size:2rem;opacity:.6;">🎵</div>`;
  } else if(mime === 'application/pdf'){
    preview = `<div class="file-icon-large" style="font-size:2rem;opacity:.6;">📄</div>`;
  } else {
    preview = `<div class="file-icon-large" style="font-size:2rem;opacity:.6;">📄</div>`;
  }

  const el = document.createElement('div');
  el.className = 'file-card';
  el.dataset.rel = meta.rel;
  el.dataset.name = meta.name || '';
  el.dataset.mime = meta.mime || '';
  el.dataset.isDir = isDir ? '1' : '0';
  el.dataset.size = String(meta.size || 0);
  el.dataset.mtime = String(meta.mtime || 0);
  el.dataset.raw = meta.raw_url || '';
  el.dataset.dl = meta.download_url || '';

  const openHref = encodeURI(`/b/${meta.rel}`);
  el.innerHTML = `
    <div class="file-preview">${preview}</div>
    <div class="file-info">
      <div class="file-name" title="${safeHTML(meta.name)}">${safeHTML(meta.name)}</div>
      <div class="file-meta">${safeHTML(meta.size_h || (isDir ? '-' : ''))} • ${safeHTML(meta.mtime_h || '')}</div>
      <div class="file-actions">
        ${isDir
          ? `<a class="btn btn-secondary btn-icon" href="${openHref}" title="Open"><i class="fas fa-folder-open"></i></a>
             <button class="btn btn-danger btn-icon" onclick="event.stopPropagation(); deleteFile('${meta.rel.replace(/'/g,"\\'")}')" title="Delete Folder"><i class="fas fa-trash"></i></button>`
          : `<a class="btn btn-primary btn-icon" href="${meta.download_url}" title="Download"><i class="fas fa-download"></i></a>
             <button class="btn btn-secondary btn-icon" onclick="event.stopPropagation(); shareFile('${meta.rel.replace(/'/g,"\\'")}')" title="Share"><i class="fas fa-share"></i></button>
             <button class="btn btn-danger btn-icon" onclick="event.stopPropagation(); deleteFile('${meta.rel.replace(/'/g,"\\'")}')" title="Delete"><i class="fas fa-trash"></i></button>`
        }
      </div>
    </div>
  `;
  return el;
}
function upsertFileCard(meta){
  const grid = document.getElementById('fileGrid');
  if(!grid || !meta) return;

  const noFilesMessage = document.getElementById('noFilesMessage');
  if (noFilesMessage) {
    noFilesMessage.style.display = 'none';
  }

  const existing = qsCardByRel(meta.rel);
  const node = renderFileCard(meta);
  if(existing){
    existing.replaceWith(node);
  } else {
    grid.appendChild(node);
  }
  // Keep UX consistent: apply current sort and search filter
  try { applySort(); } catch(e){}
  try { searchFiles(); } catch(e){}
}
function checkGridEmpty() {
    const grid = document.getElementById('fileGrid');
    const noFilesMessage = document.getElementById('noFilesMessage');
    if (!grid || !noFilesMessage) return;
    const hasCards = grid.querySelector('.file-card');
    noFilesMessage.style.display = hasCards ? 'none' : '';
}
function removeFileCard(rel){
  const el = qsCardByRel(rel);
  if(el) {
    el.remove();
    setTimeout(checkGridEmpty, 50);
  }
}
    // My QR modal with toggle (optional online/local)
    let qrOnlineMode = localStorage.getItem('qrMode') === 'online';
    async function showMyQR(){
      try {
        const mode = qrOnlineMode ? 'online' : 'local';
        const r = await fetch(`{{ url_for("api_my_qr") }}?mode=${mode}`, {cache:'no-store'});
        const j = await r.json();
        if(j.ok){
          const toggleId = 'qrToggle-' + Date.now();
          document.getElementById('myQRBody').innerHTML = `
            ${j.ngrok_available ? `
            <div class="toggle-container">
              <span class="toggle-label">Local</span>
              <div class="toggle-switch ${qrOnlineMode ? 'active' : ''}" id="${toggleId}">
                <div class="slider"></div>
              </div>
              <span class="toggle-label">Online</span>
            </div>
            ` : ''}
            <div class="qr-box"><img src="data:image/png;base64,${j.b64}" alt="QR" style="image-rendering:pixelated; image-rendering:crisp-edges;"/></div>
            <div class="row" style="justify-content:space-between; margin-top:.75rem;">
              <div style="font-size:.85rem; color:var(--text-secondary); word-break:break-all;" id="myQRLink">${j.url}</div>
              <button class="btn btn-secondary" id="copyQRBtn"><i class="fas fa-link"></i> Copy</button>
            </div>
            ${!j.ngrok_available && qrOnlineMode ? '<p style="color:var(--warning); text-align:center; margin-top:.5rem;"><i class="fas fa-exclamation-triangle"></i> Ngrok not available. Showing local QR.</p>' : ''}
          `;
          document.getElementById('copyQRBtn')?.addEventListener('click', ()=> copyLink(j.url));
          if(j.ngrok_available){
            const toggle = document.getElementById(toggleId);
            if(toggle){
              toggle.addEventListener('click', ()=>{
                qrOnlineMode = !qrOnlineMode;
                localStorage.setItem('qrMode', qrOnlineMode ? 'online' : 'local');
                closeModal('myQRModal');
                setTimeout(showMyQR, 100);
              });
            }
          }
          openModal('myQRModal');
        } else {
          showToast('Failed to generate QR', 'error');
        }
      } catch(e){ showToast('Failed to generate QR', 'error'); }
    }
    document.getElementById('myQRBtn')?.addEventListener('click', showMyQR);

    // Settings (only for admin; button is hidden for non-admin)
    async function openSettings(){
      try {
        const r = await fetch('/api/me', {cache:'no-store'});
        const j = await r.json();
        const privacyToggle = document.getElementById('privacyToggle');
        if(j.public === false) privacyToggle.classList.add('active'); else privacyToggle.classList.remove('active');

        const deleteToggle = document.getElementById('allowDeleteToggle');
        if(j.prefs?.allow_non_admin_delete === false) deleteToggle.classList.remove('active'); else deleteToggle.classList.add('active');

        openModal('settingsModal');
      } catch(e){ openModal('settingsModal'); }
    }
    function togglePrivacy(){ const t = document.getElementById('privacyToggle'); t.classList.toggle('active'); }
    document.getElementById('settingsBtn')?.addEventListener('click', openSettings);
    document.getElementById('privacyToggle')?.addEventListener('click', togglePrivacy);
    document.getElementById('allowDeleteToggle')?.addEventListener('click', ()=> document.getElementById('allowDeleteToggle').classList.toggle('active'));
    document.getElementById('generateTokenBtn')?.addEventListener('click', generateToken);
    document.getElementById('shareTokenBtn')?.addEventListener('click', showTokenShare);
    document.getElementById('saveSettingsBtn')?.addEventListener('click', async ()=>{
      const priv = document.getElementById('privacyToggle').classList.contains('active'); // true => private
      const pwd = document.getElementById('privacyPassword').value || '';
      const allowDelete = document.getElementById('allowDeleteToggle').classList.contains('active');

      let all_ok = true;
      try {
        await savePref('allow_non_admin_delete', allowDelete);
      } catch(e) { all_ok = false; }

      try {
        const r = await fetch('/api/privacy', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({public: !priv, password: pwd})});
        const j = await r.json();
        if(!j.ok){ all_ok = false; showToast(j.error || 'Failed to save privacy', 'error'); }
      } catch(e){ all_ok = false; showToast('Failed to save privacy', 'error'); }

      if(all_ok){
        showToast('Settings saved', 'success');
        document.getElementById('privacyPassword').value='';
        closeModal('settingsModal');
      }
    });

    async function generateToken() {
      try {
        const r = await fetch('/api/accounts/token', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name: 'Non-expiring API Token'})
        });
        const j = await r.json();

        if (j.ok) {
          const tokenInput = document.getElementById('apiTokenInput');
          tokenInput.value = j.token;
          tokenInput.select();
          document.execCommand('copy');
          // Store token for sharing
          tokenInput.dataset.token = j.token;
          // Show share button
          document.getElementById('shareTokenBtn').style.display = 'inline-flex';
          showToast('Token generated and copied to clipboard', 'success');
        } else {
          showToast(j.error || 'Failed to generate token', 'error');
        }
      } catch (e) {
        showToast('Failed to generate token', 'error');
      }
    }

    async function showTokenShare() {
      try {
        const tokenInput = document.getElementById('apiTokenInput');
        const token = tokenInput.dataset.token || tokenInput.value;

        if (!token) {
          showToast('Please generate a token first', 'warning');
          return;
        }

        // Generate QR code for token URL
        const mode = localStorage.getItem('qrMode') === 'online' ? 'online' : 'local';
        const r = await fetch(`{{ url_for("api_my_qr") }}?mode=${mode}&token=${encodeURIComponent(token)}`, {cache:'no-store'});
        const j = await r.json();

        if (j.ok) {
          const toggleId = 'tokenQrToggle-' + Date.now();
          document.getElementById('tokenShareBody').innerHTML = `
            ${j.ngrok_available ? `
            <div class="toggle-container">
              <span class="toggle-label">Local</span>
              <div class="toggle-switch ${qrOnlineMode ? 'active' : ''}" id="${toggleId}">
                <div class="slider"></div>
              </div>
              <span class="toggle-label">Online</span>
            </div>
            ` : ''}
            <div class="qr-box"><img src="data:image/png;base64,${j.b64}" alt="QR" style="image-rendering:pixelated; image-rendering:crisp-edges;"/></div>
            <div class="row" style="justify-content:space-between; margin-top:.75rem;">
              <div style="font-size:.85rem; color:var(--text-secondary); word-break:break-all;" id="tokenShareLink">${j.url}</div>
              <button class="btn btn-secondary" id="copyTokenShareBtn"><i class="fas fa-link"></i> Copy</button>
            </div>
            <p style="margin-top:0.5rem; text-align:center;">Share this link to allow others to access your server with this token</p>
            ${!j.ngrok_available && qrOnlineMode ? '<p style="color:var(--warning); text-align:center; margin-top:.5rem;"><i class="fas fa-exclamation-triangle"></i> Ngrok not available. Showing local QR.</p>' : ''}
          `;

          document.getElementById('copyTokenShareBtn')?.addEventListener('click', () => copyTokenShareLink());

          if (j.ngrok_available) {
            const toggle = document.getElementById(toggleId);
            if (toggle) {
              toggle.addEventListener('click', () => {
                qrOnlineMode = !qrOnlineMode;
                localStorage.setItem('qrMode', qrOnlineMode ? 'online' : 'local');
                closeModal('tokenShareModal');
                setTimeout(showTokenShare, 100);
              });
            }
          }

          openModal('tokenShareModal');
        } else {
          showToast('Failed to generate QR code', 'error');
        }
      } catch (e) {
        console.error(e);
        showToast('Failed to generate QR code', 'error');
      }
    }

    function copyTokenShareLink() {
      const linkElement = document.getElementById('tokenShareLink');
      if (linkElement) {
        const text = linkElement.textContent;
        try {
          // Try the modern clipboard API first
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text)
              .then(() => showToast('Link copied to clipboard', 'success'))
              .catch(err => {
                console.error('Clipboard API error:', err);
                fallbackCopy();
              });
          } else {
            fallbackCopy();
          }
        } catch (e) {
          console.error('Copy error:', e);
          fallbackCopy();
        }

        // Fallback copy method
        function fallbackCopy() {
          try {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';  // Prevent scrolling to the element
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.focus();
            textarea.select();
            const successful = document.execCommand('copy');
            document.body.removeChild(textarea);
            if (successful) {
              showToast('Link copied to clipboard', 'success');
            } else {
              showToast('Failed to copy link', 'error');
            }
          } catch (err) {
            console.error('Fallback copy error:', err);
            showToast('Failed to copy link', 'error');
          }
        }
      }
    }

    // INIT
    document.addEventListener('DOMContentLoaded', async ()=>{
      window.currentPath = "{{ current_rel|default('', true) }}";
      try {
        const r = await fetch('/api/prefs'); const j = await r.json();
        const v = j?.prefs?.view || localStorage.getItem('fileView') || 'grid';
        setView(v);
      } catch(e){ setView(localStorage.getItem('fileView') || 'grid'); }

      document.getElementById('searchInput')?.addEventListener('input', searchFiles);
      initUploadArea();
      initFileGrid();
      initSortControls();
      applySort();
      initBulkActions();
      checkGridEmpty();
      initSocket();
      checkForPendingShares(); // Check for shares on page load

      // Bind Create Folder / Paste text buttons
      document.getElementById('mkdirCreateBtn')?.addEventListener('click', createNewFolder);
      document.getElementById('folderNameInput')?.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ e.preventDefault(); createNewFolder(); }});
      document.getElementById('openClipBtn')?.addEventListener('click', openClipModal);
      document.getElementById('clipSaveBtn')?.addEventListener('click', saveClipboardText);
      document.getElementById('clipTextInput')?.addEventListener('keydown', (e)=>{ if((e.ctrlKey||e.metaKey) && e.key==='Enter'){ e.preventDefault(); saveClipboardText(); }});
      document.getElementById('clipNameInput')?.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ e.preventDefault(); saveClipboardText(); }});
      document.getElementById('confirmShareBtn')?.addEventListener('click', confirmShare);
      document.getElementById('confirmRenameBtn')?.addEventListener('click', confirmRename);
      initPwaInstall();
    });

    // PWA INSTALL
    function initPwaInstall() {
      let deferredPrompt;
      const installBtn = document.getElementById('installBtn');
      if (!installBtn) return;

      window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        installBtn.style.display = 'flex';
      });

      installBtn.addEventListener('click', async () => {
        if (deferredPrompt) {
          deferredPrompt.prompt();
          const { outcome } = await deferredPrompt.userChoice;
          if (outcome === 'accepted') {
            showToast('App installed!', 'success');
          }
          deferredPrompt = null;
          installBtn.style.display = 'none';
        }
      });

      window.addEventListener('appinstalled', () => {
        installBtn.style.display = 'none';
        deferredPrompt = null;
        showToast('Installation complete!', 'success');
      });
    }

    // FAB
    function toggleFabMenu(){ document.getElementById('fabMenu')?.classList.toggle('active'); }
    function closeFabMenu(){ document.getElementById('fabMenu')?.classList.remove('active'); }
  </script>
</body>
</html>
"""

BROWSE_HTML = """
<!-- Stats -->
<div class="stats-grid">
  <div class="stat-card">
    <div class="stat-icon" style="background: rgba(59,130,246,.2); color: var(--primary);"><i class="fas fa-file"></i></div>
    <div class="stat-info"><div class="stat-label">Files</div><div class="stat-value">{{ stats.files }}</div></div>
  </div>
  <div class="stat-card">
    <div class="stat-icon" style="background: rgba(245,158,11,.2); color: var(--warning);"><i class="fas fa-hdd"></i></div>
    <div class="stat-info"><div class="stat-label">Storage</div><div class="stat-value">{{ stats.size_h }}</div></div>
  </div>
  <div class="stat-card">
    <div class="stat-icon" style="background: rgba(139,92,246,.2); color: var(--secondary);"><i class="fas fa-folder"></i></div>
    <div class="stat-info"><div class="stat-label">Folders</div><div class="stat-value">{{ stats.dirs }}</div></div>
  </div>
  <div class="stat-card">
    <div class="stat-icon" style="background: rgba(16,185,129,.2); color: var(--success);"><i class="fas fa-calendar"></i></div>
    <div class="stat-info"><div class="stat-label">Since</div><div class="stat-value">{{ since }}</div></div>
  </div>
</div>

<!-- Bulk Actions Toolbar -->
<div id="bulkActionsToolbar" class="toolbar" style="display:none; background:color-mix(in srgb, var(--bg-secondary) 60%, var(--primary));">
  <div class="toolbar-row" style="justify-content:space-between;">
    <div style="font-weight:700;" id="selectionCount"></div>
    <div style="display:flex; gap:.5rem;">
      <button class="btn btn-primary" id="bulkMoveBtn"><i class="fas fa-people-carry"></i> Move</button>
      <button class="btn btn-danger" id="bulkDeleteBtn"><i class="fas fa-trash"></i> Delete</button>
      <button class="btn btn-success" id="bulkDownloadBtn"><i class="fas fa-download"></i> Download</button>
      <button class="btn btn-secondary" id="deselectAllBtn">Cancel</button>
    </div>
  </div>
</div>

<!-- Toolbar -->
<div class="toolbar">
  <div class="toolbar-row">
    <div class="search-box">
      <input id="searchInput" class="search-input" placeholder="Search..." />
      <i class="fas fa-search search-icon"></i>
    </div>
    <div class="view-controls">
      <button class="view-btn" data-view="grid" onclick="setView('grid')"><i class="fas fa-th"></i><span>Grid</span></button>
      <button class="view-btn" data-view="list" onclick="setView('list')"><i class="fas fa-list"></i><span>List</span></button>
    </div>
    <!-- Sorting controls -->
    <div class="view-controls" style="gap:.5rem;">
      <select id="sortBy" class="btn btn-secondary" title="Sort by">
        <option value="name">Name</option>
        <option value="size">Size</option>
        <option value="type">Type</option>
        <option value="date">Date</option>
      </select>
      <button id="sortDir" class="btn btn-secondary" title="Asc/Desc" data-dir="asc"><i class="fas fa-arrow-up-wide-short"></i></button>
      <label class="btn btn-secondary" style="gap:.5rem; cursor:pointer;">
        <input type="checkbox" id="foldersFirst" style="accent-color:#3B82F6; width:16px; height:16px;"> Folders first </label>
    </div>
    <button class="btn btn-secondary" onclick="showNewFolderModal()"><i class="fas fa-folder-plus"></i> New Folder</button>
    <button class="btn btn-primary" id="openClipBtn"><i class="fas fa-clipboard"></i> Paste Text</button>
    <nav class="nav-menu">
    <a class="btn btn-secondary" href=".." title="Up one folder">
      <i class="fas fa-level-up-alt"></i>
    </a>



  </div>
</div>

<!-- Upload -->
<div class="upload-section">
  <div class="upload-area" id="uploadArea">
    <input type="file" id="uploadInput" class="upload-input" multiple accept="*/*" />
    <div class="upload-icon"><i class="fas fa-cloud-upload-alt"></i></div>
    <div class="upload-text">Drop files or tap here</div>
    <div class="upload-subtext">Max 10GB per file</div>
  </div>
  <div class="progress-container" id="progressContainer"></div>
</div>

<!-- Files -->
<div class="file-grid list-view" id="fileGrid">
  {% if not entries %}
    <div class="card" id="noFilesMessage" style="text-align:center; color:var(--text-muted);">No files yet. Upload something!</div>
  {% endif %}
  {% for item in entries %}
    <div class="file-card"
         data-rel="{{ item.rel }}"
         data-name="{{ item.name }}"
         data-mime="{{ item.mime }}"
         data-is-dir="{{ 1 if item.is_dir else 0 }}"
         data-size="{{ item.size }}"
         data-mtime="{{ item.mtime }}"
         data-raw="{{ url_for('raw', path=item.rel) }}"
         data-dl="{{ url_for('download', path=item.rel) }}">
      <input type="checkbox" class="file-select-checkbox" data-rel="{{ item.rel }}" onchange="handleSelectionChange()" onclick="event.stopPropagation();">
      <div class="file-preview">
        {% if item.is_dir %}
          <div class="file-icon-large" style="font-size:2rem;opacity:.6;">📁</div>
        {% elif item.mime.startswith('image/') %}
          <img src="{{ url_for('raw', path=item.rel) }}" alt="{{ item.name }}" loading="lazy" />
        {% elif item.mime.startswith('video/') %}
          <div class="file-icon-large" style="font-size:2rem;opacity:.6;">🎬</div>
        {% elif item.mime.startswith('audio/') %}
          <div class="file-icon-large" style="font-size:2rem;opacity:.6;">🎵</div>
        {% elif item.mime == 'application/pdf' %}
          <div class="file-icon-large" style="font-size:2rem;opacity:.6;">📄</div>
        {% else %}
          <div class="file-icon-large" style="font-size:2rem;opacity:.6;">📄</div>
        {% endif %}
      </div>
      <div class="file-info">
        <div class="file-name" title="{{ item.name }}">{{ item.name }}</div>
        <div class="file-meta">{{ item.size_h }} • {{ item.mtime_h }}</div>
        <div class="file-actions">
          {% if not item.is_dir %}
            <a class="btn btn-primary btn-icon" href="{{ url_for('download', path=item.rel) }}" title="Download"><i class="fas fa-download"></i></a>
            <button class="btn btn-secondary btn-icon" onclick="event.stopPropagation(); shareFile('{{ item.rel }}')" title="Share"><i class="fas fa-share"></i></button>
            <button class="btn btn-danger btn-icon" onclick="event.stopPropagation(); deleteFile('{{ item.rel }}')" title="Delete"><i class="fas fa-trash"></i></button>
          {% else %}
            <a class="btn btn-secondary btn-icon" href="{{ url_for('browse') }}/{{ item.rel }}" title="Open"><i class="fas fa-folder-open"></i></a>
            <button class="btn btn-danger btn-icon" onclick="event.stopPropagation(); deleteFile('{{ item.rel }}')" title="Delete Folder"><i class="fas fa-trash"></i></button>
          {% endif %}
        </div>
      </div>
    </div>
  {% endfor %}
</div>

<!-- New Folder Modal -->
<div class="modal" id="newFolderModal">
  <div class="modal-content">
    <div class="modal-header">
      <h3 class="modal-title">Create New Folder</h3>
      <button class="modal-close" onclick="closeModal('newFolderModal')"><i class="fas fa-times"></i></button>
    </div>
    <div class="modal-body">
      <div class="form-group">
        <label class="form-label">Folder Name</label>
        <input type="text" id="folderNameInput" class="form-input" placeholder="Enter folder name" autocomplete="off">
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="closeModal('newFolderModal')">Cancel</button>
      <button class="btn btn-primary" id="mkdirCreateBtn"><i class="fas fa-folder-plus"></i> Create</button>
    </div>
  </div>
</div>

<!-- Paste Text Modal -->
<div class="modal" id="clipModal">
  <div class="modal-content">
    <div class="modal-header">
      <h3 class="modal-title">Paste Text</h3>
      <button class="modal-close" onclick="closeModal('clipModal')"><i class="fas fa-times"></i></button>
    </div>
    <div class="modal-body">
      <label class="form-label">File name (optional)</label>
      <input type="text" id="clipNameInput" class="form-input" placeholder="E.g. note.txt (default auto)">
      <label class="form-label" style="margin-top:.75rem;">Text</label>
      <textarea id="clipTextInput" class="form-input" rows="10" placeholder="Paste here"></textarea>
    </div>
    <div class="modal-footer">
      <button class="btn btn-primary" id="clipSaveBtn"><i class="fas fa-save"></i> Save</button>
    </div>
  </div>
</div>

<!-- FAB -->
<div class="fab-container">
  <div class="fab-menu" id="fabMenu">
    <button class="fab-menu-item" id="installBtn" style="display: none;"><i class="fas fa-download"></i> Install App</button>
    <button class="fab-menu-item" onclick="showNewFolderModal()"><i class="fas fa-folder-plus"></i> New Folder</button>
    <button class="fab-menu-item" onclick="document.getElementById('uploadInput').click()"><i class="fas fa-file-upload"></i> Upload Files</button>
    <button class="fab-menu-item" onclick="openClipModal()"><i class="fas fa-clipboard"></i> Paste Text</button>
  </div>
  <button class="fab" onclick="toggleFabMenu()"><i class="fas fa-plus"></i></button>
</div>
"""

LOGIN_HTML = """
<style>
.user-badge {
    display: none;
}
</style>

<div class="card">
  <h2 style="margin-bottom:.5rem;">Scan to login</h2>
  <p style="color:var(--text-secondary); margin-bottom:.75rem;">{{ message }}</p>

  {% if ngrok_available %}
  <div class="toggle-container" style="margin-bottom:1rem;">
    <span class="toggle-label">Local</span>
    <div class="toggle-switch" id="loginModeToggle">
      <div class="slider"></div>
    </div>
    <span class="toggle-label">Online</span>
  </div>
  {% endif %}

  <div style="display:flex; align-items:center; justify-content:center; padding:16px; background:#fff; border-radius:12px;">
    <img id="qrImage" src="data:image/png;base64,{{ qr_b64 }}" alt="QR Code" style="image-rendering:pixelated; image-rendering:crisp-edges;" />
  </div>
  <p class="muted" style="margin-top:.75rem; color:var(--text-muted);">Or open: <code id="qrUrl">{{ qr_url }}</code></p>
</div>
<script>
  let currentMode = 'local';
  let currentToken = "{{ token }}";

  {% if ngrok_available %}
  const toggle = document.getElementById('loginModeToggle');
  toggle.addEventListener('click', async ()=>{
    currentMode = currentMode === 'local' ? 'online' : 'local';
    toggle.classList.toggle('active', currentMode === 'online');
    try {
      const r = await fetch(`/api/login_qr?token=${currentToken}&mode=${currentMode}`, {cache:'no-store'});
      const j = await r.json();
      if(j.ok){
        document.getElementById('qrImage').src = `data:image/png;base64,${j.b64}`;
        document.getElementById('qrUrl').textContent = j.url;
      }
    } catch(e){}
  });
  {% endif %}

  async function poll(){
    try {
      const r = await fetch("{{ url_for('check_login', token=token) }}", {cache:'no-store'});
      const j = await r.json();
      if(j.authenticated && j.url){ window.location = j.url; return; }
    } catch(e){}
    setTimeout(poll, 1000);
  }
  setTimeout(poll, 500);
</script>
"""

UNLOCK_HTML = """
<div class="card" style="max-width:520px; margin:0 auto;">
  <h2 style="margin-bottom:.5rem;">Unlock Account</h2>
  <p style="color:var(--text-secondary); margin-bottom:.75rem;">This account is private. Enter password to continue.</p>
  {% if error %}
    <div style="background:rgba(239,68,68,.12); color:#fecaca; border:1px solid rgba(239,68,68,.4); border-radius:.5rem; padding:.5rem .75rem; margin-bottom:.5rem;">
      <i class="fas fa-exclamation-triangle"></i> {{ error }}
    </div>
  {% endif %}
  <form method="POST">
    <input type="hidden" name="next" value="{{ next_url|e }}">
    <input type="password" name="password" class="form-input" placeholder="Password" required>
    <div class="modal-footer" style="padding:0; margin-top:.75rem;">
      <button class="btn btn-primary" type="submit"><i class="fas fa-lock-open"></i> Unlock</button>
    </div>
  </form>
</div>
"""

# -----------------------------
# Routes: Auth with persistent device folders + Privacy
# -----------------------------
@app.route("/api/accounts/transfer_admin_start", methods=["POST"])
def api_accounts_transfer_admin_start():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401
    data = request.get_json(silent=True) or {}
    folder = (data.get("folder") or "").strip()
    if not folder:
        return jsonify({"ok": False, "error": "folder required"}), 400
    if not is_admin_device_of(folder):
        return jsonify({"ok": False, "error": "only current admin can start transfer"}), 403

    token = secrets.token_urlsafe(16)
    admin_claim_tokens[token] = {
        "folder": folder,
        "created": datetime.utcnow().isoformat() + "Z"
    }

    # Build claim URL (external-aware)
    scheme = "https" if (request.is_secure or request.headers.get("X-Forwarded-Proto", "http") == "https") else "http"
    claim_url = url_for("scan_admin", token=token, _external=True, _scheme=scheme)
    b64 = make_qr_png_b64(claim_url)
    return jsonify({"ok": True, "b64": b64, "url": claim_url})

@app.route("/scan_admin/<token>")
def scan_admin(token: str):
    info = admin_claim_tokens.pop(token, None)
    if not info:
        return ("Invalid or expired token", 404)
    folder = info.get("folder")
    if not folder:
        return ("Invalid token", 400)

    # Identify this device (create if missing)
    device_id, _existing_folder = get_or_create_device_folder(request)

    # Assign admin to this device for the target folder
    users = app.config.setdefault("USERS", load_users())
    cfg = users.get(folder) or get_user_cfg(folder)
    cfg["admin_device"] = device_id
    save_users(users)

    # Log this device into that account and set default
    session["authed"] = True
    session["folder"] = folder
    session["icon"] = get_user_icon(folder)
    app.config["DEVICE_MAP"][device_id] = {"folder": folder, "created": datetime.utcnow().isoformat() + "Z"}
    save_device_map(app.config["DEVICE_MAP"])

    resp = make_response(redirect(url_for("browse", subpath=folder)))
    resp.set_cookie(DEVICE_COOKIE_NAME, device_id, max_age=60*60*24*730, samesite="Lax")
    return resp

@app.route("/login")
def login():
    # Check if a token parameter is provided for direct access
    access_token = request.args.get("token")
    if access_token:
        # Check if this is a valid API token
        user_data = get_user_by_token(access_token)
        if user_data:
            # Set session data
            session["authed"] = True
            session["folder"] = user_data.get("folder")
            session["icon"] = user_data.get("icon") or get_user_icon(user_data.get("folder"))
            # Redirect to browse
            return redirect(url_for("browse", subpath=session.get("folder", "")))

    # Normal login flow if no token or invalid token
    token = str(uuid.uuid4())
    pc_token = secrets.token_urlsafe(16)
    pending_sessions[token] = {"authenticated": False, "folder": None, "icon": None, "pc_token": pc_token}
    session["login_token"] = token

    ngrok_url = get_ngrok_url()
    ngrok_available = bool(ngrok_url)

    ip = get_local_ip()
    # qr_url = f"http://{ip}:{PORT}/scan/{token}"
    # qr_b64 = make_qr_png_b64(qr_url)
    # in /login route
    scheme = "https" if (request.is_secure or request.headers.get("X-Forwarded-Proto", "http") == "https") else "http"
    qr_url = url_for("scan", token=token, _external=True, _scheme=scheme)
    qr_b64 = make_qr_png_b64(qr_url)



    message = "Scan this QR with your phone to approve this session."
    if ngrok_available:
        message = "Choose local (same network) or online (anywhere) and scan the QR."

    body = render_template_string(LOGIN_HTML,
                                   qr_b64=qr_b64,
                                   qr_url=qr_url,
                                   token=token,
                                   ngrok_available=ngrok_available,
                                   message=message)
    # On login page, no dhikr banner
    return render_template_string(BASE_HTML, body=body, authed=is_authed(), icon=None, user_label="", current_rel="", dhikr="", dhikr_list=[], is_admin=False)

@app.route("/api/login_qr")
def api_login_qr():
    token = request.args.get("token")
    mode = request.args.get("mode", "local")

    if not token or token not in pending_sessions:
        return jsonify({"ok": False, "error": "Invalid token"}), 400

    if mode == "online":
        ngrok_url = get_ngrok_url()
        if ngrok_url:
            qr_url = f"{ngrok_url}/scan/{token}"
        else:
            ip = get_local_ip()
            qr_url = f"http://{ip}:{PORT}/scan/{token}"
    else:
        ip = get_local_ip()
        qr_url = f"http://{ip}:{PORT}/scan/{token}"

    qr_b64 = make_qr_png_b64(qr_url)
    return jsonify({"ok": True, "b64": qr_b64, "url": qr_url})

@app.route("/unlock", methods=["GET","POST"])
def unlock():
    folder = request.args.get("folder") or session.get("folder")
    if not folder:
        return redirect(url_for("login"))
    error = None
    next_url = request.values.get("next") or url_for("browse", subpath=folder)
    if request.method == "POST":
        pwd = request.form.get("password") or ""
        if verify_password(folder, pwd):
            ao = session.get("access_ok", {})
            ao[folder] = True
            session["access_ok"] = ao
            return redirect(next_url)
        else:
            error = "Wrong password"
    body = render_template_string(UNLOCK_HTML, error=error, next_url=next_url)
    return render_template_string(BASE_HTML, body=body, authed=False, icon=None, user_label="", current_rel="", dhikr="", dhikr_list=[], is_admin=False)

@app.route("/check/<token>")
def check_login(token: str):
    info = pending_sessions.get(token)
    if not info:
        return jsonify({"authenticated": False})
    if info["authenticated"]:
        pc_token = info.get("pc_token")
        pc_url = None
        if pc_token and info.get("folder"):
            app.config["LOGIN_TOKENS"][pc_token] = info["folder"]
            pc_url = url_for("pc_login", token=pc_token)
        return jsonify({"authenticated": True, "folder": info.get("folder"), "icon": info.get("icon"), "url": pc_url})
    return jsonify({"authenticated": False})

@app.route("/scan/<token>")
def scan(token: str):
    info = pending_sessions.get(token)
    if not info:
        return ("Invalid or expired token", 404)
    device_id, folder = get_or_create_device_folder(request)
    icon = get_user_icon(folder)
    session["authed"] = True
    session["folder"] = folder
    session["icon"] = icon
    info["authenticated"] = True
    if info.get("folder"):
        session["folder"] = info["folder"]
        session["icon"] = info.get("icon") or get_user_icon(info["folder"])
        folder = info["folder"]
        icon = session["icon"]
    else:
        info["folder"] = folder
        info["icon"] = icon
    resp = make_response(redirect(url_for("browse", subpath=folder)))
    resp.set_cookie(DEVICE_COOKIE_NAME, device_id, max_age=60*60*24*730, samesite="Lax")
    return resp

@app.route("/pc_login/<token>")
def pc_login(token):
    folder = app.config["LOGIN_TOKENS"].pop(token, None)
    if not folder:
        abort(403)
    session["authed"] = True
    session["folder"] = folder
    session["icon"] = get_user_icon(folder)
    return redirect(url_for("browse"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -----------------------------
# Routes: Files
# -----------------------------
@app.route("/")
def home():
    if not is_authed():
        return redirect(url_for("login"))
    return redirect(url_for("browse", subpath=session.get("folder", "")))

@app.route("/b/")
@app.route("/b/<path:subpath>")
def browse(subpath: Optional[str] = None):
    if not is_authed():
        return redirect(url_for("login"))
    if not subpath:
        subpath = session.get("folder", "")
    # Enforce access on folder
    folder_name = subpath.split("/",1)[0] if subpath else session.get("folder","")
    need = enforce_access_or_redirect(folder_name)
    if need: return need

    dest = safe_path(subpath) if subpath else ROOT_DIR
    if not dest.exists():
        abort(404)
    if dest.is_file():
        rel = path_rel(dest)
        return redirect(url_for("download", path=rel))

    items = []
    for p in sorted(dest.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        items.append(get_file_meta(p))

    root_for_stats = ROOT_DIR / session.get("folder", "")
    stats = get_stats(root_for_stats if root_for_stats.exists() else ROOT_DIR)
    device_map = app.config["DEVICE_MAP"]
    since_iso = None
    for did, info in device_map.items():
        if info.get("folder") == session.get("folder"):
            since_iso = info.get("created")
            break
    since_txt = datetime.fromisoformat(since_iso.replace("Z","")) if since_iso else datetime.utcnow()
    since = since_txt.strftime("%b %Y")

    dhikr = get_random_dhikr()
    dhikr_list = [{"dhikr": d} for d in ISLAMIC_DHIKR]

    device_id = request.cookies.get(DEVICE_COOKIE_NAME)
    cfg = get_user_cfg(session.get("folder",""))
    is_admin = bool(device_id and device_id == cfg.get("admin_device"))

    body = render_template_string(BROWSE_HTML, entries=items, stats=stats, since=since)
    return render_template_string(
        BASE_HTML,
        body=body,
        authed=True,
        icon=session.get("icon"),
        user_label=session.get("folder",""),
        current_rel=(path_rel(dest) if dest != ROOT_DIR else ""),
        dhikr=dhikr, dhikr_list=dhikr_list,
        is_admin=is_admin
    )

@app.route("/download")
def download():
    if not is_authed():
        return redirect(url_for("login"))
    rel = request.args.get("path", "")
    p = safe_path(rel)
    if not p.exists() or not p.is_file():
        abort(404)
    folder_name = first_segment(rel) or session.get("folder","")
    need = enforce_access_or_redirect(folder_name)
    if need: return need
    return send_from_directory(p.parent, p.name, as_attachment=True, download_name=p.name)

@app.route("/raw")
def raw():
    if not is_authed():
        return redirect(url_for("login"))
    rel = request.args.get("path", "")
    p = safe_path(rel)
    if not p.exists() or not p.is_file():
        abort(404)
    folder_name = first_segment(rel) or session.get("folder","")
    need = enforce_access_or_redirect(folder_name)
    if need: return need
    mime = guess_mime(p)
    return send_partial_file(p, mime)

# -----------------------------
# APIs (User + Files)
# -----------------------------
@app.route("/api/dhikr")
def api_dhikr():
    dhikr = get_random_dhikr()
    return jsonify({"dhikr": dhikr})

@app.route("/api/me")
def api_me():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401
    folder = session.get("folder")
    cfg = get_user_cfg(folder)
    device_id = request.cookies.get(DEVICE_COOKIE_NAME)
    is_admin = bool(device_id and device_id == cfg.get("admin_device"))
    return jsonify({"ok": True, "folder": folder, "public": cfg.get("public", True), "has_password": bool(cfg.get("password_hash")), "prefs": cfg.get("prefs", {}), "is_admin": is_admin})

@app.route("/api/privacy", methods=["POST"])
def api_privacy():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401
    folder = session.get("folder")
    cfg = get_user_cfg(folder)
    device_id = request.cookies.get(DEVICE_COOKIE_NAME)
    if not device_id or device_id != cfg.get("admin_device"):
        return jsonify({"ok": False, "error": "only admin device can change privacy"}), 403
    data = request.get_json(silent=True) or {}
    is_public = bool(data.get("public", True))
    pwd = (data.get("password") or "").strip()
    if not is_public and not cfg.get("password_hash") and len(pwd) < 4:
        return jsonify({"ok": False, "error": "set a password (min 4 chars) to make private"}), 400
    set_privacy(folder, is_public, pwd if (pwd and not is_public) else None)
    return jsonify({"ok": True, "public": is_public})

@app.route("/api/prefs", methods=["GET","POST"])
def api_prefs():
    if not is_authed():
        return jsonify({"ok": True, "prefs": {"theme": "dark", "view": "list"}}), 200
    folder = session.get("folder")
    if request.method == "GET":
        cfg = get_user_cfg(folder)
        return jsonify({"ok": True, "prefs": cfg.get("prefs", {})})
    data = request.get_json(silent=True) or {}
    key = data.get("key")
    value = data.get("value")
    if not key:
        return jsonify({"ok": False, "error": "key required"}), 400
    save_pref(folder, key, value)
    return jsonify({"ok": True})

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401
    dest_rel = request.form.get("dest", "")
    dest_dir = safe_path(dest_rel)
    base_folder = session.get("folder")
    if first_segment(path_rel(dest_dir)) != base_folder and path_rel(dest_dir) != "":
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if not dest_dir.exists() or not dest_dir.is_dir():
        return jsonify({"ok": False, "error": "bad dest"}), 400
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "no file"}), 400

    filename = sanitize_filename(f.filename)
    if ALLOWED_UPLOAD_EXT:
      ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
      if ext not in ALLOWED_UPLOAD_EXT:
        return jsonify({"ok": False, "error": "file type not allowed"}), 400

    save_path = dest_dir / filename
    base, ext = os.path.splitext(filename)
    i = 1
    while save_path.exists():
        save_path = dest_dir / f"{base} ({i}){ext}"
        i += 1
    try:
        f.save(save_path)
    except Exception as e:
        return jsonify({"ok": False, "error": f"save failed: {e}"}), 500

    meta = get_file_meta(save_path)
    parent_rel = path_rel(dest_dir) if dest_dir != ROOT_DIR else ""
    socketio.emit("file_update", {"action":"added","dir": parent_rel, "meta": meta})
    return jsonify({"ok": True, "meta": meta}), 201

@app.route("/api/delete", methods=["POST"])
def api_delete():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401

    base_folder = session.get("folder")
    cfg = get_user_cfg(base_folder)
    allow_non_admin_delete = cfg.get("prefs", {}).get("allow_non_admin_delete", True)
    if not allow_non_admin_delete and not is_admin_device_of(base_folder):
        return jsonify({"ok": False, "error": "You do not have permission to delete files."}), 403

    data = request.get_json(silent=True) or {}
    files = data.get("files") or []
    deleted = []
    for rel in files:
        if first_segment(rel) != base_folder:
            continue
        p = safe_path(rel)
        if p.exists():
            try:
                if p.is_file():
                    p.unlink()
                elif p.is_dir():
                    for sub in sorted(p.rglob("*"), reverse=True):
                        if sub.is_file(): sub.unlink()
                        else: sub.rmdir()
                    p.rmdir()
                deleted.append(rel)
            except Exception as e:
                print("Delete failed:", e)
    for rel in deleted:
        parent = str(Path(rel).parent).replace("\\", "/")
        if parent == ".": parent = ""
        socketio.emit("file_update", {"action":"deleted","dir": parent, "rel": rel})
    return jsonify({"ok": True, "deleted": deleted})

@app.route("/api/mkdir", methods=["POST"])
def api_mkdir():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401
    data = request.get_json(silent=True) or {}
    dest_rel = data.get("dest") or ""
    name = sanitize_filename((data.get("name") or "").strip())
    base_folder = session.get("folder")
    target_dir = safe_path(dest_rel)
    if first_segment(path_rel(target_dir)) != base_folder and path_rel(target_dir) != "":
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if not name:
        return jsonify({"ok": False, "error": "name required"}), 400
    if name in {".",".."}:
        return jsonify({"ok": False, "error": "bad name"}), 400
    dest = target_dir
    if not dest.exists() or not dest.is_dir():
        return jsonify({"ok": False, "error": "bad dest"}), 400
    new_dir = dest / name
    try:
        new_dir.mkdir(parents=False, exist_ok=False)
    except FileExistsError:
        return jsonify({"ok": False, "error": "already exists"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    meta = get_file_meta(new_dir)
    socketio.emit("file_update", {"action":"added","dir": dest_rel, "meta": meta})
    return jsonify({"ok": True, "meta": meta})

@app.route("/api/my_qr")
def api_my_qr():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401

    mode = request.args.get("mode", "local")
    access_token = request.args.get("token")

    # If a specific token is provided, create a URL with that token
    if access_token:
        ngrok_url = get_ngrok_url()
        ngrok_available = bool(ngrok_url)

        if mode == "online" and ngrok_url:
            qr_url = f"{ngrok_url}/login?token={access_token}"
        else:
            ip = get_local_ip()
            qr_url = f"http://{ip}:{PORT}/login?token={access_token}"
    # Otherwise, generate a temporary session token for QR login
    else:
        token = str(uuid.uuid4())
        pc_token = secrets.token_urlsafe(16)
        pending_sessions[token] = {
            "authenticated": False,
            "folder": session.get("folder"),
            "icon": session.get("icon"),
            "pc_token": pc_token,
        }

        ngrok_url = get_ngrok_url()
        ngrok_available = bool(ngrok_url)

        if mode == "online" and ngrok_url:
            qr_url = f"{ngrok_url}/scan/{token}"
        else:
            ip = get_local_ip()
            qr_url = f"http://{ip}:{PORT}/scan/{token}"

    qr_b64 = make_qr_png_b64(qr_url)
    return jsonify({"ok": True, "b64": qr_b64, "url": qr_url, "ngrok_available": ngrok_available})

@app.route("/api/cliptext", methods=["POST"])
def api_cliptext():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401
    data = request.get_json(silent=True) or {}
    dest_rel = data.get("dest") or ""
    text = data.get("text")
    name = (data.get("name") or "").strip()
    base_folder = session.get("folder")
    target_dir = safe_path(dest_rel)
    if first_segment(path_rel(target_dir)) != base_folder and path_rel(target_dir) != "":
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if text is None:
        return jsonify({"ok": False, "error": "text required"}), 400
    dest_dir = target_dir
    if not dest_dir.exists() or not dest_dir.is_dir():
        return jsonify({"ok": False, "error": "bad dest"}), 400
    if name:
        filename = sanitize_filename(name)
    else:
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        filename = f"clip-{ts}.txt"
    if "." not in filename:
        filename += ".txt"
    base, ext = os.path.splitext(filename)
    if not ext:
        ext = ".txt"
        filename = base + ext
    save_path = dest_dir / filename
    i = 1
    while save_path.exists():
        save_path = dest_dir / f"{base} ({i}){ext}"
        i += 1
    try:
        save_path.write_text(text, encoding="utf-8", errors="replace")
    except Exception as e:
        return jsonify({"ok": False, "error": f"save failed: {e}"}), 500

    meta = get_file_meta(save_path)
    parent_rel = path_rel(dest_dir) if dest_dir != ROOT_DIR else ""
    socketio.emit("file_update", {"action":"added","dir": parent_rel, "meta": meta})
    return jsonify({"ok": True, "meta": meta})

@app.route("/api/folders")
def api_folders():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401

    base_folder_path = ROOT_DIR / session.get("folder", "")

    def get_dir_structure(path):
        structure = []
        try:
            for item in path.iterdir():
                if item.is_dir():
                    children = get_dir_structure(item)
                    structure.append({
                        "name": item.name,
                        "path": path_rel(item),
                        "children": children
                    })
        except Exception as e:
            print(f"Error reading directory {path}: {e}")
        return sorted(structure, key=lambda x: x['name'].lower())

    folder_tree = [{
        "name": session.get("folder", "root"),
        "path": session.get("folder", ""),
        "children": get_dir_structure(base_folder_path)
    }]

    return jsonify({"ok": True, "tree": folder_tree})

@app.route("/api/move", methods=["POST"])
def api_move():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401
    data = request.get_json(silent=True) or {}
    sources = data.get("sources", [])
    destination = data.get("destination", "")

    if not sources or destination is None:
        return jsonify({"ok": False, "error": "sources and destination required"}), 400

    base_folder = session.get("folder")
    dest_dir = safe_path(destination)

    # Security checks
    if first_segment(path_rel(dest_dir)) != base_folder and path_rel(dest_dir) != base_folder:
        return jsonify({"ok": False, "error": "forbidden destination"}), 403
    if not dest_dir.exists() or not dest_dir.is_dir():
        return jsonify({"ok": False, "error": "bad destination"}), 400

    moved_files = []
    errors = []

    for rel_path in sources:
        if first_segment(rel_path) != base_folder:
            errors.append({"path": rel_path, "error": "forbidden source"})
            continue

        source_path = safe_path(rel_path)
        if not source_path.exists():
            errors.append({"path": rel_path, "error": "source does not exist"})
            continue

        if source_path == dest_dir or str(dest_dir).startswith(str(source_path) + os.sep):
            errors.append({"path": rel_path, "error": "cannot move a folder into itself"})
            continue

        target_path = dest_dir / source_path.name

        # Handle name conflicts
        if target_path.exists() and str(target_path) != str(source_path):
            base, ext = os.path.splitext(source_path.name)
            i = 1
            while target_path.exists():
                target_path = dest_dir / f"{base} ({i}){ext}"
                i += 1

        try:
            shutil.move(str(source_path), str(target_path))
            # Emit socket events for UI update
            old_parent = str(Path(rel_path).parent)
            if old_parent == '.': old_parent = ''
            socketio.emit("file_update", {"action": "deleted", "dir": old_parent, "rel": rel_path})
            socketio.emit("file_update", {"action": "added", "dir": destination, "meta": get_file_meta(target_path)})
            moved_files.append({"from": rel_path, "to": path_rel(target_path)})
        except Exception as e:
            errors.append({"path": rel_path, "error": str(e)})

    return jsonify({"ok": len(moved_files) > 0, "moved": moved_files, "errors": errors})

@app.route("/api/download_zip", methods=["POST"])
def api_download_zip():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401

    data = request.get_json(silent=True) or {}
    files = data.get("files", [])
    if not files:
        return jsonify({"ok": False, "error": "No files selected"}), 400

    base_folder = session.get("folder")

    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for rel_path in files:
            if first_segment(rel_path) != base_folder:
                continue

            abs_path = safe_path(rel_path)
            if not abs_path.exists():
                continue

            if abs_path.is_file():
                zf.write(abs_path, arcname=abs_path.name)
            elif abs_path.is_dir():
                for root, _, dir_files in os.walk(abs_path):
                    for f_name in dir_files:
                        file_path = Path(root) / f_name
                        arcname = file_path.relative_to(abs_path.parent).as_posix()
                        zf.write(file_path, arcname=arcname)

    memory_file.seek(0)

    zip_name = f"{base_folder}-download.zip" if len(files) > 1 else f"{Path(files[0]).name}.zip"

    return send_file(
        memory_file,
        download_name=zip_name,
        as_attachment=True,
        mimetype='application/zip'
    )

# -----------------------------
# -----------------------------
# Routes: PWA Share Target
# -----------------------------
SHARE_MODAL_HTML = """
<div class="modal" id="shareModal">
  <div class="modal-content" style="max-width:520px;">
    <div class="modal-header">
      <div class="modal-title">Complete Your Share</div>
      <button class="modal-close" onclick="closeModal('shareModal')" aria-label="Close"><i class="fas fa-times"></i></button>
    </div>
    <div class="modal-body">
      <p style="margin-bottom:.5rem;">Saving file: <strong id="shareFileName"></strong></p>
      <p>Select destination folder:</p>
      <div id="shareFolderTree" style="height: 200px; overflow-y: auto; border: 1px solid var(--border); padding: .5rem; border-radius: .5rem; background: var(--bg-primary);">
        Loading...
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="closeModal('shareModal')">Cancel</button>
      <button class="btn btn-primary" id="confirmShareBtn"><i class="fas fa-save"></i> Save Here</button>
    </div>
  </div>
</div>
"""

@app.route("/share-receiver", methods=["POST"])
def share_receiver():
    device_id, folder = get_or_create_device_folder(request)
    if not folder:
        return Response("Device not recognized. Please log in to the app first.", status=401)

    f = request.files.get("files")
    if not f or not f.filename:
        return Response("No file was shared.", status=400)

    pending_dir = safe_path(folder) / ".pending_shares"
    pending_dir.mkdir(exist_ok=True)

    filename = sanitize_filename(f.filename)
    # Use a UUID to avoid filename collisions in the pending folder
    save_name = f"{str(uuid.uuid4())}__{filename}"
    save_path = pending_dir / save_name

    try:
        f.save(save_path)
    except Exception as e:
        print(f"[share] Save failed: {e}")
        return Response("Failed to save shared file.", status=500)

    # Let the main app know a share is ready via socket
    socketio.emit("share_ready", {"folder": folder})
    return Response(status=204)

@app.route("/api/pending_shares")
def api_pending_shares():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401

    folder = session.get("folder")
    pending_dir = safe_path(folder) / ".pending_shares"
    files = []
    if pending_dir.exists():
        for p in pending_dir.iterdir():
            if p.is_file():
                try:
                    uuid_part, name_part = p.name.split("__", 1)
                    files.append({"id": p.name, "name": name_part})
                except ValueError:
                    continue # Skip files not in the expected format
    return jsonify({"ok": True, "files": files})

@app.route("/api/commit_share", methods=["POST"])
def api_commit_share():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401

    data = request.get_json(silent=True) or {}
    pending_id = data.get("id")
    destination_rel = data.get("destination")

    if not pending_id or destination_rel is None:
        return jsonify({"ok": False, "error": "id and destination required"}), 400

    base_folder = session.get("folder")
    if first_segment(destination_rel) != base_folder and destination_rel != base_folder:
        return jsonify({"ok": False, "error": "forbidden destination"}), 403

    pending_dir = safe_path(base_folder) / ".pending_shares"
    pending_file = pending_dir / pending_id

    if not pending_file.exists() or not pending_file.is_file():
        return jsonify({"ok": False, "error": "pending file not found"}), 404

    try:
        _, original_filename = pending_id.split("__", 1)
    except ValueError:
        original_filename = pending_id # fallback

    dest_dir = safe_path(destination_rel)
    save_path = dest_dir / original_filename

    # Handle name conflicts
    base, ext = os.path.splitext(original_filename)
    i = 1
    while save_path.exists():
        save_path = dest_dir / f"{base} ({i}){ext}"
        i += 1

    try:
        shutil.move(str(pending_file), str(save_path))
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to move file: {e}"}), 500

    meta = get_file_meta(save_path)
    socketio.emit("file_update", {"action":"added", "dir": destination_rel, "meta": meta})
    return jsonify({"ok": True, "meta": meta})


# Error handlers: redirect to login on not found/forbidden
# -----------------------------
@app.errorhandler(404)
def handle_404(e):
    if request.path.startswith("/static") or request.path.startswith("/socket.io"):
        return e
    if not is_authed():
        return redirect(url_for('login'))
    return redirect(url_for('login'))

@app.errorhandler(403)
def handle_403(e):
    if request.path.startswith("/static") or request.path.startswith("/socket.io"):
        return e
    if not is_authed():
        return redirect(url_for('login'))
    return redirect(url_for('home'))

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    ip = get_local_ip()
    print(f"Serving FileVault on http://0.0.0.0:{PORT}  (scan: http://{ip}:{PORT})")
    ngrok_url = get_ngrok_url()
    if ngrok_url:
        print(f"Ngrok URL detected: {ngrok_url}")
    else:
        print("Ngrok not detected. To enable online access, run: ngrok http 5000")
    print(f"Root directory: {ROOT_DIR}")
    socketio.run(app, host="0.0.0.0", port=PORT, debug=False)
