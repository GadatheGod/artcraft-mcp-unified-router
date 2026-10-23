# ArtCraft MCP Unified Router

A community project for running multiple **ArtCraft** desktop applications behind a single **Model Context Protocol (MCP)** gateway, with a Windows launcher and dynamic tool discovery.

> This is a community integration, not an official ArtCraft or OpenAI release. You must install the applications and configure your own credentials and paths.

## Architecture

```text
ChatGPT / OpenCode / other MCP client
                 |
         MCP tools/list, tools/call
                 |
      Remote tunnel (optional)
                 |
        Unified ArtCraft Router
         /         |         \
   GridCraft   SolidCraft   DeckCraft / other apps
         \         |         /
          Local application APIs
```

**Application API:** the underlying command engine that actually edits a workbook, model, or presentation.

**MCP server:** a wrapper that advertises callable operations as tools with JSON input schemas. MCP clients discover these with `tools/list` and invoke them with `tools/call`.

**Unified router:** discovers each selected application's MCP tools, aggregates the catalog, and forwards calls to the appropriate application.

**Tunnel:** provides transport from a remote MCP client/control plane to your local router. A tunnel does not generate tools or replace the application API.

**ChatGPT plugin/connection:** makes permitted tools visible to ChatGPT. The client may cache the tool catalog; reconnect after updates if new tools do not appear.

## Requirements

- Windows 10/11 and Python 3.10 or later.
- ArtCraft application(s) and their matching CLI/MCP servers installed locally.
- For local use, an MCP-capable client.
- For remote ChatGPT use, a compatible ChatGPT connection, tunnel client, authorized tunnel ID, and control-plane API credential. Availability depends on your ChatGPT/workspace setup.

## Quick start

1. Clone the repository or download the ZIP.
2. Configure the paths for installed ArtCraft applications in `artcraft_unified_launcher_v9.py` and `artcraft_router.json`.
3. Disable applications not installed on your computer.
4. Start the Windows launcher:

   ```powershell
   python artcraft_unified_launcher_v9.py
   ```

5. Start the selected application GUIs and their MCP endpoints.
6. Verify that each application's MCP server is reachable.
7. Start the unified router or tunnel using your local configuration.
8. Confirm the tool catalog through the router's status, catalog, and refresh functions.
9. Connect an MCP-compatible client and test a read-only command before allowing modifications.

## Download the official OpenAI Secure MCP Tunnel client

