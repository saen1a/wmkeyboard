#!/usr/bin/env bash
# Fixture installer: performs the one missing step and nothing else.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p config state
cat > config/agent.yml <<'YML'
port: 8080
target: /opt/agent-cli
YML
: > state/ready
echo "installed: config/agent.yml written, state/ready present"
