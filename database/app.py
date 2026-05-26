import math
import os
import random
import csv
import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import create_engine
import re

try:
    import mysql.connector
except ImportError:
    mysql = None

try:
    import msal
except ImportError:
    msal = None

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


def get_db_tables():
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        return tables
    except Exception as exc:
        st.error(f"Unable to load tables: {exc}")
        return []
    finally:
        cursor.close()
        conn.close()


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
                    changes_applied.append(f"Created table: {table}")
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
                    changes_applied.append(f"Added column {col_name} to {table}")

                # Modify changed columns
                for change in changes["modified_columns"]:
                    col_name = change["column"]
                    new_type = change["new_type"]
                    try:
                        cursor.execute(
                            f"ALTER TABLE `{table}` MODIFY COLUMN `{col_name}` {new_type}"
                        )
                        changes_applied.append(f"Modified column {col_name} in {table}")
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
                                f"Dropped column {col_name} from {table}"
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
                    changes_applied.append(f"Dropped table: {table}")
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


def backup_database(selected_tables=None):
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

        if selected_tables is None:
            selected_tables = tables
        selected_tables = [table for table in selected_tables if table in tables]
        if not selected_tables:
            return False, "No tables selected for backup."

        with open(backup_file, "w", encoding="utf-8") as f:
            f.write(f"CREATE DATABASE IF NOT EXISTS `{config['database']}`;\n")
            f.write(f"USE `{config['database']}`;\n\n")

            for table in selected_tables:
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


def load_emails_from_cache_bins(selected_country=None):
    """
    Load emails from cache_bins table, parse them, and get password/recovery/country from accounts_details.
    Returns a DataFrame with email, pass, recovery, and country columns.
    """
    if msal is None:
        st.error("msal is not installed. Cannot load from cache bins.")
        return None

    conn = get_db_connection()
    if conn is None:
        st.error("Unable to connect to database")
        return None

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT cache_bin_file FROM cache_bins")
        results = cursor.fetchall()

        # Parse all cache bins to extract emails
        combined_data = {
            "Account": {},
            "IdToken": {},
            "AccessToken": {},
            "RefreshToken": {},
            "AppMetadata": {},
        }

        for result in results:
            if result and result[0]:
                try:
                    temp_cache = msal.SerializableTokenCache()
                    temp_cache.deserialize(result[0].decode("utf-8"))
                    raw_data = json.loads(temp_cache.serialize())
                    for category in combined_data.keys():
                        if category in raw_data:
                            combined_data[category].update(raw_data[category])
                except Exception as e:
                    st.warning(f"Error parsing cache bin: {e}")
                    continue

        # Extract emails from Account data
        account_data = combined_data.get("Account", {})
        emails = set()
        for account_key, account_info in account_data.items():
            if isinstance(account_info, dict):
                username = account_info.get("username", "")
                if username:
                    emails.add(username.lower())

        if not emails:
            st.warning("No emails found in cache bins")
            return None

        cursor.execute("SELECT LOWER(email) FROM sender_input_accounts")
        assigned_emails = {row[0] for row in cursor.fetchall() if row and row[0]}
        cursor.execute("SELECT LOWER(email) FROM sender_failed_accounts")
        failed_emails = {row[0] for row in cursor.fetchall() if row and row[0]}

        available_emails = [
            email
            for email in emails
            if email not in assigned_emails and email not in failed_emails
        ]
        if not available_emails:
            st.warning(
                "No available emails left after removing assigned and failed sender accounts."
            )
            cursor.close()
            conn.close()
            return None

        selected_country = selected_country.lower() if selected_country else None
        st.info(
            f"Found {len(available_emails)} available sender emails from cache bins. Getting full info for country '{selected_country}'..."
        )

        placeholders = ",".join(["%s"] * len(available_emails))
        query = (
            "SELECT email_acc, password, recovery_email, country "
            "FROM accounts_details "
            "WHERE LOWER(email_acc) IN (" + placeholders + ")"
        )
        params = tuple(available_emails)
        if selected_country:
            query += " AND LOWER(country) = %s"
            params = params + (selected_country,)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        lookup = {
            row[0].lower(): (
                row[0],
                row[1],
                row[2] if row[2] else "",
                row[3] if row[3] else "",
            )
            for row in rows
        }

        data = []
        for email in sorted(available_emails):
            if email in lookup:
                row_email, password, recovery, country = lookup[email]
                data.append(
                    {
                        "email": row_email,
                        "pass": password,
                        "recovery": recovery,
                        "country": country,
                    }
                )

        cursor.close()
        conn.close()

        if not data:
            st.warning(
                "No matching sender accounts found in accounts_details for the selected country."
            )
            return None

        return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Error loading emails from cache bins: {e}")
        return None
    finally:
        try:
            conn.close()
        except:
            pass


def get_cached_sender_emails():
    """Return a set of sender account emails found in all cache bins."""
    conn = get_db_connection()
    if conn is None:
        return set()

    emails = set()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT cache_bin_file FROM cache_bins")
        rows = cursor.fetchall()
        cursor.close()

        for row in rows:
            cache_bin = row[0]
            if not cache_bin:
                continue

            try:
                content = (
                    cache_bin.decode("utf-8")
                    if isinstance(cache_bin, (bytes, bytearray))
                    else str(cache_bin)
                )
                token_cache = msal.SerializableTokenCache()
                token_cache.deserialize(content)
                raw_data = json.loads(token_cache.serialize())
                account_data = raw_data.get("Account", {})
                for account_info in account_data.values():
                    if isinstance(account_info, dict):
                        username = account_info.get("username", "")
                        if username:
                            emails.add(username.lower())
            except Exception:
                continue

    except Exception:
        pass
    finally:
        try:
            conn.close()
        except:
            pass

    return emails


