import time
from datetime import timedelta, datetime
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from seleniumbase import Driver
import pandas as pd
import requests
from dotenv import load_dotenv
import threading
from concurrent.futures import ThreadPoolExecutor
import re
import json
import subprocess
import mysql.connector

import random
import msal

lock = threading.Lock()
load_dotenv()

THE_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_bot_settings():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(BASE_DIR, "settings.json")

    try:
        with open(settings_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data.get("hotmailbot", {})
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


FAMILYBOT_SETTINGS = load_bot_settings()
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

# print(chrome_location)

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


BOT_TYPE = "hotmailbot"


def get_db_connection():
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
        print(f"Unable to connect to database: {exc}")
        return None


CLIENT_ID = get_setting("CLIENT_ID")
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["https://graph.microsoft.com/.default"]
CACHE_PATH = os.path.normpath(
    os.path.join(THE_BASE_DIR, os.path.abspath(get_setting("CACHE_PATH") or ""))
)

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
                random.choice(pd.read_csv("utils/express_countries.csv").id.to_list())
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
            df = pd.read_csv("utils/express_countries_all.csv")
            df = get_locations()

            # df[df.country.apply(lambda x: x.lower().startswith('indonesia'))]

            rand_locations = df[
                df.country.apply(lambda x: x.lower().startswith(PREFERRED_SMS_COUNTRY))
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


def read_input_emails_data():
    try:
        df = pd.read_csv(emails_dir)
        # df = pd.read_csv(emails_dir, names=["email_address", "password", "x", 'y'])

        return df.to_dict(orient="records")
    except:
        return []


def read_input_emails_txt_data():
    try:
        df = pd.read_csv(emails_dir, sep=":", names=["email", "pass"])

        try:
            signing_emails = pd.read_csv("logs/signin_log.csv").email_acc.to_list()
        except:
            signing_emails = []

        try:
            accounts_emails = pd.read_csv("utils/accounts.csv").email_acc.to_list()
        except:
            accounts_emails = []

        processed_emails = list(set(signing_emails + accounts_emails))
        df = df[~df.email.apply(lambda x: x in processed_emails)]
        return df.to_dict(orient="records")
    except:
        return []


def load_proxies():
    with open(proxies_dir, "r") as f:
        content = f.read().split("\n")

    proxy_data = [
        {"proxy": f"{x[2]}:{x[3]}@{x[0]}:{x[1]}", "used": 0}
        for x in [proxy.split(":") for proxy in content]
    ]

    pd.DataFrame(proxy_data).to_json("utils/proxy.json", orient="records")


# def get_family_link() -> str:
#     try:
#         json_path = r"input_data\family_link.txt"
#         with open(json_path, "r", encoding="utf-8") as f:
#             data = json.load(f)

#         if not data:
#             return False, ""

#         least_used_link = min(data, key=lambda k: data[k])

#         data[least_used_link] += 1

#         with open(json_path, "w", encoding="utf-8") as f:
#             json.dump(data, f, indent=2)

#         return True, least_used_link
#     except:
#         return False, ""


def get_proxy():
    try:
        df = pd.read_json("utils/proxy.json")
        df = df.sort_values("used", ascending=True)

        proxy = df.iat[0, 0]
        df.iat[0, 1] = df.iat[0, 1] + 1
        df.to_json("utils/proxy.json", orient="records")
        return True, proxy
    except:
        return False, False


def rollback_proxy(proxy):
    try:
        _, proxy = get_proxy()
        df = pd.read_json("utils/proxy.json")

        df.iat[df[df.proxy == proxy].index[0], 1] = (
            df.iat[df[df.proxy == proxy].index[0], 1] - 1
        )

        df.to_json("utils/proxy.json", orient="records")

        return True, proxy
    except:
        return False, False


def get_new_profile_path():
    if os.path.exists(profile_dir):
        current_profiles = os.listdir(profile_dir)
        if not current_profiles:
            user_data_dir = os.path.abspath(profile_dir + "/1")
        else:
            user_data_dir = os.path.abspath(
                profile_dir + f"/{str(max([int(i) for i in current_profiles]) + 1)}"
            )

    return user_data_dir


def initialize_new_profile_driver():
    try:
        with lock:
            # user_data_dir = get_new_profile_path()
            user_data_dir = ""

            # status, proxy = get_proxy()
            proxy = "NO PROXY USED"

            if SAVE_COOKIES:
                driver = Driver(
                    uc=True,
                    # browser="firefox",
                    # proxy=proxy,
                    binary_location=chrome_location,
                    user_data_dir=user_data_dir,
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


def get_existing_profile_path(email):
    """
    Retrieve path for driver from csv
    """
    try:
        df = pd.read_csv("utils/accounts.csv")

        path = df[df["email_acc"] == email].profile_dir.values[0]
        if path:
            return True, path
        else:
            return False, False
    except:
        return False, False


def initialize_existing_profile_driver(email, profile_dir="", proxy=""):
    try:
        driver = Driver(
            uc=True,
            proxy=proxy,
            binary_location=chrome_location,
            user_data_dir=profile_dir,
            extension_dir=extension_dir,
            locale_code="en",
        )

        driver.maximize_window()

        return True, driver
    except Exception as E:
        try:
            driver.quit()
            time.sleep(0.5)
        except:
            pass
        return False, False


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
            conn = get_db_connection()
            if conn is None:
                return False, ""
            cursor = conn.cursor()
            cursor.execute(
                "SELECT link FROM familybot_extracted_family_links ORDER BY link_id"
            )
            links = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()

            if not links:
                return False, "NO_LINK"

            for link in links:
                # print(f"Checking link usage for: {link}")
                conn = get_db_connection()
                if conn is None:
                    continue
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT times_used FROM link_stats WHERE link = %s  LIMIT 1",
                    (link,),
                )
                result = cursor.fetchone()
                times_used = result[0] if result else 0
                cursor.close()
                conn.close()
                # print(f"Link {link} has been used {times_used} times.")

                if times_used >= 5:
                    successfully_worked_links(link)
                else:
                    # print(f"Link {link} has not been used enough times.")
                    # break
                    return True, link

            return False, "NO_LINK"
        except Exception as e:
            print(f"Error in get_family_link: {e}")
            return False, ""


def get_family_link_old(driver):
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
    try:
        conn = get_db_connection()
        if conn is None:
            return
        cursor = conn.cursor()
        cursor.execute("SELECT times_used FROM link_stats WHERE link = %s", (link,))
        result = cursor.fetchone()
        if result:
            cursor.execute(
                "UPDATE link_stats SET times_used = times_used + 1, server_ip = %s, bot_type = %s, date_time = %s WHERE link = %s",
                (SERVER_IP, BOT_TYPE, datetime.now(), link),
            )
        else:
            cursor.execute(
                "INSERT INTO link_stats (server_ip, bot_type, date_time, link, times_used) VALUES (%s, %s, %s, %s, %s)",
                (SERVER_IP, BOT_TYPE, datetime.now(), link, 1),
            )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error in update_link_usage_times: {e}")


def not_working_links(link):
    try:
        conn = get_db_connection()
        if conn is None:
            return
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expired_family_links (server_ip, bot_type, date_time, link) VALUES (%s, %s, %s, %s)",
            (SERVER_IP, BOT_TYPE, datetime.now(), link),
        )
        cursor.execute(
            "DELETE FROM familybot_extracted_family_links WHERE link = %s", (link,)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error in not_working_links: {e}")


def successfully_worked_links(link):
    try:
        conn = get_db_connection()
        if conn is None:
            return
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO used_5_times_family_links (server_ip, bot_type, date_time, link) VALUES (%s, %s, %s, %s)",
            (SERVER_IP, BOT_TYPE, datetime.now(), link),
        )
        cursor.execute(
            "DELETE FROM familybot_extracted_family_links WHERE link = %s", (link,)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error in successfully_worked_links: {e}")


# email_data = data[0]
def processed_email_old(email_data):
    try:
        email_str = f"{email_data.get('email')}:{email_data.get('pass')}"

        with open("input_data/processed_emails.txt", "a", encoding="utf-8") as file:
            file.write(email_str + "\n")
        with open("input_data/emails.txt", "r", encoding="utf-8") as file:
            lines = file.readlines()

        cleaned_lines = [line for line in lines if line.strip() != email_str.strip()]

        with open("input_data/emails.txt", "w", encoding="utf-8") as file:
            file.writelines(cleaned_lines)
    except:
        pass


def processed_email(email_data):
    try:
        import mysql.connector

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
        conn.close()
    except Exception as e:
        print(f"Error in processed_email: {e}")
        pass


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


def click_join_family_link_btn(driver, new_profile_data):
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
        try:
            button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[aria-label="Sign in"]')
                )
            )

            button.click()

            password = new_profile_data.get("pass", "")
            click_use_your_password_button(driver)
            enter_password(driver, password=password)
            click_password_next_button(driver)

            click_existing_account_smtp(driver)
            enter_password(driver, password=password)
            click_password_next_button(driver)

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


