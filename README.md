# VICIdial Listener & ARI Speech-to-Text (STT) Bridge

A lightweight Python service that listens to Asterisk AMI events, retrieves VICIdial lead information, and updates VICIdial lead details or dynamically streams call audio to an external Speech-to-Text (STT) pipeline using Asterisk ARI Snoop and External Media.

## Features

* **AMI Event Monitoring:** Listens for active call bridge events (`BridgeEnter`, `BridgeLeave`, `Hangup`, `NewCallerid`).
* **Real-Time Audio Snooping:** Streams customer (`spy=in`) and agent (`spy=out`) audio separately to an external STT server via Asterisk ARI External Media.
* **Customer Lookup & Lead Update:** Connects to backend APIs and VICIdial MySQL/MariaDB databases to update lead metadata on the fly.
* **Modular Handlers:** Clean, event-driven architecture separating customer lookup workflows from ARI media streaming handlers.
* **Systemd Integration:** Pre-configured system daemon file for automatic boot-up and production persistence.

- *Environment-based configuration*
- *Systemd service support*
- *Logging*
- *Easy deployment after VICIdial reinstallation*

---

## Project Structure

```
vicidial_listener/
│
├── .vscode/
├── config/
│   └── settings.py            # Loads configuration from .env
│
├── handlers/                  # Event-driven worker logic
│   ├── __init__.py
│   ├── customer_lookup_handler.py  # Handles API lookups & DB updates
│   └── external_media_handler.py   # Handles ARI Snoop & External Media
│
├── logs/                      # Log storage directory
│
├── services/                  # Core integration clients
│   ├── __init__.py
│   ├── ami_service.py         # Asterisk AMI connection manager
│   ├── customer_service.py    # Backend API client
│   ├── logger_service.py      # Structured logger configuration
│   └── vicidial_service.py    # VICIdial DB/MySQL operations
│
├── systemd/
│   └── vicidial_listener.service  # Systemd service unit configuration
│
├── tests/                     # Unit & integration tests
├── venv/                      # Python virtual environment
│
├── .env                       # Active environment variables (Git ignored)
├── .env.example               # Environment template
├── .gitignore
├── .python-version
├── app.py                     # Main application entry point
├── ARCHITECTURE.md            # Technical architecture documentation
├── README.md                  # Project documentation
└── requirements.txt           # Python dependencies
```

---

## Requirements & Prerequisites

* **Python:** 3.6+
* **Asterisk:** Version 16+
* **Asterisk Modules Required on Server 1:**
* `res_ari.so`
* `res_ari_channels.so`
* `res_ari_applications.so`
* `app_chanspy.so`

---

## Server Configuration

### 1. `/etc/asterisk/ari.conf`

```ini
[general]
enabled = yes
pretty = yes

[stt_service]
type = user
read_only = no
password = your_secure_ari_password
password_format = plain

```

### 2. `/etc/asterisk/http.conf`

```ini
[general]
enabled = yes
bindaddr = 127.0.0.1
bindport = 8088

```

---

## Useful VICIdial Configuration Files

### AMI

```text
/etc/asterisk/manager.conf

```

Recommended AMI user:

```text
listencron

```

---

### Database

```text
/etc/astguiclient.conf

```

Recommended database user:

```text
cron

```


## Installation

1. **Clone the repository:**
```bash
cd /opt
git clone <repository-url> vicidial_listener
cd vicidial_listener

```


2. **Create and activate virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate

```


3. **Install dependencies:**
```bash
pip install -r requirements.txt

```


---

## Environment Configuration

Copy `.env.example` to `.env` and adjust your variables:

```bash
cp .env.example .env

```

**`.env` Configuration File:**

```env
LOG_LEVEL=INFO

# Asterisk AMI
AMI_HOST=127.0.0.1
AMI_PORT=5038
AMI_USERNAME=admin
AMI_PASSWORD=password

# VICIdial Database
VICIDIAL_DB_HOST=127.0.0.1
VICIDIAL_DB_PORT=3306
VICIDIAL_DB_NAME=asterisk
VICIDIAL_DB_USER=cron
VICIDIAL_DB_PASSWORD=1234

# Backend API
API_BASE_URL=http://localhost:3000/api

# Asterisk ARI Configuration
ARI_BASE_URL=http://127.0.0.1:8088/ari
ARI_USER=stt_service
ARI_PASS=your_secure_ari_password

# STT Processing Server
STT_SERVER_IP=192.168.1.100

```

---

## Running the Application

Activate virtual environment

```bash
source venv/bin/activate
```

Run

```bash
python app.py
```

---

### Development Mode

```bash
cd /opt/vicidial_listener
source venv/bin/activate
python app.py

```

---

### Production Mode (Systemd Service)

**Copy the systemd unit file:**
```bash
sudo cp systemd/vicidial_listener.service /etc/systemd/system/

```

**Enable and start the service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable vicidial_listener
sudo systemctl start vicidial_listener

```

**Restart and status the service:**
```bash
sudo systemctl restart vicidial_listener
sudo systemctl status vicidial_listener

```

**Monitor logs:**
```bash
journalctl -u vicidial_listener -f

```

or

```bash
tail -f logs/listener.log
```

---


# License

Internal project for VICIdial customer integration.