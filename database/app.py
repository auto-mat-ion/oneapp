import os

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta
import re

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


def load_full_settings():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(BASE_DIR, "../bots/settings.json")

    try:
        with open(settings_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data
    except Exception:
        return {}


def save_settings(settings):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(BASE_DIR, "../bots/settings.json")

    try:
        with open(settings_path, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2)
        return True
    except Exception:
        return False


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


def parse_schema(file_path):
    """Parse CREATE TABLE statements from a SQL file to get table and full column definitions"""
    tables = {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return tables

    create_table_pattern = re.compile(
        r"CREATE TABLE\s+`?(\w+)`?\s*\((.*?)\);", re.DOTALL | re.IGNORECASE
    )
    for match in create_table_pattern.finditer(content):
        table_name = match.group(1)
        table_def = match.group(2)
        columns = {}
        lines = [line.strip() for line in table_def.split(",") if line.strip()]
        for line in lines:
            if (
                line.upper().startswith("PRIMARY KEY")
                or line.upper().startswith("KEY")
                or line.upper().startswith("CONSTRAINT")
                or line.upper().startswith("INDEX")
                or line.upper().startswith("UNIQUE")
            ):
                continue
            col_match = re.match(r"`?(\w+)`?\s+(.+)$", line, re.IGNORECASE)
            if col_match:
                col_name = col_match.group(1)
                col_def = col_match.group(2).strip()
                columns[col_name] = col_def
        tables[table_name] = columns
    return tables


def get_current_schema():
    """Get the current database schema from the live database"""
    conn = get_db_connection()
    if conn is None:
        return {}

    try:
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables_list = [row[0] for row in cursor.fetchall()]

        schema = {}
        for table in tables_list:
            cursor.execute(f"SHOW COLUMNS FROM `{table}`")
            columns = {}
            for row in cursor.fetchall():
                col_name = row[0]
                col_type = row[1]
                is_nullable = row[2] == "YES"
                default = row[4]
                extra = row[5]
                full_def = col_type
                if not is_nullable:
                    full_def += " NOT NULL"
                if default is not None:
                    full_def += f" DEFAULT {default}"
                if extra:
                    full_def += f" {extra}"
                columns[col_name] = full_def
            schema[table] = columns

        cursor.close()
        conn.close()
        return schema
    except Exception:
        return {}


def compare_schemas(current_schema, new_schema):
    """Compare current and new schemas, return detailed differences"""
    differences = {"new_tables": [], "dropped_tables": [], "modified_tables": {}}

    for table in new_schema:
        if table not in current_schema:
            differences["new_tables"].append(table)

    for table in current_schema:
        if table not in new_schema:
            differences["dropped_tables"].append(table)

    for table in new_schema:
        if table in current_schema:
            current_cols = current_schema[table]
            new_cols = new_schema[table]

            table_changes = {
                "new_columns": [],
                "dropped_columns": [],
                "modified_columns": [],
            }

            for col in new_cols:
                if col not in current_cols:
                    table_changes["new_columns"].append((col, new_cols[col]))

            for col in current_cols:
                if col not in new_cols:
                    table_changes["dropped_columns"].append((col, current_cols[col]))

            for col in current_cols:
                if col in new_cols and current_cols[col] != new_cols[col]:
                    table_changes["modified_columns"].append(
                        {
                            "column": col,
                            "old_type": current_cols[col],
                            "new_type": new_cols[col],
                        }
                    )

            if (
                table_changes["new_columns"]
                or table_changes["dropped_columns"]
                or table_changes["modified_columns"]
            ):
                differences["modified_tables"][table] = table_changes

    return differences


def get_schema_comparison():
    """Get the current vs new schema comparison"""
    schema_path = os.path.join(THE_BASE_DIR, "db_schema.sql")
    if not os.path.exists(schema_path):
        return None, "db_schema.sql not found"

    current_schema = get_current_schema()
    if not current_schema:
        return None, "Could not read current database schema"

    new_schema = parse_schema(schema_path)
    differences = compare_schemas(current_schema, new_schema)

    return differences, None


def apply_schema_changes(differences, skip_drop_tables=True):
    """Apply schema changes with safety checks. Never drops tables by default."""
    conn = get_db_connection()
    if conn is None:
        return False, "No database connection"

    cursor = conn.cursor()
    changes_applied = []

    try:
        schema_path = os.path.join(THE_BASE_DIR, "db_schema.sql")
        schema_tables = parse_schema(schema_path)

        # Step 1: Create new tables
        for table in differences["new_tables"]:
            if table in schema_tables:
                try:
                    cols_def = []
                    for col_name, col_def in schema_tables[table].items():
                        cols_def.append(f"`{col_name}` {col_def}")
                    create_stmt = (
                        f"CREATE TABLE `{table}` (" + ", ".join(cols_def) + ")"
                    )
                    cursor.execute(create_stmt)
                    changes_applied.append(f"✓ Created table: {table}")
                except Exception as e:
                    return False, f"Failed to create table {table}: {str(e)}"

        # Step 2: Modify existing tables - only alter structure, never drop tables
        for table, changes in differences["modified_tables"].items():
            try:
                # Add new columns
                for col_name, col_def in changes["new_columns"]:
                    cursor.execute(
                        f"ALTER TABLE `{table}` ADD COLUMN IF NOT EXISTS `{col_name}` {col_def}"
                    )
                    changes_applied.append(f"✓ Added column {col_name} to {table}")

                # Modify changed columns
                for change in changes["modified_columns"]:
                    col_name = change["column"]
                    new_type = change["new_type"]
                    try:
                        cursor.execute(
                            f"ALTER TABLE `{table}` MODIFY COLUMN `{col_name}` {new_type}"
                        )
                        changes_applied.append(
                            f"✓ Modified column {col_name} in {table}"
                        )
                    except Exception as col_err:
                        return (
                            False,
                            f"Failed to modify column {col_name} in {table}: {str(col_err)}",
                        )

                # Drop columns ONLY if explicitly requested and only if they're not in schema
                if not skip_drop_tables:
                    for col_name, _ in changes["dropped_columns"]:
                        try:
                            cursor.execute(
                                f"ALTER TABLE `{table}` DROP COLUMN `{col_name}`"
                            )
                            changes_applied.append(
                                f"✓ Dropped column {col_name} from {table}"
                            )
                        except Exception as drop_err:
                            pass  # Silently skip if column doesn't exist
            except Exception as e:
                return False, f"Error modifying table {table}: {str(e)}"

        # Step 3: Optional table dropping (disabled by default for safety)
        if not skip_drop_tables:
            for table in differences["dropped_tables"]:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
                    changes_applied.append(f"✓ Dropped table: {table}")
                except Exception as e:
                    return False, f"Failed to drop table {table}: {str(e)}"

        conn.commit()
        summary = (
            "\n".join(changes_applied) if changes_applied else "No changes applied"
        )
        return True, f"Schema updated successfully!\n\n{summary}"
    except Exception as exc:
        conn.rollback()
        return False, f"Error applying schema changes: {str(exc)}"
    finally:
        cursor.close()
        conn.close()
    """Update database tables by comparing most recent backup with schema and syncing database"""
    schema_path = os.path.join(THE_BASE_DIR, "db_schema.sql")
    if not os.path.exists(schema_path):
        return False, "db_schema.sql not found"

    # Find most recent backup
    try:
        backup_dirs = [d for d in os.listdir(THE_BASE_DIR) if d.startswith("backup_")]
        if not backup_dirs:
            return False, "No backup found to compare with schema"
        backup_dirs.sort(reverse=True)
        latest_backup_dir = backup_dirs[0]
        backup_file = os.path.join(THE_BASE_DIR, latest_backup_dir, "backup.sql")
        if not os.path.exists(backup_file):
            return False, "Backup file not found"
    except Exception:
        return False, "Error finding backup"

    schema_tables = parse_schema(schema_path)
    backup_tables = parse_schema(backup_file)

    conn = get_db_connection()
    if conn is None:
        return False, "No database connection"

    cursor = conn.cursor()
    try:
        # Get current tables
        cursor.execute("SHOW TABLES")
        current_tables = [row[0] for row in cursor.fetchall()]

        # Create tables in schema but not in backup
        for table in schema_tables:
            if table not in backup_tables:
                create_stmt = f"CREATE TABLE IF NOT EXISTS {table} ("
                cols = [
                    f"{col_name} {col_type}"
                    for col_name, col_type in schema_tables[table]
                ]
                create_stmt += ", ".join(cols) + ")"
                cursor.execute(create_stmt)

        # Drop tables in backup but not in schema
        for table in backup_tables:
            if table not in schema_tables and table in current_tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")

        # Update columns for tables in both
        for table in schema_tables:
            if table in backup_tables and table in current_tables:
                # Get current columns
                cursor.execute(f"SHOW COLUMNS FROM {table}")
                current_cols = [row[0] for row in cursor.fetchall()]

                schema_cols = [col[0] for col in schema_tables[table]]
                backup_cols = [col[0] for col in backup_tables[table]]

                # Add columns in schema but not in backup
                for col in schema_cols:
                    if col not in backup_cols and col not in current_cols:
                        col_type = next(
                            c[1] for c in schema_tables[table] if c[0] == col
                        )
                        cursor.execute(
                            f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                        )

                # Drop columns in backup but not in schema
                for col in backup_cols:
                    if col not in schema_cols and col in current_cols:
                        cursor.execute(f"ALTER TABLE {table} DROP COLUMN {col}")

        conn.commit()
        return True, "Database updated successfully to match schema"
    except Exception as exc:
        return False, f"Error updating database: {str(exc)}"
    finally:
        cursor.close()
        conn.close()


def sql_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, str):
        return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def backup_database():
    """Create a database backup using Python instead of external mysqldump."""
    config = get_db_config()
    if mysql is None:
        return (
            False,
            "mysql-connector-python is not installed. Install it with `pip install mysql-connector-python`.",
        )

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = os.path.join(THE_BASE_DIR, f"backup_{timestamp}")
    os.makedirs(backup_dir, exist_ok=True)
    backup_file = os.path.join(backup_dir, "backup.sql")

    try:
        conn = get_db_connection()
        if conn is None:
            return False, "No database connection"

        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]

        with open(backup_file, "w", encoding="utf-8") as f:
            f.write(f"CREATE DATABASE IF NOT EXISTS `{config['database']}`;\n")
            f.write(f"USE `{config['database']}`;\n\n")

            for table in tables:
                cursor.execute(f"SHOW CREATE TABLE `{table}`")
                create_stmt = cursor.fetchone()[1]
                f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
                f.write(create_stmt + ";\n\n")

                cursor.execute(f"SELECT * FROM `{table}`")
                rows = cursor.fetchall()
                if rows:
                    columns = [f"`{name}`" for name in cursor.column_names]
                    for row in rows:
                        values = [sql_literal(value) for value in row]
                        f.write(
                            f"INSERT INTO `{table}` ({', '.join(columns)}) VALUES ({', '.join(values)});\n"
                        )
                    f.write("\n")

        cursor.close()
        conn.close()
        return True, f"Backup created successfully at {backup_file}"
    except Exception as exc:
        return False, f"Backup failed: {str(exc)}"


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


