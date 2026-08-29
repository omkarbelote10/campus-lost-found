"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { ArrowRight, Bell, Check, Heart, MapPin, Package, Search, ShieldCheck, Sparkles } from "lucide-react"
import { adminService, itemService, resolveMediaUrl } from "@/services/api"

interface Item {
  id: number
  title: string
  description?: string
  category: string
  campus_zone: string
  type: string
  status?: string
  image_urls?: string[]
}

const categoryLabels: Record<string, string> = {
  ELECTRONICS: "Electronics",
  WALLETS_CARDS: "Wallets & Cards",
  KEYS: "Keys",
  CLOTHING: "Clothing",
  DOCUMENTS: "Documents",
  OTHER: "Other",
}

function useScrollMotion() {
  useEffect(() => {
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible")
          revealObserver.unobserve(entry.target)
        }
      })
    }, { threshold: 0.16 })

    const revealed = document.querySelectorAll(".reveal")
    revealed.forEach((element) => revealObserver.observe(element))

    let frame = 0
    const updateParallax = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        document.querySelectorAll<HTMLElement>("[data-parallax]").forEach((element) => {
          const speed = Number(element.dataset.parallax || 0.1)
          const offset = (window.scrollY - element.offsetTop + window.innerHeight * 0.5) * speed
          element.style.setProperty("--parallax-y", `${offset}px`)
        })
      })
    }
    updateParallax()
    window.addEventListener("scroll", updateParallax, { passive: true })
    return () => {
      revealObserver.disconnect()
      window.removeEventListener("scroll", updateParallax)
      cancelAnimationFrame(frame)
    }
  }, [])
}

