import axios from "axios";

// Now relying on Next.js proxy rewrite for "/api" requests
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

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
  submitComplaint: (data: object) =>
    api.post("/api/public/complaints", data),
  trackTicket: (code: string) => api.get(`/api/public/track/${code}`),
  getStats: () => api.get("/api/public/stats"),
  getLeaderboard: () => api.get("/api/public/wards/leaderboard"),
  getHeatmap: (deptId?: string) => api.get("/api/public/heatmap", { params: { dept_id: deptId } }),
  getSeasonalAlerts: (wardId: number, month: number) =>
    api.get(`/api/public/seasonal-alerts?ward_id=${wardId}&month=${month}`),
  getMapIssues: (params?: Record<string, string>) =>
    api.get("/api/public/map/issues", { params }),
  getMyTickets: () => api.get("/api/public/my-tickets"),
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
  getMyTickets: () =>
    api.get("/api/officer/tickets/assigned-to-me"),
  getDashboardSummary: () =>
    api.get("/api/officer/dashboard/summary"),
  getTicket: (id: string) => api.get(`/api/officer/tickets/${id}`),
  validateTicket: (id: string, data: { category_confirmed: boolean, is_duplicate: boolean, ward_confirmed: boolean }) =>
    api.post(`/api/officer/tickets/${id}/validate`, data),
  getJuniorEngineers: () => api.get("/api/officer/staff/junior-engineers"),
  getFieldStaff: () => api.get("/api/officer/staff/field"),
  updateStatus: (id: string, status: string, reason?: string) =>
    api.patch(`/api/officer/tickets/${id}/status`, { status, reason }),
  assignTicket: (id: string, officerId?: string, technicianId?: string) =>
    api.post(`/api/officer/tickets/${id}/assign`, {
      officer_id: officerId,
      technician_id: technicianId,
    }),
  assignFieldStaff: (id: string, technicianId: string, scheduledDate: string) =>
    api.post(`/api/officer/tickets/${id}/assign-field`, {
      technician_id: technicianId,
      scheduled_date: scheduledDate
    }),
  uploadProof: (id: string, photoUrl: string) =>
    api.post(`/api/officer/tickets/${id}/verify-completion`, { after_photo_url: photoUrl }),
  getLocationHistory: (id: string) =>
    api.get(`/api/officer/tickets/${id}/location-history`),
  addRemark: (id: string, text: string) =>
    api.post(`/api/officer/tickets/${id}/remark`, { text }),
  scheduleTicket: (id: string, scheduledDate: string) =>
    api.patch(`/api/officer/tickets/${id}/schedule`, { scheduled_date: scheduledDate }),
  overridePriority: (id: string, score: number, reason: string) =>
    api.post(`/api/officer/tickets/${id}/override-priority`, {
      priority_score: score,
      reason,
    }),
  setCompletionDeadline: (id: string, completionDeadline: string, useAiSuggestion: boolean) =>
    api.patch(`/api/officer/tickets/${id}/set-completion-deadline`, {
      completion_deadline: completionDeadline,
      use_ai_suggestion: useAiSuggestion,
    }),
  downloadApr: (id: string) =>
    api.get(`/api/documents/tickets/${id}/apr`, { responseType: 'blob' }),
  getSmartSchedule: (id: string) =>
    api.get(`/api/officer/tickets/${id}/smart-schedule`),
  applySmartSchedule: (id: string, data: object) =>
    api.post(`/api/officer/tickets/${id}/smart-assign`, data),
  seedTechnicians: (deptId: string) =>
    api.post("/api/officer/staff/seed-technicians", { dept_id: deptId }),
};

export const calendarApi = {
  getEvents: (params?: { dept_id?: string; ward_id?: number; month?: number; year?: number }) =>
    api.get("/api/calendar/events", { params }),
  createEvent: (data: {
    ticket_id: string;
    dept_id: string;
    ward_id?: number;
    scheduled_date: string;
    time_slot?: string;
    notes?: string;
    is_ai_suggested?: boolean;
  }) => api.post("/api/calendar/events", data),
  deleteEvent: (id: string) => api.delete(`/api/calendar/events/${id}`),
  getAISuggestions: (deptId: string, wardId: number) =>
    api.get(`/api/calendar/ai-suggest?dept_id=${deptId}&ward_id=${wardId}`),
  applyAISuggestions: (deptId: string, wardId: number) =>
    api.post(`/api/calendar/ai-suggest/apply?dept_id=${deptId}&ward_id=${wardId}`),
};

export const councillorApi = {
  getWardSummary: (wardId?: number) =>
    api.get("/api/councillor/ward-summary", { params: wardId ? { ward_id: wardId } : {} }),
  getDeptPerformance: (wardId?: number) =>
    api.get("/api/councillor/department-performance", { params: wardId ? { ward_id: wardId } : {} }),
  getSatisfactionTrend: (wardId?: number, weeks = 8) =>
    api.get("/api/councillor/satisfaction-trend", { params: { ward_id: wardId, weeks } }),
  getTopIssues: (wardId?: number, limit = 8) =>
    api.get("/api/councillor/top-issues", { params: { ward_id: wardId, limit } }),
  getOverdueTickets: (wardId?: number) =>
    api.get("/api/councillor/overdue-tickets", { params: wardId ? { ward_id: wardId } : {} }),
  getFeed: (wardId?: number) =>
    api.get("/api/councillor/announcement-feed", { params: wardId ? { ward_id: wardId } : {} }),
  getIntelligenceBriefing: (wardId?: number) =>
    api.get("/api/councillor/intelligence/briefing", { params: wardId ? { ward_id: wardId } : {} }),
  getRootCauses: (wardId?: number) =>
    api.get("/api/councillor/intelligence/root-causes", { params: wardId ? { ward_id: wardId } : {} }),
  getPredictiveAlerts: (wardId?: number) =>
    api.get("/api/councillor/intelligence/predictions", { params: wardId ? { ward_id: wardId } : {} }),
};

