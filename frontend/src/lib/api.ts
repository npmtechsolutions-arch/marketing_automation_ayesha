import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";
import { useAuthStore } from "@/stores/authStore";

const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  if (
    typeof window !== "undefined" &&
    window.location.hostname !== "localhost" &&
    window.location.hostname !== "127.0.0.1"
  ) {
    return `${window.location.origin}/api/v1`;
  }
  return "http://localhost:8000/api/v1";
};

const API_BASE_URL = getApiBaseUrl();

// Tokens are NOT stored in localStorage.
//
// The access token lives in zustand state (memory only): it dies with the tab,
// and a script that manages to run on the page cannot read it out of storage
// after the fact. The refresh token is never visible to JavaScript at all --
// the backend sets it as an httpOnly cookie scoped to /api/v1/auth, which the
// browser attaches to refresh and logout calls and nothing else.
//
// withCredentials is what makes the browser send that cookie cross-origin, and
// it is why the API's CORS allow-list has to be exact origins.
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 60000,
  withCredentials: true,
});

// Request interceptor - attach the in-memory access token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().accessToken;
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// A single in-flight refresh, shared by every request that gets a 401.
//
// Access tokens are short-lived now, so a page that fires several requests at
// once will see several 401s at once. Without this they would each refresh
// independently; because refresh tokens rotate, the second would present a
// token the first had already spent, the backend would read that as theft, and
// it would revoke the session -- logging the user out for loading a dashboard.
let refreshInFlight: Promise<string> | null = null;

function refreshAccessToken(): Promise<string> {
  if (!refreshInFlight) {
    refreshInFlight = axios
      .post(
        `${API_BASE_URL}/auth/refresh`,
        {},
        { withCredentials: true } // the refresh token rides in the cookie
      )
      .then(({ data }) => {
        useAuthStore.getState().setSession(data.access_token, data.user ?? null);
        return data.access_token as string;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

function redirectToLogin() {
  useAuthStore.getState().clearSession();
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

// Response interceptor - refresh once on 401, then replay the request
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & {
      _retry?: boolean;
      url?: string;
    };

    const isAuthEndpoint =
      originalRequest?.url?.includes("/auth/refresh") ||
      originalRequest?.url?.includes("/auth/login") ||
      originalRequest?.url?.includes("/auth/logout");

    // Never try to refresh a failed refresh -- that is an infinite loop.
    if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      originalRequest._retry = true;
      try {
        const token = await refreshAccessToken();
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${token}`;
        }
        return api(originalRequest);
      } catch {
        redirectToLogin();
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  }
);

export { refreshAccessToken };

// Generic request helpers
export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.get<T>(url, config);
  return response.data;
}

export async function post<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await api.post<T>(url, data, config);
  return response.data;
}

export async function put<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await api.put<T>(url, data, config);
  return response.data;
}

export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.delete<T>(url, config);
  return response.data;
}

// The active workspace comes from the auth store, which is the single source of
// truth. It used to be read straight from localStorage in seven different
// places, each of which could disagree with the others after a switch.
//
// The async signature is kept so the ~40 existing call sites need no change.
export async function getAccountId(): Promise<string | null> {
  const { activeWorkspaceId, loadTenants } = useAuthStore.getState();
  if (activeWorkspaceId) return activeWorkspaceId;

  // Not loaded yet (a deep link straight into a page, say).
  await loadTenants();
  return useAuthStore.getState().activeWorkspaceId;
}

export function getAccountIdSync(): string | null {
  return useAuthStore.getState().activeWorkspaceId;
}

export default api;
