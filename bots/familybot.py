import time
from datetime import timedelta, datetime, timezone
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains

from selenium.webdriver.support import expected_conditions as EC

from seleniumbase import Driver
import pandas as pd
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
import re
import json
import subprocess
import mysql.connector

import random
import msal

import pyautogui

lock = threading.Lock()

THE_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_db_connection():
    retries = 0
    while retries <= 5:
        try:
            return mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                charset="utf8mb4",
                use_unicode=True,
            )
        except Exception as exc:
            print(
                f"Database connection failed (attempt {retries + 1}/5): {exc}. Retrying connection in 5 seconds..."
            )
            time.sleep(5)
        retries += 1

    print(f"Unable to connect to database after {retries} attempts.")
    return None


def execute_db_action(action, retries=3, delay=5):
    attempt = 1
    while attempt <= retries:
        try:
            return action()
        except Exception as exc:
            if attempt == retries:
                raise
            print(
                f"Database write failed (attempt {attempt}/{retries}): {exc}. Retrying in {delay} seconds..."
            )
            time.sleep(delay)
            attempt += 1


def get_new_profile_data_from_history(retries=3, delay=5):
    """Fetch a new profile from history and claim it for the current server IP.

    If a record is already processing for this IP, refresh its processing timestamp
    and return it. Otherwise claim a new record whose state is not processing or
    processed.
    """
    attempt = 1
    while attempt <= retries:
        try:
            conn = None
            try:
                conn = get_db_connection()
                if conn is None:
                    raise Exception("Unable to connect to the database.")

                cursor = conn.cursor(dictionary=True)
                now = datetime.now()

                cursor.execute(
                    "SELECT link_id, email, pass, recovery, link "
                    "FROM familybot_extracted_family_links_history "
                    "WHERE processing_server_ip = %s AND status = 'processing'  AND LOWER(country) = %s "
                    "ORDER BY processing_date_time DESC LIMIT 1",
                    (SERVER_IP, PREFERRED_SMS_COUNTRY.lower()),
                )
                row = cursor.fetchone()

                if row:
                    cursor.execute(
                        "UPDATE familybot_extracted_family_links_history "
                        "SET processing_date_time = %s, processing_server_ip = %s "
                        "WHERE link_id = %s",
                        (now, SERVER_IP, row["link_id"]),
                    )
                    conn.commit()
                    return True, {
                        "email": row["email"],
                        "pass": row["pass"],
                        "recovery": row["recovery"],
                        "link": row["link"],
                    }

                cursor.execute(
                    "SELECT link_id FROM familybot_extracted_family_links_history "
                    "WHERE status IS NULL AND LOWER(country) = %s"
                    "ORDER BY date_time ASC LIMIT 1",
                    (PREFERRED_SMS_COUNTRY.lower(),),
                )
                row = cursor.fetchone()
                if not row:
                    return False, None

                link_id = row["link_id"]
                cursor.execute(
                    "UPDATE familybot_extracted_family_links_history "
                    "SET status = 'processing', processing_server_ip = %s, processing_date_time = %s "
                    "WHERE link_id = %s",
                    (SERVER_IP, now, link_id),
                )
                conn.commit()

                cursor.execute(
                    "SELECT email, pass, recovery, link "
                    "FROM familybot_extracted_family_links_history "
                    "WHERE link_id = %s",
                    (link_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return False, None

                return True, {
                    "email": row["email"],
                    "pass": row["pass"],
                    "recovery": row["recovery"],
                    "link": row["link"],
                }
            finally:
                if conn is not None:
                    conn.close()
        except Exception as exc:
            if attempt == retries:
                return False, None
            print(
                f"Error reading new profile from history (attempt {attempt}/{retries}): {exc}. Retrying in {delay} seconds..."
            )
            time.sleep(delay)
            attempt += 1


def load_familybot_settings():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(BASE_DIR, "settings.json")

    try:
        with open(settings_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data.get("familybot", {})
    except Exception:
        return {}


def load_app_settings():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(BASE_DIR, "settings.json")

    try:
        with open(settings_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data.get("app", {})
    except Exception:
        return {}


FAMILYBOT_SETTINGS = load_familybot_settings()
APP_SETTINGS = load_app_settings()

DB_HOST = APP_SETTINGS.get("DB_HOST")
DB_USER = APP_SETTINGS.get("DB_USER")
DB_PASSWORD = APP_SETTINGS.get("DB_PASSWORD")
DB_NAME = APP_SETTINGS.get("DB_NAME")
SERVER_IP = APP_SETTINGS.get("SERVER_IP", "0.0.0.0")


def get_setting(key, default=None):
    return FAMILYBOT_SETTINGS.get(key, default)


profile_dir = os.path.abspath(get_setting("PROFILES_DIR") or "")
chrome_location = os.path.normpath(
    os.path.join(THE_BASE_DIR, get_setting("CHROMEDRIVER_LOCATION") or "")
)

extension_dir = os.path.normpath(
    os.path.join(THE_BASE_DIR, get_setting("EXTENSION_DIR") or "")
)

EXPRESSVPN_CMD = os.path.normpath(
    os.path.join(THE_BASE_DIR, get_setting("EXPRESSVPN_CMD") or "")
)
emails_dir = os.path.normpath(
    os.path.join(THE_BASE_DIR, get_setting("EMAILS_TXT_FILE") or "")
)
PROCESSING_URLS_FILE = os.path.abspath("utils/processing_urls.txt")
MICROSOFT_LOGIN_URL = get_setting("MICROSOFT_LOGIN_URL")
HERO_SMS_API_KEY = get_setting("HERO_SMS_API_KEY")

try:
    TEMPMAIL_URL = get_setting("TEMPMAIL_URL")
    if not TEMPMAIL_URL:
        raise ValueError()
except:
    TEMPMAIL_URL = "https://temp-mail.io/en"

try:
    OUTLOOK_URL = get_setting("OUTLOOK_URL")
    if not OUTLOOK_URL:
        raise ValueError()
except:
    OUTLOOK_URL = "https://outlook.live.com/"
try:
    SAVE_COOKIES = (
        True if str(get_setting("SAVE_COOKIES", "false")).lower() == "true" else False
    )
except:
    SAVE_COOKIES = False

try:
    MAX_SIGNIN_THREADS = int(get_setting("MAX_SIGNIN_THREADS", 5))
except:
    MAX_SIGNIN_THREADS = 5

try:
    PREFERRED_SMS_COUNTRY = str(
        get_setting("PREFERRED_SMS_COUNTRY", "netherlands")
    ).lower()
    if not PREFERRED_SMS_COUNTRY:
        PREFERRED_SMS_COUNTRY = "netherlands"
except:
    PREFERRED_SMS_COUNTRY = "netherlands"

try:
    CHANGE_COUNTRY = str(get_setting("CHANGE_COUNTRY", "sweden")).lower()
    if not CHANGE_COUNTRY:
        CHANGE_COUNTRY = "sweden"
except:
    CHANGE_COUNTRY = "sweden"

try:
    CHANGE_COUNTRY_TEMP = str(get_setting("CHANGE_COUNTRY_TEMP", "australia")).lower()
    if not CHANGE_COUNTRY_TEMP:
        CHANGE_COUNTRY_TEMP = "australia"
except:
    CHANGE_COUNTRY_TEMP = "australia"

try:
    EMAIL_WAIT_TIME = int(get_setting("EMAIL_WAIT_TIME", 120))
except:
    EMAIL_WAIT_TIME = 120

try:
    CATCHA_WAIT_TIME = int(get_setting("CATCHA_WAIT_TIME", 300))
except:
    CATCHA_WAIT_TIME = 300

try:
    CREDIT_CARD_INTERVAL_HRS = int(get_setting("CREDIT_CARD_INTERVAL_HRS", 50))
    if not CREDIT_CARD_INTERVAL_HRS:
        CREDIT_CARD_INTERVAL_HRS = 50
except:
    CREDIT_CARD_INTERVAL_HRS = 50


BOT_TYPE = "familybot"

CLIENT_ID = get_setting("CLIENT_ID")
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["https://graph.microsoft.com/.default"]
CACHE_PATH = os.path.abspath(get_setting("CACHE_PATH") or "")
os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)

wait_time = 10

# ── Custom TempMail API ──────────────────────────────────────────────────────
BASE_URL = "https://affworker.com"
TEMPMAIL_API_KEY = "LCIE5xag3SScK9CH55pwoiVuPNMmkvbm2nb16ca4"


def create_email():
    url = f"{BASE_URL}/api/email/create/{TEMPMAIL_API_KEY}"
    try:
        resp = requests.post(url, timeout=15)
        data = resp.json()
        if data.get("status") == "success":
            return True, data["data"]["email"], data["data"]["email_token"]
        return False, "", ""
    except:
        return False, "", ""


def fetch_messages(email_token: str):
    url = f"{BASE_URL}/api/messages/{TEMPMAIL_API_KEY}"
    try:
        resp = requests.post(url, json={"email_token": email_token}, timeout=15)
        data = resp.json()
        if data.get("status") == "success":
            return True, data["data"]["messages"]
        return False, []
    except:
        return False, []


def wait_for_code(email_token, timeout=120, poll_interval=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        ok, messages = fetch_messages(email_token)
        if ok and messages:
            for msg in messages:
                combined = " ".join(
                    [
                        msg.get("subject", ""),
                        msg.get("from", ""),
                        msg.get("from_email", ""),
                        msg.get("content", ""),
                    ]
                )
                if "microsoft account team" in combined.lower():
                    plain = re.sub(r"<[^>]+>", " ", combined)  # strip HTML
                    match = re.search(r"Security code:\s*(\d{6})", plain)
                    if match:
                        return True, match.group(1)
        time.sleep(poll_interval)
    return False, ""


def fetch_messages_smtp2(recovery_email):
    try:
        BASE_URL = "https://affworker.com"
        TEMPMAIL_API_KEY = "LCIE5xag3SScK9CH55pwoiVuPNMmkvbm2nb16ca4"

        resp = requests.post(
            f"{BASE_URL}/api/messages/by-email/{TEMPMAIL_API_KEY}",
            json={"email": recovery_email},
            timeout=15,
        )

        data = resp.json()
        if data.get("status") == "success":
            return True, data["data"]["messages"]
        return False, []
    except:
        return False, []


def wait_for_code_by_recovery_mail(recovery_email, timeout=120, poll_interval=1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            ok, messages = fetch_messages_smtp2(recovery_email)

            last_message = messages[0]
            # print(f"Last message received: \n{last_message}\n++++++++++++++++++++++")

            current_time = datetime.now(timezone(timedelta(hours=-7)))

            message_send_time = datetime.strptime(
                last_message.get("receivedAt"), "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=timezone(timedelta(hours=-7)))

            if (
                (
                    last_message["from"].lower()
                    in ["microsoft account team", "microsoft 帐户团队"]
                )
                and (
                    last_message["subject"].lower()
                    in ["your single-use code", "你的一次性代码"]
                )
                and (((current_time - message_send_time).total_seconds()) < 30)
            ):
                plain = re.sub(
                    r"<[^>]+>", " ", last_message.get("content")
                )  # strip HTML
                match = re.search(r":\s*(\d{6})", plain)
                if match:
                    return True, match.group(1)
            time.sleep(poll_interval)
        except:
            pass
    return False, "Message not sent - Timed out"


THE_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
utils_dir = os.path.normpath(os.path.join(THE_BASE_DIR, "../utils"))


def connect_new_random_old():
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

        disconnect()
        time.sleep(1)
        try:
            random_location = str(
                random.choice(
                    pd.read_csv(
                        os.path.join(utils_dir, "express_countries.csv")
                    ).id.to_list()
                )
            )
        except:
            locations = "93,208,156,209,81,162,219,192,193,194,175,238,160,114,63,152,112,80,57,224,223,133,195,174,111,137,196,197,113,198,164,190,107,154,37,58,199,108,101,128,117,88,115,243,232,91,163,45,79,169,181,245,125,131,100,246,240,144,141,247,241,132,20,142,242,244,140,95,271,19,283,288,270,276,265,273,17,302,299,304,292,306,9,294,18,172,278,284,293,275,165,277,286,290,161,272,6,70,74,71,280,291,54,202,305,285,301,26,155,168,281,75,295,289,297,94,282,296,298,204,1,207,2,300,287,166,303,25,279,274,143,126,184,185,21,307,186,85,147,110,118,124,56,78,130,34,150,153,104,8,103,136,7,92,210,102,99,106,33,129,182,157,29,188,122,119,36,12,134,120,187,189,4,16,212,146,96,32,31,86,145,127,121,211,35,22,23,203,11,201,89,53,178,5,15,263,90,87,139,84,239,105,176,248,249,109,264".split(
                ","
            )
            random_location = str(random.choice(locations))

        connect(random_location)
        time.sleep(2)
        return True
    except:
        return False


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
                        "usa"
                        if PREFERRED_SMS_COUNTRY.lower() == "united states"
                        else PREFERRED_SMS_COUNTRY.lower()
                    )
                )
            ].id.to_list()

            random_location = str(random.choice(rand_locations))
            print(f"Connecting to : {PREFERRED_SMS_COUNTRY}")

        except:
            try:
                random_location = str(
                    random.choice(
                        pd.read_csv("utils/express_countries.csv").id.to_list()
                    )
                )
                print(
                    f"No {PREFERRED_SMS_COUNTRY} server found. Connecting to Netherlands server"
                )
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


def connect_non_us_random():
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

        disconnect()
        time.sleep(1)
        locations = "93,208,156,209,81,162,219,192,193,194,175,238,160,114,63,152,112,80,57,224,223,133,195,174,111,137,196,197,113,198,164,190,107,154,37,58,199,108,101,128,117,88,115,243,232,91,163,45,79,169,181,245,125,131,100,246,240,144,141,247,241,132,20,142,242,244,140,143,126,184,185,21,307,186,85,147,110,118,124,56,78,130,34,150,153,104,8,103,136,7,92,210,102,99,106,33,129,182,157,29,188,122,119,36,12,134,120,187,189,4,16,212,146,96,32,31,86,145,127,121,211,35,22,23,203,11,201,89,53,178,5,15,263,90,87,139,84,239,105,176,248,249,109,264".split(
            ","
        )
        random_location = str(random.choice(locations))

        connect(random_location)
        time.sleep(2)
        return True
    except:
        return False


def connect_us_random():
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

        disconnect()
        time.sleep(1)
        locations = [
            "95",
            "271",
            "19",
            "283",
            "288",
            "270",
            "276",
            "265",
            "273",
            "17",
            "302",
            "299",
            "304",
            "292",
            "306",
            "9",
            "294",
            "18",
            "172",
            "278",
            "284",
            "293",
            "275",
            "165",
            "277",
            "286",
            "290",
            "161",
            "272",
            "6",
            "70",
            "74",
            "71",
            "280",
            "291",
            "54",
            "202",
            "305",
            "285",
            "301",
            "26",
            "155",
            "168",
            "281",
            "75",
            "295",
            "289",
            "297",
            "94",
            "282",
            "296",
            "298",
            "204",
            "1",
            "207",
            "2",
            "300",
            "287",
            "166",
            "303",
            "25",
            "279",
            "274",
        ]

        random_location = str(random.choice(locations))

        connect(random_location)
        time.sleep(3)
        return True
    except:
        return False


def initialize_new_profile_driver():
    try:
        with lock:
            # status, proxy = get_proxy()
            proxy = "NO PROXY USED"

            if SAVE_COOKIES:
                driver = Driver(
                    uc=True,
                    # browser="firefox",
                    # proxy=proxy,
                    binary_location=chrome_location,
                    extension_dir=extension_dir,
                    locale_code="en",
                )
            else:
                user_data_dir = "Cookies not saved. SAVE_COOKIES option turned off."
                driver = Driver(
                    uc=True,
                    # browser="firefox",
                    # proxy=proxy,
                    binary_location=chrome_location,
                    # user_data_dir=user_data_dir,
                    extension_dir=extension_dir,
                    locale_code="en",
                )

            return (
                True,
                {"driver": driver, "user_path": user_data_dir, "proxy": proxy},
                None,
            )
    except Exception as E:
        try:
            rollback_proxy(proxy)
        except:
            pass
        return False, f"Driver_init_error: {E}", None


def is_captcha_page(driver):
    RECAPTCHA_IFRAME_ELEMENT = (By.CSS_SELECTOR, 'iframe[title="reCAPTCHA"]')

    try:
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located(RECAPTCHA_IFRAME_ELEMENT)
        )
        return True
    except:
        return False


def enter_email(driver, email_address):
    try:
        """
        Enters the email address in the email input box
        """
        wait_time = 60
        EMAIL_INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[type="email"]')

        email_input_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(EMAIL_INPUT_ELEMENT)
        )

        email_input_element.clear()
        email_input_element.send_keys(email_address)
        time.sleep(0.5)
        return True
    except:
        return False


def click_next_button(driver):
    """
    Clicks the next button
    """
    try:
        NEXT_BUTTON_ELEMENT = (By.CSS_SELECTOR, 'input[type="submit"]')

        next_button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(NEXT_BUTTON_ELEMENT)
        )

        next_button.click()
        return True
    except:
        return False


def click_next_button_rec_email(driver):
    """
    Clicks the next button
    """
    try:
        NEXT_BUTTON_ELEMENT = (By.CSS_SELECTOR, 'input[type="submit"]')

        next_button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(NEXT_BUTTON_ELEMENT)
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", next_button
        )

        next_button.click()
        return True, ""
    except:
        try:
            time.sleep(1)
            NEXT_BUTTON_ELEMENT = (By.CSS_SELECTOR, 'input[type="submit"]')

            next_button = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(NEXT_BUTTON_ELEMENT)
            )
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", next_button
            )

            next_button.click()
            return True, ""

        except Exception as E:
            return False, E


def click_password_next_button(driver):
    """
    Clicks the next button on gmail login
    """
    try:
        NEXT_BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[type="submit"]')

        next_button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(NEXT_BUTTON_ELEMENT)
        )

        next_button.click()
        return True
    except:
        return False


def click_share_dropdown_button(driver):
    """
    Clicks the dropdown button on share
    """
    try:
        NEXT_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            # 'div[id="microsoft365-coldstart-sharing-drawer"] span[role="button"]',
            'div[id$="sharing-drawer"] span[role="button"]',
        )

        next_button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(NEXT_BUTTON_ELEMENT)
        )

        # scroll to view
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", next_button
        )

        if next_button.get_attribute("aria-expanded") != "true":
            next_button.click()

        return True
    except:
        return False


def click_start_sharing_button(driver):
    """
    Clicks the start sharing button
    """
    try:
        print("Clicking start sharing button for all members")
        START_SHARING_BTN_ELEMENT = (
            By.CSS_SELECTOR,
            'button[aria-label="Start sharing Microsoft 365 Family"]',
        )

        GOT_IT_BTN = (By.CSS_SELECTOR, 'button[aria-label="Got it"]')
        try:
            total_start_sharing_buttons = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_all_elements_located(START_SHARING_BTN_ELEMENT)
            )
            # print(
            #     f"Found {len(total_start_sharing_buttons)} members that need start sharing"
            # )
        except:
            try:
                START_SHARING_BTN_ELEMENT = (
                    By.CSS_SELECTOR,
                    'button[aria-label="Start sharing Microsoft 365 Premium"]',
                )

                total_start_sharing_buttons = WebDriverWait(driver, wait_time).until(
                    EC.visibility_of_all_elements_located(START_SHARING_BTN_ELEMENT)
                )

            except:
                print("No members found that need start sharing")
                return True

        for i in range(len(total_start_sharing_buttons)):
            try:
                # print(
                #     f"Processing member {i + 1} of {len(total_start_sharing_buttons)}"
                # )
                start_sharing_buttons = WebDriverWait(driver, wait_time * 2).until(
                    EC.visibility_of_all_elements_located(START_SHARING_BTN_ELEMENT)
                )
                time.sleep(1)
                element = start_sharing_buttons[0]
                # scroll to view
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", element
                )

                time.sleep(1.5)

                element.click()
                time.sleep(1)
                got_it_button = WebDriverWait(driver, wait_time * 2).until(
                    EC.element_to_be_clickable(GOT_IT_BTN)
                )
                time.sleep(2)
                got_it_button.click()
                time.sleep(3)

                # print(
                #     f"Processed  member {i + 1} of {len(total_start_sharing_buttons)}"
                # )
            except:
                # print(
                #     f"Error processing member {i + 1} of {len(total_start_sharing_buttons)}. Skipping."
                # )
                pass

        return True
    except:
        return False


def is_your_account_has_been_locked_page(driver):
    """
    Checks if the page is YOUR ACCOUNT HAS BEEN LOCKED
    """
    try:
        TITLE_ELEMENT = (By.CSS_SELECTOR, 'div[role="heading"]')

        title_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(TITLE_ELEMENT)
        )
        if "your account has been locked" in title_element.text.lower():
            return True
        else:
            return False
    except:
        return False


