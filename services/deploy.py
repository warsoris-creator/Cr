import os
import re
import subprocess

BOTS_BASE_DIR = "/srv/telegram-bots"
PROTECTED_USERS = {"booK"}

# Паттерн Telegram токена
TOKEN_RE = re.compile(r'["\'](\d{8,12}:[A-Za-z0-9_-]{35,})["\']')


def is_protected(name: str) -> bool:
    return name.lower() in PROTECTED_USERS


def extract_token_from_file(filepath: str) -> str | None:
    """Ищет Telegram-токен в .py файле по regex."""
    try:
        result = subprocess.run(
            ["sudo", "cat", filepath], capture_output=True, text=True, timeout=10
        )
        match = TOKEN_RE.search(result.stdout)
        return match.group(1) if match else None
    except Exception:
        return None


def scan_existing_bots() -> list[dict]:
    """
    Сканирует /home/ по паттерну /home/{name}/{name}/{name}.py
    Пропускает защищённых пользователей.
    Возвращает список найденных ботов.
    """
    found = []
    try:
        result = subprocess.run(
            ["sudo", "ls", "/home"], capture_output=True, text=True, timeout=10
        )
        users = result.stdout.split()
    except Exception:
        return found

    for name in users:
        if is_protected(name):
            continue

        py_path = f"/home/{name}/{name}/{name}.py"
        service_name = f"{name}.service"
        service_path = f"/etc/systemd/system/{service_name}"

        # Проверяем что файл и сервис существуют
        py_exists = subprocess.run(
            ["sudo", "test", "-f", py_path], capture_output=True
        ).returncode == 0
        svc_exists = subprocess.run(
            ["sudo", "test", "-f", service_path], capture_output=True
        ).returncode == 0

        if not py_exists or not svc_exists:
            continue

        token = extract_token_from_file(py_path)

        found.append({
            "name": name,
            "work_dir": f"/home/{name}/{name}",
            "entrypoint": f"{name}.py",
            "system_user": name,
            "service_name": service_name,
            "token": token,
        })

    return found

async def create_system_user(username):
    try:
        subprocess.run(["sudo", "useradd", "-r", "-s", "/bin/false", username], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        if b"already exists" in e.stderr:
            return True
        return False

async def clone_github(repo_url, work_dir, branch="main"):
    try:
        os.makedirs(work_dir, exist_ok=True)
        subprocess.run(["sudo", "git", "clone", "-b", branch, repo_url, work_dir],
                      check=True, capture_output=True, timeout=120)
        return True
    except Exception:
        return False

async def save_python_file(file_bytes, work_dir, filename="bot.py"):
    try:
        os.makedirs(work_dir, exist_ok=True)
        file_path = os.path.join(work_dir, filename)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        return True
    except Exception:
        return False

async def setup_venv(work_dir):
    try:
        venv_path = os.path.join(work_dir, "venv")
        subprocess.run(["sudo", "python3", "-m", "venv", venv_path],
                      check=True, capture_output=True, timeout=120)

        req_path = os.path.join(work_dir, "requirements.txt")
        if os.path.exists(req_path):
            pip_path = os.path.join(venv_path, "bin", "pip")
            subprocess.run(["sudo", pip_path, "install", "-r", req_path],
                          check=True, capture_output=True, timeout=300)
        return True
    except Exception:
        return False

async def create_systemd_service(bot_id, username, work_dir, entrypoint="bot.py"):
    venv_python = os.path.join(work_dir, "venv", "bin", "python3")
    script_path = os.path.join(work_dir, entrypoint)

    service_content = f"""[Unit]
Description=Telegram Bot {bot_id}
After=network.target

[Service]
Type=simple
User={username}
WorkingDirectory={work_dir}
ExecStart={venv_python} {script_path}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    service_path = f"/etc/systemd/system/tgbot_{bot_id}.service"

    try:
        with open(f"/tmp/tgbot_{bot_id}.service", "w") as f:
            f.write(service_content)
        subprocess.run(["sudo", "mv", f"/tmp/tgbot_{bot_id}.service", service_path],
                      check=True, capture_output=True)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True, capture_output=True)
        return True
    except Exception:
        return False

async def start_service_by_name(service_name: str) -> bool:
    try:
        subprocess.run(["sudo", "systemctl", "enable", service_name], check=True, capture_output=True)
        subprocess.run(["sudo", "systemctl", "start", service_name], check=True, capture_output=True)
        return True
    except Exception:
        return False

async def stop_service_by_name(service_name: str) -> bool:
    try:
        subprocess.run(["sudo", "systemctl", "stop", service_name], check=True, capture_output=True)
        return True
    except Exception:
        return False

async def restart_service_by_name(service_name: str) -> bool:
    try:
        subprocess.run(["sudo", "systemctl", "restart", service_name], check=True, capture_output=True)
        return True
    except Exception:
        return False

async def get_service_status_by_name(service_name: str) -> str:
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "is-active", service_name],
            capture_output=True, text=True
        )
        return result.stdout.strip()
    except Exception:
        return "inactive"

async def get_logs_by_name(service_name: str, lines: int = 50) -> str:
    try:
        result = subprocess.run(
            ["sudo", "journalctl", "-u", service_name, "-n", str(lines), "--no-pager"],
            capture_output=True, text=True
        )
        return result.stdout
    except Exception as e:
        return f"Error getting logs: {e}"

async def delete_service_by_name(service_name: str, username: str, work_dir: str, source_type: str = "") -> bool:
    """
    Удаляет сервис.
    Для source_type='existing' — не удаляет файлы и пользователя (бот был до менеджера).
    """
    if is_protected(username):
        raise PermissionError(f"Пользователь {username} защищён от удаления")
    try:
        await stop_service_by_name(service_name)
        if source_type != "existing":
            subprocess.run(["sudo", "systemctl", "disable", service_name], capture_output=True)
            subprocess.run(["sudo", "rm", "-f", f"/etc/systemd/system/{service_name}"], capture_output=True)
            subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True)
            subprocess.run(["sudo", "userdel", username], capture_output=True)
            subprocess.run(["sudo", "rm", "-rf", work_dir], capture_output=True)
        return True
    except PermissionError:
        raise
    except Exception:
        return False

# Обратная совместимость для handlers/add_bot.py
async def start_service(bot_id: str) -> bool:
    return await start_service_by_name(f"tgbot_{bot_id}.service")

async def stop_service(bot_id: str) -> bool:
    return await stop_service_by_name(f"tgbot_{bot_id}.service")

async def restart_service(bot_id: str) -> bool:
    return await restart_service_by_name(f"tgbot_{bot_id}.service")

async def get_service_status(bot_id: str) -> str:
    return await get_service_status_by_name(f"tgbot_{bot_id}.service")

async def get_logs(bot_id: str, lines: int = 50) -> str:
    return await get_logs_by_name(f"tgbot_{bot_id}.service", lines)

async def delete_service(bot_id: str, username: str, work_dir: str) -> bool:
    return await delete_service_by_name(f"tgbot_{bot_id}.service", username, work_dir, source_type="deployed")
