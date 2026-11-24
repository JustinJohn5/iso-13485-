export interface Template {
  id: string; title: string; category: string; version: string; description: string;
  fields: Array<{ key: string; label: string; multiline?: boolean }>;
  sections: Array<{ id: string; title: string; body: string }>;
}

export interface GenerationMetadata {
  requirements_basis?: { version: string; source?: unknown; legacy?: boolean; requirements: Array<{ clause: string; title: string; generation?: unknown; source?: unknown; conditions?: string[]; uncertainty?: unknown }> };
  generation_review?: { pending_count: number; pending: unknown[]; manual_review: unknown[]; reference_gaps?: unknown[]; missing_requirements?: unknown[]; boundary?: string };
}

export interface DraftSnapshot extends GenerationMetadata {
  template_id: string; template_version: string; title: string; parameters: Record<string, string>;
  sections: Array<{ id: string; title: string; body: string }>; origin: string; status: string;
}

export interface Draft {
  draft_uid: string; revision: number; snapshot: DraftSnapshot;
  history: Array<{ revision: number; user_id: number; reason: string; created_at: string }>;
}

export interface DraftSummary { draft_uid: string; revision: number; title: string; project: string }