def funcaptcha_present(driver):
    """
    Checks if captcha is present
    """
    try:
        TITLE_ELEMENT = (By.CSS_SELECTOR, 'div[role="heading"]')

        title_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(TITLE_ELEMENT)
        )
        time.sleep(6)
        title_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(TITLE_ELEMENT)
        )
        if "help us beat the robots" in title_element.text.lower():
            return True
        else:
            return False
    except:
        return False


def wait_funcaptcha_bypass(driver):
    """
    Checks if the page is captcha page and waits till bypass
    """
    try:
        TITLE_ELEMENT = (By.CSS_SELECTOR, 'div[role="heading"]')
        retries = 0

        while retries < (round(CATCHA_WAIT_TIME / 5)):
            try:
                title_element = WebDriverWait(driver, wait_time).until(
                    EC.visibility_of_element_located(TITLE_ELEMENT)
                )
                time.sleep(2)
                if "help us beat the robots" in title_element.text.lower():
                    time.sleep(3)
                else:
                    return True
            except:
                return True
            retries += 1
        return False
    except:
        return False


def click_next_button_locked_page(driver):
    """
    Clicks the next button on your account has been locked page
    """
    try:
        NEXT_BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[id="StartAction"]')

        next_button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(NEXT_BUTTON_ELEMENT)
        )

        next_button.click()
        return True
    except:
        return False


def enter_phone_number_and_click_next_microsoft(driver, phone_number):
    """
    Enters phone number and clicks next
    """
    try:
        # COUNTRY_SELECT_ELEMENT = (
        #     By.CSS_SELECTOR,
        #     'select[id="DisplayPhoneCountryISO"]',
        # )
        COUNTRY_SELECT_ELEMENT = (By.CSS_SELECTOR, 'select[id="phoneCountry"]')

        country_select_element = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located(COUNTRY_SELECT_ELEMENT)
        )

        # data = []
        # for option in Select(country_select_element).options:
        #     value = option.get_attribute("value")
        #     text = option.text

        #     data.append((text, value))
        #     print(value, text)

        # df = pd.DataFrame(data, columns=["country", "code"])
        # df.country = df.country.str.lower()
        # df.country = df.country.replace(r"\s*\([^)]*\)", "", regex=True)
        # df.to_csv('utils/microsoft_country_codes.csv', index=False)

        df = pd.read_csv("utils/microsoft_country_codes.csv")
        df.set_index("country", inplace=True)

        country_value_dict = df.to_dict()["code"]
        # df.to_dict(orient='records')

        # country_value_dict = {
        #     "columbia": "CO",
        #     "indonesia": "ID",
        #     "spain": "ES",
        #     "portugal": "PT",
        #     "slovenia": "SI",
        #     "netherlands": "NL",
        #     "chile": "CL",
        # }
        c_val = country_value_dict.get(PREFERRED_SMS_COUNTRY.lower())
        # country_value_dict.get('senegal')
        Select(country_select_element).select_by_value(c_val)

        time.sleep(0.5)
        PHONE_NUMBER_ELEMENT = (By.CSS_SELECTOR, 'input[placeholder="Phone number"]')

        phone_number_element = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located(PHONE_NUMBER_ELEMENT)
        )

        # time.sleep(0.5)
        # phone_number_element.send_keys(Keys.BACKSPACE * 20)
        time.sleep(1)
        for i in str(phone_number):
            phone_number_element.send_keys(i)
            time.sleep(random.random())

        time.sleep(1)

        NEXT_BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[type="submit"]')

        next_element = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located(NEXT_BUTTON_ELEMENT)
        )

        next_element.click()

        return True
    except:
        return False


def bypassed_funcaptcha_to_code_page(driver):
    """
    CHECKS IF ITS THE CODE INPUT PAGE
    """
    try:
        CODE_INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[placeholder="Enter code"]')

        input_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(CODE_INPUT_ELEMENT)
        )
        return True
    except:
        return False


def enter_sent_code(driver, code):
    """
    Clicks the next button on your account has been locked page
    """
    try:
        CODE_INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[placeholder="Enter code"]')

        input_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(CODE_INPUT_ELEMENT)
        )

        input_element.clear()
        input_element.send_keys(str(code))
        time.sleep(0.5)
        NEXT_BTN_ELEMENT = (By.CSS_SELECTOR, 'button[id="nextButton"]')

        next_btn_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(NEXT_BTN_ELEMENT)
        )
        next_btn_element.click()
        return True
    except:
        return False


def click_next_if_acc_unblocked(driver):
    """
    Clicks the next button if otp-verification is successfull
    """
    try:
        HEADER_ELEMENT = (By.CSS_SELECTOR, 'div[role="heading"]')

        header_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(HEADER_ELEMENT)
        )
        time.sleep(3)
        header_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(HEADER_ELEMENT)
        )

        if header_element.text.lower().startswith("your account has been unblocked"):
            NEXT_BTN_ELEMENT = (By.CSS_SELECTOR, 'button[id="FinishAction"]')

            next_btn_element = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(NEXT_BTN_ELEMENT)
            )
            next_btn_element.click()
            return True
        else:
            return False
    except:
        return False


def is_try_another_verification_method(driver):
    """
    Clicks the next button on your account has been locked page
    """
    try:
        HEADER_ELEMENT = (By.CSS_SELECTOR, 'div[role="heading"]')

        header_element = WebDriverWait(driver, 3).until(
            EC.visibility_of_element_located(HEADER_ELEMENT)
        )

        if header_element.text.lower().startswith("try another verification method"):
            return True
        else:
            return False

    except:
        return False


def click_back_to_phone_number_button(driver):
    """
    Clicks the back button after not receiving verification code
    """
    try:
        BACK_BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[aria-label="Back"]')

        back_button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(BACK_BUTTON_ELEMENT)
        )

        back_button.click()
        return True
    except:
        return False


def is_protect_your_account_page(driver):
    """
    Checks if the page is protect your account
    """
    try:
        TITLE_ELEMENT = (By.CSS_SELECTOR, 'div[id="iPageTitle"]')

        title_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(TITLE_ELEMENT)
        )
        if "protect your account" in title_element.text.lower():
            return True
        else:
            return False
    except:
        return False


def lets_protect_your_account_banner_page(driver):
    """
    Checks if the page is protect your account without any actions, and clicks next
    """
    try:
        TITLE_ELEMENT = (By.CSS_SELECTOR, 'div[id="iPageTitle"]')

        title_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(TITLE_ELEMENT)
        )
        if "protect your account" in title_element.text.lower():
            PARAGRAPH_ELEMENT = (By.CSS_SELECTOR, 'p[id="idPwdSectioDescrp"]')

            p_element = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(PARAGRAPH_ELEMENT)
            )

            if "add another way to verify it's you" in p_element.text.lower():
                click_next_button(driver)

            return True
        else:
            return False
    except:
        return False


def invalid_code(driver):
    """
    Checks if the code entered output an error
    """
    try:
        ERROR_ELEMENT = (By.CSS_SELECTOR, 'div[class="alert alert-error ErrMsg"]')

        error_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(ERROR_ELEMENT)
        )
        if "code didn't work" in error_element.text.lower():
            return True
        else:
            return False
    except:
        return False


def select_alternate_email_option(driver):
    """
    Selects 'An alternate email address' option
    """
    try:
        PROTECTION_OPTIONS_ELEMENT = (By.CSS_SELECTOR, 'select[id="iProofOptions"]')

        options_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(PROTECTION_OPTIONS_ELEMENT)
        )

        Select(options_element).select_by_value("Email")
        return True
    except:
        return False


def accept_tempmail_consent(driver):
    try:
        CONSENT_BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[aria-label="Consent"]')

        consent_element = WebDriverWait(driver, 3).until(
            EC.visibility_of_element_located(CONSENT_BUTTON_ELEMENT)
        )

        consent_element.click()
    except:
        pass


def open_new_tempmail_tab(driver):
    try:
        driver.switch_to.new_window("tab")
        # driver.window_handles
        driver.get(TEMPMAIL_URL)

        accept_tempmail_consent(driver)
        return True
    except:
        return False


def fetch_email_from_tempmail_tab(driver):
    try:
        retries = 0
        EMAIL_ELEMENT = (By.CSS_SELECTOR, 'input[id="email"]')
        accept_tempmail_consent(driver)
        while retries < round(EMAIL_WAIT_TIME / 3):
            email_element = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(EMAIL_ELEMENT)
            )

            email_address = email_element.get_attribute("value")

            if email_address != "":
                return True, email_address

            time.sleep(3)

        return False, "Tempmail-error"

    except:
        return False, False


def get_email_from_tempmail(driver):
    try:
        open_new_tempmail_tab(driver=driver)
        status, email_address = fetch_email_from_tempmail_tab(driver=driver)

        if status:
            return True, email_address
        else:
            return False, f"EE:{email_address}"
    except:
        return False, False
    finally:
        try:
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass


def get_email_code(driver):
    """
    Retrieves code sent to temp-mail next tab
    """
    try:
        driver.switch_to.window(driver.window_handles[1])

        EMAIL_ELEMENT = (
            By.CSS_SELECTOR,
            'ul[class="email-list grow overflow-x-hidden absolute w-full min-h-full"] > li',
        )

        REFRESH_BTN_ELEMENT = (
            By.CSS_SELECTOR,
            'button[data-qa="refresh-button"]',
        )

        retries = 0
        accept_tempmail_consent(driver)
        while retries < round(EMAIL_WAIT_TIME / 3):
            try:
                email_elements = WebDriverWait(driver, 1).until(
                    EC.visibility_of_all_elements_located(EMAIL_ELEMENT)
                )

                code = [
                    re.search(r"Security code:\s*(\d{6})", i.text).group(1)
                    for i in email_elements
                    if "microsoft account team" in i.text.lower()
                ]
                if code:
                    return True, code[0]
            except:
                pass
            time.sleep(3)
            try:
                # click_refresh
                refresh_btn = WebDriverWait(driver, 1).until(
                    EC.presence_of_element_located(REFRESH_BTN_ELEMENT)
                )
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", refresh_btn
                )

                refresh_btn.click()
            except:
                pass

            retries += 1

        return False, False

    except:
        return False, False
    finally:
        try:
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass


def enter_code(driver, code):
    try:
        """
        Enters the email address in the email input box
        """
        wait_time = 30
        INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[placeholder="Code"]')

        input_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(INPUT_ELEMENT)
        )

        input_element.clear()
        input_element.send_keys(code)
        time.sleep(0.5)
        return True
    except:
        return False


def enter_code_and_click_next_after_pass_change(driver, code):
    try:
        """
        Enters the code
        """
        INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[id="codeEntry-0"]')

        input_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(INPUT_ELEMENT)
        )

        input_element.clear()
        input_element.send_keys(code)
        time.sleep(0.5)
        return True
    except:
        return False


def wait_till_captcha_bypass(driver):
    try:
        retries = 0
        while is_captcha_page(driver) and retries < 40:
            # print("Captcha present, waiting for solution")
            time.sleep(3)
            retries += 1
        if is_captcha_page(driver):
            return False
        else:
            return True
    except:
        return False


def click_stay_signed_in_button(driver):
    """
    Clicks the stay signed in button after login
    """
    try:
        BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[data-testid="primaryButton"]')

        button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(BUTTON_ELEMENT)
        )

        button.click()
        return True
    except:
        return False


def cancel_setup_passkey(driver):
    """
    Cancels passkey setup if poppup pops up
    """
    try:
        retries = 0
        while retries < 5:
            try:
                TITLE_ELEMENT = (By.CSS_SELECTOR, 'div[id="title"]')
                CANCEL_BTN_ELEMENT = (By.CSS_SELECTOR, 'input[value="Cancel"]')

                title_element = WebDriverWait(driver, 0.1).until(
                    EC.visibility_of_element_located(TITLE_ELEMENT)
                )
                if "setting up your passkey" in title_element.text.lower():
                    cancel_btn_element = WebDriverWait(driver, 0.2).until(
                        EC.visibility_of_element_located(CANCEL_BTN_ELEMENT)
                    )

                    try:
                        WebDriverWait(driver, wait_time / 2).until(
                            EC.alert_is_present()
                        )
                        print("Cancelled alert")
                        # cancel_btn_element.click()
                    except:
                        # cancel_btn_element.click()
                        pass
                    try:
                        cancel_btn_element.click()
                        print("Cancelled alert")

                    except:
                        pass

                    CANCEL_BTN_ELEMENT = (
                        By.CSS_SELECTOR,
                        'button[data-testid="secondaryButton"]',
                    )
                    time.sleep(3)
                    cancel_btn_element = WebDriverWait(driver, 0.2).until(
                        EC.visibility_of_element_located(CANCEL_BTN_ELEMENT)
                    )
                    cancel_btn_element.click()

                    return True
            except:
                pass
            retries += 1
            time.sleep(1)

        return False
    except:
        return False


def click_next_if_a_quick_note_page(driver):
    """
    Clicks the stay signed in button after login
    """
    try:
        HEADER_ELEMENT = (By.CSS_SELECTOR, 'span[role="heading"]')

        header_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(HEADER_ELEMENT)
        )
        time.sleep(3)
        header_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(HEADER_ELEMENT)
        )

        if header_element.text.lower().startswith(
            "a quick note about your microsoft account"
        ):
            BUTTON_ELEMENT = (By.CSS_SELECTOR, 'div[id="StickyFooter"]>button')

            button = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(BUTTON_ELEMENT)
            )

            button.click()

            time.sleep(1)
            button = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(BUTTON_ELEMENT)
            )

            button.click()

            return True
        else:
            return False
    except:
        return False


def close_poppup_after_login(driver):
    """
    Clossed popups after login
    """
    try:
        BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[aria-label="Close"]')

        button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(BUTTON_ELEMENT)
        )

        button.click()
        return True
    except:
        return False


def successfull_login_page(driver):
    try:
        ELEMENT = (By.CSS_SELECTOR, 'div[id="meInitialsButton"]')

        element = WebDriverWait(driver, 60).until(
            EC.visibility_of_element_located(ELEMENT)
        )

        return True

    except:
        return False


def sync_family_links_to_json():
    # Read links from txt
    txt_path = "input_data/family_link.txt"
    json_path = "utils/family_links.json"
    with open(txt_path, "r", encoding="utf-8") as f:
        links = {line.strip() for line in f if line.strip()}

    # Load existing JSON or initialize
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

            data = {i[0]: i[1] for i in data.items() if i[0] in links}

    else:
        data = {}

    # Add only new links
    for link in links:
        if link not in data:
            data[link] = 0

    # Save back to JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return data


def get_family_link(driver):
    with lock:
        try:
            with open(r"input_data\family_link.txt", "r", encoding="utf-8") as f:
                data = [i for i in f.read().split("\n") if i.strip()]

            if not data:
                return False, "NO_LINK"

            link = data[0]

            try:
                stats = {}
                with open("output_data/link_stats.txt", "r") as f:
                    for line in f:
                        if ":" in line:
                            lnk, count = line.strip().rsplit(":", 1)
                            stats[lnk] = int(count)

                if stats.get(link, 0) >= 5:
                    successfully_worked_links(link)
                    if len(data) > 1:
                        link = data[1]
                    else:
                        return False, "NO_LINK"
            except:
                pass

            return True, link
        except:
            return False, ""


def update_link_usage_times(link):
    stats = {}
    file_path = "output_data/link_stats.txt"

    # Read existing data
    try:
        with open(file_path, "r") as f:
            for line in f:
                if ":" in line:
                    lnk, count = line.strip().rsplit(":", 1)
                    stats[lnk] = int(count)
    except FileNotFoundError:
        pass  # file will be created if it doesn't exist

    # Update count
    if link in stats:
        stats[link] += 1
    else:
        stats[link] = 1

    # Write back
    with open(file_path, "w") as f:
        for lnk, count in stats.items():
            f.write(f"{lnk}:{count}\n")


def not_working_links(link):
    try:
        with open("input_data/expired_family_links.txt", "a", encoding="utf-8") as file:
            file.write(link + "\n")
        with open("input_data/family_link.txt", "r", encoding="utf-8") as file:
            lines = file.readlines()

        cleaned_lines = [line for line in lines if line.strip() != link.strip()]

        with open("input_data/family_link.txt", "w", encoding="utf-8") as file:
            file.writelines(cleaned_lines)

    except:
        pass


def successfully_worked_links(link):
    try:
        with open(
            "input_data/used_5_times_family_links.txt", "a", encoding="utf-8"
        ) as file:
            file.write(link + "\n")
        with open("input_data/family_link.txt", "r", encoding="utf-8") as file:
            lines = file.readlines()

        cleaned_lines = [line for line in lines if line.strip() != link.strip()]

        with open("input_data/family_link.txt", "w", encoding="utf-8") as file:
            file.writelines(cleaned_lines)

    except:
        pass


def processed_email(email_data):
    def db_action():
        import mysql.connector

        conn = None
        try:
            conn = mysql.connector.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
            )
            cursor = conn.cursor()

            # Insert into processed_emails
            insert_query = """
            INSERT INTO processed_emails (server_ip, bot_type,date_time, email, pass)
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(
                insert_query,
                (
                    SERVER_IP,
                    BOT_TYPE,
                    datetime.now(),
                    email_data.get("email"),
                    email_data.get("pass"),
                ),
            )

            # Delete from processing_emails
            delete_query = """
            DELETE FROM processing_emails
            WHERE server_ip = %s AND bot_type = %s AND email = %s 
            """
            cursor.execute(
                delete_query,
                (SERVER_IP, BOT_TYPE, email_data.get("email")),
            )

            conn.commit()
            cursor.close()
        finally:
            if conn is not None:
                conn.close()

    try:
        execute_db_action(db_action)
    except Exception as e:
        print(f"Error in processed_email: {e}")
        pass


def mark_share_as_done(email_address):
    """Mark the given email's share record as processed."""

    def db_action():
        conn = None
        try:
            conn = mysql.connector.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
            )
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE familybot_extracted_family_links_history "
                "SET status = %s, processing_server_ip = %s, processing_date_time = %s "
                "WHERE email = %s ",
                ("processed", SERVER_IP, datetime.now(), email_address),
            )
            conn.commit()
            cursor.close()
            return cursor.rowcount
        finally:
            if conn is not None:
                conn.close()

    try:
        updated = execute_db_action(db_action)
        print(f"{email_address} : Updated database status as successfully processed.")

        return bool(updated)
    except Exception as e:
        print(f"{email_address} : Error updating share status in database: {e}")
        return False


def click_join_family_link_btn(driver):
    try:
        button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'button[aria-label="Join now"]')
            )
        )
        time.sleep(1)
        button.click()
        time.sleep(5)

        return True
    except:
        return False


def link_is_invalid(driver):
    try:
        INVALID_ELEMENT = (By.TAG_NAME, "h1")

        invalid = WebDriverWait(driver, 1).until(
            EC.visibility_of_element_located(INVALID_ELEMENT)
        )

        if invalid.text.lower() in [
            "try a different url",
            "looks like this invitation is invalid",
            "looks like this invitation link is not working",
        ]:
            return True

        return False
    except:
        return False


def sucessfully_joined_microsoft_premium(driver):
    try:
        CONGRATULATIONS_ELEMENT = (By.CSS_SELECTOR, "h1")

        label_element = WebDriverWait(driver, 1).until(
            EC.visibility_of_element_located(CONGRATULATIONS_ELEMENT)
        )

        if (
            label_element.text.lower().startswith("you’ve already joined")
            or label_element.text.lower().startswith("congratulations")
            or label_element.text.lower().startswith(
                "looks like you already have a subscription"
            )
            or label_element.text.lower().startswith(
                "hmm... it looks like you're already in a family group"
            )
        ):
            # time.sleep(1)
            return True

        elif label_element.text.lower().startswith(
            "looks like there aren’t any subscriptions available"
        ):
            return False

        return False
    except:
        return False


def looks_like_there_arent_microsoft_premium(driver):
    try:
        CONGRATULATIONS_ELEMENT = (By.CSS_SELECTOR, "h1")

        label_element = WebDriverWait(driver, 1).until(
            EC.visibility_of_element_located(CONGRATULATIONS_ELEMENT)
        )

        if label_element.text.lower().startswith(
            "looks like there aren’t any subscriptions available"
        ):
            return True

        return False
    except:
        return False


def use_link_to_join_family_acc(driver):
    try:
        status, invite_url = get_family_link(driver)
        if status:
            print("Using family url to join.")
            driver.get(invite_url)
            check_btn_retries = 0
            proceed = False
            while (check_btn_retries < 15) and (not proceed):
                if click_join_family_link_btn(driver):
                    # update_link_usage_times(invite_url)
                    print("Clicked join now button. Waiting for success message")
                    proceed = True
                elif sucessfully_joined_microsoft_premium(driver):
                    print("Successfully joined Microsoft Premium.")
                    proceed = True
                elif link_is_invalid(driver):
                    print("Link is invalid.")
                    not_working_links(invite_url)
                    return False

                time.sleep(1)
                check_btn_retries += 1

            if not proceed:
                print(
                    "Loading timeout. Join now button not present. Link is invalid label not present"
                )
                # not_working_links(invite_url)
                return False

            success_message_retries = 0
            while success_message_retries < 10:
                if sucessfully_joined_microsoft_premium(driver):
                    update_link_usage_times(invite_url)
                    print("Successfully joined premium using family link")
                    return True
                elif looks_like_there_arent_microsoft_premium(driver):
                    print(
                        "'Looks like there aren’t any subscriptions available' displayed. "
                    )
                    not_working_links(invite_url)

                    return False

                elif link_is_invalid(driver):
                    print("Link is invalid.")
                    not_working_links(invite_url)
                    return False

                success_message_retries += 1
                time.sleep(1.5)

            print("Waited for congratulations message and timed out after a minute")
            return False
        else:
            if invite_url == "NO_LINK":
                print("NO family urls.")
                try:
                    driver.quit()
                except:
                    pass
                os._exit(1)
                return False
            else:
                print("Unable to get family url.")
                return False

    except Exception as E:
        print(f"Exception: {E}")
        return False


