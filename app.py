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
from urllib.parse import urlparse
from io import BytesIO
from pathlib import Path
from datetime import datetime
from typing import Optional

from flask import (
    Flask, request, session, redirect, url_for, send_from_directory, send_file,
    render_template, abort, jsonify, Response, make_response
)
from flask_cors import CORS
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

def generate_temp_code() -> str:
    """Generates a 6-digit numeric code."""
    return f"{random.randint(100000, 999999):06d}"

def generate_unique_permanent_code() -> str:
    """Generates a unique 6-digit code for permanent login."""
    users = app.config.setdefault("USERS", load_users())
    for _ in range(100):  # Max 100 retries
        code = f"{random.randint(100000, 999999):06d}"
        if not any(user.get("permanent_code") == code for user in users.values()):
            return code
    raise Exception("Could not generate a unique permanent code.")

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

app = Flask(__name__, static_folder="static", template_folder="templates", static_url_path="/static")
CORS(app) # Initialize CORS to allow cross-origin requests
app.secret_key = APP_SECRET
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["SESSION_COOKIE_NAME"] = SESSION_COOKIE_NAME
app.config["JSONIFY_MIMETYPE"] = "application/json; charset=utf-8"
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

# The ensure_favicon_assets function was removed because the manifest and icon
# are now static files managed directly, providing better control for PWA features.

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

@app.context_processor
def inject_ngrok_status():
    ngrok_url_str = get_ngrok_url()
    is_on_ngrok = False
    is_on_local = False

    if ngrok_url_str:
        ngrok_host = urlparse(ngrok_url_str).hostname
        request_host = request.host.split(':')[0]
        if ngrok_host and ngrok_host == request_host:
            is_on_ngrok = True
        else:
            local_ip = get_local_ip()
            if request_host == local_ip or request_host in ['127.0.0.1', 'localhost']:
                is_on_local = True

    return dict(
        is_on_ngrok=is_on_ngrok,
        is_on_local_with_ngrok_available=(is_on_local and bool(ngrok_url_str))
    )

# The /api/go_online and /api/go_offline routes are no longer needed,
# as this functionality is now handled by the launcher page (index.html).

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

    user_cfg = users[folder]
    tokens = user_cfg.setdefault("tokens", {})

    # Get or create permanent code
    permanent_code = user_cfg.get("permanent_code")
    if not permanent_code:
        try:
            permanent_code = generate_unique_permanent_code()
            user_cfg["permanent_code"] = permanent_code
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    # Get or create permanent token
    existing_token_info = next((info for info in tokens.values() if info.get("expires") is None), None)
    if existing_token_info:
        token = existing_token_info["token"]
        token_id = next((tid for tid, info in tokens.items() if info == existing_token_info), None)
        message = "Permanent token and code already exist."
    else:
        token = secrets.token_urlsafe(32)
        token_id = str(uuid.uuid4())
        tokens[token_id] = {
            "token": token,
            "created": datetime.utcnow().isoformat() + "Z",
            "name": data.get("name", "API Token"),
            "expires": None
        }
        message = "Permanent token and code created successfully."

    save_users(users)

    return jsonify({
        "ok": True,
        "token": token,
        "permanent_code": permanent_code,
        "token_id": token_id,
        "message": message
    })

