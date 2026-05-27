# Cloudflare Tunnel

Configure the public hostname in Cloudflare to route to:

```text
http://web:8000
```

Set `CLOUDFLARE_TUNNEL_TOKEN` only in the VPS environment consumed by Docker
Compose. The Compose configuration deliberately does not publish the `web`
container port on the host, so public requests reach FastAPI through
Cloudflare Tunnel rather than bypassing Turnstile and edge protections.