def join_family_acc(driver):
    retries = 0
    while retries < 5:
        if use_link_to_join_family_acc(driver):
            return True

        retries += 1
        # connect_us_random()
        time.sleep(1)
    return False


def click_existing_account_on_login(driver):
    """
    Selects currently logged in account
    """
    try:
        BUTTON_ELEMENT = (By.CSS_SELECTOR, 'div[id="newSessionLink"]')

        button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(BUTTON_ELEMENT)
        )

        button.click()
        return True
    except:
        return False


def close_outlook_poppup(driver):
    """
    closes popup
    """

    try:
        BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[class="fui-Button r1alrhcs"]')

        button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(BUTTON_ELEMENT)
        )

        button.click()
    except:
        pass


def go_to_outlook(driver):
    """
    goes to outlook using url
    """
    try:
        driver.get(OUTLOOK_URL)
        click_inbox_button(driver)
        return True
    except:
        return False


def get_bitly_code_from_email(driver):
    """
    Gets the code from email
    """
    try:
        click_inbox_button(driver)
        retries = 0
        EMAIL_ELEMENTS = (By.CSS_SELECTOR, 'div[role="option"]')

        while retries < round(EMAIL_WAIT_TIME / 3):
            try:
                email_elements = WebDriverWait(driver, 1).until(
                    EC.presence_of_all_elements_located(EMAIL_ELEMENTS)
                )

                email_text_content = [
                    email_element.get_attribute("aria-label")
                    for email_element in email_elements
                ]

                valid_code = [
                    re.search(r" code:\s*(\d{6})", each_item).group(1)
                    for each_item in email_text_content
                    if "bitly" in each_item.lower()
                ]

                if valid_code:
                    # print(f"Bitly code: {valid_code[0]}")
                    return True, valid_code[0]

                # if retries % 10 == 0:
                #     go_to_outlook(driver)
                #     time.sleep(1)

                # if retries % 2 == 0:
                #     click_outlook_inbox_other(driver)
                # else:
                #     # click_inbox_button(driver)
                #     click_focused_button(driver)
            except:
                pass

            try:
                if retries % 2 == 0:
                    click_outlook_inbox_other(driver)
                else:
                    click_focused_button(driver)

                if retries % 10 == 0:
                    go_to_outlook(driver)
                    time.sleep(1)
            except:
                pass
            time.sleep(3)
            retries += 1

        return False, False
    except:
        return False, False


def enter_bitly_code(driver, code):
    try:
        """
        Enters the verification code sent to email to bitly
        """
        # wait_time = 30
        INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[aria-required="true"]')

        input_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(INPUT_ELEMENT)
        )

        input_element.clear()
        input_element.send_keys(code)
        time.sleep(0.5)
        return True
    except:
        return False


def bitly_click_verify_button(driver):
    try:
        CREATE_BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[type="submit"]')

        create_button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(CREATE_BUTTON_ELEMENT)
        )

        create_button.click()
        return True
    except:
        return False


def click_outlook_inbox_other(driver):
    try:
        click_inbox_button(driver)
        BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[name="Other"]')

        button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(BUTTON_ELEMENT)
        )

        button.click()
        return True
    except:
        return False


def bitly_remind_me_later_button(driver):
    try:
        BUTTON_ELEMENT = (By.CSS_SELECTOR, 'div[class="remind-me-later"] > button')

        button = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(BUTTON_ELEMENT)
        )

        button.click()
        return True
    except:
        return False


def create_a_link_using_bitly(driver, link):
    """
    Creates a short link using bitly
    """
    try:
        create_link_page = "https://app.bitly.com"
        driver.get(create_link_page)

        URL_INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[id="destination-url"]')
        SHORTENED_URL = (By.CSS_SELECTOR, 'a[rel="noreferrer"]')
        CREATE_NEW_BUTTON_LINK = (
            By.CSS_SELECTOR,
            'button[class="orb-button default create-btn"]',
        )
        CREATE_BITLY_LINK = (
            By.CSS_SELECTOR,
            'div[class="quick-create-buttons"] > button',
        )
        create_btn = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(CREATE_NEW_BUTTON_LINK)
        )
        create_btn.click()
        time.sleep(1)

        new_link_btn = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(CREATE_BITLY_LINK)
        )

        new_link_btn.click()

        time.sleep(1)

        input_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(URL_INPUT_ELEMENT)
        )

        input_element.clear()
        input_element.send_keys(link)
        bitly_click_verify_button(driver)

        url_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(SHORTENED_URL)
        )

        shortened_url = url_element.get_attribute("href")
        return True, shortened_url

    except:
        return False, False


def sign_up_to_bitly_and_verify_otp(driver, email_address, password):
    """
    Signs in to bitly
    """
    try:
        # open 2 tabs, tab one for outlook, tab two for bitly
        driver.switch_to.window(driver.window_handles[0])
        go_to_outlook(driver)
        close_outlook_poppup(driver)

        driver.switch_to.new_window("tab")
        driver.switch_to.window(driver.window_handles[1])
        go_to_bitly(driver)

        signup_status = sign_up_to_bitly(driver, email_address, password)

        driver.switch_to.window(driver.window_handles[0])

        if signup_status:
            status, code = get_bitly_code_from_email(driver)

            if status:
                driver.switch_to.window(driver.window_handles[1])
                enter_bitly_code(driver, str(code))
                time.sleep(0.5)
                bitly_click_verify_button(driver)
                time.sleep(0.5)
                bitly_remind_me_later_button(driver)

                return True

        return False
    except:
        return False


def login_to_bitly(driver, bitly_email, bitly_password):
    try:
        bitly_login_url = "https://bitly.com/a/sign_in"
        driver.get(bitly_login_url)

        # Enter Email
        try:
            INPUT_ELEMENT = (By.CSS_SELECTOR, 'label[class="css-dqxkk4"] > input')

            email_input = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(INPUT_ELEMENT)
            )

            email_input.send_keys(bitly_email)
        except:
            pass

        # Enter password
        try:
            time.sleep(1)
            INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[type="password"]')

            password_input = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(INPUT_ELEMENT)
            )

            password_input.send_keys(bitly_password)
        except:
            pass

        # Click create free account
        try:
            time.sleep(1)
            CREATE_BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[type="submit"]')

            create_button = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(CREATE_BUTTON_ELEMENT)
            )

            create_button.click()
        except:
            pass
        return True
    except:
        return False


def sign_up_bitly_2(driver, email_address, password):
    try:
        password = password + "A1!"  # To meet bitly's password rules

        print(f"{email_address}: Signing up to bitly...")
        signup_status = sign_up_to_bitly_and_verify_otp(driver, email_address, password)
        if signup_status:
            print(f"{email_address}: Successfully signed up to bitly")
            update_accounts_data(
                email=email_address,
                has_bitly_account="YES",
                bitly_acc_password=password,
            )
            return True
        else:
            update_accounts_data(
                email=email_address,
                has_bitly_account="NO",
                bitly_acc_password="",
            )
            return False
    except:
        return False


def enter_password(driver, password, wait_time=wait_time):
    try:
        PASSWORD_INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[type="password"]')

        time.sleep(0.5)
        password_input_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(PASSWORD_INPUT_ELEMENT)
        )
        password_input_element.clear()
        password_input_element.send_keys(password)

        return True
    except:
        return False


def wrong_password_error_displayed(driver):
    """
    Checks if wrong password label appears.
    """
    try:
        WRONG_PASSWORD_INPUT_ELEMENT = (By.CSS_SELECTOR, 'div[jsname="B34EJ"]')

        incorrect_password_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(WRONG_PASSWORD_INPUT_ELEMENT)
        )

        if incorrect_password_element.text.lower().startswith("wrong"):
            return True
        else:
            return False
    except:
        return False


def invalid_phone_number(driver):
    """
    Checks if 'This phone number can't be used for verification' label appears.
    """
    try:
        WRONG_PASSWORD_INPUT_ELEMENT = (By.CSS_SELECTOR, 'div[jsname="B34EJ"]')

        incorrect_password_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(WRONG_PASSWORD_INPUT_ELEMENT)
        )

        return True
    except:
        return False


def signin_error(driver):
    try:
        COULDNT_SIGN_IN_ELEMENT = (By.CSS_SELECTOR, 'h1[id="headingText"]')
        element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(COULDNT_SIGN_IN_ELEMENT)
        )

        if element.text.lower().startswith("couldn’t sign you in"):
            return True

    except:
        return False


def click_confirm_recovery_email_button(driver):
    """
    Clicks confirm recovery email button
    """
    try:
        try:
            CONFIRM_RECOVERY_EMAIL_BTN_ELEMENT = (
                By.CSS_SELECTOR,
                'div[data-challengetype="12"][data-challengeid="6"]',
            )
            confirm_recovery_email_input_element = WebDriverWait(
                driver, wait_time
            ).until(
                EC.visibility_of_element_located(CONFIRM_RECOVERY_EMAIL_BTN_ELEMENT)
            )

            confirm_recovery_email_input_element.click()
            return True
        except:
            CONFIRM_RECOVERY_EMAIL_BTN_ELEMENT = (
                By.CSS_SELECTOR,
                'div[data-challengetype="12"]',
            )
            confirm_recovery_email_input_element = WebDriverWait(
                driver, wait_time
            ).until(
                EC.visibility_of_element_located(CONFIRM_RECOVERY_EMAIL_BTN_ELEMENT)
            )

            confirm_recovery_email_input_element.click()
            return True
    except:
        return False


def existing_number_to_confirm_code(driver):
    """
    Checks if there is an existing number to receive code
    """
    try:
        ELEMENT = (
            By.CSS_SELECTOR,
            'div[class="dMNVAe"]',
        )
        element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(ELEMENT)
        )

        if "confirm the phone number you added to your account" in element.text.lower():
            return True

        else:
            return False

    except:
        return False


def click_try_another_way_button(driver):
    """
    Clicks try another way button
    """
    try:
        TRY_ANOTHER_WAY = (
            By.CSS_SELECTOR,
            'button[jsname="LgbsSe"]',
        )
        elements = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_all_elements_located(TRY_ANOTHER_WAY)
        )

        element = elements[
            [
                True if i.text.lower().startswith("try another way") else False
                for i in elements
            ].index(True)
        ]
        element.click()
        return True
    except:
        return False


def click_cancel_button(driver):
    """
    Clicks cancel button
    """
    try:
        CANCEL = (
            By.CSS_SELECTOR,
            'button[aria-label="Cancel"]',
        )
        element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(CANCEL)
        )
        element.click()
        return True
    except:
        return False


def click_skip_button(driver):
    """
    Clicks cancel button
    """
    try:
        SKIP = (
            By.CSS_SELECTOR,
            'button[aria-label="Skip"]',
        )
        element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(SKIP)
        )
        element.click()
        return True
    except:
        return False


def enter_recovery_email(driver, recovery_email):
    try:
        EMAIL_INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[type="email"]')

        recovery_email_input_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(EMAIL_INPUT_ELEMENT)
        )

        recovery_email_input_element.clear()
        recovery_email_input_element.send_keys(recovery_email)
        return True
    except:
        return False


def enter_recovery_email_2(driver, recovery_email):
    try:
        EMAIL_INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[type="text"]')

        recovery_email_input_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(EMAIL_INPUT_ELEMENT)
        )

        recovery_email_input_element.clear()
        recovery_email_input_element.send_keys(recovery_email)
        return True
    except:
        return False


def enter_phone_number(driver, phone_number):
    try:
        PHONE_NUMBER_INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[type="tel"]')

        phone_number_input = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located(PHONE_NUMBER_INPUT_ELEMENT)
        )

        phone_number_input.clear()
        phone_number_input.send_keys("+" + phone_number)
        return True
    except:
        return False


def phone_number_error(driver):
    try:
        PHONE_NUMBER_ERROR_ELEMENT = (By.CSS_SELECTOR, 'div[jsname="B34EJ"]')

        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located(PHONE_NUMBER_ERROR_ELEMENT)
        )
        return True

    except:
        return False


def click_next_if_is_updating_terms_page(driver):
    try:
        TITLE_ELEMENT = (By.CSS_SELECTOR, 'h1[data-testid="title"]')

        title = WebDriverWait(driver, wait_time / 3).until(
            EC.presence_of_element_located(TITLE_ELEMENT)
        )
        time.sleep(3)
        title = WebDriverWait(driver, 2).until(
            EC.presence_of_element_located(TITLE_ELEMENT)
        )
        if title.text.lower().startswith("we're updating our terms"):
            try:
                NEXT_BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[type="submit"]')

                next_button = WebDriverWait(driver, 2).until(
                    EC.visibility_of_element_located(NEXT_BUTTON_ELEMENT)
                )

                next_button.click()
                return True
            except:
                return False

        return True

    except:
        return False


def enter_verification_code(driver, code):
    try:
        VERIFICATION_CODE_INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[type="tel"]')
        verification_code = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(VERIFICATION_CODE_INPUT_ELEMENT)
        )

        verification_code.clear()
        verification_code.send_keys(code)
        return True
    except:
        return False


def profile_picture_element(driver):
    """
    Checks if login is successfull and profile is displayed
    """
    try:
        ELEMENT = (By.CSS_SELECTOR, 'button[aria-label="change profile picture"]')
        element = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located(ELEMENT)
        )

        return True
    except:
        return False


def add_new_number(
    activation_id,
    phone_number,
    used,
    activationCost,
    accounts_used_on,
    activationTime,
    activation_end_time,
):
    try:
        try:
            df = pd.read_json("utils/numbers.json")
        except:
            df = pd.DataFrame(
                columns=[
                    "activation_id",
                    "phone_number",
                    "used",
                    "activationCost",
                    "accounts_used_on",
                    "activationTime",
                    "activation_end_time",
                ]
            )

        df.loc[len(df)] = [
            activation_id,
            phone_number,
            used,
            activationCost,
            accounts_used_on,
            activationTime,
            activation_end_time,
        ]
        df.astype({"activation_id": int, "phone_number": int})

        df.to_json("utils/numbers.json", orient="records")

        return True
    except:
        return False


def update_number_details(activation_id, phone_number, account_used_on):
    """
    Updates the phone status(phone number used by which email) in the numbers json file
    """
    try:
        df = pd.read_json("utils/numbers.json")

        df.astype({"activation_id": int, "phone_number": int})
        num_index = df[
            (df["activation_id"] == int(activation_id))
            & (df["phone_number"] == int(phone_number))
        ].index[0]
        # df.loc[num_index, 'used'] = df.loc[num_index, 'used']+1
        current_acc_used_on = df.loc[num_index, "accounts_used_on"]
        if current_acc_used_on:
            df.loc[num_index, "accounts_used_on"] = (
                f"{current_acc_used_on},{account_used_on}"
            )
        else:
            df.loc[num_index, "accounts_used_on"] = account_used_on

        df.to_json("utils/numbers.json", orient="records")

        return True
    except:
        return False


def get_phone_number_from_api():
    """
    Gets a new phone number from API
    """

    try:
        country_id_dict = {
            "indonesia": 6,
            "columbia": 33,
            "portugal": 117,
            "slovenia": 59,
            "spain": 56,
            "netherlands": 48,
            "chile": 151,
        }
        country_id = country_id_dict.get("netherlands")

        try:
            resp2 = requests.get(
                "https://hero-sms.com/stubs/handler_api.php?action=getCountries",
                params={"api_key": HERO_SMS_API_KEY},
            )
            dta = resp2.json()

            df2 = pd.DataFrame(dta)
            country_id = str(
                df2[
                    df2.eng.apply(lambda x: x.lower().startswith(PREFERRED_SMS_COUNTRY))
                ].id.iloc[0]
            )
        except:
            print(
                f"{PREFERRED_SMS_COUNTRY} number NOT AVAILABLE in herosms. Defaulting to Netherlands"
            )

        service_code = "mm"

        response = requests.get(
            "https://hero-sms.com/stubs/handler_api.php?action=getNumberV2",
            params={
                "service": service_code,
                "country": country_id,
                "api_key": HERO_SMS_API_KEY,
            },
        )
        response.content

        # get_balance()
        phone_data = response.json()

        # response.text

        activation_id = phone_data.get("activationId")
        # phone_number = phone_data.get("phoneNumber")
        phone_number = str(phone_data.get("phoneNumber")).removeprefix(
            str(phone_data.get("countryPhoneCode"))
        )

        activationCost = phone_data.get("activationCost")
        used = 1
        accounts_used_on = ""
        activationTime = pd.to_datetime(phone_data.get("activationTime"))
        activation_end_time = pd.to_datetime(phone_data.get("activationEndTime"))

        return (
            True,
            activation_id,
            phone_number,
            activationCost,
            used,
            accounts_used_on,
            activationTime,
            activation_end_time,
        )
    except Exception as E:
        return False, f"Exception: {E}", False, False, False, False, False, False


def get_valid_phone_number_from_file():
    """
    Checks if there is a number that's still valid and used less than 2 times from file
    """
    try:
        df = pd.read_json("utils/numbers.json")

        df.astype({"activation_id": int, "phone_number": int})
        # df['activationTime']=df['activationTime'].astype("datetime64[ms]")

        num_index = df[
            (df["used"] < 2)
            & (
                df["activationTime"].astype("datetime64[ms]") + timedelta(minutes=3)
                < (pd.Timestamp.now())
            )
            & (df["activation_end_time"] > (pd.Timestamp.now() + timedelta(minutes=2)))
        ].index[0]
        df.loc[num_index, "used"] = df.loc[num_index, "used"] + 1
        df.to_json("utils/numbers.json", orient="records")
        activation_id = df.loc[num_index, :].activation_id
        phone_number = df.loc[num_index, :].phone_number

        return True, activation_id, phone_number
    except:
        return False, False, False


def get_number_for_verification():
    """
    Checks if there is a valid phone number used less than 2 times from file.
    If no phone number from file, get a new one from API
    """
    try:
        (
            status2,
            activation_id,
            phone_number,
            activationCost,
            used,
            accounts_used_on,
            activationTime,
            activation_end_time,
        ) = get_phone_number_from_api()

        if status2:
            # add_new_number(
            #     activation_id,
            #     phone_number,
            #     used,
            #     activationCost,
            #     accounts_used_on,
            #     activationTime,
            #     activation_end_time,
            # )

            return True, activation_id, phone_number
        else:
            return False, activation_id, False

    except:
        return False, False, False


def get_code(activation_id):
    try:
        retries = 0
        while retries < 30:
            status, code = get_message(activation_id)
            if status:
                return True, code
            else:
                time.sleep(3)
                retries += 1
        return False, False
    except:
        return False, False


def cancel_number(activation_id):
    try:
        response = requests.get(
            "https://hero-sms.com/stubs/handler_api.php?action=setStatus",
            params={
                "id": str(activation_id),
                "status": "8",
                "api_key": HERO_SMS_API_KEY,
            },
        )

        response.content
        # response.json()
        return True
    except:
        return False


def get_status(activation_id):
    try:
        resp = requests.get(
            "https://hero-sms.com/stubs/handler_api.php?action=getStatus",
            params={"id": activation_id, "api_key": HERO_SMS_API_KEY},
        )

        resp.text
    except:
        pass


def set_readiness_for_message(activation_id):
    try:
        resp = requests.get(
            "https://hero-sms.com/stubs/handler_api.php?action=setStatus",
            params={
                "id": str(activation_id),
                "status": "1",
                "api_key": HERO_SMS_API_KEY,
            },
        )

        return True
    except:
        return False


def set_status_3_for_message(activation_id):
    try:
        resp = requests.get(
            "https://hero-sms.com/stubs/handler_api.php?action=setStatus",
            params={
                "id": str(activation_id),
                "status": "3",
                "api_key": HERO_SMS_API_KEY,
            },
        )

        resp.text

        return True
    except:
        return False


def set_status_6_for_message(activation_id):
    try:
        resp = requests.get(
            "https://hero-sms.com/stubs/handler_api.php?action=setStatus",
            params={
                "id": str(activation_id),
                "status": "6",
                "api_key": HERO_SMS_API_KEY,
            },
        )

        resp.text

        return True
    except:
        return False


def get_message(activation_id):
    try:
        response = requests.get(
            "https://hero-sms.com/stubs/handler_api.php?action=getStatusV2",
            params={"id": str(activation_id), "api_key": HERO_SMS_API_KEY},
        )

        data = response.json()
        data
        if data["sms"]:
            code = data["sms"]["code"]
            return True, code
        elif data["call"]:
            code = data["call"]["code"]
            return True, code
        else:
            return False, False

    except:
        return False, False


