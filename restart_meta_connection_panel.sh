#!/usr/bin/env bash
set -euo pipefail

sudo systemctl restart meta-connection-panel
sudo systemctl status meta-connection-panel --no-pager
