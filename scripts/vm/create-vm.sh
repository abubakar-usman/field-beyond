#!/usr/bin/env bash
# Laptop, once (Git Bash). Creates bucket, service account, static IP, firewall rules and the VM.
# COSTS MONEY: about $3/day while the VM runs and about $20/month for the disk. Confirm with the owner first.
source "$(dirname "$0")/_lib.sh"
need gcloud
need curl

say "project $PROJECT_ID"
gcloud config set project "$PROJECT_ID" >/dev/null
gc services enable compute.googleapis.com storage.googleapis.com

if gc storage buckets describe "$BUCKET" >/dev/null 2>&1; then
  say "bucket $BUCKET exists"
else
  say "creating bucket $BUCKET"
  gc storage buckets create "$BUCKET" --location "$REGION" --uniform-bucket-level-access
fi

if gc iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
  say "service account $SA_EMAIL exists"
else
  say "creating service account $SA_NAME"
  gc iam service-accounts create "$SA_NAME" --display-name "EAE VM (bucket only)"
fi
say "granting bucket-level objectAdmin to $SA_EMAIL"
gc storage buckets add-iam-policy-binding "$BUCKET" \
  --member "serviceAccount:$SA_EMAIL" --role roles/storage.objectAdmin >/dev/null

if [[ -n "$(static_ip)" ]]; then
  say "static IP $(static_ip) exists"
else
  say "reserving static IP $IP_NAME"
  gc compute addresses create "$IP_NAME" --region "$REGION"
fi

MYIP="$(curl -fsS https://ifconfig.me)"
if gc compute firewall-rules describe eae-allow-ssh >/dev/null 2>&1; then
  say "updating SSH rule to $MYIP/32"
  gc compute firewall-rules update eae-allow-ssh --source-ranges "$MYIP/32"
else
  say "allowing SSH from $MYIP/32 only"
  gc compute firewall-rules create eae-allow-ssh --allow tcp:22 --source-ranges "$MYIP/32" --target-tags eae
fi
if ! gc compute firewall-rules describe eae-allow-web >/dev/null 2>&1; then
  say "allowing HTTP/HTTPS"
  gc compute firewall-rules create eae-allow-web --allow tcp:80,tcp:443 --source-ranges 0.0.0.0/0 --target-tags eae
fi

if [[ "$(vm_status)" != MISSING ]]; then
  say "VM $VM_NAME exists ($(vm_status))"
else
  say "creating VM $VM_NAME ($VM_TYPE, ${DISK_GB} GB)"
  gc compute instances create "$VM_NAME" --zone "$ZONE" --machine-type "$VM_TYPE" \
    --image-family ubuntu-2404-lts-amd64 --image-project ubuntu-os-cloud \
    --boot-disk-size "${DISK_GB}GB" --boot-disk-type pd-balanced \
    --service-account "$SA_EMAIL" --scopes cloud-platform \
    --tags eae --address "$(static_ip)"
fi

say "next: scripts/vm/ssh.sh, then on the VM clone the repo or copy scripts/vm/, and run bootstrap.sh"
say "public URL will be https://$(public_hostname)"
warn "stop the VM when idle (scripts/vm/stop.sh) and keep a \$50 budget alert on the project"
