import subprocess
import os
import threading
from seleniumbase import sb_cdp
import time
import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import re
import random
import pandas as pd
import msal
import mysql.connector
from datetime import timedelta, datetime, timezone

# sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

wait_time = 10


BASE_URL = "https://affworker.com"
TEMPMAIL_API_KEY = "jcfPNcqnl7GZoYYBUp9gTHObSIQaRnwIIBtNRd5J"
EXPRESSVPN_CMD = "C:\\Program Files (x86)\\ExpressVPN\\services\\ExpressVPN.CLI.exe"


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


def connect_new_random(PREFERRED_SMS_COUNTRY="Netherlands"):
    try:
        vpn_country = "Netherlands"
        disconnect()
        connect("4")
        return True
    except:
        return False


def connect_new_random(PREFERRED_SMS_COUNTRY="Netherlands"):
    return True


def create_email_sb():
    url = f"{BASE_URL}/api/email/create/{TEMPMAIL_API_KEY}"
    try:
        resp = requests.post(url, timeout=15)
        data = resp.json()
        if data.get("status") == "success":
            return True, data["data"]["email"], data["data"]["email_token"]
        return False, "", ""
    except:
        return False, "", ""


def get_email_token_sb(recovery_email: str):
    try:
        status, temp_email, email_token = create_email_sb()
        username = recovery_email.split("@")[0]
        domain = recovery_email.split("@")[1]
        url = f"{BASE_URL}/api/email/change/{email_token}/{username}/{domain}/{TEMPMAIL_API_KEY}"
        resp = requests.post(url, timeout=15)
        data = resp.json()
        if data.get("status") == "success":
            return True, data["data"]["email_token"]
        return False, ""
    except Exception as e:
        return False, e


def fetch_messages_sb(email_token: str):
    url = f"{BASE_URL}/api/messages/{email_token}/{TEMPMAIL_API_KEY}"
    try:
        resp = requests.get(url, timeout=15)
        data = resp.json()
        if data.get("status") == "success":
            return True, data["data"]["messages"]
        return False, []
    except:
        return False, []


def delete_message_sb(message_id: str):
    try:
        url = f"{BASE_URL}/api/message/delete/{message_id}/{TEMPMAIL_API_KEY}"
        resp = requests.post(url, timeout=15)
        data = resp.json()
        if data.get("status") == "success":
            return True
        return False
    except:
        return False


