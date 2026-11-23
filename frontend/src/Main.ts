import './style.css';
import './document-control.css';
import { api, type DocumentType, type TypeDetection, type User, type ValidationResult } from './Api';
import { renderResult } from './Components/Results';
import { escape } from './Utils/Html';
import { bindReviewEvents, renderDocumentReview, renderMetadata } from './Components/DocumentReview';
import type { ControlMetadata, DocumentReview, MetadataChanges } from './Types/DocumentControl';
import { AuthoringWorkspace } from './Components/Authoring';
import { LlmSettingsPage } from './Components/LlmSettings';

type QueueItem = { file: File; type: string; uid?: string; error?: string; detection?: TypeDetection; warnings?: string[]; metadata?: ControlMetadata; changes?: MetadataChanges };
const root = document.querySelector<HTMLDivElement>('#app')!;
let user: User | null = null;
let types: DocumentType[] = [];
let queue: QueueItem[] = [];
let result: ValidationResult | null = null;
let busy = false;
let notice = '';
let documentReview: DocumentReview | null = null;
let asOfDate = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

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
  const options = '<option value="auto">自动识别</option>' + types.map((item) => `<option value="${escape(item.type)}">${escape(item.label)}</option>`).join('');
  const queued = queue.length ? queue.map((item, index) => `
    <div class="file-row">
      <div class="file-icon">${escape(item.file.name.split('.').pop()?.toUpperCase() || 'FILE')}</div>
      <div class="file-name"><strong title="${escape(item.file.name)}">${escape(item.file.name)}</strong><small>${formatSize(item.file.size)}${item.uid ? ' · 已解析' : ''}</small>${item.detection ? `<small data-testid="file-detection-${index}">${item.type === 'auto' ? `自动识别：${escape(item.detection.label)} · ${escape(item.detection.reason)}` : `手动选择：${escape(types.find((type) => type.type === item.type)?.label || item.type)}`}</small>` : ''}${item.warnings?.length ? `<small>${escape(item.warnings.join('；'))}</small>` : ''}${item.error ? `<small class="form-error">${escape(item.error)}</small>` : ''}</div>
      <select ${busy ? 'disabled' : ''} aria-label="${escape(item.file.name)} 文件类型" data-testid="document-type-${index}" data-type-index="${index}">${options.replace(`value="${escape(item.type)}"`, `value="${escape(item.type)}" selected`)}</select>
      <button ${busy ? 'disabled' : ''} data-testid="remove-file-${index}" class="icon-button remove-file" data-remove="${index}" aria-label="移除 ${escape(item.file.name)}" title="移除文件">×</button>
    </div>${item.metadata ? renderMetadata(item.metadata, index, busy) : ''}`).join('') : '<div class="empty-queue">选择文件后将在这里显示解析队列</div>';
  root.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <a class="brand" href="#"><span class="brand-mark">Q</span><span><b>QMS</b><small>DOCUMENT REVIEW</small></span></a>
        <div class="side-label">工作区</div>
        <button data-testid="precheck-nav" class="nav-item active"><span class="nav-symbol">▦</span>文件预筛</button>
        <button data-testid="templates-nav" class="nav-item" id="templates-nav"><span class="nav-symbol">▤</span>模板与编写</button>
        ${user.role === 'admin' ? '<button data-testid="llm-settings-nav" class="nav-item" id="llm-settings-nav"><span class="nav-symbol">⚙</span>模型配置</button>' : ''}
        <button data-testid="rules-nav" class="nav-item" id="rules-nav"><span class="nav-symbol">≡</span>规则说明</button>
        <div class="sidebar-bottom"><div class="standard-tag"><span class="status-dot"></span><span>规则包已就绪<small>ISO 13485:2016 · v1.0.1</small></span></div><button ${busy ? 'disabled' : ''} data-testid="logout" id="logout" class="logout">退出登录</button></div>
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
                <div id="dropzone" class="dropzone" data-testid="upload-dropzone"><input id="file-input" data-testid="upload-files" type="file" multiple accept=".pdf,.docx,.xlsx,.txt,.md" ${busy ? 'disabled' : ''} hidden><div class="upload-symbol">↑</div><strong>拖放文件到此处，或 <button ${busy ? 'disabled' : ''} id="browse" data-testid="browse-files" class="text-button" type="button">浏览文件</button></strong><span>添加后自动上传并识别类型，可手动修正；每次最多 20 份文件</span></div>
                <div class="file-list">${queued}</div>
              </section>
              ${renderDocumentReview(documentReview, asOfDate, busy, queue.length > 0)}
              <section class="section-block action-block"><div class="action-copy"><strong>规则预筛</strong><span>逐份文件运行基础规则集，可在结果中查看证据与建议。</span></div><button id="analyze" data-testid="analyze-button" class="button button-primary" ${busy || !queue.length ? 'disabled' : ''}>${busy ? '<span class="spinner"></span> 正在处理' : '开始预筛'} <span aria-hidden="true">→</span></button></section>
              ${notice ? `<div class="inline-notice ${notice.startsWith('错误') ? 'is-error' : ''}" role="status">${escape(notice)}</div>` : ''}
              ${result ? renderResult(result) : ''}
            </div>
            <aside class="side-column">
              <section class="side-panel"><div class="panel-heading"><span class="panel-icon">⌁</span><div><h3>检查范围</h3><p>当前规则包覆盖的基础线索</p></div></div><div class="scope-list"><div><span>01</span><p>文件编号与修订标识</p></div><div><span>02</span><p>批准与生效日期字段</p></div><div><span>03</span><p>部分体系文件关键要素</p></div><div><span>04</span><p>条款级文本命中情况</p></div></div><button data-testid="show-rules" id="show-rules" class="panel-link">查看规则包说明 <span>→</span></button></section>
              <section class="side-panel quality-note" id="rule-note"><div class="note-top"><span class="status-dot"></span>使用说明</div><h3>文本命中不代表<br>过程已经有效实施</h3><p>扫描件、图片和表格中的内容可能无法完整提取。请结合原始文件、记录和实际过程进行人工复核。</p><div class="note-divider"></div><small>RULESET · ${escape(result?.rule_set.version || '1.0.1')}</small></section>
            </aside>
          </section>
        </div>
      </main>
    </div>`;
  bindEvents();
}

function bindEvents(): void {
  root.querySelector('#templates-nav')?.addEventListener('click', () => {
    if (!busy) void new AuthoringWorkspace(root, render, user?.role === 'admin').open();
  });
  root.querySelector('#llm-settings-nav')?.addEventListener('click', () => {
    if (!busy) void new LlmSettingsPage(root, render).open();
  });
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
  root.querySelectorAll<HTMLSelectElement>('[data-type-index]').forEach((select) => select.addEventListener('change', async () => {
    const item = queue[Number(select.dataset.typeIndex)];
    const previous = item.type;
    item.type = select.value; result = null; documentReview = null; notice = ''; busy = true; render();
    try {
      if (item.uid) {
        const updated = await api.updateType(item.uid, item.type);
        item.detection = updated.type_detection;
        item.metadata = updated.control_metadata; item.changes = {};
      } else await prepareFiles();
    } catch (error) {
      item.type = previous;
      notice = `错误：${error instanceof Error ? error.message : '类型更新失败'}`;
    } finally { busy = false; render(); }
  }));
  root.querySelectorAll<HTMLButtonElement>('[data-remove]').forEach((button) => button.addEventListener('click', () => {
    queue.splice(Number(button.dataset.remove), 1); result = null; documentReview = null; notice = ''; render();
  }));
  root.querySelector<HTMLButtonElement>('#analyze')?.addEventListener('click', analyze);
  root.querySelector<HTMLButtonElement>('#logout')?.addEventListener('click', async () => {
    await api.logout().catch(() => undefined); user = null; queue = []; result = null; documentReview = null; renderLogin();
  });
  root.querySelectorAll<HTMLButtonElement>('#show-rules, #rules-nav').forEach((button) => button.addEventListener('click', () => {
    document.querySelector('#rule-note')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }));
  root.querySelector('#notice-link')?.addEventListener('click', () => document.querySelector('#rule-note')?.scrollIntoView({ behavior: 'smooth' }));
  root.querySelector('#reset-result')?.addEventListener('click', () => { queue = []; result = null; documentReview = null; notice = ''; render(); });
  bindReviewEvents(root, (index, field, value) => {
    const item = queue[index]; if (!item.metadata || busy) return;
    item.metadata[field] = value; item.changes = { ...item.changes, [field]: value };
    documentReview = null; result = null; notice = '文件控制信息已校正，请重新检查关联与版本'; render();
  }, (value) => { asOfDate = value; documentReview = null; result = null; render(); }, checkRelations, confirmDecision);
}

async function addFiles(files: File[]): Promise<void> {
  if (busy) return;
  const allowed = /\.(pdf|docx|xlsx|txt|md)$/i;
  let rejected = false;
  for (const file of files) {
    if (!allowed.test(file.name) || queue.some((item) => item.file.name === file.name && item.file.size === file.size) || queue.length >= 20) { rejected = true; continue; }
    queue.push({ file, type: 'auto' });
  }
  notice = rejected ? '部分文件格式不支持、已在队列中或超出 20 份限制' : '';
  result = null; documentReview = null; busy = true; render();
  try { await prepareFiles(); } finally { busy = false; render(); }
}

async function prepareFiles(): Promise<void> {
  for (const item of queue) {
    if (item.uid) continue;
    try {
      const uploaded = await api.upload(item.file, item.type);
      item.uid = uploaded.file_uid;
      item.detection = uploaded.type_detection;
      item.warnings = uploaded.warnings;
      item.metadata = uploaded.control_metadata; item.changes = {};
      item.error = undefined;
    } catch (error) {
      item.error = error instanceof Error ? error.message : '上传失败，请重试';
    }
  }
}

async function analyze(): Promise<void> {
  if (busy) return;
  busy = true; notice = ''; result = null; render();
  try {
    await prepareFiles();
    if (queue.some((item) => !item.uid)) throw new Error('部分文件未解析成功，请修正或移除后重试');
    if (!documentReview) await createReview();
    if (!documentReview!.ready) { notice = '已发现文件冲突，请在“关联文件与正式版本”中选择依据并确认后再预筛'; return; }
    result = await api.validate(queue.map((item) => item.uid!), documentReview!.review_uid, documentReview!.revision);
    notice = '预筛完成，请结合文件原文复核各项线索。';
  } catch (error) {
    notice = `错误：${error instanceof Error ? error.message : '处理失败'}`;
  } finally {
    busy = false; render();
    if (result) document.querySelector('#result')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

async function createReview(): Promise<void> {
  const overrides = Object.fromEntries(queue.filter((item) => item.uid && item.changes && Object.keys(item.changes).length).map((item) => [item.uid!, item.changes!]));
  documentReview = await api.createReview(queue.map((item) => item.uid!), asOfDate, overrides);
}

async function checkRelations(): Promise<void> {
  if (busy) return;
  busy = true; result = null; notice = ''; render();
  try {
    await prepareFiles();
    if (queue.some((item) => !item.uid)) throw new Error('部分文件未解析成功，请先处理');
    await createReview();
    notice = '关联与版本检查完成，请核对文件依据及补件提示';
  } catch (error) { notice = `错误：${error instanceof Error ? error.message : '关联检查失败'}`; }
  finally { busy = false; render(); }
}

async function confirmDecision(kind: 'version' | 'requirement', id: string, uid: string, reason: string): Promise<void> {
  if (busy || !documentReview) return;
  busy = true; result = null; notice = ''; render();
  try {
    documentReview = await api.confirmReview(documentReview, kind, id, uid, reason);
    notice = '确认依据已保存，原文件和确认历史均保留';
  } catch (error) { notice = `错误：${error instanceof Error ? error.message : '确认失败'}`; }
  finally { busy = false; render(); }
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
