import json
import os
import re
import time
from datetime import datetime
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from seleniumbase import Driver
import subprocess
import random
import pyautogui


EXPRESSVPN_CMD = "C:\\Program Files (x86)\\ExpressVPN\\services\\ExpressVPN.CLI.exe"


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


AVAILABLE_COUNTRIES = ["united states", "sweden", "poland", "norway"]
COUNTRY_DISPLAY = {
    "united states": "United States",
    "sweden": "Sweden",
    "poland": "Poland",
    "norway": "Norway",
}


def format_choice(choice: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", choice.strip().lower())


def choose_country():
    print("Available countries:")
    for index, country in enumerate(AVAILABLE_COUNTRIES, start=1):
        print(f"  {index}. {COUNTRY_DISPLAY[country]}")

    while True:
        choice = input("Select country by number or name: ").strip()
        if not choice:
            print("Please enter a country number or name.")
            continue

        numeric_choice = choice.split(".")[0].strip()
        if numeric_choice.isdigit():
            index = int(numeric_choice) - 1
            if 0 <= index < len(AVAILABLE_COUNTRIES):
                return AVAILABLE_COUNTRIES[index]
            print("Invalid number, try again.")
            continue

        cleaned = format_choice(choice)
        for country in AVAILABLE_COUNTRIES:
            if cleaned == format_choice(country):
                return country
            if cleaned == format_choice(COUNTRY_DISPLAY[country]):
                return country

        print("Country not found, try again.")


def ask_positive_integer(prompt_text: str):
    while True:
        value = input(prompt_text).strip()
        if not value:
            print("Please enter a number.")
            continue
        if not value.isdigit():
            print("Enter a valid positive integer.")
            continue
        count = int(value)
        if count <= 0:
            print("Number must be greater than zero.")
            continue
        return count


def save_records(file_path: str, records: list):
    with open(file_path, "w", encoding="utf-8") as output_file:
        json.dump(records, output_file, indent=2, ensure_ascii=False)


def save_records_with_country(
    file_path: str, records: list, country: str, full_data: dict
):
    """
    Save records preserving the country-keyed dict structure.
    """
    full_data[country] = records
    with open(file_path, "w", encoding="utf-8") as output_file:
        json.dump(full_data, output_file, indent=2, ensure_ascii=False)


# Alias for backward compatibility
def save_records(
    file_path: str, records: list, country: str = None, full_data: dict = None
):
    if country is not None and full_data is not None:
        save_records_with_country(file_path, records, country, full_data)
    else:
        with open(file_path, "w", encoding="utf-8") as output_file:
            json.dump(records, output_file, indent=2, ensure_ascii=False)


def load_records(file_path: str, country: str = None) -> tuple:
    """
    Load records from file. Returns (records_list, full_data_dict)
    - records_list: list of records for the selected country (for appending)
    - full_data_dict: the full file data structure (for preserving other countries)
    """
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Handle both old dict structure (country-keyed) and new list structure
                if isinstance(data, dict):
                    # Old format: {country: [records], ...}
                    records = data.get(country, []) if country else []
                    return records, data
                elif isinstance(data, list):
                    # New format: [records] - convert to dict for consistency
                    records = data if country is None else []
                    return records, {country: records} if country else {}
                return [], {}
        except (json.JSONDecodeError, IOError):
            return [], {}
    return [], {}


def is_valid_record(record: dict) -> bool:
    for value in record.values():
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
    return True


def scraper():
    selected_country = choose_country()
    count = ask_positive_integer("Enter number of fake details to collect: ")

    output_filename = "fake_details.json"
    output_path = os.path.abspath(output_filename)
    records, full_data = load_records(output_path, selected_country)
    initial_count = len(records)

    print(f"Saving records to {output_path}")
    print(f"Existing records: {initial_count}")
    print("Press Ctrl+C to stop early; saved records will remain in the output file.")

    driver = None
    try:
        connect_us_random()

        driver = Driver(
            uc=True,
            # binary_location=chrome_location,
            # extension_dir="utils/adblock",
            locale_code="en",
        )
        driver.maximize_window()

        for index in range(count):
            time.sleep(1)
            success, data = get_fakey_data(driver, country=selected_country)
            if not success:
                print(f"Failed to fetch record {index + 1}/{count}. Retrying...")
                continue

            record = {"country": COUNTRY_DISPLAY[selected_country], **data}
            record["record_index"] = index + 1
            if not is_valid_record(record):
                print(f"Skipping incomplete record {index + 1}/{count}.")
                continue

            records.append(record)
            save_records(output_path, records, selected_country, full_data)
            print(f"Saved record {index + 1}/{count}")

    except KeyboardInterrupt:
        print(f"\nStopped early.")
    except Exception as exc:
        print(f"Unexpected error: {exc}")
    finally:
        if driver:
            try:
                close_other_tabs(driver)
                driver.quit()
            except Exception:
                pass

    added_records = len(records) - initial_count
    total_records = len(records)
    print(f"\n--- Summary ---")
    print(f"Records added: {added_records}")
    print(f"Total records: {total_records}")
    if total_records > 0:
        print(f"Output file: {output_path}")
    else:
        print("No records were saved.")