def insert_into_db(table_name, df, server_ip=None, bot_type=None, overwrite=False):
    conn = get_db_connection()
    if conn is None:
        return False, "No database connection"
    try:
        cursor = conn.cursor()
        if overwrite and table_name == "sender_link":
            cursor.execute("DELETE FROM sender_link")
            conn.commit()
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
    if table_name == "sender_input_accounts":
        if not all(col in df.columns for col in ["email", "pass", "recovery"]):
            return (
                False,
                "Table sender_input_accounts requires columns: email, pass, recovery",
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


def general_uploader():
    table_options = {
        "input_emails": "Email Accounts",
        "familybot_first_names": "First Names",
        "familybot_surnames": "Surnames",
        "familybot_card_details": "Card Details",
        "familybot_fake_details": "Fake Details",
        "family_link": "Family Links",
        "familybot_extracted_family_links": "Extracted Family Links",
        "password_changer_accounts": "Password Changer Accounts",
        "cache_bins": "Cache Bin Files",
    }

    table_name = st.selectbox(
        "Select destination table",
        list(table_options.keys()),
        format_func=lambda x: table_options[x],
        key="general_table",
    )
    st.markdown(f"**Target table:** `{table_name}`")

    country_options = [
        "United States",
        "Poland",
        "Sweden",
        "United Kingdom",
    ]

    selected_country = None
    if table_name in [
        "familybot_first_names",
        "familybot_surnames",
        "familybot_card_details",
    ]:
        selected_country = st.selectbox(
            "Select country for uploaded rows",
            country_options,
            key=f"general_country_{table_name}",
        )

    file_types = (
        ["json"]
        if table_name == "familybot_fake_details"
        else ["bin", "dat", "cache"]
        if table_name == "cache_bins"
        else ["txt", "csv"]
    )
    uploaded_file = st.file_uploader(
        "Choose your file", type=file_types, key=f"general_file_{table_name}"
    )

    if uploaded_file is not None:
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
        elif table_name == "password_changer_accounts":
            df = parse_smtp_file(uploaded_file)
        elif table_name == "cache_bins":
            df = parse_cache_bin_file(uploaded_file)
        else:
            df = parse_fake_json(uploaded_file)

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
            "cache_bins",
            "familybot_extracted_family_links",
        ]:
            server_ip = st.text_input(
                "Server IP", value="", key=f"general_server_ip_{table_name}"
            )
            bot_type = st.text_input(
                "Bot Type", value="", key=f"general_bot_type_{table_name}"
            )
            if not server_ip or not bot_type:
                st.warning("Please provide Server IP and Bot Type for this table.")
                return

        if st.button("Upload to database", key=f"general_upload_{table_name}"):
            with st.spinner("Uploading..."):
                success, result_message = insert_into_db(
                    table_name, df, server_ip, bot_type
                )
                if success:
                    st.success(result_message)
                else:
                    st.error(result_message)


