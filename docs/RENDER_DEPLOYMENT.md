# Render Deployment Guide for RaktSetu

This guide provides exact configuration settings to deploy RaktSetu publicly on [Render](https://render.com) for hackathon submission without paying for hosting or changing product scope.

---

## Architecture Summary

- **Backend**: Render Web Service (Free Tier, Python). Binds to `0.0.0.0:$PORT`, runs Alembic migrations on startup, automatically seeds the empty database from `data/deployment_snapshot.json`, and exposes `/api/health` and `/api/blood-banks`.
- **Frontend**: Render Static Site (Free Tier, Node.js). Pre-rendered Vite SPA published from `frontend/dist`.
- **Database**: Ephemeral SQLite database initialized automatically on startup via database migrations and snapshot seeding (no committed database files required).
- **Telegram Bot**: Local polling bot is **not** automatically hosted by deploying the website and API (see note below).

---

## 1. Backend Web Service

In the Render Dashboard, click **New +** > **Web Service**, connect your GitHub repository ([rayyan-sidd/RaktSetu](https://github.com/rayyan-sidd/RaktSetu)), and configure the following settings:

| Setting | Value |
|---|---|
| **Name** | `raktsetu-api` |
| **Region** | Closest region (e.g., Singapore or Frankfurt) |
| **Branch** | `feat/blood-bank-discovery` |
| **Root Directory** | *(leave blank / repository root)* |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r backend/requirements.txt` |
| **Start Command** | `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT` |
| **Plan Type** | `Free` |

### Advanced Settings:
- **Health Check Path**: `/api/health`
- **Auto-Deploy**: `Yes`

### Environment Variables:
| Variable | Value | Notes |
|---|---|---|
| `PYTHON_VERSION` | `3.11.6` | Recommended Python version |
| `RAKTSETU_CORS_ORIGINS` | `https://raktsetu.onrender.com` | Replace with your deployed frontend URL once created |
| `RAKTSETU_DATABASE_URL` | `sqlite:///data/raktsetu.db` | Default SQLite location |

> [!NOTE]
> On container startup, RaktSetu runs schema migrations to `head` first, then safely loads the 163 facilities and 110 stock reports from the version-controlled `data/deployment_snapshot.json` fixture. If the database already contains data, it skips seeding to prevent overwriting.

---

## 2. Frontend Static Site

In the Render Dashboard, click **New +** > **Static Site**, connect your GitHub repository, and configure the following settings:

| Setting | Value |
|---|---|
| **Name** | `raktsetu` (or `raktsetu-web`) |
| **Branch** | `feat/blood-bank-discovery` |
| **Root Directory** | `frontend` |
| **Build Command** | `npm ci && npm run build` |
| **Publish Directory** | `dist` |
| **Plan Type** | `Free` |

### Environment Variables (Build Time):
| Variable | Value | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | `https://raktsetu-api.onrender.com` | **Must point to your deployed backend Web Service URL** (without trailing slash) |
| `VITE_TELEGRAM_BOT_URL` | *(leave unset)* | **Leave unset** unless the Telegram bot is public and running 24/7. When unset, the UI displays local development status notices. |

---

## 3. Important Notes & Limitations

### Telegram Bot Hosting
> [!IMPORTANT]
> The local Telegram discovery bot (`backend.app.bot.main`) is **not automatically hosted** by deploying the website and API web service.
> - The web service runs `uvicorn backend.app.main:app` to serve HTTP requests.
> - The Telegram bot runs an asynchronous long-polling loop against the Telegram Bot API (`getUpdates`).
> - Deploying the frontend static site and backend API makes blood bank discovery fully operational for web users. The bot is an optional coordination channel that runs locally during demonstrations or can be deployed separately as a background worker.

### Free Tier Sleep Behavior
- Render's Free Web Services spin down after 15 minutes of inactivity.
- The first request after spindown may take 30–50 seconds to boot the container, run migrations, and initialize the snapshot.
- The health check at `/api/health` can be used to monitor availability.
