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
from urllib.parse import quote_plus

try:
    from sqlalchemy import create_engine, text
except ImportError:  # fallback if SQLAlchemy is unavailable
    create_engine = None
    text = None
import pandas as pd
import subprocess


SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"
SENDER_LOG_DIR = Path(__file__).resolve().parent.parent / "sender_logs"
LOG_FILE = SENDER_LOG_DIR / "email_sender.log"
PROCESSED_FILE = SENDER_LOG_DIR / "processed_accounts.txt"
FAILED_FILE = SENDER_LOG_DIR / "failed_accounts.txt"
SENT_RECIPIENTS_FILE = SENDER_LOG_DIR / "sent_recipients.txt"

_deferred_sent_recipients: List[str] = []
_deferred_account_updates: List[Tuple[str, datetime, str, str]] = []
_deferred_failed_accounts: List[Tuple[str, str, str, str, str, str, datetime]] = []


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

APP_SETTINGS = _load_settings().get("app")
SERVER_IP = (
    APP_SETTINGS.get("SERVER_IP", "test_ip")
    if isinstance(APP_SETTINGS, dict)
    else "test_ip"
)
BOT_TYPE = "email_sender"
BATCH_NUMBER: Optional[str] = None

FIRST_BATCH_BCC = int(_EMAIL_SENDER_SETTINGS.get("FIRST_BATCH_BCC", 9))
SUBSEQUENT_BATCH_BCC = int(_EMAIL_SENDER_SETTINGS.get("SUBSEQUENT_BATCH_BCC", 329))
SUBSEQUENT_BATCHES = int(_EMAIL_SENDER_SETTINGS.get("SUBSEQUENT_BATCHES", 3))
MAX_CONCURRENT_BATCHES = int(_EMAIL_SENDER_SETTINGS.get("MAX_CONCURRENT_BATCHES", 1))
MAX_CONCURRENT_ACCOUNTS = int(_EMAIL_SENDER_SETTINGS.get("MAX_CONCURRENT_ACCOUNTS", 4))
BATCH_DELAY_MIN = float(_EMAIL_SENDER_SETTINGS.get("BATCH_DELAY_MIN", 1.0))
BATCH_DELAY_MAX = float(_EMAIL_SENDER_SETTINGS.get("BATCH_DELAY_MAX", 1.0))
STAGGER_MIN = float(_EMAIL_SENDER_SETTINGS.get("STAGGER_MIN", 1.0))
STAGGER_MAX = float(_EMAIL_SENDER_SETTINGS.get("STAGGER_MAX", 1.0))
SAVE_TO_SENT = str(_EMAIL_SENDER_SETTINGS.get("SAVE_TO_SENT", False)).lower() == "true"
CLIENT_ID = str(
    _EMAIL_SENDER_SETTINGS.get("CLIENT_ID", "e62beeb7-8a9b-4637-b57f-f8601c0d13f5")
)


GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["https://graph.microsoft.com/.default"]
CLIENT_ID = "e62beeb7-8a9b-4637-b57f-f8601c0d13f5"


EXPRESSVPN_CMD = os.path.abspath(
    _load_settings().get("familybot").get("EXPRESSVPN_CMD")
)
THE_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
utils_dir = os.path.normpath(os.path.join(THE_BASE_DIR, "../utils"))


_log_lock = threading.Lock()
_recipient_lock = threading.Lock()
_content_lock = threading.Lock()
_file_lock = threading.Lock()
_cache_lock = threading.Lock()
_stats_lock = threading.Lock()

_shared_cache = msal.SerializableTokenCache()
_shutdown = threading.Event()


_BASIC_RE = re.compile(r".+@.+\..+")