def count_unassigned_sender_accounts():
    cached_emails = get_cached_sender_emails()
    if not cached_emails:
        return 0

    conn = get_db_connection()
    if conn is None:
        return 0

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT LOWER(email) FROM sender_input_accounts")
        assigned_emails = {row[0] for row in cursor.fetchall() if row and row[0]}
        cursor.execute("SELECT LOWER(email) FROM sender_failed_accounts")
        failed_emails = {row[0] for row in cursor.fetchall() if row and row[0]}
        cursor.close()
        return len(cached_emails - assigned_emails - failed_emails)
    except Exception:
        return 0
    finally:
        try:
            conn.close()
        except:
            pass


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
    if rows and all(
        field in rows[0].lower() for field in ["email", "pass", "recovery", "link"]
    ):
        rows = rows[1:]

    for line in rows:
        if "," in line:
            reader = csv.reader([line])
            parts = next(reader, [])
        elif ":" in line:
            parts = [part.strip() for part in line.split(":")]
        else:
            parts = [part.strip() for part in line.split()]

        parts = [part.strip() for part in parts if part is not None]
        if len(parts) >= 4:
            email, password, recovery, link = parts[0], parts[1], parts[2], parts[3]
            country = parts[4] if len(parts) >= 5 else ""
            data.append(
                {
                    "email": email,
                    "password": password,
                    "recovery": recovery,
                    "link": link,
                    "country": country,
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


def enrich_familybot_card_details(df):
    if (
        "country" not in df.columns
        or df["country"].astype(str).str.strip().eq("").all()
    ):
        return (
            False,
            "familybot_card_details upload requires a country selection to assign fake details.",
        )

    country_values = df["country"].astype(str).str.strip().str.lower().unique()
    if len(country_values) != 1:
        return (
            False,
            "All uploaded familybot_card_details rows must use the same country.",
        )

    country = country_values[0]
    conn = get_db_connection()
    if conn is None:
        return False, "No database connection available for card enrichment."

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT firstnames FROM familybot_first_names WHERE LOWER(country) = %s",
            (country,),
        )
        first_names = [row[0].strip() for row in cursor.fetchall() if row[0]]

        cursor.execute(
            "SELECT surnames FROM familybot_surnames WHERE LOWER(country) = %s",
            (country,),
        )
        surnames = [row[0].strip() for row in cursor.fetchall() if row[0]]

        cursor.execute(
            "SELECT address_line1, city, state, postal_code FROM familybot_fake_details WHERE LOWER(country) = %s",
            (country,),
        )
        fake_rows = [
            {
                "address_line1": row[0] or "",
                "city": row[1] or "",
                "state": row[2] or "",
                "postal_code": row[3] or "",
            }
            for row in cursor.fetchall()
        ]
        cursor.close()

        if not first_names:
            return False, f"No first names found for country '{country}'."
        if not surnames:
            return False, f"No surnames found for country '{country}'."
        if not fake_rows:
            return False, f"No fake details found for country '{country}'."

        df = df.copy()
        df["name_on_card"] = [
            f"{random.choice(first_names)} {random.choice(surnames)}"
            for _ in range(len(df))
        ]
        chosen_fake_rows = [random.choice(fake_rows) for _ in range(len(df))]
        df["address_line1"] = [item["address_line1"] for item in chosen_fake_rows]
        df["city"] = [item["city"] for item in chosen_fake_rows]
        df["state"] = [item["state"] for item in chosen_fake_rows]
        df["postal_code"] = [item["postal_code"] for item in chosen_fake_rows]
        return True, df
    except Exception as exc:
        return False, str(exc)


def insert_into_db(
    table_name, df, server_ip=None, bot_type=None, overwrite=False, chunk_size=10000
):
    conn = get_db_connection()
    if conn is None:
        return False, "No database connection"
    try:
        if table_name == "familybot_card_details":
            success, enriched = enrich_familybot_card_details(df)
            if not success:
                return False, enriched
            df = enriched
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
            server_ip = "manual"
            bot_type = "manual"
            columns = (
                "server_ip, bot_type, date_time, email, pass, recovery, link, country"
            )
            placeholders = "%s, %s, %s, %s, %s, %s, %s, %s"
            values = [
                (
                    server_ip,
                    bot_type,
                    datetime.now(),
                    row.email,
                    row.password,
                    row.recovery,
                    row.link,
                    getattr(row, "country", ""),
                )
                for row in df.itertuples(index=False)
            ]
            history_columns = columns
            history_placeholders = placeholders
            history_query = f"INSERT INTO familybot_extracted_family_links_history ({history_columns}) VALUES ({history_placeholders})"
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
        total_rows = len(values)
        if total_rows == 0:
            cursor.close()
            conn.close()
            return True, f"Inserted 0 rows into {table_name}."

        if total_rows > chunk_size:
            if table_name == "sender_recipients":
                db_configs = get_db_config()
                engine = create_engine(
                    f"mysql+pymysql://{db_configs['user']}:{db_configs['password']}@{db_configs['host']}/{db_configs['database']}"
                )
                total_rows = len(df)
                # Lowering chunk_size to 10,000 prevents MySQL server thread-RAM exhaustion
                chunk_size = 10000

                if total_rows > 0:
                    # Initialize Streamlit UI components
                    progress_bar = st.progress(0.0)
                    status_text = st.empty()

                    inserted = 0
                    total_chunks = math.ceil(total_rows / chunk_size)

                    # 3. Explicitly loop through the DataFrame in chunks
                    for i in range(total_chunks):
                        start_idx = i * chunk_size
                        end_idx = min(start_idx + chunk_size, total_rows)

                        # Slice the DataFrame (pandas uses memory views, so it does not duplicate data)
                        chunk_df = df.iloc[start_idx:end_idx]

                        # Upload this specific chunk using optimized multi-row inserts
                        chunk_df.to_sql(
                            name=table_name,
                            con=engine,
                            if_exists="append",
                            index=False,
                            method="multi",
                        )

                        # 4. Update progress metrics immediately after the chunk completes
                        inserted += len(chunk_df)
                        progress_percentage = min(inserted / total_rows, 1.0)

                        progress_bar.progress(progress_percentage)
                        status_text.text(
                            f"Uploading {inserted:,} / {total_rows:,} rows into {table_name}..."
                        )

                    # 5. Clean up UI states upon successful completion
                    status_text.text(
                        f"Finished uploading all {inserted:,} rows into {table_name}."
                    )

            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                inserted = 0
                for start in range(0, total_rows, chunk_size):
                    chunk_values = values[start : start + chunk_size]
                    cursor.executemany(query, chunk_values)
                    if table_name == "familybot_extracted_family_links":
                        cursor.executemany(history_query, chunk_values)
                    conn.commit()
                    inserted += len(chunk_values)
                    progress_bar.progress(min(inserted / total_rows, 1.0))
                    status_text.text(
                        f"Uploading {inserted} / {total_rows} rows into {table_name}..."
                    )
                status_text.text(
                    f"Finished uploading {inserted} / {total_rows} rows into {table_name}."
                )
        else:
            cursor.executemany(query, values)
            if table_name == "familybot_extracted_family_links":
                cursor.executemany(history_query, values)
            conn.commit()
            inserted = cursor.rowcount if cursor.rowcount != -1 else total_rows
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
        # "family_link": "Family Links",
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
        "familybot_extracted_family_links",
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
            if table_name == "familybot_extracted_family_links":
                if "country" in df.columns:
                    df["country"] = (
                        df["country"]
                        .fillna("")
                        .astype(str)
                        .replace("", selected_country)
                    )
                else:
                    df["country"] = selected_country
            else:
                df["country"] = selected_country

        st.subheader("Preview top 10 files")
        st.dataframe(df.head(10), width="stretch")

        valid, message = validate_dataframe(table_name, df)
        if not valid:
            st.error(message)
            return

        if table_name == "familybot_card_details":
            with st.spinner("Getting enriched card details..."):
                success, enriched_df = enrich_familybot_card_details(df)
            if not success:
                st.error(enriched_df)
                return
            df = enriched_df
            st.success("Enriched card details are ready.")
            st.subheader("Preview top 10 enriched card rows")
            st.dataframe(df.head(10), width="stretch")
            st.info(
                "These rows include the assigned name_on_card, state, city, address_line1, and postal_code."
            )
        else:
            st.success(message)
            st.write(f"Rows found: {len(df)}")

        server_ip = None
        bot_type = None
        if table_name == "cache_bins":
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
        "Netherlands",
    ]

    # Initialize session state keys at function start
    if "sender_table_selected" not in st.session_state:
        st.session_state.sender_table_selected = None
    if "sender_df" not in st.session_state:
        st.session_state.sender_df = None
    if "sender_country" not in st.session_state:
        st.session_state.sender_country = None
    if "sender_data_source" not in st.session_state:
        st.session_state.sender_data_source = None

    table_name = st.selectbox(
        "Select destination table",
        list(table_options.keys()),
        format_func=lambda x: table_options[x],
        key="sender_table",
    )
    st.session_state.sender_table_selected = table_name
    st.markdown(f"**Target table:** `{table_name}`")

    selected_country = st.selectbox(
        "Select country for uploaded rows",
        country_options,
        key=f"sender_country_{table_name}",
    )
    st.session_state.sender_country = selected_country

    upload_method = None
    if table_name == "sender_link":
        upload_method = st.radio(
            "Upload method",
            ["Add to existing links", "Overwrite existing links"],
            key=f"sender_link_method_{table_name}",
        )

    # Data source option for sender_input_accounts
    data_source = None
    if table_name == "sender_input_accounts":
        data_source = st.radio(
            "Data source",
            ["Upload file", "Get from Database (Cache Bins)"],
            key=f"sender_data_source_{table_name}",
        )
        st.session_state.sender_data_source = data_source

    file_types = ["txt", "csv"]
    uploaded_file = None
    df = None

    # Handle file upload or database loading
    if (
        table_name == "sender_input_accounts"
        and data_source == "Get from Database (Cache Bins)"
    ):
        st.info(
            "This will load emails from cache_bins, parse them, and get password/recovery from the database."
        )
        if st.button("Load emails from cache bins", key=f"load_cache_{table_name}"):
            with st.spinner("Loading emails from cache bins..."):
                df = load_emails_from_cache_bins(selected_country)
            if df is not None:
                st.session_state.sender_df = df
                st.rerun()
    else:
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
            df = parse_text_list(uploaded_file, "recipient_email").drop_duplicates()
        elif table_name == "sender_subjects":
            df = parse_text_list(uploaded_file, "subject")
        elif table_name == "sender_texts":
            df = parse_text_list(uploaded_file, "text")

        if df is not None:
            st.session_state.sender_df = df

    # Use cached dataframe if available
    if df is None and st.session_state.sender_df is not None:
        df = st.session_state.sender_df

    if df is not None:
        if selected_country and "country" not in df.columns:
            df["country"] = selected_country

        st.subheader("Preview top 10 files")
        st.dataframe(df.head(10), width="stretch")

        valid, message = validate_dataframe(table_name, df)
        if not valid:
            st.error(message)
            return

        st.success(message)
        st.write(f"Rows found: {len(df)}")

        if table_name == "sender_recipients":
            st.subheader("Step 6: Assign servers to recipients")

            settings = load_full_settings()
            server_ips = settings.get("email_sender", {}).get("SERVER_IPS", [])

            # Server management in expander
            with st.expander("Manage Servers", expanded=False):
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

            if not server_ips:
                st.error("No servers configured. Please add servers first.")
                return

            selected_servers = st.multiselect(
                "Select servers for recipient assignment",
                server_ips,
                key=f"selected_servers_multi_{table_name}",
            )

            if not selected_servers:
                st.warning("Select at least one server to proceed.")
                return

            dist_method = st.radio(
                "Recipient distribution method",
                ["Equal", "Manual"],
                key=f"recipient_dist_method_{table_name}",
                horizontal=True,
            )

            dist_key = f"recipient_distribution_{table_name}"
            if dist_key not in st.session_state:
                st.session_state[dist_key] = []
            distribution = st.session_state[dist_key]

            if dist_method == "Equal":
                if st.button(
                    "Distribute recipients equally",
                    key=f"equal_recipient_dist_{table_name}",
                ):
                    total = len(df)
                    num_servers = len(selected_servers)
                    base = total // num_servers
                    remainder = total % num_servers
                    distribution = []
                    for i, server in enumerate(selected_servers):
                        count = base + (1 if i < remainder else 0)
                        distribution.append({"server": server, "count": count})
                    st.session_state[dist_key] = distribution
                    st.success("Recipients distributed equally across servers.")
                    st.rerun()
            else:
                st.write(
                    "**Manual distribution**: set how many recipients each selected server should receive."
                )
                manual_counts = {}
                total_assigned = 0
                for server in selected_servers:
                    count = st.number_input(
                        f"Recipients for {server}",
                        min_value=0,
                        max_value=len(df),
                        value=0,
                        key=f"manual_recipient_count_{server}_{table_name}",
                    )
                    manual_counts[server] = count
                    total_assigned += count

                st.write(f"Total assigned: {total_assigned} / {len(df)}")
                if total_assigned != len(df):
                    st.warning(
                        "Total recipient counts must equal the number of uploaded recipients."
                    )
                if st.button(
                    "Apply manual distribution",
                    key=f"apply_manual_recipient_dist_{table_name}",
                ):
                    if total_assigned != len(df):
                        st.error(
                            "Please assign exactly the total number of recipients across selected servers."
                        )
                    else:
                        distribution = [
                            {"server": server, "count": count}
                            for server, count in manual_counts.items()
                            if count > 0
                        ]
                        st.session_state[dist_key] = distribution
                        st.success("Manual recipient distribution saved.")
                        st.rerun()

            total_assigned = sum(d["count"] for d in distribution)
            st.write("---")
            st.write("**Current Recipient Distribution:**")
            if distribution:
                for d in distribution:
                    st.write(f"- {d['server']}: {d['count']} recipients")
            else:
                st.info("No distribution configured yet.")

            if total_assigned != len(df):
                st.info("Please complete recipient distribution before upload.")
                return

            df["server_ip"] = ""
            start_idx = 0
            for d in distribution:
                server = d["server"]
                server_count = d["count"]
                end_idx = start_idx + server_count
                df.loc[start_idx : end_idx - 1, "server_ip"] = server
                start_idx = end_idx

            st.success("Recipients assigned to servers.")
            st.write(
                f"Assigned {len(df)} recipients across servers: {', '.join([d['server'] for d in distribution])}"
            )
        elif table_name == "sender_input_accounts":
            st.subheader("Step 6: Server Distribution & Batching")

            settings = load_full_settings()
            server_ips = settings.get("email_sender", {}).get("SERVER_IPS", [])

            # Server management in expander
            with st.expander("Manage Servers", expanded=False):
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

            if not server_ips:
                st.error("No servers configured. Please add servers first.")
                return

            # Select servers with session state key that persists
            selected_servers = st.multiselect(
                "Select servers for distribution",
                server_ips,
                key=f"selected_servers_multi_{table_name}",
            )

            if not selected_servers:
                st.warning("Select at least one server to proceed.")
                return

            # Store selected servers in session state
            servers_key = f"selected_servers_{table_name}"
            st.session_state[servers_key] = selected_servers

            # Configure batches for each server
            st.write("**Configure batch count for each server:**")
            server_batches = {}
            for server in selected_servers:
                batch_count_key = f"batch_count_{server}_{table_name}"
                num_batches = st.number_input(
                    f"Number of batches for server {server}",
                    min_value=1,
                    value=1,
                    key=batch_count_key,
                )
                server_batches[server] = num_batches

            # Distribution method
            dist_method = st.radio(
                "Server distribution method",
                ["Manual", "Equal"],
                key=f"dist_method_{table_name}",
                horizontal=True,
            )

            # Initialize distribution in session state
            dist_key = f"distribution_{table_name}"
            if dist_key not in st.session_state:
                st.session_state[dist_key] = []

            distribution = st.session_state[dist_key]

            if dist_method == "Equal":
                if st.button(
                    "Distribute Equally Across Servers", key=f"equal_dist_{table_name}"
                ):
                    total = len(df)
                    num_servers = len(selected_servers)
                    base = total // num_servers
                    remainder = total % num_servers
                    distribution = []
                    for i, server in enumerate(selected_servers):
                        count = base + (1 if i < remainder else 0)
                        distribution.append(
                            {"server": server, "count": count, "batches": []}
                        )
                    st.session_state[dist_key] = distribution
                    st.success("Distributed equally across servers.")
                    st.rerun()
            else:  # Manual
                st.write(
                    "Assign servers sequentially. First assignment gets the top rows, etc."
                )
                remaining = len(df) - sum(d["count"] for d in distribution)
                st.write(f"Remaining rows to assign: **{remaining}**")

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
                            found = False
                            for d in distribution:
                                if d["server"] == manual_server:
                                    d["count"] = manual_count
                                    found = True
                                    break
                            if not found:
                                distribution.append(
                                    {
                                        "server": manual_server,
                                        "count": manual_count,
                                        "batches": [],
                                    }
                                )
                            st.session_state[dist_key] = distribution
                            st.success(
                                f"Assigned {manual_count} rows to {manual_server}"
                            )
                            st.rerun()

            # Show current distribution and configure batches
            st.write("---")
            st.write("**Current Distribution & Batch Configuration:**")
            total_assigned = sum(d["count"] for d in distribution)
            progress_text = f"Total: {len(df)} | Assigned: {total_assigned} | Remaining: {len(df) - total_assigned}"

            if total_assigned > 0:
                progress = min(total_assigned / len(df), 1.0)
                st.progress(progress, text=progress_text)
            else:
                st.info(progress_text)

            if distribution:
                for i, d in enumerate(distribution):
                    server = d["server"]
                    count = d["count"]
                    num_batches = server_batches.get(server, 1)

                    status_icon = (
                        "✓ Complete"
                        if d.get("batches")
                        and sum(b["count"] for b in d["batches"]) == count
                        else "⧖ Pending"
                    )
                    with st.expander(
                        f"**{i + 1}. Server {server}: {count} rows** ({status_icon})",
                        expanded=False,
                    ):
                        # Batch distribution for this server
                        batch_dist_method = st.radio(
                            f"Batch distribution method for {server}",
                            ["Manual", "Equal"],
                            key=f"batch_dist_{server}_{table_name}",
                            horizontal=True,
                        )

                        if batch_dist_method == "Equal":
                            if st.button(
                                f"Distribute {server} batches equally",
                                key=f"equal_batch_{server}_{table_name}",
                            ):
                                base = count // num_batches
                                remainder = count % num_batches
                                batches = []
                                for j in range(num_batches):
                                    batch_count = base + (1 if j < remainder else 0)
                                    batches.append(
                                        {
                                            "batch": f"batch_{j + 1}",
                                            "count": batch_count,
                                        }
                                    )
                                d["batches"] = batches
                                st.session_state[dist_key] = distribution
                                st.success(f"✓ Distributed {server} batches equally.")
                                st.rerun()
                        else:  # Manual batch distribution
                            st.write(
                                f"Enter counts for each batch (total must equal {count}):"
                            )

                            # Initialize batch counts in session state
                            batch_counts_key = f"batch_counts_{server}_{table_name}"
                            if batch_counts_key not in st.session_state:
                                st.session_state[batch_counts_key] = [0] * num_batches

                            batch_counts = st.session_state[batch_counts_key]

                            # Ensure we have the right number of batch counts
                            if len(batch_counts) != num_batches:
                                batch_counts = [0] * num_batches
                                st.session_state[batch_counts_key] = batch_counts

                            # Input boxes for each batch
                            cols = st.columns(min(num_batches, 3))  # Max 3 columns
                            for j in range(num_batches):
                                col_idx = j % 3
                                with cols[col_idx]:
                                    batch_counts[j] = st.number_input(
                                        f"Batch {j + 1}",
                                        min_value=0,
                                        max_value=count,
                                        value=batch_counts[j],
                                        key=f"batch_{j}_{server}_{table_name}",
                                    )

                            current_total = sum(batch_counts)
                            st.write(f"Total: {current_total} / {count}")

                            if current_total != count:
                                st.warning(f"Batch counts must total exactly {count}")
                            else:
                                if st.button(
                                    f"Apply batch distribution for {server}",
                                    key=f"apply_batches_{server}_{table_name}",
                                ):
                                    batches = []
                                    for j in range(num_batches):
                                        if batch_counts[j] > 0:
                                            batches.append(
                                                {
                                                    "batch": f"batch_{j + 1}",
                                                    "count": batch_counts[j],
                                                }
                                            )
                                    d["batches"] = batches
                                    st.session_state[dist_key] = distribution
                                    st.success(
                                        f"Applied batch distribution for {server}"
                                    )
                                    st.rerun()

                        # Show batches for this server
                        if d.get("batches"):
                            st.write("**Configured batches:**")
                            for j, batch in enumerate(d["batches"]):
                                st.write(f"  • {batch['batch']}: {batch['count']} rows")

                            if st.button(
                                f"Clear batches for {server}",
                                key=f"clear_batches_{server}_{table_name}",
                            ):
                                d["batches"] = []
                                batch_counts_key = f"batch_counts_{server}_{table_name}"
                                if batch_counts_key in st.session_state:
                                    del st.session_state[batch_counts_key]
                                st.session_state[dist_key] = distribution
                                st.rerun()

                st.write("---")

                if st.button("Reset Distribution", key=f"clear_dist_{table_name}"):
                    st.session_state[dist_key] = []
                    for server in selected_servers:
                        batch_counts_key = f"batch_counts_{server}_{table_name}"
                        if batch_counts_key in st.session_state:
                            del st.session_state[batch_counts_key]
                    st.rerun()

            # Check if distribution and batching is complete
            distribution_complete = total_assigned == len(df)
            batching_complete = all(
                sum(b.get("count", 0) for b in d.get("batches", [])) == d["count"]
                for d in distribution
            )

            if not distribution_complete:
                st.info("Please complete the server distribution before uploading.")
                return
            if not batching_complete:
                st.info(
                    "Please complete the batch distribution for all servers before uploading."
                )
                return

            st.success("✓ All distributions configured!")

            # Assign server_ip and batch to df
            df["server_ip"] = ""
            df["batch"] = ""
            start_idx = 0
            for d in distribution:
                server = d["server"]
                server_count = d["count"]
                end_idx = start_idx + server_count

                # Assign server_ip
                df.loc[start_idx : end_idx - 1, "server_ip"] = server

                # Assign batches within this server's rows
                batch_start = start_idx
                for batch in d.get("batches", []):
                    batch_end = batch_start + batch["count"]
                    df.loc[batch_start : batch_end - 1, "batch"] = batch["batch"]
                    batch_start = batch_end

                start_idx = end_idx
        # else:
        #     # For other tables without distribution
        #     df["server_ip"] = ""
        #     df["batch"] = ""

        # Final upload step
        st.subheader("Step 7: Upload to Database")
        overwrite = (
            upload_method == "Overwrite existing links"
            if table_name == "sender_link"
            else False
        )

        if st.button("Upload to database", key=f"sender_upload_{table_name}"):
            with st.spinner("Uploading..."):
                success, result_message = insert_into_db(
                    table_name,
                    df,
                    overwrite=overwrite,
                    chunk_size=50000 if table_name == "sender_recipients" else 50000,
                )
                if success:
                    st.success(result_message)
                    st.session_state.sender_df = (
                        None  # Clear state after successful upload
                    )
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
        query = f"SELECT LOWER({group_column}), COUNT(*) as total FROM {table}"
        if where_clause:
            query += f" WHERE {where_clause}"
        query += " GROUP BY LOWER(" + group_column + ") ORDER BY total DESC"
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


