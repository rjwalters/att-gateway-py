"""Command-line interface for att_gateway.

Examples
--------
    att-gateway login
    att-gateway ip-passthrough get
    att-gateway ip-passthrough set --mac aa:bb:cc:77:88:99 --dry-run
    att-gateway ip-passthrough set --mac aa:bb:cc:77:88:99
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .client import GatewayClient
from .exceptions import GatewayError


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (no external dependency)."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _client(args: argparse.Namespace) -> GatewayClient:
    if args.host:
        os.environ["ATT_GATEWAY_HOST"] = args.host
    if args.access_code:
        os.environ["ATT_GATEWAY_ACCESS_CODE"] = args.access_code
    return GatewayClient.from_env()


def cmd_login(args: argparse.Namespace) -> int:
    client = _client(args)
    client.login()
    print("Login OK — session established.")
    return 0


def cmd_devices(args: argparse.Namespace) -> int:
    client = _client(args)
    for d in client.get_devices():
        state = "on " if d.online else "off"
        print(f"[{state}] {d.name}  {d.connection or ''}".rstrip())
    return 0


def cmd_passthrough_get(args: argparse.Namespace) -> int:
    client = _client(args)
    state = client.get_ip_passthrough()
    print(
        json.dumps(
            {
                "enabled": state.enabled,
                "allocation_mode": state.allocation_mode,
                "passthrough_mode": state.passthrough_mode,
                "fixed_mac": state.fixed_mac,
                "manual_entry_supported": state.manual_entry_supported,
            },
            indent=2,
        )
    )
    return 0


def cmd_passthrough_set(args: argparse.Namespace) -> int:
    client = _client(args)
    payload = client.set_ip_passthrough(
        mac=args.mac,
        enable=not args.disable,
        dry_run=args.dry_run,
        verify=not args.no_verify,
    )
    if args.dry_run:
        print("DRY RUN — would POST:")
        print(json.dumps(payload, indent=2))
    else:
        print("IP Passthrough updated and verified." if not args.no_verify
              else "IP Passthrough POST submitted.")
    return 0


def cmd_reboot(args: argparse.Namespace) -> int:
    client = _client(args)
    if args.dry_run:
        payload = client.reboot(dry_run=True)
        print("DRY RUN — would POST:")
        print(json.dumps(payload, indent=2))
        return 0
    if not args.yes:
        print(
            "Refusing to reboot without --yes. The gateway drops all traffic for "
            "~2-3 minutes.",
            file=sys.stderr,
        )
        return 2
    client.reboot()
    print("Reboot command sent. Gateway will be unreachable for ~2-3 minutes.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="att-gateway", description=__doc__)
    p.add_argument("--host", help="Gateway host (default from env/192.168.1.254)")
    p.add_argument("--access-code", help="Device Access Code (else from env)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Test authentication").set_defaults(func=cmd_login)
    sub.add_parser("devices", help="List devices").set_defaults(func=cmd_devices)

    rb = sub.add_parser("reboot", help="Restart the gateway")
    rb.add_argument("--yes", action="store_true", help="Confirm the reboot")
    rb.add_argument("--dry-run", action="store_true", help="Print POST without sending")
    rb.set_defaults(func=cmd_reboot)

    pt = sub.add_parser("ip-passthrough", help="Read or set IP Passthrough")
    pt_sub = pt.add_subparsers(dest="pt_command", required=True)
    pt_sub.add_parser("get", help="Show current state").set_defaults(
        func=cmd_passthrough_get
    )
    pset = pt_sub.add_parser("set", help="Enable/disable and bind a MAC")
    pset.add_argument("--mac", required=True, help="Router WAN MAC to bind")
    pset.add_argument("--disable", action="store_true", help="Turn passthrough off")
    pset.add_argument(
        "--dry-run", action="store_true", help="Print the POST without sending"
    )
    pset.add_argument(
        "--no-verify", action="store_true", help="Skip read-back verification"
    )
    pset.set_defaults(func=cmd_passthrough_set)
    return p


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except GatewayError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