def use_link_to_join_family_acc(driver, new_profile_data):
    try:
        status, invite_url = get_family_link(driver)
        if status:
            print("Using family url to join.")
            driver.get(invite_url)
            check_btn_retries = 0
            proceed = False
            while (check_btn_retries < 15) and (not proceed):
                if click_join_family_link_btn(driver, new_profile_data):
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


def join_family_acc(driver, new_profile_data):
    retries = 0
    while retries < 5:
        if use_link_to_join_family_acc(driver, new_profile_data):
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


def sign_up_bitly_thread(profile_data):
    try:
        email_address = profile_data.get("email_acc")
        password = profile_data.get("password")
        password = password + "A1!"  # To meet bitly's password rules
        profile_dir = profile_data.get("profile_dir")
        proxy_used = profile_data.get("proxy_used")

        # GET THE PROFILE WITH THIS EMAIL
        print(f"{email_address}: Initialising existing driver")

        status, driver = initialize_existing_profile_driver(
            email=email_address, profile_dir=profile_dir, proxy=proxy_used
        )
        if status:
            print(f"{email_address}: Successfully initialising driver. Signing up...")
            signup_status = sign_up_to_bitly_and_verify_otp(
                driver, email_address, password
            )
            if signup_status:
                print(f"{email_address}: Successfully signed up to bitly")
                update_accounts_data(
                    email=email_address,
                    has_bitly_account="YES",
                    bitly_acc_password=password,
                )
    except:
        return False
    finally:
        try:
            driver.quit()
        except:
            pass


