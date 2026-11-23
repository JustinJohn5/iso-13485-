// 浏览器输入限制，与后端各自维护；字符数不等同于模型 token 数。
export const AUTHORING_LIMITS = {
  requirements: 100_000,
  instructions: 30_000,
  section: 120_000,
  outputTokens: 65_536,
  timeoutSeconds: 600,
} as const;
