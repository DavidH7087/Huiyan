# 慧眼 · Phase 3B Windows 桌面构建

新增 WebView2 原生桌面窗口、FastAPI 本机回环服务及 `%LOCALAPPDATA%/Huiyan/data` 用户级持久化目录。

GitHub Actions Windows Runner 构建 PyInstaller 便携版（一个文件夹），自动执行 Windows API 回归、打包 EXE 本地启动冒烟测试，上传 14 天有效的测试构建产物。不自动创建公开 GitHub Release。

请在 Windows 11 上人工验证 WebView2、中文排版、实际简历导入、任务恢复和离线运行。OCR / 语义模型未随便携包安装。
