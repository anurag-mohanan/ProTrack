const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(response.status, String(detail));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export interface ListParams {
  skip?: number;
  limit?: number;
  [key: string]: string | number | boolean | undefined;
}

function toQuery(params?: ListParams): string {
  if (!params) return '';
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      search.set(key, String(value));
    }
  });
  const query = search.toString();
  return query ? `?${query}` : '';
}

export function createResourceApi<T, TCreate = Partial<T>, TUpdate = Partial<T>>(
  resource: string,
) {
  return {
    list: (params?: ListParams) =>
      request<T[]>(`/${resource}${toQuery(params)}`),
    get: (id: string) => request<T>(`/${resource}/${id}`),
    create: (data: TCreate) =>
      request<T>(`/${resource}`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (id: string, data: TUpdate) =>
      request<T>(`/${resource}/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    remove: (id: string) =>
      request<void>(`/${resource}/${id}`, { method: 'DELETE' }),
  };
}