def email_sender_uploader():
    table_options = {
        "sender_input_accounts": "Sender Input Accounts",
        "sender_hyperlink_text": "Sender Hyperlink Text",
        "sender_link": "Sender Links",
        "sender_recipients": "Sender Recipients",
        "sender_subjects": "Sender Subjects",
        "sender_texts": "Sender Texts",
    }

    country_options = [
        "United States",
        "Poland",
        "Sweden",
        "United Kingdom",
    ]

    table_name = st.selectbox(
        "Select destination table",
        list(table_options.keys()),
        format_func=lambda x: table_options[x],
        key="sender_table",
    )
    st.markdown(f"**Target table:** `{table_name}`")

    selected_country = st.selectbox(
        "Select country for uploaded rows",
        country_options,
        key=f"sender_country_{table_name}",
    )

    upload_method = None
    if table_name == "sender_link":
        upload_method = st.radio(
            "Upload method",
            ["Add to existing links", "Overwrite existing links"],
            key=f"sender_link_method_{table_name}",
        )

    file_types = ["txt", "csv"]
    uploaded_file = st.file_uploader(
        "Choose your file", type=file_types, key=f"sender_file_{table_name}"
    )

    if uploaded_file is not None:
        if table_name == "sender_input_accounts":
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

        # Distribution for sender_input_accounts and sender_recipients
        if table_name in ["sender_input_accounts", "sender_recipients"]:
            st.subheader("Server Distribution")

            settings = load_full_settings()
            server_ips = settings.get("email_sender", {}).get("SERVER_IPS", [])

            # Add new server
            col1, col2 = st.columns([4, 1])
            with col1:
                new_server = st.text_input(
                    "Add new server IP", key=f"new_server_{table_name}"
                )
            with col2:
                if st.button("Add Server", key=f"add_server_{table_name}"):
                    if new_server and new_server not in server_ips:
                        server_ips.append(new_server)
                        settings["email_sender"]["SERVER_IPS"] = server_ips
                        save_settings(settings)
                        st.success(f"Added server {new_server}")
                        st.rerun()

            # Remove server
            if server_ips:
                col3, col4 = st.columns([4, 1])
                with col3:
                    remove_server = st.selectbox(
                        "Select server to remove",
                        server_ips,
                        key=f"remove_server_{table_name}",
                    )
                with col4:
                    if st.button(
                        "Remove Server", key=f"remove_server_btn_{table_name}"
                    ):
                        if remove_server in server_ips:
                            server_ips.remove(remove_server)
                            settings["email_sender"]["SERVER_IPS"] = server_ips
                            save_settings(settings)
                            st.success(f"Removed server {remove_server}")
                            st.rerun()

            # Select servers
            selected_servers = st.multiselect(
                "Select servers for distribution",
                server_ips,
                key=f"selected_servers_{table_name}",
            )

            if not selected_servers:
                st.warning("Select at least one server to proceed.")
                return

            # Distribution method
            dist_method = st.radio(
                "Distribution method",
                ["Manual", "Equal"],
                key=f"dist_method_{table_name}",
            )

            # Initialize distribution in session state
            dist_key = f"distribution_{table_name}"
            if dist_key not in st.session_state:
                st.session_state[dist_key] = []

            distribution = st.session_state[dist_key]

            if dist_method == "Equal":
                if st.button("Distribute Equally", key=f"equal_dist_{table_name}"):
                    total = len(df)
                    num_servers = len(selected_servers)
                    base = total // num_servers
                    remainder = total % num_servers
                    distribution = []
                    for i, server in enumerate(selected_servers):
                        count = base + (1 if i < remainder else 0)
                        distribution.append({"server": server, "count": count})
                    st.session_state[dist_key] = distribution
                    st.success("Distributed equally across servers.")
            else:  # Manual
                st.write(
                    "Assign servers sequentially. First assignment gets the top rows, second gets the next, etc."
                )
                remaining = len(df) - sum(d["count"] for d in distribution)
                st.write(f"Remaining rows to assign: {remaining}")

                if remaining > 0:
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        manual_server = st.selectbox(
                            "Select server",
                            selected_servers,
                            key=f"manual_server_{table_name}",
                        )
                    with col2:
                        manual_count = st.number_input(
                            "Number to assign",
                            min_value=1,
                            max_value=remaining,
                            value=min(1, remaining),
                            key=f"manual_count_{table_name}",
                        )
                    with col3:
                        if st.button("Assign", key=f"assign_{table_name}"):
                            # Check if server already assigned, overwrite count
                            found = False
                            for d in distribution:
                                if d["server"] == manual_server:
                                    d["count"] = manual_count
                                    found = True
                                    break
                            if not found:
                                distribution.append(
                                    {"server": manual_server, "count": manual_count}
                                )
                            st.session_state[dist_key] = distribution
                            st.success(
                                f"Assigned {manual_count} rows to {manual_server}"
                            )
                            st.rerun()

            # Show current distribution
            st.subheader("Current Distribution")
            total_assigned = sum(d["count"] for d in distribution)
            st.write(
                f"Total rows: {len(df)}, Assigned: {total_assigned}, Remaining: {len(df) - total_assigned}"
            )

            if distribution:
                for i, d in enumerate(distribution):
                    st.write(f"{i + 1}. Server {d['server']}: {d['count']} rows")

                if st.button("Clear Distribution", key=f"clear_dist_{table_name}"):
                    st.session_state[dist_key] = []
                    st.rerun()

            # Check if distribution is complete
            if total_assigned != len(df):
                st.warning("Please complete the distribution before uploading.")
                return

            # Assign server_ip to df
            df["server_ip"] = ""
            start_idx = 0
            for d in distribution:
                end_idx = start_idx + d["count"]
                df.loc[start_idx : end_idx - 1, "server_ip"] = d["server"]
                start_idx = end_idx

        overwrite = (
            upload_method == "Overwrite existing links"
            if table_name == "sender_link"
            else False
        )

        if st.button("Upload to database", key=f"sender_upload_{table_name}"):
            with st.spinner("Uploading..."):
                success, result_message = insert_into_db(
                    table_name, df, overwrite=overwrite
                )
                if success:
                    st.success(result_message)
                else:
                    st.error(result_message)


