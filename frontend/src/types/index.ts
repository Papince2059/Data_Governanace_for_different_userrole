export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_admin: boolean;
  tenant_id: string;
  department_id: string | null;
  department_name: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  is_admin: boolean;
  tenant_id: string;
  department_id: string | null;
  department_name: string | null;
}

export interface Document {
  id: string;
  title: string;
  description: string | null;
  file_type: string;
  file_size_bytes?: number;
  status: string;
  department_id: string | null;
  folder_id: string | null;
  owner_id: string;
  created_at: string;
}

export interface Department {
  id: string;
  name: string;
  description: string | null;
  organization_id: string;
  is_active: boolean;
}

export interface Group {
  id: string;
  name: string;
  description: string | null;
  organization_id: string;
  is_active: boolean;
}

export interface Citation {
  document_id: string;
  title: string;
  chunk_index: number;
  similarity: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: Date;
  isStreaming?: boolean;
}

export interface IngestionJob {
  id: string;
  document_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface IngestionEventPayload {
  job_id: string;
  event_type: string;
  message: string;
  metadata: Record<string, unknown>;
  timestamp: string;
}

