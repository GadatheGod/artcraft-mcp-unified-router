ArtCraft Unified MCP Router (Windows)
=====================================
Put all three files in one folder:
  artcraft_unified_launcher_v9.py
  artcraft_unified_router.py
  artcraft_router.json

1. Open artcraft_router.json. Update each app's CLI executable path and MCP arguments based on that app's installed CLI help. Unverified apps are disabled by default.
2. Start the launcher: py artcraft_unified_launcher_v9.py
3. Select installed apps, click Scan installations, then Launch checked GUIs if needed.
4. Click Start tunnel. It generates ONE 'main' MCP channel to the router.
5. In ChatGPT, reconnect/refresh the MCP connection to discover the newly namespaced tools.
6. Ask the agent to call artcraft_status. It shows which child apps connected.

Important:
- The existing tunnel YAML's original prefix and credentials are preserved.
- App CLIs are separate processes; their stdout must contain MCP protocol messages only.
- This router exposes real child tools dynamically, not fabricated command names.
- Apps without verified CLI paths or MCP flags will not connect until configured.
- 'artcraft_refresh' retries apps, but tool lists may require a client reconnect.
- The original launcher may block tunnel startup if a GUI port is missing; deselect that app or start it first.
- Do not place API keys in the JSON config. Use environment variables or existing tunnel credentials.
- The router does not proxy resources/prompts or child-initiated sampling requests.
- This package has passed syntax checks but has not been tested against your Windows installations.