def get_balance():
    response = requests.get(
        "https://hero-sms.com/stubs/handler_api.php?action=getBalance",
        params={"api_key": HERO_SMS_API_KEY},
    )
    return response.content


def bring_to_front(driver):
    try:
        with lock:
            position = driver.get_window_position()
            driver.minimize_window()
            driver.set_window_position(position["x"], position["y"])
            driver.maximize_window()
            time.sleep(1)
    except:
        pass


def new_profile_logger_old(email, status, error):
    with lock:
        try:
            try:
                df = pd.read_csv("logs/signin_log.csv")
            except:
                df = pd.DataFrame(
                    columns=[
                        "email_acc",
                        "log_time",
                        "status",
                        "error",
                    ]
                )

            df.loc[len(df)] = [
                email,
                datetime.now(),
                status,
                error,
            ]

            df.to_csv("logs/signin_log.csv", index=False)
            return True
        except:
            return False


def new_profile_logger(email, status, error):
    with lock:

        def db_action():
            conn = None
            try:
                conn = mysql.connector.connect(
                    host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
                )
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO signin_log (server_ip, bot_type, email_acc, log_time, status, error) VALUES (%s, %s, %s, %s, %s, %s)",
                    (SERVER_IP, BOT_TYPE, email, datetime.now(), status, error),
                )
                conn.commit()
                cursor.close()
            finally:
                if conn is not None:
                    conn.close()

        try:
            execute_db_action(db_action)
            return True
        except:
            return False


def update_accounts_data_old(
    email,
    password=None,
    profile_dir=None,
    proxy_used=None,
    has_recovery_email=None,
    recovery_email=None,
    has_recovery_phone=None,
    recovery_phone_number=None,
    joined_microsoft_premium=None,
    has_bitly_account=None,
    bitly_acc_password=None,
    save_smtp="NO",
):
    CSV_PATH = "utils/accounts.csv"

    COLUMNS = [
        "email_acc",
        "password",
        "profile_dir",
        "proxy_used",
        "country",
        "has_recovery_email",
        "recovery_email",
        "has_recovery_phone",
        "recovery_phone_number",
        "joined_microsoft_premium",
        "has_bitly_account",
        "bitly_acc_password",
    ]

    if not email:
        return False

    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

    # Load or create DataFrame
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH, dtype=str)
    else:
        df = pd.DataFrame(columns=COLUMNS)

    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Map args → dict
    values = {
        "email_acc": email,
        "password": password,
        "profile_dir": profile_dir,
        "proxy_used": proxy_used,
        "has_recovery_email": has_recovery_email,
        "recovery_email": recovery_email,
        "country": PREFERRED_SMS_COUNTRY,
        "has_recovery_phone": has_recovery_phone,
        "recovery_phone_number": recovery_phone_number,
        "joined_microsoft_premium": joined_microsoft_premium,
        "has_bitly_account": has_bitly_account,
        "bitly_acc_password": bitly_acc_password,
        "save_smtp": save_smtp,
    }

    if email in df["email_acc"].values:
        idx = df.index[df["email_acc"] == email][0]
        for col, val in values.items():
            if val is not None:
                df.at[idx, col] = str(val)
    else:
        new_row = {col: "" for col in COLUMNS}
        for col, val in values.items():
            if val is not None:
                new_row[col] = str(val)
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    df.to_csv(CSV_PATH, index=False)


def update_accounts_data(
    email,
    password=None,
    date_time=None,
    profile_dir=None,
    proxy_used=None,
    has_recovery_email=None,
    recovery_email=None,
    has_recovery_phone=None,
    recovery_phone_number=None,
    joined_microsoft_premium=None,
    join_time_microsoft_premium=None,
    has_bitly_account=None,
    bitly_acc_password=None,
    save_smtp="NO",
):
    if not email:
        return False

    def db_action():
        conn = None
        try:
            conn = mysql.connector.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
            )
            cursor = conn.cursor()

            # Check if email exists
            cursor.execute(
                "SELECT account_id FROM accounts_details WHERE email_acc = %s", (email,)
            )
            result = cursor.fetchone()

            if result:
                # Update existing record
                update_fields = []
                update_values = []

                if password is not None:
                    update_fields.append("password = %s")
                    update_values.append(password)
                if profile_dir is not None:
                    update_fields.append("profile_dir = %s")
                    update_values.append(profile_dir)
                if join_time_microsoft_premium is not None:
                    update_fields.append("join_time_microsoft_premium = %s")
                    update_values.append(datetime.now())
                if date_time is not None:
                    update_fields.append("date_time = %s")
                    update_values.append(datetime.now())

                if proxy_used is not None:
                    update_fields.append("proxy_used = %s")
                    update_values.append(proxy_used)
                if has_recovery_email is not None:
                    update_fields.append("has_recovery_email = %s")
                    update_values.append(str(has_recovery_email))
                if recovery_email is not None:
                    update_fields.append("recovery_email = %s")
                    update_values.append(recovery_email)
                if has_recovery_phone is not None:
                    update_fields.append("has_recovery_phone = %s")
                    update_values.append(str(has_recovery_phone))
                if recovery_phone_number is not None:
                    update_fields.append("recovery_phone_number = %s")
                    update_values.append(recovery_phone_number)
                if joined_microsoft_premium is not None:
                    update_fields.append("joined_microsoft_premium = %s")
                    update_values.append(str(joined_microsoft_premium))
                if has_bitly_account is not None:
                    update_fields.append("has_bitly_account = %s")
                    update_values.append(str(has_bitly_account))
                if bitly_acc_password is not None:
                    update_fields.append("bitly_acc_password = %s")
                    update_values.append(bitly_acc_password)
                if save_smtp:
                    update_fields.append("save_smtp = %s")
                    update_values.append(save_smtp)

                if update_fields:
                    update_values.append(email)
                    query = f"UPDATE accounts_details SET {', '.join(update_fields)} WHERE email_acc = %s"
                    cursor.execute(query, tuple(update_values))
            else:
                # Insert new record
                cursor.execute(
                    "INSERT INTO accounts_details (server_ip, bot_type, date_time, email_acc, password, profile_dir, proxy_used, country, has_recovery_email, recovery_email, has_recovery_phone, recovery_phone_number, joined_microsoft_premium,join_time_microsoft_premium, has_bitly_account, bitly_acc_password, save_smtp) VALUES (%s, %s, %s, %s, %s,%s,%s, %s, %s, %s, %s, %s, %s,%s, %s, %s, %s)",
                    (
                        SERVER_IP,
                        BOT_TYPE,
                        datetime.now(),
                        email,
                        password,
                        profile_dir,
                        proxy_used,
                        PREFERRED_SMS_COUNTRY,
                        str(has_recovery_email)
                        if has_recovery_email is not None
                        else None,
                        recovery_email,
                        str(has_recovery_phone)
                        if has_recovery_phone is not None
                        else None,
                        recovery_phone_number,
                        str(joined_microsoft_premium)
                        if joined_microsoft_premium is not None
                        else None,
                        datetime.now()
                        if join_time_microsoft_premium is not None
                        else None,
                        str(has_bitly_account)
                        if has_bitly_account is not None
                        else None,
                        bitly_acc_password,
                        save_smtp,
                    ),
                )

            conn.commit()
            return True
        finally:
            if conn is not None:
                conn.close()

    try:
        execute_db_action(db_action)
        return True
    except Exception as e:
        print(f"Error saving to accounts table: {e}")
        return False


def close_other_tabs(driver):
    """
    Closes all other tabs
    """
    try:
        main = driver.window_handles[0]

        for handle in driver.window_handles[1:]:
            driver.switch_to.window(handle)
            driver.close()

        driver.switch_to.window(main)
        return True
    except:
        return False


def premium_logger(email_address, password, temp_email):
    try:
        with open("logs/accounts.txt", "a") as f:
            f.write(f"{email_address},{password},{temp_email},{datetime.now()}\n")
    except:
        pass


def click_continue_if_you_see_this_code_button_smtp(driver):
    """
    Clicks the next button on gmail login
    """
    try:
        retries = 0
        while retries < 5:
            try:
                H1_ELEMENT = (By.TAG_NAME, "h1")

                header_element = WebDriverWait(driver, wait_time).until(
                    EC.visibility_of_element_located(H1_ELEMENT)
                )
                if header_element.text.lower().startswith(
                    "continue if you see this code"
                ):
                    CONTINUE_BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[type="submit"]')

                    continue_button = WebDriverWait(driver, wait_time).until(
                        EC.element_to_be_clickable(CONTINUE_BUTTON_ELEMENT)
                    )

                    continue_button.click()

                    return True
            except:
                pass

            time.sleep(2)

        return False

    except:
        return False


def is_let_this_app_access_your_info_page(driver):
    """
    Clicks the stay signed in button after login
    """
    try:
        HEADER_ELEMENT = (By.CSS_SELECTOR, 'div[data-testid="appConsentTitle"]')

        header_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(HEADER_ELEMENT)
        )

        if header_element.text.lower().startswith("let this app access your info"):
            return True
        else:
            return False
    except:
        return False


def all_done_page(driver):
    """
    Checks if page is all done page
    """
    try:
        SUCCESS_LABEL_ELEMENT = (By.CSS_SELECTOR, 'div[id="idDiv_Finish_ErrTxt"]')

        success_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(SUCCESS_LABEL_ELEMENT)
        )

        time.sleep(3)
        success_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(SUCCESS_LABEL_ELEMENT)
        )
        if success_element.text.lower().startswith(
            "you're now signed in to outlook oauth app"
        ):
            return True
        else:
            return False
    except:
        return False


def smtp_accept_access(driver):
    try:
        BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[type="submit"]')

        button_elements = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_all_elements_located(BUTTON_ELEMENT)
        )

        button_element = button_elements[
            [i.text.lower() for i in button_elements].index("accept")
        ]

        button_element.click()
        return True
    except:
        return False


def load_cache():
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_PATH):
        cache.deserialize(open(CACHE_PATH, "r").read())
    return cache


def save_cache(cache):
    if cache.has_state_changed:
        # os.makedirs(CACHE_PATH, exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            f.write(cache.serialize())


def click_existing_account_smtp(driver, wait_time=wait_time):
    """
    Clicks the existing account button on login page if exists
    """
    try:
        EXISTING_ACC_BTN_ELEMENT = (By.CSS_SELECTOR, 'div[id="newSessionLink"]')

        existing_acc_btn_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(EXISTING_ACC_BTN_ELEMENT)
        )

        existing_acc_btn_element.click()
        return True
    except:
        return False


def enter_smtp_code(driver, code):
    """
    Enters code in otp field
    """
    try:
        wait_time = 10
        OTP_INPUT_ELEMENT = (By.CSS_SELECTOR, 'input[name="otc"]')

        otp_input_element = WebDriverWait(driver, wait_time / 2).until(
            EC.visibility_of_element_located(OTP_INPUT_ELEMENT)
        )

        otp_input_element.clear()
        otp_input_element.send_keys(code)
        time.sleep(0.5)

        NEXT_BTN_ELEMENT = (By.CSS_SELECTOR, 'input[type="submit"]')

        next_btn_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(NEXT_BTN_ELEMENT)
        )

        next_btn_element.click()
        time.sleep(0.5)

        return True
    except:
        return False


def setup_smtp_driver(driver, verification_url, code):
    """
    Lauches chrome driver for login
    """
    try:
        retries = 0
        while retries < 5:
            try:
                driver.maximize_window()
                time.sleep(2)
                driver.get(verification_url)
                if enter_smtp_code(driver, code):
                    return True
            except:
                pass
            retries += 1
        return False
    except:
        return False


def entire_smtp_process(driver, new_profile_data):
    try:
        email_address = new_profile_data.get("email")
        password = new_profile_data.get("pass")
        print(f"{email_address} : Creating app. Getting login url and code")

        cache = load_cache()
        app = msal.PublicClientApplication(
            CLIENT_ID, authority=AUTHORITY, token_cache=cache
        )
        print(f"{email_address} : Created app. Getting login url and code")
        flow = app.initiate_device_flow(scopes=SCOPES)
        verification_url = flow["verification_uri"]
        setup_code = flow["message"].split(" ")[
            flow["message"].split(" ").index("code") + 1
        ]
        print(f"{email_address} : Got login url and code")
        status = setup_smtp_driver(
            driver=driver, verification_url=verification_url, code=setup_code
        )
        if not status:
            return False, "Error setting up driver"

        print(f"{email_address} : Successfully set up driver")
        click_existing_account_smtp(driver)
        if click_continue_if_you_see_this_code_button_smtp(driver):
            print(f"{email_address} : Clicked continue if you see this code button")
        else:
            print(
                f"{email_address} : Continue if you see this code button not found. Continuing without clicking it."
            )
            return (
                False,
                "Error clicking Continue if you see this code button not found",
            )

        if not enter_password(driver=driver, password=password):
            print(f"{email_address}: Error entering password")
            return False, "Error Entering password"
        time.sleep(1)

        if not click_password_next_button(driver=driver):
            print(
                f"{email_address}: Error clicking next button after entering password"
            )
            return False, "Error clicking next button after entering password"
        time.sleep(1)

        time.sleep(1)
        if is_let_this_app_access_your_info_page(driver):
            print(f"{email_address} : Accept access page displayed")
            if smtp_accept_access(driver):
                print(f"{email_address} : Clicked access button")
        else:
            print(f"{email_address} : Accept access page NOT displayed")

        if all_done_page(driver):
            print(
                f"{email_address} : Manual signing completed successfully. Saving tokens"
            )
            result = app.acquire_token_by_device_flow(flow)
            save_cache(cache)
            print(f"{email_address} : Successfully saved tokens")

            return True, "SUCCESS"
        else:
            print(f"{email_address} : Authorization UNSUCCESSFULL")

            return False, "PROCESS DONE BUT NO SUCCESS PAGE"
    except Exception as e:
        return False, f"Undocumented error during SMTP process: {str(e)}"


def failed_smtp(email_address, password, temp_email):
    try:
        with open("output_data/failed_smtp.txt", "a", encoding="utf-8") as file:
            file.write(",".join([email_address, password, temp_email]) + "\n")
    except:
        pass


def smtp_process(driver, new_profile_data):
    retries = 0
    message = "Fail"
    while retries < 3:
        try:
            status, message = entire_smtp_process(driver, new_profile_data)
            if status:
                return True, message
            else:
                print(
                    f"{new_profile_data.get('email')} : SMTP ERROR -> {message} Retrying..."
                )

        except Exception as e:
            print(
                f"{new_profile_data.get('email')} : Exception during SMTP process: {str(e)}"
            )

        retries += 1

    print(f"{new_profile_data.get('email')} : Out of retries...")

    return False, message


def click_use_your_password_button(driver):
    """
    Clicks the use your password button
    """
    try:
        BUTTON_ELEMENT = (By.CSS_SELECTOR, 'span[role="button"]')

        button_elements = WebDriverWait(driver, wait_time / 2).until(
            EC.visibility_of_all_elements_located(BUTTON_ELEMENT)
        )

        button_element = button_elements[
            [
                i.text.lower().startswith("use your password") for i in button_elements
            ].index(True)
        ]

        button_element.click()
        return True
    except:
        return False


def click_send_code_to_recovery_email_button(driver):
    """
    Clicks the use your password button
    """
    try:
        BUTTON_ELEMENT = (By.CSS_SELECTOR, 'span[role="button"]')

        button_elements = WebDriverWait(driver, wait_time / 2).until(
            EC.visibility_of_all_elements_located(BUTTON_ELEMENT)
        )

        button_element = button_elements[
            [
                i.text.lower().startswith("send a code to") for i in button_elements
            ].index(True)
        ]

        button_element.click()
        return True
    except:
        return False


def change_acc_pass(driver, new_profile_data):
    try:
        password = new_profile_data.get("pass")
        email = new_profile_data.get("email")
        print(f"{email} : Initializing change password")

        bring_to_front(driver)
        pass_change_url = "https://account.live.com/password/change"

        driver.get(pass_change_url)

        time.sleep(2)

        new_pass = password + ".!Ze8"
        # new_pass = password + "."

        retries = 0
        while retries < 3:
            try:
                PASSWORD_ELEMENT = (By.CSS_SELECTOR, 'input[type="password"]')

                password_input_elements = WebDriverWait(driver, wait_time).until(
                    EC.visibility_of_all_elements_located(PASSWORD_ELEMENT)
                )

                for password_input_element in password_input_elements:
                    password_input_element.clear()
                    password_input_element.send_keys(new_pass)
                    time.sleep(1)

                print(f"{email} : Entered and confirmed new password")
                retries = 10
                break
            except:
                print(f"{email} : Error locating password input elements. Retrying...")
                driver.get(pass_change_url)
                time.sleep(2)

                retries += 1

        if retries != 10:
            return False, "Error entering new password"

        time.sleep(2)
        if not click_next_button_rec_email(driver=driver):
            print(f"{email} : Error clicking next button after changing password")
            return False, "Error locating password input elements"
        time.sleep(1)

        # RELOG IN
        try:
            print(f"{email}: Reloging in with NEW password")
            click_existing_account_smtp(driver)

            click_use_your_password_button(driver)

            if enter_password(driver=driver, password=new_pass):
                click_password_next_button(driver=driver)
        except:
            pass

        print(f"{email} : Password changed successfully")
        return True, new_pass

    except Exception as e:
        print(f"{email} : Exception error while changing password: {str(e)}")
        return False, f"Exception during changing password: {str(e)}"


def re_login_existing_acc(driver, password):
    try:
        if click_existing_account_smtp(driver, wait_time=2) or enter_password(
            driver, password, 2
        ):
            click_use_your_password_button(driver)
            time.sleep(2)
            if enter_password(driver=driver, password=password):
                click_password_next_button(driver=driver)
                return True

        return False
    except:
        return False


def logout_then_re_login_existing_acc(driver, new_profile_data):
    try:
        email = new_profile_data.get("email")
        password = new_profile_data.get("pass")
        recovery = new_profile_data.get("recovery_email")

        print(f"{email} : Logging out then in again")

        driver.get("https://login.live.com/logout.srf")
        bring_to_front(driver)
        time.sleep(10)

        driver.get(MICROSOFT_LOGIN_URL)

        enter_email(driver, email)
        click_next_button(driver)
        click_send_code_to_recovery_email_button(driver)
        enter_recovery_email_2(driver, recovery)
        # click_next_button(driver)
        click_password_next_button(driver)
        status, code = wait_for_code_by_recovery_mail(recovery)
        if not status:
            print(f"{email} : Code not sent to recovery email!")
            return False
        enter_code_and_click_next_after_pass_change(driver, code)
        click_stay_signed_in_button(driver)
        driver.get("https://account.microsoft.com/profile")
        login_on_country_page(driver, new_profile_data)
        print(f"{email} : Re-logged in successfully")
        return True

    except:
        return False


def logout_then_re_login_existing_acc___(driver, new_profile_data):
    try:
        email = new_profile_data.get("email")
        password = new_profile_data.get("pass")
        recovery = new_profile_data.get("recovery_email")

        print(f"{email} : Logging out then in again")

        driver.get("https://login.live.com/logout.srf")
        bring_to_front(driver)
        time.sleep(3)

        driver.get(MICROSOFT_LOGIN_URL)

        enter_email(driver, email)
        click_next_button(driver)
        click_use_your_password_button(driver)
        time.sleep(2)
        if enter_password(driver=driver, password=password):
            time.sleep(2)
            click_password_next_button(driver=driver)
            click_stay_signed_in_button(driver)
            driver.get("https://account.microsoft.com/profile")

            print(f"{email} : Re-logged in successfully")
            return True

        return False
    except:
        driver.get(MICROSOFT_LOGIN_URL)

        enter_email(driver, email)
        click_next_button(driver)
        click_send_code_to_recovery_email_button(driver)
        enter_recovery_email_2(driver, recovery)
        click_next_button(driver)
        click_password_next_button(driver)
        status, code = wait_for_code_by_recovery_mail(recovery)
        enter_code_and_click_next_after_pass_change(driver, code)
        click_stay_signed_in_button(driver)
        return True


def country_is_the_desired(driver):
    try:
        COUNTRY_EDIT_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'div[id="profile.profile-info.country-or-region.listItem"]',
        )

        country_edit_button = WebDriverWait(driver, wait_time / 3).until(
            EC.element_to_be_clickable(COUNTRY_EDIT_BUTTON_ELEMENT)
        )

        # scroll to view first
        driver.execute_script(
            "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
            country_edit_button,
        )
        time.sleep(1)

        if CHANGE_COUNTRY.lower() in country_edit_button.text.lower():
            return True
        else:
            return False

    except:
        return False


def language_is_the_desired(driver):
    try:
        LANGUAGE_EDIT_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'select[id="cultureSelectId"]',
        )

        language_edit_button = WebDriverWait(driver, wait_time * 2).until(
            EC.element_to_be_clickable(LANGUAGE_EDIT_BUTTON_ELEMENT)
        )

        # scroll to view first
        driver.execute_script(
            "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
            language_edit_button,
        )
        time.sleep(1)

        if (
            Select(language_edit_button).first_selected_option.text
            == "English (United States)"
        ):
            return True
        else:
            return False

    except:
        return False


