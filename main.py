from bots.smtp import run_smtp_bot
from bots.familybot import run_family_link_extractor, run_familybot, run_familybot_share
from bots.hotmailbot import run_hotmailbot
from bots.password_changer import run_password_changerbot


# from bots.email_sender_test import main_sec
from bots.new_app_hotmail import run_second_app_hotmails
from bots.manual_sender import save_cookies, runner
import json
from utils.server_ip_helper import get_server_ip
from bots.fakey_scrapper import scraper


if get_server_ip() == "test_ip":
    print(
        "Please set the SERVER_IP in utils/server_ip file before running the application."
    )
    exit(1)


bot = int(
    input(
        f"Oneapp v2.1\n\nSERVER IP: {get_server_ip()}\n\nSelect bot to run:\n1. Familybot\n2. Hotmailbot\n3. Family link extractor\n4. Email Sender\n5. Familybot Share\n6. New app Hotmailbot \n7. Save manual sender cookies\n8. Fakey scraperr\nEnter choice (1/2/3/4/5/6): ".format()
    )
)

if bot == 1:
    run_familybot()
elif bot == 2:
    run_hotmailbot()
elif bot == 3:
    run_family_link_extractor()
elif bot == 4:
    run_smtp_bot()
elif bot == 5:
    run_familybot_share()
elif bot == 6:
    run_second_app_hotmails()
elif bot == 7:
    save_cookies()
elif bot == 8:
    scraper()
else:
    print("Invalid choice. Please select 1, 2, 3, 4, or 5.")
