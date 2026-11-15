const view = document.getElementById('view');
const nav = [...document.querySelectorAll('[data-view]')];
const state = {
  page:'home', tasks:[], task:null, runs:[], run:null, result:null, selected:null,
  description:'', descriptionLeads:[], required:[], preferred:[], excluded:[], matchMode:'aliases', title:'', editing:false, filter:'全部', busy:false, preview:null,
  currentText:null, uploadSummary:null, importRecords:[], stagedFiles:[], retryFiles:[], historyCompare:null, retentionReport:null, diagnostics:null, reviewEvents:[], taskChanges:[], search:'', health:null, profileStatus:null, recoveryNotice:'',
};
const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const e=escapeHtml;
const el = id=>document.getElementById(id);
const terms = text => [...new Set(String(text||'').split(/[,，、;；\n]+/).map(s=>s.trim()).filter(Boolean))];
const fmt = time => time ? time.replace('T',' ').slice(0,16):'';
let toastTimer;
function toast(message){const t=el('toast');t.textContent=message;t.classList.add('shown');clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.remove('shown'),3800)}
async function api(url,opts={}){
  const res=await fetch(url,opts);
  if(!res.ok){let problem='操作失败';try{const payload=await res.json();problem=typeof payload.detail==='string'?payload.detail:JSON.stringify(payload.detail)}catch{}throw new Error(problem)}
  return res.json();
}
const post=(url,data)=>api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
const patch=(url,data)=>api(url,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
async function withBusy(action){if(state.busy)return;state.busy=true;try{await action()}catch(err){console.error(err);toast(err.message||'操作失败，请重试')}finally{state.busy=false}}
async function fetchTasks(){state.tasks=await api('/api/tasks')}
async function fetchProfiles(){if(state.health?.restore_available)state.profileStatus=await api('/api/system/profiles')}
function setPage(page){state.page=page;nav.forEach(n=>n.classList.toggle('active',n.dataset.view===page));el('breadcrumb').textContent=({home:'首页',tasks:'筛选任务',archive:'招聘档案',confirm:'确认招聘要求',import:'添加简历',results:'候选人筛选结果'})[page]||'慧眼';render()}
function badge(label,color='neutral'){return `<span class="badge ${color}">${e(label)}</span>`}
function taskCard(task){return `<button class="folder" data-task="${task.id}"><span class="folder-icon">▤</span><div class="grow"><strong>${e(task.title)}</strong><p>${task.resume_count||0} 份简历 · ${task.run_count||0} 轮筛选 · ${e(fmt(task.created_at))}</p></div>${badge(task.archived?'已归档':'进行中',task.archived?'neutral':'green')}<span class="subtle">›</span></button>`}
function home(){return `<div class="home"><div class="hero"><h1>开始简历筛选</h1><p>输入岗位要求，添加简历，快速找到值得关注的人选。</p></div>
<div class="entry"><textarea id="newDescription" placeholder="输入招聘要求，或直接粘贴岗位 JD……">${e(state.description)}</textarea><div class="entry-footer"><span class="subtle small">关键词与自然语言均可使用，下一步可修改条件</span><button id="describeNext" class="btn">下一步　→</button></div></div>
<section class="recent"><div class="section-head"><h2>最近的任务</h2><button class="btn ghost small" data-go="archive">查看全部</button></div><div class="task-list">${state.tasks.slice(0,4).map(taskCard).join('')||'<div class="empty">还没有招聘任务。从上方创建第一个任务。</div>'}</div></section></div>`}
function confirm(){return `<div class="page-title"><h1>${state.editing?'编辑招聘要求':'确认筛选要求'}</h1><p>关键词可选。即使只填写岗位描述，也可以开始筛选；描述仅提供待核实的文字线索，最终由 HR 判断。</p></div>
<div class="surface"><div class="field"><label for="jobTitle">岗位或任务名称</label><input id="jobTitle" value="${e(state.title)}" placeholder="例如：销售经理招聘"></div>
<div class="field"><label for="descConfirm">招聘需求</label><textarea id="descConfirm">${e(state.description)}</textarea></div>
<div class="field"><label for="descClues">从描述提取的参考线索（可修改或全部删除）</label><textarea id="descClues" style="min-height:76px" placeholder="系统提取的可选检索线索">${e(state.descriptionLeads.join('、'))}</textarea><small>这些线索只帮助发现相关文字；删除它们不会改变您手工填写的必须或优先条件。最多保留 8 项。</small></div>
<div class="form-grid"><div class="field"><label for="mustTerms">必须具备</label><textarea id="mustTerms" style="min-height:110px">${e(state.required.join('、'))}</textarea><small>可留空。多个条件使用顿号分隔；未发现相关文字不会自动淘汰。</small></div>
<div class="field"><label for="bonusTerms">优先考虑</label><textarea id="bonusTerms" style="min-height:110px">${e(state.preferred.join('、'))}</textarea><small>这些条件有相关经历则优先显示，但并非必要条件。</small></div></div>
<div class="form-grid"><div class="field"><label for="excludedTerms">排除线索（选填）</label><textarea id="excludedTerms" style="min-height:72px" placeholder="例如：仅短期兼职、未独立负责">${e(state.excluded.join('、'))}</textarea><small>只标记需要 HR 复核的线索，系统不会自动淘汰或删除简历。不要使用年龄、性别等敏感个人特征。</small></div>
<div class="field"><label for="keywordMode">关键词匹配方式</label><select id="keywordMode"><option value="aliases" ${state.matchMode==='aliases'?'selected':''}>智能同义（默认）</option><option value="exact" ${state.matchMode==='exact'?'selected':''}>精确文字（不扩展同义词）</option></select><small>仅影响关键词检索，不代表判断应聘者真实能力。</small></div></div>
<div class="notice">自动提取只是建议。描述中的补充线索只辅助检索，不会自动成为必须条件；“最好”“不限”等表达请人工核对。</div>
<div class="actions" style="margin-top:22px"><button class="btn secondary" data-go="home">返回修改</button><button class="btn" id="createTask">${state.editing?'保存条件（历史轮次不变）':'创建任务，添加简历 →'}</button></div></div>`}
function importPage(){return `<div class="page-title"><h1>添加简历</h1><p>${e(state.task?.title||'')} · 可以一次添加多个文件或整个文件夹。</p></div>
<div class="surface"><div class="dropzone" id="resumeDropzone"><strong>选择文件，或将简历拖到这里</strong><p>支持 PDF、DOCX、TXT、ZIP；${state.health?.ocr?.state==='ready' ? '扫描 PDF 和图片式 Word 将自动尝试本地 OCR 识别。' : '当前扫描件识别未就绪；文字 PDF 和普通 Word 不受影响。'}</p><input type="file" id="fileInput" multiple accept=".pdf,.docx,.txt,.zip"><p style="margin-top:16px">或者选择整个文件夹</p><input type="file" id="folderInput" multiple webkitdirectory directory><p id="selectedFiles" class="hint">${state.stagedFiles.length?'已选择 '+state.stagedFiles.length+' 个文件':'尚未选择文件'}</p></div>
${state.health?.ocr ? `<p class="hint">文字识别：${e(state.health.ocr.message)}${state.health.ocr.state==='ready'?'':'。扫描版简历可能导入失败，请查看 OCR 配置说明。'}</p>` : ''}<p id="importProgress" class="hint" role="status" aria-live="polite"></p><div class="actions" style="margin-top:18px"><button class="btn secondary" data-go="tasks">稍后添加</button><button class="btn" id="uploadFiles">导入所选简历</button></div>
${state.uploadSummary?`<div class="notice">成功导入 ${state.uploadSummary.imported} 份，重复 ${state.uploadSummary.duplicates} 份，问题文件 ${state.uploadSummary.issues.length} 份，需核对 ${state.uploadSummary.warnings?.length||0} 份。</div>`:''}
${state.uploadSummary?.issues?.length?`<div class="notice warn">${state.uploadSummary.issues.slice(0,6).map(x=>e(x.filename+': '+x.message)).join('<br>')}</div>`:''}
${state.uploadSummary?.warnings?.length?`<div class="notice warn">${state.uploadSummary.warnings.slice(0,8).map(x=>e(x.filename+': '+x.message)).join('<br>')}</div>`:''}${state.retryFiles.length?'<button class="btn secondary small" id="retryIssues">重试本次失败的文件</button>':''}
<details class="audit-log"><summary>查看导入明细（最近 300 条）</summary>${state.importRecords.map(x=>`<p>${e(fmt(x.created_at))} · ${e(x.state)} · ${e(x.filename)}${x.message?' · '+e(x.message):''}</p>`).join('')||'<p>暂无记录</p>'}</details><div class="divider"></div><div class="toolbar"><span>此任务已有 <strong>${state.task?.resume_count||0}</strong> 份简历</span><button class="btn" id="startScreening" ${(state.task?.resume_count||0)<1?'disabled':''}>开始筛选 →</button></div>
<p class="hint">注：无关键词也可根据岗位描述查找参考线索。可选本地语义模型能提供更多待核实内容；不能据此自动淘汰候选人。</p></div>`}
function allTasks(archive=false){const records=archive==='all'?state.tasks:state.tasks.filter(t=>archive?t.archived:!t.archived);return `<div class="section-head"><div><h1>${archive?'招聘档案':'筛选任务'}</h1><p class="subtle">${archive?'所有岗位和筛选历史集中管理，支持归档与恢复。':'管理当前招聘、筛选结果和人工审核。'}</p></div><button class="btn" data-go="home">+ 新建任务</button></div><div class="task-list">${records.map(taskCard).join('')||'<div class="empty">这里暂时没有招聘任务。</div>'}</div>${!archive?`<div class="subpanel"><h2 style="margin-bottom:14px">已归档</h2><div class="task-list">${state.tasks.filter(t=>t.archived).map(taskCard).join('')||'<p class="subtle small">没有已归档的任务。</p>'}</div></div>`:''}`}
function groupCounts(results){return ['优先查看','需要确认'].map(k=>({name:k,count:results.filter(r=>r.evaluation.group===k).length}));}
function resultsPage(){const run=state.result?.run;const rows=state.result?.results||[];
const visible=rows.filter(r=>(state.filter==='全部'||(state.filter==='面试名单'?r.review_status==='加入面试名单':r.evaluation.group===state.filter)) && (`${r.name} ${r.filename} ${r.evaluation.checks.map(c=>c.term).join(' ')}`.toLowerCase().includes(state.search.toLowerCase())));
const selected=visible.find(x=>x.resume_id===state.selected)||visible[0];
const counts=groupCounts(rows);
return `<div class="task-header"><div><h1>${e(state.task?.title||'筛选任务')}</h1><div class="subtle small">${e(run?.name||'尚未筛选')} · ${e(fmt(run?.created_at))}</div></div><div class="inline-actions"><button class="btn secondary small" id="uploadMore">+ 添加简历</button><button class="btn secondary small" id="editCriteria">编辑岗位条件</button><button class="btn secondary small" id="toggleArchive">${state.task?.archived?'恢复任务':'归档任务'}</button>${run?`<a class="btn small" href="/api/tasks/${state.task.id}/runs/${run.id}/export">导出 Excel</a>`:''}</div></div>
<div class="stat-row"><div class="stat"><strong>${rows.length}</strong><span>本轮候选人</span></div>${counts.map(c=>`<div class="stat"><strong>${c.count}</strong><span>${c.name}</span></div>`).join('')}</div>
<div class="toolbar"><div class="left"><h2>候选人</h2><span class="subtle small">按相关文字证据排序，语义线索需人工核实</span></div><button class="btn secondary small" id="openHistory">筛选历史 (${state.runs.length})</button></div>
${run?.criteria?.semantic?.state==='error'?`<div class="notice warn">本地语义分析暂不可用，已改用基础文字匹配。请在设置中检查模型。</div>`:''}${!run?`<div class="empty"><p>还没有筛选结果。</p><button class="btn" id="firstScreening">开始第一轮筛选</button></div>`:`<div class="filters">${['全部','优先查看','需要确认','面试名单'].map(f=>`<button class="filter ${state.filter===f?'active':''}" data-filter="${e(f)}">${e(f)}</button>`).join('')}</div>
<div class="two-col"><div><div style="margin-bottom:13px"><input id="candidateSearch" placeholder="搜索候选人、文件名或条件" value="${e(state.search)}"></div>
<div class="candidate-list">${visible.map(r=>`<div class="candidate-row ${selected?.resume_id===r.resume_id?'selected':''}" data-candidate="${r.resume_id}"><header><strong>${e(r.name)}</strong>${badge(r.evaluation.group,r.evaluation.group==='优先查看'?'green':'amber')}${r.possible_duplicate_with?.length?badge('疑似重复','amber'):''}</header><p>${e(r.filename)} · 找到 ${r.evaluation.matched_count} 项文字证据${r.evaluation.semantic_hint_count?` · ${r.evaluation.semantic_hint_count} 项语义线索`:''}${r.evaluation.exclusion_flags?` · ${r.evaluation.exclusion_flags} 项排除线索待核实`:''} · ${e(r.review_status)}</p></div>`).join('')||'<div class="empty">当前筛选条件没有候选人。</div>'}</div>
<div class="surface subpanel"><h2>继续筛选</h2><p class="hint">输入补充条件并创建新轮次，原结果不变。补充条件默认作为优先线索，不自动提高必要门槛。</p><textarea id="followupQuery" placeholder="例如：更关注有制造业客户经验的人" style="min-height:80px"></textarea><label for="followupScope">在这些候选人中继续筛选</label><select id="followupScope"><option value="全部">当前轮次全部人选</option><option value="优先查看">仅优先查看的人选</option><option value="需要确认">仅需要确认的人选</option><option value="面试名单">仅面试名单</option></select><div class="actions" style="margin-top:10px"><button class="btn secondary" id="screenAgain">创建新一轮筛选</button></div></div></div>
<aside class="surface panel">${selected?candidatePanel(selected):'<p class="subtle">选择一位候选人查看详情。</p>'}</aside></div>
<div class="subpanel"><h2>历史轮次</h2><div style="margin-top:14px">${roundsMarkup()}</div></div>${comparisonMarkup()}`}`}
function retentionMarkup(){
 const report=state.retentionReport;if(!report)return '';
 return `<div class="notice"><strong>${report.days} 天以上的简历：${report.due_count} 份</strong><p>这是供 HR 审阅的待处理清单，并非自动删除期限。请按企业制度核对原始文件和外部备份。</p>
 ${report.candidates.slice(0,30).map(c=>`<p>${e(c.name)} · ${e(c.filename)} · 导入于 ${e(fmt(c.imported_at))}</p>`).join('')}
 ${report.due_count>30?'<p>还有更多候选人未在此处列出，可在完整名单查看。</p>':''}</div>`;
}
function comparisonMarkup(){
 const report=state.historyCompare;if(!report)return '';
 const labels=(records,empty)=>records.length?records.slice(0,12).map(r=>e(r.name+'（'+r.filename+'）')).join('、'):empty;
 return `<div class="surface subpanel"><div class="toolbar"><h2>筛选轮次对比</h2><button class="btn ghost small" id="closeCompare">关闭对比</button></div>
 <p class="hint">${e(report.left.name)} → ${e(report.right.name)}，比较的是各轮保存的筛选证据，不是今天的审核状态。</p>
 <div class="stat-row"><div class="stat"><strong>${Number(report.same)}</strong><span>共同候选人</span></div><div class="stat"><strong>${Number(report.added_count)}</strong><span>新增候选人</span></div><div class="stat"><strong>${Number(report.removed_count)}</strong><span>不再出现</span></div><div class="stat"><strong>${Number(report.changed_group_count)}</strong><span>分组变化</span></div></div>
 <p class="hint">新增：${labels(report.added,'无')}；未包含：${labels(report.removed,'无')}</p>
 <p class="hint">分组变动：${report.changed.length?report.changed.slice(0,12).map(v=>e(v.name+'：'+v.before+' → '+v.after)).join('；'):'无'}</p>
 <p class="hint">仅展示前 100 项变化。历史记录不会被修改。</p></div>`;
}
function candidatePanel(r){const checks=r.evaluation.checks;return `<h3>${e(r.name)}</h3><div class="file-details">${e(r.filename)}<br>证据覆盖率：${r.evaluation.evidence_coverage}%（并非能力分数）</div>
${r.possible_duplicate_with?.length?`<div class="notice warn">发现 ${r.possible_duplicate_with.length} 份联系方式相同的简历（ID：${r.possible_duplicate_with.map(x=>Number(x)).join("、")}），可能是同一人的不同版本。原始文件均保留，请人工核对。</div>`:''}
${r.ocr_pages?`<div class="notice warn">${r.ocr_pages} 页来自扫描件 OCR；识别文字可能出错，请打开原简历核对。</div>`:''}
${r.parse_warnings&&!r.ocr_pages?`<div class="notice warn">该简历有 ${r.parse_warnings} 页文字不完整，建议核对原件。</div>`:''}
${r.evaluation.exclusion_flags?`<div class="notice warn">发现 ${Number(r.evaluation.exclusion_flags)} 项排除线索，<strong>只能由 HR 人工核实</strong>，系统不会自动淘汰。</div>`:''}
<div class="inline-actions"><button class="btn secondary small" data-preview="${r.resume_id}">阅读简历内容</button><a class="btn secondary small" target="_blank" rel="noopener" href="/api/tasks/${state.task.id}/resumes/${r.resume_id}/original">打开原文件</a></div>
${checks.map(c=>`<div class="evidence-item"><div class="toolbar" style="margin:0"><strong>${e(c.term)}</strong>${badge(c.state||'待核实',c.state==='有相关文字'?'green':'amber')}</div>${c.evidence?`<p>第 ${Number(c.evidence.page)} 页 · “${e(c.evidence.excerpt)}”</p>`:c.semantic_hint?`<p class="semantic-lead">可能相关的经历（第 ${Number(c.semantic_hint.page)} 页），<strong>需要人工核实</strong>： “${e(c.semantic_hint.excerpt)}”</p>`:'<p>没有找到足够的直接文字证据，不能直接判定候选人不具备该能力。</p>'}</div>`).join('')||'<div class="notice">当前任务没有配置明确筛选条件，请返回修改岗位要求。</div>'}
<div class="subpanel"><h3>人工审核</h3>${r.review_at_run?`<p class="hint">本轮创建时：${e(r.review_at_run.status)}（历史快照）；下方为当前审核状态。</p>`:'<p class="hint">旧轮次未记录创建时的审核状态；下方显示当前状态。</p>'}<label for="reviewStatus">审核状态</label><select id="reviewStatus">${['未审核','加入面试名单','需要补充资料','暂不推进'].map(v=>`<option value="${e(v)}" ${v===r.review_status?'selected':''}>${e(v)}</option>`).join('')}</select>
<label for="reviewNote">备注</label><textarea id="reviewNote" style="min-height:74px" placeholder="填写人工审核意见……">${e(r.review_note||'')}</textarea><button class="btn" style="width:100%;margin-top:12px" data-save-review="${r.resume_id}">保存审核</button>
<p class="hint" style="margin-top:18px">需要响应个人资料删除申请时，可以永久删除该候选人的原文件与全部相关审核记录，历史筛选人数也会相应变化。</p>
<button class="btn secondary small" id="deleteCandidate" data-delete-candidate="${r.resume_id}" data-filename="${e(r.filename)}">永久删除这位候选人</button></div>`}
function roundsMarkup(){return state.runs.map((r,i)=>`<div class="round-row" data-run="${r.id}"><span class="round-no">${state.runs.length-i}</span><div class="grow"><strong>${e(r.name)}</strong><p>${e(fmt(r.created_at))} · ${r.candidate_count} 人 · ${r.parent_id?'基于上一轮':'全量筛选'}${r.criteria?.source_filter&&r.criteria.source_filter!=='全部'?' · '+e(r.criteria.source_filter):''}</p></div>${state.result?.run?.id===r.id?badge('当前轮次','green'):'<span class="subtle small">查看 ›</span>'}<button class="btn secondary small" data-compare="${r.id}" aria-label="与当前轮次比较">对比</button><button class="btn secondary small" data-replay="${r.id}" aria-label="复用本轮条件">复用条件</button><button class="btn secondary small" data-restore-criteria="${r.id}" aria-label="恢复本轮岗位条件">恢复条件</button></div>`).join('')||'<div class="empty">暂无筛选记录</div>'}
function baseArchivePage(){if(!state.task){return allTasks("all") + (state.health?.backup_available?`<div class="surface subpanel"><h2>加密备份招聘档案</h2><p class="hint">导出全部招聘任务、审核记录及原始简历。请妥善保存备份密码；遗失后无法恢复。</p><div class="actions" style="margin-top:12px"><input id="backupPassword" type="password" autocomplete="new-password" placeholder="设置至少 12 字符的备份密码" style="max-width:330px" aria-label="备份密码"><button class="btn secondary" id="createBackup">创建并下载加密备份</button></div><p class="hint">仅限本机 Windows 版；本备份文件含个人信息，切勿发送到公共仓库。</p></div>`:'')}return `<div class="toolbar"><button class="btn secondary small" id="archiveBack">← 所有任务</button><button class="btn small" data-go="results">查看候选人</button></div><div class="page-title"><h1>${e(state.task.title)} · 筛选档案</h1><p>每一次筛选都会单独记录条件和结果，不覆盖历史。</p></div><div class="surface"><h2 style="margin-bottom:18px">筛选轮次</h2><div class="actions" style="margin-bottom:14px"><label for="retentionDays">待复核资料期限</label><select id="retentionDays"><option value="180">180 天</option><option value="365" selected>365 天</option><option value="730">730 天</option></select><button class="btn secondary small" id="checkRetention">检查旧简历</button><button class="btn secondary small" id="editCriteria">编辑岗位条件</button></div>${retentionMarkup()}${roundsMarkup()}${comparisonMarkup()}<details class="audit-log"><summary>岗位条件修改记录（最近 200 条）</summary>${(state.taskChanges||[]).map(v=>`<p>${e(fmt(v.occurred_at))} · ${e(v.action.startsWith('restore_round:')?'恢复历史条件':'编辑岗位条件')} · 必须：${e((v.previous.required||[]).join('、')||'无')} → ${e((v.next.required||[]).join('、')||'无')}</p>`).join('')||'<p>暂无修改记录</p>'}</details><details class="audit-log"><summary>人工审核操作记录（最近 500 条）</summary>${(state.reviewEvents||[]).map(v=>`<p>${e(fmt(v.occurred_at))} · ${e(v.name||'候选人')} · ${e(v.status)}${v.note?' · '+e(v.note):''}</p>`).join('')||'<p>暂无操作记录</p>'}</details><div class="notice">筛选依据保留历史快照；人工审核当前状态可更新，每轮创建时的审核状态独立记录。</div>${state.task.archived?'<div class="actions" style="margin-top:16px"><button class="btn secondary small" id="deleteArchivedTask">永久删除任务及全部简历（不可恢复）</button></div>':''}</div>`}
function archivePage(){
  const original=baseArchivePage();
  if(state.task || !state.health?.restore_available)return original;
  const profile=state.profileStatus||{};
  const notice=state.recoveryNotice?`<div class="notice">${e(state.recoveryNotice)}</div>`:'';
  const pending=profile.pending_profile?`<div class="notice warn">新的招聘档案已准备好。请完全关闭并重新打开慧眼后生效。</div>`:'';
  const switchBack=profile.can_return_to_original && !profile.pending_profile
    ? '<button class="btn secondary small" id="switchOriginal">下次启动切回最初档案</button>' : '';
  return original+`<div class="surface subpanel"><h2>恢复加密招聘档案</h2>
    <p class="hint">从之前导出的 .hyb 加密文件恢复。系统验证备份后建立独立档案，<strong>不会覆盖当前任何简历或筛选历史</strong>。关闭再重新打开慧眼后切换。</p>
    <div class="field"><label for="restoreFile">加密备份文件</label><input type="file" id="restoreFile" accept=".hyb,application/octet-stream"></div>
    <div class="actions" style="margin-top:12px"><input id="restorePassword" type="password" autocomplete="off" placeholder="原备份密码" aria-label="恢复密码" style="max-width:300px"><input id="restoreConfirm" placeholder="输入“恢复”确认" aria-label="恢复确认" style="max-width:180px"><button class="btn secondary" id="restoreBackup">验证并恢复（重启生效）</button></div>
    <p class="hint">仅在本机处理。密码不会保存；恢复需要额外磁盘空间。请不要把备份上传到公共 GitHub。</p>
    ${pending}${notice}${switchBack}</div><div class="surface subpanel"><h2>本地数据完整性</h2><p class="hint">仅核对本机数据库及原始简历文件数量，不会上传或删除资料。检查结果不包含候选人姓名。</p><button class="btn secondary small" id="checkIntegrity">检查本地数据</button>${state.diagnostics?`<p class="hint">${e(state.diagnostics.message)} · 简历 ${Number(state.diagnostics.resume_count||0)} · 缺失文件 ${Number(state.diagnostics.missing_files)} · 多余文件 ${Number(state.diagnostics.orphan_files)}</p>`:''}</div>`;
}
function previewPage(){if(!state.preview)return '<p>没有已打开的简历</p>';const p=state.preview.profile||{};const edu=(p.education_mentions||[]).map(x=>x.label).join('、')||'未明确提及';const skills=(p.skill_mentions||[]).map(x=>x.label).join('、')||'未明确提及';const years=(p.stated_experience_years||[]).join('、')||'未明确提及';const profileHtml=`<div class="surface" style="margin-bottom:15px"><h2>结构化信息（请核对原文）</h2><p class="hint">学历：${e(edu)} · 技能：${e(skills)} · 明确提及的工作年限：${e(years)}${p.stated_experience_years?.length?' 年':''}</p>${p.experience_years_conflict?'<p class="hint">⚠ 工作年限描述存在差异，请人工核实。</p>':''}${p.needs_source_review?'<p class="hint">⚠ 部分信息来自扫描件或解析存疑，请查看原件。</p>':''}<p class="hint">这些只是文字提及，不代表学历和技能已经验证。</p></div>`;return `<div class="toolbar"><button class="btn secondary" data-go="results">← 返回名单</button><a class="btn small" target="_blank" rel="noopener" href="/api/tasks/${state.task.id}/resumes/${state.preview.id}/original">打开原文件</a></div><div class="page-title"><h1>${e(state.preview.filename)}</h1><p>提取的纯文本，仅供核对。PDF 可通过原文件查看。</p></div>${profileHtml}${state.preview.pages.map(p=>`<div class="surface" style="margin-bottom:15px"><h2 style="margin-bottom:12px">第 ${Number(p.page)} 页</h2><div class="textview">${e(p.text)}</div></div>`).join('')}`}
function render(){switch(state.page){case 'home':view.innerHTML=home();break;case 'confirm':view.innerHTML=confirm();break;case 'import':view.innerHTML=importPage();break;case 'tasks':view.innerHTML=allTasks();break;case 'archive':view.innerHTML=archivePage();break;case 'results':view.innerHTML=resultsPage();break;case 'preview':view.innerHTML=previewPage();break;default:view.innerHTML=home();}}
async function showTask(taskId,asArchive=false){state.task=await api(`/api/tasks/${taskId}`);state.runs=await api(`/api/tasks/${taskId}/runs`);state.reviewEvents=await api(`/api/tasks/${taskId}/review-history`);state.taskChanges=await api(`/api/tasks/${taskId}/changes`);state.historyCompare=null;state.retentionReport=null;state.run=state.runs[0]||null;state.selected=null;state.filter='全部';state.search='';if(state.run){if(asArchive){state.result=await api(`/api/tasks/${taskId}/runs/${state.run.id}/results`);setPage('archive')}else await showRun(state.run.id)}else setPage(asArchive?'archive':'results')}
async function showRun(runId){state.result=await api(`/api/tasks/${state.task.id}/runs/${runId}/results`);state.run=state.runs.find(r=>r.id===runId)||null;state.selected=state.result.results[0]?.resume_id||null;setPage('results')}
async function createRun(query='',parent=false,sourceFilter='全部'){const response=await post(`/api/tasks/${state.task.id}/runs`,{name:parent?`补充筛选 · ${query.slice(0,20)||'新条件'}`:'综合筛选',query,scope:parent?'parent':'all',parent_id:parent?state.result?.run?.id:null,source_filter:sourceFilter});state.runs=await api(`/api/tasks/${state.task.id}/runs`);await showRun(response.id);toast(`已保存筛选轮次，包含 ${response.candidate_count} 份简历`)}
nav.forEach(n=>n.addEventListener('click',()=>{const p=n.dataset.view;state.task=null;state.result=null;if(p==='home'){setPage(p);return}withBusy(async()=>{await fetchTasks();if(p==='archive')await fetchProfiles();setPage(p)})}));
async function importSelectedFiles(files){
 if(!files.length){toast('请先选择简历文件或文件夹');return}
 const summary={imported:0,duplicates:0,issues:[],warnings:[]};
 let processed=0;
 for(let i=0;i<files.length;i+=10){
   const batch=files.slice(i,i+10),form=new FormData();
   batch.forEach(file=>form.append('files',file,file.name));
   const res=await api(`/api/tasks/${state.task.id}/resumes`,{method:'POST',body:form});
   summary.imported+=res.imported;summary.duplicates+=res.duplicates;
   summary.issues.push(...(res.issues||[]));summary.warnings.push(...(res.warnings||[]));
   processed+=batch.length;state.uploadSummary=summary;
   const progress=el('importProgress');
   if(progress)progress.textContent=`已处理 ${processed}/${files.length} 个文件，成功 ${summary.imported} 份。`;
 }
 const issueNames=new Set(summary.issues.map(x=>x.filename));
 state.retryFiles=files.filter(f=>issueNames.has(f.name));
 state.stagedFiles=[];state.importRecords=await api(`/api/tasks/${state.task.id}/imports`);
 state.task=await api(`/api/tasks/${state.task.id}`);render();
 toast(`导入完成：成功 ${summary.imported} 份，重复 ${summary.duplicates} 份，异常 ${summary.issues.length} 份`);
}
view.addEventListener('change',ev=>{
 if(ev.target.id==='fileInput'||ev.target.id==='folderInput'){
   state.stagedFiles=[...ev.target.files];state.retryFiles=[];
   const hint=el('selectedFiles');if(hint)hint.textContent=`已选择 ${state.stagedFiles.length} 个文件`;
 }
});
view.addEventListener('dragover',ev=>{
 const zone=ev.target.closest?.('#resumeDropzone');if(!zone)return;
 ev.preventDefault();zone.classList.add('drag-over');
});
view.addEventListener('dragleave',ev=>{
 const zone=ev.target.closest?.('#resumeDropzone');if(zone)zone.classList.remove('drag-over');
});
view.addEventListener('drop',ev=>{
 const zone=ev.target.closest?.('#resumeDropzone');if(!zone)return;
 ev.preventDefault();zone.classList.remove('drag-over');
 state.stagedFiles=[...ev.dataTransfer.files];state.retryFiles=[];
 const hint=el('selectedFiles');if(hint)hint.textContent=`已选择 ${state.stagedFiles.length} 个文件`;
});
view.addEventListener('input',ev=>{if(ev.target.id==='candidateSearch'){state.search=ev.target.value;const cursor=ev.target.selectionStart;render();const inp=el('candidateSearch');if(inp){inp.focus();inp.setSelectionRange(cursor,cursor)}}});
view.addEventListener('click',ev=>withBusy(async()=>{
  const target=ev.target.closest('button,[data-candidate],[data-run]');if(!target)return;
  if(target.dataset.go){setPage(target.dataset.go);return;}
  if(target.dataset.task){await showTask(Number(target.dataset.task),state.page==='archive');return;}
  if(target.dataset.compare){
    const left=Number(target.dataset.compare),right=state.result?.run?.id||state.runs[0]?.id;
    if(!right||left===right){toast('请先打开另一轮筛选结果，再点击对比');return}
    state.historyCompare=await api(`/api/tasks/${state.task.id}/runs/compare?left=${left}&right=${right}`);
    render();return;
  }
  if(target.dataset.restoreCriteria){
    const fromId=Number(target.dataset.restoreCriteria);
    if(!window.confirm('恢复该轮的岗位筛选条件？会更新当前岗位配置，但不会删除或修改任何历史轮次。'))return;
    const restored=await post(`/api/tasks/${state.task.id}/runs/${fromId}/restore-criteria`,{});
    state.task=restored.task;state.taskChanges=await api(`/api/tasks/${state.task.id}/changes`);
    await fetchTasks();render();toast('岗位条件已恢复；可以开始新一轮筛选');return;
  }
  if(target.dataset.replay){
    const originalId=Number(target.dataset.replay);
    if(!window.confirm('按所选历史轮次的条件，针对当前仍保存的全部简历创建新轮次？原轮次和人工审核记录均不变。'))return;
    const created=await post(`/api/tasks/${state.task.id}/runs/${originalId}/replay`,{});
    state.runs=await api(`/api/tasks/${state.task.id}/runs`);state.historyCompare=null;
    await showRun(created.id);toast('已按历史条件建立新轮次');return;
  }
  if(target.dataset.run){await showRun(Number(target.dataset.run));return;}
  if(target.dataset.candidate){state.selected=Number(target.dataset.candidate);render();return;}
  if(target.dataset.filter){state.filter=target.dataset.filter;render();return;}
  if(target.id==='describeNext'){
    state.description=el('newDescription').value.trim();if(!state.description){toast('请先输入岗位要求');return}
    const suggestion=await post('/api/criteria/suggest',{description:state.description});
    state.required=suggestion.required;state.preferred=suggestion.preferred;state.descriptionLeads=suggestion.description_leads||[];state.excluded=[];state.matchMode='aliases';state.title='';state.editing=false;setPage('confirm');return;
  }
  if(target.id==='createTask'){
    state.title=el('jobTitle').value.trim();state.description=el('descConfirm').value.trim();state.descriptionLeads=terms(el('descClues').value);state.required=terms(el('mustTerms').value);state.preferred=terms(el('bonusTerms').value);state.excluded=terms(el('excludedTerms').value);state.matchMode=el('keywordMode').value;
    if(state.descriptionLeads.length>8){toast('描述参考线索最多保留 8 项');return}
    if(!state.title){toast('请输入岗位或任务名称');return}
    if(!state.description&&!state.required.length&&!state.preferred.length){toast('请填写招聘描述或至少一个筛选关键词');return}
    const config={title:state.title,description:state.description,description_leads:state.descriptionLeads,required:state.required,preferred:state.preferred,excluded:state.excluded,match_mode:state.matchMode};
    if(state.editing){state.task=await patch(`/api/tasks/${state.task.id}`,config);state.taskChanges=await api(`/api/tasks/${state.task.id}/changes`);state.editing=false;await fetchTasks();if(state.result?.run?.id)await showRun(state.result.run.id);else setPage('import');toast('招聘要求已更新；既有筛选记录仍保持不变');return;}
    state.task=await post('/api/tasks',config);
    state.task.resume_count=0;state.uploadSummary=null;state.importRecords=[];state.stagedFiles=[];state.retryFiles=[];await fetchTasks();setPage('import');toast('招聘任务已创建');return;
  }
  if(target.id==='editCriteria'){
    const task=state.task;state.editing=true;state.title=task.title;state.description=task.description;state.descriptionLeads=task.description_leads!==null?task.description_leads:(await post('/api/criteria/suggest',{description:task.description})).description_leads||[];state.required=[...task.required];state.preferred=[...task.preferred];state.excluded=[...task.excluded];state.matchMode=task.match_mode;setPage('confirm');return;
  }
  if(target.id==='closeCompare'){state.historyCompare=null;render();return;}
  if(target.id==='checkIntegrity'){state.diagnostics=await api('/api/system/diagnostics');render();return;}
  if(target.id==='checkRetention'){const days=Number(el('retentionDays').value);state.retentionReport=await api(`/api/tasks/${state.task.id}/retention?days=${days}`);render();return;}
  if(target.id==='uploadMore'){state.uploadSummary=null;state.stagedFiles=[];state.retryFiles=[];state.task=await api(`/api/tasks/${state.task.id}`);state.importRecords=await api(`/api/tasks/${state.task.id}/imports`);setPage('import');return;}
  if(target.id==='uploadFiles'){await importSelectedFiles(state.stagedFiles);return;}
  if(target.id==='retryIssues'){await importSelectedFiles(state.retryFiles);return;}
  if(target.id==='startScreening'||target.id==='firstScreening'){await createRun();return;}
  if(target.id==='screenAgain'){const query=el('followupQuery').value.trim();if(!query){toast('请输入补充筛选条件');return}await createRun(query,true,el('followupScope').value);return;}
  if(target.id==='openHistory'){setPage('archive');return;}
  if(target.id==='createBackup'){
    const inp=el('backupPassword');const password=inp?.value||'';
    if(password.length<12){toast('请设置至少 12 字符的备份密码');return}
    toast('正在加密招聘档案，请勿关闭窗口');
    const response=await fetch('/api/system/backup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password})});
    inp.value='';
    if(!response.ok){let error='备份失败';try{const info=await response.json();error=info.detail||error}catch{}throw new Error(error)}
    const blob=await response.blob();const url=URL.createObjectURL(blob);
    const link=document.createElement('a');link.href=url;link.download=`Huiyan-backup-${new Date().toISOString().slice(0,10)}.hyb`;
    document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
    toast('加密备份已生成，请妥善保管下载文件和密码');return;
  }
  if(target.id==='restoreBackup'){
    const file=el('restoreFile')?.files?.[0];const password=el('restorePassword')?.value||'';
    const confirm=el('restoreConfirm')?.value?.trim()||'';
    if(!file){toast('请选择 .hyb 加密备份文件');return}
    if(password.length<12){toast('请输入至少 12 字符的备份密码');return}
    if(confirm!=='恢复'){toast('请在确认框中输入“恢复”');return}
    const form=new FormData();form.append('file',file,file.name);form.append('password',password);form.append('confirm',confirm);
    toast('正在验证并恢复加密档案，请不要关闭窗口');
    const result=await api('/api/system/restore',{method:'POST',body:form});
    state.recoveryNotice=`已验证 ${result.restored_files} 份原始简历。请完全关闭并重新打开慧眼，恢复档案才会生效；原档案仍安全保留在本机。`;
    await fetchProfiles();setPage('archive');toast('恢复验证成功，请关闭后重启慧眼');return;
  }
  if(target.id==='switchOriginal'){
    if(!window.confirm('确定在下次启动时切回最初的本地档案？当前恢复档案会继续保留。'))return;
    await post('/api/system/profile/original',{});
    state.recoveryNotice='已安排切回最初的本地档案。请关闭并重新打开慧眼，当前档案不会被删除。';
    await fetchProfiles();setPage('archive');return;
  }
  if(target.id==='archiveBack'){state.task=null;setPage('archive');return;}
  if(target.id==='deleteArchivedTask'){
    if(!state.task?.archived){toast('请先归档任务');return}
    const confirmation=window.prompt(`此操作会永久删除所有简历、筛选轮次和审核记录。请输入任务完整名称确认：${state.task.title}`);
    if(confirmation!==state.task.title){toast('任务名称不一致，已取消');return}
    const response=await api(`/api/tasks/${state.task.id}`,{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm_title:confirmation})});
    state.task=null;state.result=null;state.runs=[];await fetchTasks();setPage('archive');
    toast(response.files_pending_cleanup?'记录已删除，但部分本地文件清理失败，请联系管理员':'任务与简历已彻底删除');return;
  }
  if(target.id==='toggleArchive'){state.task=await patch(`/api/tasks/${state.task.id}`,{archived:!state.task.archived});await fetchTasks();render();toast(state.task.archived?'任务已归档':'任务已恢复');return;}
  if(target.dataset.preview){state.preview=await api(`/api/tasks/${state.task.id}/resumes/${target.dataset.preview}`);setPage('preview');return;}
  if(target.dataset.deleteCandidate){
    const filename=target.dataset.filename;
    const confirmation=window.prompt('将删除这位候选人的原始文件、审核记录和所有历史筛选中的对应结果。请输入完整文件名确认：'+filename);
    if(confirmation!==filename){toast('文件名不一致，已取消删除');return}
    const result=await api(`/api/tasks/${state.task.id}/resumes/${target.dataset.deleteCandidate}`,{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm_filename:confirmation})});
    state.task=await api(`/api/tasks/${state.task.id}`);state.selected=null;await showRun(state.result.run.id);
    toast(result.files_pending_cleanup?'候选人记录已删除，但原文件清理失败，请联系管理员':'候选人及全部相关本地记录已删除');return;
  }
  if(target.dataset.saveReview){await patch(`/api/tasks/${state.task.id}/resumes/${target.dataset.saveReview}/review`,{status:el('reviewStatus').value,note:el('reviewNote').value});state.reviewEvents=await api(`/api/tasks/${state.task.id}/review-history`);await showRun(state.result.run.id);state.selected=Number(target.dataset.saveReview);render();toast('审核记录已保存');return;}
}));
withBusy(async()=>{await fetchTasks();try{state.health=await api('/api/health')}catch{state.health=null}setPage('home')});
