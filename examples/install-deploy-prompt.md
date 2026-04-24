# Install And Deploy Prompt

Use this prompt as-is with Codex or another coding agent if you want real installation and verification rather than a plan-only answer.

```text
Task: deploy and verify D:\task\soildworks-mcp on this Windows machine as a real SolidWorks MCP server.

Execution requirements:
1. Read D:\task\soildworks-mcp\README.md first, then follow that repository layout and deployment flow.
2. Perform the real installation, not just analysis.
3. Install Python dependencies for the repository.
4. Build bridge\SolidWorksBridge.csproj. If SolidWorks is not in a default location, detect it or pass SolidWorksInstallDir explicitly.
5. Verify that at least one of these launch paths works:
   - python .\server.py
   - python -m solidworks_mcp
6. Register the server for Codex as a stdio MCP server.
7. Run real verification, not mock verification. At minimum validate:
   - ping
   - solidworks_status
   - launch_solidworks
   - create_rectangular_block
   - create_plate_with_holes
   - design_from_prompt
8. Save at least one generated .SLDPRT file and confirm it can be reopened.
9. Report combine_all_bodies honestly. If it is unsupported on the host, do not claim success.
10. If SolidWorks shows unstable .NET or macro-related dialogs, keep troubleshooting toward a usable MCP deployment instead of stopping at symptom description.

Forbidden behavior:
- do not stop after writing a plan
- do not skip the bridge build
- do not claim deployment succeeded without real MCP calls
- do not fabricate test results

Final output must include:
- commands actually run
- files changed
- MCP tools actually called
- test results
- saved file path
- remaining limitations or host-specific risks
```