def get_table_distinct_values(table, column, where_clause=None, params=None):
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        query = f"SELECT DISTINCT {column} FROM {table}"
        if where_clause:
            query += f" WHERE {where_clause}"
        cursor.execute(query, params or ())
        return [row[0] for row in cursor.fetchall() if row and row[0]]
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except:
            pass


def get_familybot_card_interval_hours():
    settings = load_full_settings()
    try:
        interval = int(
            settings.get("familybot", {}).get("CREDIT_CARD_INTERVAL_HRS", 50)
        )
        if interval <= 0:
            interval = 50
    except Exception:
        interval = 50
    return interval


def get_familybot_available_cards_count():
    conn = get_db_connection()
    if conn is None:
        return 0

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT card_number, expiry_month_year, cvv FROM familybot_card_details"
        )
        cards = cursor.fetchall()

        cursor.execute(
            "SELECT card_num, `exp_month/year` AS exp_month_year, cvv, use_datetime FROM familybot_card_usage_log"
        )
        usage_rows = cursor.fetchall()

        usage = {}
        for row in usage_rows:
            key = (
                str(row["card_num"]),
                row["exp_month_year"],
                str(row["cvv"]),
            )
            usage.setdefault(key, []).append(row["use_datetime"])

        interval_hours = get_familybot_card_interval_hours()
        now = datetime.now()
        available_cards = 0

        for card in cards:
            card_num = str(card.get("card_number", ""))
            expiry = card.get("expiry_month_year") or ""
            cvv = str(card.get("cvv", ""))
            key = (card_num, expiry, cvv)
            timestamps = sorted(usage.get(key, []))
            uses = len(timestamps)
            if uses >= 5:
                continue
            if uses in [0, 1, 3]:
                available_cards += 1
                continue
            if uses in [2, 4] and timestamps:
                if now > timestamps[-1] + timedelta(hours=interval_hours):
                    available_cards += 1

        return available_cards
    except Exception:
        return 0
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


