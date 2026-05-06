import os

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

try:
    import mysql.connector
except ImportError:
    mysql = None

THE_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_bot_settings():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(BASE_DIR, "../bots/settings.json")

    try:
        with open(settings_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data.get("app", {})
    except Exception:
        return {}


def get_db_config():
    env = load_bot_settings()
    return {
        "host": env.get("DB_HOST", "localhost"),
        "user": env.get("DB_USER", "root"),
        "password": env.get("DB_PASSWORD", ""),
        "database": env.get("DB_NAME", "oneapp"),
        "charset": "utf8mb4",
        "use_unicode": True,
    }


def get_db_connection():
    if mysql is None:
        st.error(
            "mysql-connector-python is not installed. Install it with `pip install mysql-connector-python`."
        )
        return None
    try:
        return mysql.connector.connect(**get_db_config())
    except Exception as exc:
        st.error(f"Unable to connect to database: {exc}")
        return None


def test_db_connection():
    if mysql is None:
        return False, (
            "mysql-connector-python is not installed. Install it with `pip install mysql-connector-python`."
        )
    try:
        conn = mysql.connector.connect(**get_db_config())
        conn.close()
        return True, "Database connection successful."
    except Exception as exc:
        return False, f"Unable to connect to database: {exc}"


def create_database():
    """Create the database and all tables from db_schema.sql"""
    schema_path = os.path.join(THE_BASE_DIR, "db_schema.sql")
    if not os.path.exists(schema_path):
        return False, "db_schema.sql not found"

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        # Connect without specifying database to create it
        config = get_db_config()
        config_no_db = {k: v for k, v in config.items() if k != "database"}
        conn = mysql.connector.connect(**config_no_db)
        cursor = conn.cursor()

        # Execute the schema
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)

        conn.commit()
        cursor.close()
        conn.close()
        return True, "Database created successfully"
    except Exception as exc:
        return False, f"Error creating database: {str(exc)}"


def update_database_tables():
    """Update database tables by creating missing ones from db_schema.sql"""
    schema_path = os.path.join(THE_BASE_DIR, "db_schema.sql")
    if not os.path.exists(schema_path):
        return False, "db_schema.sql not found"

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        conn = get_db_connection()
        if conn is None:
            return False, "No database connection"

        cursor = conn.cursor()

        # Extract only CREATE TABLE statements
        statements = schema_sql.split(";")
        for statement in statements:
            statement = statement.strip()
            if statement.upper().startswith("CREATE TABLE"):
                cursor.execute(statement)

        conn.commit()
        cursor.close()
        conn.close()
        return True, "Database tables updated successfully"
    except Exception as exc:
        return False, f"Error updating tables: {str(exc)}"


def parse_email_file(uploaded_file):
    content = uploaded_file.read().decode("utf-8", errors="replace")
    rows = [row.strip() for row in content.splitlines() if row.strip()]
    data = []
    for line in rows:
        if ":" in line:
            email, password = line.split(":", 1)
            data.append({"email": email.strip(), "pass": password.strip()})
    return pd.DataFrame(data)


def parse_card_file(uploaded_file):
    content = uploaded_file.read().decode("utf-8", errors="replace")
    rows = [row.strip() for row in content.splitlines() if row.strip()]
    data = []
    for line in rows:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 3:
            try:
                data.append(
                    {
                        "card_number": int(parts[0]),
                        "expiry_month_year": parts[1],
                        "cvv": str(parts[2]),
                    }
                )
            except ValueError:
                continue
    return pd.DataFrame(data)


def parse_smtp_file(uploaded_file):
    content = uploaded_file.read().decode("utf-8", errors="replace")
    rows = [row.strip() for row in content.splitlines() if row.strip()]
    if rows and all(
        field in rows[0].lower() for field in ["email", "pass", "recovery"]
    ):
        rows = rows[1:]
    data = []
    for line in rows:
        if "," in line:
            parts = [part.strip() for part in line.split(",")]
        elif ":" in line:
            parts = [part.strip() for part in line.split(":")]
        else:
            continue
        if len(parts) >= 3:
            email, password, recovery = parts[0], parts[1], parts[2]
            data.append({"email": email, "password": password, "recovery": recovery})
    return pd.DataFrame(data)


