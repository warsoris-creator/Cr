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
    code, _, _ = await _run("sudo", "stat", path)
    return code == 0


async def read_file(path: str) -> str:
    _, stdout, _ = await _run("sudo", "cat", path)
    return stdout


async def create_system_user(username: str) -> bool:
    if is_protected(username):
        return False
    code, _, stderr = await _run("sudo", "useradd", "-r", "-s", "/bin/false", username)
    return code == 0 or "already exists" in stderr


async def clone_github(repo_url: str, work_dir: str, branch: str = "main") -> bool:
    os.makedirs(work_dir, exist_ok=True)
    code, _, _ = await _run("sudo", "git", "clone", "-b", branch, repo_url, work_dir)
    return code == 0


async def save_python_file(file_bytes: bytes, work_dir: str, filename: str = "bot.py") -> bool:
    try:
        os.makedirs(work_dir, exist_ok=True)
        with open(os.path.join(work_dir, filename), "wb") as f:
            f.write(file_bytes)
        return True
    except Exception:
        return False


async def setup_venv(work_dir: str) -> bool:
    venv_path = os.path.join(work_dir, "venv")
    code, _, _ = await _run("sudo", "python3", "-m", "venv", venv_path)
    if code != 0:
        return False
    req_path = os.path.join(work_dir, "requirements.txt")
    if os.path.exists(req_path):
        pip = os.path.join(venv_path, "bin", "pip")
        code, _, _ = await _run("sudo", pip, "install", "-r", req_path)
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

    code, _, _ = await _run("sudo", "mv", tmp_path, f"/etc/systemd/system/{service_name}")
    if code != 0:
        return False
    await _run("sudo", "systemctl", "daemon-reload")
    return True


async def start_service_by_name(service_name: str) -> bool:
    await _run("sudo", "systemctl", "enable", service_name)
    code, _, _ = await _run("sudo", "systemctl", "start", service_name)
    return code == 0


async def stop_service_by_name(service_name: str) -> bool:
    code, _, _ = await _run("sudo", "systemctl", "stop", service_name)
    return code == 0


async def restart_service_by_name(service_name: str) -> bool:
    code, _, _ = await _run("sudo", "systemctl", "restart", service_name)
    return code == 0


async def get_service_status_by_name(service_name: str) -> str:
    _, stdout, _ = await _run("sudo", "systemctl", "is-active", service_name)
    return stdout.strip()


async def get_logs_by_name(service_name: str, lines: int = 50) -> str:
    _, stdout, _ = await _run("sudo", "journalctl", "-u", service_name, "-n", str(lines), "--no-pager")
    return stdout


async def delete_service_by_name(service_name: str, username: str, work_dir: str, source_type: str = "") -> bool:
    if is_protected(username):
        raise PermissionError(f"Пользователь {username} защищён от удаления")
    await stop_service_by_name(service_name)
    if source_type != "existing":
        await _run("sudo", "systemctl", "disable", service_name)
        await _run("sudo", "rm", "-f", f"/etc/systemd/system/{service_name}")
        await _run("sudo", "systemctl", "daemon-reload")
        await _run("sudo", "userdel", username)
        await _run("sudo", "rm", "-rf", work_dir)
    return True


async def scan_existing_bots() -> list[dict]:
    """Сканирует /home/ по паттерну /home/{name}/{name}/{name}.py"""
    found = []
    try:
        users = os.listdir("/home")
    except Exception:
        return found

    for name in users:
        if is_protected(name):
            continue

        py_path = f"/home/{name}/{name}/{name}.py"
        svc_path = f"/etc/systemd/system/{name}.service"

        py_ok = await file_exists(py_path)
        svc_ok = await file_exists(svc_path)

        if not py_ok or not svc_ok:
            continue

        content = await read_file(py_path)
        token = _extract_token(content)

        found.append({
            "name": name,
            "work_dir": f"/home/{name}/{name}",
            "entrypoint": f"{name}.py",
            "system_user": name,
            "service_name": f"{name}.service",
            "token": token,
        })

    return found


def _extract_token(content: str):
    import re
    match = re.search(r'["\'](\d{8,12}:[A-Za-z0-9_-]{35,})["\']', content)
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