def db_count(table, where_clause=None, params=None):
    conn = get_db_connection()
    if conn is None:
        return 0
    try:
        cursor = conn.cursor()
        query = f"SELECT COUNT(*) FROM {table}"
        if where_clause:
            query += f" WHERE {where_clause}"
        cursor.execute(query, params or ())
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception as e:
        st.error(f"Database error in db_count: {e}")
        return 0
    finally:
        try:
            conn.close()
        except:
            pass


def db_group_count(table, group_column, where_clause=None, params=None, limit=5):
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        query = f"SELECT {group_column}, COUNT(*) as total FROM {table}"
        if where_clause:
            query += f" WHERE {where_clause}"
        query += " GROUP BY " + group_column + " ORDER BY total DESC"
        if limit:
            query += " LIMIT %s"
            params = tuple(params or ()) + (limit,)
        cursor.execute(query, params or ())
        return cursor.fetchall()
    except Exception as e:
        st.error(f"Database error in db_group_count: {e}")
        return []
    finally:
        try:
            conn.close()
        except:
            pass


def db_top_servers(table, bot_type=None, start_date=None, end_date=None, limit=5):
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        query = f"SELECT server_ip, COUNT(*) as total FROM {table}"
        conditions = []
        params = []
        if bot_type:
            conditions.append("bot_type = %s")
            params.append(bot_type)
        if start_date and end_date:
            conditions.append("date_time BETWEEN %s AND %s")
            params.append(start_date)
            params.append(end_date)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " GROUP BY server_ip ORDER BY total DESC LIMIT %s"
        params.append(limit)
        cursor.execute(query, tuple(params))
        return cursor.fetchall()
    except Exception as e:
        st.error(f"Database error in db_top_servers: {e}")
        return []
    finally:
        try:
            conn.close()
        except:
            pass


def render_stats_cards(cards):
    for i in range(0, len(cards), 3):
        row = cards[i : i + 3]
        cols = st.columns(len(row))
        for col, stat in zip(cols, row):
            col.metric(stat["label"], stat["value"], stat.get("delta", ""))