def parse_email_sender_input_accounts(uploaded_file):
    content = uploaded_file.read().decode("utf-8", errors="replace")
    rows = [row.strip() for row in content.splitlines() if row.strip()]
    if rows and all(
        field in rows[0].lower() for field in ["email", "pass", "recovery"]
    ):
        rows = rows[1:]
    data = []
    for line in rows:
        if "," in line:
            parts = [part.strip() for part in line.split(",")]
        elif ":" in line:
            parts = [part.strip() for part in line.split(":")]
        else:
            continue
        if len(parts) >= 3:
            email, password, recovery = parts[0], parts[1], parts[2]
            data.append({"email": email, "pass": password, "recovery": recovery})
    return pd.DataFrame(data)


def parse_text_list(uploaded_file, column_name):
    content = uploaded_file.read().decode("utf-8", errors="replace")
    values = [line.strip() for line in content.splitlines() if line.strip()]
    if values and values[0].strip().lower() == column_name.lower():
        values = values[1:]
    return pd.DataFrame({column_name: values})


def parse_cache_bin_file(uploaded_file):
    # For cache_bins, we upload binary files, but since insert_into_db expects DataFrame,
    # we'll create a DataFrame with the binary data
    binary_data = uploaded_file.read()
    return pd.DataFrame({"cache_bin_file": [binary_data]})


def parse_family_links_file(uploaded_file):
    content = uploaded_file.read().decode("utf-8", errors="replace")
    rows = [row.strip() for row in content.splitlines() if row.strip()]
    data = []
    for line in rows:
        # parts = [part.strip() for part in line.split(":")]
        # if len(parts) >= 4:
        # email, password, recovery, link = parts[0], parts[1], parts[2], parts[3]
        data.append(
            {
                "email": "manual_upload",
                "password": "manual_upload",
                "recovery": "manual_upload",
                "link": line.strip(),
            }
        )
    return pd.DataFrame(data)


def parse_fake_json(uploaded_file):
    payload = json.load(uploaded_file)
    data = []

    if isinstance(payload, dict):
        for country, value in payload.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        data.append(
                            {
                                "country": country,
                                "address_line1": item.get("address_line1", ""),
                                "city": item.get("city", ""),
                                "state": item.get("state", ""),
                                "postal_code": item.get("postal_code", ""),
                            }
                        )
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                data.append(
                    {
                        "country": item.get("country", ""),
                        "address_line1": item.get("address_line1", ""),
                        "city": item.get("city", ""),
                        "state": item.get("state", ""),
                        "postal_code": item.get("postal_code", ""),
                    }
                )

    return pd.DataFrame(data)


def insert_into_db(table_name, df, server_ip=None, bot_type=None):
    conn = get_db_connection()
    if conn is None:
        return False, "No database connection"
    try:
        cursor = conn.cursor()
        if table_name == "smtp_accounts":
            columns = "server_ip, bot_type, email, pass, recovery"
            placeholders = "%s, %s, %s, %s, %s"
            values = [
                (server_ip, bot_type, row.email, row.password, row.recovery)
                for row in df.itertuples(index=False)
            ]
        elif table_name == "cache_bins":
            columns = "server_ip, bot_type, date_time, cache_bin_file"
            placeholders = "%s, %s, %s, %s"
            values = [
                (server_ip, bot_type, datetime.now(), row.cache_bin_file)
                for row in df.itertuples(index=False)
            ]
        elif table_name == "familybot_extracted_family_links":
            columns = "server_ip, bot_type, date_time, email, pass, recovery, link"
            placeholders = "%s, %s, %s, %s, %s, %s, %s"
            values = [
                (
                    server_ip,
                    bot_type,
                    datetime.now(),
                    row.email,
                    row.password,
                    row.recovery,
                    row.link,
                )
                for row in df.itertuples(index=False)
            ]
        elif table_name == "password_changer_accounts":
            columns = "email, pass, recovery"
            placeholders = "%s, %s, %s"
            values = [
                (row.email, row.password, row.recovery)
                for row in df.itertuples(index=False)
            ]
        else:
            columns = ", ".join(df.columns)
            placeholders = ", ".join(["%s"] * len(df.columns))
            values = [tuple(row) for row in df.itertuples(index=False, name=None)]
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        cursor.executemany(query, values)
        conn.commit()
        inserted = cursor.rowcount
        cursor.close()
        conn.close()
        return True, f"Inserted {inserted} rows into {table_name}."
    except Exception as exc:
        return False, str(exc)


