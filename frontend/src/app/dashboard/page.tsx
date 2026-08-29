"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { ArrowRight, Bell, Calendar, FileText, Heart, MapPin, Package, Star, Users } from "lucide-react"
import { useAuthStore } from "@/hooks/useStore"
import { itemService, resolveMediaUrl } from "@/services/api"

interface DashboardItem {
  id: number
  title: string
  category: string
  campus_zone: string
  type: string
  status: string
  incident_time?: string
  image_urls?: string[]
}

const labels: Record<string, string> = { ELECTRONICS: "Electronics", WALLETS_CARDS: "Wallets & Cards", KEYS: "Keys", CLOTHING: "Clothing", DOCUMENTS: "Documents", OTHER: "Other" }

export default function DashboardPage() {
  const { user, isAuthenticated } = useAuthStore()
  const [items, setItems] = useState<DashboardItem[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState("ALL")
  const [view, setView] = useState<"grid" | "list">("grid")

  useEffect(() => {
    if (!isAuthenticated) { setLoading(false); return }
    itemService.getUserItems().then((response) => setItems(response.data)).catch(() => undefined).finally(() => setLoading(false))
  }, [isAuthenticated])

  const lostCount = items.filter((item) => item.type === "LOST").length
  const foundCount = items.filter((item) => item.type === "FOUND").length
  const returnedCount = items.filter((item) => item.status === "RESOLVED").length
  const filteredItems = useMemo(() => statusFilter === "ALL" ? items : items.filter((item) => item.status === statusFilter), [items, statusFilter])
  const displayName = user?.full_name?.split(" ")[0] || "there"
  const karma = user?.karma_score || 100

  if (!isAuthenticated) return <div className="dashboard-empty"><h1>Sign in to view your dashboard</h1><p>Your reported items and recovery activity will appear here.</p><Link href="/login" className="dashboard-primary-button">Sign in <ArrowRight size={17} /></Link></div>

  return (
    <div className="workspace-dashboard">
      <header className="workspace-header"><div><p className="eyebrow">Your campus activity</p><h1>Good afternoon, {displayName} <span className="wave">👋</span></h1><p>Here&apos;s what&apos;s happening with your lost &amp; found activity.</p></div><Link href="/report/lost" className="dashboard-primary-button"><span>+</span> Report an item</Link></header>

      <section className="dashboard-overview">
        <article className="profile-card"><div className="profile-top"><div className="profile-avatar">{displayName.charAt(0).toUpperCase()}</div><div><h2>{user?.full_name || "Campus member"}</h2><p>{user?.email}</p><span className="role-pill">{user?.role || "STUDENT"}</span></div></div><div className="karma-block"><div className="karma-icon"><Star size={32} fill="currentColor" /></div><div><p>Karma score</p><strong>{karma} <small>points</small> <span>★</span></strong><small>Thank you for helping our campus community!</small></div></div><div className="profile-metrics"><span><b>{items.length}</b>Reported</span><span><b>{returnedCount}</b>Returned</span><span><b>0</b>Matches helped</span><span><b>0</b>Upvotes</span></div></article>
        <div className="metric-grid"><article className="metric-card"><div className="metric-icon purple"><Package size={19} /></div><strong>{lostCount}</strong><p>Lost items</p><small>Active reports</small></article><article className="metric-card"><div className="metric-icon green"><Package size={19} /></div><strong>{foundCount}</strong><p>Found items</p><small>Reported by you</small></article><article className="metric-card"><div className="metric-icon violet"><Users size={19} /></div><strong>0</strong><p>Potential matches</p><small>Review when available</small></article><article className="metric-card"><div className="metric-icon gold"><Star size={19} fill="currentColor" /></div><strong>{karma}</strong><p>Karma score</p><small>Keep contributing</small></article></div>
      </section>

      <section className="dashboard-notice"><div className="notice-icon"><Bell size={20} /></div><div><strong>Stay close to your reports</strong><p>New matches and updates will appear in your item activity.</p></div><Link href="/feed">Browse items <ArrowRight size={16} /></Link></section>

      <section className="my-items-section"><div className="dashboard-section-heading"><div><p className="eyebrow">Your reports</p><h2>My items</h2></div><div className="item-controls"><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="ALL">All statuses</option><option value="OPEN">Open</option><option value="RESOLVED">Returned</option></select><button type="button" className={view === "grid" ? "selected" : ""} onClick={() => setView("grid")} aria-label="Grid view">▦</button><button type="button" className={view === "list" ? "selected" : ""} onClick={() => setView("list")} aria-label="List view">☷</button></div></div>{loading ? <div className="dashboard-placeholder">Loading your items...</div> : filteredItems.length === 0 ? <div className="dashboard-empty compact"><Package size={34} /><h3>No items yet</h3><p>You&apos;re all caught up. Report something lost or found to get started.</p><Link href="/report/lost" className="outline-dashboard-button">Report an item <ArrowRight size={16} /></Link></div> : <div className={`dashboard-item-grid ${view === "list" ? "list-view" : ""}`}>{filteredItems.map((item) => <article className="dashboard-item-card" key={item.id}><div className="dashboard-item-image">{item.image_urls?.[0] ? <img src={resolveMediaUrl(item.image_urls[0])} alt={item.title} /> : <Package size={34} />}</div><div className="dashboard-item-body"><span className={`item-status ${item.status === "RESOLVED" ? "returned" : item.type === "FOUND" ? "found-status" : "active"}`}>{item.status === "RESOLVED" ? "Returned" : item.status || "Active"}</span><h3>{item.title}</h3><p><Package size={14} /> {labels[item.category] || item.category}</p><p><MapPin size={14} /> {item.campus_zone}</p>{item.incident_time && <p><Calendar size={14} /> {new Date(item.incident_time).toLocaleDateString()}</p>}<Link href={`/feed`} className="view-details">View details <ArrowRight size={16} /></Link></div></article>)}</div>}</section>

      <section className="dashboard-lower"><article className="activity-card"><div className="dashboard-section-heading"><h2>Recent activity</h2><span className="result-count">Your latest reports</span></div>{items.slice(0, 4).map((item) => <div className="activity-row" key={item.id}><div className="activity-dot"><FileText size={15} /></div><div><p>You reported <strong>&ldquo;{item.title}&rdquo;</strong> as {item.type.toLowerCase()}.</p><small>{item.status || "Open"} · {item.campus_zone}</small></div></div>)}{items.length === 0 && <div className="activity-row"><div className="activity-dot"><Heart size={15} /></div><div><p>Your activity will appear here.</p><small>Report an item to get started</small></div></div>}</article><article className="support-card"><div className="support-icon"><Heart size={22} fill="currentColor" /></div><h2>Help make campus better</h2><p>Your contributions help build a more connected and trusted campus community.</p><div className="support-links"><Link href="/report/lost"><FileText size={17} /> Report something lost or found <ArrowRight size={15} /></Link><Link href="/feed"><Users size={17} /> Help others by returning items <ArrowRight size={15} /></Link><Link href="/dashboard"><Star size={17} /> Earn karma and unlock perks <ArrowRight size={15} /></Link></div></article></section>
    </div>
  )
}