export default function Home() {
  useScrollMotion()
  const [stats, setStats] = useState({ total_items: 0, lost_items: 0, found_items: 0, resolved_items: 0 })
  const [items, setItems] = useState<Item[]>([])
  const [query, setQuery] = useState("")
  const [type, setType] = useState("")
  const [category, setCategory] = useState("")

  useEffect(() => {
    adminService.getSystemStats().then((response) => setStats(response.data)).catch(() => undefined)
    itemService.getFeed(0, 20).then((response) => setItems(response.data)).catch(() => undefined)
  }, [])

  const visibleItems = useMemo(() => items.filter((item) => {
    const text = `${item.title} ${item.description || ""} ${item.campus_zone}`.toLowerCase()
    return text.includes(query.toLowerCase()) && (!type || item.type === type) && (!category || item.category === category)
  }), [items, query, type, category])

  return (
    <div className="landing-page">
      <section className="landing-hero">
        <div className="hero-copy reveal">
          <p className="eyebrow"><span className="eyebrow-dot" /> Campus item recovery</p>
          <h1>Lost something?<br /><em>Let&apos;s find it.</em></h1>
          <p className="hero-lede">A calmer, smarter way for your campus community to reunite people with the things that matter.</p>
          <div className="hero-actions"><Link href="/report/lost" className="action-button lost"><span className="action-plus">+</span> Report lost item</Link><Link href="/feed" className="text-link">Browse found items <ArrowRight size={17} /></Link></div>
          <div className="trust-row"><span><Check size={15} /> Campus verified</span><span><ShieldCheck size={15} /> Secure handoff</span><span><Sparkles size={15} /> Smart matching</span></div>
        </div>
        <div className="hero-visual reveal" data-parallax="0.08">
          <div className="visual-grid" />
          <div className="hero-card hero-card-main"><div className="mini-icon blue"><Search size={20} /></div><p>Searching across campus</p><strong>2,481 items reunited</strong><div className="progress-line"><span /></div><small>Match confidence <b>94%</b></small></div>
          <div className="hero-card hero-card-float" data-parallax="-0.06"><div className="mini-icon green"><Heart size={19} /></div><p>Community impact</p><strong>86% returned</strong><small>+12% this semester</small></div>
          <div className="visual-stamp"><Package size={24} /><span>Find it<br /><b>together</b></span></div>
        </div>
      </section>

      <section className="marquee-band" aria-label="Campus recovery benefits"><div className="marquee-track"><span>REPORT</span><i>✦</i><span>DISCOVER</span><i>✦</i><span>RECONNECT</span><i>✦</i><span>REPORT</span><i>✦</i><span>DISCOVER</span><i>✦</i><span>RECONNECT</span></div></section>

      <section className="management-section section-wrap">
        <div className="section-intro reveal"><p className="eyebrow">Live campus pulse</p><h2>Everything in one<br /><em>clear view.</em></h2><p>Search active reports, follow progress, and help close the loop without the usual guesswork.</p></div>
        <div className="stat-grid reveal"><div className="stat-tile"><p>Total items</p><strong>{stats.total_items}</strong><span>Across your campus</span></div><div className="stat-tile lost"><p>Lost items</p><strong>{stats.lost_items}</strong><span>Looking for their owner</span></div><div className="stat-tile found"><p>Found items</p><strong>{stats.found_items}</strong><span>Ready to be claimed</span></div><div className="stat-tile open"><p>Open cases</p><strong>{Math.max(0, stats.total_items - stats.resolved_items)}</strong><span>Active right now</span></div></div>
        <div className="filter-panel reveal"><label className="search-box"><Search size={21} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search items, locations, or categories..." /></label><div className="filter-row"><label><span className="filter-label">Type</span><select className="filter-select" value={type} onChange={(event) => setType(event.target.value)}><option value="">All types</option><option value="LOST">Lost</option><option value="FOUND">Found</option></select></label><label><span className="filter-label">Category</span><select className="filter-select" value={category} onChange={(event) => setCategory(event.target.value)}><option value="">All categories</option>{Object.entries(categoryLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><Link href="/feed" className="filter-cta">Open item directory <ArrowRight size={16} /></Link></div></div>
        <div className="section-heading reveal"><span>Recent reports</span><span className="result-count">Showing {visibleItems.length} items</span></div>
        {visibleItems.length === 0 ? <div className="empty-state reveal"><Package size={30} /><p>No reports yet. New items will appear here.</p></div> : <div className="item-grid">{visibleItems.slice(0, 6).map((item, index) => <article key={item.id} className={`item-card reveal ${item.type === "LOST" ? "lost" : "found"}`} style={{ transitionDelay: `${index * 70}ms` }}><div className="item-image">{item.image_urls?.[0] ? <img src={resolveMediaUrl(item.image_urls[0])} alt={item.title} /> : <Package size={34} />}</div><div className="item-content"><div className="item-top"><div><h3 className="item-title">{item.title}</h3><p className="item-category">{categoryLabels[item.category] || item.category}</p></div><span className="badge">{item.status || "Open"}</span></div><p className="item-description">{item.description || "No description provided."}</p><p className="item-category item-location"><MapPin size={14} />{item.campus_zone}</p></div></article>)}</div>}
      </section>

      <section className="steps-section section-wrap"><div className="section-intro centered reveal"><p className="eyebrow">A better way back</p><h2>Small actions.<br /><em>Big reunions.</em></h2></div><div className="steps-grid"><div className="step-card reveal"><span>01</span><div className="step-icon"><Package size={24} /></div><h3>Report it</h3><p>Add the details that make your item recognizable. Photos help too.</p></div><div className="step-card reveal"><span>02</span><div className="step-icon"><Sparkles size={24} /></div><h3>We connect the dots</h3><p>Smart matching surfaces likely connections across reports.</p></div><div className="step-card reveal"><span>03</span><div className="step-icon"><Heart size={24} /></div><h3>Bring it home</h3><p>Coordinate a secure handoff and close the case together.</p></div></div></section>

      <section className="community-section section-wrap"><div className="community-panel reveal"><div><p className="eyebrow">Built by the community</p><h2>Good things find<br /><em>their way back.</em></h2><p>Every report, upvote, and returned item makes campus a little more connected.</p><Link href="/report/found" className="action-button found">Report a found item <ArrowRight size={17} /></Link></div><div className="community-art" data-parallax="0.05"><div className="art-ring ring-one" /><div className="art-ring ring-two" /><Heart size={62} fill="currentColor" /></div></div></section>

      <section className="closing-section"><div className="reveal"><Bell size={27} /><p className="eyebrow">Your next reunion could start here</p><h2>Keep good things<br /><em>moving.</em></h2><p>Lost it or found it? Your campus is ready to help.</p><div className="hero-actions"><Link href="/report/lost" className="action-button lost">Report lost item <ArrowRight size={17} /></Link><Link href="/report/found" className="action-button light">Report found item <ArrowRight size={17} /></Link></div></div></section>
      <footer className="landing-footer"><span>Lost &amp; Found Management</span><span>Made for campus communities</span><span>© 2026</span></footer>
    </div>
  )
}
