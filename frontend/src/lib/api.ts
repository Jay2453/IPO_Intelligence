import { 
  IPOSummary, 
  IPODetail, 
  PaginatedResponse, 
  HealthResponse, 
  SystemStatusResponse, 
  IngestionJob,
  IPOEvent,
  Document,
  FinancialObservation,
  Prediction 
} from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

async function fetchFromApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      next: { revalidate: 0 }, // always fresh in dev
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`API Error [${res.status}] ${res.statusText}: ${errorText}`);
    }

    return await res.json();
  } catch (err: any) {
    console.error(`Failed to fetch from ${url}:`, err);
    throw err;
  }
}

export const api = {
  getHealth: async (): Promise<HealthResponse> => {
    return fetchFromApi<HealthResponse>('/health');
  },

  getSystemStatus: async (): Promise<SystemStatusResponse> => {
    return fetchFromApi<SystemStatusResponse>('/system/status');
  },

  getIpos: async (params?: {
    exchange?: string;
    category?: string;
    lifecycle_status?: string;
    analysis_status?: string;
    search?: string;
    sort_by?: string;
    sort_order?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<IPOSummary>> => {
    const query = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          query.set(key, String(val));
        }
      });
    }
    const qStr = query.toString();
    return fetchFromApi<PaginatedResponse<IPOSummary>>(`/ipos${qStr ? `?${qStr}` : ''}`);
  },

  getIpoDetail: async (id: string): Promise<IPODetail> => {
    return fetchFromApi<IPODetail>(`/ipos/${id}`);
  },

  getIpoEvents: async (id: string): Promise<IPOEvent[]> => {
    return fetchFromApi<IPOEvent[]>(`/ipos/${id}/events`);
  },

  getIpoDocuments: async (id: string): Promise<Document[]> => {
    return fetchFromApi<Document[]>(`/ipos/${id}/documents`);
  },

  getIpoPredictions: async (id: string): Promise<Prediction[]> => {
    return fetchFromApi<Prediction[]>(`/ipos/${id}/predictions`);
  },

  getIngestionJobs: async (params?: { page?: number; page_size?: number; status?: string }): Promise<PaginatedResponse<IngestionJob>> => {
    const query = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          query.set(key, String(val));
        }
      });
    }
    const qStr = query.toString();
    return fetchFromApi<PaginatedResponse<IngestionJob>>(`/ingestion/jobs${qStr ? `?${qStr}` : ''}`);
  },

  seedDemoData: async (force: boolean = false): Promise<any> => {
    return fetchFromApi(`/seed/demo?force=${force}`, { method: 'POST' });
  },

  getIpoFinancials: async (id: string): Promise<FinancialObservation[]> => {
    return fetchFromApi<FinancialObservation[]>(`/ipos/${id}/financials`);
  },

  syncNse: async (includePast: boolean = true, pastLimit: number = 30): Promise<any> => {
    return fetchFromApi(`/ingestion/sync?include_past=${includePast}&past_limit=${pastLimit}`, { method: 'POST' });
  },

  syncSebi: async (maxDocuments: number = 10): Promise<any> => {
    return fetchFromApi(`/sebi/sync?max_documents=${maxDocuments}`, { method: 'POST' });
  },

  getSebiStatus: async (): Promise<any> => {
    return fetchFromApi(`/sebi/status`);
  },

  getDocuments: async (params?: { page?: number; page_size?: number; extraction_status?: string; ipo_id?: string }): Promise<PaginatedResponse<Document>> => {
    const query = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          query.set(key, String(val));
        }
      });
    }
    const qStr = query.toString();
    return fetchFromApi<PaginatedResponse<Document>>(`/documents${qStr ? `?${qStr}` : ''}`);
  },

  extractDocument: async (id: string): Promise<any> => {
    return fetchFromApi(`/documents/${id}/extract`, { method: 'POST' });
  },

  extractPendingDocuments: async (limit: number = 5): Promise<any> => {
    return fetchFromApi(`/sebi/extract-pending?limit=${limit}`, { method: 'POST' });
  },
};
