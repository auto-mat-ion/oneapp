import json
import os
import re
import time
from datetime import datetime
from selenium.webdriver.support.wait import WebDriverWait

from automation import (
    Driver,
    chrome_location,
    connect_us_random,
    close_other_tabs,
    get_fakey_data,
)

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


def main():
    selected_country = choose_country()
    count = ask_positive_integer("Enter number of fake details to collect: ")

    output_filename = "utils/fake_details.json"
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


if __name__ == "__main__":
    main()
