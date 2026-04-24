<div align="right">

[English](README.md) | [中文](README.zh-CN.md)

</div>

# soildworks-mcp

`soildworks-mcp` is a Windows-first MCP server for SolidWorks. It exposes a local SolidWorks COM automation workflow to Codex or any other MCP client through a Python stdio server plus a C# bridge.

This repository is structured for direct local build, editable install, MCP registration, and real host-side verification.

## What Works

The following capabilities are implemented and verified in the current codebase:

- launch or attach to SolidWorks
- inspect SolidWorks process and active document state
- create a new part
- open and save `.SLDPRT` files
- start a sketch on a base plane
- create center rectangles and circles
- create boss extrusions
- create cut extrusions
- build a rectangular block from dimensions
- build a drilled plate from dimensions
- inspect bodies and feature history of the active part
- apply fillets to the edges owned by a feature
- apply chamfers to the edges owned by a feature
- run a one-sentence showcase workflow through `design_from_prompt`
- run a one-call feature validation workflow through `create_feature_showcase_part`

## Current Limitation

`combine_all_bodies` is exposed and diagnosed, but it is not currently stable on this host. The server reports that state explicitly instead of pretending the operation succeeded.

Current combine result on the verified machine:

- `combineSupported: false`
- `combineStatus.reason: combine_insert_failed`

The rest of the showcase workflow remains usable and returns structured validation for boss, cut, fillet, and chamfer.

## Repository Layout

```text
soildworks-mcp/
|- bridge/
|  |- Program.cs
|  |- SolidWorksBridge.csproj
|- examples/
|  |- codex-config.toml
|  |- install-deploy-prompt.md
|  |- install-deploy-prompt.zh-CN.md
|- scripts/
|  |- bootstrap.ps1
|  |- build_bridge.ps1
|  |- smoke_test.py
|- src/
|  |- solidworks_mcp/
|     |- __init__.py
|     |- __main__.py
|     |- server.py
|- tests/
|- server.py
|- pyproject.toml
|- requirements.txt
|- README.md
`- README.zh-CN.md
```

## Requirements

- Windows
- Python 3.11 or newer
- .NET SDK 8 or newer
- SolidWorks installed locally
- access to `SolidWorks.Interop.sldworks.dll`
- access to `SolidWorks.Interop.swconst.dll`

## Quick Deploy

If you want Codex CLI, Claude Code CLI, or another MCP-capable coding CLI to deploy this repository for you, use this single prompt:

- [examples/install-deploy-prompt.md](examples/install-deploy-prompt.md)
- [中文版本 / Chinese version](examples/install-deploy-prompt.zh-CN.md)

That prompt is written to:

- work across MCP-capable coding CLIs instead of one specific client
- ask the user where the deployment and MCP registration should go before making changes
- perform a real install, real bridge build, real MCP registration, and real SolidWorks verification
- report unsupported host behavior honestly instead of pretending deployment is complete

## Installation

### 1. Clone the repository

```powershell
git clone https://github.com/Xuan-BOMS/soildworks-mcp.git
cd soildworks-mcp
```

### 2. Install Python dependencies

Recommended:

```powershell
python -m pip install -e .
```

Fallback:

```powershell
python -m pip install -r requirements.txt
```

### 3. Build the SolidWorks bridge

If SolidWorks is installed in a default location:

```powershell
.\scripts\build_bridge.ps1
```

If SolidWorks is installed elsewhere:

```powershell
.\scripts\build_bridge.ps1 -SolidWorksInstallDir "<path-to-solidworks-install-dir>"
```

### 4. One-step bootstrap

If you want editable install plus bridge build in one step:

```powershell
.\scripts\bootstrap.ps1 -Python "<path-to-python>" -SolidWorksInstallDir "<path-to-solidworks-install-dir>"
```

### 5. Start the MCP server

Either of these is valid:

```powershell
python .\server.py
```

```powershell
python -m solidworks_mcp
```

## MCP Client Registration

After installation, register the server as a stdio MCP server in your coding client.

Example:

```toml
[mcp_servers.solidworks]
type = "stdio"
command = "python"
args = ["-m", "solidworks_mcp"]
```

If you prefer a direct repository path instead of module execution:

```toml
[mcp_servers.solidworks]
type = "stdio"
command = "<path-to-python>"
args = ["<path-to-repo>/server.py"]
```

The exact config file location depends on the client. The same stdio command and args can be adapted for Codex CLI, Claude Code CLI, and other MCP-capable tools.

## Optional Environment Variables

- `SOLIDWORKS_MCP_BRIDGE_DLL`
  Override the default bridge DLL path.
- `SOLIDWORKS_MCP_TEMPLATE`
  Override the default SolidWorks part template.

Example:

```powershell
$env:SOLIDWORKS_MCP_TEMPLATE = "C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2023\templates\gb_part.prtdot"
python -m solidworks_mcp
```

## Smoke Test

Start with:

```powershell
python .\scripts\smoke_test.py
```

Then run real workflow tests as needed:

```powershell
python .\tests\tests_required_tools.py
python .\tests\tests_rectangular_block_workflow.py
python .\tests\tests_plate_with_holes_workflow.py
python .\tests\tests_design_from_prompt_workflow.py
python .\tests\tests_cut_and_inspect_workflow.py
python .\tests\tests_feature_showcase_workflow.py
python .\tests\tests_showcase_prompt_workflow.py
```

## High-Level Tool Summary

Stable tools:

- `launch_solidworks`
- `close_solidworks`
- `solidworks_status`
- `active_document`
- `open_document`
- `save_active_document`
- `new_part`
- `create_sketch_on_plane`
- `create_center_rectangle`
- `create_circle`
- `extrude_boss`
- `extrude_cut`
- `inspect_active_part`
- `apply_fillet_to_feature_edges`
- `apply_chamfer_to_feature_edges`
- `create_rectangular_block`
- `create_plate_with_holes`
- `create_feature_showcase_part`
- `design_from_prompt`

Guarded or limited tools:

- `combine_all_bodies`
  Exposed, but currently reports unsupported/failed state on the verified machine.
- `run_macro`
  Intentionally disabled because VSTA macro loading can crash SolidWorks on this host.
- `add_dimension`
  Not enabled as a stable production path.

## Verified Behavior In This Codebase

The synchronized code in this repository has already been updated to include:

- cut extrusion support in the bridge
- active part inspection with feature and body summaries
- fillet and chamfer feature-edge workflows
- showcase validation workflow
- explicit reporting for unsupported combine behavior
- prompt-based one-sentence showcase generation

## Upstream Reference

- Upstream reference: [eyfel/mcp-server-solidworks](https://github.com/eyfel/mcp-server-solidworks)
- License: MIT
- Additional packaging and host-stability work in this repository: `Xuan_Boms`