- **[Download the latest tunnel-client release (Windows, macOS, Linux)](https://github.com/openai/tunnel-client/releases/latest)**
- [OpenAI tunnel-client source code](https://github.com/openai/tunnel-client)
- [Official Secure MCP Tunnel setup guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [OpenAI Platform tunnel management](https://platform.openai.com/settings/organization/tunnels)

On Windows, open the latest release, download the appropriate `windows-amd64` ZIP for most Intel/AMD PCs, extract it, and locate `tunnel-client.exe`. In PowerShell run ` .\\tunnel-client.exe help quickstart ` for supported setup instructions. Create your own tunnel ID and credentials in OpenAI Platform; never reuse another person's values.

### Generate your own OpenAI API key

1. Sign in to the **[OpenAI API Keys page](https://platform.openai.com/api-keys)**.
2. Select the appropriate project and choose **Create new secret key**.
3. Copy the key securely when it is displayed. Never commit it to this repository.
4. For a local PowerShell session, set `$env:CONTROL_PLANE_API_KEY = "YOUR_OWN_KEY"` only if your tunnel setup specifically requires an OpenAI API key for that variable.

**Important:** OpenAI API keys and ChatGPT subscriptions are separate. A standard OpenAI API key may not be sufficient to authenticate a particular tunnel/control-plane deployment; use the credential required by your tunnel setup.

## OpenAI tunnel and API setup (optional)

A ChatGPT subscription is **not** an OpenAI API key. Obtain tunnel credentials through the supported control-plane onboarding process; do not commit secrets to GitHub.

Example control-plane configuration fragment (adapt to the installed tunnel-client version and its documented YAML format):

```yaml
config_version: 1
control_plane:
  base_url: "https://api.openai.com"
  tunnel_id: "REPLACE_WITH_YOUR_OWN_TUNNEL_ID"
  api_key: "env:CONTROL_PLANE_API_KEY"
```

In PowerShell:

```powershell
$env:CONTROL_PLANE_API_KEY = "YOUR_OWN_API_KEY"
.\tunnel-client.exe run --profile YOUR_PROFILE
```

This fragment is **not a complete tunnel profile**. Configure its MCP backend to launch or connect to the unified router, not an individual app, when aggregation is desired. Use the official tunnel-client documentation for its exact transport and backend fields. Do not expose unauthenticated local ports publicly.

## Connect ChatGPT Web, OpenCode, Claude Desktop, and Claude Web

**One ArtCraft command engine, different MCP transports.** Each Craft app still needs its own installed GUI and compatible local MCP/control-mode interface. The unified router aggregates these interfaces; the AI client chooses how to reach the router.

| Client | Connection path | OpenAI tunnel? | Status |
| --- | --- | --- | --- |
| **ChatGPT Web** | ChatGPT → OpenAI Secure MCP Tunnel → local unified router → Craft app MCP/control mode | **Yes**, for this project's current ChatGPT Web arrangement | GridCraft end-to-end flow **reported tested by project owner** |
| **OpenCode (running on same Windows PC)** | OpenCode → local stdio MCP router → Craft app MCP/control mode | **No** | Example configuration; verify locally |
| **Claude Desktop** | Claude Desktop → local stdio MCP router → Craft app MCP/control mode | **No** | Example configuration; verify locally |
| **Claude Web (claude.ai)** | Claude Web → authenticated public HTTPS MCP endpoint → HTTP-to-MCP bridge/router → Craft app MCP/control mode | **No OpenAI tunnel**; requires secure remote access | **Not implemented or verified** in this repository |

### ChatGPT Web: OpenAI Secure MCP Tunnel

```text
ChatGPT Web
  → OpenAI Secure MCP Tunnel (authorized tunnel ID / credentials)
  → ArtCraft Unified MCP Router (local Windows PC)
  → selected GridCraft / SolidCraft / DeckCraft MCP server
  → Craft GUI launched in control mode
```

Install the [official OpenAI tunnel-client](https://github.com/openai/tunnel-client/releases/latest), configure a valid control-plane profile and its MCP backend according to the [official documentation](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels), and connect through a supported ChatGPT MCP integration. **The tunnel is transport, not the unified router or an application MCP server.** Installing the tunnel alone does not launch Craft applications or configure their paths.

### OpenCode on Windows: direct local MCP, no tunnel

Configure the **local** MCP server in `opencode.json` (merge with existing settings):

```json
{
  "mcp": {
    "artcraft": {
      "type": "local",
      "command": [
        "python",
        "C:\\ArtCraft\\artcraft_unified_router.py",
        "--config",
        "C:\\ArtCraft\\artcraft_router.json"
      ],
      "enabled": true
    }
  }
}
```

Replace `C:\ArtCraft` with your installation directory. OpenCode launches the stdio router locally; the router dispatches to the configured app MCP servers. See [OpenCode MCP documentation](https://opencode.ai/docs/mcp-servers/) for the supported configuration schema in your installed version. **No OpenAI tunnel or public IP is needed.**

### Claude Desktop: direct local MCP, no tunnel

Add a local stdio server to `%APPDATA%\Claude\claude_desktop_config.json` (merge into existing `mcpServers`):

```json
{
  "mcpServers": {
    "artcraft": {
      "command": "python",
      "args": [
        "C:\\ArtCraft\\artcraft_unified_router.py",
        "--config",
        "C:\\ArtCraft\\artcraft_router.json"
      ]
    }
  }
}
```

Restart Claude Desktop after changing the file. This is **Claude Desktop**, not Claude in a browser.

### Claude Web: secure remote HTTP MCP endpoint required

```text
Claude Web (claude.ai)
  → HTTPS remote MCP endpoint with appropriate authentication
  → HTTP MCP bridge / Streamable HTTP server on your Windows PC
  → ArtCraft Unified MCP Router
  → Craft app MCP server → Craft GUI in control mode
```

Claude Web cannot directly start a Windows stdio command on your PC. A third-party network tunnel (for example, Cloudflare Tunnel) can provide HTTPS reachability, **but a tunnel by itself does not convert stdio MCP to HTTP MCP**. You must also run a compatible HTTP MCP server/bridge supporting the transport accepted by Claude's custom connectors, and secure it with authentication and access controls. Then add the remote connector in [Claude's connector settings](https://claude.ai/settings/connectors), subject to plan and workspace availability.

**Current repository limitation:** This project currently provides a stdio router. It does **not** include a tested Claude Web HTTP bridge, Cloudflare Tunnel configuration, or authentication implementation. Do not publish an unauthenticated MCP endpoint to the internet.

### Recommended cross-client architecture

```text
                  ┌─ ChatGPT Web ─ OpenAI Secure MCP Tunnel ─┐
ArtCraft Router ←─┼─ OpenCode / Claude Desktop ─ local stdio ┤
                  └─ Claude Web ─ HTTPS + authenticated HTTP bridge ┘
                           |
                  app MCP servers / GUI control mode
```

The diagram shows **alternative frontends into one router**, not a requirement to run all connections at once. Keep Craft-specific commands and discovery in the shared router; add transport adapters separately. After application updates, refresh tool discovery and reconnect a client if its tool catalog remains cached.

## Dynamic discovery when applications update

1. Install the updated application and matching MCP server.
2. Restart that server if required.
3. Refresh the unified router's MCP tool catalog.
4. Verify the new tool in `tools/list`.
5. Reconnect ChatGPT or your MCP client if its list remains stale.

A stable `execute_command` MCP tool can often invoke newly added ribbon/menu commands by command ID, even when no new top-level MCP tool was added. **Automatic refresh is not guaranteed** by every client.

## Testing

Run from the project root:

```powershell
python -m unittest discover -p "test_router_v*.py"
```

Passing unit tests does not verify that an actual GUI, tunnel, or ChatGPT integration is functioning.

## Security

- Replace example paths, ports, and tunnel identifiers with your own.
- Keep local MCP and GUI control endpoints on `127.0.0.1` where possible.
- Never commit tokens, API keys, machine-specific generated YAML, logs, or personal file paths.
- Restrict write/destructive MCP tools to trusted users.
- Revoke any accidentally exposed credential immediately.

## Repository files

- `artcraft_unified_router.py`: unified MCP tool aggregation and dispatch.
- `artcraft_unified_launcher_v9.py`: Windows launcher.
- `artcraft_router.json`: configurable application registry.
- `test_router_v10.py`, `test_router_v11.py`: unit tests.
- `.gitignore`, `LICENSE`: project hygiene and licensing.

## License

MIT — see [LICENSE](LICENSE).

Contributions, bug reports, and compatibility updates are welcome.
