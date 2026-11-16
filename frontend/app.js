const view = document.getElementById('view');
const nav = [...document.querySelectorAll('[data-view]')];
const state = {
  page:'home', tasks:[], task:null, runs:[], run:null, result:null, selected:null, editingName:null,
  description:'', descriptionLeads:[], required:[], preferred:[], excluded:[], matchMode:'aliases', termModes:{}, title:'', editing:false, filter:'全部', busy:false, preview:null,
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
function home(){return `<div class="home"><div class="hero"><h1>开始简历筛选</h1><p>填写岗位要求，导入简历，查看筛选结果。</p></div>
<div class="entry"><textarea id="newDescription" placeholder="输入招聘要求，或直接粘贴岗位 JD……">${e(state.description)}</textarea><div class="entry-footer"><span class="subtle small">下一步可调整筛选条件</span><button id="describeNext" class="btn">下一步　→</button></div></div>
<section class="recent"><div class="section-head"><h2>最近的任务</h2><button class="btn ghost small" data-go="archive">查看全部</button></div><div class="task-list">${state.tasks.slice(0,4).map(taskCard).join('')||'<div class="empty">还没有招聘任务。从上方创建第一个任务。</div>'}</div></section></div>`}
function confirm(){return `<div class="page-title"><h1>${state.editing?'编辑招聘要求':'确认筛选要求'}</h1><p>核对岗位要求和筛选条件。</p></div>
<div class="surface"><div class="field"><label for="jobTitle">岗位或任务名称</label><input id="jobTitle" value="${e(state.title)}" placeholder="例如：销售经理招聘"></div>
<div class="field"><label for="descConfirm">招聘需求</label><textarea id="descConfirm">${e(state.description)}</textarea></div>
<div class="field"><label for="descClues">其他检索线索</label><textarea id="descClues" style="min-height:76px" placeholder="从岗位描述提取的线索">${e(state.descriptionLeads.join('、'))}</textarea><small>可直接修改，最多 8 项。</small></div>
<div class="form-grid"><div class="field"><label for="mustTerms">必须具备</label><textarea id="mustTerms" style="min-height:110px">${e(state.required.join('、'))}</textarea><small>多个条件用顿号分隔。</small></div>
<div class="field"><label for="bonusTerms">优先考虑</label><textarea id="bonusTerms" style="min-height:110px">${e(state.preferred.join('、'))}</textarea><small>符合的候选人优先展示。</small></div></div>
<div class="form-grid"><div class="field"><label for="excludedTerms">排除条件</label><textarea id="excludedTerms" style="min-height:72px" placeholder="例如：仅短期兼职、未独立负责">${e(state.excluded.join('、'))}</textarea><small>用于标记不符合岗位要求的描述，不自动排除。</small></div>
<div class="field"><label for="keywordMode">匹配方式</label><select id="keywordMode"><option value="aliases" ${state.matchMode==='aliases'?'selected':''}>包含同义词</option><option value="exact" ${state.matchMode==='exact'?'selected':''}>仅匹配原词</option></select><small>仅影响文字检索。</small></div></div>
<details class="audit-log"><summary>高级设置</summary><p class="hint">需精确匹配的条件，以顿号分隔。</p><textarea id="exactTerms" style="min-height:70px" placeholder="例如：Java、ISO9001">${e(Object.keys(state.termModes).filter(k=>state.termModes[k]==='exact').join('、'))}</textarea></details>
<div class="notice">提交前请检查筛选条件。</div>
<div class="actions" style="margin-top:22px"><button class="btn secondary" data-go="home">返回修改</button><button class="btn" id="createTask">${state.editing?'保存条件':'创建任务'}</button></div></div>`}
function importPage(){return `<div class="page-title"><h1>添加简历</h1><p>${e(state.task?.title||'')} · 可以一次添加多个文件或整个文件夹。</p></div>
<div class="surface"><div class="dropzone" id="resumeDropzone"><strong>选择文件，或将简历拖到这里</strong><p>支持 PDF、DOCX、TXT、ZIP；${state.health?.ocr?.state==='ready' ? '支持扫描版简历识别。' : '扫描版简历识别暂不可用。'}</p><input type="file" id="fileInput" multiple accept=".pdf,.docx,.txt,.zip"><p style="margin-top:16px">或者选择整个文件夹</p><input type="file" id="folderInput" multiple webkitdirectory directory><p id="selectedFiles" class="hint">${state.stagedFiles.length?'已选择 '+state.stagedFiles.length+' 个文件':'尚未选择文件'}</p></div>
${state.health?.ocr ? `<p class="hint">${state.health.ocr.state==='ready'?'支持扫描版简历':'扫描件识别暂不可用，请使用文字版简历'}</p>` : ''}<p id="importProgress" class="hint" role="status" aria-live="polite"></p><div class="actions" style="margin-top:18px"><button class="btn secondary" data-go="tasks">稍后添加</button><button class="btn" id="uploadFiles">导入所选简历</button></div>
${state.uploadSummary?`<div class="notice">成功导入 ${state.uploadSummary.imported} 份，重复 ${state.uploadSummary.duplicates} 份，问题文件 ${state.uploadSummary.issues.length} 份，需核对 ${state.uploadSummary.warnings?.length||0} 份。</div>`:''}
${state.uploadSummary?.issues?.length?`<div class="notice warn">${state.uploadSummary.issues.slice(0,6).map(x=>e(x.filename+': '+x.message)).join('<br>')}</div>`:''}
${state.uploadSummary?.warnings?.length?`<div class="notice warn">${state.uploadSummary.warnings.slice(0,8).map(x=>e(x.filename+': '+x.message)).join('<br>')}</div>`:''}${state.retryFiles.length?'<button class="btn secondary small" id="retryIssues">重试本次失败的文件</button>':''}
<details class="audit-log"><summary>导入记录</summary>${state.importRecords.map(x=>`<p>${e(fmt(x.created_at))} · ${e(x.state)} · ${e(x.filename)}${x.message?' · '+e(x.message):''}</p>`).join('')||'<p>暂无记录</p>'}</details><div class="divider"></div><div class="toolbar"><span>此任务已有 <strong>${state.task?.resume_count||0}</strong> 份简历</span><button class="btn" id="startScreening" ${(state.task?.resume_count||0)<1?'disabled':''}>开始筛选 →</button></div>
<p class="hint">筛选结果用于辅助人工审核。</p></div>`}
function allTasks(archive=false){const records=archive==='all'?state.tasks:state.tasks.filter(t=>archive?t.archived:!t.archived);return `<div class="section-head"><div><h1>${archive?'招聘档案':'筛选任务'}</h1><p class="subtle">${archive?'所有岗位和筛选历史集中管理，支持归档与恢复。':'管理当前招聘、筛选结果和人工审核。'}</p></div><button class="btn" data-go="home">+ 新建任务</button></div><div class="task-list">${records.map(taskCard).join('')||'<div class="empty">这里暂时没有招聘任务。</div>'}</div>${!archive?`<div class="subpanel"><h2 style="margin-bottom:14px">已归档</h2><div class="task-list">${state.tasks.filter(t=>t.archived).map(taskCard).join('')||'<p class="subtle small">没有已归档的任务。</p>'}</div></div>`:''}`}
function groupCounts(results){return ['优先查看','需要确认'].map(k=>({name:k,count:results.filter(r=>r.evaluation.group===k).length}));}
function resultsPage(){const run=state.result?.run;const rows=state.result?.results||[];
const visible=rows.filter(r=>(state.filter==='全部'||(state.filter==='面试名单'?r.review_status==='加入面试名单':r.evaluation.group===state.filter)) && (`${r.name} ${r.filename} ${r.evaluation.checks.map(c=>c.term).join(' ')}`.toLowerCase().includes(state.search.toLowerCase())));
const selected=visible.find(x=>x.resume_id===state.selected)||visible[0];
const counts=groupCounts(rows);
return `<div class="task-header"><div><h1>${e(state.task?.title||'筛选任务')}</h1><div class="subtle small">${e(run?.name||'尚未筛选')} · ${e(fmt(run?.created_at))}</div></div><div class="inline-actions"><button class="btn secondary small" id="uploadMore">+ 添加简历</button><button class="btn secondary small" id="editCriteria">编辑岗位条件</button><button class="btn secondary small" id="toggleArchive">${state.task?.archived?'恢复任务':'归档任务'}</button>${run?`<button class="btn small" id="exportExcel">导出 Excel</button>`:''}</div></div>
<div class="stat-row"><div class="stat"><strong>${rows.length}</strong><span>本轮候选人</span></div>${counts.map(c=>`<div class="stat"><strong>${c.count}</strong><span>${c.name}</span></div>`).join('')}</div>
<div class="toolbar"><div class="left"><h2>候选人</h2><span class="subtle small">按条件相关性排序</span></div><button class="btn secondary small" id="openHistory">筛选历史 · ${state.runs.length}</button></div>
${run?.criteria?.removed_legacy_terms?.length?`<div class="notice">已清理旧筛选条件：${e(run.criteria.removed_legacy_terms.join('、'))}。历史记录不变。</div>`:''}${run?.criteria?.semantic?.state==='error'?`<div class="notice warn">语义检索未启用，当前使用文字匹配。</div>`:''}${!run?`<div class="empty"><p>还没有筛选结果。</p><button class="btn" id="firstScreening">开始第一轮筛选</button></div>`:`<div class="filters">${['全部','优先查看','需要确认','面试名单'].map(f=>`<button class="filter ${state.filter===f?'active':''}" data-filter="${e(f)}">${e(f)}</button>`).join('')}</div>
<div class="two-col"><div><div style="margin-bottom:13px"><input id="candidateSearch" placeholder="搜索候选人、文件名或条件" value="${e(state.search)}"></div>
<div class="candidate-list">${visible.map(r=>`<div class="candidate-row ${selected?.resume_id===r.resume_id?'selected':''}" data-candidate="${r.resume_id}"><header><strong>${e(r.name)}</strong>${badge(r.evaluation.group,r.evaluation.group==='优先查看'?'green':'amber')}${r.possible_duplicate_with?.length?badge('疑似重复','amber'):''}</header><p>${e(r.filename)} · 找到 ${r.evaluation.matched_count} 项文字证据${r.evaluation.semantic_hint_count?` · ${r.evaluation.semantic_hint_count} 项语义线索`:''}${r.evaluation.exclusion_flags?` · ${r.evaluation.exclusion_flags} 项排除线索待核实`:''} · ${e(r.review_status)}</p></div>`).join('')||'<div class="empty">当前筛选条件没有候选人。</div>'}</div>
<div class="surface subpanel"><h2>继续筛选</h2><p class="hint">补充筛选条件，生成新轮次。原结果保留。</p><textarea id="followupQuery" placeholder="例如：更关注有制造业客户经验的人" style="min-height:80px"></textarea><label for="followupScope">筛选范围</label><select id="followupScope"><option value="全部">当前轮次全部人选</option><option value="优先查看">仅优先查看的人选</option><option value="需要确认">仅需要确认的人选</option><option value="面试名单">仅面试名单</option></select><div class="actions" style="margin-top:10px"><button class="btn secondary" id="screenAgain">创建新一轮筛选</button></div></div></div>
<aside class="surface panel">${selected?candidatePanel(selected):'<p class="subtle">选择一位候选人查看详情。</p>'}</aside></div>
<div class="subpanel"><h2>历史轮次</h2><div style="margin-top:14px">${roundsMarkup()}</div></div>${comparisonMarkup()}`}`}
function retentionMarkup(){
 const report=state.retentionReport;if(!report)return '';
 return `<div class="notice"><strong>${report.days} 天以上的简历：${report.due_count} 份</strong><p>该清单仅供检查，不会自动删除数据。</p>
 ${report.candidates.slice(0,30).map(c=>`<p>${e(c.name)} · ${e(c.filename)} · 导入于 ${e(fmt(c.imported_at))}</p>`).join('')}
 ${report.due_count>30?'<p>还有更多候选人未在此处列出，可在完整名单查看。</p>':''}</div>`;
}
function comparisonMarkup(){
 const report=state.historyCompare;if(!report)return '';
 const labels=(records,empty)=>records.length?records.slice(0,12).map(r=>e(r.name+' · '+r.filename)).join('、'):empty;
 return `<div class="surface subpanel"><div class="toolbar"><h2>筛选轮次对比</h2><button class="btn ghost small" id="closeCompare">关闭对比</button></div>
 <p class="hint">${e(report.left.name)} → ${e(report.right.name)}，比较的是各轮保存的筛选证据，不是今天的审核状态。</p>
 <div class="stat-row"><div class="stat"><strong>${Number(report.same)}</strong><span>共同候选人</span></div><div class="stat"><strong>${Number(report.added_count)}</strong><span>新增候选人</span></div><div class="stat"><strong>${Number(report.removed_count)}</strong><span>不再出现</span></div><div class="stat"><strong>${Number(report.changed_group_count)}</strong><span>分组变化</span></div></div>
 <p class="hint">新增：${labels(report.added,'无')}；未包含：${labels(report.removed,'无')}</p>
 <p class="hint">分组变动：${report.changed.length?report.changed.slice(0,12).map(v=>e(v.name+'：'+v.before+' → '+v.after)).join('；'):'无'}</p>
 <p class="hint">显示前 100 项变化，原记录不变。</p></div>`;
}
function candidatePanel(r){
 const checks=r.evaluation.checks||[];
 const considered=checks.filter(c=>c.kind!=='excluded');
 const matched=considered.filter(c=>!!c.evidence).length;
 const editing=state.editingName===r.resume_id;
 const unconfirmed=r.name_source==='unknown';
 return `<div class="person-panel-head"><div><h3>${e(r.name)}</h3><p class="person-filename">${e(r.filename)}</p></div><button class="btn ghost small" data-edit-name="${r.resume_id}">修改姓名</button></div>
 ${unconfirmed?'<p class="quiet-note">未从简历中找到姓名，请核对后填写。</p>':''}
 ${editing?`<div class="name-editor"><label for="candidateNameInput">应聘人姓名</label><input id="candidateNameInput" maxlength="60" value="${e(unconfirmed?'':r.name)}" placeholder="请输入简历上的姓名"><div class="inline-actions"><button class="btn small" data-save-name="${r.resume_id}">保存姓名</button><button class="btn secondary small" id="cancelEditName">取消</button></div></div>`:''}
 <div class="candidate-quick-info">${r.phone?`<span>电话：${e(r.phone)}</span>`:''}${r.email?`<span>邮箱：${e(r.email)}</span>`:''}</div>
 <div class="evidence-summary"><span>文字匹配 <strong>${matched} / ${considered.length}</strong></span><span>覆盖率 <strong>${Number(r.evaluation.evidence_coverage)}%</strong></span></div>
 ${r.possible_duplicate_with?.length?`<p class="quiet-note">发现 ${r.possible_duplicate_with.length} 份联系方式相同的简历，可在完整资料中核对。</p>`:''}
 ${r.ocr_pages||r.parse_warnings?'<p class="quiet-note">部分内容可能识别不完整，请留意下方原文。</p>':''}
 ${r.evaluation.exclusion_flags?`<p class="quiet-note">发现 ${Number(r.evaluation.exclusion_flags)} 项排除线索，请核对具体内容。</p>`:''}
 <button class="btn secondary" data-preview="${r.resume_id}">查看简历详情</button>
 <div class="section-divider"><h3>条件匹配</h3></div>
 ${checks.map(c=>`<div class="evidence-item"><div class="toolbar" style="margin:0"><strong>${e(c.term)}</strong>${badge(c.evidence?'找到文字':c.negative_evidence?'否定表述':c.semantic_hint?'相近内容':'未找到',c.evidence?'green':'neutral')}</div>${c.evidence?`<p class="proof-source">第 ${Number(c.evidence.page)} 页</p><p class="proof-excerpt">${e(c.evidence.excerpt)}</p>`:c.negative_evidence?`<p class="proof-source">否定表述 · 第 ${Number(c.negative_evidence.page)} 页</p><p class="proof-excerpt">${e(c.negative_evidence.excerpt)}</p>`:c.semantic_hint?`<p class="proof-source">相近内容 · 第 ${Number(c.semantic_hint.page)} 页</p><p class="proof-excerpt">${e(c.semantic_hint.excerpt)}</p>`:'<p class="muted-copy">未找到直接相关的文字。</p>'}</div>`).join('')||'<p class="muted-copy">尚未设置筛选条件。</p>'}
 <div class="subpanel"><h3>审核记录</h3>${r.review_at_run?`<p class="hint">本轮创建时：${e(r.review_at_run.status)} · 当前：${e(r.review_status)}</p>`:'<p class="hint">本轮未保存早期审核状态。</p>'}
 <label for="reviewStatus">审核状态</label><select id="reviewStatus">${['未审核','加入面试名单','需要补充资料','暂不推进'].map(v=>`<option value="${e(v)}" ${v===r.review_status?'selected':''}>${e(v)}</option>`).join('')}</select>
 <label for="reviewNote">备注</label><textarea id="reviewNote" style="min-height:74px" placeholder="填写审核意见">${e(r.review_note||'')}</textarea>
 <button class="btn" style="width:100%;margin-top:12px" data-save-review="${r.resume_id}">保存审核</button>
 <details class="subtle-action"><summary>资料管理</summary><p class="hint">删除后无法恢复，相关筛选记录也会更新。</p><button class="btn secondary small" id="deleteCandidate" data-delete-candidate="${r.resume_id}" data-filename="${e(r.filename)}">永久删除该应聘人</button></details></div>`;
}
function roundsMarkup(){return state.runs.map((r,i)=>`<div class="round-row" data-run="${r.id}"><span class="round-no">${state.runs.length-i}</span><div class="grow"><strong>${e(r.name)}</strong><p>${e(fmt(r.created_at))} · ${r.candidate_count} 人 · ${r.parent_id?'基于上一轮':'全量筛选'}${r.criteria?.source_filter&&r.criteria.source_filter!=='全部'?' · '+e(r.criteria.source_filter):''}</p></div>${state.result?.run?.id===r.id?badge('当前轮次','green'):'<span class="subtle small">查看 ›</span>'}<button class="btn secondary small" data-compare="${r.id}" aria-label="与当前轮次比较">对比</button><button class="btn secondary small" data-replay="${r.id}" aria-label="复用本轮条件">复用条件</button><button class="btn secondary small" data-restore-criteria="${r.id}" aria-label="恢复本轮岗位条件">恢复条件</button></div>`).join('')||'<div class="empty">暂无筛选记录</div>'}
function baseArchivePage(){if(!state.task){return allTasks("all") + (state.health?.backup_available?`<div class="surface subpanel"><h2>加密备份招聘档案</h2><p class="hint">导出全部招聘任务、审核记录及原始简历。请妥善保存备份密码；遗失后无法恢复。</p><div class="actions" style="margin-top:12px"><input id="backupPassword" type="password" autocomplete="new-password" placeholder="设置至少 12 字符的备份密码" style="max-width:330px" aria-label="备份密码"><button class="btn secondary" id="createBackup">创建并下载加密备份</button></div><p class="hint">备份包含招聘资料，请妥善保管。</p></div>`:'')}return `<div class="toolbar"><button class="btn secondary small" id="archiveBack">← 所有任务</button><button class="btn small" data-go="results">查看候选人</button></div><div class="page-title"><h1>${e(state.task.title)} · 筛选档案</h1><p>保留各轮筛选条件和结果。</p></div><div class="surface"><h2 style="margin-bottom:18px">筛选轮次</h2><div class="actions" style="margin-bottom:14px"><label for="retentionDays">待复核资料期限</label><select id="retentionDays"><option value="180">180 天</option><option value="365" selected>365 天</option><option value="730">730 天</option></select><button class="btn secondary small" id="checkRetention">检查旧简历</button><button class="btn secondary small" id="editCriteria">编辑岗位条件</button></div>${retentionMarkup()}${roundsMarkup()}${comparisonMarkup()}<details class="audit-log"><summary>岗位条件记录</summary>${(state.taskChanges||[]).map(v=>`<p>${e(fmt(v.occurred_at))} · ${e(v.action.startsWith('restore_round:')?'恢复历史条件':'编辑岗位条件')} · 必须：${e((v.previous.required||[]).join('、')||'无')} → ${e((v.next.required||[]).join('、')||'无')}</p>`).join('')||'<p>暂无修改记录</p>'}</details><details class="audit-log"><summary>审核操作记录</summary>${(state.reviewEvents||[]).map(v=>`<p>${e(fmt(v.occurred_at))} · ${e(v.name||'候选人')} · ${e(v.status)}${v.note?' · '+e(v.note):''}</p>`).join('')||'<p>暂无操作记录</p>'}</details><div class="notice">筛选依据保留历史快照；人工审核当前状态可更新，每轮创建时的审核状态独立记录。</div>${state.task.archived?'<div class="actions" style="margin-top:16px"><button class="btn secondary small" id="deleteArchivedTask">永久删除任务及全部简历（不可恢复）</button></div>':''}</div>`}
function archivePage(){
  const original=baseArchivePage();
  if(state.task || !state.health?.restore_available)return original;
  const profile=state.profileStatus||{};
  const notice=state.recoveryNotice?`<div class="notice">${e(state.recoveryNotice)}</div>`:'';
  const pending=profile.pending_profile?`<div class="notice warn">新的招聘档案已准备好。请完全关闭并重新打开慧眼后生效。</div>`:'';
  const switchBack=profile.can_return_to_original && !profile.pending_profile
    ? '<button class="btn secondary small" id="switchOriginal">下次启动切回最初档案</button>' : '';
  return original+`<div class="surface subpanel"><h2>恢复加密招聘档案</h2>
    <p class="hint">导入此前创建的加密备份。恢复为独立档案，不覆盖当前记录。重启后生效。</p>
    <div class="field"><label for="restoreFile">加密备份文件</label><input type="file" id="restoreFile" accept=".hyb,application/octet-stream"></div>
    <div class="actions" style="margin-top:12px"><input id="restorePassword" type="password" autocomplete="off" placeholder="原备份密码" aria-label="恢复密码" style="max-width:300px"><input id="restoreConfirm" placeholder="输入“恢复”确认" aria-label="恢复确认" style="max-width:180px"><button class="btn secondary" id="restoreBackup">恢复备份</button></div>
    <p class="hint">密码不保存。请妥善保管备份文件。</p>
    ${pending}${notice}${switchBack}</div><div class="surface subpanel"><h2>本地数据完整性</h2><p class="hint">检查本地招聘资料是否完整，不会修改数据。</p><button class="btn secondary small" id="checkIntegrity">检查本地数据</button>${state.diagnostics?`<p class="hint">${e(state.diagnostics.message)} · 简历 ${Number(state.diagnostics.resume_count||0)} · 缺失文件 ${Number(state.diagnostics.missing_files)} · 多余文件 ${Number(state.diagnostics.orphan_files)}</p>`:''}</div>`;
}
function previewPage(){
 if(!state.preview)return '<p class="empty">请选择一份简历。</p>';
 const doc=state.preview,p=doc.profile||{};
 const sourceTag=ref=>ref?.evidence?.page||ref?.page||1;
 const factItems=(items,empty)=>items.length?items.map(item=>`<div class="resume-fact"><strong>${e(item.label)}</strong><span>第 ${Number(sourceTag(item))} 页</span>${item.evidence?.excerpt?`<p>${e(item.evidence.excerpt)}</p>`:''}</div>`).join(''):`<p class="muted-copy">${empty}</p>`;
 const years=(p.experience_duration_mentions||[]);
 const totalYears=[...new Set(years.filter(v=>v.scope==='total').map(v=>v.years))];
 const roleYears=[...new Set(years.filter(v=>v.scope==='specific').map(v=>v.years))];
 const yearList=arr=>arr.length?arr.map(v=>e(v)+' 年').join('、'):'未提及';
 const experiences=(p.experience_mentions||[]).slice(0,12);
 const hasWarnings=doc.pages.some(page=>page.warning||page.source==='ocr');
 return `<div class="toolbar"><button class="btn secondary" data-go="results">← 返回候选人</button></div>
 <div class="resume-header"><h1>${e(doc.name)}</h1><p class="subtle">${e(doc.filename)}</p>${doc.name_source==='unknown'?'<p class="quiet-note">姓名尚未识别，请返回候选人列表核对。</p>':''}
 <div class="resume-contact">${doc.phone?`<span>电话　${e(doc.phone)}</span>`:''}${doc.email?`<span>邮箱　${e(doc.email)}</span>`:''}</div></div>
 ${hasWarnings?'<p class="quiet-note">部分文字来自扫描识别或存在缺失，请核对内容。</p>':''}
 <div class="resume-sections">
   <section class="surface resume-section"><h2>工作经验</h2><div class="resume-stats"><div><span>工作年限</span><strong>${yearList(totalYears)}</strong></div><div><span>岗位相关经验</span><strong>${yearList(roleYears)}</strong></div></div>
   ${p.experience_years_conflict?'<p class="quiet-note">简历出现不同年限描述，请核对。</p>':''}
   <h3 class="resume-minor-heading">经历摘录</h3>
   ${experiences.length?experiences.map(x=>`<div class="resume-quote"><span>第 ${Number(x.page||1)} 页</span><p>${e(x.excerpt)}</p></div>`).join(''):'<p class="muted-copy">未找到明确的工作经历描述。</p>'}</section>
   <section class="surface resume-section"><h2>学历</h2>${factItems((p.education_mentions||[]).slice(0,10),'未找到学历信息。')}</section>
   <section class="surface resume-section"><h2>专业技能</h2>${factItems((p.skill_mentions||[]).slice(0,20),'未找到可识别的技能关键词。')}</section>
 </div>
 <section class="surface resume-section"><h2>简历文本</h2><p class="subtle small">按原文顺序展示，点击页码可展开或收起。</p>
 ${doc.pages.map((page,index)=>`<details class="resume-source" ${index===0?'open':''}><summary>第 ${Number(page.page)} 页${page.source==='ocr'?' · 扫描识别':''}</summary>${page.warning?`<p class="quiet-note">${e(page.warning)}</p>`:''}<div class="resume-text">${e(page.text||'未提取到文字')}</div></details>`).join('')}</section>`;
}
function render(){switch(state.page){case 'home':view.innerHTML=home();break;case 'confirm':view.innerHTML=confirm();break;case 'import':view.innerHTML=importPage();break;case 'tasks':view.innerHTML=allTasks();break;case 'archive':view.innerHTML=archivePage();break;case 'results':view.innerHTML=resultsPage();break;case 'preview':view.innerHTML=previewPage();break;default:view.innerHTML=home();}}
async function showTask(taskId,asArchive=false){state.task=await api(`/api/tasks/${taskId}`);state.runs=await api(`/api/tasks/${taskId}/runs`);state.reviewEvents=await api(`/api/tasks/${taskId}/review-history`);state.taskChanges=await api(`/api/tasks/${taskId}/changes`);state.historyCompare=null;state.retentionReport=null;state.run=state.runs[0]||null;state.selected=null;state.filter='全部';state.search='';if(state.run){if(asArchive){state.result=await api(`/api/tasks/${taskId}/runs/${state.run.id}/results`);setPage('archive')}else await showRun(state.run.id)}else setPage(asArchive?'archive':'results')}
async function showRun(runId){state.editingName=null;state.result=await api(`/api/tasks/${state.task.id}/runs/${runId}/results`);state.run=state.runs.find(r=>r.id===runId)||null;state.selected=state.result.results[0]?.resume_id||null;setPage('results')}
async function exportExcel(){
  if(!state.task||!state.result?.run)throw new Error('请先选择筛选轮次');
  const taskId=state.task.id,runId=state.result.run.id;
  if(window.pywebview?.api?.export_excel){
    toast('请选择 Excel 文件保存位置');
    const response=await window.pywebview.api.export_excel(taskId,runId);
    if(response?.cancelled){toast('已取消 Excel 导出');return}
    if(!response?.ok)throw new Error(response?.message||'Excel 保存失败');
    toast('Excel 已保存到所选目录：'+response.filename);
    return;
  }
  toast('正在生成 Excel 文件');
  const response=await fetch('/api/tasks/'+taskId+'/runs/'+runId+'/export');
  if(!response.ok)throw new Error('Excel 生成失败，错误码 '+response.status);
  const blob=await response.blob();
  if(blob.size<150)throw new Error('Excel 文件为空或异常');
  const buffer=await blob.slice(0,4).arrayBuffer();
  const signature=new Uint8Array(buffer);
  if(signature[0]!==0x50||signature[1]!==0x4b)throw new Error('导出内容不是有效的 Excel 文件');
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;a.download='Huiyan-task-'+taskId+'-run-'+runId+'.xlsx';
  document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),30000);
  toast('Excel 已交给浏览器下载，请查看下载记录');
}
async function createRun(query='',parent=false,sourceFilter='全部'){const response=await post(`/api/tasks/${state.task.id}/runs`,{name:parent?`补充筛选 · ${query.slice(0,20)||'新条件'}`:'综合筛选',query,scope:parent?'parent':'all',parent_id:parent?state.result?.run?.id:null,source_filter:sourceFilter});state.runs=await api(`/api/tasks/${state.task.id}/runs`);await showRun(response.id);window.scrollTo({top:0,behavior:'smooth'});toast(`已保存筛选轮次，包含 ${response.candidate_count} 份简历`)}
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
    await fetchTasks();render();toast(restored.removed_legacy_terms?.length?'岗位条件已恢复，忽略旧版无效参考：'+restored.removed_legacy_terms.join('、'):'岗位条件已恢复；可以开始新一轮筛选');return;
  }
  if(target.dataset.replay){
    const originalId=Number(target.dataset.replay);
    if(!window.confirm('按所选历史轮次的条件，针对当前仍保存的全部简历创建新轮次？原轮次和人工审核记录均不变。'))return;
    const created=await post(`/api/tasks/${state.task.id}/runs/${originalId}/replay`,{});
    state.runs=await api(`/api/tasks/${state.task.id}/runs`);state.historyCompare=null;
    await showRun(created.id);window.scrollTo({top:0,behavior:'smooth'});toast(created.criteria?.removed_legacy_terms?.length?'已复用历史条件，并清理无效参考：'+created.criteria.removed_legacy_terms.join('、'):'已按历史条件建立新轮次');return;
  }
  if(target.dataset.run){await showRun(Number(target.dataset.run));return;}
  if(target.dataset.candidate){state.selected=Number(target.dataset.candidate);state.editingName=null;render();return;}
  if(target.dataset.editName){state.editingName=Number(target.dataset.editName);render();el('candidateNameInput')?.focus();return;}
  if(target.id==='cancelEditName'){state.editingName=null;render();return;}
  if(target.dataset.saveName){
    const name=el('candidateNameInput')?.value.trim()||'';
    if(!name){toast('请输入姓名');return}
    const id=Number(target.dataset.saveName);
    await patch(`/api/tasks/${state.task.id}/resumes/${id}/name`,{name});
    state.editingName=null;await showRun(state.result.run.id);state.selected=id;render();
    toast('姓名已更新');return;
  }
  if(target.dataset.filter){state.filter=target.dataset.filter;render();return;}
  if(target.id==='describeNext'){
    state.description=el('newDescription').value.trim();if(!state.description){toast('请先输入岗位要求');return}
    const suggestion=await post('/api/criteria/suggest',{description:state.description});
    state.required=suggestion.required;state.preferred=suggestion.preferred;state.descriptionLeads=suggestion.description_leads||[];state.excluded=[];state.matchMode='aliases';state.termModes={};state.title='';state.editing=false;setPage('confirm');return;
  }
  if(target.id==='createTask'){
    state.title=el('jobTitle').value.trim();state.description=el('descConfirm').value.trim();state.descriptionLeads=terms(el('descClues').value);state.required=terms(el('mustTerms').value);state.preferred=terms(el('bonusTerms').value);state.excluded=terms(el('excludedTerms').value);state.matchMode=el('keywordMode').value;state.termModes=Object.fromEntries(terms(el('exactTerms').value).map(x=>[x,'exact']));
    if(Object.keys(state.termModes).length>80){toast('精确匹配条件最多 80 项');return}
    if(state.descriptionLeads.length>8){toast('描述参考线索最多保留 8 项');return}
    if(!state.title){toast('请输入岗位或任务名称');return}
    if(!state.description&&!state.required.length&&!state.preferred.length){toast('请填写招聘描述或至少一个筛选关键词');return}
    const config={title:state.title,description:state.description,description_leads:state.descriptionLeads,required:state.required,preferred:state.preferred,excluded:state.excluded,match_mode:state.matchMode,term_modes:state.termModes};
    if(state.editing){state.task=await patch(`/api/tasks/${state.task.id}`,config);state.taskChanges=await api(`/api/tasks/${state.task.id}/changes`);state.editing=false;await fetchTasks();if(state.result?.run?.id)await showRun(state.result.run.id);else setPage('import');toast('招聘要求已更新；既有筛选记录仍保持不变');return;}
    state.task=await post('/api/tasks',config);
    state.task.resume_count=0;state.uploadSummary=null;state.importRecords=[];state.stagedFiles=[];state.retryFiles=[];await fetchTasks();setPage('import');toast('招聘任务已创建');return;
  }
  if(target.id==='editCriteria'){
    const task=state.task;state.editing=true;state.title=task.title;state.description=task.description;state.descriptionLeads=task.description_leads!==null?task.description_leads:(await post('/api/criteria/suggest',{description:task.description})).description_leads||[];state.required=[...task.required];state.preferred=[...task.preferred];state.excluded=[...task.excluded];state.matchMode=task.match_mode;state.termModes={...task.term_modes};setPage('confirm');return;
  }
  if(target.id==='closeCompare'){state.historyCompare=null;render();return;}
  if(target.id==='checkIntegrity'){state.diagnostics=await api('/api/system/diagnostics');render();return;}
  if(target.id==='checkRetention'){const days=Number(el('retentionDays').value);state.retentionReport=await api(`/api/tasks/${state.task.id}/retention?days=${days}`);render();return;}
  if(target.id==='uploadMore'){state.uploadSummary=null;state.stagedFiles=[];state.retryFiles=[];state.task=await api(`/api/tasks/${state.task.id}`);state.importRecords=await api(`/api/tasks/${state.task.id}/imports`);setPage('import');return;}
  if(target.id==='uploadFiles'){await importSelectedFiles(state.stagedFiles);return;}
  if(target.id==='retryIssues'){await importSelectedFiles(state.retryFiles);return;}
  if(target.id==='exportExcel'){await exportExcel();return;}
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
    toast(result.files_pending_cleanup?'候选人记录已删除，但导入文件清理失败，请联系管理员':'候选人及全部相关本地记录已删除');return;
  }
  if(target.dataset.saveReview){await patch(`/api/tasks/${state.task.id}/resumes/${target.dataset.saveReview}/review`,{status:el('reviewStatus').value,note:el('reviewNote').value});state.reviewEvents=await api(`/api/tasks/${state.task.id}/review-history`);await showRun(state.result.run.id);state.selected=Number(target.dataset.saveReview);render();toast('审核记录已保存');return;}
}));
withBusy(async()=>{await fetchTasks();try{state.health=await api('/api/health')}catch{state.health=null}setPage('home')});
