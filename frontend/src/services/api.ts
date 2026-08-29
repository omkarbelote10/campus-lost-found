import axios from "axios"
import { useAuthStore } from "@/hooks/useStore"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"

// Origin of the API, used to resolve relative upload paths like "/uploads/x.jpg"
// which are served by the backend, not by Next.js.
const API_ORIGIN = API_BASE_URL.replace(/\/api\/?$/, "")

export const resolveMediaUrl = (path?: string | null): string => {
  if (!path) return ""
  if (/^(https?:)?\/\//.test(path) || path.startsWith("data:")) return path
  return `${API_ORIGIN}${path.startsWith("/") ? "" : "/"}${path}`
}

// Decode the JWT payload and check it has not expired (30s clock-skew buffer).
export const isTokenValid = (token?: string | null): boolean => {
  const value = token ?? (typeof window !== "undefined" ? localStorage.getItem("token") : null)
  if (!value) return false
  try {
    const base64 = value.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")
    const payload = JSON.parse(atob(base64))
    return typeof payload.exp === "number" && payload.exp * 1000 > Date.now() + 30_000
  } catch {
    return false
  }
}

// NOTE: no global Content-Type here. Setting "application/json" as an instance
// default makes axios serialize FormData bodies to JSON (see transformRequest),
// which breaks every multipart upload. Axios sets JSON automatically for plain
// object payloads and multipart (with boundary) for FormData.
const apiClient = axios.create({
  baseURL: API_BASE_URL,
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const url: string = error.config?.url || ""
    const isCredentialAttempt = url.includes("/auth/login") || url.includes("/auth/register")
    if (error.response?.status === 401 && typeof window !== "undefined" && !isCredentialAttempt) {
      // Session is gone: clear storage *and* the in-memory store so the UI agrees,
      // then send the user to sign in and back to where they were.
      useAuthStore.getState().logout()
      const path = window.location.pathname
      if (path !== "/login" && path !== "/register") {
        window.location.href = `/login?redirect=${encodeURIComponent(path)}`
      }
    }
    return Promise.reject(error)
  },
)

// Add token to requests
apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token")
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  return config
})

export const authService = {
  register: (email: string, password: string, fullName: string) =>
    apiClient.post("/auth/register", { email, password, full_name: fullName }),

  login: (email: string, password: string) =>
    apiClient.post("/auth/login", { email, password }),

  getProfile: () => apiClient.get("/auth/me"),
}

export const itemService = {
  reportItem: (formData: FormData) =>
    apiClient.post("/items/report", formData),

  getFeed: (skip = 0, limit = 20, filters?: any) =>
    apiClient.get("/items/feed", { params: { skip, limit, ...filters } }),

  getItem: (id: number) => apiClient.get(`/items/${id}`),

  getUserItems: () => apiClient.get("/items/"),
}

export const matchService = {
  findMatches: (lostItemId: number) =>
    apiClient.post(`/matches/find`, { lost_item_id: lostItemId }),

  getMatch: (id: number) => apiClient.get(`/matches/${id}`),

  getItemMatches: (itemId: number) =>
    apiClient.get(`/matches/item/${itemId}`),
}

export const claimService = {
  createChallenge: (matchId: number, question: string, answer: string) =>
    apiClient.post("/claims/challenge/create", {
      match_id: matchId,
      challenge_question: question,
      claimant_answer: answer,
    }),

  respondToChallenge: (claimId: number, answer: string) =>
    apiClient.post("/claims/challenge/respond", { claim_id: claimId, answer }),

  approveChallenge: (claimId: number) =>
    apiClient.post("/claims/challenge/approve", { claim_id: claimId }),

  verifyHandshake: (qrToken: string) =>
    apiClient.post("/claims/handshake/verify", { qr_token: qrToken }),
}

export const adminService = {
  getUnclaimedItems: () => apiClient.get("/admin/vault/unclaimed"),

  processVault: (action: string) =>
    apiClient.post("/admin/vault/process", { action }),

  getSystemStats: () => apiClient.get("/admin/stats"),
}

export default apiClient
