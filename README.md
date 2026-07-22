# att-gateway-py

Python client + CLI to **read and configure AT&T ARRIS fiber gateways** from
scripts and agents. Built for the **CGW452** (AT&T Business Fiber "All-Fi Hub")
and, by firmware family, the **BGW320**.

The headline feature is **programmatic IP Passthrough** — so you can hand the
public IP to your own router (e.g. a UniFi UDM-Pro on WAN2) without clicking
through the gateway's web UI.

> **Why this exists:** every existing open-source tool for these gateways
> (e.g. [`edgan/att-fiber-gateway-info`](https://github.com/edgan/att-fiber-gateway-info))
> is **read-only** monitoring. None can *write* config like IP Passthrough, and
> none targets the CGW452. This does both. The login flow is a Python port of the
> gateway's own nonce + MD5 challenge, cross-checked against that project.

## Install

```bash
pip install -e ".[dev]"      # from a clone
```

## Configure

Copy `.env.example` to `.env` and fill in your gateway's **Device Access Code**
(printed on the sticker, e.g. `12@34567/8`):

```bash
cp .env.example .env
$EDITOR .env
```

`.env` is gitignored — **secrets never get committed** (this is a public repo).

## Use

CLI:

```bash
att-gateway login                     # verify auth
att-gateway ip-passthrough get        # show current state
att-gateway ip-passthrough set --mac aa:bb:cc:11:22:33 --dry-run   # preview the POST
att-gateway ip-passthrough set --mac aa:bb:cc:11:22:33             # apply + verify
att-gateway reboot --dry-run          # preview the restart POST
att-gateway reboot --yes              # restart the gateway (~2-3 min)
```

> **Which MAC?** Bind to the router's **WAN device MAC** (in UniFi:
> Settings → Internet → WAN2 → MAC Address), *not* the port hardware MAC or the
> "Connected MAC" (that's the upstream gateway). See
> [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Library:

```python
from att_gateway import GatewayClient

gw = GatewayClient.from_env()
gw.login()
print(gw.get_ip_passthrough())
gw.set_ip_passthrough(mac="aa:bb:cc:11:22:33")   # reads back to verify
gw.reboot()                                       # apply the new binding
```

## Safety

This writes to a **live edge device**. The client is built to be careful:

- **`--dry-run`** prints the exact POST body without sending it.
- Writes **read back and verify** the value landed (`WriteVerificationError` if not).
- Config forms are **round-tripped** — we parse the whole live form and mutate
  only the fields we intend to change, preserving the per-page nonce and any
  firmware-specific hidden fields.

## Status

| Area | State |
|------|-------|
| Login (nonce + MD5) | ✅ confirmed live on CGW452; unit-tested |
| Form parse / round-trip | ✅ unit-tested |
| IP Passthrough read/write | ✅ confirmed live on CGW452 (public IP handed to a UDM-Pro) |
| Reboot | ✅ confirmed live on CGW452 |
| Device list parse | 🚧 best-effort; layout varies |

Field names (`allocmode`, `passmode`, `passmac`, …) are confirmed against CGW452
firmware. On a different model, `att-gateway ip-passthrough get` will raise with
the real field list if they differ — update the `PASSTHROUGH_*` constants in
`src/att_gateway/client.py` and `--dry-run` before applying.

## Develop

```bash
pytest          # unit tests, no gateway required
ruff check .
```

## License

MIT. Auth flow reverse-engineered from the gateway's own login page;
cross-referenced with `edgan/att-fiber-gateway-info` (also open source).
Not affiliated with or endorsed by AT&T or ARRIS.