def wait_for_code_sb(email_token, timeout=120, poll_interval=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            message_id = None
            ok, messages = fetch_messages_sb(email_token)
            last_message = messages[0]
            message_id = last_message.get("id")
            try:
                plain = re.sub(r"<[^>]+>", " ", last_message.get("content"))
                match = re.search(r"\s*(\d{6})", plain)
                if match:
                    try:
                        if message_id:
                            delete_message_sb(message_id)
                        return True, match.group(1)
                    except:
                        pass
            except:
                pass
            if message_id:
                delete_message_sb(message_id)
            time.sleep(poll_interval)
        except:
            pass
    return False, ""


def enter_email_sb(driver: sb_cdp.Chrome, email_address: str, timeout: int = 10):
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


def click_next_button_sb(driver):
    """
    Clicks the next button
    """
    try:
        NEXT_BUTTON_ELEMENT = 'input[type="submit"]'
        driver.wait_for_element_visible(NEXT_BUTTON_ELEMENT, timeout=wait_time)
        time.sleep(2)
        driver.click(NEXT_BUTTON_ELEMENT)
        return True
    except:
        return False


def is_your_account_has_been_locked_page_sb(driver):
    """
    Checks if the page is YOUR ACCOUNT HAS BEEN LOCKED
    """
    try:
        TITLE_ELEMENT = 'div[role="heading"]'
        title_element = driver.wait_for_element_visible(
            TITLE_ELEMENT, timeout=wait_time
        )
        time.sleep(2)
        if "your account has been locked" in title_element.text.lower():
            return True
        else:
            return False
    except:
        return False


def email_login_limit_reached_sb(driver):
    try:
        title = 'h1[data-testid="title"]'
        driver.wait_for_element_visible(title, timeout=15)
        driver.click(title)
        time.sleep(5)
        return (
            driver.get_text(title)
            .lower()
            .startswith("you've reached your limit with this sign-in method")
        )
    except:
        try:
            driver.wait_for_element_visible('input[id="codeEntry-0"]', wait_time)
            return False
        except:
            return True


def click_use_your_password_button_sb(driver):
    """
    Clicks the use your password button
    """
    try:
        BUTTON_ELEMENT = 'span[role="button"]'
        button_elements = driver.find_all(BUTTON_ELEMENT, wait_time)
        button_element = button_elements[
            [
                i.text.lower().startswith("use your password") for i in button_elements
            ].index(True)
        ]
        time.sleep(2)
        button_element.click()
        return True
    except:
        return False


def enter_recovery_email_2_sb(driver, recovery_email):
    try:
        input_element = 'input[type="text"]'
        driver.wait_for_element_visible(input_element, timeout=wait_time)
        time.sleep(3)
        driver.type(input_element, recovery_email)
        return True
    except:
        return False


def click_send_code_to_recovery_email_button_sb(driver):
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


def click_send_code_button_sb(driver):
    """
    Clicks the next button on gmail login
    """
    try:
        NEXT_BUTTON_ELEMENT = 'button[type="submit"]'
        driver.wait_for_element_visible(NEXT_BUTTON_ELEMENT, timeout=10)
        time.sleep(2)
        driver.click(NEXT_BUTTON_ELEMENT)
        return True
    except Exception as E:
        print(f"Exception: {E}")
        return False


def enter_code_and_click_next_after_pass_change_sb(driver, code):
    try:
        input_element = 'input[id="codeEntry-0"]'
        driver.wait_for_element_visible(input_element, timeout=wait_time)
        driver.clear_input(input_element)
        driver.type(input_element, code)
        time.sleep(0.5)
        return True
    except:
        return False


def _check_shutdown_requested():
    return True


SAVE_COOKIES = False
import weakref

ACTIVE_DRIVERS = weakref.WeakSet()

lock = threading.Lock()


def _track_driver(driver):
    with lock:
        ACTIVE_DRIVERS.add(driver)
    return driver


def initialize_new_profile_driver():
    try:
        user_data_dir = ""
        proxy = "NO PROXY USED"
        if SAVE_COOKIES:
            driver = sb_cdp.Chrome()
        else:
            user_data_dir = "Cookies not saved. SAVE_COOKIES option turned off."
            driver = sb_cdp.Chrome()
        return (
            True,
            {
                "driver": _track_driver(driver),
                "user_path": user_data_dir,
                "proxy": proxy,
            },
            None,
        )
    except Exception as E:
        try:
            pass
        except:
            pass
        return False, f"Driver_init_error: {E}", None


MICROSOFT_LOGIN_URL = "https://login.microsoftonline.com/"


def click_next_if_is_updating_terms_page_sb(driver):
    try:
        TITLE_ELEMENT = 'h1[data-testid="title"]'
        NEXT_BUTTON_ELEMENT = 'button[type="submit"]'
        driver.wait_for_element_visible(TITLE_ELEMENT, timeout=wait_time / 3)
        time.sleep(1)
        # driver.wait_for_element_visible(TITLE_ELEMENT, timeout=2)
        if (
            driver.get_text(TITLE_ELEMENT)
            .lower()
            .startswith("we're updating our terms")
        ):
            driver.wait_for_element_visible(NEXT_BUTTON_ELEMENT, timeout=4)
            time.sleep(2)
            driver.click(NEXT_BUTTON_ELEMENT)
            return True
        return True
    except:
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


def click_looks_good_button_sb(driver):
    try:
        BUTTON_ELEMENT = 'input[id="iLooksGood"]'
        driver.wait_for_element_visible(BUTTON_ELEMENT, timeout=wait_time / 2)
        time.sleep(2)
        driver.click(BUTTON_ELEMENT)
        return True
    except:
        return False


def click_next_if_a_quick_note_page_sb(driver):
    try:
        HEADER_ELEMENT = 'span[role="heading"]'
        driver.wait_for_element_visible(HEADER_ELEMENT, timeout=wait_time)
        time.sleep(3)
        driver.wait_for_element_visible(HEADER_ELEMENT, timeout=wait_time)
        if (
            driver.get_text(HEADER_ELEMENT)
            .lower()
            .startswith("a quick note about your microsoft account")
        ):
            BUTTON_ELEMENT = 'div[id="StickyFooter"]>button'
            driver.wait_for_element_visible(BUTTON_ELEMENT, timeout=wait_time)
            driver.click(BUTTON_ELEMENT)
            time.sleep(1)
            driver.wait_for_element_visible(BUTTON_ELEMENT, timeout=wait_time)
            driver.click(BUTTON_ELEMENT)
            return True
        return False
    except:
        return False


def click_stay_signed_in_button_sb(driver):
    try:
        BUTTON_ELEMENT = 'button[data-testid="primaryButton"]'
        driver.wait_for_element_visible(BUTTON_ELEMENT, timeout=wait_time)
        driver.click(BUTTON_ELEMENT)
        return True
    except:
        return False


def update_accounts_data(email, **kwargs):
    return True


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


def click_existing_account_smtp_sb(driver):
    """
    Clicks the existing account button on login page if exists
    """
    try:
        EXISTING_ACC_BTN_ELEMENT = 'div[id="newSessionLink"]'
        driver.wait_for_element_visible(EXISTING_ACC_BTN_ELEMENT, timeout=wait_time)
        time.sleep(3)
        driver.click(EXISTING_ACC_BTN_ELEMENT)
        return True
    except:
        return False


def enter_password_sb(driver, password):
    try:
        PASSWORD_INPUT_ELEMENT = 'input[type="password"]'
        driver.wait_for_element_visible(PASSWORD_INPUT_ELEMENT, timeout=wait_time)
        time.sleep(2)
        driver.click(PASSWORD_INPUT_ELEMENT)
        return True
    except:
        return False


def click_password_next_button_sb(driver):
    """
    Clicks the next button on gmail login
    """
    try:
        NEXT_BUTTON_ELEMENT = 'button[type="submit"]'
        driver.wait_for_element_visible(NEXT_BUTTON_ELEMENT, timeout=wait_time)
        time.sleep(2)
        driver.click(NEXT_BUTTON_ELEMENT)
        return True
    except:
        return False


def change_acc_pass_sb(driver, new_profile_data):
    try:
        password = new_profile_data.get("pass")
        email = new_profile_data.get("email")
        recovery = new_profile_data.get("recovery")
        email_token = new_profile_data.get("email_token")
        print(f"{email} : Initializing change password")
        bring_to_front(driver)
        pass_change_url = "https://account.live.com/password/change"
        driver.get(pass_change_url)
        click_next_if_a_quick_note_page_sb(driver)
        _check_shutdown_requested()
        new_pass = password + ".ak"
        retries = 0
        while retries < 3:
            try:
                _check_shutdown_requested()
                PASSWORD_ELEMENT = 'input[type="password"]'
                driver.wait_for_element_visible(PASSWORD_ELEMENT, timeout=wait_time)
                time.sleep(3)
                password_input_elements = driver.find_elements(PASSWORD_ELEMENT)
                for password_input_element in password_input_elements:
                    password_input_element.clear_input()
                    password_input_element.send_keys(new_pass)
                    time.sleep(1)
                print(f"{email} : Entered and confirmed new password")
                retries = 10
                break
            except:
                _check_shutdown_requested()
                print(f"{email} : Error locating password input elements. Retrying...")
                driver.get(pass_change_url)
                click_next_if_a_quick_note_page_sb(driver)
                time.sleep(2)
                retries += 1
        if retries != 10:
            return False, "Error entering new password"
        if not click_next_button_sb(driver):
            print(f"{email} : Error clicking next button after changing password")
            return False, "Error locating password input elements"
        time.sleep(5)
        try:
            print(f"{email}: Reloging in after password change")
            if click_existing_account_smtp_sb(driver):
                print(f"{email}: Clicked existing smtp account button.")
            else:
                print(f"{email}: No existing smtp account button.")
            if enter_recovery_email_2_sb(driver, recovery):
                print(f"{email} : Entered recovery email. Clicking next button.")
                if click_send_code_button_sb(driver):
                    print(
                        f"{email} : Clicked send code button. Waiting for recovery code."
                    )
                else:
                    print(f"{email} : Error clicking send code button.")
                if email_login_limit_reached_sb(driver):
                    print(f"{email} : Login limit reached. Using password.")
                    click_use_your_password_button_sb(driver)
                    print(f"{email} : Clicked use your password button.")
                    enter_password_sb(driver, password)
                    print(f"{email} : Entered password. Clicking next button.")
                    time.sleep(2)
                    click_password_next_button_sb(driver)
                    print(
                        f"{email} : Clicked next button. Password changed successfully."
                    )
                else:
                    print(
                        f"{email} : Recovery email page loaded. Waiting for recovery code."
                    )
                    status, code = wait_for_code_sb(email_token)
                    print(f"{email} : Recovery code received: {code}")
                    if not status:
                        print(
                            f"{email} : Recovery code not received. Cannot change password."
                        )
                        return False, "Recovery code not received"
                    print(f"{email} : Entering recovery code and clicking next button.")
                    enter_code_and_click_next_after_pass_change_sb(driver, code)
                    print(
                        f"{email} : Recovery code entered. Password changed successfully."
                    )
            elif enter_password_sb(driver=driver, password=new_pass):
                print(f"{email}: Entered new password. Clicking next button.")
                time.sleep(2)
                click_password_next_button_sb(driver=driver)
                print(f"{email}: Clicked next button.")
            else:
                print(f"{email}: Error entering new password or recovery.")
        except Exception as e:
            print(f"{email} : Error occurred while changing password: {str(e)}")
        print(f"{email} : Password changed process completed")
        return True, new_pass
    except Exception as e:
        print(f"{email} : Exception error while changing password: {str(e)}")
        return False, f"Exception during changing password: {str(e)}"


def cancel_setup_passkey_sb(driver):
    """
    Cancels passkey setup if poppup pops up
    """
    try:
        retries = 0
        while retries < 5:
            try:
                TITLE_ELEMENT = 'div[id="title"]'
                CANCEL_BTN_ELEMENT = 'input[value="Cancel"]'
                if "setting up your passkey" in driver.get_text(TITLE_ELEMENT).lower():
                    driver.wait_for_element_visible(
                        CANCEL_BTN_ELEMENT, timeout=wait_time
                    )
                    driver.click(CANCEL_BTN_ELEMENT)
                    return True
            except:
                pass
            retries += 1
            time.sleep(1)
        return False
    except:
        return False


def new_profile_logger(email_address, status, message):
    """
    Logs the status of the new profile creation process.
    """
    print(f"Logging for {email_address}: Status: {status}, Message: {message}")
    # Here you can implement actual logging to a file or database if needed.


########################


def password_use_unavailable_sb(driver):
    """
    Checks if the password is unavailable label appears.
    """
    try:
        PASSWORD_UNAVAILABLE_ELEMENT = 'div[role="alert"]'
        driver.wait_for_element_visible(PASSWORD_UNAVAILABLE_ELEMENT, timeout=wait_time)
        return (
            driver.get_text(PASSWORD_UNAVAILABLE_ELEMENT)
            .lower()
            .startswith("password sign-in isn't available")
        )
    except:
        return False


def click_join_family_link_btn_sb(driver, new_profile_data):
    try:
        wait_time = 30
        button = 'button[aria-label="Join now"]'
        driver.wait_for_element_visible(button, timeout=wait_time)
        time.sleep(3)
        driver.click(button)
        time.sleep(5)
        return True
    except:
        try:
            button = 'button[aria-label="Sign in"]'
            driver.wait_for_element_visible(button, timeout=wait_time)
            time.sleep(3)
            driver.click(button)
            password = new_profile_data.get("pass", "")
            recovery = new_profile_data.get("recovery", "")
            email = new_profile_data.get("email", "")
            time.sleep(2)
            while click_looks_good_button_sb(driver):
                time.sleep(3)
                print(f"{email} : Clicked looks good button")
            time.sleep(1)
            click_existing_account_smtp_sb(driver)
            time.sleep(2)
            click_use_your_password_button_sb(driver)
            time.sleep(2)
            enter_password_sb(driver, password=password)
            time.sleep(2)
            click_password_next_button_sb(driver)
            if password_use_unavailable_sb(driver):
                click_send_code_to_recovery_email_button_sb(driver)
                if enter_recovery_email_2_sb(driver, recovery):
                    click_password_next_button_sb(driver)
                    if email_login_limit_reached_sb(driver):
                        print(f"{email} : Login limit reached. Using password.")
                        click_use_your_password_button_sb(driver)
                        enter_password_sb(driver, password)
                        click_password_next_button_sb(driver)
                    else:
                        status, code = wait_for_code_sb(
                            email_token=new_profile_data.get("email_token", "")
                        )
                        if not status:
                            return False
                        enter_code_and_click_next_after_pass_change_sb(driver, code)
            else:
                click_existing_account_smtp_sb(driver)
                enter_password_sb(driver, password=password)
                click_password_next_button_sb(driver)
            click_looks_good_button_sb(driver)
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


def sucessfully_joined_microsoft_premium_sb(driver):
    try:
        CONGRATULATIONS_ELEMENT = "h1"
        label_element = driver.wait_for_element_visible(
            CONGRATULATIONS_ELEMENT, timeout=1
        )
        if (
            label_element.text.lower().startswith("you've already joined")
            or label_element.text.lower().startswith("congratulations")
            or label_element.text.lower().startswith(
                "looks like you already have a subscription"
            )
            or label_element.text.lower()
            .lower()
            .startswith("hmm... it looks like you're already in a family group")
        ):
            return True
        elif label_element.text.lower().startswith(
            "looks like there aren't any subscriptions available"
        ):
            return False
        return False
    except:
        return False


def link_is_invalid_sb(driver):
    try:
        INVALID_ELEMENT = "h1"
        invalid = driver.wait_for_element_visible(INVALID_ELEMENT, timeout=1)
        if invalid.text.lower() in [
            "try a different url",
            "looks like this invitation is invalid",
            "looks like this invitation link is not working",
        ]:
            return True
        return False
    except:
        return False


def looks_like_there_arent_microsoft_premium_sb(driver):
    try:
        CONGRATULATIONS_ELEMENT = "h1"
        label_element = driver.wait_for_element_visible(
            CONGRATULATIONS_ELEMENT, timeout=1
        )
        if label_element.text.lower().startswith(
            "looks like there aren't any subscriptions available"
        ):
            return True
        return False
    except:
        return False


def link_is_full_sb(driver):
    try:
        INVALID_ELEMENT = "h1"
        invalid = driver.wait_for_element_visible(INVALID_ELEMENT, timeout=1)
        if invalid.text.lower() in [
            "hmm... it looks like the family group is full",
        ]:
            return True
        return False
    except:
        return False


def use_link_to_join_family_acc_sb(driver, new_profile_data):
    try:
        # status, invite_url = get_family_link()
        status, invite_url = True, "https://aka.ms/5411d1e75ea64dfa839a0e53"
        email_address = new_profile_data.get("email")
        if status:
            _check_shutdown_requested()
            print("Using family url to join.")
            driver.get(invite_url)
            check_btn_retries = 0
            proceed = False
            while (check_btn_retries < 15) and (not proceed):
                _check_shutdown_requested()
                if click_join_family_link_btn_sb(driver, new_profile_data):
                    print(
                        f"{email_address}: Clicked join now button. Waiting for success message"
                    )
                    proceed = True
                elif sucessfully_joined_microsoft_premium_sb(driver):
                    print(f"{email_address}: Successfully joined Microsoft Premium.")
                    proceed = True
                elif link_is_invalid_sb(driver):
                    print(f"{email_address}: Link is invalid.")
                    not_working_links(invite_url)
                    return False
                time.sleep(1)
                check_btn_retries += 1
            if not proceed:
                print(
                    f"{email_address}: Loading timeout. Join now button not present. Link is invalid label not present"
                )
                return False
            success_message_retries = 0
            while success_message_retries < 20:
                _check_shutdown_requested()
                if sucessfully_joined_microsoft_premium_sb(driver):
                    # Update mother details here
                    if update_link_mother_details(new_profile_data, invite_url):
                        print(f"{email_address}: Saved premium mother details")
                    else:
                        print(f"{email_address}: Could not save premium mother details")
                    if return_link_to_extracted_family_links_table(invite_url):
                        print(
                            f"{email_address}: Returned link to extracted_family_links table"
                        )
                    update_link_usage_times(invite_url)
                    print(
                        f"{email_address}: Successfully joined premium using family link"
                    )
                    return True
                elif looks_like_there_arent_microsoft_premium_sb(driver):
                    print(
                        f"{email_address}: 'Looks like there aren't any subscriptions available' displayed. "
                    )
                    not_working_links(invite_url)
                    return False
                elif link_is_invalid_sb(driver):
                    print(f"{email_address}: Link is invalid.")
                    not_working_links(invite_url)
                    return False
                elif link_is_full_sb(driver):
                    print(f"{email_address}: Family group is full.")
                    successfully_worked_links(invite_url)
                    return False
                success_message_retries += 1
                _check_shutdown_requested()
                time.sleep(1.5)
            print(
                f"{email_address}: Waited for congratulations message and timed out after a minute"
            )
            return False
        else:
            if invite_url == "NO_LINK":
                print(f"NO family urls for preferred country: {PREFERRED_SMS_COUNTRY}")
                try:
                    _check_shutdown_requested()
                    driver.quit()
                except:
                    pass
                return "NO_LINK"
            else:
                print("Unable to get family url.")
                return False
    except Exception as E:
        _check_shutdown_requested()
        print(f"Exception: {E}")
        return False


def join_family_acc_sb(driver, new_profile_data):
    retries = 0
    while retries < 5:
        _check_shutdown_requested()
        join_status = use_link_to_join_family_acc_sb(driver, new_profile_data)
        if join_status == "NO_LINK" or (
            isinstance(join_status, tuple)
            and len(join_status) > 1
            and join_status[1] == "NO_LINK"
        ):
            return "NO_LINK"
        if join_status is True:
            return True
        retries += 1
        # connect_us_random()
        time.sleep(1)
    return False


def enter_smtp_code_sb(driver, code):
    """
    Enters code in otp field
    """
    try:
        wait_time = 10
        OTP_INPUT_ELEMENT = 'input[name="otc"]'
        otp_input_element = driver.wait_for_element_visible(
            OTP_INPUT_ELEMENT, timeout=wait_time
        )
        time.sleep(2)
        driver.clear_input(OTP_INPUT_ELEMENT)
        driver.send_keys(OTP_INPUT_ELEMENT, code)
        time.sleep(0.5)
        NEXT_BTN_ELEMENT = 'input[type="submit"]'
        next_btn_element = driver.wait_for_element_visible(
            NEXT_BTN_ELEMENT, timeout=wait_time
        )
        time.sleep(0.3)
        next_btn_element.click()
        time.sleep(0.5)
        return True
    except:
        return False


def setup_smtp_driver_sb(driver, verification_url, code):
    """
    Lauches chrome driver for login
    """
    try:
        retries = 0
        while retries < 5:
            try:
                driver.maximize()
                # time.sleep(2)
                driver.get(verification_url)
                if enter_smtp_code_sb(driver, code):
                    return True
            except:
                pass
            retries += 1
        return False
    except:
        return False


def click_continue_if_you_see_this_code_button_smtp_sb(driver):
    """
    Clicks the next button on gmail login
    """
    try:
        retries = 0
        while retries < 5:
            try:
                H1_ELEMENT = "h1"
                header_element = driver.wait_for_element_visible(
                    H1_ELEMENT, timeout=wait_time
                )
                time.sleep(1)
                if header_element.text.lower().startswith(
                    "continue if you see this code"
                ):
                    CONTINUE_BUTTON_ELEMENT = 'button[type="submit"]'
                    continue_button = driver.wait_for_element_visible(
                        CONTINUE_BUTTON_ELEMENT, timeout=wait_time
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


def is_let_this_app_access_your_info_page_sb(driver):
    """
    Clicks the stay signed in button after login
    """
    try:
        HEADER_ELEMENT = 'div[data-testid="appConsentTitle"]'
        header_element = driver.wait_for_element_visible(
            HEADER_ELEMENT, timeout=wait_time
        )
        if header_element.text.lower().startswith("let this app access your info"):
            return True
        else:
            return False
    except:
        return False


def smtp_accept_access_sb(driver):
    try:
        BUTTON_ELEMENT = 'button[type="submit"]'
        button_elements = driver.wait_for_element_visible(
            BUTTON_ELEMENT, timeout=wait_time
        )
        time.sleep(1)
        button_elements = driver.find_all(BUTTON_ELEMENT, wait_time)
        button_element = button_elements[
            [i.text.lower() for i in button_elements].index("accept")
        ]
        button_element.click()
        return True
    except:
        return False


def all_done_page_sb(driver):
    """
    Checks if page is all done page
    """
    try:
        SUCCESS_LABEL_ELEMENT = 'div[id="idDiv_Finish_ErrTxt"]'
        success_element = driver.wait_for_element_visible(
            SUCCESS_LABEL_ELEMENT, timeout=wait_time
        )
        time.sleep(3)
        success_element = driver.wait_for_element_visible(
            SUCCESS_LABEL_ELEMENT, timeout=wait_time
        )
        if success_element.text.lower().startswith("you're now signed in to"):
            return True
        else:
            return False
    except:
        return False


def entire_smtp_process_sb(driver, new_profile_data):
    try:
        email_address = new_profile_data.get("email")
        email = email_address
        password = new_profile_data.get("pass")
        recovery = new_profile_data.get("recovery")
        email_token = new_profile_data.get("email_token")
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
        status = setup_smtp_driver_sb(
            driver=driver, verification_url=verification_url, code=setup_code
        )
        if not status:
            return False, "Error setting up driver"
        print(f"{email_address} : Successfully set up driver")
        _check_shutdown_requested()
        time.sleep(1)
        click_existing_account_smtp_sb(driver)
        time.sleep(1)
        if click_continue_if_you_see_this_code_button_smtp_sb(driver):
            print(f"{email_address} : Clicked continue if you see this code button")
        else:
            print(
                f"{email_address} : Continue if you see this code button not found. Continuing without clicking it."
            )
            return (
                False,
                "Error clicking Continue if you see this code button not found",
            )
        _check_shutdown_requested()
        if enter_recovery_email_2_sb(driver, recovery):
            print(f"{email} : Entered recovery email. Clicking next button.")
            if click_send_code_button_sb(driver):
                print(f"{email} : Clicked send code button. Waiting for recovery code.")
            else:
                print(f"{email} : Error clicking send code button.")
            if email_login_limit_reached_sb(driver):
                print(f"{email} : Login limit reached. Using password.")
                click_use_your_password_button_sb(driver)
                print(f"{email} : Clicked use your password button.")
                enter_password_sb(driver, password)
                print(f"{email} : Entered password. Clicking next button.")
                time.sleep(2)
                click_password_next_button_sb(driver)
                print(f"{email} : Clicked next button. Password changed successfully.")
            else:
                print(
                    f"{email} : Recovery email page loaded. Waiting for recovery code."
                )
                status, code = wait_for_code_sb(email_token)
                print(f"{email} : Recovery code received: {code}")
                if not status:
                    print(
                        f"{email} : Recovery code not received. Cannot change password."
                    )
                    return False, "Recovery code not received"
                print(f"{email} : Entering recovery code and clicking next button.")
                enter_code_and_click_next_after_pass_change_sb(driver, code)
                print(
                    f"{email} : Recovery code entered. Password changed successfully."
                )
        elif enter_password_sb(driver=driver, password=password):
            print(f"{email}: Entered new password. Clicking next button.")
            time.sleep(2)
            click_password_next_button_sb(driver=driver)
            print(f"{email}: Clicked next button.")
        else:
            print(f"{email}: Error entering new password or recovery.")
        time.sleep(1)
        _check_shutdown_requested()
        time.sleep(1)
        if is_let_this_app_access_your_info_page_sb(driver):
            print(f"{email_address} : Accept access page displayed")
            if smtp_accept_access_sb(driver):
                print(f"{email_address} : Clicked access button")
        else:
            print(f"{email_address} : Accept access page NOT displayed")
        click_looks_good_button_sb(driver)
        if all_done_page_sb(driver):
            print(
                f"{email_address} : Manual signing completed successfully. Saving tokens"
            )
            result = app.acquire_token_by_device_flow(flow)
            _check_shutdown_requested()
            save_cache(cache)
            print(f"{email_address} : Successfully saved tokens")
            return True, "SUCCESS"
        else:
            print(f"{email_address} : Authorization UNSUCCESSFULL")
            return False, "PROCESS DONE BUT NO SUCCESS PAGE"
    except Exception as e:
        _check_shutdown_requested()
        return False, f"Undocumented error during SMTP process: {str(e)}"


def smtp_process_sb(driver, new_profile_data):
    retries = 0
    message = "Fail"
    while retries < 3:
        _check_shutdown_requested()
        try:
            status, message = entire_smtp_process_sb(driver, new_profile_data)
            if status:
                return True, message
            else:
                print(
                    f"{new_profile_data.get('email')} : SMTP ERROR -> {message} Retrying..."
                )
        except Exception as e:
            _check_shutdown_requested()
            click_looks_good_button_sb(driver)
            print(
                f"{new_profile_data.get('email')} : Exception during SMTP process: {str(e)}"
            )
        retries += 1
        time.sleep(3)
    print(f"{new_profile_data.get('email')} : Out of retries...")
    return False, message


def initialize_new_profile_sb(new_profile_data):
    """
    Creating a new chrome profile.
    A dictionary with email_address, and password
    """
    try:
        _check_shutdown_requested()
        print("\n")
        connect_new_random()
        time.sleep(0.5)
        _check_shutdown_requested()
        email_address = new_profile_data.get("email")
        password = new_profile_data.get("pass")
        recovery = new_profile_data.get("recovery")
        recovery_email = recovery
        status, email_token = get_email_token_sb(recovery_email=recovery)
        if not status:
            print(
                f"{email_address}: Error getting email token for recovery email: {email_token}"
            )
            new_profile_logger(
                email_address,
                "FAIL",
                "Error getting email token for recovery email",
            )
            return False, "Error getting email token for recovery email"
        print(f"{email_address}: Got email token for recovery email")
        new_profile_data["email_token"] = email_token
        new_profile_data_original = new_profile_data.copy()
        retries = 0
        driver_success = False
        print(f"{email_address}: Initializing browser driver")
        while (retries < 3) and (not driver_success):
            try:
                status, driverdata, error = initialize_new_profile_driver()
                if status:
                    print(f"{email_address}: Driver initialized successfully")
                    driver, user_path, proxy = driverdata.values()
                    time.sleep(0.5)
                    driver.maximize()
                    time.sleep(0.5)
                    driver.get(MICROSOFT_LOGIN_URL)
                    time.sleep(0.5)
                    driver_success = True
            except:
                try:
                    driver.quit()
                except:
                    pass
                retries += 1
        _check_shutdown_requested()
        if not driver_success:
            print(f"{email_address}: Error initializing new browser driver")
            new_profile_logger(
                email_address,
                "FAIL",
                "Error initializing new browser driver. Network or proxy error",
            )
            return False, "Error initializing new browser driver instance"
        _check_shutdown_requested()
        if not enter_email_sb(driver=driver, email_address=email_address):
            print(f"{email_address}: Error entering email")
            new_profile_logger(email_address, "FAIL", "Error loading login page")
            return False, "Error loading login page"
        time.sleep(1)
        _check_shutdown_requested()
        if not click_next_button_sb(driver=driver):
            print(f"{email_address}: Error clicking next button after entering email")
            new_profile_logger(
                email_address, "FAIL", "Error clicking next button after entering email"
            )
            return False, "Error clicking next button after entering email"
        time.sleep(2)
        _check_shutdown_requested()
        if not enter_recovery_email_2_sb(driver, recovery_email):
            print(f"{email_address}: Failed to enter recovery email")
            new_profile_logger(
                email_address, "FAIL", "Error clicking next button after entering email"
            )
            return False, "Error clicking next button after entering email"
        time.sleep(2)
        _check_shutdown_requested()
        if not click_send_code_button_sb(driver):
            print(f"{email_address}: Failed to click send code button")
            new_profile_logger(email_address, "FAIL", "Error clicking send code button")
            return False, "Error clicking send code button"
        _check_shutdown_requested()
        code_status, code = wait_for_code_sb(email_token=email_token)
        _check_shutdown_requested()
        if not code_status:
            print(f"{email_address}: Failed to get code from recovery email")
            new_profile_logger(
                email_address, "FAIL", "Error getting code from recovery email"
            )
            return False, "Error getting code from recovery email"
        print(f"{email_address}: Got code from recovery email: {code}")
        _check_shutdown_requested()
        if not enter_code_and_click_next_after_pass_change_sb(driver, code):
            print(f"{email_address}: Failed to enter code")
            new_profile_logger(email_address, "FAIL", "Error entering code")
            return False, "Error entering code"
        _check_shutdown_requested()
        print(f"{email_address}: Checking if updating terms page is present")
        time.sleep(1)
        if click_next_if_is_updating_terms_page_sb(driver):
            print(f"{email_address}: Clicked next on updating terms page")
        else:
            print(f"{email_address}: No updating terms page found")
        _check_shutdown_requested()
        print(f"{email_address}: Checking if account has been locked page is present")
        time.sleep(1)
        if is_your_account_has_been_locked_page_sb(driver):
            print(f"{email_address}: Account has been locked page found")
            new_profile_logger(
                email_address, "FAIL", "Account has been locked page found"
            )
            return False, "Account has been locked page found"
        time.sleep(1)
        print(f"{email_address}: Is your security info")
        if click_looks_good_button_sb(driver):
            print(f"{email_address}: Clicked looks good button")
        print(f"{email_address}: Checking if quick note page is present")
        time.sleep(1)
        if click_next_if_a_quick_note_page_sb(driver):
            print(f"{email_address}: Clicked next on quick note page")
        else:
            print(f"{email_address}: No quick note page found")
        _check_shutdown_requested()
        print(f"{email_address}: Checking if passkey setup page is present")
        time.sleep(1)
        if cancel_setup_passkey_sb(driver):
            print(f"{email_address}: Cancelled passkey setup page")
        else:
            print(f"{email_address}: No passkey setup page found")
        _check_shutdown_requested()
        time.sleep(1)
        print(f"{email_address}: Checking if stay signed in page is present")
        if click_stay_signed_in_button_sb(driver):
            print(f"{email_address}: Clicked stay signed in button")
        else:
            print(f"{email_address}: No stay signed in button/btn found")
        _check_shutdown_requested()
        time.sleep(1)
        recovery_email_page_popped_up = "YES"
        temp_email = recovery_email
        has_recovery_phone = "NO"
        recovery_phone_number = ""
        _check_shutdown_requested()
        print(f"{email_address}: Finalizing signin")
        _check_shutdown_requested()
        close_other_tabs(driver)
        # click_looks_good_button_sb(driver)
        _check_shutdown_requested()
        joined_microsoft_premium = "NO"
        print(f"{email_address}: SUCCESSFULL LOGIN!")
        _check_shutdown_requested()
        update_accounts_data(
            email=email_address,
            profile_dir="NONE",
            proxy_used="NONE",
            password=password,
            has_recovery_email=recovery_email_page_popped_up,
            recovery_email=temp_email,
            has_recovery_phone=has_recovery_phone,
            recovery_phone_number=recovery_phone_number,
            joined_microsoft_premium=joined_microsoft_premium,
        )
        _check_shutdown_requested()
        status, error = change_acc_pass_sb(driver, new_profile_data)
        _check_shutdown_requested()
        if status:
            update_accounts_data(email=email_address, password=error)
            new_profile_data["pass"] = error
        else:
            print(f"{email_address}: Error changing password: {error}")
            new_profile_logger(
                email_address,
                "FAIL",
                f"Error changing password: {error}",
            )
            return False, f"Error changing password: {error}"
        print(f"{email_address}: Joining microsoft premium")
        driver.refresh()
        _check_shutdown_requested()
        join_status = join_family_acc_sb(driver, new_profile_data)
        if join_status is True:
            joined_microsoft_premium = "YES"
            premium_logger(email_address, password, temp_email)
            print(f"{email_address}: Successfully joined microsoft premium")
        elif join_status == "NO_LINK":
            print(
                f"{email_address}: No family links available. Returning to signal wait."
            )
            return False, "NO_LINK"
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
        _check_shutdown_requested()
        status, error = smtp_process_sb(driver, new_profile_data)
        if status:
            print(f"{email_address}: Finalising")
            new_profile_logger(
                email_address,
                "SUCCESS",
                "Login successfull",
            )
            update_accounts_data(email=email_address, save_smtp="YES")
            print(f"{email_address}: Successfully set up SMTP")
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
            # driver.quit()
            # processed_email(new_profile_data_original)
            pass
        except:
            pass
        print("\n--------------------------------------\n")


def failed_smtp(email_address, password, temp_email):
    return True


def not_working_links(invite_url):
    return True


def update_link_mother_details(new_profile_data, invite_url):
    return True


def return_link_to_extracted_family_links_table(invite_url):
    return True


def update_link_usage_times(invite_url):
    return True


def successfully_worked_links(invite_url):
    return True


def premium_logger(email_address, password, temp_email):
    return True


def get_db_connection():
    try:
        DB_HOST = "68.183.208.150"
        DB_USER = "root"
        DB_PASSWORD = "root101."
        DB_NAME = "oneapp"
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


def execute_db_action(action, retries=7, delay=10):
    attempt = 1
    while attempt <= retries:
        try:
            _check_shutdown_requested()
            return action()
        except Exception as exc:
            _check_shutdown_requested()
            if attempt == retries:
                raise
            print(
                f"Database action failed (attempt {attempt}/{retries}): {exc}. Retrying in {delay} seconds..."
            )
            time.sleep(delay)
            attempt += 1


def load_cc_action():
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError("Unable to connect to database")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT cache_bin_file FROM cache_bins2 WHERE server_ip = %s AND bot_type = %s ORDER BY date_time DESC LIMIT 1",
        (SERVER_IP, BOT_TYPE),
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result


def load_cache():
    try:
        cache = msal.SerializableTokenCache()
        try:
            result = execute_db_action(load_cc_action, retries=7, delay=10)
        except Exception as e:
            print(f"Error loading cache after retries: {e}")
            return cache
        if result and result[0]:
            cache.deserialize(result[0].decode("utf-8"))
        return cache
    except Exception as e:
        print(f"Error loading cache: {e}")
        return msal.SerializableTokenCache()


def save_cache(cache):
    try:
        if not cache.has_state_changed:
            return
        serialized_cache = cache.serialize()

        def save_action():
            _check_shutdown_requested()
            conn = get_db_connection()
            if conn is None:
                raise RuntimeError("Unable to connect to database")
            cursor = conn.cursor()
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

        try:
            execute_db_action(save_action, retries=10, delay=10)
        except Exception as e:
            _check_shutdown_requested()
            print(f"Error saving cache after retries: {e}")
    except Exception as e:
        print(f"Error saving cache: {e}")


PREFERRED_SMS_COUNTRY = "BITCHLAND"
MODE = "APP1"
SERVER_IP = "0.1.0.1"
BOT_TYPE = "old_hotmailbot"
CLIENT_ID = "e62beeb7-8a9b-4637-b57f-f8601c0d13f5"
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["https://graph.microsoft.com/.default"]

data = "clasdjhobellk@outlook.com,zYBAlU71,veronicacooley4281@affworker.com"
new_profile_data = {
    "email": data.split(",")[0],
    "pass": data.split(",")[1],
    "recovery": data.split(",")[2],
}

connect_new_random()
driver = initialize_new_profile_sb(new_profile_data)
# change_acc_pass_sb(driver, new_profile_data)
# invite_url = "https://aka.ms/5411d1e75ea64dfa839a0e53"
