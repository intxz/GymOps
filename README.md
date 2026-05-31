# GymOps - Fitness Tracker via Telegram

> Telegram bot for logging strength workouts, analyzing progression, and monitoring metrics. Designed for self-hosting on Raspberry Pi 5 with Ubuntu 26.04 LTS.

## What is GymOps?

GymOps is a Telegram bot that lets you log strength workouts directly from chat. Type `/squat 100x5 8` and the bot saves the set with weight, reps, and RPE (rate of perceived exertion). When you end the session (`/end`), you receive a detailed summary with progression analysis, load recommendations, and volume metrics.

Everything runs in Docker containers with a lightweight architecture: SQLite as the database, FastAPI for logic, and Nginx Proxy Manager to expose services with SSL.

## Architecture

```
[Telegram] ←→ [Bot (aiogram)] ←→ [FastAPI + SQLite]
                     ↓
            [Prometheus] ←→ [Grafana]
                     ↑
         [Nginx Proxy Manager + SSL (Let's Encrypt)]
```

| Component | Description |
|-----------|-------------|
| **FastAPI** | Stores users, sessions, sets. Calculates statistics and exposes Prometheus metrics on `/metrics`. |
| **Telegram Bot** | Receives commands, parses dynamic exercises (`/<exercise> WEIGHTxREPS RPE`), and talks to the API. |
| **SQLite** | Embedded database in Docker volume (`gymops_data`). No external server. |
| **Prometheus + Grafana** | Built-in observability. Provisioned dashboards for volume, effective sets, e1RM, etc. |
| **Nginx Proxy Manager** | Reverse proxy with free SSL via Let's Encrypt. Exposes `gymops.yourdomain.com` and `grafana-gymops.yourdomain.com`. |

## Requirements

Tested and optimized for:

| Requirement | Detail |
|-----------|---------|
| Hardware | Raspberry Pi 5 Model B (ARM64, 4 cores) |
| OS | Ubuntu 26.04 LTS (Resolute Raccoon) |
| Docker Engine | ≥ 24.x |
| Docker Compose | ≥ v2.x (`docker compose` plugin) |
| Public domain | Required for SSL certificates (e.g., `a2technology.net`) |
| BotFather token | For your Telegram bot (e.g., `@gymops`) |

### Install Docker (if not already)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine and Docker Compose
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add user to docker group (requires re-login)
sudo usermod -aG docker $USER
```

## Step-by-step installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/gymops.git
cd gymops
```

### 2. Configure environment variables

Copy the example file and edit it with your data:

```bash
cp infra/docker/.env.example infra/docker/.env
nano infra/docker/.env
```

Required variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token (from BotFather) | `123456789:ABC...` |
| `API_SECRET_KEY` | Shared secret between bot and API (generate a long random string) | `sk-gymops-64chars...` |
| `PUBLIC_DOMAIN` | Your public domain | `a2technology.net` |
| `PUBLIC_API_SUBDOMAIN` | Subdomain for the API | `gymops` |
| `PUBLIC_GRAFANA_SUBDOMAIN` | Subdomain for Grafana | `grafana-gymops` |
| `NPM_ADMIN_BIND` | IP and port for NPM panel (LAN only) | `192.168.1.66:81` |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password | `astrongpassword` |

Optional (Hermes AI):

| Variable | Description |
|----------|-------------|
| `HERMES_OAUTH_ENABLED` | `true` to use Hermes CLI with your local OAuth |
| `HERMES_HOME_HOST` | Path to your Hermes profile on the host (e.g., `/home/raspi/.hermes`) |
| `OPENAI_ENABLED` | `false` by default. `true` to use OpenAI as fallback |
| `OPENAI_API_KEY` | Only if `OPENAI_ENABLED=true` |

### 3. Start the stack

```bash
docker compose -f infra/docker/docker-compose.rpi.yml up -d --build
```

This builds and starts:
- `gym-api` (FastAPI)
- `gym-telegram-bot` (aiogram)
- `gym-prometheus`
- `gym-grafana`
- `gym-npm` (Nginx Proxy Manager)

Verify everything is running:
```bash
docker ps -a
```

