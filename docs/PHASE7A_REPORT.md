# 慧眼 Phase 7A · Windows 安装包可追溯性与校验清单

每次成功的 Windows GitHub Actions 预览构建都将额外生成 `Huiyan-SHA256SUMS.txt`、`Huiyan-build.json` 和 `Huiyan-dependencies.json`，与已存在的安装 EXE、便携 ZIP 一并作为 Artifacts 保存。这些文件记录 GitHub 提交 SHA、运行 ID、构建平台、安装包 SHA-256 和安装时的依赖列表。用户拿到安装包后可以对照校验值验证文件在传输中是否变更。

这**不是** Microsoft Authenticode 代码签名，无法自动消除 Windows SmartScreen 警告，也不代表应用通过第三方安全审计。正式商用版仍需签名证书、最终依赖漏洞审查、离线/权限实机验收、个人信息保护方案和真实招聘准确性测试。当前构建以「未签名内部预览版」方式保留在 Actions，不公开发布 GitHub Release。

Windows 用户可在 PowerShell 中运行：

```powershell
Get-FileHash -Algorithm SHA256 .\Huiyan-Setup-0.7.2-preview.exe
```

将输出的 SHA256 与 `Huiyan-SHA256SUMS.txt` 对照。GitHub 工作流将对生成的清单做基本存在性和长度检查；预览产物保留期延长至 30 天。
