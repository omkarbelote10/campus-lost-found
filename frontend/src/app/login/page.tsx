"use client"

import { useState } from "react"
import { ArrowRight, Building2, Check, Eye, LockKeyhole, Mail, User } from "lucide-react"
import { authService } from "@/services/api"
import { useAuthStore } from "@/hooks/useStore"
import { useRouter } from "next/navigation"

type AuthMode = "login" | "register"

export default function LoginPage() {
  const router = useRouter()
  const { login } = useAuthStore()
  const [mode, setMode] = useState<AuthMode>("login")
  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const switchMode = (nextMode: AuthMode) => {
    setMode(nextMode)
    setError("")
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError("")
    if (mode === "register" && password !== confirmPassword) {
      setError("Passwords do not match.")
      return
    }

    setLoading(true)
    try {
      const response = mode === "login"
        ? await authService.login(email, password)
        : await authService.register(email, password, fullName)
      login(response.data.user, response.data.access_token)
      // Only follow same-site paths, so ?redirect= cannot send users off-site
      const redirect = new URLSearchParams(window.location.search).get("redirect")
      router.push(redirect && redirect.startsWith("/") ? redirect : "/dashboard")
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setError(Array.isArray(detail) ? detail.map((item: any) => item.msg).join(" ") : detail || `${mode === "login" ? "Login" : "Registration"} failed. Please try again.`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-panel">
        <div className="auth-tabs"><button type="button" className={mode === "login" ? "active" : ""} onClick={() => switchMode("login")}>Sign in</button><button type="button" className={mode === "register" ? "active" : ""} onClick={() => switchMode("register")}>Create account</button></div>
        <div className="auth-columns">
          <section className="auth-column login-column">
            <p className="auth-kicker">{mode === "login" ? "Welcome back" : "Join the community"}</p>
            <h1>{mode === "login" ? "Sign in to your account" : "Create your account"}</h1>
            <p className="auth-description">{mode === "login" ? "Use your campus email to continue to Lost & Found Management." : "Join your campus community and help items find their way home."}</p>
            {error && <div className="auth-error">{error}</div>}
            <form onSubmit={handleSubmit} className="auth-form">
              {mode === "register" && <div className="auth-field"><label htmlFor="auth-name">Full name</label><div className="auth-input"><User size={17} /><input id="auth-name" type="text" value={fullName} onChange={(event) => setFullName(event.target.value)} required placeholder="Enter your full name" /></div></div>}
              <div className="auth-field"><label htmlFor="auth-email">Campus email</label><div className="auth-input"><Mail size={17} /><input id="auth-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required placeholder="you@college.edu" /></div></div>
              <div className="auth-field"><label htmlFor="auth-password">Password</label><div className="auth-input"><LockKeyhole size={17} /><input id="auth-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required placeholder={mode === "login" ? "Enter your password" : "Create a strong password"} /><Eye size={17} /></div></div>
              {mode === "register" && <div className="auth-field"><label htmlFor="auth-confirm-password">Confirm password</label><div className="auth-input"><LockKeyhole size={17} /><input id="auth-confirm-password" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} minLength={8} required placeholder="Repeat your password" /></div></div>}
              {mode === "login" && <div className="auth-options"><label><input type="checkbox" /> Remember me</label><a href="mailto:support@college.edu">Forgot password?</a></div>}
              <button type="submit" className="auth-submit" disabled={loading}>{loading ? (mode === "login" ? "Signing in..." : "Creating account...") : (mode === "login" ? "Sign in" : "Create account")}<ArrowRight size={19} /></button>
            </form>
            {mode === "login" && <><div className="auth-divider"><span>Or sign in with your university</span></div><button type="button" className="sso-button"><Building2 size={17} /> Sign in with University SSO</button><p className="auth-security"><LockKeyhole size={15} /> Secure authentication powered by your university.</p></>}
          </section>
          <section className="auth-column register-column"><p className="auth-kicker">{mode === "login" ? "New to campus recovery?" : "Already part of the community?"}</p><h2>{mode === "login" ? "Create your account" : "Welcome back"}</h2><p className="auth-description">{mode === "login" ? "Join the campus community and help items find their way home." : "Sign in to manage reports, matches, and returns."}</p>{mode === "login" ? <><div className="auth-benefits"><span><Check size={16} /> Report lost and found items</span><span><Check size={16} /> Get smart match notifications</span><span><Check size={16} /> Build your community karma</span></div><button type="button" onClick={() => switchMode("register")} className="create-account-button">Create account <ArrowRight size={18} /></button></> : <button type="button" onClick={() => switchMode("login")} className="create-account-button">Sign in <ArrowRight size={18} /></button>}</section>
        </div>
        <div className="auth-terms">By continuing, you agree to our <a href="#terms">Terms of Service</a> and <a href="#privacy">Privacy Policy</a>.</div>
      </div>
    </div>
  )
}
