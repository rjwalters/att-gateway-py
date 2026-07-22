# Troubleshooting AT&T gateway + downstream router (UDM-Pro etc.)

Field notes from getting IP Passthrough working on a CGW452 feeding a UniFi
UDM-Pro on WAN2. These are the non-obvious traps, in the order they bite.

## Symptom: downstream WAN gets *no IP at all*

Almost always a **subnet overlap**, not a link problem. The CGW452 LAN is
`192.168.1.0/24` (gateway `192.168.1.254`). If your downstream router's LAN is
*also* `192.168.1.0/24` (the UDM-Pro default), UniFi **refuses the WAN DHCP
lease** because it overlaps a network it already owns → WAN shows "no IP" with
the link up.

**Fix:** renumber the downstream LAN off `192.168.1.0/24` (e.g. `192.168.10.0/24`).
The WAN will immediately pull a lease.

## Symptom: WAN gets a *private* `192.168.1.x` instead of the public IP

You're in **double-NAT** — passthrough isn't matching your router. Check the next
hop: a private gateway (`192.168.1.254`) means a normal LAN lease, not passthrough.

The usual cause is the **passthrough MAC is bound to the wrong address.**

### Use the *WAN device MAC*, not the port-table / connected MAC

This is the subtle one. Several different MACs are visible:

| Where you see it | Example | Is it the right one? |
|---|---|---|
| UniFi **Settings → Internet → WAN2 → MAC Address** | `aa:bb:cc:11:22:33` | ✅ **This is the one to bind** |
| UniFi Ports table / "Connected MAC" | `dd:ee:ff:44:55:66` | ❌ that's the *upstream gateway* |
| UDM device port hardware MAC | `aa:bb:cc:77:88:99` | ❌ not the MAC WAN2 DHCPs with |

Bind IP Passthrough (`passmac`) to the **WAN device MAC** from
Settings → Internet. Confirm it appears in the gateway's seen-MAC list
(`ippassmaclist` on the ippass.ha form) — if it's not there, the gateway has
never received DHCP from it and passthrough can't hand off.

## After changing the passthrough MAC: reboot, then renew

The CGW452 does **not** re-home the public IP to a newly-bound MAC until it
reboots. Sequence:

```bash
att-gateway ip-passthrough set --mac <WAN-device-MAC>   # verifies read-back
att-gateway reboot --yes                                # ~2-3 min; only WAN2 blips
# wait for it to come back, then renew WAN2 on the UDM (Settings → Internet → WAN2)
```

Rebooting the AT&T gateway only affects the link behind it — a *separate* primary
ISP on another WAN port is unaffected.

**Success:** the downstream WAN flips from `192.168.1.x` to a public address and
its next hop is no longer `192.168.1.254`.

## Keep inbound services (Plex, etc.) pinned to the primary WAN

Dual-WAN + an inbound service = asymmetric-routing pain and a moving public IP.
Pin port-forwarded services (Plex `32400`, etc.) to the stable primary WAN via a
UniFi traffic route; let the AT&T link be failover.
