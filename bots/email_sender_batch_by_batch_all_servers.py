import json
import os
import signal
import random
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta, datetime, timezone, UTC
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import deque
import msal
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from email_validator import validate_email, EmailNotValidError
from urllib.parse import quote_plus

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.server_ip_helper import get_server_ip

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
SERVER_IP = get_server_ip()
BOT_TYPE = "email_sender"
BATCH_NUMBER: Optional[str] = None
SENDER_APP = 1  # 1 for old, 2 for new
SAMPLE_RECIPIENT = 1


def _get_sender_accounts_table() -> str:
    return "sender2_input_accounts" if SENDER_APP == 2 else "sender_input_accounts"


def _get_client_id() -> str:
    return (
        "fe61e5b1-479a-480d-b45e-636e075bc1d3"
        if SENDER_APP == 2
        else "e62beeb7-8a9b-4637-b57f-f8601c0d13f5"
    )


def _get_sender2_failed_accounts_table() -> str:
    return "sender2_failed_accounts" if SENDER_APP == 2 else "sender_failed_accounts"


def _get_cache_bins_table() -> str:
    return "second_app_cache_bins" if SENDER_APP == 2 else "cache_bins"


# FIRST_BATCH_BCC = int(_EMAIL_SENDER_SETTINGS.get("FIRST_BATCH_BCC", 10))
# SUBSEQUENT_BATCH_BCC = int(_EMAIL_SENDER_SETTINGS.get("SUBSEQUENT_BATCH_BCC", 330))
# SUBSEQUENT_BATCHES = int(_EMAIL_SENDER_SETTINGS.get("SUBSEQUENT_BATCHES", 3))
# MAX_CONCURRENT_BATCHES = int(_EMAIL_SENDER_SETTINGS.get("MAX_CONCURRENT_BATCHES", 1))
# MAX_CONCURRENT_ACCOUNTS = int(_EMAIL_SENDER_SETTINGS.get("MAX_CONCURRENT_ACCOUNTS", 1))
# BATCH_DELAY_MIN = float(_EMAIL_SENDER_SETTINGS.get("BATCH_DELAY_MIN", 1.0))
# BATCH_DELAY_MAX = float(_EMAIL_SENDER_SETTINGS.get("BATCH_DELAY_MAX", 1.0))
# STAGGER_MIN = float(_EMAIL_SENDER_SETTINGS.get("STAGGER_MIN", 1.0))
# STAGGER_MAX = float(_EMAIL_SENDER_SETTINGS.get("STAGGER_MAX", 1.0))
# SAVE_TO_SENT = str(_EMAIL_SENDER_SETTINGS.get("SAVE_TO_SENT", False)).lower() == "true"
# CLIENT_ID = str(
#     _EMAIL_SENDER_SETTINGS.get("CLIENT_ID", "e62beeb7-8a9b-4637-b57f-f8601c0d13f5")
# )
# SPINNER_TIME = float(_EMAIL_SENDER_SETTINGS.get("SPINNER_TIME", 15))
# # VPN_COUNTRY = _EMAIL_SENDER_SETTINGS.get("VPN_COUNTRY", "poland").lower()
# BATCH_WAIT_TIME = float(_EMAIL_SENDER_SETTINGS.get("BATCH_WAIT_TIME", 30))


FIRST_BATCH_BCC = 49
FIRST_BATCH_BCC_LOWER = 40
SUBSEQUENT_BATCH_BCC = 49
SUBSEQUENT_BATCH_BCC_LOWER = 40
SUBSEQUENT_BATCHES = random.randint(17, 20)
MAX_CONCURRENT_BATCHES = int(_EMAIL_SENDER_SETTINGS.get("MAX_CONCURRENT_BATCHES", 1))

