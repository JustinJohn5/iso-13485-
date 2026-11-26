export interface PersonalFileGroup { group_uid: string; name: string; }
export interface PersonalFile {
  file_uid: string; name: string; document_type: string; size_bytes: number;
  text_status: string; created_at: string; groups: PersonalFileGroup[];
  control_metadata?: unknown; type_detection?: unknown;
}
export interface PageResult<T> { items: T[]; total: number; page: number; page_size: number; }
export interface FileGroup { group_uid: string; name: string; file_count: number; created_at: string; }
