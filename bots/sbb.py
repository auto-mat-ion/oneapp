from asyncio import subprocess
import os
from seleniumbase import sb_cdp
import time
import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from ali.email_sender_batch_by_batch import EXPRESSVPN_CMD
from ali.old_hotmailbot import _check_shutdown_requested, new_profile_logger
from bots.hotmailbot2 import get_email_token

import requests
import re
import random
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

wait_time = 10


BASE_URL = "https://affworker.com"
TEMPMAIL_API_KEY = "jcfPNcqnl7GZoYYBUp9gTHObSIQaRnwIIBtNRd5J"


def connect_new_random(PREFERRED_SMS_COUNTRY="Netherlands"):

    try:
        vpn_country = PREFERRED_SMS_COUNTRY.lower()
        if vpn_country == "poland2":
            vpn_country = "poland"

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
                        if vpn_country.lower() == "united states"
                        else vpn_country.lower()
                    )
                )
            ].id.to_list()

            random_location = str(random.choice(rand_locations))
            print(f"Connecting to : {vpn_country}")

        except:
            try:
                random_location = str(
                    random.choice(
                        pd.read_csv("utils/express_countries.csv").id.to_list()
                    )
                )
                print(
                    f"No {vpn_country} server found. Connecting to Netherlands server"
                )
            except:
                locations = "93,208,156,209,81,162,219,192,193,194,175,238,160,114,63,152,112,80,57,224,223,133,195,174,111,137,196,197,113,198,164,190,107,154,37,58,199,108,101,128,117,88,115,243,232,91,163,45,79,169,181,245,125,131,100,246,240,144,141,247,241,132,20,142,242,244,140,95,271,19,283,288,270,276,265,273,17,302,299,304,292,306,9,294,18,172,278,284,293,275,165,277,286,290,161,272,6,70,74,71,280,291,54,202,305,285,301,26,155,168,281,75,295,289,297,94,282,296,298,204,1,207,2,300,287,166,303,25,279,274,143,126,184,185,21,307,186,85,147,110,118,124,56,78,130,34,150,153,104,8,103,136,7,92,210,102,99,106,33,129,182,157,29,188,122,119,36,12,134,120,187,189,4,16,212,146,96,32,31,86,145,127,121,211,35,22,23,203,11,201,89,53,178,5,15,263,90,87,139,84,239,105,176,248,249,109,264".split(
                    ","
                )
                random_location = str(random.choice(locations))
                print("Connecting to Random server")

        connect(random_location)
        time.sleep(2)
        VPN_CONNECTION_STATUS = "connected"
        VPN_CONNECTION_WATCHDOG_STOP.set()
        return True
    except:
        VPN_CONNECTION_STATUS = "none"
        VPN_CONNECTION_WATCHDOG_STOP.set()
        return False


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


def get_email_token(recovery_email: str):
    try:
        status, temp_email, email_token = create_email()
        username = recovery_email.split("@")[0]
        domain = recovery_email.split("@")[1]
        url = f"{BASE_URL}/api/email/change/{email_token}/{username}/{domain}/{TEMPMAIL_API_KEY}"
        resp = requests.post(url, timeout=15)
        data = resp.json()
        if data.get("status") == "success":
            return True, data["data"]["email_token"]
        return False, ""
    except:
        return False, ""


def fetch_messages(email_token: str):
    url = f"{BASE_URL}/api/messages/{email_token}/{TEMPMAIL_API_KEY}"
    try:
        resp = requests.get(url, timeout=15)
        data = resp.json()
        if data.get("status") == "success":
            return True, data["data"]["messages"]
        return False, []
    except:
        return False, []


def delete_message(message_id: str):
    try:
        url = f"{BASE_URL}/api/message/delete/{message_id}/{TEMPMAIL_API_KEY}"
        resp = requests.post(url, timeout=15)
        data = resp.json()
        if data.get("status") == "success":
            return True
        return False
    except:
        return False