BATCH_DELAY_MIN = float(_EMAIL_SENDER_SETTINGS.get("BATCH_DELAY_MIN", 1.0))
BATCH_DELAY_MAX = float(_EMAIL_SENDER_SETTINGS.get("BATCH_DELAY_MAX", 1.0))
STAGGER_MIN = float(_EMAIL_SENDER_SETTINGS.get("STAGGER_MIN", 1.0))
STAGGER_MAX = float(_EMAIL_SENDER_SETTINGS.get("STAGGER_MAX", 1.0))
SAVE_TO_SENT = False
CLIENT_ID = str(
    _EMAIL_SENDER_SETTINGS.get("CLIENT_ID", "e62beeb7-8a9b-4637-b57f-f8601c0d13f5")
)
SPINNER_TIME = float(_EMAIL_SENDER_SETTINGS.get("SPINNER_TIME", 15))
# VPN_COUNTRY = _EMAIL_SENDER_SETTINGS.get("VPN_COUNTRY", "poland").lower()
BATCH_WAIT_TIME = 0
MAX_RUNTIME_SECONDS = 50 * 60
NEXT_RUN_WAIT_TIME = 4 * 60 * 60

if SERVER_IP in [
    "51.77.216.17",
    "51.75.119.199",
    "13.140.161.126",
    "13.140.181.21",
    "13.140.181.18",
    "13.140.181.23",
    "13.140.181.20",
    "13.140.181.19",
    "13.140.181.17",
    "13.140.181.14",
    "13.140.181.16",
    "13.140.181.22",
]:
    MAX_CONCURRENT_ACCOUNTS = 4
else:
    MAX_CONCURRENT_ACCOUNTS = 4

SAMPLE_RECIPIENT_EMAIL = []

if SERVER_IP in ["51.91.56.36"]:
    SAMPLE_RECIPIENT_EMAIL = [
        "mitestingacc.01@gmail.com",
        # "stacash.affiliate@gmail.com",
    ]
elif SERVER_IP in ["137.74.115.164"]:
    # SAMPLE_RECIPIENT_EMAIL = ["mitestingacc.02@gmail.com", "stacho1988@gmail.com"]
    SAMPLE_RECIPIENT_EMAIL = ["mitestingacc.02@gmail.com"]
elif SERVER_IP in ["13.140.181.17"]:
    SAMPLE_RECIPIENT_EMAIL = ["mitestingacc.03@gmail.com"]
else:
    SAMPLE_RECIPIENT_EMAIL = []

VPN_COUNTRY = {
    "51.91.59.107": "hungary",
    "79.137.75.57": "denmark",
    "51.91.56.36": "sweden",
    "193.70.86.209": "poland",
    "51.161.34.220": "czech",
    "51.77.195.218": "latvia",
    "51.91.97.55": "slovakia",
    "162.19.220.105": "slovenia",
}.get(SERVER_IP, "poland")


GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["https://graph.microsoft.com/.default"]


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
_account_status_lock = threading.Lock()
_account_success_count = 0
_account_fail_count = 0

_shared_cache = msal.SerializableTokenCache()
_shutdown = threading.Event()
_shutdown_reason: Optional[str] = None
_connect_lock = threading.Lock()
_pause_requested = threading.Event()


_BASIC_RE = re.compile(r".+@.+\..+")


