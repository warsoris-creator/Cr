import aiosqlite
import uuid
from datetime import datetime
from config import DB_PATH

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bots (
                id TEXT PRIMARY KEY,
                telegram_bot_id INTEGER,
                telegram_bot_username TEXT,
                token TEXT,
                source_type TEXT,
                source_value TEXT,
                entrypoint TEXT DEFAULT 'bot.py',
                branch TEXT DEFAULT 'main',
                system_user TEXT,
                work_dir TEXT,
                systemd_unit TEXT,
                status TEXT DEFAULT 'stopped',
                pid INTEGER,
                last_error TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        await db.commit()

async def add_bot(telegram_bot_id, telegram_bot_username, token, source_type, source_value, entrypoint='bot.py', branch='main'):
    bot_id = str(uuid.uuid4())[:8]
    system_user = f"tgbot_{bot_id}"
    work_dir = f"/srv/telegram-bots/{bot_id}"
    systemd_unit = f"tgbot_{bot_id}.service"
    now = datetime.now().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO bots (id, telegram_bot_id, telegram_bot_username, token, source_type, source_value,
                            entrypoint, branch, system_user, work_dir, systemd_unit, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'deploying', ?, ?)
        """, (bot_id, telegram_bot_id, telegram_bot_username, token, source_type, source_value,
              entrypoint, branch, system_user, work_dir, systemd_unit, now, now))
        await db.commit()
    return bot_id

async def get_all_bots():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM bots ORDER BY created_at DESC")
        return await cursor.fetchall()

async def get_bot(bot_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))
        return await cursor.fetchone()

async def update_bot_status(bot_id, status, pid=None, last_error=None):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        if pid is not None:
            await db.execute("UPDATE bots SET status = ?, pid = ?, last_error = ?, updated_at = ? WHERE id = ?",
                           (status, pid, last_error, now, bot_id))
        else:
            await db.execute("UPDATE bots SET status = ?, last_error = ?, updated_at = ? WHERE id = ?",
                           (status, last_error, now, bot_id))
        await db.commit()

async def add_existing_bot(name, telegram_bot_id, telegram_bot_username, token,
                           system_user, work_dir, entrypoint, service_name):
    """Импортирует уже существующий бот без деплоя."""
    bot_id = name  # используем имя как ID для удобства
    now = datetime.now().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO bots
              (id, telegram_bot_id, telegram_bot_username, token, source_type, source_value,
               entrypoint, branch, system_user, work_dir, systemd_unit, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'existing', '', ?, 'main', ?, ?, ?, 'stopped', ?, ?)
        """, (bot_id, telegram_bot_id, telegram_bot_username, token,
              entrypoint, system_user, work_dir, service_name, now, now))
        await db.commit()
    return bot_id


async def delete_bot(bot_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
        await db.commit()
