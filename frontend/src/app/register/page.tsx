"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { authService } from "@/services/api"
import { useAuthStore } from "@/hooks/useStore"

export default function RegisterPage() {
  const router = useRouter()
  const { login } = useAuthStore()
  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleRegister = async (event: React.FormEvent) => {
    event.preventDefault()
    setError("")

    if (password !== confirmPassword) {
      setError("Passwords do not match.")
      return
    }

    setLoading(true)
    try {
      const response = await authService.register(email, password, fullName)
      login(response.data.user, response.data.access_token)
      const redirect = new URLSearchParams(window.location.search).get("redirect")
      router.push(redirect && redirect.startsWith("/") ? redirect : "/dashboard")
    } catch (err: any) {
      setError(err.response?.data?.detail || "Registration failed. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="report-page" style={{ maxWidth: 560 }}>
      <div className="report-heading">
        <div>
          <p className="eyebrow">Join your campus network</p>
          <h1 className="display-title">Create account</h1>
        </div>
      </div>
      <form onSubmit={handleRegister} className="report-form" style={{ gridTemplateColumns: "1fr" }}>
        {error && <div style={{ gridColumn: "1 / -1", padding: "12px 14px", color: "#b42318", background: "#fff1f0", borderRadius: 9 }}>{error}</div>}
        <div>
          <label htmlFor="full-name">Full name *</label>
          <input id="full-name" type="text" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Your full name" required />
        </div>
        <div>
          <label htmlFor="register-email">Campus email *</label>
          <input id="register-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="your@college.edu" required />
        </div>
        <div>
          <label htmlFor="register-password">Password *</label>
          <input id="register-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} placeholder="At least 8 characters" required />
        </div>
        <div>
          <label htmlFor="confirm-password">Confirm password *</label>
          <input id="confirm-password" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} minLength={8} placeholder="Repeat your password" required />
        </div>
        <button type="submit" disabled={loading}>{loading ? "Creating account..." : "Create account"}</button>
        <p style={{ gridColumn: "1 / -1", margin: 0, color: "var(--muted)", textAlign: "center", fontSize: 14 }}>
          Already registered? <Link href="/login" style={{ color: "var(--blue)", fontWeight: 700 }}>Sign in</Link>
        </p>
      </form>
    </div>
  )
}
