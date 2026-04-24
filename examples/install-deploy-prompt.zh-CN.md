# 安装与部署提示词

这是一份可直接用于 Codex CLI、Claude Code CLI 或其他支持 MCP 的编码 CLI 的完整中文提示词。

```text
任务：把 D:\task\soildworks-mcp 在这台 Windows 机器上部署并验证为一个真实可用的 SolidWorks MCP server。

在开始改动文件或执行安装命令之前，先用一条简短消息问我这三个部署选择：
1. 这次要部署到哪里？
   例如：继续使用 D:\task\soildworks-mcp、克隆到新的目录、或使用某个现有 checkout。
2. 这次要注册到哪个编码客户端里使用？
   例如：Codex CLI、Claude Code CLI，或其他支持 MCP 的客户端。
3. 最终 MCP server 要使用哪个 Python 解释器或虚拟环境？

等我回答后，再继续执行完整部署。

执行要求：
1. 先阅读仓库 README，再按仓库既有结构执行，不要擅自发明新目录结构。
2. 必须执行真实安装，不能只给分析或计划。
3. 安装仓库所需的 Python 依赖。
4. 构建 bridge\SolidWorksBridge.csproj。如果 SolidWorks 不在默认路径，要自动识别或显式传入 SolidWorksInstallDir。
5. 必须验证以下任一启动方式可用：
   - python .\server.py
   - python -m solidworks_mcp
6. 必须把该 server 以 stdio MCP server 的方式注册到选定的编码客户端。
7. 必须执行真实验证，不能做 mock 验证。最少验证：
   - ping
   - solidworks_status
   - launch_solidworks
   - create_rectangular_block
   - create_plate_with_holes
   - design_from_prompt
8. 至少保存一个真实生成的 .SLDPRT 文件，并确认该文件可重新打开。
9. 必须如实报告 combine_all_bodies。如果宿主环境不支持，就明确说明，不要假装成功。
10. 如果 SolidWorks 出现 .NET 或 macro 相关不稳定弹窗，不要只停留在现象描述，要继续排查到 MCP 处于尽可能可用的状态。

禁止事项：
- 不要只写计划不执行
- 不要跳过 bridge 构建
- 不要在没有真实 MCP 调用的情况下声称部署成功
- 不要伪造测试结果

最终输出必须包含：
- 实际使用的部署路径
- 实际注册到的编码客户端
- 最终配置的 MCP stdio 命令
- 实际执行过的命令
- 修改过的文件
- 实际调用过的 MCP 工具
- 测试结果
- 保存文件路径
- 仍然存在的限制或宿主风险
```
