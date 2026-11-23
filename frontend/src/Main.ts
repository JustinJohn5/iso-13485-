import './style.css';
import { api, type DocumentType, type Finding, type User, type ValidationResult } from './Api';

type QueueItem = { file: File; type: string; uid?: string; error?: string };
const root = document.querySelector<HTMLDivElement>('#app')!;
let user: User | null = null;
let types: DocumentType[] = [];
let queue: QueueItem[] = [];
let result: ValidationResult | null = null;
let busy = false;
let notice = '';

function escape(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]!);
}

function renderLogin(message = ''): void {
  root.innerHTML = `
    <main class="login-page">
      <section class="login-panel">
        <div class="brand-mark">Q</div>
        <p class="eyebrow">QUALITY SYSTEM REVIEW</p>
        <h1>ISO 13485<br>文件预筛平台</h1>
        <p class="login-copy">上传质量体系文件，查看文本规则预筛结果与待核实事项。</p>
        <form id="login-form" class="login-form" data-testid="login-form">
          <label>邮箱<input data-testid="login-email" name="email" type="email" autocomplete="username" required placeholder="name@company.com"></label>
          <label>密码<input data-testid="login-password" name="password" type="password" autocomplete="current-password" required></label>
          <p class="form-error" role="alert">${escape(message)}</p>
          <button data-testid="login-submit" class="button button-primary" type="submit">登录工作区 <span aria-hidden="true">→</span></button>
        </form>
        <p class="login-foot">仅授权账号可访问文件与校验记录</p>
      </section>
      <aside class="login-aside"><div class="aside-rule"></div><p>DOCUMENT<br>CONTROL</p><span>受控文件的<br>结构化预筛</span><small>RULESET · 1.0</small></aside>
    </main>`;
  root.querySelector<HTMLFormElement>('#login-form')!.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget as HTMLFormElement);
    try {
      user = await api.login(String(data.get('email')), String(data.get('password')));
      await loadWorkspace();
    } catch (error) {
      renderLogin(error instanceof Error ? error.message : '登录失败');
    }
  });
}

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function render(): void {
  if (!user) return renderLogin();
  const options = types.map((item) => `<option value="${escape(item.type)}">${escape(item.label)}</option>`).join('');
  const queued = queue.length ? queue.map((item, index) => `
    <div class="file-row">
      <div class="file-icon">${escape(item.file.name.split('.').pop()?.toUpperCase() || 'FILE')}</div>
      <div class="file-name"><strong title="${escape(item.file.name)}">${escape(item.file.name)}</strong><small>${formatSize(item.file.size)}${item.uid ? ' · 已解析' : ''}</small>${item.error ? `<small class="form-error">${escape(item.error)}</small>` : ''}</div>
      <select aria-label="${escape(item.file.name)} 文件类型" data-testid="document-type-${index}" data-type-index="${index}">${options.replace(`value="${escape(item.type)}"`, `value="${escape(item.type)}" selected`)}</select>
      <button data-testid="remove-file-${index}" class="icon-button remove-file" data-remove="${index}" aria-label="移除 ${escape(item.file.name)}" title="移除文件">×</button>
    </div>`).join('') : '<div class="empty-queue">选择文件后将在这里显示解析队列</div>';
  const findingRows = result?.findings.map((item) => findingRow(item)).join('') || '';
  root.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <a class="brand" href="#"><span class="brand-mark">Q</span><span><b>QMS</b><small>DOCUMENT REVIEW</small></span></a>
        <div class="side-label">工作区</div>
        <button data-testid="precheck-nav" class="nav-item active"><span class="nav-symbol">▦</span>文件预筛</button>
        <button data-testid="rules-nav" class="nav-item" id="rules-nav"><span class="nav-symbol">≡</span>规则说明</button>
        <div class="sidebar-bottom"><div class="standard-tag"><span class="status-dot"></span><span>规则包已就绪<small>ISO 13485:2016 · v1.0</small></span></div><button data-testid="logout" id="logout" class="logout">退出登录</button></div>
      </aside>
      <main class="main-content">
        <header class="topbar"><div class="breadcrumb">工作区 <span>/</span> <b>文件预筛</b></div><div class="account"><span class="account-avatar">${escape((user.display_name || user.email).slice(0, 1).toUpperCase())}</span><span>${escape(user.display_name || user.email)}<small>${escape(user.role)}</small></span></div></header>
        <div class="content-wrap">
          <section class="page-heading"><div><p class="eyebrow">DOCUMENT COMPLIANCE</p><h1>文件预筛</h1><p>基于文本规则检查文件结构与关键内容，辅助质量体系自查。</p></div><div class="standard-pill"><span class="status-dot"></span>ISO 13485:2016</div></section>
          <div class="notice-bar"><span class="notice-icon">i</span><p>预筛结果仅用于内部文件检查，不构成认证、审核结论或法规符合性声明。</p><a href="#rule-note" id="notice-link">了解边界</a></div>
          <section class="workspace-grid">
            <div class="primary-column">
              <section class="section-block">
                <div class="section-title"><div><span class="step-no">01</span><div><h2>添加文件</h2><p>支持 PDF、DOCX、XLSX、TXT、MD，单文件不超过 40 MB</p></div></div><span class="count-label">${queue.length} 个文件</span></div>
                <div id="dropzone" class="dropzone" data-testid="upload-dropzone"><input id="file-input" data-testid="upload-files" type="file" multiple accept=".pdf,.docx,.xlsx,.txt,.md" hidden><div class="upload-symbol">↑</div><strong>拖放文件到此处，或 <button id="browse" data-testid="browse-files" class="text-button" type="button">浏览文件</button></strong><span>文件仅在授权工作区处理，上传后不会公开访问</span></div>
                <div class="file-list">${queued}</div>
              </section>
              <section class="section-block action-block"><div class="action-copy"><strong>规则预筛</strong><span>逐份文件运行基础规则集，可在结果中查看证据与建议。</span></div><button id="analyze" data-testid="analyze-button" class="button button-primary" ${busy || !queue.length ? 'disabled' : ''}>${busy ? '<span class="spinner"></span> 正在处理' : '开始预筛'} <span aria-hidden="true">→</span></button></section>
              ${notice ? `<div class="inline-notice ${notice.startsWith('错误') ? 'is-error' : ''}" role="status">${escape(notice)}</div>` : ''}
              ${result ? renderResult(result, findingRows) : ''}
            </div>
            <aside class="side-column">
              <section class="side-panel"><div class="panel-heading"><span class="panel-icon">⌁</span><div><h3>检查范围</h3><p>当前规则包覆盖的基础线索</p></div></div><div class="scope-list"><div><span>01</span><p>文件编号与修订标识</p></div><div><span>02</span><p>批准与生效日期字段</p></div><div><span>03</span><p>部分体系文件关键要素</p></div><div><span>04</span><p>条款级文本命中情况</p></div></div><button data-testid="show-rules" id="show-rules" class="panel-link">查看规则包说明 <span>→</span></button></section>
              <section class="side-panel quality-note" id="rule-note"><div class="note-top"><span class="status-dot"></span>使用说明</div><h3>文本命中不代表<br>过程已经有效实施</h3><p>扫描件、图片和表格中的内容可能无法完整提取。请结合原始文件、记录和实际过程进行人工复核。</p><div class="note-divider"></div><small>RULESET · ${escape(result?.rule_set.version || '1.0.0')}</small></section>
            </aside>
          </section>
        </div>
      </main>
    </div>`;
  bindEvents();
}

function findingRow(item: Finding): string {
  const state = item.status === 'pass' ? '通过' : item.status === 'fail' ? '待核实' : '未适用';
  const severity = ({ critical: '严重', major: '主要', minor: '一般', observation: '观察' } as Record<string, string>)[item.severity] || item.severity;
  return `<tr><td><span class="clause-id">${escape(item.clause)}</span><small>${escape(item.clause_title)}</small></td><td><strong>${escape(item.title)}</strong><small>${escape(item.rule_id)}${item.document_name ? ` · ${escape(item.document_name)}` : ''}</small></td><td><span class="severity severity-${escape(item.severity)}">${escape(severity)}</span></td><td><span class="finding-status status-${item.status}"><i></i>${state}</span></td><td>${escape(item.evidence || item.detail || '—')}</td><td>${escape(item.suggestion || '—')}</td></tr>`;
}

function renderResult(data: ValidationResult, rows: string): string {
  return `<section class="result-section" id="result" data-testid="results"><div class="result-heading"><div><p class="eyebrow">SCREENING RESULT · ${escape(data.run_uid.slice(0, 8))}</p><h2 data-testid="results-title">预筛结果</h2></div><button id="reset-result" class="button button-secondary">新建预筛</button></div><div class="result-overview"><div class="score-block"><span>规则线索得分</span><strong>${data.score.score}<small>/100</small></strong><em>${escape(data.score.verdict)}</em></div><div class="result-stat"><strong>${data.score.total_count}</strong><span>参与规则</span></div><div class="result-stat success-stat"><strong>${data.score.passed_count}</strong><span>通过</span></div><div class="result-stat warning-stat"><strong>${data.score.failed_count}</strong><span>待核实</span></div><div class="result-stat muted-stat"><strong>${data.score.skipped_count}</strong><span>未适用</span></div></div><div class="table-scroll"><table><thead><tr><th>条款</th><th>检查项</th><th>级别</th><th>状态</th><th>文本证据</th><th>建议</th></tr></thead><tbody>${rows}</tbody></table></div><div class="result-disclaimer">${escape(data.disclaimer)}</div></section>`;
}

function bindEvents(): void {
  const input = root.querySelector<HTMLInputElement>('#file-input')!;
  root.querySelector('#browse')!.addEventListener('click', () => input.click());
  input.addEventListener('change', () => addFiles([...input.files || []]));
  const dropzone = root.querySelector<HTMLDivElement>('#dropzone')!;
  dropzone.addEventListener('dragover', (event) => { event.preventDefault(); dropzone.classList.add('dragover'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', (event) => {
    event.preventDefault(); dropzone.classList.remove('dragover');
    addFiles([...event.dataTransfer?.files || []]);
  });
  root.querySelectorAll<HTMLSelectElement>('[data-type-index]').forEach((select) => select.addEventListener('change', () => {
    queue[Number(select.dataset.typeIndex)].type = select.value;
  }));
  root.querySelectorAll<HTMLButtonElement>('[data-remove]').forEach((button) => button.addEventListener('click', () => {
    queue.splice(Number(button.dataset.remove), 1); render();
  }));
  root.querySelector<HTMLButtonElement>('#analyze')?.addEventListener('click', analyze);
  root.querySelector<HTMLButtonElement>('#logout')?.addEventListener('click', async () => {
    await api.logout().catch(() => undefined); user = null; queue = []; result = null; renderLogin();
  });
  root.querySelectorAll<HTMLButtonElement>('#show-rules, #rules-nav').forEach((button) => button.addEventListener('click', () => {
    document.querySelector('#rule-note')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }));
  root.querySelector('#notice-link')?.addEventListener('click', () => document.querySelector('#rule-note')?.scrollIntoView({ behavior: 'smooth' }));
  root.querySelector('#reset-result')?.addEventListener('click', () => { queue = []; result = null; notice = ''; render(); });
}

function addFiles(files: File[]): void {
  const allowed = /\.(pdf|docx|xlsx|txt|md)$/i;
  const fresh = files.filter((file) => allowed.test(file.name) && !queue.some((item) => item.file.name === file.name && item.file.size === file.size));
  const defaultType = types.find((item) => item.type === 'other')?.type || types[0]?.type || 'other';
  queue.push(...fresh.map((file) => ({ file, type: defaultType })));
  if (files.length !== fresh.length) notice = '部分文件格式不支持或已在队列中';
  else notice = '';
  result = null;
  render();
}

async function analyze(): Promise<void> {
  if (busy) return;
  busy = true; notice = ''; render();
  try {
    for (const item of queue) {
      if (!item.uid) {
        const uploaded = await api.upload(item.file, item.type);
        item.uid = uploaded.file_uid;
      }
    }
    result = await api.validate(queue.map((item) => item.uid!));
    notice = '预筛完成，请结合文件原文复核各项线索。';
  } catch (error) {
    notice = `错误：${error instanceof Error ? error.message : '处理失败'}`;
  } finally {
    busy = false; render();
    if (result) document.querySelector('#result')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

async function loadWorkspace(): Promise<void> {
  try {
    types = await api.documentTypes();
    render();
  } catch (error) {
    user = null;
    renderLogin(error instanceof Error ? error.message : '无法加载工作区');
  }
}

async function boot(): Promise<void> {
  try {
    user = await api.me();
    await loadWorkspace();
  } catch {
    renderLogin();
  }
}

void boot();
