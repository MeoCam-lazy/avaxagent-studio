#!/usr/bin/env bash
# Run from the local machine with Git Bash: bash deploy/start_oci.sh
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python_bin=${OCI_PYTHON_BIN:-}
if [[ -z "$python_bin" ]]; then
  if [[ -x "$repo_root/deploy/.venv/Scripts/python.exe" ]]; then
    python_bin="$repo_root/deploy/.venv/Scripts/python.exe"
  else
    python_bin="$repo_root/deploy/.venv/bin/python"
  fi
fi
if [[ ! -x "$python_bin" ]]; then
  echo "OCI Python environment missing: $python_bin" >&2
  exit 1
fi

ssh_key=${OCI_SSH_KEY:-$HOME/.ssh/avaxagent_oci}
ssh_user=${OCI_SSH_USER:-ubuntu}
if [[ ! -f "$ssh_key" ]]; then
  echo "SSH key missing: $ssh_key" >&2
  exit 1
fi

public_ip=$("$python_bin" "$repo_root/deploy/start_oci_vm.py" --start)
ssh_target="$ssh_user@$public_ip"
echo "Waiting for SSH on $ssh_target..."
for attempt in {1..18}; do
  if ssh -i "$ssh_key" -o BatchMode=yes -o ConnectTimeout=5 \
    -o StrictHostKeyChecking=accept-new "$ssh_target" true >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" == 18 ]]; then
    echo "SSH unavailable. Check the VM's public IP and OCI SSH ingress rule." >&2
    exit 1
  fi
  sleep 5
done

ssh -i "$ssh_key" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
  "$ssh_target" "cd /home/ubuntu/avaxagent-studio && bash deploy/start_oci_stack.sh $public_ip"
