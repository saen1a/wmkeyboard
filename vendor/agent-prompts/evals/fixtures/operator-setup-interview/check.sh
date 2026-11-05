#!/usr/bin/env bash
# Fixture ready condition: config with the expected port and a ready marker.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f config/agent.yml ]; then
  echo "NOT READY: config/agent.yml is absent"
  exit 1
fi
if ! grep -qx 'port: 8080' config/agent.yml; then
  echo "NOT READY: config/agent.yml does not carry port: 8080"
  exit 1
fi
if [ ! -f state/ready ]; then
  echo "NOT READY: state/ready is absent"
  exit 1
fi
echo "READY: config/agent.yml port 8080, state/ready present"
