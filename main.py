from bots.email_sender_batch_by_batch_all_servers import main_batches
from bots.familybot import run_familybot, run_familybot_share
from bots.hotmailbot import run_hotmailbot
from bots.password_changer import run_password_changerbot


# from bots.email_sender_test import main_sec
from bots.new_app_hotmail import run_second_app_hotmails
from bots.manual_sender import save_cookies, runner
import json
from utils.server_ip_helper import get_server_ip

if get_server_ip() == "test_ip":
    print(
        "Please set the SERVER_IP in utils/server_ip file before running the application."
    )
    exit(1)


bot = int(
    input(
        f"Oneapp v1.82\n\nSERVER IP: {get_server_ip()}\n\nSelect bot to run:\n1. Familybot\n2. Hotmailbot\n3. Password Changer\n4. Email Sender\n5. Familybot Share\n6. New app Hotmailbot \n7. Save manual sender cookies\n8. Run manual bot\nEnter choice (1/2/3/4/5/6): ".format()
    )
)

if bot == 1:
    run_familybot()
elif bot == 2:
    run_hotmailbot()
elif bot == 3:
    run_password_changerbot()
elif bot == 4:
    main_batches()
elif bot == 5:
    run_familybot_share()
elif bot == 6:
    run_second_app_hotmails()
elif bot == 7:
    save_cookies()
elif bot == 8:
    runner()
else:
    print("Invalid choice. Please select 1, 2, 3, 4, or 5.")
