#!/usr/bin/env bash
# Laptop. SSH to the VM with the right project and zone.
source "$(dirname "$0")/_lib.sh"
gc compute ssh "$VM_NAME" --zone "$ZONE" "$@"
