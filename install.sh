#!/bin/bash
set -e

echo "🚀 Установка Bot Manager на Ubuntu..."

# Python и зависимости
echo "📦 Установка Python..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git curl

# Пользователь для менеджера
echo "👤 Создание пользователя botmanager..."
sudo useradd -m -s /bin/bash botmanager 2>/dev/null || true

# Папка для ботов
echo "📁 Создание папки для ботов..."
sudo mkdir -p /srv/telegram-bots
sudo chown botmanager:botmanager /srv/telegram-bots

# Права sudo
echo "🔐 Настройка sudo прав..."
echo "botmanager ALL=(ALL) NOPASSWD: /bin/systemctl, /usr/bin/journalctl, /usr/sbin/useradd, /usr/sbin/userdel, /usr/bin/git, /bin/mv, /bin/rm, /usr/bin/python3" | sudo tee /etc/sudoers.d/botmanager
sudo chmod 440 /etc/sudoers.d/botmanager

# Установка менеджера
echo "📥 Установка Bot Manager..."
sudo mkdir -p /opt/bot-manager
sudo cp -r . /opt/bot-manager/
sudo chown -R botmanager:botmanager /opt/bot-manager

# venv и зависимости
echo "🔧 Создание venv..."
sudo -u botmanager python3 -m venv /opt/bot-manager/venv
sudo -u botmanager /opt/bot-manager/venv/bin/pip install -r /opt/bot-manager/requirements.txt

# .env файл
echo "⚙️ Создание .env файла..."
if [ ! -f /opt/bot-manager/.env ]; then
    sudo cp /opt/bot-manager/.env.example /opt/bot-manager/.env
    sudo chown botmanager:botmanager /opt/bot-manager/.env
    echo "❗ Отредактируйте /opt/bot-manager/.env и укажите MANAGER_BOT_TOKEN и ADMIN_IDS"
fi

# systemd сервис
echo "⚙️ Установка systemd сервиса..."
sudo cp /opt/bot-manager/bot-manager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bot-manager.service

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "1. Отредактируйте /opt/bot-manager/.env"
echo "   sudo nano /opt/bot-manager/.env"
echo "2. Запустите: sudo systemctl start bot-manager"
echo "3. Проверьте: sudo systemctl status bot-manager"
echo ""
