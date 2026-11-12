'use strict';
const API = window.LINKEDCODE_API_URL || (location.pathname.startsWith('/app') ? location.origin : 'http://127.0.0.1:8000');
const $ = id => document.getElementById(id);
const state = {token: sessionStorage.getItem('linkedcode-token'), user: null, registering: false, generated: [], recommendations: [], tab: 'generated', generating: false};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const title = slug => slug.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
const date = value => value ? new Date(value).toLocaleDateString(undefined, {month:'short',day:'numeric',year:'numeric'}) : '';
function notice(message, error = false) {
  $('notice').innerHTML = message ? `<span class="notice-icon" aria-hidden="true">${error?'!':'✓'}</span><span class="notice-message">${esc(message)}</span><button type="button" aria-label="Dismiss notification">×</button>` : '';
  $('notice').className = error ? 'error' : ''; $('notice').hidden = !message;
}
$('notice').addEventListener('click',event=>{if(event.target.closest('button'))notice('');});
function analysisEmpty() {
  return '<div class="empty-state"><span class="empty-icon" aria-hidden="true">◴</span><strong>Your patterns, brought into focus.</strong><p>Refresh analysis to see topics and difficulty<br>across your recent accepted submissions.</p><span class="empty-caption">A recent snapshot, not your all-time history</span></div>';
}
function richText(value) {
  return esc(value).replace(/`([^`\n]+)`/g,'<code>$1</code>').replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>');
}
function signOut() { state.editorQuestionId = null; state.token = null; state.user = null; state.generated = []; state.recommendations = []; sessionStorage.removeItem('linkedcode-token'); $('dashboard').hidden = true; $('auth-view').hidden = false; document.body.dataset.view='auth'; $('logout').hidden = true; $('latest').hidden = true; $('question-dialog').close(); $('question-content').replaceChildren();
  $('analysis').innerHTML = analysisEmpty();
  $('metrics').replaceChildren(); $('history').replaceChildren(); $('continue-practice').replaceChildren(); $('library-count').textContent='0'; $('history-count').textContent='0'; $('profile-username').value = '';
  $('history-search').value = ''; $('difficulty-filter').value = ''; $('status-filter').value = '';
  state.tab = 'generated';
}
async function api(path, options = {}) {
  const requestToken = state.token;
  const headers = {'Content-Type':'application/json', ...(state.token ? {Authorization:`Bearer ${state.token}`} : {}), ...options.headers};
  let response;
  try { response = await fetch(API + path, {...options, headers}); }
  catch { throw new Error('Cannot reach LinkedCode. Check that the backend is running on port 8000.'); }
  const data = await response.json().catch(() => ({}));
  if (requestToken && requestToken !== state.token) throw new Error('Session changed. Sign in to continue.');
  if (!response.ok) {
    if (response.status === 401 && state.user) signOut();
    const detail = Array.isArray(data.detail) ? data.detail.map(e => `${e.loc?.slice(-1)[0] || 'Input'}: ${e.msg}`).join('; ') : data.detail;
    if(path==='/recommendations/generate') {
      if(/token budget|request.*limit/i.test(String(detail))) throw new Error('The AI service could not fit this generation request. Your saved challenges are still available. Please try again later.');
      if(response.status>=500) throw new Error('New challenges could not be created right now. Your saved library is ready to practice—please try generation again later.');
    }
    throw new Error(detail || `Request failed (${response.status}).`);
  }
  return data;
}
async function busy(button, label, work) {
  const original = button.innerHTML; button.disabled = true; button.classList.add('is-loading'); button.setAttribute('aria-busy','true'); button.innerHTML = `<span class="spinner" aria-hidden="true"></span>${esc(label)}`;
  try { return await work(); } catch (error) { notice(error.message, true); }
  finally { button.disabled = false; button.innerHTML = original; button.classList.remove('is-loading'); button.removeAttribute('aria-busy'); }
}
async function enterDashboard() {
  state.user = await api('/auth/me');
  document.body.dataset.view='dashboard';
  $('auth-view').hidden = true; $('dashboard').hidden = false; $('logout').hidden = false;
  $('account-label').textContent = state.user.leetcode_username ? `Your next step starts here, ${state.user.leetcode_username}. Let’s make it a good one.` : 'Link your LeetCode username to get started.';
  $('profile-username').value = state.user.leetcode_username || '';
  const name=state.user.leetcode_username || state.user.email.split('@')[0];
  $('sidebar-username').textContent=name; $('user-avatar').textContent=name.slice(0,2).toUpperCase();
  $('profile-connection').textContent=state.user.leetcode_username ? `Connected as ${state.user.leetcode_username}` : 'Link your LeetCode account';
  $('profile-settings').open=!state.user.leetcode_username;
  $('generate').disabled = !state.user.leetcode_username; $('analyze').disabled = !state.user.leetcode_username;
  await loadHistory();
}
async function loadHistory() {
  const [generated, recommendations, progress] = await Promise.all([api('/generated-questions'), api('/recommendations/history'), api('/practice/progress')]);
  state.generated = generated.questions; state.recommendations = recommendations.recommendations;
  const metrics = [
    [progress.solved,'Solved in your history','Your linked practice record','✓'],
    [progress.statuses.completed,'LeetCode completed','One step closer to mastery','↗'],
    [progress.statuses.attempted,'In progress','Keep the momentum going','◴'],
    [`${progress.generated_completed ?? 0}/${progress.generated}`,'Original challenges solved','Correctness + performance checked','✧']
  ];
  $('metrics').innerHTML = metrics.map(([value,label,caption,icon]) => `<div class="metric"><div class="metric-top"><span>${label}</span><span class="metric-icon" aria-hidden="true">${icon}</span></div><strong>${esc(value)}</strong><small>${caption}</small></div>`).join('');
  $('library-count').textContent=state.generated.length+state.recommendations.length;
  renderContinuePractice();
  renderHistory();
}
function renderContinuePractice() {
  const q=state.generated[0];
  $('continue-practice').innerHTML=q ? `<span class="eyebrow">A FRESH WAY TO THINK</span><span class="continue-icon" aria-hidden="true">✧</span><div class="continue-meta"><span class="badge ${esc(q.difficulty)}">${esc(q.difficulty)}</span><span>Latest original challenge · ${esc(date(q.created_at))}</span></div><h3>${esc(q.title)}</h3><div class="topic-list">${(q.topics||[]).slice(0,4).map(t=>`<span class="topic">${esc(t)}</span>`).join('')}</div><button data-question="${q.id}" type="button">Open workspace <span aria-hidden="true">↗</span></button>` : '<span class="eyebrow">A FRESH WAY TO THINK</span><span class="continue-icon" aria-hidden="true">✧</span><h3>Your next challenge is waiting to be written.</h3><p>Create your personalized pair to get an original problem you can solve right here in Python.</p><a href="#overview">Let’s get started ↗</a>';
}
$('continue-practice').addEventListener('click',event=>{const button=event.target.closest('[data-question]');if(button)showQuestion(button.dataset.question);});
$('latest').addEventListener('click',event=>{const button=event.target.closest('[data-question]');if(button)showQuestion(button.dataset.question);});
function renderHistory() {
  const search = $('history-search').value.trim().toLowerCase();
  const isGenerated = state.tab === 'generated';
  $('difficulty-filter').hidden = !isGenerated; $('status-filter').hidden = isGenerated;
  $('tab-generated').tabIndex=isGenerated?0:-1; $('tab-recommendations').tabIndex=isGenerated?-1:0;
  $('tab-generated').setAttribute('aria-selected', String(isGenerated)); $('tab-recommendations').setAttribute('aria-selected', String(!isGenerated));
  const rows = (isGenerated ? state.generated : state.recommendations).filter(q => {
    const name = isGenerated ? q.title + ' ' + (q.topics || []).join(' ') : title(q.question_slug);
    return name.toLowerCase().includes(search) && (isGenerated ? (!$('difficulty-filter').value || q.difficulty === $('difficulty-filter').value) : (!$('status-filter').value || q.status === $('status-filter').value));
  });
  $('history-count').textContent=rows.length;
  $('history').innerHTML = rows.length ? rows.map((q,index) => isGenerated ? `<div class="question-row"><span class="question-number">${String(index+1).padStart(2,'0')}</span><span class="badge ${esc(q.difficulty)}">${esc(q.difficulty)}</span><div class="row-copy"><h3>${esc(q.title)}</h3><p>${esc((q.topics || []).join(' · '))} · ${esc(date(q.created_at))}</p></div><button class="quiet" data-question="${q.id}">Solve challenge ↗</button></div>` : `<div class="question-row"><span class="question-number">${String(index+1).padStart(2,'0')}</span><div class="row-copy"><h3><a href="https://leetcode.com/problems/${encodeURIComponent(q.question_slug)}/" target="_blank" rel="noopener noreferrer">${esc(title(q.question_slug))} ↗</a></h3><p>${esc(date(q.recommended_at))}</p></div><label><span class="sr-only">Practice status for ${esc(title(q.question_slug))}</span><select aria-label="Practice status for ${esc(title(q.question_slug))}" data-status="${esc(q.question_slug)}" ${q.status === 'completed' ? 'disabled' : ''}>${['recommended','attempted','completed','skipped'].map(s => `<option value="${s}" ${q.status === s ? 'selected' : ''}>${title(s)}</option>`).join('')}</select></label></div>`).join('') : '<div class="empty-state"><span class="empty-icon" aria-hidden="true">⌕</span><strong>A little quiet here.</strong><p>Create your next challenges, or try a different search.</p></div>';
}
function showQuestion(id) {
  const saved = state.generated.find(q => q.id === Number(id)); if (!saved) return;
  const q = saved.question_data;
  state.editorQuestionId = saved.id;
  const text = value => typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  const section = (heading, value) => `<h3>${heading}</h3><p>${richText(text(value))}</p>`;
  $('question-content').innerHTML = `<span class="eyebrow">ORIGINAL CHALLENGE · ${esc(q.difficulty)}</span><h2>${esc(q.title)}</h2><div>${(q.topics || []).map(t => `<span class="topic">${esc(t)}</span>`).join('')}</div>${section('The challenge',q.description)}${section('Input',q.input_format)}${section('Output',q.output_format)}<h3>Constraints</h3><ul>${q.constraints.map(c => `<li>${esc(c)}</li>`).join('')}</ul><h3>Examples</h3>${q.examples.map((e,i) => `<h4>Example ${i+1}</h4><pre>Input\n${esc(e.input)}\n\nOutput\n${esc(e.output)}</pre><p>${richText(e.explanation)}</p>`).join('')}<details><summary>Reveal solutions & complexity</summary><h4>Optimized solution</h4><pre>${esc(q.reference_solution)}</pre><p>Time: ${esc(q.time_complexity)} · Space: ${esc(q.space_complexity)}</p><h4>Brute-force solution</h4><pre>${esc(q.brute_force_solution)}</pre></details><details><summary>Practice test cases</summary>${q.test_cases.map((c,i) => `<h4>Case ${i+1}</h4><pre>Input\n${esc(c.input)}\n\nExpected output\n${esc(c.expected_output)}</pre>`).join('')}</details><p class="muted small">Validation: ${esc(saved.validation_report?.passed || 0)}/${esc(saved.validation_report?.total_tests || 0)} checks passed.</p>`;
  const problem = $('question-content').innerHTML;
  $('question-content').innerHTML = `<div class="practice-layout"><div class="problem-pane">${problem}</div>${pythonEditor(saved.id)}</div>`;
  try { $('python-code').value = sessionStorage.getItem(draftKey(saved.id)) || PYTHON_STARTER; }
  catch { $('python-code').value = PYTHON_STARTER; }
  updateCodeLines();
  if (state.editorRunning) setEditorBusy(true);
  loadSubmissions(saved.id);
  $('question-dialog').showModal();
}
$('auth-toggle').addEventListener('click', () => {
  state.registering = !state.registering;
  $('auth-title').textContent = state.registering ? 'Build your momentum.' : 'Pick up your momentum.';
  $('auth-description').textContent = state.registering ? 'Create your personal learning space.' : 'Sign in to your personal practice space.';
  $('register-username').hidden = !state.registering;
  $('auth-submit').textContent = state.registering ? 'Create your account →' : 'Sign in to workspace →';
  $('auth-toggle').textContent = state.registering ? 'Already a member? Sign in' : 'New here? Create an account';
  $('password').minLength = state.registering ? 8 : 1;
  $('password').autocomplete = state.registering ? 'new-password' : 'current-password';
  notice('');
});
$('auth-form').addEventListener('submit', event => {
  event.preventDefault();
  busy($('auth-submit'), 'Opening your workspace…', async () => {
    const body = {email:$('email').value.trim(), password:$('password').value};
    if (state.registering) await api('/auth/register', {method:'POST', body:JSON.stringify({...body,leetcode_username:$('signup-username').value.trim() || null})});
    const auth = await api('/auth/login', {method:'POST',body:JSON.stringify(body)});
    state.token = auth.access_token; sessionStorage.setItem('linkedcode-token',state.token); $('password').value = ''; notice(''); await enterDashboard();
  });
});
$('logout').addEventListener('click', () => {signOut(); notice('Signed out.');});
$('profile-form').addEventListener('submit', event => {
  event.preventDefault(); busy(event.submitter, 'Saving…', async () => {
    await api('/auth/profile',{method:'PATCH',body:JSON.stringify({leetcode_username:$('profile-username').value.trim()})});
    $('analysis').innerHTML = analysisEmpty();
    await enterDashboard(); notice('LeetCode username saved.');
  });
});
$('analyze').addEventListener('click', () => busy($('analyze'),'Analyzing…',async () => {
  const data = await api('/leetcode/analyze'); const profile = data.user_profile;
  const topics = Object.entries(profile.topic_frequency || {}).sort((a,b) => b[1]-a[1]); const max = Math.max(1,...topics.map(t => t[1]));
  $('analysis').innerHTML = `<p class="muted small">Based on ${esc(profile.total_unique_questions)} recent unique accepted questions; this is a recent sample, not your full LeetCode history.</p><div class="difficulty-stats">${Object.entries(profile.difficulty_distribution || {}).map(([d,n]) => `<span>${esc(d)} <strong>${esc(n)}</strong></span>`).join('')}</div><h3>Recently practiced topics</h3>${topics.length ? topics.slice(0,8).map(([t,n]) => `<div class="bar-row"><span>${esc(t)}</span><meter min="0" max="${max}" value="${n}" aria-label="${esc(t)}: ${n}"></meter><strong>${n}</strong></div>`).join('') : '<p class="empty">No recent accepted submissions found.</p>'}`;
}));
$('generate').addEventListener('click', () => {
  if(state.generating) return;
  state.generating = true;
  busy($('generate'),'Creating your challenges…',async () => {
    notice('Your challenges are being generated and checked. This can take a few minutes.');
    const result = await api('/recommendations/generate',{method:'POST'});
    await loadHistory(); const existing = result.recommendations.existing_question;
    $('latest').hidden = false;
    const original=result.recommendations.generated_question;
    const saved=state.generated.find(q=>q.title===original?.title);
    $('latest').innerHTML = `<div class="section-head"><div><span class="eyebrow">A DIRECTION OF YOUR OWN</span><h2>Your next pair is ready.</h2></div><span class="badge Easy">Saved to your library</span></div><div class="pair-results"><div><span class="eyebrow">01 / LEETCODE PICK</span><h3>${esc(existing.title || title(existing.title_slug))}</h3><p>${esc(existing.reason || existing.reasoning || 'A fresh LeetCode problem based on your recent history.')}</p><a href="https://leetcode.com/problems/${encodeURIComponent(existing.title_slug)}/" target="_blank" rel="noopener noreferrer">Open on LeetCode ↗</a></div><div><span class="eyebrow">02 / ORIGINAL CHALLENGE</span><h3>${esc(original?.title || 'Your original challenge')}</h3><p>A new problem to explore, with a Python workspace and checked test cases.</p>${saved?`<button type="button" data-question="${saved.id}">Open workspace ↗</button>`:''}</div></div>`;
    notice('Both challenges are ready and saved.');
  }).finally(() => {state.generating = false;});
});
$('refresh-history').addEventListener('click', () => busy($('refresh-history'),'Loading…',loadHistory));
$('tab-generated').addEventListener('click', () => {state.tab='generated';renderHistory();});
$('tab-recommendations').addEventListener('click', () => {state.tab='recommendations';renderHistory();});
for (const id of ['history-search','difficulty-filter','status-filter']) $(id).addEventListener('input',renderHistory);
$('history').addEventListener('click',event => {const button=event.target.closest('[data-question]');if(button) showQuestion(button.dataset.question);});
$('history').addEventListener('change',async event => {
  const select=event.target.closest('[data-status]');if(!select)return;select.disabled=true;
  try{await api(`/recommendations/${encodeURIComponent(select.dataset.status)}/status`,{method:'PATCH',body:JSON.stringify({status:select.value})});await loadHistory();notice('Practice progress updated.');}
  catch(error){notice(error.message,true);renderHistory();}
});
$('close-dialog').addEventListener('click',()=>$('question-dialog').close());
$('workspace-code').addEventListener('click',()=>{$('python-code')?.focus();});
$('workspace-problem').addEventListener('click',()=>{const pane=document.querySelector('.problem-pane');if(pane){pane.scrollTop=0;pane.scrollIntoView({block:'start',behavior:'smooth'});}});
function syncNavigation() {
  const hash=location.hash || '#overview';
  for(const link of document.querySelectorAll('.nav-link')) {
    const active=link.getAttribute('href')===hash;
    link.classList.toggle('active',active);
    if(active){link.setAttribute('aria-current','page');document.querySelector('.breadcrumb strong').textContent=link.getAttribute('aria-label');}
    else link.removeAttribute('aria-current');
  }
}
window.addEventListener('hashchange',syncNavigation);syncNavigation();
for(const id of ['tab-generated','tab-recommendations'])$(id).addEventListener('keydown',event=>{
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  event.preventDefault();
  state.tab=event.key==='Home'?'generated':event.key==='End'?'recommendations':state.tab==='generated'?'recommendations':'generated';
  renderHistory();$(state.tab==='generated'?'tab-generated':'tab-recommendations').focus();
});
if(state.token) enterDashboard().catch(error=>{signOut();notice(error.message,true);});


const PYTHON_STARTER = `import sys


