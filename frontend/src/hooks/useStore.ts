import { create } from "zustand"

interface AuthStore {
  user: any | null
  token: string | null
  isAuthenticated: boolean
  login: (user: any, token: string) => void
  logout: () => void
  setUser: (user: any) => void
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  login: (user, token) => {
    localStorage.setItem("token", token)
    localStorage.setItem("user", JSON.stringify(user))
    set({ user, token, isAuthenticated: true })
  },
  logout: () => {
    localStorage.removeItem("token")
    localStorage.removeItem("user")
    set({ user: null, token: null, isAuthenticated: false })
  },
  setUser: (user) => set({ user }),
}))

interface ItemsStore {
  items: any[]
  currentItem: any | null
  setItems: (items: any[]) => void
  setCurrentItem: (item: any) => void
}

export const useItemsStore = create<ItemsStore>((set) => ({
  items: [],
  currentItem: null,
  setItems: (items) => set({ items }),
  setCurrentItem: (item) => set({ currentItem: item }),
}))

interface MatchesStore {
  matches: any[]
  setMatches: (matches: any[]) => void
}

export const useMatchesStore = create<MatchesStore>((set) => ({
  matches: [],
  setMatches: (matches) => set({ matches }),
}))
