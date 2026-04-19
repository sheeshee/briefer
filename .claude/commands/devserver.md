Start or stop the Briefer development server.

## Starting the server

Always bind to `0.0.0.0:8000` so the server accepts connections from all network interfaces — this is required for accessing Briefer from other devices on the same local network.

```bash
uv run manage.py runserver 0.0.0.0:8000
```

Run this in the background. After starting, provide the access URL using the machine's mDNS hostname:

**http://sheehy-xps.local:8000**

## Stopping the server

```bash
pkill -f "manage.py runserver"
```

## Notes

- The hostname `sheehy-xps.local` resolves via mDNS on the local network, allowing access from phones, tablets, or other computers without knowing the IP address.
- `ALLOWED_HOSTS` is already set to `*` by default in `briefer/settings.py`, so no config change is needed.
- Always prefer `0.0.0.0:8000` over `127.0.0.1:8000` — localhost-only binding makes the server inaccessible from other devices.