export const commissionerApi = {
  getCitySummary: () => api.get("/api/commissioner/city-summary"),
  getWardPerformance: () => api.get("/api/commissioner/ward-performance"),
  getBudgetBurnRate: (weeks: number = 12) => api.get("/api/commissioner/budget-burn-rate", { params: { weeks } }),
  getCriticalOpenTickets: (limit: number = 20) => api.get("/api/commissioner/critical-open-tickets", { params: { limit } }),
};

export const socialIntelApi = {
  getSentimentOverview: (wardId?: number) =>
    api.get("/api/social-intel/sentiment-overview", { params: wardId ? { ward_id: wardId } : {} }),
  getEmergingIssues: (wardId?: number, hours = 24, limit = 8) =>
    api.get("/api/social-intel/emerging-issues", { params: { ward_id: wardId, hours, limit } }),
  getSocialPosts: (wardId?: number, platform?: string, page = 1, pageSize = 20) =>
    api.get("/api/social-intel/social-posts", { params: { ward_id: wardId, platform, page, page_size: pageSize } }),
  getPlatformStats: (wardId?: number) =>
    api.get("/api/social-intel/platform-stats", { params: wardId ? { ward_id: wardId } : {} }),
  triggerScrape: (wardId?: number, keywords?: string) =>
    api.post("/api/social-intel/trigger-scrape", null, { params: { ward_id: wardId, keywords } }),
  triggerWardScrape: (wardId?: number, keywords?: string) =>
    api.post("/api/social-intel/trigger-ward-scrape", null, { params: { ward_id: wardId, keywords } }),
};

export const analyticsApi = {
  getResourceHealth: (wardId?: number) =>
    api.get("/api/analytics/resource-health", { params: wardId ? { ward_id: wardId } : {} }),
  analyzeScenario: (params: {
    scenario_type: string;
    dept_to?: string;
    dept_from?: string;
    n_technicians: number;
    duration_weeks: number;
    ward_id?: number;
  }) => api.post("/api/analytics/scenario/analyze", params),
  getBenchmarks: (wardId?: number) =>
    api.get("/api/analytics/benchmarks", { params: wardId ? { ward_id: wardId } : {} }),
};

// ─── Pillar 3: Public Trust API ───────────────────────────────────────────────

export const trustApi = {
  // Feature 1 — AI-Verified Work Proof
  resolveWithProof: (ticketId: string, formData: FormData) =>
    api.post(`/api/v1/trust/tickets/${ticketId}/resolve-with-proof`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  getVerifiedResolutions: (wardId?: number, limit = 50) =>
    api.get("/api/v1/trust/tickets/verified-resolutions", {
      params: { ward_id: wardId, limit },
    }),

  // Feature 2 — Notification log + ward config
  getNotificationLog: (wardId?: number, limit = 100) =>
    api.get("/api/v1/trust/notifications/log", { params: { ward_id: wardId, limit } }),
  getTicketNotifications: (ticketCode: string) =>
    api.get(`/api/v1/trust/notifications/ticket/${ticketCode}`),
  getWardConfig: (wardId: number) => api.get(`/api/v1/trust/ward-config/${wardId}`),
  updateWardConfig: (wardId: number, data: {
    preferred_language?: string;
    proactive_notifications_enabled?: boolean;
    ward_name?: string;
  }) => api.patch(`/api/v1/trust/ward-config/${wardId}`, data),

  // Feature 3 — Misinformation flags
  getMisinfoFlags: (wardId?: number, riskLevel?: string, status?: string, limit = 50) =>
    api.get("/api/v1/trust/misinformation/flags", {
      params: { ward_id: wardId, risk_level: riskLevel, status, limit },
    }),
  actionMisinfoFlag: (flagId: string, action: string, editedResponse?: string) =>
    api.patch(`/api/v1/trust/misinformation/flags/${flagId}`, {
      action,
      edited_response: editedResponse,
    }),
  runMisinfoCheck: (wardId?: number) =>
    api.post("/api/v1/trust/misinformation/run-check", null, {
      params: { ward_id: wardId },
    }),

  // Feature 4 — Trust Score
  getTrustScore: (wardId: number, month?: string) =>
    api.get(`/api/v1/trust/wards/${wardId}/trust-score`, { params: month ? { month } : {} }),
  getTrustScoreHistory: (wardId: number, months = 6) =>
    api.get(`/api/v1/trust/wards/${wardId}/trust-score/history`, { params: { months } }),
  getTrustScoreInsights: (wardId: number) =>
    api.post(`/api/v1/trust/wards/${wardId}/trust-score/insights`),
};

export const opportunityApi = {
  getZones: (wardId?: number, days = 180) =>
    api.get("/api/opportunity/zones", { params: { ward_id: wardId, days } }),
};

export const proposalsApi = {
  generate: (data: {
    ward_id?: number;
    zone_cell_id?: string;
    zone_lat: number;
    zone_lng: number;
    development_type: string;
    estimated_cost?: number;
    councillor_name: string;
    ward_name: string;
    additional_context?: string;
  }) => api.post("/api/proposals/generate", data),
  download: (id: string) =>
    api.get(`/api/proposals/${id}/download`, { responseType: "blob" }),
  list: (wardId?: number) =>
    api.get("/api/proposals", { params: { ward_id: wardId } }),
  get: (id: string) => api.get(`/api/proposals/${id}`),
};

