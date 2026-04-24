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

这一节适合直接复制给 Codex、ChatGPT Codex 或其他本地代码助手使用。

写法参考了更偏“执行单 / 安装工单”风格的代理提示词：先冻结目标，再约束执行方式，最后规定验收输出。这样比“帮我装一下”更容易让代理稳定完成真实部署。

### 标准部署提示词

```text
任务：在当前 Windows 主机上部署并验证 `D:\task\soildworks-mcp`，把它配置成可被 Codex 以 MCP stdio 方式直接调用的 SolidWorks MCP server。

目标：
- 让仓库可以在本机直接构建、启动、接入 Codex。
- 完成真实测试，不接受只给理论步骤。

执行要求：
1. 先阅读仓库 README，再按 README 中描述的标准方式部署。
2. 不要另起炉灶，不要发明新的目录结构，不要绕过 bridge。
3. 必须安装 Python 依赖，并确认以下任一启动方式可用：
   - `python .\server.py`
   - `python -m solidworks_mcp`
4. 必须构建 `bridge\SolidWorksBridge.csproj`。
   - 如果 SolidWorks 安装路径不是默认路径，自动识别或显式传入 `SolidWorksInstallDir`。
5. 必须把这个 server 配到 Codex 的 `config.toml` 中，使用 `stdio` 方式调用。
6. 必须做真实冒烟测试，至少验证：
   - `ping`
   - `solidworks_status`
   - `launch_solidworks`
   - `create_rectangular_block`
   - `save_active_document`
7. 不要把“命令运行成功”当作“部署成功”。
   - 必须验证生成文件真实存在。
   - 必须验证已保存的 `.SLDPRT` 可以重新打开。
8. 如果遇到 SolidWorks 的 `.NET Framework` / 宏 / 宿主稳定性弹窗，不要停在现象描述，要继续排查并尽量修到“可用状态”。

禁止事项：
- 不要只输出计划，不执行命令。
- 不要跳过 bridge 构建。
- 不要伪造测试结果。
- 不要在未验证的情况下声称“已可用”。

验收标准：
- MCP server 可启动。
- Codex 可通过 stdio 调用。
- SolidWorks 可被拉起。
- 至少成功创建一个实体零件。
- 零件可保存到磁盘并重新打开。

最终输出必须包含：
- 实际执行过的命令
- 修改过的文件
- 测试结果
- 生成文件路径
- 仍然存在的限制或风险
```

### 带建模任务的部署提示词

```text
任务：部署并验证 `D:\task\soildworks-mcp`，然后用它在 SolidWorks 中真实生成一个零件。

目标零件：
- 带 4 个 M3 孔的支架
- 长宽 20 cm
- 厚度 5 mm
- 孔距边 5 mm
- 保存为 `.SLDPRT` 到桌面

执行要求：
1. 先完成仓库部署和 bridge 构建。
2. 再把该 MCP server 以 stdio 方式接入 Codex。
3. 使用真实 MCP 调用完成建模，不要只写示例代码。
4. 保存后验证文件存在，并重新打开验证可读。

最终输出必须包含：
- 部署命令
- 调用的 MCP 工具
- 测试结果
- 桌面上的实际保存路径
- 如果 `M3` 只是按 `3 mm` 几何孔处理，也要明确说明
```

### 极简触发版

如果你只是想快速丢给代理一句话，可以用这个版本：

```text
请按 D:\task\soildworks-mcp 的 README 在本机完成真实部署和测试，不要只给方案。部署后通过 MCP 在 SolidWorks 中创建一个带 4 个 M3 孔的支架，长宽 20 cm，厚度 5 mm，孔距边 5 mm，保存到桌面，并验证文件可重新打开。最后汇报命令、修改文件、测试结果和保存路径。
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
