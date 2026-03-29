import os
import asyncio

PROTECTED_USERS = {"book"}
TOKEN_RE = None  # импортируется в scan


def is_protected(name: str) -> bool:
    return name.lower() in PROTECTED_USERS


async def _run(*args, timeout: int = 30) -> tuple[int, str, str]:
    """Запускает команду асинхронно, возвращает (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 1, "", "timeout"
    return proc.returncode, stdout.decode(errors="ignore"), stderr.decode(errors="ignore")


async def file_exists(path: str) -> bool:
    code, _, _ = await _run("/usr/bin/sudo", "stat", path)
    return code == 0


async def read_file(path: str) -> str:
    _, stdout, _ = await _run("/usr/bin/sudo", "cat", path)
    return stdout


async def create_system_user(username: str) -> bool:
    if is_protected(username):
        return False
    code, _, stderr = await _run("/usr/bin/sudo", "useradd", "-r", "-m", "-s", "/bin/bash", username)
    return code == 0 or "already exists" in stderr


async def clone_github(repo_url: str, work_dir: str, branch: str = "main", username: str = "root") -> bool:
    await _run("/usr/bin/sudo", "mkdir", "-p", work_dir)
    await _run("/usr/bin/sudo", "chown", f"{username}:{username}", work_dir)
    code, _, _ = await _run("/usr/bin/sudo", "-u", username, "/usr/bin/git", "clone", "-b", branch, repo_url, work_dir)
    return code == 0


async def save_python_file(file_bytes: bytes, work_dir: str, filename: str = "bot.py", username: str = "root") -> bool:
    try:
        await _run("/usr/bin/sudo", "mkdir", "-p", work_dir)
        await _run("/usr/bin/sudo", "chown", f"{username}:{username}", work_dir)
        tmp = f"/tmp/{filename}"
        with open(tmp, "wb") as f:
            f.write(file_bytes)
        await _run("/usr/bin/sudo", "mv", tmp, os.path.join(work_dir, filename))
        await _run("/usr/bin/sudo", "chown", f"{username}:{username}", os.path.join(work_dir, filename))
        return True
    except Exception:
        return False


async def setup_venv(work_dir: str, username: str) -> bool:
    venv_path = os.path.join(work_dir, "venv")
    code, _, _ = await _run("/usr/bin/sudo", "-H", "-u", username, "/usr/bin/python3", "-m", "venv", venv_path, timeout=60)
    if code != 0:
        return False
    req_path = os.path.join(work_dir, "requirements.txt")
    req_exists = await file_exists(req_path)
    if req_exists:
        pip = os.path.join(venv_path, "bin", "pip")
        code, _, _ = await _run("/usr/bin/sudo", "-H", "-u", username, pip, "install", "-r", req_path, timeout=300)
        return code == 0
    return True


async def create_systemd_service(bot_id: str, username: str, work_dir: str, entrypoint: str = "bot.py") -> bool:
    venv_python = os.path.join(work_dir, "venv", "bin", "python3")
    script_path = os.path.join(work_dir, entrypoint)
    service_name = f"tgbot_{bot_id}.service"
    tmp_path = f"/tmp/{service_name}"
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
    try:
        with open(tmp_path, "w") as f:
            f.write(service_content)
    except Exception:
        return False

    code, _, _ = await _run("/usr/bin/sudo", "mv", tmp_path, f"/etc/systemd/system/{service_name}")
    if code != 0:
        return False
    await _run("/usr/bin/sudo", "/usr/bin/systemctl", "daemon-reload")
    return True


async def start_service_by_name(service_name: str) -> bool:
    await _run("/usr/bin/sudo", "/usr/bin/systemctl", "enable", service_name)
    code, _, _ = await _run("/usr/bin/sudo", "/usr/bin/systemctl", "start", service_name)
    return code == 0


async def stop_service_by_name(service_name: str) -> bool:
    code, _, _ = await _run("/usr/bin/sudo", "/usr/bin/systemctl", "stop", service_name)
    return code == 0


async def restart_service_by_name(service_name: str) -> bool:
    code, _, _ = await _run("/usr/bin/sudo", "/usr/bin/systemctl", "restart", service_name)
    return code == 0





async def get_service_status_by_name(service_name: str) -> str:
    _, stdout, _ = await _run("/usr/bin/systemctl", "is-active", service_name)
    return stdout.strip()


async def get_logs_by_name(service_name: str, lines: int = 50) -> str:
    _, stdout, _ = await _run("/usr/bin/sudo", "/usr/bin/journalctl", "-u", service_name, "-n", str(lines), "--no-pager")
    return stdout


async def delete_service_by_name(service_name: str, username: str, work_dir: str, source_type: str = "") -> bool:
    if is_protected(username):
        raise PermissionError(f"Пользователь {username} защищён от удаления")
    await stop_service_by_name(service_name)
    if source_type != "existing":
        await _run("/usr/bin/sudo", "/usr/bin/systemctl", "disable", service_name)
        await _run("/usr/bin/sudo", "rm", "-f", f"/etc/systemd/system/{service_name}")
        await _run("/usr/bin/sudo", "/usr/bin/systemctl", "daemon-reload")
        await _run("/usr/bin/sudo", "userdel", username)
        await _run("/usr/bin/sudo", "rm", "-rf", work_dir)
    return True


def scan_existing_bots() -> list[dict]:
    """
    Сканирует /etc/systemd/system/ — читается без sudo.
    Ищет сервисы {name}.service где User={name} и путь /home/{name}/{name}/{name}.py
    """
    found = []
    svc_dir = "/etc/systemd/system"

    try:
        entries = os.listdir(svc_dir)
    except Exception:
        return found

    for filename in entries:
        if not filename.endswith(".service"):
            continue
        # Пропускаем служебные сервисы менеджера
        if filename.startswith("tgbot_") or filename == "bot-manager.service":
            continue

        name = filename[:-len(".service")]

        if is_protected(name):
            continue

        svc_path = os.path.join(svc_dir, filename)
        try:
            with open(svc_path, "r", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue

        # Проверяем что User={name}
        if f"User={name}" not in content:
            continue

        # Проверяем что путь соответствует паттерну (с или без ведущего слеша)
        py_path = f"/home/{name}/{name}/{name}.py"
        py_path_rel = f"home/{name}/{name}/{name}.py"
        if py_path not in content and py_path_rel not in content:
            continue

        # Читаем токен из py файла (без sudo — попробуем напрямую)
        token = None
        try:
            with open(py_path, "r", errors="ignore") as f:
                token = _extract_token(f.read())
        except Exception:
            pass

        found.append({
            "name": name,
            "work_dir": f"/home/{name}/{name}",
            "entrypoint": f"{name}.py",
            "system_user": name,
            "service_name": filename,
            "token": token,
        })

    return found


def _extract_token(content: str):
    import re
    # Ищем токен в кавычках или без (BOT_TOKEN=... или "token")
    match = re.search(r'["\']?(\d{8,12}:[A-Za-z0-9_-]{35,})["\']?', content)
    return match.group(1) if match else None


# Обратная совместимость
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