def select_english_language(driver):
    try:
        LANGUAGE_EDIT_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'select[id="cultureSelectId"]',
        )

        SAVE_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'div[class="Xut6I"]>button',
        )

        language_edit_button = WebDriverWait(driver, wait_time / 3).until(
            EC.element_to_be_clickable(LANGUAGE_EDIT_BUTTON_ELEMENT)
        )

        # scroll to view first
        driver.execute_script(
            "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
            language_edit_button,
        )
        time.sleep(1)

        Select(language_edit_button).select_by_value("en-US")

        time.sleep(1)

        save_button_element = WebDriverWait(driver, wait_time / 3).until(
            EC.element_to_be_clickable(SAVE_BUTTON_ELEMENT)
        )
        save_button_element.click()

        return True

    except:
        return False


def change_timezone(driver):
    try:
        timezone_url = "https://outlook.live.com/mail/options/calendar/view/timezones"
        driver.get(timezone_url)

        card_details_dict = get_processing_card()

        TZ_EDIT_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'input[placeholder="Search for a city"]',
        )

        UPDATE_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'div[class*="fui-MessageBarActions "] > button',
        )

        OPTIONS_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            "button[role='option']",
        )

        SAVE_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'div[class="Xut6I"]>button',
        )

        tz_edit_button = WebDriverWait(driver, wait_time * 5).until(
            EC.element_to_be_clickable(TZ_EDIT_BUTTON_ELEMENT)
        )

        tz_edit_button.clear()

        try:
            city_state = (
                card_details_dict.get("city") + " " + card_details_dict.get("state")
            )
        except:
            city_state = "Washington, District of Columbia"

        tz_edit_button.send_keys(city_state)
        time.sleep(3)
        tz_options = WebDriverWait(driver, wait_time / 2).until(
            EC.presence_of_all_elements_located(OPTIONS_BUTTON_ELEMENT)
        )

        if len(tz_options) > 0:
            tz_edit_button.send_keys(Keys.ENTER)
        else:
            city_state = "Washington, District of Columbia"

            tz_edit_button.send_keys(city_state)
            time.sleep(3)
            tz_edit_button.send_keys(Keys.ENTER)

        time.sleep(1)

        try:
            save_button = WebDriverWait(driver, wait_time / 2).until(
                EC.element_to_be_clickable(SAVE_BUTTON_ELEMENT)
            )

            # scroll to view first
            driver.execute_script(
                "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                save_button,
            )
            time.sleep(1)
            save_button.click()
        except:
            pass

        time.sleep(1)

        try:
            update_button = WebDriverWait(driver, wait_time / 2).until(
                EC.element_to_be_clickable(UPDATE_BUTTON_ELEMENT)
            )

            # scroll to view first
            driver.execute_script(
                "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                update_button,
            )
            time.sleep(1)
            update_button.click()
        except:
            pass

        return True

    except:
        return False


def click_accept_preferences_button(driver):
    try:
        retries = 0
        while retries < 10:
            try:
                LANGUAGE_EDIT_BUTTON_ELEMENT = (
                    By.CSS_SELECTOR,
                    'div[class="X6UT9"] > button:nth-child(3)',
                )

                NO_THANKS_BUTTON_ELEMENT = (
                    By.CSS_SELECTOR,
                    'button[class="fui-Button r1f29ykk"]',
                )

                try:
                    language_edit_button = WebDriverWait(driver, 1).until(
                        EC.element_to_be_clickable(LANGUAGE_EDIT_BUTTON_ELEMENT)
                    )
                except:
                    language_edit_button = WebDriverWait(driver, 1).until(
                        EC.element_to_be_clickable(NO_THANKS_BUTTON_ELEMENT)
                    )

                # scroll to view first
                driver.execute_script(
                    "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                    language_edit_button,
                )
                time.sleep(1)

                language_edit_button.click()

                return True

            except:
                pass

            time.sleep(1)
            retries += 1

        return False
    except:
        return False


def login_on_country_page(driver, new_profile_data):
    try:
        email = new_profile_data.get("email")
        password = new_profile_data.get("pass")

        SIGN_IN_BTN = (
            By.CSS_SELECTOR,
            'button[data-bi-id="signedout.hero.signIn"]',
        )

        sign_in_btn = WebDriverWait(driver, wait_time / 2).until(
            EC.element_to_be_clickable(SIGN_IN_BTN)
        )
        sign_in_btn.click()
        time.sleep(2)

        # new_pass = password + ".!Ze8"
        print(f"{email} : Sign in button found on profile page.")
        # status, error = change_acc_pass(
        #     driver, new_profile_data=new_profile_data
        # )
        print(f"{email} : Reloging in with NEW password")
        click_existing_account_smtp(driver)
        click_use_your_password_button(driver)
        time.sleep(2)
        if enter_password(driver=driver, password=password):
            click_password_next_button(driver=driver)
            driver.get("https://account.microsoft.com/profile")
            return True
    except:
        return False


def change_account_country(driver, new_profile_data):
    try:
        retries = 0
        num_of_retries = 5
        while retries < num_of_retries:
            try:
                email = new_profile_data.get("email")
                password = new_profile_data.get("pass")
                bring_to_front(driver)

                driver.get("https://account.microsoft.com/profile")

                login_on_country_page(driver, new_profile_data)

                if country_is_the_desired(driver):
                    return True

                COUNTRY_EDIT_BUTTON_ELEMENT = (
                    By.CSS_SELECTOR,
                    'div[id="profile.profile-info.country-or-region.listItem"]',
                )

                country_edit_button = WebDriverWait(driver, wait_time).until(
                    EC.element_to_be_clickable(COUNTRY_EDIT_BUTTON_ELEMENT)
                )

                # scroll to view first
                driver.execute_script(
                    "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                    country_edit_button,
                )
                time.sleep(1)
                country_edit_button.click()
                time.sleep(1)

                COUNTRY_INPUT_ELEMENT = (
                    By.CSS_SELECTOR,
                    'input[id="profile.edit-profile-info.region-input"]',
                )

                country_input_element = WebDriverWait(driver, wait_time).until(
                    EC.visibility_of_element_located(COUNTRY_INPUT_ELEMENT)
                )

                # data[0]
                country_input_element.click()
                re_login_existing_acc(driver, password)
                time.sleep(0.5)
                country_input_element.send_keys(Keys.BACK_SPACE * 50)
                time.sleep(0.5)
                country_input_element.send_keys(CHANGE_COUNTRY)
                time.sleep(2.5)
                country_input_element.send_keys(Keys.ENTER)
                time.sleep(1)

                try:
                    SAVE_BUTTON_ELEMENT = (By.CSS_SELECTOR, 'button[aria-label="Save"]')

                    save_button_element = WebDriverWait(driver, wait_time).until(
                        EC.element_to_be_clickable(SAVE_BUTTON_ELEMENT)
                    )

                    save_button_element.click()
                    time.sleep(2)
                except:
                    logout_then_re_login_existing_acc(driver, new_profile_data)

                if country_is_the_desired(driver):
                    return True
                else:
                    print(
                        f"{email} : Country not changed. Retrying... ({retries}/{num_of_retries})"
                    )
                    retries += 1

            except Exception as E:
                retries += 1
                print(
                    f"{email} : Exception error changing country. Retrying... ({retries}/{num_of_retries})"
                )

        return False
    except:
        return False


def change_account_language(driver, new_profile_data):
    try:
        retries = 0
        num_of_retries = 5
        while retries < num_of_retries:
            try:
                email = new_profile_data.get("email")
                password = new_profile_data.get("pass")
                bring_to_front(driver)
                language_url = (
                    "https://outlook.live.com/mail/options/general/timeAndLanguage"
                )

                driver.get(language_url)
                time.sleep(2)
                driver.get(language_url)

                # login_on_country_page(driver, new_profile_data)

                click_accept_preferences_button(driver)

                if language_is_the_desired(driver):
                    change_timezone(driver)
                    return True

                select_english_language(driver)
                change_timezone(driver)
                driver.get(language_url)

                if language_is_the_desired(driver):
                    return True

            except Exception as E:
                retries += 1
                print(
                    f"{email} : Exception error changing language: {E}. Retrying... ({retries}/{num_of_retries})"
                )

        return False
    except:
        return False


def get_fakey_data(driver, country="united states"):
    try:
        countries = {
            "united states": "https://www.fakexy.com/fake-address-generator-us",
            "sweden": "https://www.fakexy.com/fake-address-generator-se",
            "poland": "https://www.fakexy.com/fake-address-generator-pl",
            "norway": "https://www.fakexy.com/fake-address-generator-no",
        }

        # url = "https://www.fakexy.com/fake-address-generator-se"
        # url = "https://www.fakexy.com"
        url = countries.get(country.lower())
        # driver.execute_script(f"window.open('{url}', '_blank');")
        driver.get(url)
        # driver.switch_to.window(driver.window_handles[1])
        wait = WebDriverWait(driver, 5)

        retries = 0
        while retries < 3:
            try:
                LOGO_ELEMENT = (By.CSS_SELECTOR, 'h2[class="logoh"]')
                logo = wait.until(EC.visibility_of_element_located(LOGO_ELEMENT))
                if logo.text.lower().startswith("fake address generator"):
                    retries = 5
                    # print("Fakey tab loaded successfully")
                    break
                else:
                    print("Logo displayed differently!!")
                    driver.refresh()
                    retries += 1
            except:
                try:
                    # time.sleep(10)
                    driver.uc_gui_click_captcha()
                    time.sleep(5)
                    pyautogui.click()
                    time.sleep(5)

                    logo = wait.until(EC.visibility_of_element_located(LOGO_ELEMENT))
                    if logo.text.lower().startswith("fake address generator"):
                        retries = 5
                        # print("Fakey tab loaded successfully")
                        break
                    else:
                        driver.refresh()
                        retries += 1
                except:
                    driver.refresh()
                    retries += 1
            # except:
            #     driver.refresh()
            #     retries += 1

        wait = WebDriverWait(driver, 10)
        if retries != 5:
            print("Error loading fakey tab")
            return False, "Error loading fakey tab"

        # Wait for at least one section to load
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.box")))

        section_data = {}

        boxes = driver.find_elements("css selector", "div.box")

        for box in boxes:
            try:
                title = box.find_element(By.CSS_SELECTOR, "h1.titleh").text.strip()
            except:
                continue

            # Skip hidden sections
            if "display: none" in (box.get_attribute("style") or ""):
                continue

            # Wait for rows inside this box (if table exists)
            try:
                WebDriverWait(driver, 1).until(
                    lambda d: (
                        len(box.find_elements(By.CSS_SELECTOR, "table tbody tr")) > 0
                    )
                )
            except:
                pass

            rows = box.find_elements(By.CSS_SELECTOR, "table tbody tr")

            for row in rows:
                cols = row.find_elements(By.CSS_SELECTOR, "td")
                if len(cols) == 2:
                    key = cols[0].text.strip()
                    value = cols[1].text.strip()
                    if key == "Expire":
                        # section_data["expiry_month"] = value.split("/")[1].strip()
                        # section_data["expiry_year"] = value.split("/")[0].strip()
                        pass
                    elif key == "City/Town":
                        section_data["city"] = value
                    elif key == "Zip/Postal Code":
                        section_data["postal_code"] = value
                    elif key == "Street":
                        section_data["address_line1"] = value
                    elif key == "Credit card number":
                        # section_data["card_number"] = value
                        pass
                    elif key == "Full Name":
                        # section_data["name_on_card"] = value
                        pass
                    elif key == "CVV":
                        # section_data["cvv"] = value
                        pass
                    elif key == "State/Province/Region":
                        section_data["state"] = value
                        pass
                    else:
                        pass
                        # section_data[key] = value

        return True, section_data

    except:
        return False, {}
    finally:
        driver.switch_to.window(driver.window_handles[0])
        close_other_tabs(driver)


def get_fake_details():
    try:
        # countries = ["sweden", "united states", "poland", "norway"]
        countries = ["sweden"]
        num_records = 500

        driver = Driver(
            uc=True,
            binary_location=chrome_location,
            extension_dir=extension_dir,
            locale_code="en",
        )

        driver.maximize_window()

        # for each country, get num_records fake details and save as a ductionary, key = country, value = list of dictionaries with details.
        # Ensure previous one is not same as old one
        all_details = {}
        # country = countries[0]
        for country in countries:
            connect_us_random()
            time.sleep(1)
            country_data = []
            for i in range(num_records):
                try:
                    data = get_fakey_data(driver, country=country)
                    if data[0]:
                        country_data.append(data[1])
                        print(f"Got fake details for {country} ({i + 1}/{num_records})")
                except:
                    print(
                        f"Error getting fake details for {country} ({i + 1}/{num_records})"
                    )
                time.sleep(1)
            all_details[country] = country_data
            print(f"Completed getting fake details for {country}")

        with open("utils/fake_details.json", "w") as f:
            json.dump(all_details, f)

    except:
        pass


def get_creditcard_details_old():
    with open("input_data/card_details.txt", "r", encoding="utf-8") as f:
        lines = [i.split(",") for i in f.read().split("\n") if i]
        cards_data = []
        # line = lines[0]
        for line in lines:
            random_location = random.choice(
                json.load(open("utils/fake_details.json", "r"))[PREFERRED_SMS_COUNTRY]
            )

            random_name = (
                random.choice(
                    open("input_data/names.txt", "r", encoding="utf-8")
                    .read()
                    .split("\n")
                )
                + " "
                + random.choice(
                    open("input_data/surnames.txt", "r", encoding="utf-8")
                    .read()
                    .split("\n")
                )
            )

            # (
            #     random.choice(open("input_data/names.txt", "r").read().split("\n"))
            #     + " "
            #     + random.choice(open("input_data/surnames.txt", "r").read().split("\n"))
            # )
            cards_data.append(
                {
                    "name_on_card": random_name,
                    "card_number": line[0].strip().replace(" ", ""),
                    "expiry_month": line[1].strip().split("/")[0].strip(),
                    "expiry_year": "20" + line[1].strip().split("/")[1].strip(),
                    "cvv": line[2].strip(),
                    "address_line1": random_location.get("address_line1", ""),
                    "city": random_location.get("city", ""),
                    "postal_code": random_location.get("postal_code", ""),
                }
            )
        return cards_data


def get_creditcard_details():
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    cursor = conn.cursor(dictionary=True)

    # Get all card details for preferred country
    cursor.execute(
        "SELECT * FROM familybot_card_details WHERE LOWER(country) = %s",
        (PREFERRED_SMS_COUNTRY,),
    )
    cards = cursor.fetchall()

    # # Get first names for preferred country
    # cursor.execute(
    #     "SELECT firstnames FROM familybot_first_names WHERE LOWER(country) = %s",
    #     (PREFERRED_SMS_COUNTRY,),
    # )
    # first_names = [row["firstnames"] for row in cursor.fetchall()]

    # # Get surnames for preferred country
    # cursor.execute(
    #     "SELECT surnames FROM familybot_surnames WHERE LOWER(country) = %s",
    #     (PREFERRED_SMS_COUNTRY,),
    # )
    # surnames = [row["surnames"] for row in cursor.fetchall()]

    # # Get fake details for preferred country
    # cursor.execute(
    #     "SELECT * FROM familybot_fake_details WHERE LOWER(country) = %s",
    #     (PREFERRED_SMS_COUNTRY,),
    # )
    # locations = cursor.fetchall()

    conn.close()

    cards_data = []
    for card in cards:
        # random_location = random.choice(locations) if locations else {}
        # random_name = random.choice(first_names) + " " + random.choice(surnames)

        cards_data.append(
            {
                "name_on_card": card["name_on_card"].strip(),
                "card_number": str(card["card_number"]).replace(" ", ""),
                "expiry_month": card["expiry_month_year"].strip().split("/")[0].strip(),
                "expiry_year": "20"
                + card["expiry_month_year"].strip().split("/")[1].strip(),
                "cvv": card["cvv"],
                "address_line1": card["address_line1"].strip(),
                "city": card["city"].strip(),
                "country": card["country"].strip(),
                "state": card["state"].strip(),
                "postal_code": card["postal_code"].strip(),
            }
        )
    return cards_data


def log_card_usage(card_details):
    def db_action():
        conn = None
        try:
            conn = mysql.connector.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
            )
            cursor = conn.cursor()
            timestamp = datetime.now()
            card_number = card_details.get("card_number")
            expiry = f"{card_details.get('expiry_month')}/{card_details.get('expiry_year')[2:]}"  # MM/YY
            cvv = card_details.get("cvv")
            cursor.execute(
                "INSERT INTO familybot_card_usage_log (server_ip, bot_type, use_datetime, card_num, `exp_month/year`, cvv, country) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    SERVER_IP,
                    BOT_TYPE,
                    timestamp,
                    card_number,
                    expiry,
                    cvv,
                    PREFERRED_SMS_COUNTRY,
                ),
            )
            conn.commit()
        finally:
            if conn is not None:
                conn.close()

    execute_db_action(db_action)


def mark_card_failed_old(card_details):
    # Save to output_data/failed_cards.txt
    # card_details = all_cards[0]
    os.makedirs("output_data", exist_ok=True)

    failure_reason = "failed"
    try:
        log_file = "logs/card_usage.log"
        timestamps = []
        if os.path.exists(log_file):
            with open(log_file, "r") as lf:
                for line in lf:
                    parts = line.strip().split(",")
                    if len(parts) == 4:
                        timestamp_str, card_num, expiry, cvv = parts
                        if (
                            card_num == card_details.get("card_number")
                            and expiry
                            == f"{card_details.get('expiry_month')}/{card_details.get('expiry_year')}"
                            and cvv == card_details.get("cvv")
                        ):
                            try:
                                timestamps.append(datetime.fromisoformat(timestamp_str))
                            except:
                                pass
        uses = len(timestamps)
        if uses == 0:
            failure_reason = "failed on first attempt"
        elif uses == 1:
            failure_reason = "failed on second attempt"
        elif uses == 2:
            if timestamps:
                elapsed_hrs = (
                    datetime.now() - max(timestamps)
                ).total_seconds() / 3600.0
                failure_reason = (
                    f"failed on third attempt after waiting {elapsed_hrs:.1f} hrs"
                )
            else:
                failure_reason = "failed on third attempt"
        elif uses == 3:
            failure_reason = "failed after 4 times"
        elif uses == 4:
            if timestamps:
                elapsed_hrs = (
                    datetime.now() - max(timestamps)
                ).total_seconds() / 3600.0
                failure_reason = (
                    f"failed on fifth attempt after waiting {elapsed_hrs:.1f} hrs"
                )
            else:
                failure_reason = "failed after 4 times"
        else:
            failure_reason = f"failed after {uses + 1} attempts"
    except:
        failure_reason = "failed"

    with open("output_data/failed_cards.txt", "a") as f:
        card_number = card_details.get("card_number")
        expiry = (
            f"{card_details.get('expiry_month')}/{card_details.get('expiry_year')[-2:]}"
        )
        cvv = card_details.get("cvv")
        f.write(f"{card_number},{expiry},{cvv},{failure_reason}\n")

    # Remove from input_data/card_details.txt
    with open("input_data/card_details.txt", "r") as f:
        lines = f.readlines()
        # line= lines[0]

    with open("input_data/card_details.txt", "w") as f:
        for line in lines:
            parts = [p.strip() for p in line.strip().split(",")]
            if len(parts) >= 3:
                if (
                    parts[0].replace(" ", "") == card_details.get("card_number")
                    and parts[1].split("/")[0].strip()
                    == card_details.get("expiry_month")
                    and "20" + parts[1].split("/")[1].strip()
                    == card_details.get("expiry_year")
                    and parts[2] == card_details.get("cvv")
                ):
                    continue  # skip this line
            f.write(line)


