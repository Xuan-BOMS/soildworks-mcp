# soildworks-mcp

`soildworks-mcp` 是一个面向 Windows + SolidWorks 的 MCP 服务器封装仓库，用来把 SolidWorks 的本地 COM 自动化能力暴露给 Codex / 其他支持 MCP 的客户端。

这个仓库参考并延展了 [eyfel/mcp-server-solidworks](https://github.com/eyfel/mcp-server-solidworks)，但目标不是保留原始散装实验形态，而是提供一个更适合本地直接导入、构建、部署和二次修改的仓库结构。

## 项目定位

- 面向本机安装了 SolidWorks 的 Windows 工作站
- 通过 Python 提供 MCP stdio server
- 通过 C# bridge 执行 SolidWorks COM API 调用
- 优先保证 Codex 本地可部署、可测试、可保存文件
- 针对部分宿主机上的 SolidWorks `.NET Framework` 弹窗，内置了保守的窗口抑制策略

## 当前已验证能力

已在本机真实验证：

- 冷启动 SolidWorks
- 新建零件
- 在基准面建草图
- 画中心矩形
- 画圆
- 拉伸凸台
- 生成矩形块
- 生成带 4 孔的板式支架
- 保存当前零件到指定路径
- 重新打开已保存的 `.SLDPRT`

当前高层工具包括：

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
- `create_rectangular_block`
- `create_plate_with_holes`
- `design_from_prompt`

## 已知限制

- `run_macro` 目前默认禁用。
  原因：在当前宿主机上，VSTA / 宏加载链路可能触发 `.NET Framework` 弹窗并导致 SolidWorks 退出。
- `add_dimension` 仍保持保守模式，没有开放高风险实现。
- `design_from_prompt` 目前是窄域自然语言解析，不是通用 CAD Agent。
- `M3` 当前按 `3 mm` 几何孔处理，不是 Hole Wizard 螺纹特征。

## 仓库结构

```text
soildworks-mcp/
├─ bridge/
│  ├─ Program.cs
│  └─ SolidWorksBridge.csproj
├─ scripts/
│  ├─ bootstrap.ps1
│  ├─ build_bridge.ps1
│  └─ smoke_test.py
├─ src/
│  └─ solidworks_mcp/
│     ├─ __init__.py
│     ├─ __main__.py
│     └─ server.py
├─ tests/
├─ server.py
├─ pyproject.toml
├─ requirements.txt
└─ README.md
```

## 环境要求

- Windows
- Python 3.11+
- .NET SDK 8 或 9
- 已安装 SolidWorks
- 可访问 `SolidWorks.Interop.sldworks.dll` 和 `SolidWorks.Interop.swconst.dll`

## 快速部署

### 1. 克隆仓库

```powershell
git clone https://github.com/Xuan-BOMS/soildworks-mcp.git
cd soildworks-mcp
```

### 2. 安装 Python 依赖

推荐直接可编辑安装：

```powershell
python -m pip install -e .
```

或者：

```powershell
python -m pip install -r requirements.txt
```

### 3. 构建 C# Bridge

如果 SolidWorks 默认安装在 `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS` 或 `D:\Program Files\SOLIDWORKS Corp\SOLIDWORKS`，可以直接：

```powershell
.\scripts\build_bridge.ps1
```

如果你的安装路径不同：

```powershell
.\scripts\build_bridge.ps1 -SolidWorksInstallDir "D:\Program Files\SOLIDWORKS Corp\SOLIDWORKS"
```

也可以一步完成 Python 安装 + Bridge 构建：

```powershell
.\scripts\bootstrap.ps1 -Python "C:\Python312\python.exe" -SolidWorksInstallDir "D:\Program Files\SOLIDWORKS Corp\SOLIDWORKS"
```

### 4. 启动 MCP Server

```powershell
python .\server.py
```

或者：

```powershell
python -m solidworks_mcp
```

## 在 Codex 中接入

把下面配置加入 `~/.codex/config.toml`：

```toml
[mcp_servers.solidworks]
type = "stdio"
command = "C:/Python312/python.exe"
args = ["D:/task/soildworks-mcp/server.py"]
```

如果你用的是虚拟环境 Python，把 `command` 改成虚拟环境里的 `python.exe`。

## 提示词部署

如果你想把这个仓库直接交给 Codex、ChatGPT Codex 或其他本地代码助手去自动部署，可以把下面这段提示词直接发给它：

```text
请在当前 Windows 机器上部署 D:\task\soildworks-mcp 这个 SolidWorks MCP 仓库，并完成真实测试。

要求：
1. 使用仓库 README 中描述的标准方式部署，不要自行发明另一套目录结构。
2. 安装 Python 依赖，确保 `python -m solidworks_mcp` 或 `python server.py` 可以启动。
3. 构建 bridge\SolidWorksBridge.csproj；如果 SolidWorks 安装路径不是默认路径，请自动识别或在构建参数里传入 `SolidWorksInstallDir`。
4. 在 Codex 配置中按 stdio MCP 方式接入这个 server。
5. 做真实冒烟测试，至少验证：
   - `launch_solidworks`
   - `solidworks_status`
   - `create_rectangular_block`
   - `save_active_document`
6. 如果宿主机出现 SolidWorks 的 .NET Framework 弹窗，不要只汇报现象，要继续排查并尽量修到“可用”状态。
7. 最终输出：
   - 实际修改过的文件
   - 部署命令
   - 测试结果
   - 如果还有限制，明确列出。

补充约束：
- 必须真的在本机执行命令和测试，不要只给理论步骤。
- 不要跳过 bridge 构建。
- 不要假设保存成功，必须验证生成文件存在且可重新打开。
```

如果你希望助手直接生成一个“四孔支架并保存到桌面”，可以用更具体的版本：

```text
请部署并测试 D:\task\soildworks-mcp，然后通过 MCP 在 SolidWorks 中创建一个带 4 个 M3 孔的支架，长宽 20 cm，厚度 5 mm，孔距边 5 mm，并把生成的 SLDPRT 文件保存到桌面。完成后给出保存路径和测试结果。
```

## 可选环境变量

- `SOLIDWORKS_MCP_BRIDGE_DLL`
  覆盖 bridge DLL 路径
- `SOLIDWORKS_MCP_TEMPLATE`
  覆盖默认零件模板路径

示例：

```powershell
$env:SOLIDWORKS_MCP_TEMPLATE = "C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2023\templates\gb_part.prtdot"
python .\server.py
```

## 冒烟测试

先确认 SolidWorks 可以在本机正常启动，然后运行：

```powershell
python .\scripts\smoke_test.py
```

如果要执行高层建模测试，可以直接运行：

```powershell
python .\tests\tests_rectangular_block_workflow.py
python .\tests\tests_plate_with_holes_workflow.py
python .\tests\tests_design_from_prompt_workflow.py
```

## 本机验证记录

在当前开发机上，已经真实验证：

- `create_plate_with_holes` 成功生成 `200 x 200 x 5 mm`、距边 `5 mm` 的四孔支架
- `save_active_document` 成功保存到桌面
- `open_document` 成功重新打开已保存文件

示例保存文件：

- `C:\Users\Xuan\Desktop\bracket-200x200x5-4xM3-edge5.SLDPRT`

## 为什么保留弹窗抑制逻辑

某些 SolidWorks 2023 宿主环境中，会在延迟加载某些托管组件时弹出 `.NET Framework` 相关对话框。这个仓库没有声称彻底修复 SolidWorks 本体问题，而是通过更保守的启动与窗口管理策略，把 MCP 工作流稳定在“可用”状态。

这属于工程性绕过，不是 Dassault 官方修复。

## 开源说明

- Upstream reference: [eyfel/mcp-server-solidworks](https://github.com/eyfel/mcp-server-solidworks)
- License: MIT
- Additional packaging and host-stability work in this repo: `Xuan_Boms`