def enter_password(driver, password):
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
            conn.close()
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


# def update_accounts_data(
#     email,
#     password=None,
#     date_time=None,
#     profile_dir=None,
#     proxy_used=None,
#     has_recovery_email=None,
#     recovery_email=None,
#     has_recovery_phone=None,
#     recovery_phone_number=None,
#     joined_microsoft_premium=None,
#     join_time_microsoft_premium=None,
#     has_bitly_account=None,
#     bitly_acc_password=None,
#     save_smtp="NO",
# ):
#     if not email:
#         return False

#     try:
#         conn = mysql.connector.connect(
#             host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
#         )
#         cursor = conn.cursor()

#         # Check if email exists
#         cursor.execute(
#             "SELECT account_id FROM accounts_details WHERE email_acc = %s", (email,)
#         )
#         result = cursor.fetchone()

#         if result:
#             # Update existing record
#             update_fields = []
#             update_values = []

#             if password is not None:
#                 update_fields.append("password = %s")
#                 update_values.append(password)
#             if profile_dir is not None:
#                 update_fields.append("profile_dir = %s")
#                 update_values.append(profile_dir)
#             if profile_dir is not None:
#                 update_fields.append("join_time_microsoft_premium = %s")
#                 update_values.append(datetime.now())
#             if profile_dir is not None:
#                 update_fields.append("date_time = %s")
#                 update_values.append(datetime.now())