def mark_card_failed(card_details):
    def db_action():
        conn = None
        try:
            conn = mysql.connector.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
            )
            cursor = conn.cursor(dictionary=True)

            failure_reason = "failed"
            try:
                card_number = card_details.get("card_number")
                expiry = f"{card_details.get('expiry_month')}/{card_details.get('expiry_year')[2:]}"
                cvv = card_details.get("cvv")

                # Get logs from DB
                cursor.execute(
                    "SELECT use_datetime FROM familybot_card_usage_log WHERE LOWER(country) = %s AND card_num = %s AND `exp_month/year` = %s AND cvv = %s ORDER BY use_datetime",
                    (PREFERRED_SMS_COUNTRY, card_number, expiry, cvv),
                )
                logs = cursor.fetchall()
                timestamps = [row["use_datetime"] for row in logs]

                uses = len(timestamps)
                if uses == 0:
                    failure_reason = "failed on first attempt"
                elif uses == 1:
                    failure_reason = "failed on second attempt"
                elif uses == 2:
                    if timestamps:
                        elapsed_hrs = (
                            datetime.now() - max(timestamps)
                        ).total_seconds() / 3600.0
                        failure_reason = f"failed on third attempt after waiting {elapsed_hrs:.1f} hrs"
                    else:
                        failure_reason = "failed on third attempt"
                elif uses == 3:
                    failure_reason = "failed after 4 times"
                elif uses == 4:
                    if timestamps:
                        elapsed_hrs = (
                            datetime.now() - max(timestamps)
                        ).total_seconds() / 3600.0
                        failure_reason = f"failed on fifth attempt after waiting {elapsed_hrs:.1f} hrs"
                    else:
                        failure_reason = "failed after 4 times"
                else:
                    failure_reason = f"failed after {uses + 1} attempts"
            except:
                failure_reason = "failed"

            # Insert into familybot_failed_cards
            card_number = card_details.get("card_number")
            expiry = f"{card_details.get('expiry_month')}/{card_details.get('expiry_year')[2:]}"
            cvv = card_details.get("cvv")
            cursor.execute(
                "INSERT INTO familybot_failed_cards (server_ip, bot_type,date_time, card_number, expiry_month_year, cvv, country, reason_for_fail) VALUES (%s, %s,%s, %s, %s, %s, %s, %s)",
                (
                    SERVER_IP,
                    BOT_TYPE,
                    datetime.now(),
                    card_number,
                    expiry,
                    cvv,
                    PREFERRED_SMS_COUNTRY,
                    failure_reason,
                ),
            )

            # Remove from processing_card_details
            cursor.execute(
                "DELETE FROM processing_card_details WHERE card_number = %s AND expiry_month_year = %s AND cvv = %s",
                (card_number, expiry, cvv),
            )

            conn.commit()
        finally:
            if conn is not None:
                conn.close()

    execute_db_action(db_action)


def get_next_card_old():
    all_cards = get_creditcard_details()
    # Load usage log
    usage = {}
    log_file = "logs/card_usage.log"
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 4:
                    timestamp_str, card_num, expiry, cvv = parts
                    key = (card_num, expiry, cvv)
                    if key not in usage:
                        usage[key] = []
                    try:
                        usage[key].append(datetime.fromisoformat(timestamp_str))
                    except:
                        pass  # invalid timestamp

    # Now, for each card, check if can use
    available_cards = []
    fully_used = []

    # card = all_cards[0]
    for card in all_cards:
        card_num = card["card_number"]
        expiry = f"{card['expiry_month']}/{card['expiry_year']}"
        cvv = card["cvv"]
        key = (card_num, expiry, cvv)
        timestamps = sorted(usage.get(key, []))
        uses = len(timestamps)
        now = datetime.now()
        can_use = False
        if uses >= 5:
            fully_used.append(card)
            continue
        elif uses in [0, 1, 3]:
            can_use = True
        elif uses == 2:
            if timestamps and now > timestamps[-1] + timedelta(
                hours=CREDIT_CARD_INTERVAL_HRS
            ):
                can_use = True
        elif uses == 4:
            if timestamps and now > timestamps[-1] + timedelta(
                hours=CREDIT_CARD_INTERVAL_HRS
            ):
                can_use = True
        if can_use:
            available_cards.append(card)

    # If there are fully used, save them and remove from input
    if fully_used:
        os.makedirs("output_data", exist_ok=True)
        with open("output_data/fully_used_cards.txt", "a") as f:
            for card in fully_used:
                card_num = card["card_number"]
                expiry = f"{card['expiry_month']}/{card['expiry_year']}"
                cvv = card["cvv"]
                f.write(f"{card_num},{expiry},{cvv}\n")

        # Remove from input_data/card_details.txt
        with open("input_data/card_details.txt", "r") as f:
            lines = f.readlines()

        with open("input_data/card_details.txt", "w") as f:
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    card_num = parts[0].replace(" ", "")
                    exp_month = parts[1].split("/")[0].strip()
                    exp_year = "20" + parts[1].split("/")[1].strip()
                    cvv = parts[2]
                    expiry = f"{exp_month}/{exp_year}"
                    if any(
                        f"{c['card_number']},{c['expiry_month']}/{c['expiry_year']},{c['cvv']}"
                        == f"{card_num},{expiry},{cvv}"
                        for c in fully_used
                    ):
                        continue
                f.write(line + "\n")

    # Return the first available card
    if available_cards:
        return available_cards[0]
    else:
        return None


def get_next_card():
    def db_action():
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )
        try:
            cursor = conn.cursor(dictionary=True)

            all_cards = get_creditcard_details()

            # Load usage log from DB for preferred country only
            cursor.execute(
                "SELECT card_num, `exp_month/year`, cvv, use_datetime FROM familybot_card_usage_log WHERE LOWER(country) = %s",
                (PREFERRED_SMS_COUNTRY,),
            )
            usage_rows = cursor.fetchall()
            usage = {}
            for row in usage_rows:
                key = (str(row["card_num"]), row["exp_month/year"], str(row["cvv"]))
                if key not in usage:
                    usage[key] = []
                usage[key].append(row["use_datetime"])

            # Now, for each card, check if can use
            available_cards = []
            fully_used = []

            for card in all_cards:
                card_num = card["card_number"]
                expiry = f"{card['expiry_month']}/{card['expiry_year'][2:]}"  # MM/YY
                cvv = card["cvv"]
                key = (card_num, expiry, cvv)
                timestamps = sorted(usage.get(key, []))
                uses = len(timestamps)
                now = datetime.now()
                can_use = False
                if uses >= 5:
                    fully_used.append(card)
                    continue
                elif uses in [0, 1, 3]:
                    can_use = True
                elif uses == 2:
                    if timestamps and now > timestamps[-1] + timedelta(
                        hours=CREDIT_CARD_INTERVAL_HRS
                    ):
                        can_use = True
                elif uses == 4:
                    if timestamps and now > timestamps[-1] + timedelta(
                        hours=CREDIT_CARD_INTERVAL_HRS
                    ):
                        can_use = True
                if can_use:
                    available_cards.append(card)

            # For fully used, insert into familybot_fully_used_cards and delete from familybot_card_details
            for card in fully_used:
                expiry = f"{card['expiry_month']}/{card['expiry_year'][2:]}"
                cursor.execute(
                    "INSERT INTO familybot_fully_used_cards (server_ip, bot_type,date_time, card_number, expiry_month_year, cvv, country, name_on_card, address_line1, city, postal_code, state) VALUES (%s, %s,%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        SERVER_IP,
                        BOT_TYPE,
                        datetime.now(),
                        card["card_number"],
                        expiry,
                        card["cvv"],
                        card.get("country", PREFERRED_SMS_COUNTRY),
                        card["name_on_card"],
                        card["address_line1"],
                        card["city"],
                        card["postal_code"],
                        card["state"],
                    ),
                )
                cursor.execute(
                    "DELETE FROM familybot_card_details WHERE card_number = %s AND expiry_month_year = %s AND cvv = %s",
                    (card["card_number"], expiry, card["cvv"]),
                )

            # Return the first available card, move to processing_card_details
            if available_cards:
                card = available_cards[0]
                expiry = f"{card['expiry_month']}/{card['expiry_year'][2:]}"
                cursor.execute(
                    "INSERT INTO processing_card_details (server_ip, bot_type,date_time,name_on_card, card_number, expiry_month_year, cvv,country, address_line1, city, state, postal_code) VALUES (%s, %s, %s,%s, %s,%s,%s, %s, %s, %s, %s, %s)",
                    (
                        SERVER_IP,
                        BOT_TYPE,
                        datetime.now(),
                        card["name_on_card"],
                        card["card_number"],
                        expiry,
                        card["cvv"],
                        card.get("country", PREFERRED_SMS_COUNTRY),
                        card["address_line1"],
                        card["city"],
                        card["state"],
                        card["postal_code"],
                    ),
                )
                cursor.execute(
                    "DELETE FROM familybot_card_details WHERE card_number = %s AND expiry_month_year = %s AND cvv = %s",
                    (card["card_number"], expiry, card["cvv"]),
                )
                conn.commit()
                return card
            else:
                return None
        finally:
            conn.close()

    try:
        return execute_db_action(db_action)
    except Exception as e:
        print(f"Error in get_next_card: {e}")
        return None


def click_signin_on_adding_card(driver):
    try:
        SIGNIN_ELEMENT = (
            By.TAG_NAME,
            "h2",
        )

        signin_elements = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_all_elements_located(SIGNIN_ELEMENT)
        )

        if "for added security, please sign in to continue with your purchase." in [
            i.text.lower() for i in signin_elements
        ]:
            time.sleep(1)
            SIGNIN_BTN_ELEMENT = (
                By.CSS_SELECTOR,
                'button[type="button"]',
            )

            signin_btn_elements = WebDriverWait(driver, wait_time).until(
                EC.presence_of_all_elements_located(SIGNIN_BTN_ELEMENT)
            )

            for btn in signin_btn_elements:
                if btn.text.lower().strip() == "sign in":
                    btn.click()
                    time.sleep(1)

                    return True
        return False
    except:
        return False


def credit_card_is_declined(driver):
    try:
        SIGNIN_ELEMENT = (
            By.CSS_SELECTOR,
            'span[data-automation-id="error-message"]',
        )

        error_element = WebDriverWait(driver, wait_time * 2).until(
            EC.visibility_of_all_elements_located(SIGNIN_ELEMENT)
        )

        return True if [i for i in error_element if i.text != ""] else False
    except:
        try:
            EXPIRY_ELEMENT = (
                By.CSS_SELECTOR,
                'div[id*="error-expiryGroup"][aria-hidden="false"]',
            )

            error_element = WebDriverWait(driver, wait_time / 2).until(
                EC.visibility_of_all_elements_located(EXPIRY_ELEMENT)
            )

            return True if [i for i in error_element] else False

        except:
            return False


def affirm_card_is_added(driver, cardholder_name):
    try:
        AFFIRM_ELEMENT = (
            By.CSS_SELECTOR,
            'div[id="input_id"]',
        )

        affirm_element = WebDriverWait(driver, wait_time * 15).until(
            EC.visibility_of_element_located(AFFIRM_ELEMENT)
        )

        # card_details_dict.get("name_on_card")

        return cardholder_name.lower() in affirm_element.text.lower()

    except:
        return False


def affirm_congrats_card_added(driver):
    try:
        time_in_sec = 160
        while time_in_sec > 0:
            try:
                AFFIRM_CONGRATS_ELEMENT = (
                    By.CSS_SELECTOR,
                    'h1[class^="postTransactionTitle"]',
                )

                affirm_congrats_element = WebDriverWait(driver, 1).until(
                    EC.visibility_of_element_located(AFFIRM_CONGRATS_ELEMENT)
                )

                if "welcome to microsoft 365" in affirm_congrats_element.text.lower():
                    time.sleep(2)
                    return True

            except:
                pass

            time.sleep(1)
            time_in_sec -= 1

        return False

    except:
        return False


def store_extracted_link(new_profile_data, link, card_details_dict):
    try:
        email = new_profile_data.get("email")
        recovery_email = new_profile_data.get("recovery_email")
        password = new_profile_data.get("pass")
        # with open("output_data/extracted_family_links_with_email.txt", "a") as f:
        #     f.write(f"{email}:{password}:{recovery_email}:{link}\n")

        # with open("output_data/extracted_family_links_pure.txt", "a") as f:
        #     f.write(f"{link}\n")

        def db_action():
            conn = None
            try:
                conn = mysql.connector.connect(
                    host=DB_HOST,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                )
                cursor = conn.cursor()
                insert_values = (
                    SERVER_IP,
                    BOT_TYPE,
                    datetime.now(),
                    email,
                    password,
                    recovery_email,
                    link,
                    PREFERRED_SMS_COUNTRY,
                )

                insert_values_history = (
                    SERVER_IP,
                    BOT_TYPE,
                    datetime.now(),
                    email,
                    password,
                    recovery_email,
                    link,
                    PREFERRED_SMS_COUNTRY,
                    card_details_dict.get("card_number", ""),
                )

                cursor.execute(
                    "INSERT INTO familybot_extracted_family_links (server_ip, bot_type, date_time, email, pass, recovery, link, country) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    insert_values,
                )
                cursor.execute(
                    "INSERT INTO familybot_extracted_family_links_history (server_ip, bot_type, date_time, email, pass, recovery, link, country, card_number) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    insert_values_history,
                )
                conn.commit()
            finally:
                if conn is not None:
                    conn.close()

        try:
            execute_db_action(db_action)
        except Exception as db_e:
            print(
                f"Error inserting extracted link into DB for {email}. Link: {link}\nDB Error: {db_e}"
            )
    except Exception as E:
        print(f"Error storing extracted link for {email}. Link: {link}\nError: {E}")


def add_billing(driver, new_profile_data, card_details_dict):
    try:
        ADDRESS_LINE1_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="address_line1"]',
        )
        CITY_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="city"]',
        )
        STATE_CLICK_ELEMENT = (
            By.CSS_SELECTOR,
            'div[id="input_region"]',
        )

        STATE_OPTIONS_ELEMENT = (
            By.CSS_SELECTOR,
            'button[id*="input_region-list"]',
        )

        POSTAL_CODE_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="postal_code"]',
        )

        SAVE_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'button[aria-label="Save"]',
        )

        ADD_BILLING_ADDRESS_BTN = (
            By.CSS_SELECTOR,
            'button[aria-label="Add billing address"]',
        )

        billing_address = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(ADD_BILLING_ADDRESS_BTN)
        )

        if "add billing address" in billing_address.text.lower():
            print("Billing address Required. Filling details...")
            billing_address.click()
            time.sleep(1)
        else:
            return True

        email_address = new_profile_data.get("email")

        current_status = "entering address line 1"

        address_line1_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(ADDRESS_LINE1_ELEMENT)
        )
        address_line1_element.clear()
        time.sleep(0.5)
        address_line1_element.send_keys(card_details_dict.get("address_line1"))
        print(
            f"{email_address} : Entered address line 1: {card_details_dict.get('address_line1')}"
        )
        time.sleep(0.5)
        current_status = "entering city"

        city_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(CITY_ELEMENT)
        )
        city_element.clear()
        time.sleep(0.5)
        city_element.send_keys(card_details_dict.get("city"))
        print(f"{email_address} : Entered city: {card_details_dict.get('city')}")
        time.sleep(0.5)

        if PREFERRED_SMS_COUNTRY.lower() == "united states":
            current_status = "entering state"

            state_element = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(STATE_CLICK_ELEMENT)
            )

            time.sleep(3)
            state_element.click()
            time.sleep(0.5)

            state_options_element = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_all_elements_located(STATE_OPTIONS_ELEMENT)
            )

            city_element = [
                i
                for i in state_options_element
                if i.text.lower() == card_details_dict.get("state", "").lower()
            ][0]

            # scroll into view
            driver.execute_script(
                "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                city_element,
            )
            time.sleep(1)
            city_element.click()

            print(f"{email_address} : Entered state: {card_details_dict.get('state')}")
            time.sleep(0.5)

        current_status = "entering postal code"
        postal_code_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(POSTAL_CODE_ELEMENT)
        )
        postal_code_element.clear()
        time.sleep(0.5)
        postal_code_element.send_keys(card_details_dict.get("postal_code"))
        print(
            f"{email_address} : Entered postal code: {card_details_dict.get('postal_code')}"
        )
        time.sleep(0.5)
        current_status = "clicking save button"
        save_button_element = WebDriverWait(driver, wait_time).until(
            EC.element_to_be_clickable(SAVE_BUTTON_ELEMENT)
        )
        save_button_element.click()
        print(f"{email_address} : Clicked save button")
        return True
    except:
        return True


