# Install And Deploy Prompt

Use this single prompt with Codex CLI, Claude Code CLI, or any other MCP-capable coding CLI.

```text
Task: deploy and verify D:\task\soildworks-mcp as a real SolidWorks MCP server on this Windows machine.

Before making changes or running install commands, ask me these deployment choices in one short message:
1. Where should this be deployed from?
   Examples: keep using D:\task\soildworks-mcp, clone to another path, or install from an existing checkout.
2. Which coding client should be registered for MCP use?
   Examples: Codex CLI, Claude Code CLI, or another MCP-capable client.
3. Which Python interpreter or virtual environment should be used for the final MCP server command?

After I answer, execute the deployment end to end.

Execution requirements:
1. Read the repository README first, then follow the repository layout instead of inventing a different structure.
2. Perform the real installation, not just analysis.
3. Install Python dependencies for the repository.
4. Build bridge\SolidWorksBridge.csproj. If SolidWorks is not in a default location, detect it or pass SolidWorksInstallDir explicitly.
5. Verify that at least one of these launch paths works:
   - python .\server.py
   - python -m solidworks_mcp
6. Register the server as a stdio MCP server in the chosen coding client.
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
- deployment path actually used
- coding client actually registered
- final stdio command configured for MCP
- commands actually run
- files changed
- MCP tools actually called
- test results
- saved file path
- remaining limitations or host-specific risks
```
