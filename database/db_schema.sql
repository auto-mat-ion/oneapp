-- Create Family database tables for MySQL
DROP DATABASE IF EXISTS oneapp;

CREATE DATABASE IF NOT EXISTS oneapp CHARACTER
SET
  utf8mb4 COLLATE utf8mb4_unicode_ci;

USE oneapp;

-- FamilyBot Tables
CREATE TABLE
  IF NOT EXISTS familybot_card_details (
    card_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    card_number BIGINT NULL,
    expiry_month_year VARCHAR(16) NULL,
    cvv VARCHAR(32) NULL,
    name_on_card VARCHAR(200) NULL,
    country VARCHAR(255) NULL,
    address_line1 VARCHAR(100) NULL,
    city VARCHAR(100) NULL,
    postal_code VARCHAR(100) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS familybot_fully_used_cards (
    card_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    card_number BIGINT NULL,
    expiry_month_year VARCHAR(16) NULL,
    cvv VARCHAR(32) NULL,
    name_on_card VARCHAR(200) NULL,
    country VARCHAR(255) NULL,
    address_line1 VARCHAR(100) NULL,
    city VARCHAR(100) NULL,
    postal_code VARCHAR(100) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS processing_card_details (
    card_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    name_on_card VARCHAR(200) NULL,
    card_number BIGINT NULL,
    expiry_month_year VARCHAR(16) NULL,
    cvv VARCHAR(32) NULL,
    country VARCHAR(255) NULL,
    address_line1 VARCHAR(100) NULL,
    city VARCHAR(100) NULL,
    postal_code VARCHAR(100) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS input_emails (
    email_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NULL,
    pass VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS processing_emails (
    email_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    email VARCHAR(255) NULL,
    pass VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS familybot_first_names (
    name_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    firstnames VARCHAR(100) NULL,
    country VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS familybot_surnames (
    name_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    surnames VARCHAR(100) NULL,
    country VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS processed_emails (
    email_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    email VARCHAR(255) NULL,
    pass VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS familybot_fake_details (
    detail_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    country VARCHAR(255) NULL,
    address_line1 VARCHAR(255) NULL,
    city VARCHAR(255) NULL,
    state VARCHAR(255) NULL,
    postal_code VARCHAR(20) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS familybot_extracted_family_links (
    link_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    email VARCHAR(255) NULL,
    pass VARCHAR(255) NULL,
    recovery VARCHAR(255) NULL,
    link TEXT NULL,
    country VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS familybot_failed_cards (
    card_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    card_number BIGINT NULL,
    expiry_month_year VARCHAR(16) NULL,
    cvv VARCHAR(32) NULL,
    country VARCHAR(255) NULL,
    reason_for_fail TEXT NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS familybot_card_usage_log (
    card_usage_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    use_datetime DATETIME NULL,
    card_num BIGINT NULL,
    `exp_month/year` VARCHAR(32) NULL,
    cvv VARCHAR(32) NULL,
    country VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS signin_log (
    log_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    email_acc VARCHAR(255) NULL,
    log_time DATETIME NULL,
    status VARCHAR(255) NULL,
    error TEXT NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS accounts_details (
    account_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    email_acc VARCHAR(255) NULL,
    password VARCHAR(255) NULL,
    profile_dir VARCHAR(255) NULL,
    proxy_used VARCHAR(255) NULL,
    country VARCHAR(100) NULL,
    has_recovery_email VARCHAR(10) NULL,
    recovery_email VARCHAR(255) NULL,
    has_recovery_phone VARCHAR(10) NULL,
    recovery_phone_number VARCHAR(50) NULL,
    joined_microsoft_premium VARCHAR(10) NULL,
    join_time_microsoft_premium DATETIME NULL,
    has_bitly_account VARCHAR(10) NULL,
    bitly_acc_password VARCHAR(255) NULL,
    save_smtp VARCHAR(10) NULL
  ) ENGINE = InnoDB;

-- HOTMAIL Tables
-- emails_input uses input_emails
-- processed_emails uses processed_emails
-- signin_log uses signin_log
-- accounts uses accounts_details
CREATE TABLE
  IF NOT EXISTS cache_bins (
    cache_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    cache_bin_file LONGBLOB NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS family_link (
    link_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    link TEXT NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS expired_family_links (
    link_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    link TEXT NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS subdomains (
    subdomain_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    subdomain VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS processing_family_links (
    link_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    link TEXT NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS used_5_times_family_links (
    link_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    link TEXT NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS link_stats (
    link_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    link TEXT NULL,
    times_used INT NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS failed_smtp (
    email_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    email_address VARCHAR(145) NULL,
    password VARCHAR(145) NULL,
    temp_email VARCHAR(145) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS shortened_urls (
    link_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    link TEXT NULL,
    shortened INT NULL
  ) ENGINE = InnoDB;

-- SMTP Tables
-- cache.bin uses cache_bins
CREATE TABLE
  IF NOT EXISTS processing_smtp_emails (
    email_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    email VARCHAR(255) NULL,
    pass VARCHAR(255) NULL,
    recovery VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS sender_emails_setup_logs (
    log_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    email_acc VARCHAR(255) NULL,
    log_time DATETIME NULL,
    status VARCHAR(255) NULL,
    error TEXT NULL
  ) ENGINE = InnoDB;

-- change passwords
CREATE TABLE
  IF NOT EXISTS password_changer_accounts (
    acc_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NULL,
    pass VARCHAR(255) NULL,
    recovery VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS processing_password_changes (
    change_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    server_ip VARCHAR(45) NULL,
    bot_type VARCHAR(50) NULL,
    date_time DATETIME NULL,
    email VARCHAR(255) NULL,
    pass VARCHAR(255) NULL,
    recovery VARCHAR(255) NULL
  ) ENGINE = InnoDB;

-- EMAIL SENDER
CREATE TABLE
  IF NOT EXISTS sender_input_accounts (
    acc_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NULL,
    pass VARCHAR(255) NULL,
    recovery VARCHAR(255) NULL,
    country VARCHAR(255) NULL,
    last_used DATETIME NULL,
    times_used INT NULL,
    server_ip VARCHAR(255) NULL,
    batch VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS sender_processed_accounts (
    acc_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NULL,
    pass VARCHAR(255) NULL,
    recovery VARCHAR(255) NULL,
    date_time DATETIME NULL,
    country VARCHAR(255) NULL,
    server_ip VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS sender_failed_accounts (
    acc_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NULL,
    pass VARCHAR(255) NULL,
    recovery VARCHAR(255) NULL,
    country VARCHAR(255) NULL,
    server_ip VARCHAR(255) NULL,
    fail_reason TEXT NULL,
    date_time DATETIME NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS sender_hyperlink_text (
    text_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    hyperlink_text TEXT NULL,
    country VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS sender_link (
    link_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    link VARCHAR(255) NULL,
    country VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS sender_recipients (
    recipient_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    recipient_email VARCHAR(255) NULL,
    country VARCHAR(255) NULL,
    server_ip VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS sender_subjects (
    subject_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    subject VARCHAR(255) NULL,
    country VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS sender_texts (
    text_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    text TEXT NULL,
    country VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS sender_log (
    log_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    log_text TEXT NULL,
    country VARCHAR(255) NULL,
    server_ip VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS sender_sent_recipients (
    recipient_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    recipient_email VARCHAR(255) NULL,
    date_time DATETIME NULL,
    country VARCHAR(255) NULL,
    server_ip VARCHAR(255) NULL
  ) ENGINE = InnoDB;

CREATE TABLE
  IF NOT EXISTS sender_invalid_recipients (
    email_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    recipient_email VARCHAR(255) NULL,
    reason DATETIME NULL,
    country VARCHAR(255) NULL,
    server_ip VARCHAR(255) NULL
  ) ENGINE = InnoDB;