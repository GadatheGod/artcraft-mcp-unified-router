# Restored ArtCraft V11 implementation

This package restores the original `artcraft_unified_launcher_v9.py`, `artcraft_unified_router.py`, `artcraft_router.json`, and both test suites from the user's `artcraft_unified_mcp_v11_fixed(1).zip` archive. It is NOT the simplified launcher published to GitHub.

## Original GUI features retained
- Select 14 Craft apps, status display, and installation scan.
- **Launch checked GUIs** in `--control` mode for apps with configured control ports.
- **Check ports**, optional auto-launch when starting tunnel.
- Tunnel executable and source YAML browsing, dashboard port selection.
- Generate selected-app YAML and configure the router's enabled apps.
- Start/stop tunnel, dashboard open, health polling.
- Show generated YAML, save/clear logs, verbosity filtering.
- Check whether an API key environment variable is set without printing the value.

## Important notes
- The launcher is named `v9` for historical compatibility but is the file included in the V11 ZIP.
- It only stops the tunnel it launches, not all Craft GUIs.
- Verify CLI paths, ports, YAML compatibility, and tunnel arguments on the actual Windows PC.
- Never publish generated YAML, environment variables, API keys, tokens, or local logs.
- The bundled paths and app CLI arguments are defaults and may require local adjustment.
- Tested here: Python syntax compilation and 5 router unit tests; live Windows GUI and tunnel integration cannot be tested in this environment.