#             if proxy_used is not None:
#                 update_fields.append("proxy_used = %s")
#                 update_values.append(proxy_used)
#             if has_recovery_email is not None:
#                 update_fields.append("has_recovery_email = %s")
#                 update_values.append(str(has_recovery_email))
#             if recovery_email is not None:
#                 update_fields.append("recovery_email = %s")
#                 update_values.append(recovery_email)
#             if has_recovery_phone is not None:
#                 update_fields.append("has_recovery_phone = %s")
#                 update_values.append(str(has_recovery_phone))
#             if recovery_phone_number is not None:
#                 update_fields.append("recovery_phone_number = %s")
#                 update_values.append(recovery_phone_number)
#             if joined_microsoft_premium is not None:
#                 update_fields.append("joined_microsoft_premium = %s")
#                 update_values.append(str(joined_microsoft_premium))
#             if has_bitly_account is not None:
#                 update_fields.append("has_bitly_account = %s")
#                 update_values.append(str(has_bitly_account))
#             if bitly_acc_password is not None:
#                 update_fields.append("bitly_acc_password = %s")
#                 update_values.append(bitly_acc_password)
#             if save_smtp:
#                 update_fields.append("save_smtp = %s")
#                 update_values.append(save_smtp)

#             if update_fields:
#                 update_values.append(email)
#                 query = f"UPDATE accounts_details SET {', '.join(update_fields)} WHERE email_acc = %s"
#                 cursor.execute(query, tuple(update_values))
#         else:
#             # Insert new record
#             cursor.execute(
#                 "INSERT INTO accounts_details (server_ip, bot_type,date_time, email_acc, password, profile_dir, proxy_used, country, has_recovery_email, recovery_email, has_recovery_phone, recovery_phone_number, joined_microsoft_premium, has_bitly_account, bitly_acc_password, save_smtp) VALUES (%s, %s, %s, %s, %s,%s,%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
#                 (
#                     SERVER_IP,
#                     BOT_TYPE,
#                     datetime.now(),
#                     email,
#                     password,
#                     profile_dir,
#                     proxy_used,
#                     PREFERRED_SMS_COUNTRY,
#                     str(has_recovery_email) if has_recovery_email is not None else None,
#                     recovery_email,
#                     str(has_recovery_phone) if has_recovery_phone is not None else None,
#                     recovery_phone_number,
#                     str(joined_microsoft_premium)
#                     if joined_microsoft_premium is not None
#                     else None,
#                     datetime.now() if join_time_microsoft_premium is not None else None,
#                     str(has_bitly_account) if has_bitly_account is not None else None,
#                     bitly_acc_password,
#                     save_smtp,
#                 ),
#             )

#         conn.commit()
#         conn.close()
#         return True
#     except Exception as e:
#         print(f"Error saving to accounts table: {e}")
#         return False


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
                    str(has_recovery_email) if has_recovery_email is not None else None,
                    recovery_email,
                    str(has_recovery_phone) if has_recovery_phone is not None else None,
                    recovery_phone_number,
                    str(joined_microsoft_premium)
                    if joined_microsoft_premium is not None
                    else None,
                    datetime.now() if join_time_microsoft_premium is not None else None,
                    str(has_bitly_account) if has_bitly_account is not None else None,
                    bitly_acc_password,
                    save_smtp,
                ),
            )

        conn.commit()
        conn.close()
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

            retries += 1

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
    try:
        conn = get_db_connection()
        if conn is None:
            return msal.SerializableTokenCache()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT cache_bin_file FROM cache_bins WHERE server_ip = %s AND bot_type = %s ORDER BY date_time DESC LIMIT 1",
            (SERVER_IP, BOT_TYPE),
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result and result[0]:
            cache = msal.SerializableTokenCache()
            cache.deserialize(result[0].decode("utf-8"))
            return cache
        else:
            return msal.SerializableTokenCache()
    except Exception as e:
        print(f"Error loading cache: {e}")
        return msal.SerializableTokenCache()


