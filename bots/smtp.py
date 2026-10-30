import gc
import json
import os
import platform
import signal
import subprocess
import random
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
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

SMTP_VERSION = "v1.0.6"
SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"
SENDER_LOG_DIR = Path(__file__).resolve().parent.parent / "sender_logs"
LOG_FILE = SENDER_LOG_DIR / "email_sender.log"
PROCESSED_FILE = SENDER_LOG_DIR / "processed_accounts.txt"
FAILED_FILE = SENDER_LOG_DIR / "failed_accounts.txt"
SENT_RECIPIENTS_FILE = SENDER_LOG_DIR / "sent_recipients.txt"
STATS_FILE = SENDER_LOG_DIR / "stats.json"

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


def update():
    """Launch the SMTP updater and close the invoking process."""
    try:
        print(
            f"Update signal received. Restarting the application...\n ============================================================================="
        )
        base_dir = Path(__file__).resolve().parent.parent
        linux_server = is_linux_server()
        update_path = base_dir / (
            "update_smtp.sh" if linux_server else "update_smtp.bat"
        )
        if not update_path.exists():
            raise FileNotFoundError(f"Update script not found: {update_path}")

        print(f"Executing update script: {update_path}")
        if linux_server:
            subprocess.Popen(
                ["bash", str(update_path)],
                cwd=base_dir,
                start_new_session=True,
                close_fds=True,
            )
        else:
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))
            subprocess.Popen(
                ["cmd.exe", "/d", "/c", "call", str(update_path)],
                cwd=os.path.dirname(BASE_DIR),
                creationflags=subprocess.CREATE_NEW_CONSOLE
                | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
            subprocess.run(
                ["taskkill", "/PID", str(os.getppid()), "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        os._exit(0)

    except Exception as exc:
        print(f"update() failed: {exc}")
        return False
    return True


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


FIRST_BATCH_BCC = 10
FIRST_BATCH_BCC_LOWER = 9
SUBSEQUENT_BATCH_BCC = 10
SUBSEQUENT_BATCH_BCC_LOWER = 9
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
STAGGER_ = 3
SUBSEQUENT_BATCHES = 2

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
    MAX_CONCURRENT_ACCOUNTS = 2
else:
    MAX_CONCURRENT_ACCOUNTS = 2


SMTP_MAILER = {
    "51.178.81.140": "smtp45@affworker.com",
    "57.129.184.182": "smtp46@affworker.com",
    "57.129.184.183": "smtp47@affworker.com",
    "57.129.184.181": "smtp48@affworker.com",
    "57.129.184.185": "smtp49@affworker.com",
    "57.129.184.184": "smtp50@affworker.com",
    "54.39.109.65": "smtp51@affworker.com",
    "54.39.109.66": "smtp52@affworker.com",
    "54.39.109.63": "smtp53@affworker.com",
    "54.39.109.68": "smtp54@affworker.com",
    "54.39.109.64": "smtp55@affworker.com",
    "54.39.109.60": "smtp56@affworker.com",
    "54.39.109.69": "smtp57@affworker.com",
    "54.39.109.67": "smtp58@affworker.com",
    "54.39.109.61": "smtp59@affworker.com",
    "54.39.109.62": "smtp60@affworker.com",
}

SAMPLE_RECIPIENT_EMAIL = (
    [SMTP_MAILER.get(SERVER_IP)] if SMTP_MAILER.get(SERVER_IP) else []
)
# SAMPLE_RECIPIENT_EMAIL = []

if SERVER_IP in ["51.91.59.107"]:
    SAMPLE_RECIPIENT_EMAIL += [
        "mitestingacc.01@gmail.com",
    ]

elif SERVER_IP in ["162.19.229.114"]:
    SAMPLE_RECIPIENT_EMAIL += ["mitestingacc.02@gmail.com", "stacho1988@gmail.com"]

elif SERVER_IP in ["51.178.81.140"]:
    SAMPLE_RECIPIENT_EMAIL += [
        "mitestingacc.03@gmail.com",
        "stacash.affiliate@gmail.com",
    ]

elif SERVER_IP in ["164.132.105.244"]:
    SAMPLE_RECIPIENT_EMAIL += ["andrewsetup17@gmail.com"]

elif SERVER_IP in ["51.161.34.220"]:
    SAMPLE_RECIPIENT_EMAIL += ["durwoodstacks100@gmail.com"]

elif SERVER_IP in ["162.19.26.217"]:
    SAMPLE_RECIPIENT_EMAIL += [
        "marcusfrancis0227@gmail.com",
        "mitestingacc.04@gmail.com",
    ]

elif SERVER_IP in ["162.19.27.8"]:
    SAMPLE_RECIPIENT_EMAIL += ["wrochna1988@gmail.com", "dover.miranach@gmail.com"]

elif SERVER_IP in ["146.59.196.225"]:
    SAMPLE_RECIPIENT_EMAIL += ["aidanmotthews986@gmail.com", "bradley.konsa@gmail.com"]

# else:
#     SAMPLE_RECIPIENT_EMAIL = []


VPN_COUNTRY = {
    "51.91.59.107": "poland",
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


LOCK_TIMEOUT_SECONDS = 10


class TimeoutLock:
    def __init__(self):
        self._lock = threading.Lock()

    def acquire(self, blocking=True, timeout=LOCK_TIMEOUT_SECONDS):
        if not blocking:
            return self._lock.acquire(blocking=False)

        if timeout is None or timeout < 0:
            timeout = LOCK_TIMEOUT_SECONDS
        timeout = min(float(timeout), LOCK_TIMEOUT_SECONDS)
        return self._lock.acquire(timeout=timeout)

    def release(self):
        self._lock.release()

    def locked(self):
        return self._lock.locked()

    def __enter__(self):
        if not self.acquire(timeout=LOCK_TIMEOUT_SECONDS):
            raise TimeoutError(
                f"Timed out waiting up to {LOCK_TIMEOUT_SECONDS} seconds for lock"
            )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        return False


_log_lock = TimeoutLock()
_recipient_lock = TimeoutLock()
_content_lock = TimeoutLock()
_file_lock = TimeoutLock()
_cache_lock = TimeoutLock()
_stats_lock = TimeoutLock()
_account_status_lock = TimeoutLock()
_recipient_window_lock = TimeoutLock()
_account_success_count = 0
_account_fail_count = 0
_recipient_window_start = 0

_shared_cache = msal.SerializableTokenCache()
_shutdown = threading.Event()
_shutdown_reason: Optional[str] = None
_shutdown_watcher_started = False
_connect_lock = TimeoutLock()
_pause_requested = threading.Event()


_BASIC_RE = re.compile(r".+@.+\..+")
LOAD_RETRY_ATTEMPTS = 7
LOAD_RETRY_DELAY_SECONDS = 5.0
CACHE_LOAD_RETRIES = 10
EMAIL_ROUNDS = 2

# NEW_RECIPIENT_LIST = [
#     "144.217.85.183",
#     "152.228.137.224",
#     "217.182.71.146",
#     "146.59.196.225",
#     "51.254.222.49",
#     "162.19.26.243",
#     "162.19.26.44",
#     "162.19.27.233",
#     "162.19.27.118",
#     "162.19.26.209",
#     "162.19.27.8",
#     "162.19.27.214",
#     "162.19.27.84",
#     "162.19.26.200",
#     "162.19.27.76",
#     "162.19.26.195",
#     "162.19.27.202",
#     "162.19.26.217",
# ]

NEW_RECIPIENT_LIST = []


def _run_with_retry(
    operation_name: str,
    func,
    default=None,
    attempts: int = LOAD_RETRY_ATTEMPTS,
    delay_seconds: float = LOAD_RETRY_DELAY_SECONDS,
):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                log(f"Failed to {operation_name} after {attempts} attempts: {exc}")
                return default
            wait_time = min(delay_seconds * attempt, 30.0)
            log(
                f"Retrying {operation_name} in {wait_time:.1f}s "
                f"({attempt}/{attempts}) after error: {exc}"
            )
            time.sleep(wait_time)
    return default


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
                print(f"No {COUNTRY} server found. Connecting to random server")
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


def disconnect_vpn():
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

        disconnect()
        return True
    except:
        return False


def _start_runtime_watchdog():
    _clear_shutdown_state()
    time.sleep(
        3
    )  # Ensure any previous shutdown state is cleared before starting the watcher

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


def _resume_after_runtime_pause_old(
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


def _resume_after_runtime_pause(
    content: "ContentManager",
) -> Optional["ContentManager"]:
    if _shutdown_reason != "timeout":
        return content
    # Stop immediately after max runtime instead of waiting for NEXT_RUN_WAIT_TIME
    log("Max runtime reached. Stopping immediately.")
    return None


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


# def _signal_handler(sig, frame):
#     if not _shutdown.is_set():
#         log("⚠ Shutdown requested (Ctrl+C). Finishing current accounts...")
#         global _shutdown_reason
#         _shutdown_reason = "manual"
#         _shutdown.set()


# signal.signal(signal.SIGINT, _signal_handler)
# try:
#     signal.signal(signal.SIGBREAK, _signal_handler)
# except AttributeError:
#     pass


def load_cache() -> bool:
    def _load_once():
        log("Loading cache")
        conn = None
        cursor = None
        try:
            conn = _get_db_connection()
            if conn is None:
                raise RuntimeError("unable to connect to database for cache")

            cursor = conn.cursor()
            cursor.execute(f"SELECT cache_bin_file FROM {_get_cache_bins_table()}")
            results = cursor.fetchall()

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
                    raw_data = json.loads(temp_cache.serialize())
                    for category in combined_data.keys():
                        if category in raw_data:
                            combined_data[category].update(raw_data[category])

            num_accounts = len(combined_data.get("Account", {}))
            _shared_cache.deserialize(json.dumps(combined_data))

            log(
                f"Cache loaded from database: {len(results)} servers caches, {num_accounts} accounts"
            )
        except Exception as exc:
            raise RuntimeError(f"cache load failed: {exc}") from exc
        finally:
            try:
                if cursor is not None:
                    cursor.close()
            except Exception:
                pass
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

    total_attempts = CACHE_LOAD_RETRIES + 1
    for attempt in range(1, total_attempts + 1):
        try:
            _load_once()
            return True
        except Exception as exc:
            log(f"Cache load attempt {attempt}/{total_attempts} failed: {exc}")
            if attempt < total_attempts:
                wait_seconds = random.randint(40, 120)
                log(f"Retrying cache load in {wait_seconds} seconds.")
                time.sleep(wait_seconds)

    log(
        f"Cache could not be loaded after {CACHE_LOAD_RETRIES} retries. Returning to signal loop."
    )
    return False


def load_cache_local(cache_path: Optional[str] = None) -> bool:
    """Load an MSAL token cache from a local file into the shared cache."""
    global _shared_cache
    _shared_cache = msal.SerializableTokenCache()
    configured_path = cache_path
    path = Path(configured_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path

    try:
        with path.open("rb") as handle:
            serialized_cache = handle.read()

        if not serialized_cache:
            raise ValueError("cache file is empty")

        if isinstance(serialized_cache, bytes):
            serialized_cache = serialized_cache.decode("utf-8")

        with _cache_lock:
            _shared_cache.deserialize(serialized_cache)

        log(f"Cache loaded from file: {path}")
        return True
    except Exception as exc:
        log(f"Failed to load cache from file {path}: {exc}")
        return False


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


def _get_db_connection(
    attempts: int = LOAD_RETRY_ATTEMPTS, delay_seconds: float = LOAD_RETRY_DELAY_SECONDS
):
    try:
        import mysql.connector
    except ImportError:
        return None

    for attempt in range(1, attempts + 1):
        try:
            return mysql.connector.connect(**_load_db_config())
        except Exception as exc:
            if attempt >= attempts:
                log(f"Error: unable to connect to database: {exc}")
                return None
            wait_time = min(delay_seconds * attempt, 10.0)
            log(
                f"Retrying database connection in {wait_time:.1f}s "
                f"({attempt}/{attempts}) after error: {exc}"
            )
            time.sleep(wait_time)

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
    if not _cache_lock.acquire(timeout=LOCK_TIMEOUT_SECONDS):
        log(f"Token lookup skipped for {email}: timed out waiting for cache lock.")
        return None

    try:
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
    finally:
        _cache_lock.release()


def get_access_token(email: str) -> Optional[str]:
    """Return the access token stored in the loaded cache without refreshing it."""
    try:
        normalized_email = email.strip().lower()
        cache_data = json.loads(_shared_cache.serialize())
        account_ids = {
            account.get("home_account_id")
            for account in cache_data.get("Account", {}).values()
            if isinstance(account, dict)
            and account.get("username", "").strip().lower() == normalized_email
        }

        if not account_ids:
            return None

        for record in cache_data.get("AccessToken", {}).values():
            if not isinstance(record, dict):
                continue
            if (
                record.get("home_account_id") in account_ids
                and record.get("client_id") == _get_client_id()
                and "https://graph.microsoft.com/.default" in record.get("target", "")
            ):
                return record.get("secret")
    except Exception:
        pass

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
    def __init__(self, part: int):

        self.part = part

        link_table = "sender_content_links_3"
        subject_table = "sender_content_subjects_3"
        hyperlink_table = "sender_content_hyperlink_text_3"
        text_table = "sender_content_texts_3"

        self.hyperlinks = self._load(hyperlink_table, "hyperlink_text")
        self.links = self._load(link_table, "link")
        self.subjects = self._load(subject_table, "subject")
        self.texts = self._load(text_table, "text")

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
        return self._load_table_attribute(
            table_name, column_name, COUNTRY, self.part, limit, offset
        )

    def _load_table_attribute(
        self,
        table_name: str,
        column_name: str,
        country: str = "",
        part: int = 0,
        limit: int = 0,
        offset: int = 0,
    ) -> List[str]:
        def _load_once() -> List[str]:
            conn = _get_db_connection()
            if conn is None:
                raise RuntimeError(
                    f"unable to connect to database for {table_name}.{column_name}"
                )

            try:
                cursor = conn.cursor()
                query = f"SELECT `{column_name}` FROM `{table_name}`"
                params = []
                where_clauses = []
                if country:
                    where_clauses.append("LOWER(country) = %s")
                    params.append(country.lower())

                if self.part:
                    where_clauses.append("part = %s")
                    params.append(self.part)

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
                raise RuntimeError(
                    f"failed to load {table_name}.{column_name}: {exc}"
                ) from exc
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        return _run_with_retry(
            f"load {table_name}.{column_name} from database",
            _load_once,
            default=[],
        )

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

    # def _next(self, items: List[str], key: str) -> str:
    #     if not items:
    #         return ""
    #     idx = self._idx[key]
    #     self._idx[key] = (idx + 1) % len(items)
    #     return items[idx]

    def _next(self, items: List[str], key: str) -> str:
        return random.choice(items) if items else ""

    def is_valid(self) -> bool:
        return bool(self.subjects and self.texts and self.links and self.hyperlinks)


class RecipientManager:
    def __init__(self, account_count: int):
        self.queue = deque()
        self._sent_count = 0
        self._total_loaded = 0
        self.account_count = max(0, account_count)
        # self.recipients_needed = round(
        #     self.account_count
        #     * (SUBSEQUENT_BATCHES + 1)
        #     * SUBSEQUENT_BATCH_BCC
        #     * EMAIL_ROUNDS
        # )
        self.recipients_needed = round(
            self.account_count
            * (SUBSEQUENT_BATCHES + 1)
            * sum([SUBSEQUENT_BATCH_BCC, SUBSEQUENT_BATCH_BCC_LOWER])
            / len([SUBSEQUENT_BATCH_BCC, SUBSEQUENT_BATCH_BCC_LOWER])
            * EMAIL_ROUNDS
        )

        self._load()

    def _load(self):
        def _load_once():
            conn = _get_db_connection()
            if conn is None:
                raise RuntimeError("unable to connect to database for recipients")

            try:
                try:
                    batch_number = (
                        int(str(BATCH_NUMBER).strip())
                        if BATCH_NUMBER is not None
                        else 0
                    )
                except (TypeError, ValueError):
                    batch_number = 0

                cursor = conn.cursor()
                # if SERVER_IP in NEW_RECIPIENT_LIST:
                #     log("loading from sender_recipients_2 recipients")
                #     query = (
                #         "SELECT recipient_email FROM sender_recipients_2 "
                #         "WHERE server_ip = %s AND COALESCE(country, '') = %s "
                #         "ORDER BY recipient_email "
                #         "LIMIT 1000000 offset 0"
                #     )
                # elif batch_number == 500:
                #     log("loading from list2 recipients")
                #     query = (
                #         "SELECT recipient_email FROM sender_recipients_2 "
                #         "WHERE server_ip = %s AND COALESCE(country, '') = %s "
                #         "ORDER BY recipient_email "
                #         "LIMIT 1000000 offset 0"
                #     )
                # else:
                #     log("loading from sender_recipient recipients")
                #     query = (
                #         "SELECT recipient_email FROM sender_recipients "
                #         "WHERE server_ip = %s AND COALESCE(country, '') = %s "
                #         "ORDER BY recipient_email "
                #         "LIMIT 1000000 offset 0"
                #     )
                log("loading from sender_recipient recipients")
                query = (
                    "SELECT recipient_email FROM sender_recipients "
                    "WHERE server_ip = %s AND COALESCE(country, '') = %s "
                    "ORDER BY recipient_email "
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

                selection_label = "all"
                if batch_number == 500:
                    split_index = len(recipients) // 2
                    if batch_number % 2 == 1:
                        recipients = recipients[:split_index]
                        selection_label = "first_half"
                    else:
                        recipients = recipients[split_index:]
                        selection_label = "second_half"

                with _recipient_window_lock:
                    global _recipient_window_start
                    if recipients:
                        total_recipients = len(recipients)
                        start = _recipient_window_start % total_recipients
                        window_length = min(self.recipients_needed, total_recipients)
                        end = start + window_length

                        if end <= total_recipients:
                            selected_recipients = recipients[start:end]
                            _recipient_window_start = end % total_recipients
                            selection_label = f"{selection_label} {start}:{end}"
                        else:
                            selected_recipients = (
                                recipients[start:]
                                + recipients[: end - total_recipients]
                            )
                            _recipient_window_start = end % total_recipients
                            selection_label = (
                                f"{selection_label} {start}:{total_recipients}+"
                                f"0:{end - total_recipients}"
                            )
                    else:
                        selected_recipients = []

                recipients = selected_recipients
                random.shuffle(recipients)

                self.queue = deque()
                self._total_loaded = 0
                self.queue.extend(recipients)
                self._total_loaded = len(recipients)

                log(
                    f"✓ Loaded {len(recipients)} valid recipients from DB ({selection_label})"
                )
            except Exception as exc:
                raise RuntimeError(
                    f"failed to load recipients from database: {exc}"
                ) from exc
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        _run_with_retry("load recipients from database", _load_once, default=None)

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
    def __init__(self, part: int):
        self.part = part
        self.accounts: List[Dict] = []
        self._load()

    def _load(self):
        def _load_once():
            conn = _get_db_connection()
            if conn is None:
                raise RuntimeError("unable to connect to database for accounts")

            try:
                cursor = conn.cursor()
                query = (
                    f"SELECT email, pass, recovery FROM {_get_sender_accounts_table()} "
                    "WHERE server_ip = %s AND COALESCE(country, '') = %s "
                )
                params = [SERVER_IP, COUNTRY]
                if BATCH_NUMBER:
                    query += " AND batch = %s "
                    params.append(f"batch_{BATCH_NUMBER}")
                query += " LIMIT 2000 OFFSET 0"
                cursor.execute(query, params)
                rows = cursor.fetchall()
                cursor.close()

                accounts = []
                for row in rows:
                    if not row or row[0] is None:
                        continue
                    email = str(row[0]).strip()
                    password = str(row[1]).strip()
                    recovery = (
                        str(row[2]).strip()
                        if len(row) > 2 and row[2] is not None
                        else ""
                    )
                    if not email:
                        continue
                    accounts.append(
                        {
                            "email": email,
                            "password": password,
                            "recovery": recovery,
                            "creation_date": "",
                        }
                    )
                # if self.part in {1, 2, 3}:
                #     start = len(accounts) * (self.part - 1) // 3
                #     end = len(accounts) * self.part // 3
                #     accounts = accounts[start:end]
                self.accounts = accounts
                log(f"Accounts: {len(self.accounts)}")
            except Exception as exc:
                raise RuntimeError(
                    f"failed to load accounts from database: {exc}"
                ) from exc
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        _run_with_retry("load accounts from database", _load_once, default=None)

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

    if _shutdown.is_set():
        return False, "SHUTDOWN"
    # global SALNJLA
    # delay = random.uniform(3, 5)
    # if _shutdown.wait(delay):
    #     return False, "SHUTDOWN"

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
                    wait = 30
                except:
                    wait = 30
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
            return True, "RECIPIENT_LIMIT"
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
    # return (
    #     f'<html><body><div style="font-family:Arial,sans-serif;'
    #     f'font-size:14px;color:#333;">{text}<br><br>'
    #     f'<a href="{link}">{hyperlink}</a></div></body></html>'
    # )
    return (
        f'<html><body><div style="font-family:Arial,sans-serif;'
        f'font-size:14px;color:#333;">{text}<br><br>{hyperlink}: {link}</div></body></html>'
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


def process_account_batch_looper(
    state: AccountState,
    recipients: "RecipientManager",
    content: "ContentManager",
) -> Dict:
    total_sent = 0
    h, link, subj, body = content.get()
    for mess_num in range(EMAIL_ROUNDS):
        # process account 10 times if everything ok, keeping track of sent count and failed status. if failed, break and return the status, else continue to next iteration. if sent count is 0, break and return the status. if completed, break and return the status. if shutdown, break and return the status.
        # The 10 rounds are not for fail mitigation. They ensure sending 10 times the batch size of emails per account, as per the EMAIL_ROUNDS constant. The loop should not exit early, but run all 10 rounds.
        # Exit only in case of error, shutdown, or if the account has completed its sending quota.
        result = process_account_batch(
            state,
            recipients,
            content,
            mess_num=mess_num,
            h=h,
            link=link,
            subj=subj,
            body=body,
        )

        if result.get("failed") or result.get("skipped"):
            return result

        if state.sent == 0:
            log(f"  - {_short(state.account['email'])}: no emails sent; skipping")
            return {"skipped": True}
        if state.completed:
            log(f"  - {_short(state.account['email'])}: completed sending")
            return result
        if _shutdown.is_set():
            log(f"  - {_short(state.account['email'])}: shutdown initiated; skipping")
            return {"skipped": True}

        if result.get("sent"):
            total_sent += result["sent"]

    state.batch_round += 1
    return result


def process_account_batch(
    state: AccountState,
    recipients: "RecipientManager",
    content: "ContentManager",
    mess_num: int,
    h: str,
    link: str,
    subj: str,
    body: str,
) -> Dict:

    if _shutdown.is_set() or state.failed or not recipients.has_more():
        if _shutdown.is_set():
            # log("Shutdown initiated!")
            pass
        elif state.failed:
            print("Acc has failed")
        elif recipients.has_more():
            print("No more recipients")
        else:
            print("Account unable to process")
        return {"skipped": True}

    session = make_session()
    try:
        email = state.account["email"]

        log(f"[{state.account_idx + 1}/{state.total_accounts}] {email}")
        if not state.started:
            state.started = True

        if state.batch_round == 0:
            if mess_num == 0:
                batch_size = 1
                label = "warmup-m1"
            else:
                batch_size = random.randint(FIRST_BATCH_BCC_LOWER, FIRST_BATCH_BCC)
            label = "warmup-m2"
        else:
            if mess_num == 0:
                batch_size = 1
                label = f"b{state.batch_round + 1}-m1"
            else:
                batch_size = random.randint(
                    SUBSEQUENT_BATCH_BCC_LOWER, SUBSEQUENT_BATCH_BCC
                )
                label = f"b{state.batch_round + 1}-m{mess_num + 1}"

        batch = recipients.get_batch(batch_size)
        if not batch:
            state.completed = True
            return {"skipped": True}

        if not state.token:
            state.token = get_token(email)
            # state.token = True
            if not state.token:
                recipients.return_batch(batch)
                state.failed = True
                state.error = "AUTH_FAILED"
                log("Auth failed!")
                return {"failed": True, "error": "AUTH_FAILED", "sent": 0}

            log(f"  ✓ {_short(email)}: token OK")

        # print(f"Sending email for account {state.account['email']} with batch: {batch}")

        html = build_html(body, h, link)
        # print(html)
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
        # time.sleep(STAGGER_)

        if state.batch_round == 0:
            delay = random.uniform(BATCH_DELAY_MIN, BATCH_DELAY_MAX)
            if _shutdown.wait(delay):
                return {"skipped": True}

        if state.batch_round > SUBSEQUENT_BATCHES + 1:
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


def _safe_divide(numerator: int | float, denominator: int | float) -> float:
    return numerator / denominator if denominator != 0 else 0.0


class DailyStatsTracker:
    def __init__(self):
        self.stats_path = STATS_FILE
        self.data = self._load()
        self._reset_if_new_utc_day()

    def _utc_day(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def _empty_day(self) -> Dict:
        return {
            "total_senders": 0,
            "total_failed_senders_today": 0,
            "total_recipients_sent_today": 0,
            "total_batches_sent_today": 0,
            "average_recipients_per_sender": 0,
            "average_batch_time": 0,
            "average_batch_per_run": 0,
            "_successful_senders": 0,
            "_sender_emails": [],
            "_failed_sender_emails": [],
            "_batch_time_total": 0.0,
            "_runs": 0,
        }

    def _load(self) -> Dict:
        try:
            if self.stats_path.exists():
                loaded = json.loads(self.stats_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    return loaded
        except (OSError, json.JSONDecodeError):
            pass
        return {"date": self._utc_day(), "days": {}, **self._empty_day()}

    def _save(self):
        self.stats_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.stats_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(temp_path, self.stats_path)

    def _reset_if_new_utc_day(self):
        today = self._utc_day()
        saved_day = str(self.data.get("date", ""))
        if saved_day != today:
            if saved_day and saved_day in self.data.get("days", {}):
                pass
            elif saved_day:
                previous = {
                    key: value
                    for key, value in self.data.items()
                    if key in self._empty_day()
                }
                if previous:
                    self.data.setdefault("days", {})[saved_day] = previous
            self.data = {
                "date": today,
                "days": self.data.get("days", {}),
                **self._empty_day(),
            }
            self._save()
        else:
            self.data.setdefault("days", {})
            self.data.setdefault("date", today)
            self._save()

    def _archive_current(self):
        day = str(self.data.get("date", ""))
        if day:
            self.data.setdefault("days", {})[day] = {
                key: value
                for key, value in self.data.items()
                if key in self._empty_day()
            }

    def _day_stats(self) -> Dict:
        return {
            key: self.data.get(key, default)
            for key, default in self._empty_day().items()
        }

    def _refresh_averages(self):
        today = self._day_stats()
        recipients = today["total_recipients_sent_today"]
        senders = today["total_senders"]
        batches = today["total_batches_sent_today"]
        runs = today["_runs"]
        self.data.pop("average_senders_sent_per_email", None)
        self.data["average_recipients_per_sender"] = _safe_divide(recipients, senders)
        self.data["average_batch_time"] = _safe_divide(
            today["_batch_time_total"], batches
        )
        self.data["average_batch_per_run"] = _safe_divide(batches, runs)
        self._archive_current()

    def start_run(self, sender_accounts: List[Dict] | None = None):
        with _stats_lock:
            self._reset_if_new_utc_day()
            sender_emails = self.data.setdefault("_sender_emails", [])
            for account in sender_accounts or []:
                email = str(account.get("email", "")).strip().lower()
                if email and email not in sender_emails:
                    sender_emails.append(email)

            self.data["total_senders"] = len(sender_emails)
            failed_emails = self.data.setdefault("_failed_sender_emails", [])
            self.data["total_failed_senders_today"] = len(failed_emails)
            self.data["_runs"] = int(self.data.get("_runs", 0)) + 1
            self._refresh_averages()
            self._save()

    def record_sender(self, account: Dict, success: bool):
        email = str(account.get("email", "")).strip().lower()
        with _stats_lock:
            self._reset_if_new_utc_day()
            sender_emails = self.data.setdefault("_sender_emails", [])
            failed_emails = self.data.setdefault("_failed_sender_emails", [])
            if email and email not in sender_emails:
                sender_emails.append(email)
            if not success and email and email not in failed_emails:
                failed_emails.append(email)

            self.data["total_senders"] = len(sender_emails)
            self.data["total_failed_senders_today"] = len(failed_emails)
            if success and email in failed_emails:
                failed_emails.remove(email)
                self.data["total_failed_senders_today"] = len(failed_emails)
            self._refresh_averages()
            self._save()

    def _sync_server_stats(self):
        if not SERVER_IP:
            return

        conn = None
        try:
            conn = _get_db_connection()
            if conn is None:
                return

            recipients = int(self.data.get("total_recipients_sent_today", 0) or 0)
            senders = int(self.data.get("total_senders", 0) or 0)
            sent_percentage = _safe_divide(recipients * 100, senders * 1000)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO smtp_server_stats (
                    server_ip, stat_date, total_senders,
                    total_failed_senders_today, total_recipients_sent_today,
                    average_recipients_per_sender, sent_recipients_percentage,
                    total_batches_sent_today, average_batch_time,
                    average_batch_per_run, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP())
                ON DUPLICATE KEY UPDATE
                    stat_date = VALUES(stat_date),
                    total_senders = VALUES(total_senders),
                    total_failed_senders_today = VALUES(total_failed_senders_today),
                    total_recipients_sent_today = VALUES(total_recipients_sent_today),
                    average_recipients_per_sender = VALUES(average_recipients_per_sender),
                    sent_recipients_percentage = VALUES(sent_recipients_percentage),
                    total_batches_sent_today = VALUES(total_batches_sent_today),
                    average_batch_time = VALUES(average_batch_time),
                    average_batch_per_run = VALUES(average_batch_per_run),
                    updated_at = UTC_TIMESTAMP()
                """,
                (
                    str(SERVER_IP),
                    datetime.now(UTC).date(),
                    senders,
                    int(self.data.get("total_failed_senders_today", 0) or 0),
                    recipients,
                    float(self.data.get("average_recipients_per_sender", 0) or 0),
                    sent_percentage,
                    int(self.data.get("total_batches_sent_today", 0) or 0),
                    float(self.data.get("average_batch_time", 0) or 0),
                    float(self.data.get("average_batch_per_run", 0) or 0),
                ),
            )
            conn.commit()
            cursor.close()
        except Exception as exc:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            print(f"Failed to sync SMTP server stats: {exc}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def record_batch(self, recipients_sent: int, batch_seconds: float):
        with _stats_lock:
            self._reset_if_new_utc_day()
            self.data["total_recipients_sent_today"] = int(
                self.data.get("total_recipients_sent_today", 0)
            ) + max(0, recipients_sent)
            self.data["total_batches_sent_today"] = (
                int(self.data.get("total_batches_sent_today", 0)) + 1
            )
            self.data["_batch_time_total"] = float(
                self.data.get("_batch_time_total", 0.0)
            ) + max(0.0, batch_seconds)
            self._refresh_averages()
            self._save()
            self._sync_server_stats()


_daily_stats = DailyStatsTracker()


class StatsTracker:
    def __init__(
        self,
        total_accounts: int,
        total_recipients: int,
        sender_accounts: List[Dict] | None = None,
    ):
        self.total_accounts = total_accounts
        self.total_recipients = total_recipients
        self.total_sent = 0
        self.ok_count = 0
        self.fail_count = 0
        self.processed_accounts = []
        self.start_time = time.time()
        _daily_stats.start_run(sender_accounts)

    def update(self, account: Dict, success: bool, sent: int):
        with _stats_lock:
            if success:
                self.ok_count += 1
            else:
                self.fail_count += 1
            self.total_sent += sent
            self.processed_accounts.append(account)
        _daily_stats.record_sender(account, success)

    def record_batch(self, recipients_sent: int, batch_seconds: float):
        _daily_stats.record_batch(recipients_sent, batch_seconds)

    def get_stats(self) -> Dict:
        with _stats_lock:
            elapsed = time.time() - self.start_time
            rate = _safe_divide(self.total_sent, elapsed)
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
        time.sleep(random.randint(10, 80))
        while retries < 10:
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
                log("DONE SENDING!\n\n\n")

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
            time.sleep(random.randint(10, 80))


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


def sync_pc_time() -> bool:
    """Sync local PC time with the system NTP/time service."""
    try:
        system = platform.system().lower()
        if system == "windows":
            subprocess.run(
                ["w32tm", "/resync"],
                check=True,
                capture_output=True,
                text=True,
            )
            return True

        if system in {"linux", "darwin"}:
            subprocess.run(
                ["timedatectl", "set-ntp", "true"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["timedatectl", "timesync-status"],
                check=True,
                capture_output=True,
                text=True,
            )
            return True

        return False
    except subprocess.CalledProcessError:
        return False
    except Exception:
        return False


def update_server_status(status: str) -> bool:
    conn = _get_db_connection()
    if conn is None:
        return False

    cursor = None
    try:
        server_ip = str(SERVER_IP or "").strip()
        if not server_ip:
            return False

        cursor = conn.cursor()
        now_utc = datetime.now(UTC)
        cursor.execute(
            "SELECT server_id FROM server_status WHERE server_ip = %s LIMIT 1",
            (server_ip,),
        )
        if cursor.fetchone():
            cursor.execute(
                "UPDATE server_status SET last_uptime = %s, status = %s "
                "WHERE server_ip = %s",
                (now_utc, status, server_ip),
            )
        else:
            cursor.execute(
                "INSERT INTO server_status (server_ip, last_uptime, status) "
                "VALUES (%s, %s, %s)",
                (server_ip, now_utc, status),
            )

        conn.commit()
        return True
    except Exception as exc:
        conn.rollback()
        log(f"Failed to update SMTP server status: {exc}")
        return False
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def get_action_status() -> tuple[bool, dict]:
    def _fetch_action_status():
        sync_pc_time()
        conn = _get_db_connection()
        if conn is None:
            raise RuntimeError("No database connection")

        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT action, status, date_time, batch_number FROM manualbot_actions_tracker "
                "ORDER BY action_id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return False, {"batch_number": None}

            action = str(row[0]).strip().lower() if row[0] is not None else ""
            status = str(row[1]).strip().lower() if row[1] is not None else ""
            timestamp = row[2] if isinstance(row[2], datetime) else None
            if timestamp is not None:
                timestamp = (
                    timestamp.replace(tzinfo=UTC)
                    if timestamp.tzinfo is None
                    else timestamp.astimezone(UTC)
                )
            batch_number = row[3]

            if not timestamp or not isinstance(timestamp, datetime):
                return False, {"batch_number": batch_number}

            if datetime.now(UTC) - timestamp > timedelta(minutes=3):
                return False, {"batch_number": batch_number}

            return action in {"run_bots", "update"} and status == "true", {
                "batch_number": "update" if action == "update" else batch_number,
                "signal_timestamp": timestamp,
            }
        finally:
            try:
                conn.close()
            except Exception:
                pass

    return _run_with_retry(
        "check action status from database",
        _fetch_action_status,
        default=(False, {"batch_number": None}),
    )


def get_due_smtp_schedule() -> dict:
    """Return the batch number for a scheduler record within 1 minute of now in UTC."""
    conn = _get_db_connection()
    if conn is None:
        return {"status": False, "batch": None}

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT schedule_batch, schedule_time FROM oneapp.smtp_scheduler"
        )
        rows = cursor.fetchall()

        # rows = [(f"batch_{i}", datetime.now(UTC) + timedelta(minutes=i * 55)) for i in range(5)]  # Mock data for testing
        now_utc = datetime.now(UTC)
        window = timedelta(minutes=3)

        for schedule_batch, schedule_time in rows:
            try:
                batch_name = str(schedule_batch or "").strip()
                # if not batch_name.lower().startswith("batch_"):
                #     continue

                if isinstance(schedule_time, str):
                    parsed_time = datetime.fromisoformat(
                        schedule_time.replace("Z", "+00:00")
                    )
                else:
                    parsed_time = schedule_time

                if parsed_time is None:
                    continue

                if parsed_time.tzinfo is None:
                    parsed_time = parsed_time.replace(tzinfo=UTC)
                else:
                    parsed_time = parsed_time.astimezone(UTC)

                if (
                    abs((parsed_time - now_utc).total_seconds())
                    <= window.total_seconds()
                ):
                    try:
                        batch_value = int(batch_name.replace("batch_", "", 1))
                    except ValueError:
                        continue
                    log(
                        f"⏰⏰ : SMTP schedule for now found: batch {batch_value} at {parsed_time.isoformat()}\n\n"
                    )
                    return {
                        "status": True,
                        "batch": batch_value,
                        "signal_timestamp": parsed_time,
                    }
            except Exception:
                continue

        return {"status": False, "batch": None}
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def get_due_smtp_schedule_1hr() -> dict:
    """Return the batch number for a scheduler record 60-70 minutes ago in UTC."""
    conn = _get_db_connection()
    if conn is None:
        return {"status": False, "batch": None}

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT schedule_batch, schedule_time FROM oneapp.smtp_scheduler"
        )
        rows = cursor.fetchall()
        now_utc = datetime.now(UTC)
        oldest_schedule_age = timedelta(minutes=65)
        newest_schedule_age = timedelta(minutes=60)

        for schedule_batch, schedule_time in rows:
            try:
                batch_name = str(schedule_batch or "").strip()

                if isinstance(schedule_time, str):
                    parsed_time = datetime.fromisoformat(
                        schedule_time.replace("Z", "+00:00")
                    )
                else:
                    parsed_time = schedule_time

                if parsed_time is None:
                    continue

                if parsed_time.tzinfo is None:
                    parsed_time = parsed_time.replace(tzinfo=UTC)
                else:
                    parsed_time = parsed_time.astimezone(UTC)

                schedule_age = now_utc - parsed_time
                if newest_schedule_age <= schedule_age <= oldest_schedule_age:
                    try:
                        batch_value = int(batch_name.replace("batch_", "", 1))
                    except ValueError:
                        continue
                    log(
                        f"⏰⏰ : SMTP schedule from 60-70 minutes ago found: batch {batch_value} at {parsed_time.isoformat()}\n\n"
                    )
                    return {"status": True, "batch": batch_value}
            except Exception:
                continue

        return {"status": False, "batch": None}
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def get_due_smtp_schedule_2hr() -> dict:
    """Return the batch number for a scheduler record 60-70 minutes ago in UTC."""
    conn = _get_db_connection()
    if conn is None:
        return {"status": False, "batch": None}

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT schedule_batch, schedule_time FROM oneapp.smtp_scheduler"
        )
        rows = cursor.fetchall()
        now_utc = datetime.now(UTC)
        oldest_schedule_age = timedelta(minutes=125)
        newest_schedule_age = timedelta(minutes=120)

        for schedule_batch, schedule_time in rows:
            try:
                batch_name = str(schedule_batch or "").strip()

                if isinstance(schedule_time, str):
                    parsed_time = datetime.fromisoformat(
                        schedule_time.replace("Z", "+00:00")
                    )
                else:
                    parsed_time = schedule_time

                if parsed_time is None:
                    continue

                if parsed_time.tzinfo is None:
                    parsed_time = parsed_time.replace(tzinfo=UTC)
                else:
                    parsed_time = parsed_time.astimezone(UTC)

                schedule_age = now_utc - parsed_time
                if newest_schedule_age <= schedule_age <= oldest_schedule_age:
                    try:
                        batch_value = int(batch_name.replace("batch_", "", 1))
                    except ValueError:
                        continue
                    log(
                        f"⏰⏰ : SMTP schedule from 60-70 minutes ago found: batch {batch_value} at {parsed_time.isoformat()}\n\n"
                    )
                    return {"status": True, "batch": batch_value}
            except Exception:
                continue

        return {"status": False, "batch": None}
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def update_schedule_smtp_1():
    """Refresh the SMTP schedule when no batch is scheduled in the future."""
    # print("SMTP schedule update: checking scheduler table...")
    conn = _get_db_connection()
    if conn is None:
        print("SMTP schedule update: database connection unavailable.")
        return False, "Unable to connect to database"

    cursor = None
    try:
        cursor = conn.cursor()
        now_utc = datetime.now(UTC)
        cursor.execute(
            "SELECT schedule_time FROM oneapp.smtp_scheduler "
            "WHERE schedule_time IS NOT NULL ORDER BY schedule_time DESC"
        )
        schedule_times = []
        for (schedule_time,) in cursor.fetchall():
            if isinstance(schedule_time, str):
                try:
                    schedule_time = datetime.fromisoformat(
                        schedule_time.replace("Z", "+00:00")
                    )
                except ValueError:
                    continue
            if schedule_time is None:
                continue
            if schedule_time.tzinfo is None:
                schedule_time = schedule_time.replace(tzinfo=UTC)
            schedule_times.append(schedule_time.astimezone(UTC))

        # print(
        #     f"SMTP schedule update: found {len(schedule_times)} schedule time(s); "
        #     f"current UTC time is {now_utc.isoformat()}."
        # )
        if schedule_times and schedule_times[0] > now_utc:
            # print(
            #     "SMTP schedule update: future schedule already exists at "
            #     f"{schedule_times[0].isoformat()}. No changes made."
            # )
            return True, "A future SMTP schedule already exists."

        if schedule_times:
            start_time = schedule_times[0] + timedelta(minutes=180)
            if start_time <= now_utc:
                print(
                    "SMTP schedule update: calculated start is in the past; "
                    "starting 10 minutes from now."
                )
                start_time = now_utc + timedelta(minutes=10)
        else:
            print(
                "SMTP schedule update: no existing schedules; starting 10 minutes from now."
            )
            start_time = now_utc + timedelta(minutes=10)

        print(
            f"SMTP schedule update: first batch scheduled for {start_time.isoformat()}."
        )
        for batch_index in range(1, 8):
            schedule_time = start_time + timedelta(minutes=180 * (batch_index - 1))
            batch_name = f"batch_{batch_index}"
            cursor.execute(
                "UPDATE oneapp.smtp_scheduler SET schedule_time = %s "
                "WHERE schedule_batch = %s",
                (schedule_time.replace(tzinfo=None), batch_name),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT INTO oneapp.smtp_scheduler "
                    "(schedule_batch, schedule_time) VALUES (%s, %s)",
                    (batch_name, schedule_time.replace(tzinfo=None)),
                )
                print(
                    f"SMTP schedule update: inserted {batch_name} at {schedule_time.isoformat()}."
                )
            else:
                print(
                    f"SMTP schedule update: updated {batch_name} at {schedule_time.isoformat()}."
                )

        conn.commit()
        print("SMTP schedule update: committed successfully.")
        return True, "SMTP schedule updated successfully."
    except Exception as exc:
        conn.rollback()
        print(f"SMTP schedule update failed: {exc}")
        return False, f"Unable to update SMTP schedule: {exc}"
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def is_server_authorized() -> bool:
    if not SERVER_IP:
        return False

    conn = _get_db_connection()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM servers_details WHERE server_ip = %s LIMIT 1",
            (SERVER_IP,),
        )
        row = cursor.fetchone()
        cursor.close()
        return row is not None
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def is_linux_server() -> bool:
    if not SERVER_IP:
        return False

    conn = _get_db_connection()
    if conn is None:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT server_type FROM oneapp.servers_details WHERE server_ip = %s LIMIT 1",
            (SERVER_IP,),
        )
        row = cursor.fetchone()
        cursor.close()
        return bool(
            row
            and row[0]
            and (
                str(row[0]).strip().lower().startswith("debian")
                or str(row[0]).strip().lower().startswith("contabo")
            )
        )
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def check_manual_shutdown_signal() -> bool:
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
        timestamp = row[2].replace(tzinfo=timezone.utc) if row[2] else None

        if not timestamp or not isinstance(timestamp, datetime):
            return False

        if datetime.now(UTC) - timestamp > timedelta(minutes=5):
            return False

        return action == "manual_shutdown" and status == "true"
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _manual_shutdown_watcher():
    global _shutdown_watcher_started, _shutdown_reason
    last_shutdown_timestamp = None
    while True:
        if _shutdown.is_set() and _shutdown_reason == "manual":
            _shutdown_watcher_started = False
            return

        if check_manual_shutdown_signal():
            now = datetime.now(UTC)
            if last_shutdown_timestamp is None or (
                now - last_shutdown_timestamp
            ) > timedelta(seconds=1):
                last_shutdown_timestamp = now
                log("** Manual shutdown signal received from database.**")
                _shutdown_reason = "manual_triggered"
                _shutdown.set()
                _shutdown_watcher_started = False
                return

        time.sleep(5)


def _cleanup_batch_memory(run_state):
    global _shared_cache

    recipients = run_state.get("recipients")
    if recipients is not None:
        with _recipient_lock:
            recipients.queue.clear()

    accounts = run_state.get("accounts")
    if accounts is not None:
        accounts.accounts.clear()

    content = run_state.get("content")
    if content is not None:
        content.hyperlinks.clear()
        content.links.clear()
        content.subjects.clear()
        content.texts.clear()

    stats = run_state.get("stats")
    if stats is not None:
        with _stats_lock:
            stats.processed_accounts.clear()

    account_states = run_state.get("account_states")
    if account_states is not None:
        account_states.clear()

    run_state.clear()
    if _cache_lock.acquire(timeout=LOCK_TIMEOUT_SECONDS):
        try:
            _shared_cache = msal.SerializableTokenCache()
        finally:
            _cache_lock.release()
    else:
        log("Cache reset skipped: timed out waiting for cache lock.")
    gc.collect()


def main_batches(
    batch_number: int = 1,
    app_choice: int = 1,
    signal_timestamp: Optional[datetime] = None,
    part: int = 1,
):
    update_server_status("Signal received! Loading data...")
    run_state = {}
    try:
        _main_batches(batch_number, app_choice, signal_timestamp, part, run_state)
    finally:
        _cleanup_batch_memory(run_state)


def _main_batches(
    batch_number: int,
    app_choice: int,
    signal_timestamp: datetime | None,
    part: int,
    run_state,
):
    print("***********************Starting***********************************\n\n")
    signal_epoch = (
        signal_timestamp.timestamp() if signal_timestamp is not None else time.time()
    )

    global \
        BATCH_NUMBER, \
        SENDER_APP, \
        MAX_CONCURRENT_ACCOUNTS, \
        SUBSEQUENT_BATCHES, \
        SERVER_IP, \
        EMAIL_ROUNDS
    SENDER_APP = app_choice
    print(f"Selected {'New' if SENDER_APP == 2 else 'Old'} app.")

    BATCH_NUMBER = str(batch_number)
    print(f"Selected batch: {BATCH_NUMBER}")
    SUBSEQUENT_BATCHES = 7
    EMAIL_ROUNDS = 3
    time.sleep(5)

    log("Current settings:")
    log(f"  SERVER_IP: {SERVER_IP}")
    log(f"  COUNTRY: {COUNTRY}")
    log(f"  FIRST_BATCH_BCC: {FIRST_BATCH_BCC}")
    log(f"  SUBSEQUENT_BATCH_BCC: {SUBSEQUENT_BATCH_BCC}")
    log(f"  SUBSEQUENT_BATCHES: {SUBSEQUENT_BATCHES}")
    log(f"  MAX_CONCURRENT_BATCHES: {MAX_CONCURRENT_BATCHES}")
    log(f"  MAX_CONCURRENT_ACCOUNTS: {MAX_CONCURRENT_ACCOUNTS}")
    log(f"  BATCH_DELAY: {BATCH_DELAY_MIN}-{BATCH_DELAY_MAX}s")
    log(f"  STAGGER: {STAGGER_MIN}-{STAGGER_MAX}s")
    log(f"  SAVE_TO_SENT: {SAVE_TO_SENT}")
    log("")

    log("=" * 55)
    log("")
    log("EMAIL SENDER | Graph API")
    log(f"Selected batch: {BATCH_NUMBER}")
    log(
        f"Config: warmup={FIRST_BATCH_BCC} big={SUBSEQUENT_BATCHES}x"
        f"{SUBSEQUENT_BATCH_BCC} batch_threads={MAX_CONCURRENT_BATCHES}"
    )
    log(f"        account_threads={MAX_CONCURRENT_ACCOUNTS}")
    log("=" * 55)
    log(f"PART: {part} | EMAIL_ROUNDS: {EMAIL_ROUNDS}")

    log("Loading senders. Please wait...")

    accounts = AccountManager(part)
    run_state["accounts"] = accounts
    if not accounts.accounts:
        log("✗ No accounts. Exiting.")
        return

    log("Loading content. Please wait...")
    content = ContentManager(part)
    run_state["content"] = content
    if not content.is_valid():
        log("✗ Missing content (need subjects, texts, links). Exiting.")
        return

    log("Loading recipients. Please wait...")
    recipients = RecipientManager(len(accounts.accounts))
    run_state["recipients"] = recipients
    if not recipients.queue:
        log("✗ No recipients. Exiting.")
        return

    if not load_cache_local(os.path.join(utils_dir, "cache.bin")):
        return

    total_acc = len(accounts.accounts)
    total_rcpt = recipients._total_loaded
    batch_count = SUBSEQUENT_BATCHES + 1
    if batch_count <= 0:
        log("Invalid number of subsequent batches. Exiting.")
        return
    max_per_account = (FIRST_BATCH_BCC) + SUBSEQUENT_BATCHES * (SUBSEQUENT_BATCH_BCC)
    if max_per_account <= 0:
        log("Invalid recipient capacity per account. Exiting.")
        return
    est_accounts_needed = (total_rcpt + max_per_account - 1) // max_per_account

    log(f"Ready: {total_acc} accounts | {total_rcpt} recipients")
    log(f"Max/account: {max_per_account} | Est. accounts needed: {est_accounts_needed}")
    log("-" * 55)

    if signal_timestamp is not None:
        elapsed = datetime.now(UTC) - signal_timestamp
        wait_seconds = max(0, 0.5 * 60 - elapsed.total_seconds())

        if wait_seconds > 0:
            log(
                f"Signal received {elapsed.total_seconds():.1f}s ago. "
                f"Waiting {wait_seconds:.1f}s before starting run."
            )
            time.sleep(wait_seconds)

    log("Run signal synced. Starting batch processing...")

    _start_runtime_watchdog()
    global _shutdown_watcher_started
    if not _shutdown_watcher_started:
        threading.Thread(target=_manual_shutdown_watcher, daemon=True).start()
        _shutdown_watcher_started = True

    stats = StatsTracker(total_acc, total_rcpt, accounts.accounts)
    run_state["stats"] = stats
    account_states = [
        AccountState(account, idx, total_acc)
        for idx, account in enumerate(accounts.accounts)
    ]
    run_state["account_states"] = account_states

    batch_slot_seconds = MAX_RUNTIME_SECONDS / batch_count
    round_idx = 0
    batch_start_time = time.monotonic()
    while round_idx <= SUBSEQUENT_BATCHES:
        batch_start_time = time.monotonic()
        update_server_status(f"Running - b{round_idx + 1}")
        if _shutdown.is_set() and _shutdown_reason:
            log("Shutdown: stopping batch rounds. Reason: " + _shutdown_reason)
            break

        if not recipients.has_more():
            log("All recipients consumed.")
            break

        if round_idx > 0:
            MAX_CONCURRENT_ACCOUNTS = 1
        log("=" * 55)

        log(
            f"Starting batch {round_idx + 1}/{SUBSEQUENT_BATCHES + 1} || Threads: {MAX_CONCURRENT_ACCOUNTS}"
        )

        _reset_account_status()
        active_states = [s for s in account_states if not s.failed]
        log(f"Active accounts for this batch: {len(active_states)}\n\n{'=' * 55}\n")

        if not active_states:
            break

        futures = {}
        executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_ACCOUNTS)
        try:
            log(f"Submitting {len(active_states)} accounts for processing...")

            for idx, state in enumerate(active_states):
                if _shutdown.is_set():
                    break
                if not recipients.has_more():
                    break
                futures[
                    executor.submit(
                        process_account_batch_looper, state, recipients, content
                    )
                ] = state
            print(f"Submitted {len(futures)} accounts for processing.")

            batch_success = 0
            batch_fail = 0
            batch_recipients_sent = 0
            print("Waiting for account processing to complete...")
            log("=" * 55)

            while futures:
                done, not_done = wait(futures, timeout=1, return_when=FIRST_COMPLETED)

                if not done and _shutdown.is_set():
                    log("Shutdown: waiting for remaining accounts...")
                    break

                for future in done:
                    state = futures.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:
                        log(f"Error processing account future: {exc}")
                        result = {"skipped": True}

                    if _shutdown.is_set():
                        log("Shutdown: waiting for remaining accounts...")

                    if result.get("skipped"):
                        continue

                    if result.get("failed"):
                        batch_fail += 1
                    elif result.get("completed"):
                        batch_success += 1

                    batch_recipients_sent += max(0, int(result.get("sent", 0) or 0))

                    if result.get("failed") and not state.finalized:
                        state.finalized = True
                        accounts.mark_failed(state.account, result.get("error", ""))
                        stats.update(state.account, False, state.sent)
                        continue

                    if result.get("completed") and not state.finalized:
                        state.finalized = True
                        accounts.mark_done(state.account)
                        stats.update(state.account, True, state.sent)

                if _shutdown.is_set():
                    break
        finally:
            executor.shutdown(wait=True)

            log(
                f"\n{'=' * 55}\n\nBatch {round_idx + 1}/{SUBSEQUENT_BATCHES + 1} Finished\n"
            )
            log(f"Sent:       {total_rcpt - recipients.remaining()}/{total_rcpt}\n\n")
            final_stats = stats.get_stats()
            log(
                f"  Time:       {final_stats['elapsed']:.1f}s = {final_stats['elapsed'] / 60:.1f} minutes : ({final_stats['rate']:.1f}/s)"
            )
            stats.record_batch(
                batch_recipients_sent,
                time.monotonic() - batch_start_time,
            )

            if not recipients.has_more():
                log("No recipients left after batch round.")
                break

            batch_deadline = signal_epoch + (round_idx + 1) * batch_slot_seconds
            batch_now = time.time()
            batch_elapsed = batch_now - (signal_epoch + round_idx * batch_slot_seconds)
            log(
                f"Batch {round_idx + 1} used its slot for: {batch_elapsed:.1f}s = {batch_elapsed / 60:.1f} minutes"
            )
            batch_wait_time = max(random.randint(45, 80), batch_deadline - batch_now)
            if batch_wait_time > 0 and round_idx < SUBSEQUENT_BATCHES:
                log(
                    f"Waiting {batch_wait_time:.1f}s = {batch_wait_time / 60:.1f} minutes before next batch..."
                )
                _shutdown.wait(batch_wait_time)

            if _shutdown.is_set():
                log("Shutdown: stopping batch rounds. Reason: " + _shutdown_reason)
                continue

        round_idx += 1
        log("=" * 55)

        for state in account_states:
            if state.finalized:
                continue
            if state.failed and not state.finalized:
                state.finalized = True
                accounts.mark_failed(state.account, state.error or "FAILED")
                stats.update(state.account, False, state.sent)

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
    if _shutdown_reason != "manual":
        flush_db_operations()
    else:
        log("Manual shutdown: skipping DB flush.")
    log("=" * 55)


def run_smtp_bot(app_choice: int = 1):

    if not is_server_authorized():
        print("Server not authorized to run smtp")
        return

    print("Starting SMTP bot runner.")
    while True:
        if _shutdown.is_set():
            log("Clearing shutdown state and waiting for next signal.")
            _clear_shutdown_state()
        _clear_shutdown_state()

        log("Waiting for SMTP run signal...")
        batch_number = 1
        signal_time = None
        while True:
            active, data = get_action_status()
            if active:
                batch_value = data.get("batch_number")
                if str(batch_value).strip().lower() == "update":
                    update_server_status("Update signal received. Updating...")
                    update()
                else:
                    if batch_value is not None:
                        try:
                            batch_number = int(batch_value)
                        except Exception:
                            batch_number = 1
                signal_time = data.get("signal_timestamp")

                part = 1
                if batch_number > 1:
                    batch_number = 1
                    part = 2
                break

            scheduler_signal = get_due_smtp_schedule()
            if scheduler_signal.get("status"):
                # batch_number = int(scheduler_signal.get("batch", 1))
                batch_number = 1
                part = 1
                signal_time = scheduler_signal.get("signal_timestamp")
                break

            time.sleep(30)
            # scheduler_signal = get_due_smtp_schedule_1hr()
            # if scheduler_signal.get("status"):
            #     # batch_number = int(scheduler_signal.get("batch", 1))
            #     batch_number = 1
            #     part = 2
            #     signal_time = datetime.now(UTC)
            #     break
            # time.sleep(20 * 1)
            # scheduler_signal = get_due_smtp_schedule_2hr()
            # if scheduler_signal.get("status"):
            #     batch_number = 1
            #     part = 3
            #     signal_time = datetime.now(UTC)
            #     break

            if SERVER_IP == "51.91.59.107":
                update_schedule_smtp_1()
            time.sleep(random.randint(20, 30))
            update_server_status(f"{SMTP_VERSION} - standby")

        log(f"Run signal received for part {part}. Preparing to start.")
        try:
            main_batches(
                batch_number=batch_number,
                app_choice=app_choice,
                signal_timestamp=signal_time,
                part=part,
            )
        except Exception as eee:
            log(f"ERRORR WHEN RUNNING BATCH: {eee}")
        log("SMTP batch finished. Returning to signal wait loop.")
        time.sleep(5)
