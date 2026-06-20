# Tauri MCP: WSL ↔ Windows connectivity

This matters when the coding agent (and therefore the `tauri-plugin-mcp-server`
MCP server) runs **inside WSL2** while the Tauri dev app runs on the **Windows
host** — a common setup. If the app runs inside the same WSL instance as the
agent, none of this applies: the default `127.0.0.1:9999` just works.

## The problem

The MCP server connects to `127.0.0.1:9999`. In WSL2's default NAT networking,
WSL `localhost` is **not** the Windows host, and the app's plugin binds
`127.0.0.1` (loopback only) — so the socket running inside the Windows app is
unreachable and the connection fails.

## Preferred fix — mirrored networking

On Windows 11 22H2+ with WSL ≥ 2.0, enable mirrored networking so loopback is
shared between Windows and WSL. In `%UserProfile%\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
```

Then run `wsl --shutdown` and restart WSL. The app keeps its secure
`.tcp_localhost(9999)` bind, and the MCP server's default
`TAURI_MCP_TCP_HOST=127.0.0.1` now reaches the Windows app with no further
configuration and no auth token.

## Fallback — NAT mode (no mirrored networking)

If mirrored networking is unavailable, loopback is not shared, so two changes are
required:

1. **App side** — bind a non-loopback address and set an auth token (the plugin
   refuses a non-loopback bind without one):

   ```rust
   tauri_plugin_mcp::PluginConfig::new("my-app".to_string())
       .start_socket_server(true)
       .tcp("0.0.0.0".to_string(), 9999)
       .auth_token("dev-token".to_string())
   ```

2. **Server side** — point the MCP server at the Windows host IP (the WSL default
   gateway) and the same token:

   ```bash
   ip route show default | awk '{print $3}'   # e.g. 172.23.112.1
   ```

   ```json
   "env": {
     "TAURI_MCP_CONNECTION_TYPE": "tcp",
     "TAURI_MCP_TCP_HOST": "172.23.112.1",
     "TAURI_MCP_TCP_PORT": "9999",
     "TAURI_MCP_AUTH_TOKEN": "dev-token"
   }
   ```

The gateway IP can change across reboots, and binding `0.0.0.0` exposes the
dev-only control socket on the local network (token-gated) — prefer mirrored
networking for day-to-day use.

## Troubleshooting checklist

- Is the Tauri dev app actually running, and is `tauri-plugin-mcp` present in this
  (dev) build? On Windows, confirm the listener:
  `Get-NetTCPConnection -LocalPort 9999 -State Listen`.
- Mirrored mode: is `networkingMode=mirrored` set and was `wsl --shutdown` run?
- NAT mode: did you bind `0.0.0.0` + auth token, use the gateway IP, and set
  `TAURI_MCP_AUTH_TOKEN` on both sides? Windows Defender Firewall must allow
  inbound TCP 9999 on the WSL / vEthernet network.
- Quick reachability probe from WSL: `nc -vz <host> 9999`.