def render_hotmail_stats():
    st.header("Hotmail Bot Stats")

    try:
        cards = [
            {
                "label": "Total Available Input Accounts",
                "value": db_count("input_emails"),
            },
            {
                "label": "Total Available Family Links (from FamilyBot)",
                "value": db_count("familybot_extracted_family_links"),
            },
            {
                "label": "Total Processed Hotmail Accounts",
                "value": db_count("processed_emails", "bot_type = %s", ("hotmailbot",)),
            },
            {
                "label": "Total Failed Accounts",
                "value": db_count("failed_smtp", "bot_type = %s", ("hotmailbot",)),
            },
        ]
        render_stats_cards(cards)
    except Exception as e:
        st.error(f"Error loading Hotmail Bot stats: {e}")

    st.divider()


def render_familybot_stats():
    st.header("Family Bot Stats")

    today = datetime.now().date()
    default_start = today - timedelta(days=30)
    date_range = st.date_input(
        "Select date range",
        [default_start, today],
        key="familybot_stats_date_range",
    )
    if not isinstance(date_range, list) and not isinstance(date_range, tuple):
        st.error("Please select a valid start and end date.")
        return
    if len(date_range) != 2:
        st.error("Please select both a start date and an end date.")
        return

    start_date, end_date = date_range
    if start_date is None or end_date is None:
        st.error("Please select a valid date range.")
        return

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    if start_dt > end_dt:
        st.error("Start date must be before end date.")
        return

    total_cards = db_count("familybot_card_details")
    total_failed_cards = db_count(
        "familybot_failed_cards",
        "date_time BETWEEN %s AND %s",
        (start_dt, end_dt),
    )
    available_cards = get_familybot_available_cards_count()
    total_fully_used_cards = db_count(
        "familybot_fully_used_cards",
        "date_time BETWEEN %s AND %s",
        (start_dt, end_dt),
    )
    total_firstnames = sum(
        count for _, count in db_group_count("familybot_first_names", "country")
    )
    total_surnames = sum(
        count for _, count in db_group_count("familybot_surnames", "country")
    )
    total_fake_details = sum(
        count for _, count in db_group_count("familybot_fake_details", "country")
    )

    try:
        cards = [
            {
                "label": "Total Email Inputs",
                "value": db_count("input_emails"),
            },
            {
                "label": "Extracted Family Links",
                "value": db_count("familybot_extracted_family_links"),
            },
            {"label": "Total Cards", "value": total_cards},
            {"label": "Total Failed Cards", "value": total_failed_cards},
            {"label": "Cards Available for Use", "value": available_cards},
            {"label": "Total Fully Used Cards", "value": total_fully_used_cards},
            {"label": "Available First Names", "value": total_firstnames},
            {"label": "Available Surnames", "value": total_surnames},
        ]
        render_stats_cards(cards)
    except Exception as e:
        st.error(f"Error loading Family Bot stats: {e}")
        return

    st.divider()

    try:
        card_by_country = db_group_count(
            "familybot_card_details",
            "country",
            "country IS NOT NULL AND country <> ''",
            (),
            limit=1000,
        )
        extracted_links_by_country = db_group_count(
            "familybot_extracted_family_links",
            "country",
            "country IS NOT NULL AND country <> ''",
            (),
            limit=1000,
        )
        failed_by_country = db_group_count(
            "familybot_failed_cards",
            "country",
            "date_time BETWEEN %s AND %s AND country IS NOT NULL AND country <> ''",
            (start_dt, end_dt),
            limit=1000,
        )
        fully_used_by_country = db_group_count(
            "familybot_fully_used_cards",
            "country",
            "date_time BETWEEN %s AND %s AND country IS NOT NULL AND country <> ''",
            (start_dt, end_dt),
            limit=1000,
        )
        firstnames_by_country = db_group_count(
            "familybot_first_names",
            "country",
            "country IS NOT NULL AND country <> ''",
            (),
            limit=1000,
        )
        surnames_by_country = db_group_count(
            "familybot_surnames",
            "country",
            "country IS NOT NULL AND country <> ''",
            (),
            limit=1000,
        )
        fake_details_by_country = db_group_count(
            "familybot_fake_details",
            "country",
            "country IS NOT NULL AND country <> ''",
            (),
            limit=1000,
        )

        if card_by_country:
            st.subheader("Total Cards by Country")
            st.dataframe(
                pd.DataFrame(card_by_country, columns=["Country", "Count"]),
                width="stretch",
            )

        if extracted_links_by_country:
            st.subheader("Extracted Family Links by Country")
            st.dataframe(
                pd.DataFrame(extracted_links_by_country, columns=["Country", "Count"]),
                width="stretch",
            )

        if failed_by_country:
            st.subheader("Failed Cards by Country")
            st.dataframe(
                pd.DataFrame(failed_by_country, columns=["Country", "Count"]),
                width="stretch",
            )

        if fully_used_by_country:
            st.subheader("Fully Used Cards by Country")
            st.dataframe(
                pd.DataFrame(fully_used_by_country, columns=["Country", "Count"]),
                width="stretch",
            )

        if firstnames_by_country or surnames_by_country or fake_details_by_country:
            st.subheader("Available Data by Country")
            country_rows = {}
            for country, count in firstnames_by_country:
                country_rows.setdefault(country, {})["First Names"] = count
            for country, count in surnames_by_country:
                country_rows.setdefault(country, {})["Surnames"] = count
            for country, count in fake_details_by_country:
                country_rows.setdefault(country, {})["Fake Details"] = count

            breakdown = []
            for country, values in sorted(country_rows.items()):
                breakdown.append(
                    {
                        "Country": country,
                        "First Names": values.get("First Names", 0),
                        "Surnames": values.get("Surnames", 0),
                        "Fake Details": values.get("Fake Details", 0),
                    }
                )
            st.dataframe(pd.DataFrame(breakdown), width="stretch")

    except Exception as e:
        st.error(f"Error building Family Bot breakdowns: {e}")

    st.divider()
    st.subheader("Failed Cards")

    failed_countries = get_table_distinct_values("familybot_failed_cards", "country")
    if failed_countries:
        selected_failed_countries = st.multiselect(
            "Filter failed cards by country",
            failed_countries,
            default=failed_countries,
            key="failed_cards_country_filter",
        )
    else:
        selected_failed_countries = []

    failed_where = "date_time BETWEEN %s AND %s"
    failed_params = [start_dt, end_dt]
    if selected_failed_countries:
        placeholders = ",".join(["%s"] * len(selected_failed_countries))
        failed_where += f" AND country IN ({placeholders})"
        failed_params += selected_failed_countries

    try:
        conn = get_db_connection()
        if conn is None:
            st.error("Unable to connect to database")
            return

        cursor = conn.cursor()
        query = (
            "SELECT date_time, card_number, expiry_month_year, cvv, reason_for_fail, country "
            f"FROM familybot_failed_cards WHERE {failed_where} ORDER BY date_time DESC"
        )
        cursor.execute(query, tuple(failed_params))
        failed_rows = cursor.fetchall()
        cursor.close()
        conn.close()

        if not failed_rows:
            st.info("No failed cards found for the selected filters.")
            return

        failed_df = pd.DataFrame(
            failed_rows,
            columns=[
                "Date Time",
                "Card Number",
                "Expiry Month/Year",
                "CVV",
                "Reason For Fail",
                "Country",
            ],
        )
        st.dataframe(failed_df, width="stretch")

        csv = failed_df.to_csv(index=False)
        st.download_button(
            "Download failed cards as CSV",
            csv,
            file_name="familybot_failed_cards.csv",
            mime="text/csv",
        )
    except Exception as e:
        st.error(f"Error loading failed cards table: {e}")


