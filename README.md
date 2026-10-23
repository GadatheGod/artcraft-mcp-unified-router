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
