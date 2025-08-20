#!/usr/bin/env bash
set -euo pipefail

gcloud beta emulators pubsub start --project=demo --host-port=0.0.0.0:8085
