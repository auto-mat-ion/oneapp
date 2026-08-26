import json
import os
import random
import time
from datetime import datetime, timedelta, timezone

import mysql.connector

from utils.server_ip_helper import get_server_ip


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

try:
    with open(SETTINGS_PATH, "r", encoding="utf-8") as handle:
        APP_SETTINGS = json.load(handle).get("app", {})
except (OSError, json.JSONDecodeError):
    APP_SETTINGS = {}

DB_HOST = APP_SETTINGS.get("DB_HOST")
DB_USER = APP_SETTINGS.get("DB_USER")
DB_PASSWORD = APP_SETTINGS.get("DB_PASSWORD")
DB_NAME = APP_SETTINGS.get("DB_NAME")
SERVER_IP = get_server_ip()


def _parse_action_record(server_ip, action):
    """Return normalized action records from a tracker row."""
    try:
        payload = json.loads(action)
    except (TypeError, json.JSONDecodeError):
        payload = None

    if isinstance(payload, dict):
        if "server_ip" in payload:
            payload = [payload]
        else:
            payload = [
                {
                    "server_ip": payload_server_ip,
                    **payload_data,
                }
                for payload_server_ip, payload_data in payload.items()
                if isinstance(payload_data, dict)
            ]
    if isinstance(payload, list):
        return [
            {
                "server_ip": str(item.get("server_ip", "")).strip(),
                "action": item.get("action"),
                "country": item.get("country"),
            }
            for item in payload
            if isinstance(item, dict) and item.get("server_ip") and item.get("action")
        ]

    action_text = str(action or "").strip()
    if not action_text or not server_ip:
        return []

    action_name, separator, country = action_text.rpartition(":")
    if not separator:
        action_name, country = action_text, None
    return [
        {
            "server_ip": str(server_ip).strip(),
            "action": action_name,
            "country": country,
        }
    ]


def get_signal_from_db():
    """Get this server's newest recent action and country from the tracker."""
    for attempt in range(1, 6):
        now_utc = datetime.now(timezone.utc)
        cutoff_utc = now_utc - timedelta(minutes=3)
        connection = None
        cursor = None

        try:
            connection = mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
            )
            cursor = connection.cursor()
            cursor.execute(
                """
				SELECT server_ip, action
				FROM familybot_actions_tracker
				WHERE date_time >= %s AND date_time <= %s
				ORDER BY date_time ASC, action_id ASC
				""",
                (cutoff_utc, now_utc),
            )

            actions_by_server = {}
            for server_ip, action in cursor.fetchall():
                for record in _parse_action_record(server_ip, action):
                    actions_by_server[record["server_ip"]] = record

            signal = actions_by_server.get(str(SERVER_IP).strip())
            if signal:
                return True, signal["action"], signal["country"]
            return False, None, None
        except Exception as exc:
            print(
                f"Error getting action signal from database (attempt {attempt}/5): {exc}"
            )
            if attempt < 5:
                time.sleep(1)
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    return False, None, None


def keep_alive(retries=5, delay=3):
    """Update this server's status while the manager waits for a signal."""
    for attempt in range(1, retries + 1):
        connection = None
        cursor = None
        try:
            connection = mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
            )
            cursor = connection.cursor()
            now_utc = datetime.now(timezone.utc)
            cursor.execute(
                "SELECT server_id FROM server_status_family_and_hotmail WHERE server_ip = %s",
                (SERVER_IP,),
            )
            existing_row = cursor.fetchone()

            if existing_row:
                cursor.execute(
                    """
                    UPDATE server_status_family_and_hotmail
                    SET last_uptime = %s, current_action = %s
                    WHERE server_ip = %s
                    """,
                    (now_utc, "waiting for signal", SERVER_IP),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO server_status_family_and_hotmail
                    (server_ip, last_uptime, current_action)
                    VALUES (%s, %s, %s)
                    """,
                    (SERVER_IP, now_utc, "waiting for signal"),
                )

            connection.commit()
            return True
        except (mysql.connector.Error, OSError) as exc:
            print(f"Manager keep_alive failed (attempt {attempt}/{retries}): {exc}")
            if attempt < retries:
                time.sleep(delay)
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    return False


def runner():
    """Poll for a server action and run the requested bot."""
    from bots.familybot import run_familybot
    from bots.hotmailbot import run_hotmailbot

    print(
        "\n\n============================================================================\nWaiting for a signal..."
    )

    while True:
        keep_alive()
        status, action, country = get_signal_from_db()
        if status and action == "run_familybot":
            print(
                f"Signal received: {action} for country: {country}\n ============================================================================="
            )
            return run_familybot(country)
        if status and action == "run_hotmailbot":
            print(
                f"Signal received: {action} for country: {country}\n ============================================================================="
            )
            return run_hotmailbot(country)

        time.sleep(random.uniform(40, 55))