def solve():
    data = sys.stdin.read().split()
    # Read input and implement your solution here.
    pass


if __name__ == "__main__":
    solve()
`;
function draftKey(id) { return `linkedcode-python-${state.user.id}-${id}`; }
function pythonEditor(id) {
  return `<section class="python-workspace" aria-label="Python practice editor"><div class="editor-heading"><div><span class="eyebrow">YOUR SOLUTION</span><h3>Python 3</h3></div><span id="draft-status" class="muted small">Draft saved for this browser session</span></div><p class="small muted">Write a complete program that reads standard input and prints the answer.</p><div class="code-editor"><pre id="code-lines" aria-hidden="true">1</pre><label class="sr-only" for="python-code">Python solution</label><textarea id="python-code" spellcheck="false" autocapitalize="off" autocomplete="off" autocorrect="off" wrap="off"></textarea></div><div class="run-toolbar"><button id="run-examples" type="button">Run examples</button><button id="submit-python" type="button" class="secondary">Submit all tests</button></div><details class="custom-input"><summary>Try custom input</summary><label for="python-stdin" class="small">Standard input</label><textarea id="python-stdin" rows="4" maxlength="20000" placeholder="Paste input in the question's format"></textarea><button id="run-custom" type="button" class="quiet">Run custom input →</button></details><p class="execution-note">Code and test inputs are sent to the configured Judge0 service. Submit checks correctness and large hidden performance cases. Limit: 3 seconds CPU, 128 MB memory per case. External packages are not installed.</p><div id="python-results" aria-live="polite"><p class="empty">Run the examples to check your solution.</p></div><details><summary>Recent submissions</summary><div id="python-submissions"><p class="small muted">Loading…</p></div></details></section>`;
}
function updateCodeLines() {
  const code = $('python-code'); if (!code) return;
  $('code-lines').textContent = Array.from({length:Math.max(14,code.value.split('\n').length)},(_,i)=>i+1).join('\n');
  $('code-lines').scrollTop = code.scrollTop;
}
function setEditorBusy(value) {
  for (const id of ['run-examples','run-custom','submit-python']) if($(id)) $(id).disabled=value;
}
async function loadSubmissions(id) {
  try {
    const data = await api(`/generated-questions/${id}/submissions`);
    if(state.editorQuestionId!==id || !$('python-submissions')) return;
    $('python-submissions').innerHTML = data.submissions.length ? data.submissions.map(s=>`<p class="submission-row"><strong>${esc(s.verdict==='Accepted' && s.performance_status!=='passed'?'Correctness only':s.verdict)}</strong><span>${s.passed}/${s.total} · ${esc(date(s.created_at))}</span></p>`).join('') : '<p class="small muted">No submissions yet. Running examples does not count as a submission.</p>';
  } catch(error) { if(state.editorQuestionId===id && $('python-submissions')) $('python-submissions').textContent=error.message; }
}
function showPythonResults(data) {
  const isCustom = data.mode==='custom';
  $('python-results').innerHTML = `<div class="run-summary ${data.accepted?'accepted':isCustom && data.verdict==='Executed'?'executed':'failed'}"><strong>${esc(data.verdict)}</strong><span>${isCustom?'Custom input · output is not judged':`${data.passed}/${data.total} tests passed`}</span></div><details class="all-test-results" ${data.accepted?'':'open'}><summary>View ${data.total} test result${data.total===1?'':'s'}</summary>${data.results.map((row,i)=>`<details class="case-result" ${(!row.hidden && (row.passed===false || isCustom || i===0))?'open':''}><summary>${row.kind==='performance'?'Performance':row.hidden?'Verification':'Case'} ${row.case} · ${esc(row.verdict)} <span class="small muted">${esc(row.time_seconds ?? '—')} s · ${row.memory_kb == null ? '—' : (Number(row.memory_kb)/1024).toFixed(1)} MB</span></summary>${row.hidden?'<p class="small muted">Verification input and output are not shown in run results.</p>':`<div class="result-io"><h4>Input</h4><pre>${esc(row.input || '(empty)')}</pre>${row.expected_output == null?'':`<h4>Expected output</h4><pre>${esc(row.expected_output)}</pre>`}<h4>Your output</h4><pre>${esc(row.stdout || '(no output)')}</pre>${row.error?`<h4>Error</h4><pre class="error-output">${esc(row.error)}</pre>`:''}${row.output_truncated?'<p class="small">Output display truncated.</p>':''}</div>`}</details>`).join('')}</details>`;
}
async function executePython(mode) {
  if(state.editorRunning) return;
  const id=state.editorQuestionId, token=state.token, code=$('python-code').value;
  if(!code.trim()) { $('python-results').textContent='Write some Python code first.';return; }
  if(code.length>40000) { $('python-results').textContent='Code must be under 40,000 characters.';return; }
  state.editorRunning=true; setEditorBusy(true);
  $('python-results').innerHTML='<p class="empty"><span class="spinner" aria-hidden="true"></span> Running Python and checking test cases… First submission may also calibrate large tests. Keep this page open.</p>';
  try {
    const data=await api(`/generated-questions/${id}/execute`,{method:'POST',body:JSON.stringify({code,mode,stdin:mode==='custom'?$('python-stdin').value:''})});
    if(state.token!==token || state.editorQuestionId!==id) return;
    showPythonResults(data);
    if(mode==='submit') { await loadSubmissions(id); await loadHistory(); }
  } catch(error) { if(state.token===token && state.editorQuestionId===id && $('python-results')) { $('python-results').textContent=error.message; } }
  finally { state.editorRunning=false;setEditorBusy(false); }
}
$('question-content').addEventListener('input',event=>{
  if(event.target.id!=='python-code')return;
  try {sessionStorage.setItem(draftKey(state.editorQuestionId),event.target.value);$('draft-status').textContent='Draft saved for this browser session';}
  catch {$('draft-status').textContent='Browser storage unavailable — keep your own copy';}
  updateCodeLines();
});
$('question-content').addEventListener('keydown',event=>{
  const editor=event.target;if(editor.id!=='python-code')return;
  if(event.key==='Tab') {event.preventDefault();editor.setRangeText('    ',editor.selectionStart,editor.selectionEnd,'end');editor.dispatchEvent(new Event('input',{bubbles:true}));}
  if((event.ctrlKey || event.metaKey) && event.key==='Enter') {event.preventDefault();executePython('examples');}
});
$('question-content').addEventListener('scroll',event=>{if(event.target.id==='python-code') $('code-lines').scrollTop=event.target.scrollTop;},true);
$('question-content').addEventListener('click',event=>{
  const button=event.target.closest('button');
  if(button?.id==='run-examples')executePython('examples');
  if(button?.id==='submit-python')executePython('submit');
  if(button?.id==='run-custom')executePython('custom');
});
