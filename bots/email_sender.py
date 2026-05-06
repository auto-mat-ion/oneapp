import json
import os
import signal
import random
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import deque
import msal
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from email_validator import validate_email, EmailNotValidError

INPUT_DIR = Path("input_data")
ACCOUNTS_FILE = INPUT_DIR / "accounts.txt"
HYPERLINK_TEXT_FILE = INPUT_DIR / "hyperlink_text.txt"
LINKS_FILE = INPUT_DIR / "links.txt"
RECIPIENTS_FILE = INPUT_DIR / "recipients.txt"
SUBJECTS_FILE = INPUT_DIR / "subjects.txt"
TEXTS_FILE = INPUT_DIR / "texts.txt"
MSAL_CACHE_FILE = INPUT_DIR / "msal_cache.bin"
SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"


def _load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _get_email_sender_settings() -> dict:
    settings = _load_settings().get("email_sender", {})
    return settings if isinstance(settings, dict) else {}


_EMAIL_SENDER_SETTINGS = _get_email_sender_settings()
COUNTRY = str(_EMAIL_SENDER_SETTINGS.get("COUNTRY", "")).strip()

FIRST_BATCH_BCC = int(_EMAIL_SENDER_SETTINGS.get("FIRST_BATCH_BCC", 9))
SUBSEQUENT_BATCH_BCC = int(_EMAIL_SENDER_SETTINGS.get("SUBSEQUENT_BATCH_BCC", 329))
SUBSEQUENT_BATCHES = int(_EMAIL_SENDER_SETTINGS.get("SUBSEQUENT_BATCHES", 3))
MAX_CONCURRENT_BATCHES = int(_EMAIL_SENDER_SETTINGS.get("MAX_CONCURRENT_BATCHES", 4))
MAX_CONCURRENT_ACCOUNTS = int(_EMAIL_SENDER_SETTINGS.get("MAX_CONCURRENT_ACCOUNTS", 10))
BATCH_DELAY_MIN = float(_EMAIL_SENDER_SETTINGS.get("BATCH_DELAY_MIN", 1.0))
BATCH_DELAY_MAX = float(_EMAIL_SENDER_SETTINGS.get("BATCH_DELAY_MAX", 3.0))
STAGGER_MIN = float(_EMAIL_SENDER_SETTINGS.get("STAGGER_MIN", 0.3))
STAGGER_MAX = float(_EMAIL_SENDER_SETTINGS.get("STAGGER_MAX", 1.0))
SAVE_TO_SENT = str(_EMAIL_SENDER_SETTINGS.get("SAVE_TO_SENT", False)).lower() == "true"
CLIENT_ID = str(
    _EMAIL_SENDER_SETTINGS.get("CLIENT_ID", "e62beeb7-8a9b-4637-b57f-f8601c0d13f5")
)

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "email_sender.log"
PROCESSED_FILE = LOG_DIR / "processed_accounts.txt"
FAILED_FILE = LOG_DIR / "failed_accounts.txt"
SENT_RECIPIENTS_FILE = LOG_DIR / "sent_recipients.txt"


FIRST_BATCH_BCC = int(os.getenv("FIRST_BATCH_BCC", "9"))
SUBSEQUENT_BATCH_BCC = int(os.getenv("SUBSEQUENT_BATCH_BCC", "329"))
SUBSEQUENT_BATCHES = int(os.getenv("SUBSEQUENT_BATCHES", "3"))
MAX_CONCURRENT_BATCHES = int(os.getenv("MAX_CONCURRENT_BATCHES", "4"))
MAX_CONCURRENT_ACCOUNTS = int(os.getenv("MAX_CONCURRENT_ACCOUNTS", "10"))
BATCH_DELAY_MIN = float(os.getenv("BATCH_DELAY_MIN", "1.0"))
BATCH_DELAY_MAX = float(os.getenv("BATCH_DELAY_MAX", "3.0"))
STAGGER_MIN = float(os.getenv("STAGGER_MIN", "0.3"))
STAGGER_MAX = float(os.getenv("STAGGER_MAX", "1.0"))
SAVE_TO_SENT = os.getenv("SAVE_TO_SENT", "false").lower() == "true"

GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["https://graph.microsoft.com/.default"]
CLIENT_ID = "e62beeb7-8a9b-4637-b57f-f8601c0d13f5"


_log_lock = threading.Lock()
_recipient_lock = threading.Lock()
_content_lock = threading.Lock()
_file_lock = threading.Lock()
_cache_lock = threading.Lock()
_stats_lock = threading.Lock()

_shared_cache = msal.SerializableTokenCache()
_shutdown = threading.Event()


_BASIC_RE = re.compile(r".+@.+\..+")


def _is_valid_email(email: str) -> tuple[bool, str]:
    if not _BASIC_RE.match(email):
        return False, email
    try:
        valid = validate_email(email, check_deliverability=False)
        return True, valid.normalized
    except EmailNotValidError:
        return False, email


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    full_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console_line = f"[{ts}] {msg}"
    file_line = f"[{full_ts}] {msg}"
    with _log_lock:
        print(console_line)
        try:
            LOG_DIR.mkdir(exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(file_line + "\n")
        except Exception:
            pass


def _signal_handler(sig, frame):
    if not _shutdown.is_set():
        log("⚠ Shutdown requested (Ctrl+C). Finishing current accounts...")
        _shutdown.set()


signal.signal(signal.SIGINT, _signal_handler)
try:
    signal.signal(signal.SIGBREAK, _signal_handler)
except AttributeError:
    pass


def load_cache():
    if MSAL_CACHE_FILE.exists():
        try:
            with open(MSAL_CACHE_FILE, "r", encoding="utf-8") as f:
                _shared_cache.deserialize(f.read())
            log(f"Cache loaded: {MSAL_CACHE_FILE}")
        except Exception as e:
            log(f"Cache load error: {e}")
    else:
        log(f"Warning: no cache file ({MSAL_CACHE_FILE})")


def save_cache():
    with _cache_lock:
        if _shared_cache.has_state_changed:
            try:
                with open(MSAL_CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(_shared_cache.serialize())
            except Exception:
                pass


def _load_db_config() -> dict:
    settings_path = Path(__file__).resolve().parent / "settings.json"
    config = {}
    try:
        with open(settings_path, "r", encoding="utf-8") as handle:
            config = json.load(handle).get("app", {})
    except Exception:
        pass

    return {
        "host": os.getenv("DB_HOST", config.get("DB_HOST", "localhost")),
        "user": os.getenv("DB_USER", config.get("DB_USER", "root")),
        "password": os.getenv("DB_PASSWORD", config.get("DB_PASSWORD", "")),
        "database": os.getenv("DB_NAME", config.get("DB_NAME", "oneapp")),
        "charset": "utf8mb4",
        "use_unicode": True,
    }


def _get_db_connection():
    try:
        import mysql.connector
    except ImportError:
        return None

    try:
        return mysql.connector.connect(**_load_db_config())
    except Exception as exc:
        log(f"Error: unable to connect to database: {exc}")
        return None


def get_token(email: str) -> Optional[str]:
    try:
        with _cache_lock:
            app = msal.PublicClientApplication(
                client_id=CLIENT_ID,
                authority=AUTHORITY,
                token_cache=_shared_cache,
            )
            matching = None
            for acc in app.get_accounts():
                if acc.get("username", "").lower() == email.lower():
                    matching = acc
                    break

            if not matching:
                return None

            result = app.acquire_token_silent(scopes=SCOPES, account=matching)

        if result and "access_token" in result:
            save_cache()
            return result["access_token"]

        return None
    except Exception:
        return None


def refresh_token(email: str) -> Optional[str]:
    try:
        with _cache_lock:
            app = msal.PublicClientApplication(
                client_id=CLIENT_ID,
                authority=AUTHORITY,
                token_cache=_shared_cache,
            )
            matching = None
            for acc in app.get_accounts():
                if acc.get("username", "").lower() == email.lower():
                    matching = acc
                    break

            if not matching:
                return None

            result = app.acquire_token_silent(
                scopes=SCOPES, account=matching, force_refresh=True
            )

        if result and "access_token" in result:
            save_cache()
            return result["access_token"]
        return None
    except Exception:
        return None


_SPIN_RE = re.compile(r"\{([^{}]+)\}")


def spin(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = _SPIN_RE.sub(
            lambda m: random.choice(m.group(1).split("|")).strip(), text
        )
    return text


class ContentManager:
    def __init__(self):
        self.hyperlinks = self._load("sender_hyperlink_text", "hyperlink_text")
        self.links = self._load("sender_link", "link")
        self.subjects = self._load("sender_subjects", "subject")
        self.texts = self._load("sender_texts", "text")
        self._idx = {"h": 0, "l": 0, "s": 0, "t": 0}
        log(
            f"Content: {len(self.hyperlinks)}h {len(self.links)}l "
            f"{len(self.subjects)}s {len(self.texts)}t from DB"
            + (f" country={COUNTRY}" if COUNTRY else "")
        )

    def _load(self, table_name: str, column_name: str) -> List[str]:
        return self._load_table_attribute(table_name, column_name, COUNTRY)

    def _load_table_attribute(
        self, table_name: str, column_name: str, country: str = ""
    ) -> List[str]:
        conn = _get_db_connection()
        if conn is None:
            log(f"Error: unable to load table {table_name} from database")
            return []

        try:
            cursor = conn.cursor()
            query = f"SELECT `{column_name}` FROM `{table_name}`"
            params = []
            if country:
                query += " WHERE country = %s"
                params.append(country)
            cursor.execute(query, params)
            rows = [
                str(row[0]).strip()
                for row in cursor.fetchall()
                if row and row[0] is not None and str(row[0]).strip()
            ]
            cursor.close()
            return rows
        except Exception as exc:
            log(f"Error: failed to load {table_name}.{column_name}: {exc}")
            return []
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def get(self) -> Tuple[str, str, str, str]:
        with _content_lock:
            h = self._next(self.hyperlinks, "h")
            l = self._next(self.links, "l")
            s = self._next(self.subjects, "s")
            t = self._next(self.texts, "t")
        return spin(h), l, spin(s), spin(t)

    def _next(self, items: List[str], key: str) -> str:
        if not items:
            return ""
        idx = self._idx[key]
        self._idx[key] = (idx + 1) % len(items)
        return items[idx]

    def is_valid(self) -> bool:
        return bool(self.subjects and self.texts and self.links and self.hyperlinks)


class RecipientManager:
    def __init__(self):
        self.queue = deque()
        self._sent_count = 0
        self._total_loaded = 0
        self._load()

    def _load(self):
        if not RECIPIENTS_FILE.exists():
            log(f"Error: {RECIPIENTS_FILE} not found")
            return

        seen = set()
        recipients = []
        invalid_count = 0
        invalid_preview = []
        MAX_PREVIEW = 5

        try:
            LOG_DIR.mkdir(exist_ok=True)
            invalid_log_path = LOG_DIR / "invalid_recipients.txt"
            invalid_log = open(invalid_log_path, "w", encoding="utf-8", buffering=1)
            invalid_log.write(f"Invalid recipients from {RECIPIENTS_FILE}\n\n")
            has_invalid_log = True
        except Exception:
            invalid_log = None
            has_invalid_log = False

        try:
            with open(RECIPIENTS_FILE, "r", encoding="utf-8", buffering=1 << 20) as f:
                for line_num, line in enumerate(f, 1):
                    original = line.rstrip("\n\r")
                    email = "".join(original.split()).lower()

                    if not email or email.startswith("#"):
                        continue

                    is_valid, normalized = _is_valid_email(email)

                    if not is_valid:
                        reason = f"Line {line_num}: Invalid format - '{original}'"
                    elif normalized in seen:
                        reason = f"Line {line_num}: Duplicate - {normalized}"
                    else:
                        seen.add(normalized)
                        recipients.append(normalized)
                        continue

                    invalid_count += 1
                    if len(invalid_preview) < MAX_PREVIEW:
                        invalid_preview.append(reason)
                    if invalid_log:
                        try:
                            invalid_log.write(reason + "\n")
                        except Exception:
                            pass
        finally:
            if invalid_log:
                try:
                    invalid_log.close()
                except Exception:
                    pass

        random.shuffle(recipients)
        self.queue.extend(recipients)
        self._total_loaded = len(recipients)

        log(
            f"✓ Loaded {len(recipients)} valid recipients (deduped, validated, shuffled)"
        )

        if invalid_count:
            log(f"⚠ Skipped {invalid_count} invalid/duplicate entries:")
            for line in invalid_preview:
                log(f"  {line}")
            if invalid_count > MAX_PREVIEW:
                log(f"  ... and {invalid_count - MAX_PREVIEW} more")
            if has_invalid_log:
                log(f"  Full list: {invalid_log_path}")

    def get_batch(self, size: int) -> List[str]:
        with _recipient_lock:
            batch = []
            for _ in range(size):
                if self.queue:
                    batch.append(self.queue.popleft())
                else:
                    break
            return batch

    def return_batch(self, batch: List[str]):
        with _recipient_lock:
            self.queue.extendleft(reversed(batch))

    def mark_sent(self, count: int):
        with _recipient_lock:
            self._sent_count += count

    def has_more(self) -> bool:
        with _recipient_lock:
            return len(self.queue) > 0

    def remaining(self) -> int:
        with _recipient_lock:
            return len(self.queue)

    @property
    def sent_count(self) -> int:
        with _recipient_lock:
            return self._sent_count

    def save_unsent(self):
        with _recipient_lock:
            remaining = list(self.queue)
        if remaining:
            with open(RECIPIENTS_FILE, "w", encoding="utf-8") as f:
                for r in remaining:
                    f.write(r + "\n")
            log(f"Saved {len(remaining)} unsent recipients to {RECIPIENTS_FILE}")
        else:
            with open(RECIPIENTS_FILE, "w", encoding="utf-8") as f:
                pass
            log("All recipients sent!")


class AccountManager:
    def __init__(self):
        self.accounts: List[Dict] = []
        self._load()

    def _load(self):
        if not ACCOUNTS_FILE.exists():
            log(f"Error: {ACCOUNTS_FILE} not found")
            return
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(",")
                if len(parts) >= 2:
                    self.accounts.append(
                        {
                            "email": parts[0].strip(),
                            "password": parts[1].strip(),
                            "recovery": parts[2].strip() if len(parts) > 2 else "",
                            "creation_date": parts[3].strip() if len(parts) > 3 else "",
                        }
                    )
        log(f"Accounts: {len(self.accounts)}")

    def mark_done(self, account: Dict):
        with _file_lock:
            LOG_DIR.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
                creation_date = account.get("creation_date", "")
                f.write(
                    f"{account['email']:40s} | {account['password']:20s} | {account.get('recovery', ''):30s} | {creation_date:15s} | {ts}\n"
                )

    def mark_failed(self, account: Dict, reason: str):
        with _file_lock:
            LOG_DIR.mkdir(exist_ok=True)
            clean = reason.replace("\n", " ").replace(",", ";")[:150]
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            recovery = account.get("recovery", "")
            creation_date = account.get("creation_date", "")
            with open(FAILED_FILE, "a", encoding="utf-8") as f:
                f.write(
                    f"{account['email']:40s} | {account['password']:20s} | {recovery:30s} | {creation_date:15s} | {clean:50s} | {ts}\n"
                )

    def save_remaining(self, remaining: List[Dict]):
        with _file_lock:
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                for a in remaining:
                    f.write(
                        f"{a['email']},{a['password']},{a['recovery']},{a.get('creation_date', '')}\n"
                    )


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["POST"],
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    return s


FATAL_ERRORS = {
    "ACCOUNT_SUSPENDED",
    "MAILBOX_NOT_FOUND",
    "MAILBOX_DISABLED",
    "SMS_VERIFICATION_REQUIRED",
    "UNUSUAL_ACTIVITY_VERIFICATION",
    "PHONE_VERIFICATION_REQUIRED",
}
TOKEN_ERRORS = {"TOKEN_EXPIRED"}


def send_email(
    session: requests.Session,
    token: str,
    from_email: str,
    to_email: str,
    bcc_list: List[str],
    subject: str,
    body_html: str,
) -> Tuple[bool, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body_html},
            "toRecipients": [{"emailAddress": {"address": to_email}}],
            "bccRecipients": [{"emailAddress": {"address": e}} for e in bcc_list],
        },
        "saveToSentItems": "true" if SAVE_TO_SENT else "false",
    }

    try:
        r = session.post(
            f"{GRAPH_ENDPOINT}/users/{from_email}/sendMail",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if r.status_code == 202:
            return True, ""

        body = r.text[:300] if r.text else ""

        if r.status_code == 429:
            for attempt in range(1):
                wait = min(
                    int(r.headers.get("Retry-After", str(5 * (attempt + 1)))), 60
                )
                log(f"    ⏳ throttled, wait {wait}s (retry {attempt + 1}/1)")
                time.sleep(wait)
                r = session.post(
                    f"{GRAPH_ENDPOINT}/users/{from_email}/sendMail",
                    headers=headers,
                    json=payload,
                    timeout=30,
                )
                if r.status_code == 202:
                    return True, ""
                if r.status_code != 429:
                    break
            return False, f"THROTTLE_FAIL:{r.status_code}"

        if r.status_code == 401:
            return False, "TOKEN_EXPIRED"
        if r.status_code == 403:
            if "AccountSuspend" in body:
                return False, "ACCOUNT_SUSPENDED"
            if "MailboxDisabled" in body or "MailboxInactive" in body:
                return False, "MAILBOX_DISABLED"
            if "ProofupRequired" in body or "EnforceProofUp" in body:
                return False, "SMS_VERIFICATION_REQUIRED"
            if "UnusualActivity" in body or "SuspiciousActivity" in body:
                return False, "UNUSUAL_ACTIVITY_VERIFICATION"
            return False, f"FORBIDDEN:{body[:60]}"
        if r.status_code == 404 or "MailboxNotFound" in body:
            return False, "MAILBOX_NOT_FOUND"
        if r.status_code == 452 or "ExceededMaxRecipient" in body:
            return False, "RECIPIENT_LIMIT"
        if "MessageSubmissionBlocked" in body:
            return False, "SEND_BLOCKED"
        if "VerifyPhone" in body or "PhoneVerification" in body:
            return False, "PHONE_VERIFICATION_REQUIRED"

        return False, f"HTTP_{r.status_code}:{body[:60]}"

    except requests.exceptions.Timeout:
        return False, "TIMEOUT"
    except requests.exceptions.ConnectionError:
        return False, "CONN_ERROR"
    except Exception as e:
        return False, f"ERR:{str(e)[:60]}"


def build_html(text: str, hyperlink: str, link: str) -> str:
    text = text.replace("\n", "<br>")
    return (
        f'<html><body><div style="font-family:Arial,sans-serif;'
        f'font-size:14px;color:#333;">{text}<br><br>'
        f'<a href="{link}">{hyperlink}</a></div></body></html>'
    )


def _short(email: str) -> str:
    local = email.split("@")[0]
    return local[:8] + ".." if len(local) > 10 else local


def log_sent(recipients: List[str]):
    try:
        with _file_lock:
            LOG_DIR.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(SENT_RECIPIENTS_FILE, "a", encoding="utf-8") as f:
                for r in recipients:
                    f.write(f"{r:40s} | {ts}\n")
    except Exception:
        pass


def process_account(
    account: Dict,
    recipients: RecipientManager,
    content: ContentManager,
    session: requests.Session,
) -> Tuple[bool, int, str]:
    email = account["email"]
    sent = 0

    token = get_token(email)
    if not token:
        log(f"  ✗ {_short(email)}: not in cache / token failed")
        return False, 0, "AUTH_FAILED"

    log(f"  ✓ {_short(email)}: token OK")

    warmup = recipients.get_batch(FIRST_BATCH_BCC + 1)
    if not warmup:
        return True, 0, ""

    h, link, subj, body = content.get()
    html = build_html(body, h, link)
    ok, err = send_email(session, token, email, warmup[0], warmup[1:], subj, html)

    if not ok:
        log(f"  ✗ {_short(email)} warmup: {err}")
        recipients.return_batch(warmup)

        if err in FATAL_ERRORS:
            return False, 0, err

        if err in TOKEN_ERRORS:
            token = refresh_token(email)
            if not token:
                return False, 0, "TOKEN_REFRESH_FAILED"
            log(f"  ↻ {_short(email)}: token refreshed, retrying warmup")
            warmup = recipients.get_batch(FIRST_BATCH_BCC + 1)
            if not warmup:
                return True, 0, ""
            h, link, subj, body = content.get()
            html = build_html(body, h, link)
            ok, err = send_email(
                session, token, email, warmup[0], warmup[1:], subj, html
            )
            if not ok:
                recipients.return_batch(warmup)
                return False, 0, f"WARMUP_RETRY_FAIL:{err}"

        if not ok:
            return False, 0, f"WARMUP_FAIL:{err}"

    sent += len(warmup)
    recipients.mark_sent(len(warmup))
    log_sent(warmup)
    log(f"  ✓ {_short(email)} warmup: {len(warmup)} rcpts")

    if _shutdown.is_set():
        return (sent > 0), sent, ""

    time.sleep(random.uniform(BATCH_DELAY_MIN, BATCH_DELAY_MAX))

    batches = []
    for i in range(SUBSEQUENT_BATCHES):
        if not recipients.has_more() or _shutdown.is_set():
            break
        batch = recipients.get_batch(SUBSEQUENT_BATCH_BCC + 1)
        if batch:
            batches.append((batch, f"b{i + 2}"))

    if not batches:
        return (sent > 0), sent, ""

    account_fatal = False
    token_cell = [token]

    def send_with_fresh_token(email, to, bcc, subj, html):
        batch_session = make_session()
        try:
            return send_email(batch_session, token_cell[0], email, to, bcc, subj, html)
        finally:
            batch_session.close()

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_BATCHES) as pool:
        futures = {}
        for idx, (batch, label) in enumerate(batches):
            h, link, subj, body = content.get()
            html = build_html(body, h, link)
            if idx > 0:
                time.sleep(random.uniform(STAGGER_MIN, STAGGER_MAX))
            f = pool.submit(
                send_with_fresh_token, email, batch[0], batch[1:], subj, html
            )
            futures[f] = (batch, label)

        for f in as_completed(futures):
            batch, label = futures[f]
            try:
                ok, err = f.result()
                if ok:
                    sent += len(batch)
                    recipients.mark_sent(len(batch))
                    log_sent(batch)
                    log(f"  ✓ {_short(email)} {label}: {len(batch)} rcpts")
                else:
                    log(f"  ✗ {_short(email)} {label}: {err}")
                    recipients.return_batch(batch)

                    if err in FATAL_ERRORS:
                        account_fatal = True
                    elif err in TOKEN_ERRORS:
                        new_token = refresh_token(email)
                        if new_token:
                            token_cell[0] = new_token
                            log(f"  ↻ {_short(email)}: token refreshed")
                        else:
                            account_fatal = True
            except Exception as e:
                log(f"  ✗ {_short(email)} {label}: exception")
                recipients.return_batch(batch)

    if account_fatal:
        return (sent > 0), sent, "ACCOUNT_FATAL_MID_SESSION"

    return (sent > 0), sent, ""


class StatsTracker:
    def __init__(self, total_accounts: int, total_recipients: int):
        self.total_accounts = total_accounts
        self.total_recipients = total_recipients
        self.total_sent = 0
        self.ok_count = 0
        self.fail_count = 0
        self.processed_accounts = []
        self.start_time = time.time()

    def update(self, account: Dict, success: bool, sent: int):
        with _stats_lock:
            if success:
                self.ok_count += 1
            else:
                self.fail_count += 1
            self.total_sent += sent
            self.processed_accounts.append(account)

    def get_stats(self) -> Dict:
        with _stats_lock:
            elapsed = time.time() - self.start_time
            rate = self.total_sent / elapsed if elapsed > 0 else 0
            return {
                "total_sent": self.total_sent,
                "ok_count": self.ok_count,
                "fail_count": self.fail_count,
                "rate": rate,
                "elapsed": elapsed,
                "processed_count": len(self.processed_accounts),
            }

    def get_processed(self) -> List[Dict]:
        with _stats_lock:
            return self.processed_accounts.copy()


def process_account_wrapper(
    account: Dict,
    account_idx: int,
    total_accounts: int,
    recipients: RecipientManager,
    content: ContentManager,
    accounts_manager: AccountManager,
    stats: StatsTracker,
) -> Dict:
    if _shutdown.is_set():
        return {"skipped": True}

    if not recipients.has_more():
        return {"skipped": True}

    log(f"[{account_idx + 1}/{total_accounts}] {account['email']}")

    session = make_session()

    try:
        success, sent, error = process_account(account, recipients, content, session)
    except Exception as e:
        log(f"  ✗ CRASH: {str(e)[:80]}")
        success, sent, error = False, 0, f"CRASH:{str(e)[:80]}"
    finally:
        session.close()

    if success:
        accounts_manager.mark_done(account)
    else:
        accounts_manager.mark_failed(account, error)

    stats.update(account, success, sent)

    current_stats = stats.get_stats()
    left = recipients.remaining()
    log(
        f"  📊 {current_stats['total_sent']}/{stats.total_recipients} sent | "
        f"✓{current_stats['ok_count']} ✗{current_stats['fail_count']} | "
        f"{current_stats['rate']:.1f}/s | {left} left"
    )

    return {"account": account, "success": success, "sent": sent, "error": error}


def main():
    log("=" * 55)
    log("EMAIL SENDER | Graph API")
    log(
        f"Config: warmup={FIRST_BATCH_BCC + 1} big={SUBSEQUENT_BATCHES}x"
        f"{SUBSEQUENT_BATCH_BCC + 1} batch_threads={MAX_CONCURRENT_BATCHES}"
    )
    log(f"        account_threads={MAX_CONCURRENT_ACCOUNTS}")
    log("=" * 55)

    accounts = AccountManager()
    recipients = RecipientManager()
    content = ContentManager()
    load_cache()

    if not accounts.accounts:
        log("✗ No accounts. Exiting.")
        return
    if not recipients.queue:
        log("✗ No recipients. Exiting.")
        return
    if not content.is_valid():
        log("✗ Missing content (need subjects, texts, links). Exiting.")
        return

    total_acc = len(accounts.accounts)
    total_rcpt = recipients._total_loaded
    max_per_account = (FIRST_BATCH_BCC + 1) + SUBSEQUENT_BATCHES * (
        SUBSEQUENT_BATCH_BCC + 1
    )
    est_accounts_needed = (total_rcpt + max_per_account - 1) // max_per_account

    log(f"Ready: {total_acc} accounts | {total_rcpt} recipients")
    log(f"Max/account: {max_per_account} | Est. accounts needed: {est_accounts_needed}")
    log("-" * 55)

    stats = StatsTracker(total_acc, total_rcpt)

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_ACCOUNTS) as executor:
        futures = {}

        for i, account in enumerate(accounts.accounts):
            if _shutdown.is_set():
                log("Shutdown: not submitting more accounts...")
                break

            if not recipients.has_more():
                log("All recipients consumed (pre-check).")
                break

            if i > 0:
                time.sleep(random.uniform(STAGGER_MIN, STAGGER_MAX))

            future = executor.submit(
                process_account_wrapper,
                account,
                i,
                total_acc,
                recipients,
                content,
                accounts,
                stats,
            )
            futures[future] = account

        for future in as_completed(futures):
            result = future.result()

            if _shutdown.is_set():
                log("Shutdown: waiting for remaining accounts...")

            if result.get("skipped"):
                continue

    processed = stats.get_processed()
    unused = [a for a in accounts.accounts if a not in processed]
    accounts.save_remaining(unused)

    recipients.save_unsent()

    final_stats = stats.get_stats()

    log("")
    log("=" * 55)
    log("DONE")
    log(f"  Sent:       {final_stats['total_sent']}/{total_rcpt}")
    log(
        f"  Accounts:   ✓{final_stats['ok_count']} ✗{final_stats['fail_count']} (unused: {len(unused)})"
    )
    log(f"  Time:       {final_stats['elapsed']:.1f}s ({final_stats['rate']:.1f}/s)")
    log(f"  Remaining:  {recipients.remaining()} recipients")
    if final_stats["fail_count"]:
        log(f"  Failures:   {FAILED_FILE}")
    log("=" * 55)


# if __name__ == "__main__":
#     main()
