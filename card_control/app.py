from datetime import datetime, timezone
import json
import os

import mysql.connector
import streamlit as st


DB_CONFIG = {
    "host": os.getenv("CARD_CONTROL_DB_HOST", "sql5.freesqldatabase.com"),
    "database": os.getenv("CARD_CONTROL_DB_NAME", "sql5836164"),
    "user": os.getenv("CARD_CONTROL_DB_USER", "sql5836164"),
    "password": os.getenv("CARD_CONTROL_DB_PASSWORD", "lIDbIaPyzv"),
    "port": int(os.getenv("CARD_CONTROL_DB_PORT", "3306")),
}
COUNTRIES = ("poland", "poland2", "sweden", "italy")


def get_utc_datetime():
    """Return the current UTC time in the format used by MySQL DATETIME."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def record_action(action, country=None):
    payload = [{"server_ip": "all", "action": action}]
    if country is not None:
        payload[0]["country"] = country

    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        cursor.execute("TRUNCATE TABLE card_control")
        cursor.execute(
            """
            INSERT INTO card_control (server_ip, date_time, action)
            VALUES (%s, %s, %s)
            """,
            ("all", get_utc_datetime(), json.dumps(payload)),
        )
        connection.commit()
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


st.set_page_config(page_title="Control", page_icon="CC", layout="centered")
st.title("Control")
st.caption("Send a command to all card-control workers.")

country = st.selectbox("Country", COUNTRIES)
start_clicked, pause_clicked, resume_clicked, shutdown_clicked = st.columns(4)

with start_clicked:
    if st.button("Start", type="primary", use_container_width=True):
        try:
            with st.spinner("Sending start command..."):
                record_action("run_familybot", country)
            st.success(f"Start command sent for {country}.")
        except mysql.connector.Error as error:
            st.error(f"Could not send start command: {error}")

with pause_clicked:
    if st.button("Pause", use_container_width=True):
        try:
            with st.spinner("Sending pause command..."):
                record_action("pause")
            st.success("Pause command sent.")
        except mysql.connector.Error as error:
            st.error(f"Could not send pause command: {error}")

with resume_clicked:
    if st.button("Resume", use_container_width=True):
        try:
            with st.spinner("Sending resume command..."):
                record_action("resume")
            st.success("Resume command sent.")
        except mysql.connector.Error as error:
            st.error(f"Could not send resume command: {error}")

with shutdown_clicked:
    if st.button("Shutdown", use_container_width=True):
        try:
            with st.spinner("Sending shutdown command..."):
                record_action("shutdown")
            st.success("Shutdown command sent.")
        except mysql.connector.Error as error:
            st.error(f"Could not send shutdown command: {error}")