def stats_page():
    st.header("Stats")
    st.markdown("Choose a bot to see focused metrics.")

    if "stats_bot" not in st.session_state:
        st.session_state.stats_bot = "FamilyBot"

    bot_options = ["FamilyBot", "Hotmail Bot", "Email Sender", "Password Changer"]
    cols = st.columns(len(bot_options))
    for idx, bot in enumerate(bot_options):
        with cols[idx]:
            if st.button(bot, key=f"stats_bot_{idx}"):
                st.session_state.stats_bot = bot

    selected_bot = st.session_state.stats_bot
    st.markdown(f"### {selected_bot}")

    today = datetime.now().date()
    date_range = st.date_input(
        "Filter by date range",
        [today - timedelta(days=7), today],
        key="stats_date_range",
    )
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_date, end_date = date_range
    elif isinstance(date_range, (tuple, list)) and len(date_range) == 1:
        start_date = end_date = date_range[0]
    else:
        start_date = end_date = date_range

    if end_date < start_date:
        st.error("End date must be after the start date.")
        return

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    if selected_bot == "FamilyBot":
        try:
            cards = [
                {
                    "label": "Available cards",
                    "value": db_count("familybot_card_details"),
                },
                {"label": "Failed cards", "value": db_count("familybot_failed_cards")},
                {
                    "label": "Fully used cards",
                    "value": db_count("familybot_fully_used_cards"),
                },
                {
                    "label": "Processing emails",
                    "value": db_count(
                        "processing_emails", "bot_type = %s", ("familybot",)
                    ),
                },
                {
                    "label": "Processed accounts",
                    "value": db_count(
                        "processed_emails", "bot_type = %s", ("familybot",)
                    ),
                },
                {"label": "Input emails total", "value": db_count("input_emails")},
            ]
            render_stats_cards(cards)
        except Exception as e:
            st.error(f"Error loading FamilyBot stats: {e}")

        try:
            st.markdown("### FamilyBot link stats")
            family_link_stats = db_count("link_stats", "bot_type = %s", ("familybot",))
            st.write(f"Link stats rows: {family_link_stats}")
        except Exception as e:
            st.error(f"Error loading link stats: {e}")

        try:
            st.markdown("### Top FamilyBot servers")
            family_rank = db_top_servers(
                "processed_emails",
                bot_type="familybot",
                start_date=start_dt,
                end_date=end_dt,
                limit=5,
            )
            if family_rank:
                st.table(
                    [
                        {"Server IP": server or "Unknown", "Processed": count}
                        for server, count in family_rank
                    ]
                )
            else:
                st.write("No FamilyBot server data found for the selected range.")
        except Exception as e:
            st.error(f"Error loading server stats: {e}")

        try:
            st.markdown("### Recent failed card reasons")
            failed_reasons = db_group_count(
                "familybot_failed_cards",
                "reason_for_fail",
                "bot_type = %s",
                ("familybot",),
                limit=5,
            )
            if failed_reasons:
                st.table(
                    [
                        {"Reason": reason or "Unknown", "Count": count}
                        for reason, count in failed_reasons
                    ]
                )
            else:
                st.write("No recent failed card reasons found.")
        except Exception as e:
            st.error(f"Error loading failed reasons: {e}")

    elif selected_bot == "Hotmail Bot":
        try:
            cards = [
                {
                    "label": "Processed emails",
                    "value": db_count(
                        "processed_emails", "bot_type = %s", ("hotmailbot",)
                    ),
                },
                {
                    "label": "Signin log rows",
                    "value": db_count("signin_log", "bot_type = %s", ("hotmailbot",)),
                },
                {
                    "label": "Account details",
                    "value": db_count(
                        "accounts_details", "bot_type = %s", ("hotmailbot",)
                    ),
                },
                {
                    "label": "Processing emails",
                    "value": db_count(
                        "processing_emails", "bot_type = %s", ("hotmailbot",)
                    ),
                },
                {"label": "Input emails total", "value": db_count("input_emails")},
            ]
            render_stats_cards(cards)
        except Exception as e:
            st.error(f"Error loading Hotmail Bot stats: {e}")

        try:
            st.markdown("### Top Hotmail servers")
            hotmail_rank = db_top_servers(
                "processed_emails",
                bot_type="hotmailbot",
                start_date=start_dt,
                end_date=end_dt,
                limit=5,
            )
            if hotmail_rank:
                st.table(
                    [
                        {"Server IP": server or "Unknown", "Processed": count}
                        for server, count in hotmail_rank
                    ]
                )
            else:
                st.write("No Hotmail server data found for the selected range.")
        except Exception as e:
            st.error(f"Error loading Hotmail server stats: {e}")

        try:
            st.markdown("### Signin status breakdown")
            signin_status = db_group_count(
                "signin_log",
                "status",
                "bot_type = %s",
                ("hotmailbot",),
                limit=6,
            )
            if signin_status:
                st.table(
                    [
                        {"Status": status or "Unknown", "Count": count}
                        for status, count in signin_status
                    ]
                )
            else:
                st.write("No signin status data found.")
        except Exception as e:
            st.error(f"Error loading signin status: {e}")

    elif selected_bot == "Email Sender":
        try:
            cards = [
                {
                    "label": "Sender input accounts",
                    "value": db_count("sender_input_accounts"),
                },
                {
                    "label": "Sender processed accounts",
                    "value": db_count("sender_processed_accounts"),
                },
                {"label": "Failed SMTP rows", "value": db_count("failed_smtp")},
                {
                    "label": "Processing queue",
                    "value": db_count("processing_smtp_emails"),
                },
                {
                    "label": "Link stats rows",
                    "value": db_count("link_stats", "bot_type = %s", ("email_sender",)),
                },
            ]
            render_stats_cards(cards)
        except Exception as e:
            st.error(f"Error loading Email Sender stats: {e}")

        try:
            st.markdown("### Top Email Sender servers")
            sender_rank = db_top_servers(
                "sender_processed_accounts",
                start_date=start_dt,
                end_date=end_dt,
                limit=5,
            )
            if sender_rank:
                st.table(
                    [
                        {"Server IP": server or "Unknown", "Processed": count}
                        for server, count in sender_rank
                    ]
                )
            else:
                st.write("No sender server data found for the selected range.")
        except Exception as e:
            st.error(f"Error loading sender server stats: {e}")

        try:
            st.markdown("### Top sender countries")
            sender_countries = db_group_count(
                "sender_processed_accounts",
                "country",
                limit=6,
            )
            if sender_countries:
                st.table(
                    [
                        {"Country": country or "Unknown", "Count": count}
                        for country, count in sender_countries
                    ]
                )
            else:
                st.write("No sender country data found.")
        except Exception as e:
            st.error(f"Error loading sender countries: {e}")

    elif selected_bot == "Password Changer":
        try:
            cards = [
                {
                    "label": "Input accounts",
                    "value": db_count("password_changer_accounts"),
                },
                {
                    "label": "Processed accounts",
                    "value": db_count(
                        "processed_emails", "bot_type = %s", ("password_changer",)
                    ),
                },
                {
                    "label": "Processing changes",
                    "value": db_count(
                        "processing_password_changes",
                        "bot_type = %s",
                        ("password_changer",),
                    ),
                },
                {
                    "label": "Failed changes",
                    "value": db_count(
                        "failed_smtp", "bot_type = %s", ("password_changer",)
                    ),
                },
                {
                    "label": "Signin log entries",
                    "value": db_count(
                        "signin_log", "bot_type = %s", ("password_changer",)
                    ),
                },
                {
                    "label": "Account details",
                    "value": db_count(
                        "accounts_details", "bot_type = %s", ("password_changer",)
                    ),
                },
            ]
            render_stats_cards(cards)
        except Exception as e:
            st.error(f"Error loading Password Changer stats: {e}")

        try:
            st.markdown("### Top Password Changer servers")
            password_changer_rank = db_top_servers(
                "processed_emails",
                bot_type="password_changer",
                start_date=start_dt,
                end_date=end_dt,
                limit=5,
            )
            if password_changer_rank:
                st.table(
                    [
                        {"Server IP": server or "Unknown", "Processed": count}
                        for server, count in password_changer_rank
                    ]
                )
            else:
                st.write(
                    "No Password Changer server data found for the selected range."
                )
        except Exception as e:
            st.error(f"Error loading Password Changer server stats: {e}")

        try:
            st.markdown("### Password change status breakdown")
            password_status = db_group_count(
                "signin_log",
                "status",
                "bot_type = %s",
                ("password_changer",),
                limit=6,
            )
            if password_status:
                st.table(
                    [
                        {"Status": status or "Unknown", "Count": count}
                        for status, count in password_status
                    ]
                )
            else:
                st.write("No password change status data found.")
        except Exception as e:
            st.error(f"Error loading password change status: {e}")

        try:
            st.markdown("### Failed password change reasons")
            failed_reasons = db_group_count(
                "failed_smtp",
                "temp_email",
                "bot_type = %s",
                ("password_changer",),
                limit=5,
            )
            if failed_reasons:
                st.table(
                    [
                        {"Reason": reason or "Unknown", "Count": count}
                        for reason, count in failed_reasons
                    ]
                )
            else:
                st.write("No failed password change reasons found.")
        except Exception as e:
            st.error(f"Error loading failed password change reasons: {e}")

    st.divider()
    st.subheader("Insights")
    st.write(
        "Use these bot-specific metrics as a starting point. Add more cards or tables for deeper visibility as you build additional data flows."
    )