def connect_new_random():
    try:

        def run_cmd(args):
            result = subprocess.run(
                [EXPRESSVPN_CMD] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return result.stdout.strip(), result.stderr.strip()

        def connect(location=None):
            if location:
                out, err = run_cmd(["connect", location])
            else:
                out, err = run_cmd(["connect"])
            print(f"Express vpn: {out or err}")

        def disconnect():
            out, err = run_cmd(["disconnect"])
            print(f"Express vpn: {out or err}")

        def try_int(x):
            try:
                int(x[-1])

                return True
            except:
                return False

        def parse_country(x):
            try:
                d = x.split(" ")
                return x.replace(d[-1], ""), d[-1]
            except:
                return "DADADADAD", "101"

        def get_locations():
            try:
                out, err = run_cmd(["list"])
                [i.strip() for i in out.split("\n") if try_int(i)]

                return pd.DataFrame(
                    [parse_country(i.strip()) for i in out.split("\n") if try_int(i)],
                    columns=["country", "id"],
                )
            except:
                print("Error getting country list")
                return False

        disconnect()
        time.sleep(1)
        try:
            df = pd.read_csv(os.path.join(utils_dir, "express_countries_all.csv"))
            df = get_locations()

            # df[df.country.apply(lambda x: x.lower().startswith('indonesia'))]

            rand_locations = df[
                df.country.apply(
                    lambda x: x.lower().startswith(
                        "usa" if COUNTRY.lower() == "united states" else COUNTRY.lower()
                    )
                )
            ].id.to_list()

            random_location = str(random.choice(rand_locations))
            print(f"Connecting to : {COUNTRY}")

        except:
            try:
                random_location = str(
                    random.choice(
                        pd.read_csv("utils/express_countries.csv").id.to_list()
                    )
                )
                print(f"No {COUNTRY} server found. Connecting to Netherlands server")
            except:
                locations = "93,208,156,209,81,162,219,192,193,194,175,238,160,114,63,152,112,80,57,224,223,133,195,174,111,137,196,197,113,198,164,190,107,154,37,58,199,108,101,128,117,88,115,243,232,91,163,45,79,169,181,245,125,131,100,246,240,144,141,247,241,132,20,142,242,244,140,95,271,19,283,288,270,276,265,273,17,302,299,304,292,306,9,294,18,172,278,284,293,275,165,277,286,290,161,272,6,70,74,71,280,291,54,202,305,285,301,26,155,168,281,75,295,289,297,94,282,296,298,204,1,207,2,300,287,166,303,25,279,274,143,126,184,185,21,307,186,85,147,110,118,124,56,78,130,34,150,153,104,8,103,136,7,92,210,102,99,106,33,129,182,157,29,188,122,119,36,12,134,120,187,189,4,16,212,146,96,32,31,86,145,127,121,211,35,22,23,203,11,201,89,53,178,5,15,263,90,87,139,84,239,105,176,248,249,109,264".split(
                    ","
                )
                random_location = str(random.choice(locations))
                print("Connecting to Random server")

        connect(random_location)
        time.sleep(2)
        return True
    except:
        return False


def connect_random_random():
    try:

        def run_cmd(args):
            result = subprocess.run(
                [EXPRESSVPN_CMD] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return result.stdout.strip(), result.stderr.strip()

        def connect(location=None):
            if location:
                out, err = run_cmd(["connect", location])
            else:
                out, err = run_cmd(["connect"])
            print(f"Express vpn: {out or err}")

        def disconnect():
            out, err = run_cmd(["disconnect"])
            print(f"Express vpn: {out or err}")

        def try_int(x):
            try:
                int(x[-1])

                return True
            except:
                return False

        def parse_country(x):
            try:
                d = x.split(" ")
                return x.replace(d[-1], ""), d[-1]
            except:
                return "DADADADAD", "101"

        def get_locations():
            try:
                out, err = run_cmd(["list"])
                [i.strip() for i in out.split("\n") if try_int(i)]

                return pd.DataFrame(
                    [parse_country(i.strip()) for i in out.split("\n") if try_int(i)],
                    columns=["country", "id"],
                )
            except:
                print("Error getting country list")
                return False

        disconnect()
        locations = "93,208,156,209,81,162,219,192,193,194,175,238,160,114,63,152,112,80,57,224,223,133,195,174,111,137,196,197,113,198,164,190,107,154,37,58,199,108,101,128,117,88,115,243,232,91,163,45,79,169,181,245,125,131,100,246,240,144,141,247,241,132,20,142,242,244,140,95,271,19,283,288,270,276,265,273,17,302,299,304,292,306,9,294,18,172,278,284,293,275,165,277,286,290,161,272,6,70,74,71,280,291,54,202,305,285,301,26,155,168,281,75,295,289,297,94,282,296,298,204,1,207,2,300,287,166,303,25,279,274,143,126,184,185,21,307,186,85,147,110,118,124,56,78,130,34,150,153,104,8,103,136,7,92,210,102,99,106,33,129,182,157,29,188,122,119,36,12,134,120,187,189,4,16,212,146,96,32,31,86,145,127,121,211,35,22,23,203,11,201,89,53,178,5,15,263,90,87,139,84,239,105,176,248,249,109,264".split(
            ","
        )
        random_location = str(random.choice(locations))
        print("Connecting to Random server")

        connect(random_location)
        time.sleep(2)
        return True
    except:
        return False


def _is_valid_email(email: str) -> tuple[bool, str]:
    if not _BASIC_RE.match(email):
        return False, email
    try:
        valid = validate_email(email, check_deliverability=False)
        return True, valid.normalized
    except EmailNotValidError:
        return False, email


def _ensure_sender_log_dir():
    try:
        SENDER_LOG_DIR.mkdir(exist_ok=True)
    except Exception:
        pass


def _append_to_file(path: Path, text: str):
    _ensure_sender_log_dir()
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    except Exception:
        pass


def _create_sqlalchemy_engine():
    if create_engine is None:
        return None
    config = _load_db_config()
    if not config:
        return None

    try:
        user = quote_plus(str(config.get("user", "")))
        password = quote_plus(str(config.get("password", "") or ""))
        host = config.get("host", "localhost")
        database = config.get("database", "")
        url = f"mysql+mysqlconnector://{user}:{password}@{host}/{database}?charset=utf8mb4"
        return create_engine(url, pool_pre_ping=True, future=True)
    except Exception as exc:
        log(f"Error creating SQLAlchemy engine: {exc}")
        return None


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    full_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console_line = f"[{ts}] {msg}"
    file_line = f"[{full_ts}] {msg}"
    with _log_lock:
        print(console_line)
        _append_to_file(LOG_FILE, file_line)


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
    try:
        conn = _get_db_connection()
        if conn is None:
            log("Warning: unable to connect to database for cache")
            return
        cursor = conn.cursor()
        cursor.execute("SELECT cache_bin_file FROM cache_bins")
        results = cursor.fetchall()
        cursor.close()
        conn.close()

        combined_data = {
            "Account": {},
            "IdToken": {},
            "AccessToken": {},
            "RefreshToken": {},
            "AppMetadata": {},
        }

        for result in results:
            if result and result[0]:
                temp_cache = msal.SerializableTokenCache()
                temp_cache.deserialize(result[0].decode("utf-8"))
                # _shared_cache.update(temp_cache)
                raw_data = json.loads(temp_cache.serialize())
                for category in combined_data.keys():
                    if category in raw_data:
                        combined_data[category].update(raw_data[category])

        num_accounts = len(combined_data.get("Account", {}))
        _shared_cache.deserialize(json.dumps(combined_data))

        log(
            f"Cache loaded from database: {len(results)} servers caches, {num_accounts} accounts"
        )
    except Exception as e:
        log(f"Cache load error: {e}")


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


def available_batches_for_server() -> List[str]:
    conn = _get_db_connection()
    if conn is None:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT batch FROM sender_input_accounts "
            "WHERE server_ip = %s AND COALESCE(batch, '') != '' ",
            (SERVER_IP,),
        )
        rows = [
            str(row[0]).strip()
            for row in cursor.fetchall()
            if row and row[0] is not None and str(row[0]).strip()
        ]
        cursor.close()
        return sorted(set(rows))
    except Exception as exc:
        log(f"Error: failed to load available sender batches: {exc}")
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def prompt_for_batch_selection() -> Optional[str]:
    batches = available_batches_for_server()
    if not batches:
        print(
            "No available sender batches found for this server. "
            "Please configure batch values in sender_input_accounts and sender_recipients."
        )
        return None

    print("Available sender batches for this server:")
    for idx, batch in enumerate(batches, start=1):
        print(f"  {idx}. {batch}")

    while True:
        choice = input(
            f"Select batch by number or name (1-{len(batches)}), or type 'exit' to cancel: "
        ).strip()
        if not choice:
            continue
        if choice.lower() in {"exit", "quit", "q"}:
            return None
        if choice.isdigit():
            selection = int(choice)
            if 1 <= selection <= len(batches):
                return batches[selection - 1]
            print(f"Invalid number. Enter a value between 1 and {len(batches)}.")
            continue
        if choice in batches:
            return choice
        print("Invalid batch name. Please enter one of the listed batch values.")


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
        conn = _get_db_connection()
        if conn is None:
            log("Error: unable to connect to database for recipients")
            return

        try:
            cursor = conn.cursor()
            query = (
                "SELECT recipient_email FROM sender_recipients "
                "WHERE server_ip = %s AND COALESCE(country, '') = %s "
            )
            params = [SERVER_IP, COUNTRY]
            # if BATCH_NUMBER:
            #     query += " AND batch = %s"
            #     params.append(BATCH_NUMBER)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()

            seen = set()
            recipients = []
            for row in rows:
                if not row or row[0] is None:
                    continue
                email = str(row[0]).strip().lower()
                if not email:
                    continue
                is_valid, normalized = _is_valid_email(email)
                if not is_valid or normalized in seen:
                    continue
                seen.add(normalized)
                recipients.append(normalized)

            random.shuffle(recipients)
            self.queue.extend(recipients)
            self._total_loaded = len(recipients)

            log(f"✓ Loaded {len(recipients)} valid recipients from DB")
        except Exception as exc:
            log(f"Error: failed to load recipients from database: {exc}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

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


class AccountManager:
    def __init__(self):
        self.accounts: List[Dict] = []
        self._load()

    def _load(self):
        conn = _get_db_connection()
        if conn is None:
            log("Error: unable to connect to database for accounts")
            return

        try:
            cursor = conn.cursor()
            query = (
                "SELECT email, pass, recovery FROM sender_input_accounts "
                "WHERE server_ip = %s AND COALESCE(country, '') = %s "
            )
            params = [SERVER_IP, COUNTRY]
            if BATCH_NUMBER:
                query += " AND batch = %s "
                params.append(BATCH_NUMBER)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()

            for row in rows:
                if not row or row[0] is None or row[1] is None:
                    continue
                email = str(row[0]).strip()
                password = str(row[1]).strip()
                recovery = (
                    str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
                )
                if not email or not password:
                    continue
                self.accounts.append(
                    {
                        "email": email,
                        "password": password,
                        "recovery": recovery,
                        "creation_date": "",
                    }
                )

            log(f"Accounts: {len(self.accounts)}")
        except Exception as exc:
            log(f"Error: failed to load accounts from database: {exc}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def mark_done(self, account: Dict):
        try:
            now = datetime.now()
            with _file_lock:
                _deferred_account_updates.append(
                    (account["email"], now, SERVER_IP, COUNTRY)
                )
                _append_to_file(
                    PROCESSED_FILE,
                    f"{account['email']:40s} | {account['password']:20s} | {account.get('recovery', ''):30s} | {account.get('creation_date', ''):15s} | {now.strftime('%Y-%m-%d %H:%M:%S')}",
                )
        except Exception:
            pass

    def mark_failed(self, account: Dict, reason: str):
        try:
            now = datetime.now()
            with _file_lock:
                _deferred_failed_accounts.append(
                    (
                        account["email"],
                        account["password"],
                        account.get("recovery", ""),
                        COUNTRY,
                        SERVER_IP,
                        reason,
                        now,
                    )
                )
                _append_to_file(
                    FAILED_FILE,
                    f"{account['email']:40s} | {account['password']:20s} | {account.get('recovery', ''):30s} | {account.get('creation_date', ''):15s} | {reason:50s} | {now.strftime('%Y-%m-%d %H:%M:%S')}",
                )
        except Exception:
            pass


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
        if not recipients:
            return

        unique_recipients = list(dict.fromkeys(recipients))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _file_lock:
            _deferred_sent_recipients.extend(unique_recipients)
            for r in unique_recipients:
                _append_to_file(SENT_RECIPIENTS_FILE, f"{r:40s} | {now}")
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


def flush_db_operations():
    batch_size = 10000
    with _file_lock:
        if not (
            _deferred_account_updates
            or _deferred_failed_accounts
            or _deferred_sent_recipients
        ):
            return

        engine = _create_sqlalchemy_engine()
        if engine is None:
            log("Warning: unable to start DB operations (SQLAlchemy unavailable)")
            return

        try:
            print("Starting DB update operations...")
            total_account_updates = len(_deferred_account_updates)
            total_failed = len(_deferred_failed_accounts)
            total_recipients = len(_deferred_sent_recipients)

            with engine.begin() as conn:
                if _deferred_account_updates:
                    print(f"Updating sender accounts ({total_account_updates} rows)")
                    update_sql = text(
                        "UPDATE sender_input_accounts "
                        "SET times_used = COALESCE(times_used, 0) + 1, last_used = :last_used "
                        "WHERE email = :email AND server_ip = :server_ip "
                        "AND COALESCE(country, '') = :country"
                    )
                    for batch_idx in range(0, total_account_updates, batch_size):
                        batch = _deferred_account_updates[
                            batch_idx : batch_idx + batch_size
                        ]
                        params = [
                            {
                                "email": email,
                                "last_used": last_used,
                                "server_ip": server_ip,
                                "country": country,
                            }
                            for email, last_used, server_ip, country in batch
                        ]
                        conn.execute(update_sql, params)
                        print(
                            f"  Updated accounts batch {batch_idx // batch_size + 1} "
                            f"of {(total_account_updates - 1) // batch_size + 1}"
                        )
                    print("Account updates complete.")

                if _deferred_failed_accounts:
                    print(
                        f"Inserting failed accounts and removing them from sender_input_accounts ({total_failed} rows)"
                    )
                    insert_sql = text(
                        "INSERT INTO sender_failed_accounts "
                        "(email, pass, recovery, country, server_ip, fail_reason, date_time) "
                        "VALUES (:email, :password, :recovery, :country, :server_ip, :reason, :date_time)"
                    )
                    delete_sql = text(
                        "DELETE FROM sender_input_accounts "
                        "WHERE email = :email AND server_ip = :server_ip "
                        "AND COALESCE(country, '') = :country"
                    )
                    for batch_idx in range(0, total_failed, batch_size):
                        batch = _deferred_failed_accounts[
                            batch_idx : batch_idx + batch_size
                        ]
                        params = [
                            {
                                "email": email,
                                "password": password,
                                "recovery": recovery,
                                "country": country,
                                "server_ip": server_ip,
                                "reason": reason,
                                "date_time": date_time,
                            }
                            for (
                                email,
                                password,
                                recovery,
                                country,
                                server_ip,
                                reason,
                                date_time,
                            ) in batch
                        ]
                        conn.execute(insert_sql, params)
                        conn.execute(delete_sql, params)
                        print(
                            f"  Processed failed accounts batch {batch_idx // batch_size + 1} "
                            f"of {(total_failed - 1) // batch_size + 1}"
                        )

                    print("Failed accounts update complete.")

                if _deferred_sent_recipients:
                    unique_recipients = list(dict.fromkeys(_deferred_sent_recipients))
                    total_sent_recipients = len(unique_recipients)
                    print(
                        f"Updating sent recipients list ({total_sent_recipients} unique rows)"
                    )
                    delete_sql = (
                        "DELETE FROM sender_recipients "
                        "WHERE recipient_email = %s AND server_ip = %s "
                        "AND COALESCE(country, '') = %s"
                    )
                    insert_sql = (
                        "INSERT INTO sender_sent_recipients "
                        "(recipient_email, date_time, country, server_ip) "
                        "VALUES (%s, %s, %s, %s)"
                    )
                    mysql_conn = _get_db_connection()
                    if mysql_conn is None:
                        log(
                            "Warning: unable to flush sent recipients (DB connection failed)"
                        )
                    else:
                        try:
                            cursor = mysql_conn.cursor()
                            for batch_idx in range(
                                0, total_sent_recipients, batch_size
                            ):
                                batch = unique_recipients[
                                    batch_idx : batch_idx + batch_size
                                ]
                                delete_params = [(r, SERVER_IP, COUNTRY) for r in batch]
                                insert_params = [
                                    (r, datetime.now(), COUNTRY, SERVER_IP)
                                    for r in batch
                                ]
                                # cursor.executemany(delete_sql, delete_params)
                                cursor.executemany(insert_sql, insert_params)
                                mysql_conn.commit()
                                print(
                                    f"  Processed sent recipients batch {batch_idx // batch_size + 1} "
                                    f"of {(total_sent_recipients - 1) // batch_size + 1}"
                                )
                        except Exception as exc:
                            log(f"Error flushing sent recipients: {exc}")
                        finally:
                            try:
                                cursor.close()
                            except Exception:
                                pass
                            try:
                                mysql_conn.close()
                            except Exception:
                                pass

            print("Deferred DB flush complete.")
            log(
                f"DB operations: {total_account_updates} account updates, "
                f"{total_failed} failures, {total_recipients} sent recipients"
            )
        except Exception as exc:
            log(f"Error flushing deferred DB ops: {exc}")
        finally:
            try:
                engine.dispose()
            except Exception:
                pass


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
    print("Starting...")
    connect_random_random()
    connect_new_random()

    time.sleep(5)
    print("Connected VPN...")
    print("Current settings:")
    print(f"  SERVER_IP: {SERVER_IP}")
    print(f"  COUNTRY: {COUNTRY}")
    print(f"  FIRST_BATCH_BCC: {FIRST_BATCH_BCC}")
    print(f"  SUBSEQUENT_BATCH_BCC: {SUBSEQUENT_BATCH_BCC}")
    print(f"  SUBSEQUENT_BATCHES: {SUBSEQUENT_BATCHES}")
    print(f"  MAX_CONCURRENT_BATCHES: {MAX_CONCURRENT_BATCHES}")
    print(f"  MAX_CONCURRENT_ACCOUNTS: {MAX_CONCURRENT_ACCOUNTS}")
    print(f"  BATCH_DELAY: {BATCH_DELAY_MIN}-{BATCH_DELAY_MAX}s")
    print(f"  STAGGER: {STAGGER_MIN}-{STAGGER_MAX}s")
    print(f"  SAVE_TO_SENT: {SAVE_TO_SENT}")
    print("")

    global BATCH_NUMBER
    BATCH_NUMBER = prompt_for_batch_selection()
    if not BATCH_NUMBER:
        print("No batch selected. Exiting.")
        # return

    log("=" * 55)
    log("EMAIL SENDER | Graph API")
    log(f"Selected batch: {BATCH_NUMBER}")
    log(
        f"Config: warmup={FIRST_BATCH_BCC + 1} big={SUBSEQUENT_BATCHES}x"
        f"{SUBSEQUENT_BATCH_BCC + 1} batch_threads={MAX_CONCURRENT_BATCHES}"
    )
    log(f"        account_threads={MAX_CONCURRENT_ACCOUNTS}")
    log("=" * 55)

    log("Loading senders. Please wait...")
    accounts = AccountManager()
    log("Loading content. Please wait...")
    content = ContentManager()
    log("Loading recipients. Please wait...")
    recipients = RecipientManager()

    load_cache()

    if not accounts.accounts:
        log("✗ No accounts. Exiting.")
        # return
    if not recipients.queue:
        log("✗ No recipients. Exiting.")
        # return
    if not content.is_valid():
        log("✗ Missing content (need subjects, texts, links). Exiting.")
        # return

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
    log("=" * 55)
    flush_db_operations()
    log("=" * 55)


if __name__ == "__main__":
    main()
