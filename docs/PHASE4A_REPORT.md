# 慧眼 · Phase 4A 浏览器交互验收

该阶段新增 Playwright Chromium 真实浏览器自动化：运行 FastAPI 服务 → 在首页输入招聘 JD → 确认招聘条件 → 创建任务 → 上传虚构中文简历 → 开始筛选 → 审核候选人 → 打开筛选历史。

成功执行后 GitHub Actions 会保存 `huiyan-results.png` 作为实际界面截图供人工检查。自动化测试与 Codespace 内真实人工使用不同，不能代替 Windows WebView2 图形界面和真实招聘数据测试。

`pytest` 基础环境未安装 Playwright 时将自动跳过此测试，独立的 `Huiyan Browser E2E` 工作流会安装 Chromium 并执行完整流程。
