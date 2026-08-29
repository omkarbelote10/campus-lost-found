"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import {
  AlertCircle,
  ArrowRight,
  Clock,
  Lock,
  MapPin,
  Package,
  Search,
  Tag,
} from "lucide-react"
import { itemService, resolveMediaUrl } from "@/services/api"

interface Item {
  id: number
  title: string
  category: string
  campus_zone: string
  type: string
  is_high_value: boolean
  image_urls: string[]
  created_at: string
}

const categoryLabels: Record<string, string> = {
  ELECTRONICS: "Electronics",
  WALLETS_CARDS: "Wallets & Cards",
  KEYS: "Keys",
  CLOTHING: "Clothing",
  DOCUMENTS: "Documents",
  OTHER: "Other",
}

const campusZones = [
  "Library Zone",
  "Engineering Block",
  "Science Block",
  "Hostel",
  "Sports Complex",
]

const typePills = [
  { value: "", label: "All" },
  { value: "LOST", label: "Lost" },
  { value: "FOUND", label: "Found" },
]

// created_at is a timestamptz, so the offset survives the trip and Date parses it
// directly. Guard anyway: an unparseable value should not blank out the card.
const timeAgo = (value: string): string => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Recently reported"
  return `Reported ${formatDistanceToNow(date, { addSuffix: true })}`
}

export default function FeedPage() {
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [query, setQuery] = useState("")
  const [filters, setFilters] = useState({
    category: "",
    campus_zone: "",
    type: "",
  })

  useEffect(() => {
    let active = true

    const fetchItems = async () => {
      setLoading(true)
      setError("")
      try {
        const response = await itemService.getFeed(0, 20, filters)
        if (active) setItems(response.data)
      } catch (err) {
        console.error("Failed to fetch items:", err)
        if (active) setError("We could not load the item feed. Check your connection and try again.")
      } finally {
        if (active) setLoading(false)
      }
    }

    fetchItems()
    return () => {
      active = false
    }
  }, [filters])

  // The feed endpoint has no text search, so the query narrows the fetched page
  // client-side across the fields a person would actually type.
  const visibleItems = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return items
    return items.filter((item) =>
      [item.title, item.campus_zone, categoryLabels[item.category] || item.category]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    )
  }, [items, query])

  const hasFilters = Boolean(query || filters.type || filters.category || filters.campus_zone)

  const clearFilters = () => {
    setQuery("")
    setFilters({ category: "", campus_zone: "", type: "" })
  }

  return (
    <div>
      <header className="feed-header">
        <div>
          <p className="eyebrow">Campus directory</p>
          <h1>Browse reported items</h1>
          <p>Every open report from across campus, newest first.</p>
        </div>
        <Link href="/report/lost" className="feed-report-link">
          Report an item <ArrowRight size={16} />
        </Link>
      </header>

      <div className="feed-toolbar">
        <div className="pill-group">
          {typePills.map((pill) => (
            <button
              key={pill.value || "all"}
              type="button"
              className={`pill ${filters.type === pill.value ? "active" : ""} ${pill.value.toLowerCase()}`}
              aria-pressed={filters.type === pill.value}
              onClick={() => setFilters({ ...filters, type: pill.value })}
            >
              {pill.value ? <span className="pill-dot" /> : null}
              {pill.label}
            </button>
          ))}
        </div>

        <label className="feed-search">
          <Search size={18} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by title, zone, or category..."
            aria-label="Search items"
          />
          {query ? (
            <button type="button" onClick={() => setQuery("")} aria-label="Clear search">
              &times;
            </button>
          ) : null}
        </label>

        <select
          className="feed-tool-select"
          value={filters.category}
          onChange={(event) => setFilters({ ...filters, category: event.target.value })}
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          {Object.entries(categoryLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>

        <select
          className="feed-tool-select"
          value={filters.campus_zone}
          onChange={(event) => setFilters({ ...filters, campus_zone: event.target.value })}
          aria-label="Filter by campus zone"
        >
          <option value="">All zones</option>
          {campusZones.map((zone) => (
            <option key={zone} value={zone}>
              {zone}
            </option>
          ))}
        </select>
      </div>

      {error ? (
        <div className="feed-error">
          <AlertCircle size={19} />
          {error}
          <button type="button" onClick={() => setFilters({ ...filters })}>
            Retry
          </button>
        </div>
      ) : null}

      <div className="feed-summary">
        <span>
          {loading ? "Loading items..." : <><strong>{visibleItems.length}</strong> {visibleItems.length === 1 ? "item" : "items"} found</>}
        </span>
        {hasFilters ? (
          <button type="button" className="feed-clear" onClick={clearFilters}>
            Clear filters
          </button>
        ) : null}
      </div>

      {loading ? (
        <div className="feed-grid">
          {[0, 1, 2, 3, 4, 5].map((key) => (
            <div key={key} className="feed-skeleton" />
          ))}
        </div>
      ) : visibleItems.length === 0 ? (
        <div className="empty-state">
          <Package size={30} />
          <p>
            {hasFilters
              ? "No items match these filters yet. Try widening your search."
              : "No open reports yet. New items will appear here as they are reported."}
          </p>
        </div>
      ) : (
        <div className="feed-grid">
          {visibleItems.map((item) => {
            const isLost = item.type === "LOST"
            const masked = item.is_high_value && item.image_urls.length === 0

            return (
              <article key={item.id} className="feed-card">
                <div className="feed-thumb">
                  {masked ? (
                    <div className="feed-masked">
                      <Lock size={22} />
                      <strong>Protected item</strong>
                      <small>Verify a claim to view photos</small>
                    </div>
                  ) : item.image_urls.length > 0 ? (
                    <img src={resolveMediaUrl(item.image_urls[0])} alt={item.title} />
                  ) : (
                    <Package size={34} />
                  )}

                  <span className={`feed-badge ${isLost ? "lost" : "found"}`}>
                    {isLost ? "LOST" : "FOUND"}
                  </span>

                  {item.is_high_value && !masked ? (
                    <span className="feed-secure" title="High-value item">
                      <Lock size={14} />
                    </span>
                  ) : null}
                </div>

                <div className="feed-body">
                  <h3 className="feed-title">{item.title}</h3>

                  <div className="feed-tags">
                    <span className="feed-tag zone">
                      <MapPin size={12} />
                      {item.campus_zone}
                    </span>
                    <span className="feed-tag">
                      <Tag size={12} />
                      {categoryLabels[item.category] || item.category}
                    </span>
                  </div>

                  <p className="feed-time">
                    <Clock size={12} />
                    {timeAgo(item.created_at)}
                  </p>

                  <div className="feed-actions">
                    <button type="button" className="feed-view">
                      View Details
                    </button>
                    <button type="button" className="feed-claim">
                      Claim Match
                    </button>
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
