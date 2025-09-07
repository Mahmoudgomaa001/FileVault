import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import random
import string

class SharedStore:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        try:
            if self.file_path.exists():
                with self.file_path.open('r', encoding='utf-8') as f:
                    return json.load(f)
        except (IOError, json.JSONDecodeError):
            # If file is corrupted or empty, start fresh
            pass
        return {}

    def _save(self):
        try:
            temp_path = self.file_path.with_suffix(f".tmp{os.getpid()}")
            with temp_path.open('w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.file_path)
        except IOError as e:
            print(f"Error saving shared store: {e}")

    def cleanup(self):
        now = time.time()
        expired_keys = [
            key for key, item in self._data.items()
            if isinstance(item, dict) and item.get("expires_at") and item["expires_at"] < now
        ]
        if not expired_keys:
            return

        for key in expired_keys:
            self._data.pop(key, None)
        self._save()

    def get(self, key: str) -> dict | None:
        self._data = self._load() # Always get the latest data from disk
        item = self._data.get(key)
        if not item or not isinstance(item, dict):
            return None

        expires_at = item.get("expires_at")
        if expires_at and expires_at < time.time():
            # Item has expired, remove it and return None
            self.pop(key)
            return None

        return item.get("value")

    def set(self, key: str, value: dict, expires_in_seconds: int | None = None):
        self.cleanup() # Perform cleanup before adding new items
        expires_at = None
        if expires_in_seconds is not None:
            expires_at = time.time() + expires_in_seconds

        self._data[key] = {
            "value": value,
            "expires_at": expires_at
        }
        self._save()

    def pop(self, key: str) -> dict | None:
        self._data = self._load()
        item = self._data.pop(key, None)
        self._save()

        if not item or not isinstance(item, dict):
            return None

        expires_at = item.get("expires_at")
        if expires_at and expires_at < time.time():
            return None # Treat as not found if expired

        return item.get("value")

    def generate_unique_code(self, length=6) -> str:
        self._data = self._load()
        while True:
            code = ''.join(random.choices(string.digits, k=length))
            if code not in self._data:
                return code
