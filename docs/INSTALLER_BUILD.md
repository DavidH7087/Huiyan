# 慧眼 Windows 安装程序（预览版）

Windows GitHub Actions 使用 Inno Setup 6 将通过冒烟测试的 `dist/Huiyan` 便携文件夹打包为 `Huiyan-Setup-0.6.0-preview.exe`。

- 默认按用户安装在 `%LOCALAPPDATA%\Programs\Huiyan`，无需管理员权限。
- 自动创建开始菜单快捷方式，可选桌面快捷方式，带卸载入口。
- 候选人资料位于 `%LOCALAPPDATA%\Huiyan\data`，**卸载时默认保留**，防止误删 HR 工作档案；如需彻底清除，需依据公司数据管理流程单独处理该目录。
- 安装器未经商业代码签名；Windows SmartScreen 可能弹出风险提示。在人工安全验收及签名前不能作为正式商用发行。
- 当前已捆绑离线 Tesseract OCR（简体中文及英文语言数据），无需单独安装 OCR。BGE-M3 等大型语义模型暂未内置。
- CI 验证 Python 后端、OCR 模块就绪、打包 EXE、静默安装、安装后 EXE 本机启动，再上传测试安装器产物。浏览器 E2E 验证完整招聘工作流与本地加密备份下载。