### 4. Configure Nginx Proxy Manager and SSL

1. Access the admin panel: `http://192.168.1.66:81` (adjust to your LAN IP).
   - Default email: `admin@example.com`
   - Default password: `changeme`

2. Change the default credentials.

3. Create a **Proxy Host** for the API:
   - **Domain Names**: `gymops.a2technology.net` (adjust to your domain)
   - **Scheme**: `http`
   - **Forward Hostname / IP**: `192.168.1.66` (Raspberry LAN IP)
   - **Forward Port**: `8000`
   - Go to the **SSL** tab → Request a **Let's Encrypt** certificate.

4. Create another **Proxy Host** for Grafana (optional):
   - **Domain Names**: `grafana-gymops.a2technology.net`
   - **Forward Hostname / IP**: `gym-grafana` (container name, if on the same Docker network) or the LAN IP.
   - **Forward Port**: `3000`
   - Enable SSL.

> **Recommended guide**: For a more detailed explanation of the reverse proxy and SSL process with Nginx Proxy Manager, check: https://blog.runesoft.net/ssl-y-proxy-inverso-con-nginx-proxy-manager/

### 5. Configure Telegram Webhook (Optional)

By default, the bot uses **polling** (no webhook or exposed ports needed for Telegram). If you prefer webhook for better efficiency in production:

1. Add `WEBHOOK_URL=https://gymops.yourdomain.com/webhook` to your `.env`.
2. Expose the bot port or configure the webhook on the API.
3. Run: `curl -F "url=https://gymops.yourdomain.com/webhook" https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook`

## Bot usage

Once the bot is running, send it a message on Telegram:

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Start a new workout session | — |
| `/<exercise> WEIGHTxREPS RPE` | Log a set | `/squat 100x5 8` |
| `/end` | End session and generate summary | — |
| `/cancel` | Cancel active session | — |
| `/status` | Show current session status | — |
| `/history <exercise>` | Show history and analysis for exercise | `/history bench_press` |
| `/help` | Show help with all commands | — |

### Typical workout flow

1.  **Start session**:
    ```
    /start
    ```
    Bot replies: *"Workout started. Timer running."*

2.  **Log sets** (mixing warm-up and effective sets):
    ```
    /squat 60x8 0      <- Warm-up (RPE 0)
    /squat 100x5 8     <- Effective set #1 (RPE 8)
    /squat 100x5 9     <- Effective set #2 (RPE 9)
    /squat 100x5 10    <- Effective set #3 (RPE 10)
    ```

3.  **End session**:
    ```
    /end
    ```
    You will receive a summary with total volume, progression analysis, and recommendations for the next session.

4.  **Check history** (at any time):
    ```
    /history squat
    ```

## API Endpoints

The API exposes the following endpoints under `/api/v1`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service healthcheck |
| `GET` | `/metrics` | Metrics in Prometheus format |
| `POST` | `/sessions/start` | Start a workout session |
| `POST` | `/sessions/end` | End active session |
| `POST` | `/sessions/cancel` | Cancel active session |
| `GET` | `/sessions/active` | Get active session for a user |
| `GET` | `/sessions/{id}` | Get details of a specific session |
| `POST` | `/sets` | Log an exercise set |
| `GET` | `/stats/exercise/{exercise}` | Statistics for an exercise |
| `GET` | `/summary/{session_id}` | Full summary of a session |

## Observability

The stack includes Prometheus and Grafana to monitor system performance and workouts.

- **Prometheus**: Collects API metrics (rate, errors, latency, volume, effective sets, etc.).
- **Grafana**: Visualization with provisioned dashboards:
  - **GymOps Overview**: General system status.
  - **GymOps Training Progress**: Progression per exercise (effective volume, best weight, estimated e1RM, RPE).

Access (through NPM with SSL):
- `https://grafana-gymops.yourdomain.com`
- User: `admin` (or the one defined in `GRAFANA_ADMIN_USER`)
- Password: the one defined in `GRAFANA_ADMIN_PASSWORD`

## Security

