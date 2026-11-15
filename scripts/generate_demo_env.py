"""Generate untracked local demo credentials; never put real passwords in Git."""
import argparse
import json
import secrets
from pathlib import Path

from app.auth import hash_password

parser = argparse.ArgumentParser()
parser.add_argument("--output", default=".env.demo")
parser.add_argument("--password", default=None)
args = parser.parse_args()
password = args.password or secrets.token_urlsafe(12)
users = {"demo": {"tenant": "acme", "password_hash": hash_password(password)}}
metrics_token = secrets.token_urlsafe(32)
env_file = Path(args.output)
if env_file.exists():
    raise SystemExit(f"Refusing to overwrite {env_file}")
env_file.write_text(
    "AUTH_JWT_SECRET=" + secrets.token_urlsafe(48) + "\n"
    + "RUNBOOK_USERS_JSON=" + json.dumps(users, separators=(",", ":")) + "\n"
    + "METRICS_TOKEN=" + metrics_token + "\n"
    + "GRAFANA_ADMIN_PASSWORD=" + secrets.token_urlsafe(24) + "\n"
)
env_file.chmod(0o600)
metrics_file = env_file.with_name(".metrics-token")
metrics_file.write_text(metrics_token + "\n")
metrics_file.chmod(0o600)
print(f"Generated {env_file} for tenant acme with user demo")
print(f"Demo password (save it now; not written in plaintext): {password}")
print("Metrics bearer token is stored in .env.demo (treat it as a secret).")
