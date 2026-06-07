from bots.familybot import run_familybot, run_familybot_share
from bots.hotmailbot import run_hotmailbot
from bots.password_changer import run_password_changerbot
from bots.email_sender import main
from bots.email_sender_2 import main2
from bots.new_app_hotmail import run_second_app_hotmails
import json

if (
    json.loads(open("bots/settings.json", "r").read()).get("app").get("SERVER_IP")
    == "test_ip"
):
    print(
        "Please set the SERVER_IP in bots/settings.json before running the application."
    )
    exit(1)


bot = int(
    input(
        "Oneapp v1.33\nSelect bot to run:\n1. Familybot\n2. Hotmailbot\n3. Password Changer\n4. Email Sender\n5. Familybot Share\n6. New app Hotmailbot \nEnter choice (1/2/3/4/5/6): "
    )
)

if bot == 1:
    run_familybot()
elif bot == 2:
    run_hotmailbot()
elif bot == 3:
    run_password_changerbot()
elif bot == 4:
    main()
elif bot == 5:
    run_familybot_share()
elif bot == 6:
    run_second_app_hotmails()
else:
    print("Invalid choice. Please select 1, 2, 3, 4, or 5.")