def get_microsoft_premium(driver, new_profile_data):
    try:
        email_address = new_profile_data.get("email")
        # password = new_profile_data.get("pass")
        # recovery_email = new_profile_data.get("recovery_email")

        current_status = "getting card details"
        try:
            card_details_dict = get_processing_card()
            # get_next_card()
            if not card_details_dict:
                print(
                    f"{email_address} : No available cards to use. Check logs/card_usage.log and output_data/fully_used_cards.txt for more info."
                )
                return False, "No available cards to use"
        except Exception as E:
            print(f"{email_address} : Error getting next card: {E}")
            return False, current_status

        driver.get("https://account.microsoft.com/services/")
        time.sleep(1)

        current_status = "clicking premium element"
        PREMIUM_ELEMENT = (
            By.CSS_SELECTOR,
            'button[data-bi-id="Office_Upsells_Try"]',
        )

        premium_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(PREMIUM_ELEMENT)
        )
        premium_element.click()

        time.sleep(1)
        current_status = "selecting premium subscription"
        PREMIUM_SUBSCRIPTIONS_TYPES_ELEMENTS = (
            By.CSS_SELECTOR,
            'div[class^="buttonsWrapper"] > button',
        )
        premium_subscriptions_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_all_elements_located(PREMIUM_SUBSCRIPTIONS_TYPES_ELEMENTS)
        )[1]
        premium_subscriptions_element.click()
        current_status = "clicking signin on adding card"
        click_signin_on_adding_card(driver)

        # click checkbox
        current_status = "clicking checkbox"
        time.sleep(1)
        CHECKBOX_ELEMENT = (
            By.CSS_SELECTOR,
            'i[data-icon-name="CheckMark"]',
        )
        checkbox_element = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located(CHECKBOX_ELEMENT)
        )
        time.sleep(2)
        checkbox_element.click()

        time.sleep(1)
        # click next btn
        current_status = "clicking next button after checkbox"
        NEXT_BTN_ELEMENT = (
            By.CSS_SELECTOR,
            'button[aria-label="Next"]',
        )
        next_btn_element = WebDriverWait(driver, wait_time).until(
            EC.element_to_be_clickable(NEXT_BTN_ELEMENT)
        )
        next_btn_element.click()
        time.sleep(1)

        # click card btn
        current_status = "clicking card button"

        CARD_BTN_ELEMENT = (
            By.CSS_SELECTOR,
            'button[aria-label="Debit card or credit card"]',
        )
        try:
            card_btn_element = WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable(CARD_BTN_ELEMENT)
            )
        except:
            CARD_BTN_ELEMENT = (
                By.CSS_SELECTOR,
                'button[aria-label="Credit card or debit card"]',
            )
            card_btn_element = WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable(CARD_BTN_ELEMENT)
            )

        card_btn_element.click()
        time.sleep(1)

        # INPUT ELEMENTS FOR CARD DETAILS
        current_status = "entering card details"
        CREDIT_CARD_NUMBER_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="accountToken"]',
        )
        NAME_ON_CARD_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="accountHolderName"]',
        )

        EXPIRY_MONTH_ELEMENT = (
            By.CSS_SELECTOR,
            'span[id="input_expiryMonth-option"]',
        )

        EXPIRY_YEAR_ELEMENT = (
            By.CSS_SELECTOR,
            'span[id="input_expiryYear-option"]',
        )
        CVV_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="cvvToken"]',
        )

        ADDRESS_LINE1_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="address_line1"]',
        )
        CITY_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="city"]',
        )
        STATE_CLICK_ELEMENT = (
            By.CSS_SELECTOR,
            'div[id="input_region"]',
        )

        STATE_OPTIONS_ELEMENT = (
            By.CSS_SELECTOR,
            'button[id*="input_region-list"]',
        )

        POSTAL_CODE_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="postal_code"]',
        )

        SAVE_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'button[aria-label="Save"]',
        )

        SCROLL_DOWN_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'button[aria-label="Scroll Down"]',
        )

        START_TRIAL_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'button[aria-label="Start trial, pay later"]',
        )
        # ENTERING CARD DETAILS
        current_status = "entering card number"
        card_number_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(CREDIT_CARD_NUMBER_ELEMENT)
        )
        card_number_element.clear()
        time.sleep(0.5)
        card_number_element.send_keys(
            card_details_dict.get("card_number").replace(" ", "")
        )
        print(
            f"{email_address} : Entered card number: {card_details_dict.get('card_number')}"
        )

        time.sleep(0.5)
        current_status = "entering name on card"
        name_on_card_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(NAME_ON_CARD_ELEMENT)
        )
        name_on_card_element.clear()
        time.sleep(1)
        name_on_card_element.send_keys(card_details_dict.get("name_on_card"))
        print(
            f"{email_address} : Entered name on card: {card_details_dict.get('name_on_card')}"
        )

        time.sleep(1)

        # use keyboard to press tab and enter

        print(
            f"{email_address} : Selecting expiry month: {card_details_dict.get('expiry_month')}"
        )

        # expiry_month_element = WebDriverWait(driver, wait_time).until(
        #     EC.visibility_of_element_located(EXPIRY_MONTH_ELEMENT)
        # )
        # # scroll into view
        # driver.execute_script(
        #     "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
        #     expiry_month_element,
        # )
        # time.sleep(0.5)
        # expiry_month_element.click()
        action = ActionChains(driver)
        action.send_keys(Keys.TAB).perform()
        action.send_keys(Keys.ENTER).perform()
        time.sleep(1.3)

        # button[data-index=f"{int(card_details_dict.get('expiry_month'))-1}"] element
        current_status = "selecting expiry month"
        print(f"{email_address} : Selecting expiry month option")
        expiry_month_option_element = WebDriverWait(driver, wait_time).until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    f"""button[data-index="{int(card_details_dict.get("expiry_month")) - 1}"]""",
                )
            )
        )
        expiry_month_option_element.click()
        print(
            f"{email_address} : Selected expiry month: {card_details_dict.get('expiry_month')}"
        )

        time.sleep(1)
        current_status = "selecting expiry year"
        # expiry_year_element = WebDriverWait(driver, wait_time).until(
        #     EC.visibility_of_element_located(EXPIRY_YEAR_ELEMENT)
        # )
        # # scroll into view
        # driver.execute_script(
        #     "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
        #     expiry_year_element,
        # )
        # time.sleep(0.5)
        # expiry_year_element.click()
        action = ActionChains(driver)
        action.send_keys(Keys.TAB).perform()
        action.send_keys(Keys.ENTER).perform()
        time.sleep(1)
        expiry_year_option_element = WebDriverWait(driver, wait_time).until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    f"""button[data-index="{int(card_details_dict.get("expiry_year")) - 2026}"]""",
                )
            )
        )
        expiry_year_option_element.click()
        print(
            f"{email_address} : Selected expiry year: {card_details_dict.get('expiry_year')}"
        )
        time.sleep(0.5)
        current_status = "entering cvv"
        cvv_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(CVV_ELEMENT)
        )
        cvv_element.clear()
        time.sleep(0.5)
        cvv_element.send_keys(card_details_dict.get("cvv"))
        print(f"{email_address} : Entered CVV: {card_details_dict.get('cvv')}")
        time.sleep(1)

        current_status = "entering address line 1"
        address_line1_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(ADDRESS_LINE1_ELEMENT)
        )
        address_line1_element.clear()
        time.sleep(0.5)
        address_line1_element.send_keys(card_details_dict.get("address_line1"))
        print(
            f"{email_address} : Entered address line 1: {card_details_dict.get('address_line1')}"
        )
        time.sleep(0.5)
        current_status = "entering city"

        city_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(CITY_ELEMENT)
        )
        city_element.clear()
        time.sleep(0.5)
        city_element.send_keys(card_details_dict.get("city"))
        print(f"{email_address} : Entered city: {card_details_dict.get('city')}")
        time.sleep(0.5)

        if PREFERRED_SMS_COUNTRY.lower() == "united states":
            current_status = "entering state"

            state_element = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(STATE_CLICK_ELEMENT)
            )

            time.sleep(3)
            state_element.click()
            time.sleep(0.5)

            state_options_element = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_all_elements_located(STATE_OPTIONS_ELEMENT)
            )

            city_element = [
                i
                for i in state_options_element
                if i.text.lower() == card_details_dict.get("state", "").lower()
            ][0]

            # scroll into view
            driver.execute_script(
                "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                city_element,
            )
            time.sleep(1)
            city_element.click()

            print(f"{email_address} : Entered state: {card_details_dict.get('state')}")
            time.sleep(0.5)

        current_status = "entering postal code"
        postal_code_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(POSTAL_CODE_ELEMENT)
        )
        postal_code_element.clear()
        time.sleep(0.5)
        postal_code_element.send_keys(card_details_dict.get("postal_code"))
        print(
            f"{email_address} : Entered postal code: {card_details_dict.get('postal_code')}"
        )
        time.sleep(0.5)
        current_status = "clicking save button"
        save_button_element = WebDriverWait(driver, wait_time).until(
            EC.element_to_be_clickable(SAVE_BUTTON_ELEMENT)
        )
        save_button_element.click()
        print(f"{email_address} : Clicked save button")

        current_status = "checking if card is declined"
        if credit_card_is_declined(driver):
            print(f"{email_address} : Card was declined")
            # log_card_usage(card_details_dict)
            mark_card_failed(card_details_dict)

            return False, "Card was declined"
        else:
            print(f"{email_address} : Card accepted.")

        current_status = "checking if card is added to payments"
        if affirm_card_is_added(driver, card_details_dict.get("name_on_card")):
            print(f"{email_address} : Affirm Card added to payments successfully.")
        else:
            print(f"{email_address} : Card not added to payments.")
            return False, "Card not added to payments"

        current_status = "Add billing address if prompted"
        add_billing(driver, new_profile_data, card_details_dict)

        time.sleep(2)
        try:
            current_status = "clicking scroll down button"
            scroll_button_element = WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable(SCROLL_DOWN_BUTTON_ELEMENT)
            )

            scroll_button_element.click()
            print(f"{email_address} : Clicked scroll down button")
        except:
            pass

        current_status = "clicking start trial button"
        try:
            time.sleep(4)
            print(f"{email_address} : Clicking start trial button")

            start_trial_button_element = WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable(START_TRIAL_BUTTON_ELEMENT)
            )
            time.sleep(0.5)
            start_trial_button_element = WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable(START_TRIAL_BUTTON_ELEMENT)
            )
            start_trial_button_element.click()
            print(f"{email_address} : Clicked start trial button")
        except:
            pass

        current_status = "checking if card is authorized"
        print(f"{email_address} : Waiting 5 minutes for card authorization...")
        if not affirm_congrats_card_added(driver):
            print(f"{email_address} : Card not authorized")
            return False, "card not authorized"
        else:
            log_card_usage(card_details_dict)

        time.sleep(2)

        try:
            current_status = "clicking start sharing button"
            START_SHARING_ELEMENT = (
                By.CSS_SELECTOR,
                'button[type="button"]',
            )
            name_on_card_elements = WebDriverWait(driver, wait_time).until(
                EC.presence_of_all_elements_located(START_SHARING_ELEMENT)
            )

            [i for i in name_on_card_elements if i.text.lower() == "start sharing"][
                0
            ].click()
            print(f"{email_address} : Clicked start sharing button")
        except:
            print(f"{email_address} : Start sharing button not found")
            return False, "error clicking start sharing button"

        time.sleep(2)
        try:
            current_status = "clicking share button"
            SHARE_ELEMENT = (
                By.CSS_SELECTOR,
                'button[aria-label="Share subscription"]',
            )

            COPY_BUTTON_ELEMENT = (
                By.CSS_SELECTOR,
                'button[aria-label="Copy link"]',
            )

            LINK_INPUT_ELEMENT = (
                By.CSS_SELECTOR,
                'input[aria-label="Sharing link"]',
            )

            share_btn_element = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(SHARE_ELEMENT)
            )
            # scroll into center view
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", share_btn_element
            )
            time.sleep(1)

            share_btn_element.click()
            print(f"{email_address} : Clicked share button")
            time.sleep(2)
            current_status = "clicking copy link button"
            copy_btn_element = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(COPY_BUTTON_ELEMENT)
            )
            copy_btn_element.click()
            print(f"{email_address} : Clicked copy link button")

            time.sleep(5)
            current_status = "retrieving sharing link"
            link_input_element = WebDriverWait(driver, wait_time + 40).until(
                EC.visibility_of_element_located(LINK_INPUT_ELEMENT)
            )
            link = link_input_element.get_attribute("value")
            print(f"{email_address} : Retrieved sharing link: {link}")
            store_extracted_link(new_profile_data, link, card_details_dict)
            time.sleep(4)

            print(f"{email_address} : Stored extracted link successfully")
            return True, "Success"
        except Exception as E:
            print(f"{email_address} : Error copying sharing link: {E}")
            return False, "Error copying sharing link"

    except Exception as E:
        print(
            f"{email_address} : Exception error occurred at step: {current_status}:\nError: {E} "
        )
        # create screenshot directory if not exists
        try:
            os.makedirs("../utils/screenshots", exist_ok=True)
            driver.save_screenshot(
                f"../utils/screenshots/{email_address.split('@')[0]}_{current_status}_error.png".replace(
                    " ", "_"
                )
                .replace(":", "")
                .replace("@", "")
            )
        except:
            pass
        return False, f"Error occurred: {E} at step: {current_status}"
    finally:
        try:
            if current_status != "checking if card is declined":
                return_card_to_familybot_card_details(card_details_dict)
        except Exception as E:
            print(f"Error returning card to familybot_card_details: {E}")


def get_microsoft_premium_old_(driver, new_profile_data):
    try:
        email_address = new_profile_data.get("email")
        # password = new_profile_data.get("pass")
        # recovery_email = new_profile_data.get("recovery_email")

        current_status = "getting card details"
        try:
            card_details_dict = get_processing_card()
            # get_next_card()
            if not card_details_dict:
                print(
                    f"{email_address} : No available cards to use. Check logs/card_usage.log and output_data/fully_used_cards.txt for more info."
                )
                return False, "No available cards to use"
        except Exception as E:
            print(f"{email_address} : Error getting next card: {E}")
            return False, current_status

        driver.get("https://account.microsoft.com/services/")
        time.sleep(1)

        current_status = "clicking premium element"
        PREMIUM_ELEMENT = (
            By.CSS_SELECTOR,
            'button[data-bi-id="Office_Upsells_Try"]',
        )

        premium_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(PREMIUM_ELEMENT)
        )
        premium_element.click()

        time.sleep(1)
        current_status = "selecting premium subscription"
        PREMIUM_SUBSCRIPTIONS_TYPES_ELEMENTS = (
            By.CSS_SELECTOR,
            'div[class^="buttonsWrapper"] > button',
        )
        premium_subscriptions_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_all_elements_located(PREMIUM_SUBSCRIPTIONS_TYPES_ELEMENTS)
        )[1]
        premium_subscriptions_element.click()
        current_status = "clicking signin on adding card"
        click_signin_on_adding_card(driver)

        # click checkbox
        current_status = "clicking checkbox"
        time.sleep(1)
        CHECKBOX_ELEMENT = (
            By.CSS_SELECTOR,
            'i[data-icon-name="CheckMark"]',
        )
        checkbox_element = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located(CHECKBOX_ELEMENT)
        )
        time.sleep(2)
        checkbox_element.click()

        time.sleep(1)
        # click next btn
        current_status = "clicking next button after checkbox"
        NEXT_BTN_ELEMENT = (
            By.CSS_SELECTOR,
            'button[aria-label="Next"]',
        )
        next_btn_element = WebDriverWait(driver, wait_time).until(
            EC.element_to_be_clickable(NEXT_BTN_ELEMENT)
        )
        next_btn_element.click()
        time.sleep(1)

        # click card btn
        current_status = "clicking card button"

        CARD_BTN_ELEMENT = (
            By.CSS_SELECTOR,
            'button[aria-label="Debit card or credit card"]',
        )
        try:
            card_btn_element = WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable(CARD_BTN_ELEMENT)
            )
        except:
            CARD_BTN_ELEMENT = (
                By.CSS_SELECTOR,
                'button[aria-label="Credit card or debit card"]',
            )
            card_btn_element = WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable(CARD_BTN_ELEMENT)
            )

        card_btn_element.click()
        time.sleep(1)

        # INPUT ELEMENTS FOR CARD DETAILS
        current_status = "entering card details"
        CREDIT_CARD_NUMBER_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="accountToken"]',
        )
        NAME_ON_CARD_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="accountHolderName"]',
        )

        EXPIRY_MONTH_ELEMENT = (
            By.CSS_SELECTOR,
            'span[id="input_expiryMonth-option"]',
        )

        EXPIRY_YEAR_ELEMENT = (
            By.CSS_SELECTOR,
            'span[id="input_expiryYear-option"]',
        )
        CVV_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="cvvToken"]',
        )

        ADDRESS_LINE1_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="address_line1"]',
        )
        CITY_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="city"]',
        )
        POSTAL_CODE_ELEMENT = (
            By.CSS_SELECTOR,
            'input[id="postal_code"]',
        )

        SAVE_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'button[aria-label="Save"]',
        )

        SCROLL_DOWN_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'button[aria-label="Scroll Down"]',
        )

        START_TRIAL_BUTTON_ELEMENT = (
            By.CSS_SELECTOR,
            'button[aria-label="Start trial, pay later"]',
        )
        # ENTERING CARD DETAILS
        current_status = "entering card number"
        card_number_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(CREDIT_CARD_NUMBER_ELEMENT)
        )
        card_number_element.clear()
        time.sleep(0.5)
        card_number_element.send_keys(
            card_details_dict.get("card_number").replace(" ", "")
        )
        print(
            f"{email_address} : Entered card number: {card_details_dict.get('card_number')}"
        )

        time.sleep(0.5)
        current_status = "entering name on card"
        name_on_card_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(NAME_ON_CARD_ELEMENT)
        )
        name_on_card_element.clear()
        time.sleep(1)
        name_on_card_element.send_keys(card_details_dict.get("name_on_card"))
        print(
            f"{email_address} : Entered name on card: {card_details_dict.get('name_on_card')}"
        )

        time.sleep(1)

        # use keyboard to press tab and enter

        print(
            f"{email_address} : Selecting expiry month: {card_details_dict.get('expiry_month')}"
        )

        # expiry_month_element = WebDriverWait(driver, wait_time).until(
        #     EC.visibility_of_element_located(EXPIRY_MONTH_ELEMENT)
        # )
        # # scroll into view
        # driver.execute_script(
        #     "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
        #     expiry_month_element,
        # )
        # time.sleep(0.5)
        # expiry_month_element.click()
        action = ActionChains(driver)
        action.send_keys(Keys.TAB).perform()
        action.send_keys(Keys.ENTER).perform()
        time.sleep(1.3)

        # button[data-index=f"{int(card_details_dict.get('expiry_month'))-1}"] element
        current_status = "selecting expiry month"
        print(f"{email_address} : Selecting expiry month option")
        expiry_month_option_element = WebDriverWait(driver, wait_time).until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    f"""button[data-index="{int(card_details_dict.get("expiry_month")) - 1}"]""",
                )
            )
        )
        expiry_month_option_element.click()
        print(
            f"{email_address} : Selected expiry month: {card_details_dict.get('expiry_month')}"
        )

        time.sleep(1)
        current_status = "selecting expiry year"
        # expiry_year_element = WebDriverWait(driver, wait_time).until(
        #     EC.visibility_of_element_located(EXPIRY_YEAR_ELEMENT)
        # )
        # # scroll into view
        # driver.execute_script(
        #     "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
        #     expiry_year_element,
        # )
        # time.sleep(0.5)
        # expiry_year_element.click()
        action = ActionChains(driver)
        action.send_keys(Keys.TAB).perform()
        action.send_keys(Keys.ENTER).perform()
        time.sleep(1)
        expiry_year_option_element = WebDriverWait(driver, wait_time).until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    f"""button[data-index="{int(card_details_dict.get("expiry_year")) - 2026}"]""",
                )
            )
        )
        expiry_year_option_element.click()
        print(
            f"{email_address} : Selected expiry year: {card_details_dict.get('expiry_year')}"
        )
        time.sleep(0.5)
        current_status = "entering cvv"
        cvv_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(CVV_ELEMENT)
        )
        cvv_element.clear()
        time.sleep(0.5)
        cvv_element.send_keys(card_details_dict.get("cvv"))
        print(f"{email_address} : Entered CVV: {card_details_dict.get('cvv')}")
        time.sleep(1)

        current_status = "entering address line 1"
        address_line1_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(ADDRESS_LINE1_ELEMENT)
        )
        address_line1_element.clear()
        time.sleep(0.5)
        address_line1_element.send_keys(card_details_dict.get("address_line1"))
        print(
            f"{email_address} : Entered address line 1: {card_details_dict.get('address_line1')}"
        )
        time.sleep(0.5)
        current_status = "entering city"

        city_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(CITY_ELEMENT)
        )
        city_element.clear()
        time.sleep(0.5)
        city_element.send_keys(card_details_dict.get("city"))
        print(f"{email_address} : Entered city: {card_details_dict.get('city')}")
        time.sleep(0.5)
        current_status = "entering postal code"
        postal_code_element = WebDriverWait(driver, wait_time).until(
            EC.visibility_of_element_located(POSTAL_CODE_ELEMENT)
        )
        postal_code_element.clear()
        time.sleep(0.5)
        postal_code_element.send_keys(card_details_dict.get("postal_code"))
        print(
            f"{email_address} : Entered postal code: {card_details_dict.get('postal_code')}"
        )
        time.sleep(0.5)
        current_status = "clicking save button"
        save_button_element = WebDriverWait(driver, wait_time).until(
            EC.element_to_be_clickable(SAVE_BUTTON_ELEMENT)
        )
        save_button_element.click()
        print(f"{email_address} : Clicked save button")

        current_status = "checking if card is declined"
        if credit_card_is_declined(driver):
            print(f"{email_address} : Card was declined")
            # log_card_usage(card_details_dict)
            mark_card_failed(card_details_dict)

            return False, "Card was declined"
        else:
            print(f"{email_address} : Card accepted.")

        current_status = "checking if card is added to payments"
        if affirm_card_is_added(driver, card_details_dict.get("name_on_card")):
            print(f"{email_address} : Affirm Card added to payments successfully.")
        else:
            print(f"{email_address} : Card not added to payments.")
            return False, "Card not added to payments"

        time.sleep(2)
        current_status = "clicking scroll down button"
        scroll_button_element = WebDriverWait(driver, wait_time).until(
            EC.element_to_be_clickable(SCROLL_DOWN_BUTTON_ELEMENT)
        )
        scroll_button_element.click()
        print(f"{email_address} : Clicked scroll down button")

        current_status = "clicking start trial button"
        try:
            time.sleep(4)
            print(f"{email_address} : Clicking start trial button")

            start_trial_button_element = WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable(START_TRIAL_BUTTON_ELEMENT)
            )
            time.sleep(0.5)
            start_trial_button_element = WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable(START_TRIAL_BUTTON_ELEMENT)
            )
            start_trial_button_element.click()
            print(f"{email_address} : Clicked start trial button")
        except:
            pass

        current_status = "checking if card is authorized"
        print(f"{email_address} : Waiting 5 minutes for card authorization...")
        if not affirm_congrats_card_added(driver):
            print(f"{email_address} : Card not authorized")
            return False, "card not authorized"
        else:
            log_card_usage(card_details_dict)

        time.sleep(2)

        try:
            current_status = "clicking start sharing button"
            START_SHARING_ELEMENT = (
                By.CSS_SELECTOR,
                'button[type="button"]',
            )
            name_on_card_elements = WebDriverWait(driver, wait_time).until(
                EC.presence_of_all_elements_located(START_SHARING_ELEMENT)
            )

            [i for i in name_on_card_elements if i.text.lower() == "start sharing"][
                0
            ].click()
            print(f"{email_address} : Clicked start sharing button")
        except:
            print(f"{email_address} : Start sharing button not found")
            return False, "error clicking start sharing button"

        time.sleep(2)
        try:
            current_status = "clicking share button"
            SHARE_ELEMENT = (
                By.CSS_SELECTOR,
                'button[aria-label="Share subscription"]',
            )

            COPY_BUTTON_ELEMENT = (
                By.CSS_SELECTOR,
                'button[aria-label="Copy link"]',
            )

            LINK_INPUT_ELEMENT = (
                By.CSS_SELECTOR,
                'input[aria-label="Sharing link"]',
            )

            share_btn_element = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(SHARE_ELEMENT)
            )
            # scroll into center view
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", share_btn_element
            )
            time.sleep(1)

            share_btn_element.click()
            print(f"{email_address} : Clicked share button")
            time.sleep(2)
            current_status = "clicking copy link button"
            copy_btn_element = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(COPY_BUTTON_ELEMENT)
            )
            copy_btn_element.click()
            print(f"{email_address} : Clicked copy link button")

            time.sleep(5)
            current_status = "retrieving sharing link"
            link_input_element = WebDriverWait(driver, wait_time + 40).until(
                EC.visibility_of_element_located(LINK_INPUT_ELEMENT)
            )
            link = link_input_element.get_attribute("value")
            print(f"{email_address} : Retrieved sharing link: {link}")
            store_extracted_link(new_profile_data, link)
            time.sleep(4)

            print(f"{email_address} : Stored extracted link successfully")
            return True, "Success"
        except Exception as E:
            print(f"{email_address} : Error copying sharing link: {E}")
            return False, "Error copying sharing link"

    except Exception as E:
        print(
            f"{email_address} : Exception error occurred at step: {current_status}:\nError: {E} "
        )
        # create screenshot directory if not exists
        try:
            os.makedirs("utils/screenshots", exist_ok=True)
            driver.save_screenshot(
                f"utils/screenshots/{email_address.split('@')[0]}_{current_status}_error.png".replace(
                    " ", "_"
                )
                .replace(":", "")
                .replace("@", "")
            )
        except:
            pass
        return False, f"Error occurred: {E} at step: {current_status}"
    finally:
        try:
            return_card_to_familybot_card_details(card_details_dict)
        except Exception as E:
            print(f"Error returning card to familybot_card_details: {E}")


