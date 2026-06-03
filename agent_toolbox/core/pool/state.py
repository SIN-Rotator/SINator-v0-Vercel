"""Pool State mixin.

Docs: state.doc.md
"""
import json
import re
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class PoolManagerStateMixin:
    """Auto-generated mixin from pool_manager.py split."""

    def _load(self):
        """Lädt den Pool aus der JSON-Datei.

        Auto-Recovery (V19.8): Wenn die JSON-Datei fehlt aber das macOS
        Keychain Einträge hat, wird der Pool aus dem Keychain rekonstruiert
        (siehe tools/recover_pool.py). Verhindert "Pool tot" Dashboard-Fehler
        wenn ein Sync-Tool die JSON-Datei löscht.
        """
        if self.pool_path.exists():
            try:
                with open(self.pool_path, "r") as f:
                    raw = json.load(f)
                # Handle both formats: {"accounts": [...]} (old) or [...] (new)
                if isinstance(raw, list):
                    self.keys = raw
                elif isinstance(raw, dict) and "accounts" in raw:
                    self.keys = raw["accounts"]
                else:
                    self.keys = []
                logger.info(f"{len(self.keys)} API-Keys aus Pool geladen")
            except Exception as e:
                logger.error(f"Pool-Laden fehlgeschlagen: {e}")
                self.keys = []
        else:
            # V19.8: Try auto-recovery from macOS Keychain
            recovered = self._try_recover_from_keychain()
            if recovered is not None:
                self.keys = recovered
            else:
                logger.info("Kein Pool gefunden, erstelle neuen")
                self.keys = []

    def _try_recover_from_keychain(self) -> Optional[List[Dict[str, Any]]]:
        """V19.8: Reconstruct pool entries from macOS Keychain if possible.

        Returns:
            List of recovered key entries, or None if recovery failed.
        Side effect: writes the recovered pool to disk.
        """
        try:
            import subprocess
            result = subprocess.run(
                ["security", "dump-keychain"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                return None

            accounts: List[str] = []
            capture_next = False
            for line in result.stdout.splitlines():
                if '"svce"<blob>="com.sinator.pool"' in line:
                    capture_next = True
                    continue
                if capture_next and '"acct"<blob>=' in line:
                    start = line.index('"acct"<blob>="') + len('"acct"<blob>="')
                    end = line.index('"', start)
                    accounts.append(line[start:end])
                    capture_next = False

            if not accounts:
                return None

            # V19.13: Reject non-UUID entries (ghost IDs from botched recovery)
            filtered = [aid for aid in accounts if UUID_RE.match(aid)]
            if len(filtered) != len(accounts):
                rejected_count = len(accounts) - len(filtered)
                logger.warning(
                    f"V19.13: Filtered out {rejected_count} non-UUID ghost IDs "
                    f"from keychain recovery"
                )
                for aid in accounts:
                    if not UUID_RE.match(aid):
                        logger.warning(f"  -> rejected: {aid[:60]}")
                accounts = filtered

            if not accounts:
                return None

            now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            entries: List[Dict[str, Any]] = []
            for aid in accounts:
                short = aid.split("-")[0] if "-" in aid else aid[:8]
                entries.append({
                    "id": aid,
                    "api_key": _KEYCHAIN_SENTINEL,
                    "alias_email": f"recovered-{short}@unknown.local",
                    "key_name": "recovered-from-keychain",
                    "created_at": now,
                    "used": False,
                    "used_at": None,
                    "credits_initial": 6.0,
                    "credits_remaining": 6.0,
                    "credits_checked_at": None,
                    "suspended": False,
                    "recovered": True,
                    "recovery_note": "Auto-recovered from macOS Keychain (V19.8)",
                })

            self.pool_path.parent.mkdir(parents=True, exist_ok=True)
            self.pool_path.write_text(json.dumps(entries, indent=2))
            logger.warning(
                f"🚨 AUTO-RECOVERY: Pool-JSON fehlte, {len(entries)} Keys aus "
                f"macOS Keychain rekonstruiert. Original-Metadaten verloren. "
                f"Siehe tools/recover_pool.py"
            )
            return entries
        except Exception as e:
            logger.error(f"Keychain-Recovery fehlgeschlagen: {e}")
            return None

    def reload(self):
        """Lädt den Pool frisch von Disk (sync mit externen Änderungen)."""
        self._load()

    def save(self):
        """Speichert den Pool in die JSON-Datei."""
        try:
            with open(self.pool_path, "w") as f:
                json.dump(self.keys, f, indent=2)
            logger.info(f"Pool gespeichert: {len(self.keys)} Keys")
        except Exception as e:
            logger.error(f"Pool-Speichern fehlgeschlagen: {e}")

