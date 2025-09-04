# Fantasy Board Systemd Setup

This document records the setup steps and configuration files required to automatically run the fantasy board update script (`pi/update_scores.sh`) on a schedule and copy its output to CIRCUITPY.

---

## 1. Script location

The main script lives inside the project:

```
/home/kiernan/fantasy-board/pi/update_scores.sh
```

That script calls the project’s virtual environment to run `query_scores.py` and handles atomic JSON writes and copies.  
(Already versioned in your repo, so not included here.)

---

## 2. Systemd service

**Path:** `/etc/systemd/system/fantasy-board.service`

```ini
[Unit]
Description=Run fantasy board updater (query_scores.py -> scoreboard.json and copy to CIRCUITPY)
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=kiernan
Group=kiernan
WorkingDirectory=/home/kiernan/fantasy-board/pi
ExecStart=/home/kiernan/fantasy-board/pi/update_scores.sh
```

---

## 3. Gametime timer

**Path:** `/etc/systemd/system/fantasy-board-gametime.timer`

```ini
[Unit]
Description=Fantasy board - gametime cadence (every 2m during defined windows)

[Timer]
Timezone=America/New_York
Persistent=true
AccuracySec=1s

# Mon & Thu 19:00–23:59 ET, every 2 minutes
OnCalendar=Mon,Thu *-*-* 19..23:0/2

# Sun 12:00–23:59 ET, every 2 minutes
OnCalendar=Sun *-*-* 12..23:0/2

Unit=fantasy-board.service

[Install]
WantedBy=timers.target
```

---

## 4. Off-hours timer

**Path:** `/etc/systemd/system/fantasy-board-offhours.timer`

```ini
[Unit]
Description=Fantasy board - off-hours cadence (every 30m)

[Timer]
Timezone=America/New_York
Persistent=true
AccuracySec=1s

# Every 30 minutes, all day
OnCalendar=*:0/30

Unit=fantasy-board.service

[Install]
WantedBy=timers.target
```

---

## 5. fstab entry for CIRCUITPY automount

Edited `/etc/fstab` to enable systemd automount.  

```fstab
LABEL=CIRCUITPY /mnt/CIRCUITPY vfat nofail,noauto,x-systemd.automount,x-systemd.idle-timeout=5min,uid=1000,gid=1000,umask=022 0 0
```

This allows systemd to mount `/mnt/CIRCUITPY` automatically when first accessed and unmount it after 5 minutes idle.  

---

## 6. Enable and reload

After creating the service and timer files and updating fstab:

```bash
# Reload systemd units
sudo systemctl daemon-reload

# Enable both timers
sudo systemctl enable --now fantasy-board-gametime.timer fantasy-board-offhours.timer

# Restart local-fs to pick up the new fstab automount
sudo systemctl restart local-fs.target
```

---

## 7. Useful checks

```bash
# See timers and next run times
systemctl list-timers | grep fantasy-board

# Manual run of the service
sudo systemctl start fantasy-board.service

# View logs
journalctl -u fantasy-board.service -n 50 --no-pager
journalctl -u fantasy-board.service -f
```

---

This summary was written with the help of ChatGPT v5
