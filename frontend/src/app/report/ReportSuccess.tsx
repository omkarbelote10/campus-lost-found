"use client"

import Link from "next/link"
import { ArrowRight, Check, MapPin, Package, Search, Sparkles } from "lucide-react"
import { resolveMediaUrl } from "@/services/api"

export interface MatchSide {
  id: number
  title: string
  type: string
  category: string
  campus_zone: string
  image_urls?: string[]
}

export interface ReportMatch {
  id: number
  total_score: number
  status: string
  your_item: MatchSide
  matched_item: MatchSide
}

const categoryLabels: Record<string, string> = {
  ELECTRONICS: "Electronics",
  WALLETS_CARDS: "Wallets & Cards",
  KEYS: "Keys",
  CLOTHING: "Clothing",
  DOCUMENTS: "Documents",
  OTHER: "Other",
}

/**
 * Shown in place of the form once a report is filed. Matching already ran server
 * side during the report, so results are here immediately -- the whole point is
 * that the user finds out on this screen, not after navigating to the dashboard.
 */
export default function ReportSuccess({
  type,
  title,
  matches,
  loading,
}: {
  type: "LOST" | "FOUND"
  title: string
  matches: ReportMatch[]
  loading: boolean
}) {
  const counterpart = type === "LOST" ? "found" : "lost"
  const strong = matches.filter((m) => m.status === "HIGH_CONFIDENCE").length

  return (
    <div className="report-success">
      <div className="success-mark">
        <Check size={30} strokeWidth={3} />
      </div>
      <h1>Report filed</h1>
      <p className="success-lede">
        &ldquo;{title}&rdquo; is now live. We checked it against every open {counterpart} report
        straight away.
      </p>

      {loading ? (
        <div className="success-checking">
          <Search size={17} /> Checking {counterpart} reports&hellip;
        </div>
      ) : matches.length === 0 ? (
        <div className="success-none">
          <Sparkles size={26} />
          <strong>No matches yet</strong>
          <p>
            Nothing open matches this closely right now. Every new {counterpart} report is
            scored against yours automatically, so check your dashboard later.
          </p>
        </div>
      ) : (
        <>
          <div className="success-count">
            <strong>
              {matches.length} potential {matches.length === 1 ? "match" : "matches"}
            </strong>
            {strong > 0 && <span className="success-strong">{strong} strong</span>}
          </div>

          <div className="success-matches">
            {matches.map((match) => {
              const isStrong = match.status === "HIGH_CONFIDENCE"
              const other = match.matched_item
              const percent = Math.round(match.total_score * 100)
              return (
                <article className="success-match" key={match.id}>
                  <div className="success-thumb">
                    {other.image_urls?.[0] ? (
                      <img src={resolveMediaUrl(other.image_urls[0])} alt={other.title} />
                    ) : (
                      <Package size={22} />
                    )}
                  </div>
                  <div className="success-match-body">
                    <h3>{other.title}</h3>
                    <p>
                      <MapPin size={12} /> {other.campus_zone}
                      <span className="success-dot">·</span>
                      {categoryLabels[other.category] || other.category}
                    </p>
                  </div>
                  <div className={`success-score ${isStrong ? "strong" : "possible"}`}>
                    <span>{percent}%</span>
                    <small>{isStrong ? "Strong" : "Possible"}</small>
                  </div>
                </article>
              )
            })}
          </div>
        </>
      )}

      <div className="success-actions">
        <Link href="/dashboard" className="action-button found">
          Go to dashboard <ArrowRight size={16} />
        </Link>
        <Link href="/feed" className="text-link">
          Browse all items <ArrowRight size={15} />
        </Link>
      </div>
    </div>
  )
}
