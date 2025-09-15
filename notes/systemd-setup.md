# Fantasy Board Systemd Setup

This document records the setup steps and configuration files required to automatically run the fantasy board update script (`pi/update_scores.sh`) on a schedule.  
The Pi writes `scoreboard.json` into `~/fantasy-board/www`, which is served over HTTP for the MatrixPortal to fetch.

---

## 1. Script location

The main script lives inside the project:

```
/home/kiernan/fantasy-board/pi/update_scores.sh
```

That script calls the project’s virtual environment to run `query_scores.py`, handles atomic JSON writes, and implements:
- Gametime vs. offhours cadence (1m vs. 30m updates)
- Quiet hours (00:00–08:00 → writes `{"status":"sleep"}`)

---

## 2. Systemd service (user)

**Path:** `~/.config/systemd/user/scoreboard-update.service`

```ini
[Unit]
Description=Run fantasy board updater (query_scores.py -> scoreboard.json)
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/home/kiernan/fantasy-board/pi
ExecStart=/home/kiernan/fantasy-board/pi/update_scores.sh
```

---

## 3. Gametime timer (user)

**Path:** `~/.config/systemd/user/scoreboard-update-gametime.timer`

```ini
[Unit]
Description=Fantasy board - gametime cadence (every 1m during defined windows)

[Timer]
Timezone=America/New_York
Persistent=true
AccuracySec=1s

# Mon & Thu 19:00–23:59 ET, every 1 minute
OnCalendar=Mon,Thu *-*-* 19..23:*:00

# Sun 12:00–23:59 ET, every 1 minute
OnCalendar=Sun *-*-* 12..23:*:00

Unit=scoreboard-update.service

[Install]
WantedBy=timers.target
```

---

## 4. Off-hours timer (user)

**Path:** `~/.config/systemd/user/scoreboard-update-offhours.timer`

```ini
[Unit]
Description=Fantasy board - off-hours cadence (every 30m on the half-hour)

[Timer]
Timezone=America/New_York
Persistent=true
AccuracySec=1s

# Every 30 minutes on the half-hour
OnCalendar=*:00,30

Unit=scoreboard-update.service

[Install]
WantedBy=timers.target
```

---

## 5. Enable and reload

After creating the service and timer files:

```bash
# Reload user units
systemctl --user daemon-reload

# Enable both timers
systemctl --user enable --now scoreboard-update-gametime.timer scoreboard-update-offhours.timer
```

---

## 6. Useful checks

```bash
# See timers and next run times
systemctl --user list-timers | grep scoreboard

# Manual run of the service
systemctl --user start scoreboard-update.service

# View logs from the script
journalctl --user -u scoreboard-update.service -n 50 --no-pager
journalctl --user -u scoreboard-update.service -f
```

---

This summary was updated to reflect the current setup (quiet hours handled in `update_scores.sh`, JSON served over HTTP, no CIRCUITPY USB mount).
