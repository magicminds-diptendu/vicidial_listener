# VICIdial Listener

A lightweight Python service that listens to **Asterisk AMI events**, retrieves customer information from your backend API, and updates VICIdial lead information in real time.

## Features

- Listen to Asterisk AMI events
- Event-driven architecture using decorators
- Customer lookup via backend API
- Update customer details in VICIdial
- MySQL/MariaDB integration
- Environment-based configuration
- Systemd service support
- Logging
- Easy deployment after VICIdial reinstallation

---

# Project Structure

```
vicidial_listener/
│
├── app.py                     # Application entry point
├── requirements.txt
├── README.md
├── .env
├── .env.example
├── .gitignore
│
├── config/
│   ├── __init__.py
│   └── settings.py            # Environment configuration
│
├── services/
│   ├── __init__.py
│   ├── ami_service.py         # Asterisk AMI listener
│   ├── customer_service.py    # Backend API integration
│   ├── vicidial_service.py    # VICIdial database operations
│   └── logger.py              # Logging configuration
│
├── logs/
│   └── listener.log
│
├── tests/
│
├── systemd/
│   └── vicidial_listener.service
│
└── venv/
```

---

# Requirements

- Python 3.6+
- VICIdial
- Asterisk AMI
- MariaDB/MySQL

---

# Installation

Clone the project

```bash
cd /opt

git clone <repository-url> vicidial_listener

cd vicidial_listener
```

---

## Create Virtual Environment

```bash
python3 -m venv venv
```

Activate

```bash
source venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Configuration

Create a `.env` file.

Example:

```env
LOG_LEVEL=INFO

# Asterisk AMI
AMI_HOST=127.0.0.1
AMI_PORT=5038
AMI_USERNAME=listencron
AMI_PASSWORD=1234

# VICIdial Database
VICIDIAL_DB_HOST=127.0.0.1
VICIDIAL_DB_PORT=3306
VICIDIAL_DB_NAME=asterisk
VICIDIAL_DB_USER=cron
VICIDIAL_DB_PASSWORD=1234

# Backend API
API_BASE_URL=http://127.0.0.1:3000/api
API_TOKEN=your_api_token
```

---

# Running the Application

Activate virtual environment

```bash
source venv/bin/activate
```

Run

```bash
python app.py
```

---

# Development

Start development

```bash
cd /opt/vicidial_listener

source venv/bin/activate

python app.py
```

---

# AMI Event Handlers

Register events using decorators.

```python
from services.ami_service import AMIService

ami = AMIService()


@ami.on("NewCallerid")
def handle_new_call(event):
    print(event.keys)


@ami.on("Newstate")
def handle_new_state(event):
    print(event.keys)


@ami.on("Hangup")
def handle_hangup(event):
    print(event.keys)


if __name__ == "__main__":
    ami.start()
```

---

# Customer Lookup Flow

```
Incoming Call
      │
      ▼
Asterisk AMI
      │
      ▼
NewCallerid Event
      │
      ▼
Backend API Lookup
      │
      ▼
Customer Found
      │
      ▼
Update VICIdial Lead
      │
      ▼
Agent Receives Customer Information
```

---

# Logging

Logs are stored in

```
logs/listener.log
```

---

# Systemd Service

Copy the service file

```bash
sudo cp systemd/vicidial_listener.service /etc/systemd/system/
```

Reload systemd

```bash
sudo systemctl daemon-reload
```

Enable service

```bash
sudo systemctl enable vicidial_listener
```

Start service

```bash
sudo systemctl start vicidial_listener
```

Restart

```bash
sudo systemctl restart vicidial_listener
```

Check status

```bash
sudo systemctl status vicidial_listener
```

View logs

```bash
journalctl -u vicidial_listener -f
```

or

```bash
tail -f logs/listener.log
```

---

# Useful VICIdial Configuration Files

### AMI

```
/etc/asterisk/manager.conf
```

Recommended AMI user

```
listencron
```

---

### Database

```
/etc/astguiclient.conf
```

Recommended database user

```
cron
```

---


# License

Internal project for VICIdial customer integration.