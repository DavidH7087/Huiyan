# Windows 便携版发布前说明

本阶段新增 `desktop.py`（Windows WebView2 桌面壳）、`requirements-desktop.txt`、GitHub Actions Windows 构建流水线。发布包为 onedir 便携文件夹 ZIP，不是签名安装程序。

- 在 GitHub Actions 的 `Huiyan Windows Portable Build` 工作流里下载 **测试构建产物**，解压后运行 `Huiyan.exe`。
- Windows 11 需要 WebView2 Runtime；若缺少，需由 IT 先安装。可按官方 pywebview 文档检查环境。
- 桌面模式后端仅绑定到 `127.0.0.1`，数据位于 `%LOCALAPPDATA%\\Huiyan\\data`（可通过 `HUIYAN_DATA_DIR` 覆盖）。
- Windows CI 必须完成 Python API 回归、EXE 构建、可执行文件本地 HTTP 健康检查；仍需人工实测 WebView2 UI、非技术 HR 操作、中文 OCR 模型、Windows Defender、安全与隐私。
- **禁止公开分享真实简历。** 测试包没有用户登录和加密机制，不可直接在多人共用或未受管设备上处理真实 HR 资料。
- 本地扫描件 OCR 和大模型是额外组件，未默认打进便携包；不应把构建成功等同于完整 AI 方案已发布。