- **Only expose ports 80 and 443** to the internet. These are managed by Nginx Proxy Manager.
- **Do not expose port 8000** of the API directly to the outside. Only NPM should reach it (using the internal LAN IP or the Docker `gym_backend` network).
- **The NPM admin panel (`:81`)** should be bound to your LAN IP (e.g., `192.168.1.66:81`), not `0.0.0.0`.
- **Regenerate the `TELEGRAM_BOT_TOKEN`** if you shared the bot during testing and are moving to production.
- **Change default passwords** for Grafana and Nginx Proxy Manager immediately after first boot.

## Troubleshooting

### 502 Bad Gateway error

**Symptom**: You access `https://gymops.yourdomain.com` and see "502 Bad Gateway".

**Cause**: Nginx Proxy Manager cannot connect to the `gym-api` container.

**Solution**: In the NPM Proxy Host configuration, use the **Raspberry LAN IP** (e.g., `192.168.1.66`) as *Forward Hostname / IP*, pointing to port `8000`. If both containers are on the same custom Docker network (like `gym_backend`), you can also use the container name (`gym-api`).

### Bot not responding

**Symptom**: You send commands but the bot does not reply.

**Solution**:
1. Verify the `gym-telegram-bot` container is running: `docker logs gym-telegram-bot`.
2. Confirm the token in `infra/docker/.env` is correct.
3. Ensure the API is reachable from the bot: `docker exec gym-telegram-bot curl -v http://gym-api:8000/health`.

### Issues with Hermes / OAuth

**Symptom**: The summary doesn't use Hermes analysis and falls back to local.

**Solution**: Verify the `HERMES_HOME_HOST` path in your `.env` points correctly to the `.hermes` directory of your user on the host. The API container mounts this directory to reuse your OAuth session.

## Deploying changes to a running Raspberry Pi

If your Raspberry Pi is already running GymOps and you need to apply code changes (like the API key security update):

### 1. Update the code on the Raspberry Pi

```bash
cd ~/gymops  # or wherever you cloned the repo
git pull
cp infra/docker/.env.example infra/docker/.env
# Edit .env and add your API_SECRET_KEY
nano infra/docker/.env
```

### 2. Rebuild and restart the containers

```bash
docker compose -f infra/docker/docker-compose.rpi.yml down
docker compose -f infra/docker/docker-compose.rpi.yml up -d --build
```

> **Why `--build`?** The bot and API are built from local Dockerfiles. Any code change in `services/api` or `services/bot` requires a rebuild.

### 3. Verify everything is running

```bash
docker ps -a
docker logs gym-api --tail 20
docker logs gym-telegram-bot --tail 20
```

## Auto-start on boot (power outage recovery)

All GymOps containers already have `restart: unless-stopped` in the Docker Compose file. This means:

- If a container crashes, Docker restarts it automatically.
- If the Raspberry Pi reboots, Docker starts all containers automatically.

### Ensure Docker starts on boot

```bash
# Enable Docker to start on system boot
sudo systemctl enable docker

# Verify
sudo systemctl is-enabled docker
```

### Optional: faster boot with docker-compose wait

If you want the stack to come up immediately after a power outage without manual intervention, make sure you start it with `docker compose up -d` at least once. Docker remembers which containers should be running.

You can also create a systemd service for the stack:

```bash
sudo nano /etc/systemd/system/gymops.service
```

Paste:

```ini
[Unit]
Description=GymOps Docker Stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/raspi/gymops/infra/docker
ExecStart=/usr/bin/docker compose -f docker-compose.rpi.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.rpi.yml down

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable gymops
sudo systemctl start gymops
```

> **Note:** Adjust `/home/raspi/gymops` to your actual repository path.

## Production Checklist

- [ ] Regenerate `TELEGRAM_BOT_TOKEN` in BotFather.
- [ ] Set a strong `API_SECRET_KEY` (at least 32 random characters).
- [ ] Configure domain and subdomains with your DNS provider.
- [ ] Verify router ports 80 and 443 point to the Raspberry IP.
- [ ] Change default passwords for Grafana and Nginx Proxy Manager.
- [ ] Ensure `NPM_ADMIN_BIND` is limited to the LAN IP.
- [ ] (Optional) Set up periodic backup of the `gymops_data` volume (SQLite database).

## License

MIT
