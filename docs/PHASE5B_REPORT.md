# 慧眼 Phase 5B · Windows 本地服务跨站防护

Windows 桌面模式新增请求安全边界。仅允许 `127.0.0.1` / `localhost` 的 Host，并拒绝不匹配的 `Origin` 和 `Sec-Fetch-Site: cross-site` 请求，从而降低其他网页通过 DNS rebinding 或浏览器跨站请求碰触本地简历服务的风险。

**范围限制**：这不是身份认证和完整安全审计，无法抵御本机恶意软件或任何能执行本机进程的攻击者。Codespaces 模式不会应用桌面专用 Host 限制；需要始终使用 Private 端口、开发示例数据，企业多人部署需要另加认证、加密和授权机制。

已添加 `tests/test_local_security.py`，覆盖同源请求成功、伪造 Host、外部 Origin、Cross-Site Fetch 被拒绝以及 Codespaces 非桌面环境不被误伤。需通过 GitHub CI 和 Windows 构建后才能视为阶段验收。
