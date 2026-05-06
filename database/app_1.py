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


def parse_text_list(uploaded_file, column_name):
    content = uploaded_file.read().decode("utf-8", errors="replace")
    values = [line.strip() for line in content.splitlines() if line.strip()]
    return pd.DataFrame({column_name: values})


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
    st.set_page_config(
        page_title="FamilyBot Database Uploader", page_icon="📊", layout="wide"
    )
    st.markdown(
        """
        <style>
            .stApp {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #ffffff;
            }
            .block-container {
                padding: 3rem 4rem;
                max-width: 1200px;
            }
            .stTitle {
                color: #ffffff;
                font-size: 2.5rem;
                font-weight: 700;
                text-align: center;
                margin-bottom: 1rem;
            }
            .stMarkdown {
                color: #e0e0e0;
                text-align: center;
                margin-bottom: 2rem;
            }
            .stSelectbox, .stFileUploader {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 1rem;
                margin-bottom: 1rem;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            .stButton>button {
                background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
                color: white;
                border: none;
                border-radius: 25px;
                padding: 0.75rem 2rem;
                font-weight: 600;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            }
            .stButton>button:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
            }
            .stDataFrame {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 1rem;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            .stSidebar {
                background: rgba(0, 0, 0, 0.3);
                border-right: 1px solid rgba(255, 255, 255, 0.1);
            }
            .stSidebar .stButton>button {
                background: rgba(255, 255, 255, 0.2);
                color: white;
                border-radius: 10px;
            }
            .stSuccess, .stError, .stWarning {
                border-radius: 10px;
                padding: 1rem;
                margin: 1rem 0;
            }
            .stTextInput input {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border-radius: 5px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            .stTextInput label {
                color: #ffffff;
            }
        </style>
    """,
        unsafe_allow_html=True,
    )

    st.title("📊 FamilyBot Database Uploader")
    st.markdown(
        "Upload CSV, TXT, or JSON files directly into MySQL tables with a streamlined interface."
    )

    # Main content area
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("📋 Configuration")
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

    with col2:
        if uploaded_file is not None:
            st.subheader("🔍 Data Preview")
            if table_name == "input_emails":
                df = parse_email_file(uploaded_file)
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

            st.dataframe(df.head(10), use_container_width=True)

            valid, message = validate_dataframe(table_name, df)
            if not valid:
                st.error(message)
                st.stop()

            st.success(message)
            st.write(f"📊 **Rows found:** {len(df)}")

            server_ip = None
            bot_type = None
            if table_name in [
                "smtp_accounts",
                "cache_bins",
                "familybot_extracted_family_links",
            ]:
                st.subheader("🔧 Additional Parameters")
                server_ip = st.text_input("Server IP", value="")
                bot_type = st.text_input("Bot Type", value="")
                if not server_ip or not bot_type:
                    st.warning(
                        "⚠️ Please provide Server IP and Bot Type for this table."
                    )
                    st.stop()

            st.markdown("---")
            if st.button("🚀 Upload to Database", type="primary"):
                with st.spinner("Uploading..."):
                    success, result_message = insert_into_db(
                        table_name, df, server_ip, bot_type
                    )
                    if success:
                        st.success(f"✅ {result_message}")
                    else:
                        st.error(f"❌ {result_message}")
        else:
            st.info("📤 Please select a table and upload a file to get started.")

    st.sidebar.header("⚙️ Database Configuration")
    st.sidebar.write("**DB Host:** " + get_db_config().get("host", "localhost"))
    st.sidebar.write("**Database:** " + get_db_config().get("database", "oneapp"))
    st.sidebar.write(
        "**Last Refreshed:** " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    if st.sidebar.button("🔗 Test Connection", use_container_width=True):
        with st.spinner("Testing connection..."):
            success, message = test_db_connection()
            if success:
                st.sidebar.success("✅ " + message)
            else:
                st.sidebar.error("❌ " + message)

    st.sidebar.markdown("---")
    st.sidebar.header("🛠️ Database Management")
    if st.sidebar.button("📦 Create Database", use_container_width=True):
        with st.spinner("Creating database..."):
            success, message = create_database()
            if success:
                st.sidebar.success("✅ " + message)
            else:
                st.sidebar.error("❌ " + message)

    if st.sidebar.button("🔄 Update Tables", use_container_width=True):
        with st.spinner("Updating tables..."):
            success, message = update_database_tables()
            if success:
                st.sidebar.success("✅ " + message)
            else:
                st.sidebar.error("❌ " + message)


if __name__ == "__main__":
    main()