def render_email_sender_stats():
    st.header("Email Sender Stats")

    today = datetime.now().date()
    default_start = today - timedelta(days=30)
    date_range = st.date_input(
        "Select date range for date-based sender stats",
        [default_start, today],
        key="email_sender_stats_date_range",
    )
    if not isinstance(date_range, (list, tuple)):
        st.error("Please select a valid start and end date.")
        return
    if len(date_range) != 2:
        st.error("Please select both a start date and an end date.")
        return

    start_date, end_date = date_range
    if start_date is None or end_date is None:
        st.error("Please select a valid date range.")
        return

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    if start_dt > end_dt:
        st.error("Start date must be before end date.")
        return

    # Unassigned sender accounts insight from cache bins
    try:
        unassigned_count = count_unassigned_sender_accounts()
        st.info(f"Total unassigned sender accounts in cache bins: {unassigned_count}")
    except Exception as e:
        st.warning(f"Unable to compute unassigned sender accounts: {e}")

    try:
        total_sender_accounts = db_count("sender_input_accounts")
        total_recipients = db_count("sender_recipients")
        total_invalid_recipients = db_count("sender_invalid_recipients")
        total_available_hyperlinks = db_count("sender_hyperlink_text")
        total_links = db_count("sender_link")
        total_subjects = db_count("sender_subjects")
        total_texts = db_count("sender_texts")

        total_processed_range = db_count(
            "sender_processed_accounts",
            "date_time BETWEEN %s AND %s",
            (start_dt, end_dt),
        )
        total_failed_range = db_count(
            "sender_failed_accounts",
            "date_time BETWEEN %s AND %s",
            (start_dt, end_dt),
        )
        total_sent_recipients_range = db_count(
            "sender_sent_recipients",
            "date_time BETWEEN %s AND %s",
            (start_dt, end_dt),
        )

        cards = [
            {"label": "Total Sender Accounts", "value": total_sender_accounts},
            {"label": "Total Recipients", "value": total_recipients},
            {"label": "Invalid Recipients", "value": total_invalid_recipients},
            {"label": "Available Hyperlinks", "value": total_available_hyperlinks},
            {"label": "Total Links", "value": total_links},
            {"label": "Total Subjects", "value": total_subjects},
            {"label": "Total Texts", "value": total_texts},
            {
                "label": "Processed Accounts in Range",
                "value": total_processed_range,
            },
            {
                "label": "Failed Accounts in Range",
                "value": total_failed_range,
            },
            {
                "label": "Sent Recipients in Range",
                "value": total_sent_recipients_range,
            },
        ]
        render_stats_cards(cards)
    except Exception as e:
        st.error(f"Error loading Email Sender stats: {e}")

    st.divider()
    st.subheader("Sender Breakdown by Country")

    try:
        sender_country = db_group_count(
            "sender_input_accounts",
            "country",
            "country IS NOT NULL AND country <> ''",
            (),
            limit=1000,
        )
        recipient_country = db_group_count(
            "sender_recipients",
            "country",
            "country IS NOT NULL AND country <> ''",
            (),
            limit=1000,
        )
        hyperlink_country = db_group_count(
            "sender_hyperlink_text",
            "country",
            "country IS NOT NULL AND country <> ''",
            (),
            limit=1000,
        )
        link_country = db_group_count(
            "sender_link",
            "country",
            "country IS NOT NULL AND country <> ''",
            (),
            limit=1000,
        )
        subject_country = db_group_count(
            "sender_subjects",
            "country",
            "country IS NOT NULL AND country <> ''",
            (),
            limit=1000,
        )
        text_country = db_group_count(
            "sender_texts",
            "country",
            "country IS NOT NULL AND country <> ''",
            (),
            limit=1000,
        )
        invalid_recipient_country = db_group_count(
            "sender_invalid_recipients",
            "country",
            "country IS NOT NULL AND country <> ''",
            (),
            limit=1000,
        )

        if sender_country:
            st.markdown("**Sender Accounts by Country**")
            st.dataframe(
                pd.DataFrame(sender_country, columns=["Country", "Count"]),
                width="stretch",
            )

        if recipient_country:
            st.markdown("**Recipients by Country**")
            st.dataframe(
                pd.DataFrame(recipient_country, columns=["Country", "Count"]),
                width="stretch",
            )

        if hyperlink_country:
            st.markdown("**Available Hyperlinks by Country**")
            st.dataframe(
                pd.DataFrame(hyperlink_country, columns=["Country", "Count"]),
                width="stretch",
            )

        if link_country:
            st.markdown("**Links by Country**")
            st.dataframe(
                pd.DataFrame(link_country, columns=["Country", "Count"]),
                width="stretch",
            )

        if subject_country:
            st.markdown("**Subjects by Country**")
            st.dataframe(
                pd.DataFrame(subject_country, columns=["Country", "Count"]),
                width="stretch",
            )

        if text_country:
            st.markdown("**Text Templates by Country**")
            st.dataframe(
                pd.DataFrame(text_country, columns=["Country", "Count"]),
                width="stretch",
            )

        if invalid_recipient_country:
            st.markdown("**Invalid Recipients by Country**")
            st.dataframe(
                pd.DataFrame(invalid_recipient_country, columns=["Country", "Count"]),
                width="stretch",
            )
    except Exception as e:
        st.error(f"Error building email sender country breakdowns: {e}")

    st.divider()
    st.subheader("Sender Accounts by IP")

    try:
        server_ip_counts = db_group_count(
            "sender_input_accounts",
            "server_ip",
            "server_ip IS NOT NULL AND server_ip <> ''",
            (),
            limit=1000,
        )
        if server_ip_counts:
            st.dataframe(
                pd.DataFrame(server_ip_counts, columns=["Server IP", "Count"]),
                width="stretch",
            )
        else:
            st.info("No sender server IP data available.")
    except Exception as e:
        st.error(f"Error building sender IP breakdown: {e}")

    st.divider()
    st.subheader("Sender Accounts by Server & Batch")

    try:
        conn = get_db_connection()
        if conn is not None:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COALESCE(server_ip, 'Unassigned') as server,
                    COALESCE(batch, 'No Batch') as batch_name,
                    COUNT(*) as count
                FROM sender_input_accounts
                GROUP BY server_ip, batch
                ORDER BY server_ip, batch
            """)

            results = cursor.fetchall()
            cursor.close()
            conn.close()

            if results:
                server_data = {}
                for server, batch, count in results:
                    if server not in server_data:
                        server_data[server] = []
                    server_data[server].append((batch, count))

                for server in sorted(server_data.keys()):
                    with st.expander(
                        f"**Server: {server}** (Total: {sum(count for _, count in server_data[server])} accounts)"
                    ):
                        batch_data = server_data[server]
                        if batch_data:
                            batch_df = pd.DataFrame(
                                batch_data, columns=["Batch", "Count"]
                            )
                            batch_df = batch_df.sort_values("Batch")
                            st.dataframe(batch_df, width="stretch")

                            total_accounts = batch_df["Count"].sum()
                            unique_batches = len(batch_df)
                            st.write(
                                f"**Summary:** {total_accounts} accounts across {unique_batches} batches"
                            )
                        else:
                            st.write("No batch data available")
            else:
                st.info("No sender accounts found in the database.")
        else:
            st.error("Unable to connect to database")
    except Exception as e:
        st.error(f"Error loading server/batch breakdown: {e}")

    st.divider()
    st.subheader("Quick Insights")
    st.write(
        "Monitor your email sender distribution across servers, countries, and template resources."
    )
    st.write(
        "Use the date filter above to inspect processed, failed, and sent recipient activity in the selected range."
    )


def render_password_changer_stats():
    st.header("Password Changer Stats")

    try:
        cards = [
            {
                "label": "Total Password Changer Accounts",
                "value": db_count("password_changer_accounts"),
            },
            {
                "label": "Total Saved Accounts",
                "value": db_count(
                    "accounts_details", "bot_type = %s", ("password_changer",)
                ),
            },
            {
                "label": "Total Failed SMTP Records",
                "value": db_count(
                    "failed_smtp", "bot_type = %s", ("password_changer",)
                ),
            },
        ]
        render_stats_cards(cards)
    except Exception as e:
        st.error(f"Error loading Password Changer stats: {e}")

    st.divider()
    st.subheader("Password Changer Quick Insights")
    st.write(
        "🔐 Use these stats to monitor account supply, results, and failures for password changer runs."
    )


def stats_page():
    stats_area = st.empty()

    with st.spinner("Loading stats..."):
        with stats_area.container():
            st.header("Bot Stats")

            selected_tab = st.radio(
                "Select stats tab",
                [
                    "Hotmail Bot",
                    "Family Bot",
                    "Email Sender",
                    "Password Changer",
                ],
                index=0,
                horizontal=True,
                key="stats_page_selected_tab",
            )

            if selected_tab == "Hotmail Bot":
                render_hotmail_stats()
            elif selected_tab == "Family Bot":
                render_familybot_stats()
            elif selected_tab == "Email Sender":
                render_email_sender_stats()
            elif selected_tab == "Password Changer":
                render_password_changer_stats()


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
    st.header("Database Management")

    # Connection status
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Test Connection", width="stretch"):
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

    with tab3:
        st.subheader("Backup Database")
        st.info(
            "Creates a timestamped backup in `database/backup_YYYY-MM-DD_HH-MM-SS/backup.sql`."
        )

        tables = get_db_tables()
        selected_tables = []

        if tables:
            st.write(
                "Select the tables to include in the backup. All tables are selected by default."
            )
            for table in tables:
                if st.checkbox(table, value=True, key=f"backup_table_{table}"):
                    selected_tables.append(table)

            if not selected_tables:
                st.warning("Select one or more tables before creating a backup.")
        else:
            st.warning("Unable to load tables. Check database connection settings.")

        if st.button("💾 Create Backup", width="stretch"):
            if not selected_tables:
                st.error("Please select at least one table to back up.")
            else:
                with st.spinner("Backing up selected tables..."):
                    success, message = backup_database(selected_tables=selected_tables)
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
    # st.header("Bot Settings Manager")
    # st.markdown("View and manage all bot configuration settings.")

    # Load settings
    settings = load_full_settings()
    if not settings:
        st.error("Could not load settings.json")
        return

    # Category buttons using columns for horizontal layout
    st.subheader("Select Configuration Category")

    categories = {
        "app": "General App Settings",
        "email_sender": "Email Sender",
        "familybot": "Family Bot",
        "hotmailbot": "Hotmail Bot",
        "password_changer": "Password Changer",
    }

    # Initialize session state for category selection
    if "selected_category" not in st.session_state:
        st.session_state.selected_category = "app"

    # Create button columns
    cols = st.columns(len(categories))
    for idx, (cat_key, cat_label) in enumerate(categories.items()):
        with cols[idx]:
            if st.button(cat_label, width="stretch", key=f"btn_{cat_key}"):
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
            submitted = st.form_submit_button("💾 Save Changes", width="stretch")
        with col2:
            reset = st.form_submit_button("↻ Reset", width="stretch")

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
    st.markdown("### Information")

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
    st.set_page_config(page_title="FamilyBot Upload", layout="wide")
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
            .stMarkdown h4,
            .stMarkdown h5,
            .stMarkdown h6,
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

    st.sidebar.markdown("### Pages")
    if st.sidebar.button("Bot Settings", width="stretch"):
        st.session_state.selected_page = "Bot Settings"
    if st.sidebar.button("General Upload", width="stretch"):
        st.session_state.selected_page = "General Upload"
    if st.sidebar.button("Email Sender Upload", width="stretch"):
        st.session_state.selected_page = "Email Sender Upload"
    if st.sidebar.button("Stats", width="stretch"):
        st.session_state.selected_page = "Stats"
    if st.sidebar.button("Database Management", width="stretch"):
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
        # pass
        stats_page()
    elif st.session_state.selected_page == "Database Management":
        database_management()


if __name__ == "__main__":
    main()