def connect_new_random(COUNTRY=VPN_COUNTRY):
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
                df.country.apply(lambda x: x.lower().startswith(COUNTRY))
            ].id.to_list()

            random_location = str(random.choice(rand_locations))
            print(f"Connecting to : {COUNTRY}")

        except:
            try:
                random_location = str(
                    random.choice(
                        pd.read_csv(
                            os.path.join(utils_dir, "express_countries.csv")
                        ).id.to_list()
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


def _start_runtime_watchdog():
    def watcher():
        if not _shutdown.wait(MAX_RUNTIME_SECONDS):
            log(
                f"⚠ Max runtime reached ({MAX_RUNTIME_SECONDS // 60} minutes). Initiating shutdown..."
            )
            global _shutdown_reason
            _shutdown_reason = "timeout"
            _shutdown.set()

    threading.Thread(target=watcher, daemon=True).start()


def spinner():
    """Run connect_new_random() every 10 minutes while pausing active send threads."""
    while not _shutdown.wait(600):
        log("Spinner: pausing active send threads for reconnect")

        _pause_requested.set()
        _shutdown.wait(5)
        with _connect_lock:
            # connect_new_random(VPN_COUNTRY)
            pass
        _pause_requested.clear()
        log("Spinner: reconnect complete, resuming send threads")


def wait_for_pause_clear():
    while _pause_requested.is_set() and not _shutdown.is_set():
        time.sleep(1)


def _clear_shutdown_state():
    global _shutdown_reason
    _shutdown.clear()
    _shutdown_reason = None


def _wait_next_run_or_stop() -> bool:
    wait_time = NEXT_RUN_WAIT_TIME
    log(f"Max runtime pause: waiting {wait_time} seconds before resuming.")
    start_time = time.time()
    while time.time() - start_time < wait_time:
        if _shutdown.is_set() and _shutdown_reason == "manual":
            log("Manual shutdown received during wait. Stopping.")
            return False
        time.sleep(1)
    return True


def _resume_after_runtime_pause(
    content: "ContentManager",
) -> Optional["ContentManager"]:
    if _shutdown_reason != "timeout":
        return content
    # flush_db_operations()
    if not _wait_next_run_or_stop():
        return None
    _clear_shutdown_state()
    _pause_requested.clear()
    content = ContentManager()
    _start_runtime_watchdog()
    log("Resuming after wait; content refreshed.")
    return content


def _increment_account_status(success: bool) -> tuple[int, int]:
    # print(f"Incrementing account status: success={success}")
    global _account_success_count, _account_fail_count
    with _account_status_lock:
        if success:
            _account_success_count += 1
        else:
            _account_fail_count += 1
        return _account_success_count, _account_fail_count


def _reset_account_status():
    global _account_success_count, _account_fail_count
    with _account_status_lock:
        _account_success_count = 0
        _account_fail_count = 0


def _log_account_status(success: bool):
    success_count, fail_count = _increment_account_status(success)
    log(f"Tracker: ✓{success_count} ✗{fail_count}")


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
        global _shutdown_reason
        _shutdown_reason = "manual"
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
        cursor.execute(f"SELECT cache_bin_file FROM {_get_cache_bins_table()}")
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
            f"SELECT DISTINCT batch FROM {_get_sender_accounts_table()} "
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
            "No available sender batches found for this server and app."
            f"Please configure batch values in {_get_sender_accounts_table()} and sender_recipients."
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
                client_id=_get_client_id(),
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
                client_id=_get_client_id(),
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
        self.links = self._load("sender_link", "link", limit=3000, offset=0)
        self.subjects = self._load("sender_subjects", "subject")
        self.texts = self._load("sender_texts", "text")

        self._idx = {"h": 0, "l": 0, "s": 0, "t": 0}
        self._last_spinner_change = datetime.now()

        log(
            f"Content: {len(self.hyperlinks)}h {len(self.links)}l "
            f"{len(self.subjects)}s {len(self.texts)}t from DB"
            + (f" country={COUNTRY}" if COUNTRY else "")
            + (f" server_ip={SERVER_IP}" if SERVER_IP else "")
            + (f" spinner={SPINNER_TIME} min")
        )

    def _load(
        self, table_name: str, column_name: str, limit: int = 0, offset: int = 0
    ) -> List[str]:
        # return self._load_table_attribute(table_name, column_name, COUNTRY, SERVER_IP)
        return self._load_table_attribute(
            table_name, column_name, COUNTRY, limit, offset
        )

    def _load_table_attribute(
        self,
        table_name: str,
        column_name: str,
        country: str = "",
        limit: int = 0,
        offset: int = 0,
    ) -> List[str]:
        conn = _get_db_connection()
        if conn is None:
            print(f"Error: unable to load table {table_name} from database")
            return []

        try:
            cursor = conn.cursor()
            query = f"SELECT `{column_name}` FROM `{table_name}`"
            params = []
            where_clauses = []
            if country:
                where_clauses.append("LOWER(country) = %s")
                params.append(country.lower())
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            if limit > 0:
                query += " LIMIT %s"
                params.append(limit)
            if offset > 0:
                query += " OFFSET %s"
                params.append(offset)
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
            # self._update_spinner_indexes()
            h = self._next(self.hyperlinks, "h")
            l = self._next(self.links, "l")
            s = self._next(self.subjects, "s")
            t = self._next(self.texts, "t")
        return spin(h), l, spin(s), spin(t)

    def _current(self, items: List[str], key: str) -> str:
        if not items:
            return ""
        return items[self._idx[key]]

    def _update_spinner_indexes(self):
        if SPINNER_TIME <= 0:
            return

        now = datetime.now()
        elapsed_seconds = (now - self._last_spinner_change).total_seconds()
        interval_seconds = SPINNER_TIME * 60
        if elapsed_seconds < interval_seconds:
            return

        steps = int(elapsed_seconds // interval_seconds)
        if steps <= 0:
            steps = 1

        for key, items in [
            ("h", self.hyperlinks),
            ("l", self.links),
            ("s", self.subjects),
            ("t", self.texts),
        ]:
            if items:
                self._idx[key] = (self._idx[key] + steps) % len(items)

        self._last_spinner_change += timedelta(seconds=steps * interval_seconds)
        log("==================== CHANGING CONTENT AND IP =================")
        # connect_new_random("netherlands")
        # connect_new_random(VPN_COUNTRY)
        time.sleep(5)

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
                "LIMIT 1000000 offset 0"
            )
            params = [SERVER_IP, COUNTRY]

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
        global SAMPLE_RECIPIENT, SAMPLE_RECIPIENT_EMAIL
        if int(SAMPLE_RECIPIENT) == 2:
            with _recipient_lock:
                batch = []
                for _ in range(size):
                    if self.queue:
                        batch.append(self.queue.popleft())
                    else:
                        break
                return batch
        else:
            with _recipient_lock:
                batch = []
                for _ in range(size - len(SAMPLE_RECIPIENT_EMAIL)):
                    if self.queue:
                        batch.append(self.queue.popleft())
                    else:
                        break
                batch += SAMPLE_RECIPIENT_EMAIL  # Add test recipient to each batch
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
                f"SELECT email, pass, recovery FROM {_get_sender_accounts_table()} "
                "WHERE server_ip = %s AND COALESCE(country, '') = %s "
            )
            params = [SERVER_IP, COUNTRY]
            if BATCH_NUMBER:
                query += " AND batch = %s "
                params.append(BATCH_NUMBER)
            query += " LIMIT 1001 OFFSET 0"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()

            for row in rows:
                if not row or row[0] is None:
                    continue
                email = str(row[0]).strip()
                password = str(row[1]).strip()
                recovery = (
                    str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
                )
                if not email:
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

SALNJLA = 0


def send_email(
    session: requests.Session,
    token: str,
    from_email: str,
    to_email: str,
    bcc_list: List[str],
    subject: str,
    body_html: str,
) -> Tuple[bool, str]:

    # global SALNJLA
    # time.sleep(random.uniform(3, 5))  # Random delay to avoid detection
    # SALNJLA += 1
    # if SALNJLA % 77 == 0:
    #     return False, "DODODODOD"
    # else:
    #     return True, ""
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
            for attempt in range(2):
                try:
                    wait = min(
                        int(r.headers.get("Retry-After", str(5 * (attempt + 1)))), 60
                    )
                    wait = 45
                except:
                    wait = 45
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
    # return (
    #     f'<html><body><div style="font-family:Arial,sans-serif;'
    #     f'font-size:14px;color:#333;">{text}<br><br>{hyperlink}: {link}</div></body></html>'
    # )


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

    # warmup = recipients.get_batch(FIRST_BATCH_BCC)
    warmup = recipients.get_batch(
        random.randint(FIRST_BATCH_BCC_LOWER, FIRST_BATCH_BCC)
    )

    if not warmup:
        return True, 0, ""

    h, link, subj, body = content.get()
    html = build_html(body, h, link)
    ok, err = send_email(session, token, email, warmup[0], warmup[1:], subj, html)

    if not ok:
        log(f"  ✗ {_short(email)} warmup pro 1: {err}")
        recipients.return_batch(warmup)

        if err in FATAL_ERRORS:
            return False, 0, err

        if err in TOKEN_ERRORS:
            token = refresh_token(email)
            if not token:
                return False, 0, "TOKEN_REFRESH_FAILED"
            log(f"  ↻ {_short(email)}: token refreshed, retrying warmup")
            warmup = recipients.get_batch(
                random.randint(FIRST_BATCH_BCC_LOWER, FIRST_BATCH_BCC)
            )
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
    log(f"  ✓ {_short(email)} warmup pro 2: {len(warmup)} rcpts")

    if _shutdown.is_set():
        return (sent > 0), sent, ""

    delay = random.uniform(BATCH_DELAY_MIN, BATCH_DELAY_MAX)
    if _shutdown.wait(delay):
        return (sent > 0), sent, ""

    batches = []
    for i in range(SUBSEQUENT_BATCHES):
        if not recipients.has_more() or _shutdown.is_set():
            break
        batch = recipients.get_batch(
            random.randint(SUBSEQUENT_BATCH_BCC_LOWER, SUBSEQUENT_BATCH_BCC)
        )

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
                delay = random.uniform(STAGGER_MIN, STAGGER_MAX)
                if _shutdown.wait(delay):
                    break
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


class AccountState:
    def __init__(self, account: Dict, account_idx: int, total_accounts: int):
        self.account = account
        self.account_idx = account_idx
        self.total_accounts = total_accounts
        self.batch_round = 0
        self.token = None
        self.sent = 0
        self.failed = False
        self.completed = False
        self.finalized = False
        self.error = ""
        self.started = False


def process_account_batch(
    state: AccountState,
    recipients: "RecipientManager",
    content: "ContentManager",
) -> Dict:
    # time.sleep(random.uniform(4, 7))
    # print(
    #     f"Processing account {state.account_idx + 1}/{state.total_accounts}: {state.account['email']}"
    # )
    if (
        _shutdown.is_set()
        or state.failed
        # or state.completed
        or not recipients.has_more()
    ):
        return {"skipped": True}

    session = make_session()
    # print(f"Session created for account {state.account['email']}")
    try:
        email = state.account["email"]
        if not state.started:
            log(f"[{state.account_idx + 1}/{state.total_accounts}] {email}")
            state.started = True

        if state.batch_round == 0:
            batch_size = random.randint(FIRST_BATCH_BCC_LOWER, FIRST_BATCH_BCC)
            label = "warmup"
        else:
            batch_size = random.randint(
                SUBSEQUENT_BATCH_BCC_LOWER, SUBSEQUENT_BATCH_BCC
            )
            label = f"b{state.batch_round + 1}"

        # print(
        #     f"Fetching batch of size {batch_size} for account {state.account['email']}"
        # )

        batch = recipients.get_batch(batch_size)
        if not batch:
            state.completed = True
            return {"skipped": True}

        # print(f"Batch fetched for account {state.account['email']}: {batch}")

        if not state.token:
            state.token = get_token(email)
            # state.token = True
            if not state.token:
                recipients.return_batch(batch)
                state.failed = True
                state.error = "AUTH_FAILED"
                return {"failed": True, "error": "AUTH_FAILED", "sent": 0}
            log(f"  ✓ {_short(email)}: token OK")

        # print(f"Sending email for account {state.account['email']} with batch: {batch}")

        h, link, subj, body = content.get()
        html = build_html(body, h, link)
        wait_for_pause_clear()
        # with _connect_lock:
        ok, err = send_email(
            session, state.token, email, batch[0], batch[1:], subj, html
        )
        # log(f"Email sent for account {state.account['email']}")

        if not ok:
            # log(f"Error sending email for account {state.account['email']}: {err}")
            recipients.return_batch(batch)
            log(f"  ✗ {_short(email)} {label} : {err} ")

            if err in FATAL_ERRORS:
                state.failed = True
                state.error = err
                _log_account_status(False)
                return {
                    "failed": True,
                    "error": err,
                    "sent": 0,
                    "batch_success": 0,
                    "batch_fail": len(batch),
                    "label": label,
                }

            if err in TOKEN_ERRORS:
                wait_for_pause_clear()
                # with _connect_lock:
                #     new_token = refresh_token(email)

                new_token = refresh_token(email)
                if not new_token:
                    state.failed = True
                    state.error = "TOKEN_REFRESH_FAILED"
                    _log_account_status(False)
                    return {
                        "failed": True,
                        "error": "TOKEN_REFRESH_FAILED",
                        "sent": 0,
                        "batch_success": 0,
                        "batch_fail": len(batch),
                        "label": label,
                    }

                state.token = new_token
                log(f"  ↻ {_short(email)}: token refreshed, retrying {label}")
                h, link, subj, body = content.get()
                html = build_html(body, h, link)
                wait_for_pause_clear()
                # with _connect_lock:
                #     ok, err = send_email(
                #         session, state.token, email, batch[0], batch[1:], subj, html
                #     )
                ok, err = send_email(
                    session, state.token, email, batch[0], batch[1:], subj, html
                )
                if not ok:
                    recipients.return_batch(batch)
                    state.failed = True
                    state.error = f"{label.upper()}_RETRY_FAIL:{err}"
                    _log_account_status(False)
                    return {
                        "failed": True,
                        "error": state.error,
                        "sent": 0,
                        "batch_success": 0,
                        "batch_fail": len(batch),
                        "label": label,
                    }
            else:
                state.failed = True
                state.error = f"{label.upper()}_FAIL:{err}"
                _log_account_status(False)
                return {
                    "failed": True,
                    "error": state.error,
                    "sent": 0,
                    "batch_success": 0,
                    "batch_fail": len(batch),
                    "label": label,
                }

        state.sent += len(batch)
        recipients.mark_sent(len(batch))
        log_sent(batch)
        log(f"  ✓ {_short(email)} {label} : {len(batch)} rcpts")
        _log_account_status(True)

        if state.batch_round == 0:
            delay = random.uniform(BATCH_DELAY_MIN, BATCH_DELAY_MAX)
            if _shutdown.wait(delay):
                return {"skipped": True}

        state.batch_round += 1
        if state.batch_round > SUBSEQUENT_BATCHES:
            state.completed = True
            # _log_account_status(True)
            return {
                "completed": True,
                "sent": len(batch),
                "batch_success": len(batch),
                "batch_fail": 0,
                "label": label,
            }

        return {
            "sent": len(batch),
            "batch_success": len(batch),
            "batch_fail": 0,
            "label": label,
        }
    finally:
        session.close()


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
        retries = 0
        done_acc_update = False
        done_failed_update = False
        while retries < 7:
            engine = _create_sqlalchemy_engine()
            if engine is None:
                log("Warning: unable to start DB operations (SQLAlchemy unavailable)")
                return

            try:
                log("Starting DB update operations...")
                total_account_updates = len(_deferred_account_updates)
                total_failed = len(_deferred_failed_accounts)
                total_recipients = len(_deferred_sent_recipients)

                with engine.begin() as conn:
                    if _deferred_account_updates and not done_acc_update:
                        log(f"Updating sender accounts ({total_account_updates} rows)")
                        account_table = _get_sender_accounts_table()
                        update_sql = text(
                            f"UPDATE {account_table} "
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
                            log(
                                f"  Updated accounts batch {batch_idx // batch_size + 1} "
                                f"of {(total_account_updates - 1) // batch_size + 1}"
                            )
                        log("Account updates complete.")

                        done_acc_update = True
                    elif not _deferred_account_updates:
                        done_acc_update = True

                    if _deferred_failed_accounts and not done_failed_update:
                        account_table = _get_sender_accounts_table()
                        failed_accounts_table = _get_sender2_failed_accounts_table()
                        log(
                            f"Inserting failed accounts and removing them from {account_table} ({total_failed} rows)"
                        )
                        insert_sql = text(
                            f"INSERT INTO {failed_accounts_table} "
                            "(email, pass, recovery, country, server_ip, fail_reason, date_time) "
                            "VALUES (:email, :password, :recovery, :country, :server_ip, :reason, :date_time)"
                        )
                        delete_sql = text(
                            f"DELETE FROM {account_table} "
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
                            log(
                                f"  Processed failed accounts batch {batch_idx // batch_size + 1} "
                                f"of {(total_failed - 1) // batch_size + 1}"
                            )

                        log("Failed accounts update complete.")
                        done_failed_update = True
                    elif not _deferred_failed_accounts:
                        done_failed_update = True

                log("Deferred DB flush complete.")
                log(
                    f"DB operations: {total_account_updates} account updates, "
                    f"{total_failed} failures, {total_recipients} sent recipients"
                )

            except Exception as exc:
                log(
                    f"Error flushing deferred DB ops. \n\n{exc}\n\nRetrying in 60 seconds..."
                )
            finally:
                try:
                    engine.dispose()
                except Exception:
                    pass

            if done_acc_update and done_failed_update:
                _deferred_account_updates.clear()
                _deferred_failed_accounts.clear()
                _deferred_sent_recipients.clear()
                return True

            retries += 1
            time.sleep(random.randint(55, 75))


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
        # log(f"  ✗ CRASH: {str(e)[:80]}")
        # success, sent, error = False, 0, f"CRASH:{str(e)[:80]}"
        log("  ✗ CRASH: ")
        success, sent, error = False, 0, "CRASH"
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


def prompt_for_sender_app_selection() -> Optional[int]:
    while True:
        choice = input(
            "Select email sender app:\n"
            "1. Old app\n"
            "2. New app\n"
            "Enter choice (1 or 2), or type 'exit' to cancel: "
        ).strip()
        if not choice:
            continue
        if choice.lower() in {"exit", "quit", "q"}:
            return None
        if choice in {"1", "2"}:
            return int(choice)
        print("Invalid choice. Please enter 1 for old app or 2 for new app.")


def prompt_for_sample_recipient() -> Optional[int]:
    choice = input(
        "Use a sample recipient email on each send?:\n"
        "1. Yes\n"
        "2. No\n"
        "Enter choice (1 or 2), or type Enter to exit: "
    ).strip()
    if not choice:
        return None, None
    if choice.lower() in {"exit", "quit", "q"}:
        return None, None
    if choice in {"1", "2"}:
        email = input("Enter emails (comma-separated): ").strip()
        return int(choice), email
    print("Invalid choice. Please enter 1 for old app or 2 for new app.")


def get_action_status() -> bool:
    # return True
    conn = _get_db_connection()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT action, status, date_time FROM manualbot_actions_tracker "
            "ORDER BY action_id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return False

        action = str(row[0]).strip().lower() if row[0] is not None else ""
        status = str(row[1]).strip().lower() if row[1] is not None else ""
        timestamp = row[2].replace(tzinfo=timezone.utc)

        if not timestamp or not isinstance(timestamp, datetime):
            return False

        if datetime.now(UTC) - timestamp > timedelta(minutes=10):
            return False

        return action == "run_bots" and status == "true"
    except Exception as exc:
        log(f"Error checking action status: {exc}")
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main_batches():
    print("Starting...")

    global BATCH_NUMBER, SENDER_APP, MAX_CONCURRENT_ACCOUNTS
    app_choice = prompt_for_sender_app_selection()
    if app_choice is None:
        print("No app selection made. Exiting.")
        return
    SENDER_APP = app_choice
    print(f"Selected {'New' if SENDER_APP == 2 else 'Old'} app.")

    BATCH_NUMBER = prompt_for_batch_selection()
    if not BATCH_NUMBER:
        print("No batch selected. Exiting.")
        return

    # connect_new_random("netherlands")
    # connect_new_random(VPN_COUNTRY)

    time.sleep(5)
    # print("Connected VPN...")
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

    log("=" * 55)
    log("EMAIL SENDER | Graph API")
    log(f"Selected batch: {BATCH_NUMBER}")
    log(
        f"Config: warmup={FIRST_BATCH_BCC} big={SUBSEQUENT_BATCHES}x"
        f"{SUBSEQUENT_BATCH_BCC} batch_threads={MAX_CONCURRENT_BATCHES}"
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
        return
    if not recipients.queue:
        log("✗ No recipients. Exiting.")
        return
    if not content.is_valid():
        log("✗ Missing content (need subjects, texts, links). Exiting.")
        return

    total_acc = len(accounts.accounts)
    total_rcpt = recipients._total_loaded
    max_per_account = (FIRST_BATCH_BCC) + SUBSEQUENT_BATCHES * (SUBSEQUENT_BATCH_BCC)
    est_accounts_needed = (total_rcpt + max_per_account - 1) // max_per_account

    log(f"Ready: {total_acc} accounts | {total_rcpt} recipients")
    log(f"Max/account: {max_per_account} | Est. accounts needed: {est_accounts_needed}")
    log("-" * 55)
    log("Waiting for run signal...")
    while True:
        if not get_action_status():
            time.sleep(5)
            continue
        else:
            break

    log("Run signal received. Starting batch processing...")

    _start_runtime_watchdog()

    stats = StatsTracker(total_acc, total_rcpt)
    account_states = [
        AccountState(account, idx, total_acc)
        for idx, account in enumerate(accounts.accounts)
    ]

    round_idx = 0
    while round_idx <= SUBSEQUENT_BATCHES:
        if _shutdown.is_set():
            if _shutdown_reason == "timeout":
                content = _resume_after_runtime_pause(content)
                if content is None:
                    log("Stopping due to shutdown during wait.")
                    break
                continue
            log("Shutdown: stopping batch rounds...")
            break

        if not recipients.has_more():
            log("All recipients consumed.")
            break

        if round_idx > 0:
            MAX_CONCURRENT_ACCOUNTS = 1

        log(
            f"Starting batch {round_idx + 1}/{SUBSEQUENT_BATCHES + 1}\nThreads: {MAX_CONCURRENT_ACCOUNTS}"
        )

        _reset_account_status()
        active_states = [s for s in account_states if not s.failed]
        log(f"Active accounts for this batch: {len(active_states)}\n\n{'=' * 55}\n")

        if not active_states:
            break

        futures = {}
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_ACCOUNTS) as executor:
            log(f"Submitting {len(active_states)} accounts for processing...")
            for idx, state in enumerate(active_states):
                if _shutdown.is_set():
                    break
                if not recipients.has_more():
                    break
                futures[
                    executor.submit(process_account_batch, state, recipients, content)
                ] = state
            print(f"Submitted {len(futures)} accounts for processing.")

            batch_success = 0
            batch_fail = 0
            print("Waiting for account processing to complete...")

            for future in as_completed(futures):
                state = futures[future]
                result = future.result()

                if _shutdown.is_set() and _shutdown_reason != "timeout":
                    log("Shutdown: waiting for remaining accounts...")

                if result.get("skipped"):
                    continue

                if result.get("failed"):
                    batch_fail += 1
                elif result.get("completed"):
                    batch_success += 1

                if result.get("failed") and not state.finalized:
                    state.finalized = True
                    accounts.mark_failed(state.account, result.get("error", ""))
                    stats.update(state.account, False, state.sent)
                    continue

                if result.get("completed") and not state.finalized:
                    state.finalized = True
                    accounts.mark_done(state.account)
                    stats.update(state.account, True, state.sent)

            log(
                f"\n{'=' * 55}\n\nBatch {round_idx + 1}/{SUBSEQUENT_BATCHES + 1} Finished\n"
            )
            log(f"Sent:       {total_rcpt - recipients.remaining()}/{total_rcpt}\n\n")
            final_stats = stats.get_stats()
            log(
                f"  Time:       {final_stats['elapsed']:.1f}s = {final_stats['elapsed'] / 60:.1f}minutes : ({final_stats['rate']:.1f}/s)"
            )

            if not recipients.has_more():
                log("No recipients left after batch round.")
                break

            if round_idx < SUBSEQUENT_BATCHES and BATCH_WAIT_TIME > 0:
                log(f"Waiting {BATCH_WAIT_TIME:.1f} minutes before next batch...")
                _shutdown.wait(BATCH_WAIT_TIME * 60)
                if _shutdown.is_set():
                    continue

        round_idx += 1

        for state in account_states:
            if state.finalized:
                continue
            if state.failed and not state.finalized:
                state.finalized = True
                accounts.mark_failed(state.account, state.error or "FAILED")
                stats.update(state.account, False, state.sent)

    # processed = stats.get_processed()
    # unused = [a for a in accounts.accounts if a not in processed]

    processed = stats.get_processed()
    unused = [a for a in accounts.accounts if a not in processed]

    final_stats = stats.get_stats()

    log("")
    log("=" * 55)
    log("DONE")
    log(f"  Sent:       {final_stats['total_sent']}/{total_rcpt}")
    log(f"  Sent:       {total_rcpt - recipients.remaining()}/{total_rcpt}")
    log(
        f"  Accounts:   ✓{final_stats['ok_count']} ✗{final_stats['fail_count']} (unused: {len(unused)})"
    )
    log(f"  Time:       {final_stats['elapsed']:.1f}s ({final_stats['rate']:.1f}/s)")
    log(f"  Remaining:  {recipients.remaining()} recipients")
    log("=" * 55)
    flush_db_operations()
    log("=" * 55)
