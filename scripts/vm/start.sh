#!/usr/bin/env bash
# Laptop. Start the VM.
source "$(dirname "$0")/_lib.sh"
gc compute instances start "$VM_NAME" --zone "$ZONE"
say "started. URL: https://$(public_hostname)  (stop it with scripts/vm/stop.sh when idle)"
