import os
from dotenv import load_dotenv

load_dotenv()

MANAGER_BOT_TOKEN = os.getenv("MANAGER_BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

DB_PATH = "bots.db"
BOTS_BASE_DIR = "/srv/telegram-bots"
