# Validation

## Automated Local Proof

- `python -m pytest`
- `python -m compileall -q src tests`
- `python -m pip install --dry-run -e ".[dev]"`
- `docker compose config --quiet` when Docker is available

Coverage includes public challenge/rate/cache/admin paths, Telegram delivery
success/failure, resolver safety/gate behavior, and migration structures.

## External Proof Still Required

- Supabase key rotation before any public or long-lived deployment.
- Bounded Telegram message delivery.
- Resolver real component-link proof.
- Cloudflare Tunnel public ingress and origin non-bypass smoke.