def render_setting_input(key, value, setting_key):
    """Render appropriate input widget based on value type"""
    if isinstance(value, bool):
        return st.checkbox(f"{key}", value=value, key=f"setting_{setting_key}_{key}")
    elif isinstance(value, int):
        return st.number_input(
            f"{key}", value=value, step=1, key=f"setting_{setting_key}_{key}"
        )
    elif isinstance(value, float):
        return st.number_input(
            f"{key}",
            value=value,
            step=0.1,
            format="%.2f",
            key=f"setting_{setting_key}_{key}",
        )
    elif isinstance(value, list):
        # For lists, show as text area
        list_str = "\n".join(str(item) for item in value)
        text_result = st.text_area(
            f"{key} (one item per line)",
            value=list_str,
            key=f"setting_{setting_key}_{key}",
            height=100,
        )
        return [item.strip() for item in text_result.split("\n") if item.strip()]
    else:
        return st.text_input(
            f"{key}", value=str(value), key=f"setting_{setting_key}_{key}"
        )


def database_management():
    """Dedicated page for all database operations"""
    st.header("🗄️ Database Management")

    # Connection status
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Test Connection", use_container_width=True):
            with st.spinner("Testing connection..."):
                success, message = test_db_connection()
                if success:
                    st.success(message)
                else:
                    st.error(message)

    config = get_db_config()
    with col2:
        st.metric("Host", config.get("host", "localhost"))
    with col3:
        st.metric("Database", config.get("database", "oneapp"))

    st.divider()

    # Create tabs for different operations
    tab1, tab2, tab3 = st.tabs(["🆕 Create Database", "📊 Update Schema", "💾 Backup"])

    # with tab1:
    #     st.subheader("Create Database from Schema")
    #     st.warning(
    #         "⚠️ **CRITICAL WARNING**\n\n"
    #         "This will **DELETE** the existing database and recreate it from `db_schema.sql`. "
    #         "All data will be lost. This action **CANNOT be undone**."
    #     )

    #     col1, col2 = st.columns(2)
    #     with col1:
    #         if st.button(
    #             "⚠️ Confirm - Delete & Create",
    #             key="create_db_confirm",
    #             use_container_width=True,
    #         ):
    #             with st.spinner("Creating database..."):
    #                 success, message = create_database()
    #                 if success:
    #                     st.success(message)
    #                     st.balloons()
    #                 else:
    #                     st.error(message)
    #     with col2:
    #         st.info("Creating from scratch using db_schema.sql")

    # with tab2:
    #     st.subheader("Update Schema to Match db_schema.sql")

    #     if st.button("🔍 Analyze Schema Differences", use_container_width=True):
    #         with st.spinner("Analyzing schema..."):
    #             differences, error = get_schema_comparison()

    #         if error:
    #             st.error(error)
    #         else:
    #             has_changes = (
    #                 differences["new_tables"]
    #                 or differences["dropped_tables"]
    #                 or differences["modified_tables"]
    #             )

    #             if not has_changes:
    #                 st.success("✅ Database schema is already up to date!")
    #             else:
    #                 st.warning(
    #                     f"🔄 Found {len(differences['new_tables']) + len(differences['dropped_tables']) + len(differences['modified_tables'])} changes"
    #                 )

    #                 # Display in tabs
    #                 sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs(
    #                     [
    #                         "📋 Summary",
    #                         "➕ New Tables",
    #                         "➖ Dropped Tables",
    #                         "🔄 Modified Tables",
    #                     ]
    #                 )

    #                 with sub_tab1:
    #                     col1, col2, col3 = st.columns(3)
    #                     with col1:
    #                         st.metric("New Tables", len(differences["new_tables"]))
    #                     with col2:
    #                         st.metric(
    #                             "Dropped Tables", len(differences["dropped_tables"])
    #                         )
    #                     with col3:
    #                         st.metric(
    #                             "Modified Tables", len(differences["modified_tables"])
    #                         )

    #                 with sub_tab2:
    #                     if differences["new_tables"]:
    #                         for table in differences["new_tables"]:
    #                             st.code(f"CREATE TABLE: {table}", language="sql")
    #                     else:
    #                         st.info("No new tables")

    #                 with sub_tab3:
    #                     if differences["dropped_tables"]:
    #                         st.warning("⚠️ Tables in database but NOT in schema:")
    #                         for table in differences["dropped_tables"]:
    #                             st.code(
    #                                 f"TABLE (not in schema): {table}", language="sql"
    #                             )
    #                     else:
    #                         st.info("No dropped tables")

    #                 with sub_tab4:
    #                     if differences["modified_tables"]:
    #                         for table, changes in differences[
    #                             "modified_tables"
    #                         ].items():
    #                             with st.expander(f"📝 Table: `{table}`", expanded=True):
    #                                 if changes["new_columns"]:
    #                                     st.markdown("**➕ New Columns:**")
    #                                     for col_name, col_def in changes["new_columns"]:
    #                                         st.code(
    #                                             f"ADD: {col_name} {col_def}",
    #                                             language="sql",
    #                                         )

    #                                 if changes["modified_columns"]:
    #                                     st.markdown("**🔄 Modified Columns:**")
    #                                     for change in changes["modified_columns"]:
    #                                         st.code(
    #                                             f"MODIFY: {change['column']}\n  FROM: {change['old_type']}\n  TO:   {change['new_type']}",
    #                                             language="sql",
    #                                         )

    #                                 if changes["dropped_columns"]:
    #                                     st.markdown(
    #                                         "**ℹ️ Columns in database but NOT in schema:**"
    #                                     )
    #                                     for col_name, col_def in changes[
    #                                         "dropped_columns"
    #                                     ]:
    #                                         st.code(
    #                                             f"NOT IN SCHEMA: {col_name} {col_def}",
    #                                             language="sql",
    #                                         )
    #                     else:
    #                         st.info("No modified tables")

    #                 st.divider()
    #                 st.info(
    #                     "✓ **Safe Update**: Only adds new tables and columns, modifies datatypes. Does NOT delete tables or columns."
    #                 )
    #                 st.warning(
    #                     "⚠️ **WARNING**: This action CANNOT be undone! Ensure you have a backup."
    #                 )

    #                 col1, col2 = st.columns(2)
    #                 with col1:
    #                     if st.button(
    #                         "✅ Apply Schema Update",
    #                         key="apply_schema",
    #                         use_container_width=True,
    #                     ):
    #                         with st.spinner("Applying schema changes..."):
    #                             success, message = apply_schema_changes(
    #                                 differences, skip_drop_tables=True
    #                             )
    #                             if success:
    #                                 st.success(message)
    #                                 st.balloons()
    #                             else:
    #                                 st.error(message)
    #                 with col2:
    #                     st.info("Updates structure without deleting data")

    with tab3:
        st.subheader("Backup Database")
        st.info(
            "Creates a timestamped backup in `database/backup_YYYY-MM-DD_HH-MM-SS/backup.sql`"
        )

        if st.button("💾 Create Backup", use_container_width=True):
            with st.spinner("Backing up database..."):
                success, message = backup_database()
                if success:
                    st.success(message)
                    st.balloons()
                else:
                    st.error(message)

        # List recent backups
        try:
            backup_dirs = sorted(
                [d for d in os.listdir(THE_BASE_DIR) if d.startswith("backup_")],
                reverse=True,
            )
            if backup_dirs:
                st.divider()
                st.subheader("Recent Backups")
                for backup_dir in backup_dirs[:10]:
                    backup_file = os.path.join(THE_BASE_DIR, backup_dir, "backup.sql")
                    if os.path.exists(backup_file):
                        file_size = os.path.getsize(backup_file) / 1024
                        st.write(f"📦 {backup_dir} ({file_size:.1f} KB)")
        except Exception:
            pass


