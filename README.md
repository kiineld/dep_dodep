# 🤖 VPN Telegram Bot (Remnawave Integration)

A full-featured Telegram bot for selling VPN subscriptions via [Remnawave](https://docs.rw) API.

## 📸 Screenshots

The bot UI matches the provided design screenshots:
- **Main menu** — profile info, balance, action buttons
- **Buy flow** — VPN category → devices → period → payment
- **Balance top-up** — quick amounts or manual entry
- **Promo codes** — apply codes for balance/days bonuses
- **Admin panel** — via `/admin` command (ADMIN_IDS only)

---

## 🚀 Quick Start

### 1. Clone & configure

```bash
git clone <this-repo>
cd vpn-bot
cp .env.example .env
nano .env  # Fill in your tokens
```

### 2. Required .env values

```env
BOT_TOKEN=your_bot_token_from_BotFather
ADMIN_IDS=your_telegram_id

REMNAWAVE_API_URL=https://your-remnawave-panel.com
REMNAWAVE_API_KEY=your_api_key
```

### 3. Run with Docker (recommended)

```bash
mkdir -p data
docker compose up -d
docker compose logs -f bot
```

### 4. Run locally (dev)

```bash
pip install -r requirements.txt
python main.py
```

---

## ⚙️ Configuration

All settings are in `.env`. Key options:

| Variable | Description | Default |
|---|---|---|
| `BOT_TOKEN` | Token from @BotFather | required |
| `ADMIN_IDS` | Comma-separated Telegram IDs | required |
| `BOT_RUN_MODE` | `polling` or `webhook` | `polling` |
| `REMNAWAVE_API_URL` | Your Remnawave panel URL | required |
| `REMNAWAVE_API_KEY` | Remnawave API key | required |
| `YOOKASSA_ENABLED` | Enable YooKassa payments | `false` |
| `CRYPTOBOT_ENABLED` | Enable CryptoBot payments | `false` |
| `TRIAL_ENABLED` | Enable trial period | `true` |
| `TRIAL_DAYS` | Trial duration in days | `3` |
| `PLAN_30_DAYS_PRICE` | Price in kopecks (150 RUB = 15000) | `15000` |

---

## 💳 Payment Setup

### YooKassa
1. Set `YOOKASSA_ENABLED=true`
2. Set `YOOKASSA_SHOP_ID` and `YOOKASSA_SECRET_KEY`
3. Configure webhook in YooKassa dashboard → `https://your-domain.com/yookassa-webhook`

### CryptoBot
1. Set `CRYPTOBOT_ENABLED=true`
2. Set `CRYPTOBOT_API_TOKEN` from @CryptoBot
3. Configure webhook → `https://your-domain.com/cryptobot-webhook`

---

## 🛡️ Admin Panel

Send `/admin` to access the admin panel. Available to `ADMIN_IDS` only.

**Features:**
- 👥 User management (search, ban/unban, balance adjustments)
- 📊 Statistics (users, subscriptions, revenue)
- 🎁 Promo code management (create, list, deactivate)
- 📢 Broadcast messages to all users
- ⚙️ Remnawave server status and stats

---

## 🗂️ Project Structure

```
vpn-bot/
├── main.py                    # Entry point
├── .env.example               # Config template
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── bot/
    ├── config.py              # Pydantic settings
    ├── database.py            # SQLAlchemy models
    ├── states.py              # FSM states
    ├── handlers/
    │   ├── start.py           # /start, main menu
    │   ├── buy.py             # Subscription purchase flow
    │   ├── balance.py         # Top-up balance
    │   ├── subscriptions.py   # View subscriptions
    │   ├── promo.py           # Promo codes
    │   └── admin.py           # Full admin panel
    ├── keyboards/
    │   ├── user.py            # User-facing buttons
    │   └── admin.py           # Admin buttons
    ├── middlewares/
    │   └── user.py            # Auto-register users
    └── services/
        ├── remnawave.py       # Remnawave API client
        ├── user_service.py    # User DB operations
        ├── subscription_service.py
        └── promo_service.py
```

---

## 📋 Bot Commands

| Command | Description |
|---|---|
| `/start` | Open main menu |
| `/admin` | Open admin panel (admins only) |

---

## 🔧 Adding PostgreSQL

1. Uncomment the `postgres` service in `docker-compose.yml`
2. Change `DATABASE_URL` in `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://vpnuser:strongpassword@postgres:5432/vpnbot
   ```
3. Add `asyncpg` to `requirements.txt`
4. Restart: `docker compose up -d`

---

## 📝 License

MIT
