import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT to every request
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Auto-logout on 401
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ─── API helpers ────────────────────────────────────────────────────────────

export const publicApi = {
  submitComplaint: (data: FormData) =>
    api.post("/api/public/complaints", data, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  trackTicket: (code: string) => api.get(`/api/public/track/${code}`),
  getStats: () => api.get("/api/public/stats"),
  getLeaderboard: () => api.get("/api/public/wards/leaderboard"),
  getHeatmap: () => api.get("/api/public/heatmap"),
  getSeasonalAlerts: (wardId: number, month: number) =>
    api.get(`/api/public/seasonal-alerts?ward_id=${wardId}&month=${month}`),
  getMapIssues: (params?: Record<string, string>) =>
    api.get("/api/public/map/issues", { params }),
};

export const authApi = {
  login: (email: string, password: string) => {
    const form = new URLSearchParams();
    form.append("username", email);
    form.append("password", password);
    return api.post("/api/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
  },
  registerPublic: (data: {
    name: string;
    email: string;
    phone: string;
    password: string;
  }) => api.post("/api/auth/register/public", data),
  logout: () => api.post("/api/auth/logout"),
};

export const officerApi = {
  getTickets: (limit = 100) =>
    api.get(`/api/officer/tickets?limit=${limit}`),
  getTicket: (id: string) => api.get(`/api/officer/tickets/${id}`),
  updateStatus: (id: string, status: string, reason?: string) =>
    api.patch(`/api/officer/tickets/${id}/status`, { status, reason }),
  overridePriority: (id: string, score: number, reason: string) =>
    api.post(`/api/officer/tickets/${id}/override-priority`, {
      priority_score: score,
      reason,
    }),
};
