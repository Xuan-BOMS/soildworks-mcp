<div align="right">

[English](README.md) | [中文](README.zh-CN.md)

</div>

# soildworks-mcp

`soildworks-mcp` 是一个面向 Windows 的 SolidWorks MCP 服务器。它通过 Python stdio server 加 C# bridge 的方式，把本机的 SolidWorks COM 自动化能力暴露给 Codex、Claude Code 或其他支持 MCP 的客户端。

这个仓库已经整理成适合本地直接构建、可编辑安装、MCP 注册和真实主机验证的结构。

## 已可用能力

当前代码库中已经实现并验证的能力包括：

- 启动或附着到 SolidWorks
- 检查 SolidWorks 进程和当前活动文档状态
- 新建零件
- 打开和保存 `.SLDPRT` 文件
- 在基准面上开始草图
- 创建中心矩形和圆
- 创建凸台拉伸
- 创建切除拉伸
- 根据尺寸生成矩形块
- 根据尺寸生成带孔板件
- 检查活动零件的实体和特征历史
- 对指定特征边应用圆角
- 对指定特征边应用倒角
- 通过 `design_from_prompt` 执行一句话 showcase 工作流
- 通过 `create_feature_showcase_part` 执行一次调用的特征验证工作流

## 当前限制

`combine_all_bodies` 已暴露并带诊断返回，但在当前验证主机上还不稳定。服务器会明确报告这个状态，而不是伪装成成功。

当前主机上的组合体结果：

- `combineSupported: false`
- `combineStatus.reason: combine_insert_failed`

除了组合体之外，showcase 工作流仍然可用，并且会返回凸台、切除、圆角、倒角的结构化验证结果。

## 仓库结构

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

## 环境要求

- Windows
- Python 3.11 或更高版本
- .NET SDK 8 或更高版本
- 本机已安装 SolidWorks
- 可访问 `SolidWorks.Interop.sldworks.dll`
- 可访问 `SolidWorks.Interop.swconst.dll`

## 快速部署

如果你想让 Codex CLI、Claude Code CLI 或其他支持 MCP 的编码 CLI 帮你完成部署，请直接使用这一份完整提示词：

- [examples/install-deploy-prompt.zh-CN.md](examples/install-deploy-prompt.zh-CN.md)

这份提示词的目标是：

- 适用于多种支持 MCP 的编码 CLI，而不是只限定单一客户端
- 在真正改动系统前，先询问用户要部署到哪里、注册到哪个客户端
- 执行真实安装、真实 bridge 构建、真实 MCP 注册、真实 SolidWorks 验证
- 如果主机上存在不支持或不稳定能力，明确报告，不伪装成部署完成

## 传统安装方法

### 1. 克隆仓库

```powershell
git clone https://github.com/Xuan-BOMS/soildworks-mcp.git
cd soildworks-mcp
```

### 2. 安装 Python 依赖

推荐：

```powershell
python -m pip install -e .
```

兜底方式：

```powershell
python -m pip install -r requirements.txt
```

### 3. 构建 SolidWorks bridge

如果 SolidWorks 安装在默认位置：

```powershell
.\scripts\build_bridge.ps1
```

如果 SolidWorks 安装在其他位置：

```powershell
.\scripts\build_bridge.ps1 -SolidWorksInstallDir "D:\Program Files\SOLIDWORKS Corp\SOLIDWORKS"
```

### 4. 一步式 bootstrap

如果你想一次完成可编辑安装和 bridge 构建：

```powershell
.\scripts\bootstrap.ps1 -Python "C:\Python312\python.exe" -SolidWorksInstallDir "D:\Program Files\SOLIDWORKS Corp\SOLIDWORKS"
```

### 5. 启动 MCP server

以下任一方式都可以：

```powershell
python .\server.py
```

```powershell
python -m solidworks_mcp
```

## MCP 客户端注册

安装完成后，把这个 server 注册成你所使用客户端里的 stdio MCP server。

示例：

```toml
[mcp_servers.solidworks]
type = "stdio"
command = "C:/Python312/python.exe"
args = ["-m", "solidworks_mcp"]
```

如果你更喜欢直接从仓库路径启动，而不是用模块方式：

```toml
[mcp_servers.solidworks]
type = "stdio"
command = "C:/Python312/python.exe"
args = ["D:/task/soildworks-mcp/server.py"]
```

具体配置文件路径取决于客户端本身，但这套 `stdio + command + args` 模式可以迁移到 Codex CLI、Claude Code CLI 以及其他支持 MCP 的工具中。

## 可选环境变量

- `SOLIDWORKS_MCP_BRIDGE_DLL`
  覆盖默认 bridge DLL 路径。
- `SOLIDWORKS_MCP_TEMPLATE`
  覆盖默认 SolidWorks 零件模板路径。

示例：

```powershell
$env:SOLIDWORKS_MCP_TEMPLATE = "C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2023\templates\gb_part.prtdot"
python -m solidworks_mcp
```

## 冒烟测试

先运行：

```powershell
python .\scripts\smoke_test.py
```

然后根据需要运行真实工作流测试：

```powershell
python .\tests\tests_required_tools.py
python .\tests\tests_rectangular_block_workflow.py
python .\tests\tests_plate_with_holes_workflow.py
python .\tests\tests_design_from_prompt_workflow.py
python .\tests\tests_cut_and_inspect_workflow.py
python .\tests\tests_feature_showcase_workflow.py
python .\tests\tests_showcase_prompt_workflow.py
```

## 高层工具摘要

当前稳定工具：

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

受限或保护性工具：

- `combine_all_bodies`
  已暴露，但在当前验证主机上仍会报告 unsupported/failed 状态。
- `run_macro`
  出于宿主稳定性考虑被明确禁用，因为 VSTA macro 加载可能导致 SolidWorks 崩溃。
- `add_dimension`
  目前还没有开放为稳定生产能力。

## 当前代码库已同步的改动

当前仓库中已经同步并验证的更新包括：

- bridge 层支持切除拉伸
- 活动零件检查支持特征和实体摘要
- 圆角和倒角的特征边工作流
- showcase 验证工作流
- 对不支持的组合体行为做显式报告
- 基于自然语言的一句话 showcase 生成

## 上游参考

- 上游参考: [eyfel/mcp-server-solidworks](https://github.com/eyfel/mcp-server-solidworks)
- License: MIT
- 本仓库中的额外封装与宿主稳定性处理: `Xuan_Boms`