def bot_settings():
    """Manage bot settings from settings.json"""
    st.header("⚙️ Bot Settings Manager")
    st.markdown("View and manage all bot configuration settings.")

    # Load settings
    settings = load_full_settings()
    if not settings:
        st.error("Could not load settings.json")
        return

    # Category buttons using columns for horizontal layout
    st.subheader("Select Configuration Category")

    categories = {
        "app": "🔧 General App Settings",
        "email_sender": "📧 Email Sender",
        "familybot": "👨‍👩‍👧 Family Bot",
        "hotmailbot": "🔑 Hotmail Bot",
        "password_changer": "🔄 Password Changer",
    }

    # Initialize session state for category selection
    if "selected_category" not in st.session_state:
        st.session_state.selected_category = "app"

    # Create button columns
    cols = st.columns(len(categories))
    for idx, (cat_key, cat_label) in enumerate(categories.items()):
        with cols[idx]:
            if st.button(cat_label, use_container_width=True, key=f"btn_{cat_key}"):
                st.session_state.selected_category = cat_key
                st.rerun()

    # Display current category
    selected_cat = st.session_state.selected_category
    st.divider()

    if selected_cat not in settings:
        st.warning(
            f"No settings found for {categories.get(selected_cat, selected_cat)}"
        )
        return

    cat_settings = settings[selected_cat]

    st.subheader(f"{categories.get(selected_cat, selected_cat)}")
    st.markdown(f"**Category:** `{selected_cat}`")
    st.markdown(f"**Total settings:** {len(cat_settings)}")

    st.divider()

    # Display settings in an editable format
    st.markdown("### Current Settings")

    # Create a form for editing
    with st.form(f"settings_form_{selected_cat}"):
        edited_settings = {}

        for setting_key, setting_value in cat_settings.items():
            col1, col2 = st.columns([1, 2])

            with col1:
                st.markdown(f"**{setting_key}**")

            with col2:
                edited_settings[setting_key] = render_setting_input(
                    setting_key, setting_value, selected_cat
                )

        st.divider()

        # Submit button
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            submitted = st.form_submit_button(
                "💾 Save Changes", use_container_width=True
            )
        with col2:
            reset = st.form_submit_button("↻ Reset", use_container_width=True)

        if submitted:
            # Update the settings
            settings[selected_cat] = edited_settings
            if save_settings(settings):
                st.success(
                    f"✅ Settings saved successfully for {categories.get(selected_cat, selected_cat)}"
                )
                st.rerun()
            else:
                st.error("❌ Failed to save settings. Check file permissions.")

        if reset:
            st.info("Form has been reset to current values.")

    # Display info section
    st.divider()
    st.markdown("### ℹ️ Information")

    info_cols = st.columns(3)
    with info_cols[0]:
        st.metric("Settings Count", len(cat_settings))
    with info_cols[1]:
        st.metric("Last Updated", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    with info_cols[2]:
        settings_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "../bots/settings.json"
        )
        st.metric(
            "Settings File",
            "✓ Exists" if os.path.exists(settings_path) else "✗ Missing",
        )