@app.route("/api/accounts/token/regenerate", methods=["POST"])
def api_accounts_token_regenerate():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401

    folder = session.get("folder")
    if not folder:
        return jsonify({"ok": False, "error": "no folder in session"}), 400

    if not is_admin_device_of(folder):
        return jsonify({"ok": False, "error": "only admin device can regenerate tokens"}), 403

    users = app.config.setdefault("USERS", load_users())
    user_cfg = users[folder]
    tokens = user_cfg.setdefault("tokens", {})

    # Find and remove the old permanent token if it exists
    old_token_id = None
    for token_id, token_info in tokens.items():
        if token_info.get("expires") is None:
            old_token_id = token_id
            break
    if old_token_id:
        del tokens[old_token_id]

    # Generate a new permanent token and a new unique code
    try:
        new_permanent_code = generate_unique_permanent_code()
        user_cfg["permanent_code"] = new_permanent_code
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    new_token = secrets.token_urlsafe(32)
    new_token_id = str(uuid.uuid4())
    tokens[new_token_id] = {
        "token": new_token,
        "created": datetime.utcnow().isoformat() + "Z",
        "name": "Permanent API Token",
        "expires": None
    }

    save_users(users)

    return jsonify({
        "ok": True,
        "token": new_token,
        "permanent_code": new_permanent_code,
        "token_id": new_token_id,
        "message": "Permanent token and code have been regenerated."
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

    error = request.args.get("error")
    # Normal login flow if no token or invalid token
    token = str(uuid.uuid4())
    pc_token = secrets.token_urlsafe(16)
    login_code = generate_temp_code()
    pending_sessions[token] = {"authenticated": False, "folder": None, "icon": None, "pc_token": pc_token, "login_code": login_code}
    session["login_token"] = token

    ngrok_url = get_ngrok_url()
    ngrok_available = bool(ngrok_url)

    is_on_ngrok = False
    is_on_local = False
    if ngrok_available:
        ngrok_host = urlparse(ngrok_url).hostname
        request_host = request.host.split(':')[0]
        if ngrok_host and ngrok_host == request_host:
            is_on_ngrok = True
        else:
            local_ip = get_local_ip()
            if request_host == local_ip or request_host in ['127.0.0.1', 'localhost']:
                is_on_local = True

    is_on_local_with_ngrok_available = is_on_local and ngrok_available

    # The qr_url generation correctly uses the request context, so it will be an
    # ngrok url if accessed via ngrok, and a local url otherwise.
    scheme = "https" if (request.is_secure or request.headers.get("X-Forwarded-Proto", "http") == "https") else "http"
    qr_url = url_for("scan", token=token, _external=True, _scheme=scheme)
    qr_b64 = make_qr_png_b64(qr_url)

    message = "Scan this QR with your phone to approve this session."
    if ngrok_available:
        message = "Choose local (same network) or online (anywhere) and scan the QR."

    return render_template("login.html",
                                   qr_b64=qr_b64,
                                   qr_url=qr_url,
                                   token=token,
                                   ngrok_available=ngrok_available,
                                   message=message,
                                   login_code=login_code,
                                   error=error,
                                   is_on_ngrok=is_on_ngrok,
                                   is_on_local_with_ngrok_available=is_on_local_with_ngrok_available,
                                   authed=is_authed(),
                                   icon=None,
                                   user_label="",
                                   current_rel="",
                                   dhikr="",
                                   dhikr_list=[],
                                   is_admin=False)

@app.route("/login_with_default")
def login_with_default():
    device_id = request.cookies.get(DEVICE_COOKIE_NAME)

    # If the device has a default folder mapped, check if it's the admin
    if device_id and device_id in app.config["DEVICE_MAP"]:
        folder = app.config["DEVICE_MAP"][device_id].get("folder")
        if folder and is_admin_device_of(folder):
            # If admin, log them into their default account
            session["authed"] = True
            session["folder"] = folder
            session["icon"] = get_user_icon(folder)
            resp = make_response(redirect(url_for("browse", subpath=folder)))
            # The cookie is already correct, no need to set it again
            return resp

    # In all other cases (no cookie, no mapped folder, or not admin of the folder),
    # create a brand new account and associate it with a new device ID.
    new_device_id = secrets.token_urlsafe(12)
    new_folder = ensure_unique_folder_name()
    (ROOT_DIR / new_folder).mkdir(parents=True, exist_ok=True)

    # Map the new device ID to the new folder
    app.config["DEVICE_MAP"][new_device_id] = {"folder": new_folder, "created": datetime.utcnow().isoformat() + "Z"}
    save_device_map(app.config["DEVICE_MAP"])

    # Assign this new device as the admin of the new folder
    cfg = get_user_cfg(new_folder)
    cfg["admin_device"] = new_device_id
    save_users(app.config["USERS"])

    # Log the user into their new account
    session["authed"] = True
    session["folder"] = new_folder
    session["icon"] = get_user_icon(new_folder)

    resp = make_response(redirect(url_for("browse", subpath=new_folder)))
    resp.set_cookie(DEVICE_COOKIE_NAME, new_device_id, max_age=60*60*24*730, samesite="Lax")
    return resp

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
    return render_template("unlock.html", error=error, next_url=next_url, authed=False, icon=None, user_label="", current_rel="", dhikr="", dhikr_list=[], is_admin=False, token=None)

@app.route("/check/<token>")
def check_login(token: str):
    info = pending_sessions.get(token)
    if not info:
        return jsonify({"authenticated": False})
    if info["authenticated"]:
        pc_token = info.get("pc_token")
        pc_url = None
        if pc_token and info.get("folder"):
            app.config["LOGIN_TOKENS"][pc_token] = {"folder": info["folder"]}
            pc_url = url_for("pc_login", token=pc_token)
        return jsonify({"authenticated": True, "folder": info.get("folder"), "icon": info.get("icon"), "url": pc_url})
    return jsonify({"authenticated": False})

@app.route("/login_with_code", methods=["POST"])
def login_with_code():
    code = request.form.get("code", "").strip()
    if not code or not code.isdigit() or len(code) != 6:
        return redirect(url_for("login", error="Invalid code format. Please enter a 6-digit code."))

    # 1. Check for temporary codes in pending_sessions
    found_token = None
    for token, info in pending_sessions.items():
        if info.get("login_code") == code:
            # To prevent replay attacks, let's remove the code once it's used.
            # The session will be authenticated by the scan endpoint.
            info.pop("login_code", None)
            found_token = token
            break

    if found_token:
        # Found a temporary code, mimic the /scan/<token> logic by redirecting to it.
        # This will log in the current device and also allow the original device to poll and log in.
        return redirect(url_for("scan", token=found_token))

    # 2. Check for permanent codes in users.json
    users = app.config.setdefault("USERS", load_users())
    found_folder = None
    for folder, user_data in users.items():
        if user_data.get("permanent_code") == code:
            found_folder = folder
            break

    if found_folder:
        # Found a permanent code, log this device in directly.
        device_id, _ = get_or_create_device_folder(request)

        # This device becomes associated with this user folder now.
        app.config["DEVICE_MAP"][device_id] = {"folder": found_folder, "created": datetime.utcnow().isoformat() + "Z"}
        save_device_map(app.config["DEVICE_MAP"])

        session["authed"] = True
        session["folder"] = found_folder
        session["icon"] = get_user_icon(found_folder)

        resp = make_response(redirect(url_for("browse", subpath=found_folder)))
        resp.set_cookie(DEVICE_COOKIE_NAME, device_id, max_age=60*60*24*730, samesite="Lax")
        return resp

    # 3. If no code is found
    return redirect(url_for("login", error="Invalid or expired code."))


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
    token_data = app.config["LOGIN_TOKENS"].pop(token, None)
    if not token_data:
        abort(403)

    folder = token_data.get("folder")
    if not folder:
        abort(403)

    device_id = token_data.get("device_id")
    next_url = token_data.get("next_url") or url_for("browse")

    # If no device_id was passed (i.e., QR login), get or create one for the current device.
    if not device_id:
        device_id = request.cookies.get(DEVICE_COOKIE_NAME)
        if not device_id:
            device_id = secrets.token_urlsafe(12)

    # For all login types, ensure this device is mapped to the correct folder.
    # This correctly handles new device logins and session transfers.
    app.config["DEVICE_MAP"][device_id] = {"folder": folder, "created": datetime.utcnow().isoformat() + "Z"}
    save_device_map(app.config["DEVICE_MAP"])
    (ROOT_DIR / folder).mkdir(parents=True, exist_ok=True)

    session["authed"] = True
    session["folder"] = folder
    session["icon"] = get_user_icon(folder)

    resp = make_response(redirect(next_url))
    resp.set_cookie(DEVICE_COOKIE_NAME, device_id, max_age=60*60*24*730, samesite="Lax")
    return resp

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

    accounts_count = 0
    if is_admin:
        users = app.config.setdefault("USERS", load_users())
        accounts_count = sum(1 for f, c in users.items() if c.get("admin_device") == device_id)

    return render_template(
        "browse.html",
        entries=items,
        stats=stats,
        since=since,
        accounts_count=accounts_count,
        authed=True,
        icon=session.get("icon"),
        user_label=session.get("folder",""),
        current_rel=(path_rel(dest) if dest != ROOT_DIR else ""),
        dhikr=dhikr,
        dhikr_list=dhikr_list,
        is_admin=is_admin,
        share_page_active=False
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

@app.route("/api/config")
def api_config():
    local_ip = get_local_ip()
    server_url = get_ngrok_url()
    local_url_full = f"http://{local_ip}:{PORT}"

    return jsonify({
        "ok": True,
        "local_url": local_url_full,
        "server_url": server_url or "" # Return empty string if no ngrok URL
    })

@app.route("/api/me")
def api_me():
    if not is_authed():
        return jsonify({"ok": False, "error": "not authed"}), 401
    folder = session.get("folder")
    cfg = get_user_cfg(folder)
    device_id = request.cookies.get(DEVICE_COOKIE_NAME)
    is_admin = bool(device_id and device_id == cfg.get("admin_device"))
    return jsonify({
        "ok": True,
        "folder": folder,
        "public": cfg.get("public", True),
        "has_password": bool(cfg.get("password_hash")),
        "prefs": cfg.get("prefs", {}),
        "is_admin": is_admin,
        "permanent_code": cfg.get("permanent_code")
    })

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
    base_folder = None
    authed_by = None

    # Priority 1: Check for session-based authentication
    if session.get("authed"):
        base_folder = session.get("folder")
        authed_by = "session"

    # Priority 2: Check for Authorization header (Bearer token)
    else:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            user = get_user_by_token(token)
            if user:
                base_folder = user.get("folder")
                authed_by = "token"

    if not base_folder:
        return jsonify({"ok": False, "error": "not authed"}), 401

    dest_rel = request.form.get("dest", "")
    # If dest_rel is empty (e.g., from the token-based share page),
    # default to the user's base folder.
    if not dest_rel:
        dest_rel = base_folder

    dest_dir = safe_path(dest_rel)

    # Ensure the destination is within the authenticated user's folder
    if first_segment(path_rel(dest_dir)) != base_folder:
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
    ngrok_available = bool(get_ngrok_url())
    login_code = None

    # If a specific token is provided, create a URL with that token
    if access_token:
        ngrok_url = get_ngrok_url()
        if mode == "online" and ngrok_url:
            qr_url = f"{ngrok_url}/login?token={access_token}"
        else:
            ip = get_local_ip()
            qr_url = f"http://{ip}:{PORT}/login?token={access_token}"
    # Otherwise, generate a temporary session token for QR login
    else:
        token = str(uuid.uuid4())
        pc_token = secrets.token_urlsafe(16)
        login_code = generate_temp_code()
        pending_sessions[token] = {
            "authenticated": False,
            "folder": session.get("folder"),
            "icon": session.get("icon"),
            "pc_token": pc_token,
            "login_code": login_code,
        }

        ngrok_url = get_ngrok_url()
        if mode == "online" and ngrok_url:
            qr_url = f"{ngrok_url}/scan/{token}"
        else:
            ip = get_local_ip()
            qr_url = f"http://{ip}:{PORT}/scan/{token}"

    qr_b64 = make_qr_png_b64(qr_url)
    return jsonify({
        "ok": True,
        "b64": qr_b64,
        "url": qr_url,
        "ngrok_available": ngrok_available,
        "login_code": login_code
    })

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

    moved_items_for_socket = []
    moved_files_for_response = []
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
            new_meta = get_file_meta(target_path)
            moved_items_for_socket.append({
                "from_rel": rel_path,
                "meta": new_meta
            })
            moved_files_for_response.append({"from": rel_path, "to": path_rel(target_path)})
        except Exception as e:
            errors.append({"path": rel_path, "error": str(e)})

    if moved_items_for_socket:
        socketio.emit("file_update", {
            "action": "moved",
            "items": moved_items_for_socket,
            "dir": destination
        })

    return jsonify({"ok": len(moved_files_for_response) > 0, "moved": moved_files_for_response, "errors": errors})

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
# The /share route has been removed. The share page is now a static file
# at /static/share.html, making it fully independent from the server and
# capable of loading offline. Authentication for uploads is handled via
# API tokens stored in the client's IndexedDB.


# Error handlers: redirect to login on not found/forbidden
# -----------------------------
@app.after_request
def add_security_headers(response):
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

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
    socketio.run(app, host="0.0.0.0", port=PORT, debug=False, allow_unsafe_werkzeug=True)
