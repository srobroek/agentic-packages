# Tauri MCP: WSL ↔ Windows connectivity

This matters when the coding agent (and therefore the Tauri MCP server) runs
**inside WSL2** while the Tauri dev app runs on the **Windows host** — a common
setup. If the app runs inside the same WSL instance as the agent, none of this
applies: the default `localhost:9223` just works.

## The problem

The MCP server connects to `localhost:9223` by default. In WSL2's default NAT
networking, WSL `localhost` is **not** the Windows host, so the bridge running
inside the Windows app is unreachable and the connection fails.

## Preferred fix — mirrored networking

On Windows 11 22H2+ with WSL ≥ 2.0, enable mirrored networking so loopback is
shared between Windows and WSL. In `%UserProfile%\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
```

Then run `wsl --shutdown` and restart WSL. The default `host=localhost` now
reaches the Windows app with no further configuration.

## Fallback — NAT mode

If mirrored networking is unavailable, point the client at the Windows host IP,
which from WSL is the default gateway:

```bash
ip route show default | awk '{print $3}'
```

Set that value as `MCP_BRIDGE_HOST` (or pass it as the `host` parameter to
`driver_session`). The bridge already binds `0.0.0.0`, so it accepts the
connection — **but** Windows Defender Firewall must allow inbound TCP **9223** on
the WSL / vEthernet network. Without an inbound rule the connection is silently
dropped.

## Troubleshooting checklist

- Is the Tauri dev app actually running?
- Is `tauri-plugin-mcp-bridge` present in this (dev) build?
- Is the gateway IP correct (`ip route show default`)?
- Is there a Windows Firewall inbound rule for TCP 9223?
- Is `MCP_BRIDGE_HOST` exported in the agent's environment (NAT mode), or is
  mirrored networking enabled?