def validate_dataframe(table_name, df):
    if df.empty:
        return False, "No valid data was found in the uploaded file."
    if table_name == "input_emails":
        if not all(col in df.columns for col in ["email", "pass"]):
            return False, "Table input_emails requires columns: email, pass"
    if table_name == "email_sender_input_accounts":
        if not all(col in df.columns for col in ["email", "pass", "recovery"]):
            return (
                False,
                "Table email_sender_input_accounts requires columns: email, pass, recovery",
            )
    if table_name == "sender_hyperlink_text":
        if "hyperlink_text" not in df.columns:
            return False, "Table sender_hyperlink_text requires column: hyperlink_text"
    if table_name == "sender_link":
        if "link" not in df.columns:
            return False, "Table sender_link requires column: link"
    if table_name == "sender_recipients":
        if "recipient_email" not in df.columns:
            return False, "Table sender_recipients requires column: recipient_email"
    if table_name == "sender_subjects":
        if "subject" not in df.columns:
            return False, "Table sender_subjects requires column: subject"
    if table_name == "sender_texts":
        if "text" not in df.columns:
            return False, "Table sender_texts requires column: text"
    if table_name == "familybot_first_names":
        if "firstnames" not in df.columns:
            return False, "Table familybot_first_names requires column: firstnames"
    if table_name == "familybot_surnames":
        if "surnames" not in df.columns:
            return False, "Table familybot_surnames requires column: surnames"
    if table_name == "familybot_card_details":
        if not all(
            col in df.columns for col in ["card_number", "expiry_month_year", "cvv"]
        ):
            return (
                False,
                "Table familybot_card_details requires columns: card_number, expiry_month_year, cvv",
            )
    if table_name == "familybot_fake_details":
        if not all(
            col in df.columns
            for col in ["country", "address_line1", "city", "state", "postal_code"]
        ):
            return (
                False,
                "Table familybot_fake_details requires columns: country, address_line1, city, state, postal_code",
            )
    if table_name == "family_link":
        if "link" not in df.columns:
            return False, "Table family_link requires column: link"
    if table_name in ["smtp_accounts", "password_changer_accounts"]:
        if not all(col in df.columns for col in ["email", "password", "recovery"]):
            return (
                False,
                f"Table {table_name} requires columns: email, password, recovery",
            )
    if table_name == "cache_bins":
        if "cache_bin_file" not in df.columns:
            return False, "Table cache_bins requires column: cache_bin_file"
    if table_name == "familybot_extracted_family_links":
        if not all(
            col in df.columns for col in ["email", "password", "recovery", "link"]
        ):
            return (
                False,
                "Table familybot_extracted_family_links requires columns: email, password, recovery, link",
            )
    return True, "Data looks good."