def save_cache(cache):
    try:
        if cache.has_state_changed:
            serialized_cache = cache.serialize()
            conn = get_db_connection()
            if conn is None:
                return
            cursor = conn.cursor()
            # Check if row exists
            cursor.execute(
                "SELECT cache_id FROM cache_bins WHERE server_ip = %s AND bot_type = %s",
                (SERVER_IP, BOT_TYPE),
            )
            result = cursor.fetchone()
            if result:
                cursor.execute(
                    "UPDATE cache_bins SET date_time = %s, cache_bin_file = %s WHERE server_ip = %s AND bot_type = %s",
                    (
                        datetime.now(),
                        serialized_cache.encode("utf-8"),
                        SERVER_IP,
                        BOT_TYPE,
                    ),
                )
            else:
                cursor.execute(
                    "INSERT INTO cache_bins (server_ip, bot_type, date_time, cache_bin_file) VALUES (%s, %s, %s, %s)",
                    (
                        SERVER_IP,
                        BOT_TYPE,
                        datetime.now(),
                        serialized_cache.encode("utf-8"),
                    ),
                )
            conn.commit()
            cursor.close()
            conn.close()
            # Save copy to file

            with open(CACHE_PATH, "w") as f:
                f.write(serialized_cache)
    except Exception as e:
        print(f"Error saving cache: {e}")


def click_existing_account_smtp(driver):
    """
    Clicks the existing account button on login page if exists
    """
    try:
        EXISTING_ACC_BTN_ELEMENT = (
            By.CSS_SELECTOR,
            'div[id="newSessionLink"]',
        )  # div[aria-describedby="NewSessionTitle"]

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
        conn = get_db_connection()
        if conn is None:
            return
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO failed_smtp (server_ip, bot_type, date_time, email_address, password, temp_email) VALUES (%s, %s, %s, %s, %s, %s)",
            (SERVER_IP, BOT_TYPE, datetime.now(), email_address, password, temp_email),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error in failed_smtp: {e}")


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


def change_acc_pass(driver, new_profile_data):
    try:
        password = new_profile_data.get("pass")
        email = new_profile_data.get("email")
        print(f"{email} : Initializing change password")

        bring_to_front(driver)
        pass_change_url = "https://account.live.com/password/change"

        driver.get(pass_change_url)

        time.sleep(2)

        new_pass = password + "."

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

        if not click_next_button_rec_email(driver=driver):
            print(f"{email} : Error clicking next button after changing password")
            return False, "Error locating password input elements"
        time.sleep(1)

        # RELOG IN
        try:
            print(f"{email}: Reloging in with NEW password")
            click_existing_account_smtp(driver)

            if enter_password(driver=driver, password=new_pass):
                click_password_next_button(driver=driver)
        except:
            pass

        print(f"{email} : Password changed successfully")
        return True, new_pass

    except Exception as e:
        print(f"{email} : Exception error while changing password: {str(e)}")
        return False, f"Exception during changing password: {str(e)}"


