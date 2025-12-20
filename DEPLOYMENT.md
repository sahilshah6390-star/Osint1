# VPS Deployment Guide

Complete guide to deploy DataTrace OSINT Bot on your VPS.

## Prerequisites

- VPS with Ubuntu 20.04+ / Debian 10+
- Python 3.11 or higher
- SSH access to your VPS
- Domain (optional)

## Step 1: Prepare VPS

### Update system
```bash
sudo apt update && sudo apt upgrade -y
```

### Install Python 3.11
```bash
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip -y
```

### Verify installation
```bash
python3.11 --version
```

## Step 2: Upload Bot Files

### Clone from GitHub (if you pushed there)
```bash
cd /home/youruser
git clone https://github.com/yourusername/osint-bot.git
cd osint-bot
```

### OR Upload files via SCP
```bash
# From your local machine
scp -r /path/to/bot/* user@your-vps-ip:/home/youruser/osint-bot/
```

## Step 3: Configure Bot

### Create .env file
```bash
cd /home/youruser/osint-bot
cp .env.example .env
nano .env
```

Add your bot token:
```
BOT_TOKEN=your_bot_token_from_botfather
```

Save with `Ctrl+X`, `Y`, `Enter`

## Step 4: Install Dependencies

### Create virtual environment
```bash
python3.11 -m venv venv
source venv/bin/activate
```

### Install packages
```bash
pip install python-telegram-bot[all] aiohttp requests python-dotenv
```

## Step 5: Test Bot

```bash
python bot.py
```

If you see "Bot started!" and no errors, press `Ctrl+C` to stop.

## Step 6: Run Bot Permanently

### Method 1: Using systemd (Recommended)

Create service file:
```bash
sudo nano /etc/systemd/system/osint-bot.service
```

Add this content (update paths):
```ini
[Unit]
Description=DataTrace OSINT Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/osint-bot
Environment="PATH=/home/youruser/osint-bot/venv/bin"
ExecStart=/home/youruser/osint-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable osint-bot
sudo systemctl start osint-bot
```

Check status:
```bash
sudo systemctl status osint-bot
```

View logs:
```bash
sudo journalctl -u osint-bot -f
```

Stop bot:
```bash
sudo systemctl stop osint-bot
```

### Method 2: Using Screen

```bash
screen -S osint_bot
cd /home/youruser/osint-bot
source venv/bin/activate
python bot.py
```

Detach: `Ctrl+A` then `D`

Reattach:
```bash
screen -r osint_bot
```

### Method 3: Using PM2

Install PM2:
```bash
npm install -g pm2
```

Start bot:
```bash
cd /home/youruser/osint-bot
pm2 start bot.py --name osint-bot --interpreter venv/bin/python
pm2 save
pm2 startup
```

Manage:
```bash
pm2 status
pm2 logs osint-bot
pm2 restart osint-bot
pm2 stop osint-bot
```

## Step 7: Setup Firewall (Optional)

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw enable
```

## Monitoring & Maintenance

### View logs (systemd)
```bash
sudo journalctl -u osint-bot -f --lines=100
```

### Check bot status
```bash
sudo systemctl status osint-bot
```

### Restart bot
```bash
sudo systemctl restart osint-bot
```

### Update bot
```bash
cd /home/youruser/osint-bot
git pull  # if using git
sudo systemctl restart osint-bot
```

### Backup database
```bash
cp osint_bot.db osint_bot_backup_$(date +%Y%m%d).db
```

## Troubleshooting

### Bot not starting
```bash
# Check logs
sudo journalctl -u osint-bot -n 50

# Test manually
cd /home/youruser/osint-bot
source venv/bin/activate
python bot.py
```

### Permission errors
```bash
sudo chown -R youruser:youruser /home/youruser/osint-bot
chmod +x bot.py
```

### Database locked
```bash
# Stop bot first
sudo systemctl stop osint-bot

# Remove lock
rm -f osint_bot.db-journal

# Start bot
sudo systemctl start osint-bot
```

### Memory issues
Add swap if needed:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## Security Tips

1. **Never expose tokens**
   - Keep `.env` secure
   - Never commit secrets to Git

2. **Use SSH keys**
   ```bash
   ssh-keygen -t rsa -b 4096
   ssh-copy-id user@vps-ip
   ```

3. **Disable root login**
   ```bash
   sudo nano /etc/ssh/sshd_config
   # Set: PermitRootLogin no
   sudo systemctl restart sshd
   ```

4. **Regular updates**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

5. **Backup regularly**
   ```bash
   # Daily backup cron
   0 2 * * * cp /home/youruser/osint-bot/osint_bot.db /home/youruser/backups/osint_bot_$(date +\%Y\%m\%d).db
   ```

## Performance Optimization

### For high traffic (1000+ users):

1. **Use PostgreSQL instead of SQLite**
2. **Enable caching**
3. **Use reverse proxy (nginx)**
4. **Upgrade VPS resources**

## Support

- Issues: GitHub Issues
- Support: @DataTraceSupport
- Group: @DataTraceOSINTSupport