def wait_for_code(email_token, timeout=120, poll_interval=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            message_id = None
            ok, messages = fetch_messages(email_token)
            last_message = messages[0]
            message_id = last_message.get("id")
            try:
                plain = re.sub(r"<[^>]+>", " ", last_message.get("content"))
                match = re.search(r"\s*(\d{6})", plain)
                if match:
                    try:
                        if message_id:
                            delete_message(message_id)
                        return True, match.group(1)
                    except:
                        pass
            except:
                pass
            if message_id:
                delete_message(message_id)
            time.sleep(poll_interval)
        except:
            pass
    return False, ""


def enter_email(driver: sb_cdp.Chrome, email_address: str, timeout: int = 10):
    try:
        """
        Enters the email address in the email input box
        """
        wait_time = timeout
        EMAIL_INPUT_ELEMENT = 'input[type="email"]'
        driver.wait_for_element_visible(EMAIL_INPUT_ELEMENT, timeout=wait_time)
        driver.type(EMAIL_INPUT_ELEMENT, email_address, timeout=wait_time)
        return True
    except:
        return False


def click_next_button(driver):
    """
    Clicks the next button
    """
    try:
        NEXT_BUTTON_ELEMENT = 'input[type="submit"]'
        driver.wait_for_element_visible(NEXT_BUTTON_ELEMENT, timeout=wait_time)
        driver.click(NEXT_BUTTON_ELEMENT)
        return True
    except:
        return False


def enter_recovery_email_2(driver, recovery_email):
    try:
        input_element = 'input[type="text"]'
        driver.wait_for_element_visible(input_element, timeout=wait_time)
        driver.type(input_element, recovery_email)
        return True
    except:
        return False


def click_send_code_to_recovery_email_button(driver):
    try:
        BUTTONS = 'span[role="button"]'
        driver.wait_for_element_visible(BUTTONS, timeout=wait_time)
        buttons = driver.find_elements(By.CSS_SELECTOR, BUTTONS)
        next(
            button
            for button in buttons
            if button.text.lower().startswith("send a code to")
        ).click()
        return True
    except:
        return False


def click_send_code_button(driver):
    """
    Clicks the next button on gmail login
    """
    try:
        NEXT_BUTTON_ELEMENT = 'button[type="submit"]'
        driver.wait_for_element_visible(NEXT_BUTTON_ELEMENT, timeout=10)
        time.sleep(2)
        print("Code brn visible")
        driver.click(NEXT_BUTTON_ELEMENT)
        return True
    except Exception as E:
        print(f"Exception: {E}")
        return False


def enter_code_and_click_next_after_pass_change(driver, code):
    try:
        input_element = 'input[id="codeEntry-0"]'
        driver.wait_for_element_visible(input_element, timeout=wait_time)
        driver.clear_input(input_element)
        driver.type(input_element, code)
        time.sleep(0.5)
        return True
    except:
        return False


def login(driver, email, password, recovery_email):
    status, email_token = get_email_token(recovery_email=recovery_email)
    if not status:
        print(f"{email}: Error getting email token for recovery email")
        return False, "Error getting email token for recovery email"
    print(f"{email}: Got email token for recovery email")
    driver.get("https://login.microsoftonline.com/")
    if not enter_email(driver, email):
        print(f"{email}: Failed to enter email")
        return False
    if not click_next_button(driver):
        print(f"{email}: Failed to click next button")
        return False
    time.sleep(2)
    if not enter_recovery_email_2(driver, recovery_email):
        print(f"{email}: Failed to enter recovery email")
        return False
    time.sleep(2)
    if not click_send_code_button(driver):
        print(f"{email}: Failed to click send code button")
        return False
    code_status, code = wait_for_code(email_token=email_token)
    if not code_status:
        print(f"{email}: Failed to get code from recovery email")
        return False
    print(f"{email}: Got code from recovery email: {code}")
    if not enter_code_and_click_next_after_pass_change(driver, code):
        print(f"{email}: Failed to enter code")
        return False
    return True


# we'ew updating terms
# looks good page
# a quick note page


data = "saniprevell9uq@outlook.com,D2kMPI10,erikanaylor2936@affworker.com"
new_profile_data = {
    "email": data.split(",")[0],
    "pass": data.split(",")[1],
    "recovery": data.split(",")[2],
}

driver = sb_cdp.Chrome()
driver.maximize()

driver.get("https://login.microsoftonline.com/")


data = "AlentineLover713195@hotmail.com,urkZlrI768376.New9!,gqfhbsw063@imailito.com"
new_profile_data = {
    "email": data.split(",")[0],
    "pass": data.split(",")[1],
    "recovery": data.split(",")[2],
}
login(
    driver,
    new_profile_data["email"],
    new_profile_data["pass"],
    new_profile_data["recovery"],
)

proxy = "fa837640bf79e5941f60__cr.cy:1bf070f939ca13b1@gw.dataimpulse.com:10000"
driver.get("https://strumyk.cv/#vVoR6526")


proxy = "gw.dataimpulse.com:10000"

time.sleep(5)
driver.solve_captcha()
