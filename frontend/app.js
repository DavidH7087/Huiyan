const view = document.getElementById('view');
const nav = [...document.querySelectorAll('[data-view]')];
const state = {
  page:'home', tasks:[], task:null, runs:[], run:null, result:null, selected:null,
  description:'', required:[], preferred:[], title:'', filter:'全部', busy:false, preview:null,
  currentText:null, uploadSummary:null, search:'',
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
function setPage(page){state.page=page;nav.forEach(n=>n.classList.toggle('active',n.dataset.view===page));el('breadcrumb').textContent=({home:'首页',tasks:'筛选任务',archive:'招聘档案',confirm:'确认招聘要求',import:'添加简历',results:'候选人筛选结果'})[page]||'慧眼';render()}
function badge(label,color='neutral'){return `<span class="badge ${color}">${e(label)}</span>`}
function taskCard(task){return `<button class="folder" data-task="${task.id}"><span class="folder-icon">▤</span><div class="grow"><strong>${e(task.title)}</strong><p>${task.resume_count||0} 份简历 · ${task.run_count||0} 轮筛选 · ${e(fmt(task.created_at))}</p></div>${badge(task.archived?'已归档':'进行中',task.archived?'neutral':'green')}<span class="subtle">›</span></button>`}
function home(){return `<div class="home"><div class="hero"><h1>开始简历筛选</h1><p>输入岗位要求，添加简历，快速找到值得关注的人选。</p></div>
<div class="entry"><textarea id="newDescription" placeholder="输入招聘要求，或直接粘贴岗位 JD……">${e(state.description)}</textarea><div class="entry-footer"><span class="subtle small">关键词与自然语言均可使用，下一步可修改条件</span><button id="describeNext" class="btn">下一步　→</button></div></div>
<section class="recent"><div class="section-head"><h2>最近的任务</h2><button class="btn ghost small" data-go="archive">查看全部</button></div><div class="task-list">${state.tasks.slice(0,4).map(taskCard).join('')||'<div class="empty">还没有招聘任务。从上方创建第一个任务。</div>'}</div></section></div>`}
function confirm(){return `<div class="page-title"><h1>确认筛选要求</h1><p>请检查以下条件是否正确。此版本采用本地文字证据检索，所有判断均需人工审核。</p></div>
<div class="surface"><div class="field"><label for="jobTitle">岗位或任务名称</label><input id="jobTitle" value="${e(state.title)}" placeholder="例如：销售经理招聘"></div>
<div class="field"><label for="descConfirm">招聘需求</label><textarea id="descConfirm">${e(state.description)}</textarea></div>
<div class="form-grid"><div class="field"><label for="mustTerms">必须具备</label><textarea id="mustTerms" style="min-height:110px">${e(state.required.join('、'))}</textarea><small>多个条件使用顿号分隔。未发现相关文字会标记为“需要确认”，不自动淘汰。</small></div>
<div class="field"><label for="bonusTerms">优先考虑</label><textarea id="bonusTerms" style="min-height:110px">${e(state.preferred.join('、'))}</textarea><small>这些条件有相关经历则优先显示，但并非必要条件。</small></div></div>
<div class="notice">系统对招聘描述的自动提取只是建议，尤其是“最好”“不限”等词，请在这里核对后再继续。</div>
<div class="actions" style="margin-top:22px"><button class="btn secondary" data-go="home">返回修改</button><button class="btn" id="createTask">创建任务，添加简历 →</button></div></div>`}
function importPage(){return `<div class="page-title"><h1>添加简历</h1><p>${e(state.task?.title||'')} · 可以一次添加多个文件或整个文件夹。</p></div>
<div class="surface"><div class="dropzone"><strong>选择简历文件</strong><p>支持 PDF、DOCX、TXT、ZIP；扫描件 OCR 将在后续版本支持。</p><input type="file" id="fileInput" multiple accept=".pdf,.docx,.txt,.zip"><p style="margin-top:16px">或者选择整个文件夹</p><input type="file" id="folderInput" multiple webkitdirectory directory></div>
<div class="actions" style="margin-top:18px"><button class="btn secondary" data-go="tasks">稍后添加</button><button class="btn" id="uploadFiles">导入所选简历</button></div>
${state.uploadSummary?`<div class="notice">成功导入 ${state.uploadSummary.imported} 份，重复 ${state.uploadSummary.duplicates} 份，问题文件 ${state.uploadSummary.issues.length} 份。</div>`:''}
${state.uploadSummary?.issues?.length?`<div class="notice warn">${state.uploadSummary.issues.slice(0,6).map(x=>e(x.filename+': '+x.message)).join('<br>')}</div>`:''}
<div class="divider"></div><div class="toolbar"><span>此任务已有 <strong>${state.task?.resume_count||0}</strong> 份简历</span><button class="btn" id="startScreening" ${(state.task?.resume_count||0)<1?'disabled':''}>开始筛选 →</button></div>
<p class="hint">注：默认使用本地关键词和同义词检索。配置可选的本地语义模型后，可发现更多待核实的相关经历。筛选结果不能代替 HR 判断。</p></div>`}
function allTasks(archive=false){const records=archive==='all'?state.tasks:state.tasks.filter(t=>archive?t.archived:!t.archived);return `<div class="section-head"><div><h1>${archive?'招聘档案':'筛选任务'}</h1><p class="subtle">${archive?'所有岗位和筛选历史集中管理，支持归档与恢复。':'管理当前招聘、筛选结果和人工审核。'}</p></div><button class="btn" data-go="home">+ 新建任务</button></div><div class="task-list">${records.map(taskCard).join('')||'<div class="empty">这里暂时没有招聘任务。</div>'}</div>${!archive?`<div class="subpanel"><h2 style="margin-bottom:14px">已归档</h2><div class="task-list">${state.tasks.filter(t=>t.archived).map(taskCard).join('')||'<p class="subtle small">没有已归档的任务。</p>'}</div></div>`:''}`}
function groupCounts(results){return ['优先查看','需要确认'].map(k=>({name:k,count:results.filter(r=>r.evaluation.group===k).length}));}
function resultsPage(){const run=state.result?.run;const rows=state.result?.results||[];
const visible=rows.filter(r=>(state.filter==='全部'||(state.filter==='面试名单'?r.review_status==='加入面试名单':r.evaluation.group===state.filter)) && (`${r.name} ${r.filename} ${r.evaluation.checks.map(c=>c.term).join(' ')}`.toLowerCase().includes(state.search.toLowerCase())));
const selected=visible.find(x=>x.resume_id===state.selected)||visible[0];
const counts=groupCounts(rows);
return `<div class="task-header"><div><h1>${e(state.task?.title||'筛选任务')}</h1><div class="subtle small">${e(run?.name||'尚未筛选')} · ${e(fmt(run?.created_at))}</div></div><div class="inline-actions"><button class="btn secondary small" id="uploadMore">+ 添加简历</button><button class="btn secondary small" id="toggleArchive">${state.task?.archived?'恢复任务':'归档任务'}</button>${run?`<a class="btn small" href="/api/tasks/${state.task.id}/runs/${run.id}/export">导出 Excel</a>`:''}</div></div>
<div class="stat-row"><div class="stat"><strong>${rows.length}</strong><span>本轮候选人</span></div>${counts.map(c=>`<div class="stat"><strong>${c.count}</strong><span>${c.name}</span></div>`).join('')}</div>
<div class="toolbar"><div class="left"><h2>候选人</h2><span class="subtle small">按相关文字证据排序，语义线索需人工核实</span></div><button class="btn secondary small" id="openHistory">筛选历史 (${state.runs.length})</button></div>
${run?.criteria?.semantic?.state==='error'?`<div class="notice warn">本地语义分析暂不可用，已改用基础文字匹配。请在设置中检查模型。</div>`:''}${!run?`<div class="empty"><p>还没有筛选结果。</p><button class="btn" id="firstScreening">开始第一轮筛选</button></div>`:`<div class="filters">${['全部','优先查看','需要确认','面试名单'].map(f=>`<button class="filter ${state.filter===f?'active':''}" data-filter="${e(f)}">${e(f)}</button>`).join('')}</div>
<div class="two-col"><div><div style="margin-bottom:13px"><input id="candidateSearch" placeholder="搜索候选人、文件名或条件" value="${e(state.search)}"></div>
<div class="candidate-list">${visible.map(r=>`<div class="candidate-row ${selected?.resume_id===r.resume_id?'selected':''}" data-candidate="${r.resume_id}"><header><strong>${e(r.name)}</strong>${badge(r.evaluation.group,r.evaluation.group==='优先查看'?'green':'amber')}</header><p>${e(r.filename)} · 找到 ${r.evaluation.matched_count} 项文字证据${r.evaluation.semantic_hint_count?` · ${r.evaluation.semantic_hint_count} 项语义线索`:''} · ${e(r.review_status)}</p></div>`).join('')||'<div class="empty">当前筛选条件没有候选人。</div>'}</div>
<div class="surface subpanel"><h2>继续筛选</h2><p class="hint">输入补充条件并创建新轮次，原结果不变。补充条件默认作为优先线索，不自动提高必要门槛。</p><textarea id="followupQuery" placeholder="例如：更关注有制造业客户经验的人" style="min-height:80px"></textarea><label for="followupScope">在这些候选人中继续筛选</label><select id="followupScope"><option value="全部">当前轮次全部人选</option><option value="优先查看">仅优先查看的人选</option><option value="需要确认">仅需要确认的人选</option><option value="面试名单">仅面试名单</option></select><div class="actions" style="margin-top:10px"><button class="btn secondary" id="screenAgain">创建新一轮筛选</button></div></div></div>
<aside class="surface panel">${selected?candidatePanel(selected):'<p class="subtle">选择一位候选人查看详情。</p>'}</aside></div>
<div class="subpanel"><h2>历史轮次</h2><div style="margin-top:14px">${roundsMarkup()}</div></div>`}`}
function candidatePanel(r){const checks=r.evaluation.checks;return `<h3>${e(r.name)}</h3><div class="file-details">${e(r.filename)}<br>证据覆盖率：${r.evaluation.evidence_coverage}%（并非能力分数）</div>
<div class="inline-actions"><button class="btn secondary small" data-preview="${r.resume_id}">阅读简历内容</button><a class="btn secondary small" target="_blank" rel="noopener" href="/api/tasks/${state.task.id}/resumes/${r.resume_id}/original">打开原文件</a></div>
${checks.map(c=>`<div class="evidence-item"><div class="toolbar" style="margin:0"><strong>${e(c.term)}</strong>${badge(c.evidence?'找到相关文字':'待核实',c.evidence?'green':'amber')}</div>${c.evidence?`<p>第 ${Number(c.evidence.page)} 页 · “${e(c.evidence.excerpt)}”</p>`:c.semantic_hint?`<p class="semantic-lead">可能相关的经历（第 ${Number(c.semantic_hint.page)} 页），<strong>需要人工核实</strong>： “${e(c.semantic_hint.excerpt)}”</p>`:'<p>没有找到足够的直接文字证据，不能直接判定候选人不具备该能力。</p>'}</div>`).join('')||'<div class="notice">当前任务没有配置明确筛选条件，请返回修改岗位要求。</div>'}
<div class="subpanel"><h3>人工审核</h3><label for="reviewStatus">审核状态</label><select id="reviewStatus">${['未审核','加入面试名单','需要补充资料','暂不推进'].map(v=>`<option value="${e(v)}" ${v===r.review_status?'selected':''}>${e(v)}</option>`).join('')}</select>
<label for="reviewNote">备注</label><textarea id="reviewNote" style="min-height:74px" placeholder="填写人工审核意见……">${e(r.review_note||'')}</textarea><button class="btn" style="width:100%;margin-top:12px" data-save-review="${r.resume_id}">保存审核</button></div>`}
function roundsMarkup(){return state.runs.map((r,i)=>`<div class="round-row" data-run="${r.id}"><span class="round-no">${state.runs.length-i}</span><div class="grow"><strong>${e(r.name)}</strong><p>${e(fmt(r.created_at))} · ${r.candidate_count} 人 · ${r.parent_id?'基于上一轮':'全量筛选'}${r.criteria?.source_filter&&r.criteria.source_filter!=='全部'?' · '+e(r.criteria.source_filter):''}</p></div>${state.result?.run?.id===r.id?badge('当前轮次','green'):'<span class="subtle small">查看 ›</span>'}</div>`).join('')||'<div class="empty">暂无筛选记录</div>'}
function archivePage(){if(!state.task){return allTasks("all")}return `<div class="toolbar"><button class="btn secondary small" id="archiveBack">← 所有任务</button><button class="btn small" data-go="results">查看候选人</button></div><div class="page-title"><h1>${e(state.task.title)} · 筛选档案</h1><p>每一次筛选都会单独记录条件和结果，不覆盖历史。</p></div><div class="surface"><h2 style="margin-bottom:18px">筛选轮次</h2>${roundsMarkup()}<div class="notice">筛选结果不会自动淘汰候选人；人工审核状态独立保存并保留修改记录。</div></div>`}
function previewPage(){if(!state.preview)return '<p>没有已打开的简历</p>';return `<div class="toolbar"><button class="btn secondary" data-go="results">← 返回名单</button><a class="btn small" target="_blank" rel="noopener" href="/api/tasks/${state.task.id}/resumes/${state.preview.id}/original">打开原文件</a></div><div class="page-title"><h1>${e(state.preview.filename)}</h1><p>提取的纯文本，仅供核对。PDF 可通过原文件查看。</p></div>${state.preview.pages.map(p=>`<div class="surface" style="margin-bottom:15px"><h2 style="margin-bottom:12px">第 ${Number(p.page)} 页</h2><div class="textview">${e(p.text)}</div></div>`).join('')}`}
function render(){switch(state.page){case 'home':view.innerHTML=home();break;case 'confirm':view.innerHTML=confirm();break;case 'import':view.innerHTML=importPage();break;case 'tasks':view.innerHTML=allTasks();break;case 'archive':view.innerHTML=archivePage();break;case 'results':view.innerHTML=resultsPage();break;case 'preview':view.innerHTML=previewPage();break;default:view.innerHTML=home();}}
async function showTask(taskId,asArchive=false){state.task=await api(`/api/tasks/${taskId}`);state.runs=await api(`/api/tasks/${taskId}/runs`);state.run=state.runs[0]||null;state.selected=null;state.filter='全部';state.search='';if(state.run){if(asArchive){state.result=await api(`/api/tasks/${taskId}/runs/${state.run.id}/results`);setPage('archive')}else await showRun(state.run.id)}else setPage(asArchive?'archive':'results')}
async function showRun(runId){state.result=await api(`/api/tasks/${state.task.id}/runs/${runId}/results`);state.run=state.runs.find(r=>r.id===runId)||null;state.selected=state.result.results[0]?.resume_id||null;setPage('results')}
async function createRun(query='',parent=false,sourceFilter='全部'){const response=await post(`/api/tasks/${state.task.id}/runs`,{name:parent?`补充筛选 · ${query.slice(0,20)||'新条件'}`:'综合筛选',query,scope:parent?'parent':'all',parent_id:parent?state.result?.run?.id:null,source_filter:sourceFilter});state.runs=await api(`/api/tasks/${state.task.id}/runs`);await showRun(response.id);toast(`已保存筛选轮次，包含 ${response.candidate_count} 份简历`)}
nav.forEach(n=>n.addEventListener('click',()=>{const p=n.dataset.view;state.task=null;state.result=null;setPage(p);if(p!=='home')withBusy(async()=>{await fetchTasks();render()})}));
view.addEventListener('input',ev=>{if(ev.target.id==='candidateSearch'){state.search=ev.target.value;const cursor=ev.target.selectionStart;render();const inp=el('candidateSearch');if(inp){inp.focus();inp.setSelectionRange(cursor,cursor)}}});
view.addEventListener('click',ev=>withBusy(async()=>{
  const target=ev.target.closest('button,[data-candidate],[data-run]');if(!target)return;
  if(target.dataset.go){setPage(target.dataset.go);return;}
  if(target.dataset.task){await showTask(Number(target.dataset.task),state.page==='archive');return;}
  if(target.dataset.run){await showRun(Number(target.dataset.run));return;}
  if(target.dataset.candidate){state.selected=Number(target.dataset.candidate);render();return;}
  if(target.dataset.filter){state.filter=target.dataset.filter;render();return;}
  if(target.id==='describeNext'){
    state.description=el('newDescription').value.trim();if(!state.description){toast('请先输入岗位要求');return}
    const suggestion=await post('/api/criteria/suggest',{description:state.description});
    state.required=suggestion.required;state.preferred=suggestion.preferred;state.title='';setPage('confirm');return;
  }
  if(target.id==='createTask'){
    state.title=el('jobTitle').value.trim();state.description=el('descConfirm').value.trim();state.required=terms(el('mustTerms').value);state.preferred=terms(el('bonusTerms').value);
    if(!state.title){toast('请输入岗位或任务名称');return}
    if(!state.required.length&&!state.preferred.length){toast('请至少确认一个筛选条件');return}
    state.task=await post('/api/tasks',{title:state.title,description:state.description,required:state.required,preferred:state.preferred});
    state.task.resume_count=0;state.uploadSummary=null;await fetchTasks();setPage('import');toast('招聘任务已创建');return;
  }
  if(target.id==='uploadMore'){state.uploadSummary=null;state.task=await api(`/api/tasks/${state.task.id}`);setPage('import');return;}
  if(target.id==='uploadFiles'){
    const files=[...el('fileInput').files,...el('folderInput').files];if(!files.length){toast('请先选择简历文件或文件夹');return}
    const form=new FormData();files.forEach(file=>form.append('files',file,file.name));
    const res=await api(`/api/tasks/${state.task.id}/resumes`,{method:'POST',body:form});state.uploadSummary=res;state.task=await api(`/api/tasks/${state.task.id}`);render();toast(`已导入 ${res.imported} 份，重复 ${res.duplicates} 份，异常 ${res.issues.length} 份`);return;
  }
  if(target.id==='startScreening'||target.id==='firstScreening'){await createRun();return;}
  if(target.id==='screenAgain'){const query=el('followupQuery').value.trim();if(!query){toast('请输入补充筛选条件');return}await createRun(query,true,el('followupScope').value);return;}
  if(target.id==='openHistory'){setPage('archive');return;}
  if(target.id==='archiveBack'){state.task=null;setPage('archive');return;}
  if(target.id==='toggleArchive'){state.task=await patch(`/api/tasks/${state.task.id}`,{archived:!state.task.archived});await fetchTasks();render();toast(state.task.archived?'任务已归档':'任务已恢复');return;}
  if(target.dataset.preview){state.preview=await api(`/api/tasks/${state.task.id}/resumes/${target.dataset.preview}`);setPage('preview');return;}
  if(target.dataset.saveReview){await patch(`/api/tasks/${state.task.id}/resumes/${target.dataset.saveReview}/review`,{status:el('reviewStatus').value,note:el('reviewNote').value});await showRun(state.result.run.id);state.selected=Number(target.dataset.saveReview);render();toast('审核记录已保存');return;}
}));
withBusy(async()=>{await fetchTasks();setPage('home')});