def initialize_new_profile(new_profile_data):
    """
    Creating a new chrome profile.

    A dictionary with email_address, and password
    """
    try:
        print("\n--------------------------------------\n")
        connect_new_random()
        email_address = new_profile_data.get("email")
        password = new_profile_data.get("pass")

        new_profile_data_original = new_profile_data.copy()

        retries = 0
        driver_success = False
        print(f"{email_address} : Initializing browser driver")
        while (retries < 3) and (not driver_success):
            try:
                status, driverdata, error = initialize_new_profile_driver()
                print(f"{email_address} : Driver status: {status}, error: {error}")
                if status:
                    driver, user_path, proxy = driverdata.values()

                    time.sleep(0.5)
                    driver.maximize_window()
                    time.sleep(0.5)
                    driver.get(MICROSOFT_LOGIN_URL)
                    time.sleep(1)
                    driver_success = True

            except:
                try:
                    driver.quit()
                except:
                    pass
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
        click_stay_signed_in_button(driver)

        try:
            if enter_password(driver=driver, password=password):
                print(f"{email_address}: Reloging in with password")
                click_password_next_button(driver=driver)
                click_stay_signed_in_button(driver)
        except:
            pass
        # close_poppup_after_login(driver)
        # go_to_outlook(driver)
        # close_outlook_poppup(driver)
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
            update_accounts_data(email=email_address, password=error)

            new_profile_data["pass"] = error

        print(f"{email_address}: Joining microsoft premium")
        driver.refresh()
        # return driver

        if join_family_acc(driver, new_profile_data):
            joined_microsoft_premium = "YES"
            premium_logger(email_address, password, temp_email)
            print(f"{email_address}: Successfully joined microsoft premium")
        else:
            print(f"{email_address}: Unable to join microsoft premium after 3 retries.")
            new_profile_logger(
                email_address,
                "FAIL",
                "Unable to join microsoft premium after 3 retries",
            )
            return False, "Unable to join microsoft premium after 3 retries"

        update_accounts_data(
            email=email_address,
            joined_microsoft_premium=joined_microsoft_premium,
            join_time_microsoft_premium=datetime.now(),
        )

        print(f"{email_address}: Setting up SMTP")
        status, error = smtp_process(driver, new_profile_data)
        if status:
            print(f"{email_address}: Successfully set up SMTP")
            new_profile_logger(
                email_address,
                "SUCCESS",
                "Login successfull",
            )
            update_accounts_data(email=email_address, save_smtp="YES")

            return True, driver
        else:
            print(f"{email_address}: Error setting up SMTP: {error}")
            new_profile_logger(
                email_address,
                "FAIL",
                f"Error setting up SMTP: {error}",
            )
            failed_smtp(email_address, password, temp_email)
            return False, f"Error setting up SMTP: {error}"

    except Exception as E:
        try:
            new_profile_logger(email_address, "FAIL", f"EXCEPTION_ERROR: {E}")
        except:
            pass
        return False, f"Undocumented_error: {E}"
    finally:
        try:
            # input(
            #     f"{email_address}: Process completed. Press Enter to close the browser and continue..."
            # )
            # time.sleep(3)
            driver.quit()
            processed_email(new_profile_data_original)
        except:
            pass


def signin_multithread():
    """
    Creates threads and signs in simultaneously
    """

    data = read_input_emails_txt_data()
    print(f"{len(data)} emails accounts available. Starting...")
    with ThreadPoolExecutor(max_workers=MAX_SIGNIN_THREADS) as executor:
        executor.map(initialize_new_profile, data)


def get_new_profile_data():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )
        cursor = conn.cursor()
        cursor.execute("SELECT email, pass FROM input_emails LIMIT 1")
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {}
        email, password = row
        cursor.execute(
            "INSERT INTO processing_emails (email, pass, server_ip, bot_type, date_time) VALUES (%s, %s,%s, %s, %s)",
            (email, password, SERVER_IP, BOT_TYPE, datetime.now()),
        )
        cursor.execute(
            "DELETE FROM input_emails WHERE email = %s AND pass = %s", (email, password)
        )
        conn.commit()
        conn.close()
        return True, {"email": email, "pass": password}
    except Exception as e:
        print(f"Error getting email from db: {e}")
        return False, {"email": "", "pass": ""}


def run_hotmailbot():
    """
    Creates threads and signs in simultaneously
    """

    while True:
        status, new_profile_data = get_new_profile_data()
        if status:
            initialize_new_profile(new_profile_data)

        else:
            print("No input emails in database...")
            break