def main():
    st.set_page_config(page_title="FamilyBot Upload", page_icon="🧾", layout="wide")
    st.markdown(
        """
        <style>
            :root { color-scheme: dark; }
            .stApp {
                background: #0b1220;
            }
            .block-container {
                background: #111827;
                color: #e5e7eb;
                border-radius: 24px;
                padding: 2rem 2.5rem;
                box-shadow: 0 25px 80px rgba(0, 0, 0, 0.4);
            }
            .stSidebar {
                background: #0f172a;
                color: #e5e7eb;
            }
            .stSidebar .css-1d391kg {
                background: #0f172a;
            }
            .stButton>button {
                background: linear-gradient(135deg, #4f46e5, #2563eb);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 0.7rem 1rem;
            }
            .stButton>button:hover {
                background: linear-gradient(135deg, #2563eb, #3b82f6);
                color: white;
            }
            .stTextInput>div>div>input,
            .stTextArea>div>div>textarea,
            .stSelectbox>div>div>div>div,
            .stNumberInput>div>div>input,
            .stRadio>div>label,
            .stMultiselect>div>div>div {
                background-color: #1f2937;
                color: #e5e7eb;
                border: 1px solid #334155;
            }
            .stMarkdown p,
            .stMarkdown h1,
            .stMarkdown h2,
            .stMarkdown h3,
            .stMarkdown span {
                color: #e5e7eb;
            }
            .css-1d391kg .stMarkdown {
                color: #e5e7eb;
            }
            .stTabs [role="tab"] {
                color: #cbd5e1;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "selected_page" not in st.session_state:
        st.session_state.selected_page = "Bot Settings"

    st.sidebar.markdown("### 📄 Pages")
    if st.sidebar.button("Bot Settings", use_container_width=True):
        st.session_state.selected_page = "Bot Settings"
    if st.sidebar.button("General Upload", use_container_width=True):
        st.session_state.selected_page = "General Upload"
    if st.sidebar.button("Email Sender Upload", use_container_width=True):
        st.session_state.selected_page = "Email Sender Upload"
    if st.sidebar.button("Stats", use_container_width=True):
        st.session_state.selected_page = "Stats"
    if st.sidebar.button("🗄️ Database Management", use_container_width=True):
        st.session_state.selected_page = "Database Management"

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Database Configuration**")
    st.sidebar.write(f"**Host:** {get_db_config().get('host', 'localhost')}")
    st.sidebar.write(f"**Database:** {get_db_config().get('database', 'oneapp')}")
    st.sidebar.write(f"**Refreshed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    st.title(st.session_state.selected_page)
    st.markdown("---")

    if st.session_state.selected_page == "Bot Settings":
        bot_settings()
    elif st.session_state.selected_page == "General Upload":
        general_uploader()
    elif st.session_state.selected_page == "Email Sender Upload":
        email_sender_uploader()
    elif st.session_state.selected_page == "Stats":
        stats_page()
    elif st.session_state.selected_page == "Database Management":
        database_management()


if __name__ == "__main__":
    main()
