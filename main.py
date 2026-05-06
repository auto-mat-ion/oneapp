from bots.familybot import run_familybot
from bots.hotmailbot import run_hotmailbot
from bots.password_changer import run_password_changerbot

bot = int(
    input(
        "Select bot to run:\n1. Familybot\n2. Hotmailbot\n3. Password Changer\nEnter choice (1/2/3): "
    )
)

if bot == 1:
    run_familybot()
elif bot == 2:
    run_hotmailbot()
elif bot == 3:
    run_password_changerbot()
else:
    print("Invalid choice. Please select 1, 2, or 3.")
