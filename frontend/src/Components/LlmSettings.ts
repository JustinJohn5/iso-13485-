import { llmApi, type LlmConfig } from '../Api/Llm';
import { api } from '../Api';
import { escape } from '../Utils/Html';
import { AUTHORING_LIMITS } from '../Constants/AuthoringLimits';
import '../authoring.css';

export class LlmSettingsPage {
  private config: LlmConfig | null = null;
  private busy = false;
  private message = '';
  private failed = false;
  private forbidden = false;

  constructor(private root: HTMLElement, private back: () => void) {}

  async open(): Promise<void> {
    window.scrollTo(0, 0);
    this.config = null; this.message = ''; this.failed = false; this.forbidden = false;
    this.busy = true; this.render();
    try {
      if ((await api.me()).role !== 'admin') {
        this.forbidden = true;
        throw new Error('仅管理员（admin）可查看和修改模型配置，请联系管理员。');
      }
      this.config = await llmApi.config();
    }
    catch (error) { this.failed = true; this.message = error instanceof Error ? error.message : '配置读取失败'; }
    finally { this.busy = false; this.render(); }
  }

  private render(): void {
    const config = this.config;
    this.root.innerHTML = `<div class="app-shell"><aside class="sidebar"><a class="brand" href="#"><span class="brand-mark">Q</span><span><b>QMS</b><small>MODEL SETTINGS</small></span></a>
      <button class="nav-item" data-testid="settings-back" id="settings-back" ${this.busy ? 'disabled' : ''}>← 返回工作区</button><button class="nav-item active">模型配置</button></aside>
      <main class="main-content"><header class="topbar"><div class="breadcrumb">工作区 / 模型配置</div><span>仅管理员可管理</span></header>
        <div class="content-wrap authoring-wrap"><section class="page-heading"><div><p class="eyebrow">OPENAI COMPATIBLE API</p><h1>模型配置</h1><p>所有 AI 调用统一使用此处保存的服务地址、模型及参数。</p></div></section>
          <div class="notice-bar"><span class="notice-icon">i</span><p>API Key 保存后仅显示配置状态，留空保留已有密钥。更换服务地址时须重新提交密钥；正式部署使用 HTTPS。</p></div>
          ${this.message ? `<p class="inline-notice ${this.failed ? 'is-error' : ''}" role="status" data-testid="llm-notice">${escape(this.message)}</p>` : ''}
          ${config ? `<section class="section-block authoring-editor"><form id="llm-settings-form" autocomplete="off"><fieldset class="authoring-fieldset" ${this.busy ? 'disabled' : ''}>
            <label class="section-editor">启用 AI 编写与文件审阅<input type="checkbox" id="llm-enabled" data-testid="llm-enabled" ${config.enabled ? 'checked' : ''}></label>
            <div class="authoring-fields"><label>服务地址（包含服务商要求的 API 前缀）<input type="url" required maxlength="255" id="llm-url" data-testid="llm-url" value="${escape(config.base_url)}"></label>
              <label>模型标识<input required maxlength="128" id="llm-model" data-testid="llm-model" value="${escape(config.model)}"></label>
              <label>API Key<input type="password" autocomplete="new-password" maxlength="256" id="llm-key" data-testid="llm-key" value="" placeholder="${config.api_key_configured ? '已配置；留空保留' : '尚未配置'}"></label>
              <label>单次超时（秒，5～${AUTHORING_LIMITS.timeoutSeconds}）<input type="number" required min="5" max="${AUTHORING_LIMITS.timeoutSeconds}" id="llm-timeout" data-testid="llm-timeout" value="${config.timeout_seconds}"></label>
              <label>最大输出 token（256～${AUTHORING_LIMITS.outputTokens}）<input type="number" required min="256" max="${AUTHORING_LIMITS.outputTokens}" id="llm-tokens" data-testid="llm-tokens" value="${config.max_tokens}"></label>
              <label>温度（0～2）<input type="number" required min="0" max="2" step="0.01" id="llm-temperature" data-testid="llm-temperature" value="${config.temperature}"></label></div>
            <p class="control-note" data-testid="llm-key-status">密钥状态：${config.api_key_configured ? '已配置' : '未配置'}</p>
            <p class="control-note" data-testid="llm-capacity-note">应用接受最多100万字符的总输入；字符数不等同于 token。实际输入与输出合计受所选模型上下文窗口约束，最大输出还受服务商限制，请按模型能力设置。</p>
            <button class="button button-primary" type="submit" data-testid="save-llm-settings">${this.busy ? '正在保存…' : '保存配置'}</button>
            <p class="control-note">最多重试1次；服务不可用时保留原草稿。保存配置仅校验字段，不代表已经连通服务；可在草稿中发起 AI 编写验证。</p>
          </fieldset></form></section>` : this.busy ? '<p role="status">正在加载配置…</p>' : this.forbidden ? '' : '<button class="button button-secondary" id="retry-settings">重新加载</button>'}
        </div></main></div>`;
    this.root.querySelector('#settings-back')?.addEventListener('click', this.back);
    this.root.querySelector('#retry-settings')?.addEventListener('click', () => { void this.open(); });
    this.root.querySelector('#llm-settings-form')?.addEventListener('submit', (event) => { event.preventDefault(); void this.save(); });
  }

  private async save(): Promise<void> {
    if (this.busy) return;
    const value = (id: string) => this.root.querySelector<HTMLInputElement>(`#${id}`)!.value;
    const key = value('llm-key');
    this.config = { ...this.config!, enabled: this.root.querySelector<HTMLInputElement>('#llm-enabled')!.checked,
      base_url: value('llm-url'), model: value('llm-model'), timeout_seconds: Number(value('llm-timeout')),
      max_tokens: Number(value('llm-tokens')), temperature: Number(value('llm-temperature')) };
    const { api_key_configured: _configured, ...fields } = this.config;
    this.root.querySelector<HTMLInputElement>('#llm-key')!.value = '';
    this.busy = true; this.message = ''; this.render();
    try { this.config = await llmApi.save({ ...fields, ...(key ? { api_key: key } : {}) }); this.failed = false; this.message = '配置已保存，密钥不回显。'; }
    catch (error) { this.failed = true; this.message = error instanceof Error ? error.message : '配置保存失败'; }
    finally { this.busy = false; this.render(); }
  }
}
