#!/usr/bin/env bash
set -euo pipefail

SERVICE="flighttracker.service"

echo "🔍 Checking FlightTracker service..."

# Existence check that doesn't lie:
# - systemctl cat returns non-zero if unit doesn't exist
if ! systemctl cat "$SERVICE" >/dev/null 2>&1; then
  echo "❌ Service $SERVICE not found"
  echo "Check: /etc/systemd/system/$SERVICE"
  echo
  echo "Tip: run -> sudo systemctl status $SERVICE --no-pager"
  exit 1
fi

if systemctl is-active --quiet "$SERVICE"; then
  echo "♻️  FlightTracker is running — restarting service"
  sudo systemctl restart "$SERVICE"
else
  echo "▶️  FlightTracker is not running — starting service"
  sudo systemctl start "$SERVICE"
fi

echo "✅ Done."

echo
echo "📋 Current process:"
PID="$(systemctl show -p MainPID --value "$SERVICE" || echo 0)"
if [[ -z "${PID}" || "${PID}" == "0" ]]; then
  echo "❌ No MainPID found (service may not be running)"
  echo
  echo "Last 40 log lines:"
  sudo journalctl -u "$SERVICE" -n 40 --no-pager || true
else
  ps -o user,pid,cmd -p "$PID" || true
fi