def main():
    st.set_page_config(page_title="FamilyBot Upload", page_icon="🧾", layout="wide")
    st.markdown(
        """
        <style>
            .stApp { background: linear-gradient(135deg, #2f2fa2, #4e7bdb); }
            .block-container { padding: 2rem 3rem; }
            .stButton>button { background: #1f5aff; color: white; border-radius: 10px; }
        </style>
    """,
        unsafe_allow_html=True,
    )

    st.title("FamilyBot Database Uploader")
    st.markdown(
        "Upload CSV or JSON files directly into MySQL tables with a simple interface."
    )

    table_options = {
        "input_emails": "Email Accounts",
        "email_sender_input_accounts": "Email Sender Input Accounts",
        "sender_hyperlink_text": "Sender Hyperlink Text",
        "sender_link": "Sender Links",
        "sender_recipients": "Sender Recipients",
        "sender_subjects": "Sender Subjects",
        "sender_texts": "Sender Texts",
        "familybot_first_names": "First Names",
        "familybot_surnames": "Surnames",
        "familybot_card_details": "Card Details",
        "familybot_fake_details": "Fake Details",
        "family_link": "Family Links",
        "familybot_extracted_family_links": "Extracted Family Links",
        # "smtp_accounts": "SMTP Accounts",
        "password_changer_accounts": "Password Changer Accounts",
        "cache_bins": "Cache Bin Files",
    }

    country_tables = [
        "email_sender_input_accounts",
        "sender_hyperlink_text",
        "sender_link",
        "sender_recipients",
        "sender_subjects",
        "sender_texts",
    ]

    country_options = [
        "United States",
        "United Kingdom",
        "Poland",
        "Sweden",
    ]

    table_name = st.selectbox(
        "Select destination table",
        list(table_options.keys()),
        format_func=lambda x: table_options[x],
    )
    st.markdown(f"**Target table:** `{table_name}`")

    file_types = (
        ["json"]
        if table_name == "familybot_fake_details"
        else ["bin", "dat", "cache"]
        if table_name == "cache_bins"
        else ["txt", "csv"]
    )
    uploaded_file = st.file_uploader("Choose your file", type=file_types)

    selected_country = None
    if uploaded_file is not None:
        if table_name == "input_emails":
            df = parse_email_file(uploaded_file)
        elif table_name == "email_sender_input_accounts":
            df = parse_email_sender_input_accounts(uploaded_file)
        elif table_name == "sender_hyperlink_text":
            df = parse_text_list(uploaded_file, "hyperlink_text")
        elif table_name == "sender_link":
            df = parse_text_list(uploaded_file, "link")
        elif table_name == "sender_recipients":
            df = parse_text_list(uploaded_file, "recipient_email")
        elif table_name == "sender_subjects":
            df = parse_text_list(uploaded_file, "subject")
        elif table_name == "sender_texts":
            df = parse_text_list(uploaded_file, "text")
        elif table_name == "familybot_first_names":
            df = parse_text_list(uploaded_file, "firstnames")
        elif table_name == "familybot_surnames":
            df = parse_text_list(uploaded_file, "surnames")
        elif table_name == "familybot_card_details":
            df = parse_card_file(uploaded_file)
        elif table_name == "family_link":
            df = parse_text_list(uploaded_file, "link")
        elif table_name == "familybot_extracted_family_links":
            df = parse_family_links_file(uploaded_file)
        elif table_name in ["smtp_accounts", "password_changer_accounts"]:
            df = parse_smtp_file(uploaded_file)
        elif table_name == "cache_bins":
            df = parse_cache_bin_file(uploaded_file)
        else:
            df = parse_fake_json(uploaded_file)

        if table_name in country_tables:
            selected_country = st.selectbox(
                "Select country for uploaded rows", country_options
            )
            if selected_country:
                df["country"] = selected_country

        st.subheader("Preview top 10 files")
        st.dataframe(df.head(10), width="stretch")

        valid, message = validate_dataframe(table_name, df)
        if not valid:
            st.error(message)
            return

        st.success(message)
        st.write(f"Rows found: {len(df)}")

        server_ip = None
        bot_type = None
        if table_name in [
            "smtp_accounts",
            "cache_bins",
            "familybot_extracted_family_links",
        ]:
            server_ip = st.text_input("Server IP", value="")
            bot_type = st.text_input("Bot Type", value="")
            if not server_ip or not bot_type:
                st.warning("Please provide Server IP and Bot Type for this table.")
                return

        if st.button("Upload to database"):
            with st.spinner("Uploading..."):
                success, result_message = insert_into_db(
                    table_name, df, server_ip, bot_type
                )
                if success:
                    st.success(result_message)
                else:
                    st.error(result_message)

    st.sidebar.header("Configuration")
    st.sidebar.write("DB host: " + get_db_config().get("host", "localhost"))
    st.sidebar.write("Database name: " + get_db_config().get("database", "oneapp"))
    st.sidebar.write(datetime.now().strftime("Last refreshed: %Y-%m-%d %H:%M:%S"))

    if st.sidebar.button("Test DB Connection"):
        with st.spinner("Testing connection..."):
            success, message = test_db_connection()
            if success:
                st.sidebar.success(message)
            else:
                st.sidebar.error(message)

    st.sidebar.header("Database Management")
    if st.sidebar.button("Create Database"):
        with st.spinner("Creating database..."):
            success, message = create_database()
            if success:
                st.sidebar.success(message)
            else:
                st.sidebar.error(message)

    if st.sidebar.button("Update Database Tables"):
        with st.spinner("Updating tables..."):
            success, message = update_database_tables()
            if success:
                st.sidebar.success(message)
            else:
                st.sidebar.error(message)


if __name__ == "__main__":
    main()
