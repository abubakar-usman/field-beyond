#!/usr/bin/env bash
# Laptop. Stop the VM (compute billing stops; the disk is still about $20/month).
source "$(dirname "$0")/_lib.sh"
gc compute instances stop "$VM_NAME" --zone "$ZONE"
say "stopped"
