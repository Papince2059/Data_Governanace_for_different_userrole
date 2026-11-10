import axios, { AxiosInstance } from 'axios';
import type { Department, Document, Group, IngestionJob, TokenResponse, User } from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: `${BASE_URL}/api/v1`,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Attach Bearer token to all outgoing requests
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Handle 401 Unauthorized
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('user_profile');
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
        }
        return Promise.reject(error);
      }
    );
  }

  // --- Auth ---
  async login(email: string, password: string): Promise<TokenResponse> {
    const res = await this.client.post<TokenResponse>('/auth/login', { email, password });
    return res.data;
  }

  async getMe(): Promise<User> {
    const res = await this.client.get<User>('/auth/me');
    return res.data;
  }

  // --- Users ---
  async getUsers(): Promise<User[]> {
    const res = await this.client.get<User[]>('/users');
    return res.data;
  }

  // --- Departments ---
  async getDepartments(): Promise<Department[]> {
    const res = await this.client.get<Department[]>('/departments');
    return res.data;
  }

  // --- Groups ---
  async getGroups(): Promise<Group[]> {
    const res = await this.client.get<Group[]>('/groups');
    return res.data;
  }

  // --- Documents ---
  async getDocuments(departmentId?: string): Promise<Document[]> {
    const params = departmentId ? { department_id: departmentId } : {};
    const res = await this.client.get<Document[]>('/documents', { params });
    return res.data;
  }

  async getDocument(id: string): Promise<Document> {
    const res = await this.client.get<Document>(`/documents/${id}`);
    return res.data;
  }

  async deleteDocument(id: string): Promise<void> {
    await this.client.delete(`/documents/${id}`);
  }

  async uploadDocument(formData: FormData): Promise<{ document_id: string; job_id: string; message: string }> {
    const res = await this.client.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  }

  // --- Permissions (Admin) ---
  async checkPermission(userId: string, relation: string, resourceType: string, resourceId: string) {
    const res = await this.client.post('/permissions/check', {
      user_id: userId,
      relation,
      resource_type: resourceType,
      resource_id: resourceId,
    });
    return res.data;
  }

  async grantPermission(userOrGroup: string, relation: string, resourceType: string, resourceId: string) {
    await this.client.post('/permissions/grant', {
      user_or_group: userOrGroup,
      relation,
      resource_type: resourceType,
      resource_id: resourceId,
    });
  }

  async revokePermission(userOrGroup: string, relation: string, resourceType: string, resourceId: string) {
    await this.client.post('/permissions/revoke', {
      user_or_group: userOrGroup,
      relation,
      resource_type: resourceType,
      resource_id: resourceId,
    });
  }

  async getAccessibleResources(userId?: string) {
    const params = userId ? { user_id: userId } : {};
    const res = await this.client.get('/permissions/resources', { params });
    return res.data;
  }

  // --- Ingestion ---
  async getIngestionJob(jobId: string): Promise<IngestionJob> {
    const res = await this.client.get<IngestionJob>(`/ingestion/jobs/${jobId}`);
    return res.data;
  }
}

export const api = new ApiService();

/**
 * Server-Sent Events (SSE) Stream Reader for Chat.
 * Yields parsed SSE events: { event: string, data: any }
 */
export async function* streamChatResponse(
  question: string,
  conversationId?: string,
  signal?: AbortSignal
): AsyncGenerator<{ event: string; data: any }> {
  const token = localStorage.getItem('access_token');
  const response = await fetch(`${BASE_URL}/api/v1/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      question,
      conversation_id: conversationId,
    }),
    signal,
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Chat stream failed: HTTP ${response.status} - ${errText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('Response body is not readable');

  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    let currentEvent = '';
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.replace('event: ', '').trim();
      } else if (line.startsWith('data: ') && currentEvent) {
        const rawJson = line.replace('data: ', '').trim();
        try {
          const parsed = JSON.parse(rawJson);
          yield { event: currentEvent, data: parsed };
        } catch {
          // ignore malformed chunks
        }
        currentEvent = '';
      }
    }
  }
}