########### ENTURUUUUUURU ############
def get_new_profile_data():
    retries = 0
    while retries < 3:
        try:
            conn = mysql.connector.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
            )
            cursor = conn.cursor()

            # First, check if there's an existing record in processing_emails for this server and bot type
            cursor.execute(
                "SELECT email, pass FROM processing_emails WHERE server_ip = %s AND bot_type = %s LIMIT 1",
                (SERVER_IP, BOT_TYPE),
            )
            row = cursor.fetchone()
            if row:
                conn.close()
                email, password = row
                print(f"Found existing processing email: {email}")
                return True, {"email": email, "pass": password}

            # If no existing record, get a new one from input_emails
            cursor.execute("SELECT email, pass FROM input_emails LIMIT 1")
            row = cursor.fetchone()
            if not row:
                conn.close()
                return False, {}
            email, password = row
            cursor.execute(
                "INSERT INTO processing_emails (email, pass, server_ip, bot_type, date_time) VALUES (%s, %s,%s, %s, %s)",
                (email, password, SERVER_IP, BOT_TYPE, datetime.now()),
            )
            cursor.execute(
                "DELETE FROM input_emails WHERE email = %s AND pass = %s",
                (email, password),
            )
            conn.commit()
            conn.close()
            return True, {"email": email, "pass": password}
        except Exception as e:
            if conn is not None:
                conn.close()
            print(f"Error getting email from db: {e}. retrying...")
            retries += 1
            time.sleep(5)

    print("Unable to get input email after 3 retries. Most likely no emails")
    return False, {"email": "", "pass": ""}


def get_processing_card():
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM processing_card_details WHERE server_ip = %s AND bot_type = %s LIMIT 1",
        (SERVER_IP, BOT_TYPE),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        expiry = row["expiry_month_year"]
        expiry_month = expiry.split("/")[0]
        expiry_year = "20" + expiry.split("/")[1]

        return {
            "name_on_card": row.get("name_on_card"),
            "card_number": str(row["card_number"]),
            "expiry_month": str(expiry_month),
            "expiry_year": expiry_year,
            "cvv": str(row["cvv"]),
            "address_line1": row.get("address_line1"),
            "city": row.get("city"),
            "state": row.get("state"),
            "postal_code": row.get("postal_code"),
            "country": row.get("country", PREFERRED_SMS_COUNTRY),
        }
    return None


def get_all_processing_cards(country=None):
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM processing_card_details WHERE LOWER(country) = %s",
        (country.lower() if country else None,),
    )
    rows = cursor.fetchall()
    conn.close()
    cards = []

    for row in rows:
        expiry = row["expiry_month_year"]
        expiry_month = expiry.split("/")[0]
        expiry_year = "20" + expiry.split("/")[1]

        cards.append(
            {
                "name_on_card": row.get("name_on_card"),
                "card_number": str(row["card_number"]),
                "expiry_month": str(expiry_month),
                "expiry_year": expiry_year,
                "cvv": str(row["cvv"]),
                "address_line1": row.get("address_line1"),
                "city": row.get("city"),
                "state": row.get("state"),
                "postal_code": row.get("postal_code"),
                "country": row.get("country", PREFERRED_SMS_COUNTRY),
            }
        )

    return cards


def return_card_to_familybot_card_details(card_details):
    def db_action():
        conn = None
        try:
            conn = mysql.connector.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
            )
            cursor = conn.cursor()
            expiry = f"{card_details['expiry_month']}/{card_details['expiry_year'][2:]}"
            cursor.execute(
                "INSERT INTO familybot_card_details (card_number, expiry_month_year, cvv, country, name_on_card, address_line1, city, postal_code, state) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    card_details["card_number"],
                    expiry,
                    card_details["cvv"],
                    card_details.get("country", PREFERRED_SMS_COUNTRY),
                    card_details.get("name_on_card"),
                    card_details.get("address_line1"),
                    card_details.get("city"),
                    card_details.get("postal_code"),
                    card_details.get("state"),
                ),
            )
            cursor.execute(
                "DELETE FROM processing_card_details WHERE card_number = %s AND expiry_month_year = %s AND cvv = %s",
                (card_details["card_number"], expiry, card_details["cvv"]),
            )
            conn.commit()
        finally:
            if conn is not None:
                conn.close()

    execute_db_action(db_action)


def share_premium(new_profile_data):
    """ """
    try:
        print("\n--------------------------------------\n")

        connect_new_random()

        # sql = 'SELECT email_acc, password, recovery_email, date_time FROM oneapp.accounts_details where bot_type ="familybot" AND date_time > NOW() - INTERVAL 2 DAY AND country = "united states";'

        email_address = new_profile_data.get("email").strip()
        password = new_profile_data.get("pass").strip()
        recovery = new_profile_data.get("recovery").strip()

        MICROSOFT_PREMIUM_URL = (
            "https://account.microsoft.com/services/microsoft365/details"
        )

        retries = 0
        driver_success = False
        print(f"{email_address} : Initializing browser driver")
        while (retries < 3) and (not driver_success):
            try:
                status, driverdata, error = initialize_new_profile_driver()
                if status:
                    driver, user_path, proxy = driverdata.values()

                    time.sleep(0.5)
                    driver.maximize_window()
                    time.sleep(0.5)
                    driver.get(MICROSOFT_LOGIN_URL)
                    time.sleep(1)
                    driver_success = True
            except:
                driver.quit()
                retries += 1

        if not driver_success:
            print(f"{email_address} : Error initializing new browser driver")
            new_profile_logger(
                email_address,
                "FAIL",
                "Error initializing new browser driver. Network or proxy error",
            )
            return False, "Error initializing new browser driver instance"
        if not enter_email(driver=driver, email_address=email_address):
            print(f"{email_address} : Error entering email")
            new_profile_logger(email_address, "FAIL", "Error loading login page")
            return False, "Error loading login page"

        time.sleep(1)
        if not click_next_button(driver=driver):
            print(f"{email_address} : Error clicking next button after entering email")
            new_profile_logger(
                email_address, "FAIL", "Error clicking next button after entering email"
            )
            return False, "Error clicking next button after entering email"
        time.sleep(1)

        if not enter_recovery_email_2(driver=driver, recovery_email=recovery):
            print(f"{email_address} : Error entering recovery email")
            new_profile_logger(
                email_address,
                "FAIL",
                "Error entering recovery email",
            )
            return False, "Error entering recovery email"
        time.sleep(0.5)
        bring_to_front(driver)
        time.sleep(1)

        sss = click_password_next_button(driver)
        if not sss:
            os.makedirs("screenshots", exist_ok=True)
            driver.save_screenshot(f"screenshots/{email_address}_error.png")
            print(
                f"{email_address} : Error clicking next after entering recovery email"
            )
            new_profile_logger(
                email_address,
                "FAIL",
                "Error clicking next after entering recovery email",
            )
            return False, "Error clicking next after entering recovery email"

        status, code = wait_for_code_by_recovery_mail(recovery)
        time.sleep(3)
        if not status:
            print(f"{email_address} : Error getting code from tempmail")
            new_profile_logger(
                email_address,
                "FAIL",
                "Error getting code from tempmail. Timed out without receiving code",
            )
            return False, "Error getting code from tempmail. Timeout"
        else:
            print(f"{email_address} : Code received from tempmail: {code}")

        if not enter_code_and_click_next_after_pass_change(driver, code):
            print(f"{email_address} : Error entering email verification code")
            new_profile_logger(
                email_address,
                "FAIL",
                "Error entering email verification code",
            )
            return False, "Error entering email verification code"

        print(f"{email_address} : Finalizing signin")
        close_other_tabs(driver)
        click_stay_signed_in_button(driver)

        driver.get(MICROSOFT_PREMIUM_URL)
        time.sleep(1)
        # return driver
        if click_share_dropdown_button(driver):
            print(f"{email_address} : Clicked share dropdown button")

        if not click_start_sharing_button(driver):
            return False, "Error clicking start sharing button"

        print(f"{email_address} : Clicked start sharing button for all members")

        if not mark_share_as_done(email_address):
            return False, "Error updating share status in database"

        return True
    except Exception as E:
        print(f"{email_address} : Exception error occurred: {E}")
        return False, f"Error occurred: {E}"
    finally:
        try:
            driver.quit()
            pass
            # processed_email(new_profile_data)
        except:
            pass


def initialize_new_profile(new_profile_data):
    """
    Creating a new chrome profile.

    A dictionary with email_address, and password
    """
    try:
        print("\n--------------------------------------\n")
        try:
            while True:
                card_details_dict = get_processing_card()
                if card_details_dict:
                    return_card_to_familybot_card_details(card_details_dict)
                else:
                    break
            if not get_next_card():
                print(
                    "No available cards to use for Microsoft Premium. Check logs/card_usage.log and output_data/fully_used_cards.txt for more info."
                )
                os._exit(1)
                return False, "No available cards to use for Microsoft Premium"
        except Exception as E:
            print(f"Error checking available cards: {E}")
            os._exit(1)
            return False, "Error checking available cards for Microsoft Premium"
        connect_new_random()

        email_address = new_profile_data.get("email").strip()
        password = new_profile_data.get("pass").strip()

        new_profile_data_original = new_profile_data.copy()

        retries = 0
        driver_success = False
        print(f"{email_address} : Initializing browser driver")
        while (retries < 3) and (not driver_success):
            try:
                status, driverdata, error = initialize_new_profile_driver()
                if status:
                    driver, user_path, proxy = driverdata.values()

                    time.sleep(0.5)
                    driver.maximize_window()
                    time.sleep(0.5)
                    driver.get(MICROSOFT_LOGIN_URL)
                    time.sleep(1)
                    driver_success = True
            except:
                driver.quit()
                retries += 1

        if not driver_success:
            print(f"{email_address}: Error initializing new browser driver")
            new_profile_logger(
                email_address,
                "FAIL",
                "Error initializing new browser driver. Network or proxy error",
            )
            return False, "Error initializing new browser driver instance"
        if not enter_email(driver=driver, email_address=email_address):
            print(f"{email_address}: Error entering email")
            new_profile_logger(email_address, "FAIL", "Error loading login page")
            return False, "Error loading login page"

        time.sleep(1)
        if not click_next_button(driver=driver):
            print(f"{email_address}: Error clicking next button after entering email")
            new_profile_logger(
                email_address, "FAIL", "Error clicking next button after entering email"
            )
            return False, "Error clicking next button after entering email"
        time.sleep(1)

        if not enter_password(driver=driver, password=password):
            print(f"{email_address}: Error entering password")
            new_profile_logger(email_address, "FAIL", "Error Entering password")
            return False, "Error Entering password"
        time.sleep(1)

        if not click_password_next_button(driver=driver):
            print(
                f"{email_address}: Error clicking next button after entering password"
            )
            new_profile_logger(
                email_address,
                "FAIL",
                "Error clicking next button after entering password",
            )
            return False, "Error clicking next button after entering password"
        time.sleep(1)

        click_next_if_is_updating_terms_page(driver)

        recovery_email_page_popped_up = "NO"
        temp_email = ""

        has_recovery_phone = "NO"
        recovery_phone_number = ""
        if is_your_account_has_been_locked_page(driver):
            print(
                f"{email_address}: Your account has been locked page displayed. Using phone number from hero-sms-api"
            )
            time.sleep(1)

            click_next_button_locked_page(driver)
            time.sleep(1)

            phone_retries = 0
            phone_status = False
            while phone_retries < 5 and not phone_status:
                phone_status, activation_id, recovery_phone_number = (
                    get_number_for_verification()
                )
                phone_retries += 1

            if not phone_status:
                print(f"{email_address}: Unable to get phone number from hero-api")
                new_profile_logger(
                    email_address,
                    "FAIL",
                    "Unable to get phone number from hero-api",
                )
                return False, "Unable to get phone number from hero-api"

            else:
                print(
                    f"{email_address}: Using phone number from hero-api to unlock: {recovery_phone_number}"
                )

                has_recovery_phone = "YES"
                phone_number = recovery_phone_number
                bring_to_front(driver)
                enter_phone_number_and_click_next_microsoft(driver, phone_number)
                bring_to_front(driver)
                if funcaptcha_present(driver):
                    print(
                        f"{email_address}: Captcha detected. {CATCHA_WAIT_TIME} seconds to bypass"
                    )
                    wait_funcaptcha_bypass(driver)
                    time.sleep(1)
                    if bypassed_funcaptcha_to_code_page(driver):
                        print(
                            f"{email_address}: Bypassed captcha successfully! Waiting for OTP"
                        )
                    else:
                        print(f"{email_address}: Unable to bypass captcha")
                        new_profile_logger(
                            email_address,
                            "FAIL",
                            "Unable to bypass captcha or phone verification unavailable",
                        )
                        return False, "Unable to bypass captcha"
                else:
                    print(f"{email_address}: Captcha not present")
                    if is_try_another_verification_method(driver):
                        print(f"{email_address}: Unable to verify phone number.")
                        return (
                            False,
                            "Unable to verify phone number. Try another method",
                        )

                print(f"{email_address}: Waiting for sms verification code")

                code_status, code = get_code(activation_id=activation_id)
                if code_status:
                    print(f"{email_address}: Code received: {code}. Verifying...")
                    enter_sent_code(driver, code)
                    click_next_if_acc_unblocked(driver)
                    click_next_if_is_updating_terms_page(driver)
                    update_accounts_data(
                        date_time=datetime.now(),
                        email=email_address,
                        profile_dir=user_path,
                        proxy_used=proxy,
                        password=password,
                        has_recovery_email=recovery_email_page_popped_up,
                        recovery_email=temp_email,
                        has_recovery_phone=has_recovery_phone,
                        recovery_phone_number=recovery_phone_number,
                        joined_microsoft_premium="NO",
                    )
                    print(f"{email_address}: Successfully verified mobile number")
                else:
                    cancel_number(activation_id=activation_id)
                    print(
                        f"{email_address}: Verification code not sent to number. Waiting timed out"
                    )
                    new_profile_logger(
                        email_address,
                        "FAIL",
                        "Verification code not sent to number. Waiting timed out",
                    )
                    return (
                        False,
                        "Verification code not sent to number. Waiting timed out",
                    )

        if is_protect_your_account_page(driver):
            recovery_email_page_popped_up = "YES"

            lets_protect_your_account_banner_page(driver)
            print(f"{email_address}: Protect your account page")
            if not select_alternate_email_option(driver=driver):
                print(f"{email_address}: Error selecting an alternate email option")
                new_profile_logger(
                    email_address,
                    "FAIL",
                    "Error selecting an alternate email option",
                )
                return False, "Error selecting an alternate email option"

            status, temp_email, email_token = create_email()
            new_profile_data["recovery_email"] = temp_email
            if not status:
                print(
                    f"{email_address}: Error getting a temp mail from temp-mail. Tempmail unresponsive"
                )
                new_profile_logger(
                    email_address,
                    "FAIL",
                    "Error getting email from tempmail",
                )
                return (
                    False,
                    "Error getting a temp mail from temp-mail. Tempmail unresponsive",
                )

            else:
                print(f"{email_address}: got email from temp-mail. Verifying..")
                if not enter_email(driver=driver, email_address=temp_email):
                    print(f"{email_address}: Error entering recovery email")
                    new_profile_logger(
                        email_address,
                        "FAIL",
                        "Error entering recovery email",
                    )
                    return False, "Error entering recovery email"
                time.sleep(0.5)
                bring_to_front(driver)
                time.sleep(1)
                sss, er = click_next_button_rec_email(driver)
                if not sss:
                    os.makedirs("screenshots", exist_ok=True)
                    driver.save_screenshot(f"screenshots/{email_address}_error.png")
                    print(
                        f"{email_address}: Error clicking next after entering recovery email: {er}"
                    )
                    new_profile_logger(
                        email_address,
                        "FAIL",
                        "Error clicking next after entering recovery email",
                    )
                    return False, "Error clicking next after entering recovery email"

                status, code = wait_for_code(email_token)
                time.sleep(3)
                if not status:
                    print(f"{email_address}: Error getting code from tempmail")
                    new_profile_logger(
                        email_address,
                        "FAIL",
                        "Error getting code from tempmail. Timed out without receiving code",
                    )
                    return False, "Error getting code from tempmail. Timeout"
                else:
                    print(f"{email_address}: Code received from tempmail: {code}")
                if not enter_code(driver, code):
                    print(f"{email_address}: Error entering email verification code")
                    new_profile_logger(
                        email_address,
                        "FAIL",
                        "Error entering email verification code",
                    )
                    return False, "Error entering email verification code"

                if not click_next_button(driver):
                    print(f"{email_address}: Error clicking next after entering otp")
                    new_profile_logger(
                        email_address,
                        "FAIL",
                        "Error clicking next after entering otp",
                    )
                    return False, "Error clicking next after entering otp"

                if invalid_code(driver):
                    print(f"{email_address}: OTP ENTERED IS INCORRECT")
                    new_profile_logger(
                        email_address,
                        "FAIL",
                        "Otp sent is incorrect",
                    )
                    return False, "OTP ENTERED IS INCORRECT"
                else:
                    print(f"{email_address}: OTP verified successfully")

        print(f"{email_address}:Finalizing signin")
        close_other_tabs(driver)
        # click_next_if_is_updating_terms_page(driver)
        click_next_if_a_quick_note_page(driver)
        cancel_setup_passkey(driver)
        click_stay_signed_in_button(driver)

        try:
            if enter_password(driver=driver, password=password):
                print(f"{email_address}: Reloging in with password")
                click_password_next_button(driver=driver)
                click_stay_signed_in_button(driver)
        except:
            pass

        joined_microsoft_premium = "NO"
        print(f"{email_address}: SUCCESSFULL LOGIN!")

        update_accounts_data(
            email=email_address,
            profile_dir=user_path,
            proxy_used=proxy,
            password=password,
            has_recovery_email=recovery_email_page_popped_up,
            recovery_email=temp_email,
            has_recovery_phone=has_recovery_phone,
            recovery_phone_number=recovery_phone_number,
            joined_microsoft_premium=joined_microsoft_premium,
        )

        status, error = change_acc_pass(driver, new_profile_data)
        if status:
            password = error
            update_accounts_data(email=email_address, password=error)
            new_profile_data["pass"] = error

        # print(f"{email_address}: Joining microsoft premium")
        # return driver

        # time.sleep(40)
        status = change_account_country(driver, new_profile_data)
        # if not status:
        #     status_ = change_account_country_specified(driver, new_profile_data)
        #     status = change_account_country(driver, new_profile_data)

        if not status:
            new_profile_logger(
                email_address,
                "FAIL",
                "Error to change country",
            )
            return False, "Error to change country"

        else:
            print(f"{email_address}: Country changed successfully")

        if PREFERRED_SMS_COUNTRY in ["United States", "united states"]:
            print(f"{email_address}: Changing account language to english")
            status = change_account_language(driver, new_profile_data)
            if not status:
                print(f"{email_address}: Error changing account language to english")
            else:
                print(
                    f"{email_address}: Account language changed to english successfully"
                )

        # return driver

        status, error = get_microsoft_premium(driver, new_profile_data)
        if not status:
            print(
                f"{email_address}: Error getting microsoft premium: {error}. Retrying ..."
            )
            try:
                if not get_next_card():
                    print(
                        "No available cards to use for Microsoft Premium. Check logs/card_usage.log and output_data/fully_used_cards.txt for more info."
                    )
                    os._exit(1)
                    return False, "No available cards to use for Microsoft Premium"
            except Exception as E:
                print(f"Error checking available cards: {E}")
                os._exit(1)
                return False, "Error checking available cards for Microsoft Premium"

            status, error = get_microsoft_premium(driver, new_profile_data)
            if not status:
                new_profile_logger(
                    email_address,
                    "FAIL",
                    f"Error getting microsoft premium: {error}",
                )
                return False, f"Error getting microsoft premium: {error}"
            else:
                new_profile_logger(
                    email_address, "SUCCESS", f"SUCESSFULLY GOT MICROSOFT PREMIUM"
                )

        else:
            new_profile_logger(
                email_address, "SUCCESS", f"SUCESSFULLY GOT MICROSOFT PREMIUM"
            )

        # return True, "Success"
        return driver

    except Exception as E:
        try:
            new_profile_logger(email_address, "FAIL", f"EXCEPTION_ERROR: {E}")
        except:
            pass
        return False, f"Undocumented_error: {E}"
    finally:
        try:
            driver.quit()
            processed_email(new_profile_data_original)
        except:
            pass
        try:
            card_details_dict = get_processing_card()
            if card_details_dict:
                return_card_to_familybot_card_details(card_details_dict)
        except Exception as E:
            # print(f"Error returning card to familybot_card_details: {E}")
            pass


def run_familybot():
    """
    Creates threads and signs in simultaneously
    """
    # Starting Familybot for country and ip

    print(
        f"Starting Familybot for country: {PREFERRED_SMS_COUNTRY} and IP: {SERVER_IP}"
    )
    while True:
        status, new_profile_data = get_new_profile_data()
        if status:
            initialize_new_profile(new_profile_data)

        else:
            print("No input emails in database...")
            break


def run_familybot_share():
    """
    Creates threads and signs in simultaneously
    """

    while True:
        status, new_profile_data = get_new_profile_data_from_history()
        if status:
            share_premium(new_profile_data)

        else:
            print("No unshared family acc in database...")
            break


# dta = "socialtilt_sad@outlook.com	058cLIdc4XIb.!Ze8	dociqng181@mailfrid.com"
# new_profile_data = {
#     "email": dta.split("\t")[0],
#     "pass": dta.split("\t")[1],
#     "recovery": dta.split("\t")[2],
# }


# driver = share_premium(new_profile_data)
