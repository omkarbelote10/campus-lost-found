"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useAuthStore } from "@/hooks/useStore"
import { isTokenValid } from "@/services/api"

export default function NavBar() {
  const router = useRouter()
  const { user, logout } = useAuthStore()
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const storedUser = localStorage.getItem("user")
    const token = localStorage.getItem("token")
    if (storedUser && isTokenValid(token)) {
      try {
        useAuthStore.setState({ user: JSON.parse(storedUser), token, isAuthenticated: true })
      } catch {
        localStorage.removeItem("user")
      }
    } else if (storedUser || token) {
      // Expired or half-written session: clear it so the UI never shows a
      // signed-in state backed by a token the API will reject.
      localStorage.removeItem("token")
      localStorage.removeItem("user")
    }
    setReady(true)
  }, [])

  const handleLogout = () => {
    logout()
    router.push("/")
  }

  return (
    <nav className="topbar">
      <Link href="/" className="brand">
        <span className="brand-mark">◇</span>
        <span>Lost &amp; Found <small>Management</small></span>
      </Link>
      <div className="topbar-links">
        <Link href="/feed">Browse items</Link>
        <Link href="/dashboard">Dashboard</Link>
        {ready && user ? <button type="button" className="nav-login" onClick={handleLogout}>Sign out</button> : <Link href="/login" className="nav-login">Sign in</Link>}
      </div>
    </nav>
  )
}
