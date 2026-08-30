"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  AlertCircle,
  CalendarClock,
  Clock,
  Hash,
  HeartHandshake,
  Lock,
  MapPin,
  Package,
  ShieldCheck,
  Tag,
  UserCircle,
} from "lucide-react"
import Modal from "@/components/Modal"
import { useItemDetail, ItemDetail } from "@/hooks/useItemDetail"
import { useAuthStore } from "@/hooks/useStore"
import { resolveMediaUrl } from "@/services/api"
import { isClaimable, isOwnReport } from "@/services/claimVerification"

const categoryLabels: Record<string, string> = {
  ELECTRONICS: "Electronics",
  WALLETS_CARDS: "Wallets & Cards",
  KEYS: "Keys",
  CLOTHING: "Clothing",
  DOCUMENTS: "Documents",
  OTHER: "Other",
}

const statusLabels: Record<string, string> = {
  OPEN: "Open",
  MATCH_PENDING: "Match pending",
  HANDOVER_SCHEDULED: "Handover scheduled",
  RESOLVED: "Returned",
  UNCLAIMED_VAULT: "In vault",
}

const formatDateTime = (value?: string): string => {
  if (!value) return "Not recorded"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Not recorded"
  return date.toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

interface ItemDetailsModalProps {
  itemId: number | null
  preview?: Partial<ItemDetail> | null
  /**
   * Caller-side veto for contexts where claiming never applies. The LOST/FOUND
   * and own-report rules are enforced here regardless of what is passed.
   */
  canClaim?: boolean
  onClose: () => void
  onClaim?: (item: ItemDetail) => void
}

export default function ItemDetailsModal({
  itemId,
  preview,
  canClaim = true,
  onClose,
  onClaim,
}: ItemDetailsModalProps) {
  const { item, complete, loading, error } = useItemDetail(itemId, preview)
  const viewerId: number | null = useAuthStore((state) => state.user?.id ?? null)
  const [activeImage, setActiveImage] = useState(0)

  useEffect(() => {
    setActiveImage(0)
  }, [itemId])

  if (itemId === null) return null

  const images = item?.image_urls || []
  const masked = Boolean(item?.is_high_value) && images.length === 0
  const isLost = item?.type === "LOST"
  const tokens = item?.ocr_tokens || []
  // A LOST report is a search notice: there is no item in hand to claim. Your
  // own report is not claimable either, whichever way round it was filed.
  const own = isOwnReport(item, viewerId)
  const claimable = canClaim && isClaimable(item, viewerId)

  return (
    <Modal open onClose={onClose} labelledBy="item-details-title" size="wide">
      <div className="modal-scroll">
        <div className="detail-gallery">
          {masked ? (
            <div className="detail-masked">
              <Lock size={26} />
              <strong>Photos are protected</strong>
              <small>This is a high-value item. Images unlock once a claim is verified.</small>
            </div>
          ) : images.length > 0 ? (
            <img src={resolveMediaUrl(images[activeImage])} alt={item?.title || "Reported item"} />
          ) : (
            <div className="detail-blank">
              <Package size={38} />
              <small>No photo was attached to this report</small>
            </div>
          )}

          {item?.type ? (
            <span className={`feed-badge ${isLost ? "lost" : "found"}`}>{isLost ? "LOST" : "FOUND"}</span>
          ) : null}

          {item?.is_high_value && !masked ? (
            <span className="feed-secure" title="High-value item">
              <Lock size={14} />
            </span>
          ) : null}
        </div>

        {images.length > 1 ? (
          <div className="detail-thumbs">
            {images.map((url, index) => (
              <button
                key={url}
                type="button"
                className={index === activeImage ? "active" : ""}
                onClick={() => setActiveImage(index)}
                aria-label={`View photo ${index + 1}`}
              >
                <img src={resolveMediaUrl(url)} alt="" />
              </button>
            ))}
          </div>
        ) : null}

        <div className="detail-body">
          <h2 id="item-details-title">{item?.title || "Loading item..."}</h2>

          <div className="feed-tags">
            <span className="feed-tag zone">
              <MapPin size={12} />
              {item?.campus_zone || "--"}
            </span>
            <span className="feed-tag">
              <Tag size={12} />
              {categoryLabels[item?.category || ""] || item?.category || "--"}
            </span>
            {item?.status ? (
              <span className="feed-tag status">{statusLabels[item.status] || item.status}</span>
            ) : null}
          </div>

          {error ? (
            <p className="detail-error">
              <AlertCircle size={16} /> {error}
            </p>
          ) : null}

          <section className="detail-section">
            <h3>Description</h3>
            {loading && !complete ? (
              <div className="detail-lines">
                <span />
                <span />
                <span className="short" />
              </div>
            ) : (
              <p className="detail-description">
                {complete?.description || "No description was provided for this report."}
              </p>
            )}
          </section>

          <section className="detail-section">
            <h3>Report details</h3>
            <dl className="detail-facts">
              <div>
                <dt>
                  <CalendarClock size={13} /> Lost / found on
                </dt>
                <dd>{formatDateTime(complete?.incident_time)}</dd>
              </div>
              <div>
                <dt>
                  <Clock size={13} /> Reported on
                </dt>
                <dd>{formatDateTime(complete?.created_at || item?.created_at)}</dd>
              </div>
              <div>
                <dt>
                  <MapPin size={13} /> Campus zone
                </dt>
                <dd>{item?.campus_zone || "--"}</dd>
              </div>
              <div>
                <dt>
                  <Hash size={13} /> Reference
                </dt>
                <dd>#{String(itemId).padStart(5, "0")}</dd>
              </div>
            </dl>
          </section>

          {tokens.length > 0 ? (
            <section className="detail-section">
              <h3>Detected text on the item</h3>
              <div className="detail-tokens">
                {tokens.map((token) => (
                  <span key={token}>{token}</span>
                ))}
              </div>
            </section>
          ) : null}

          {own ? (
            <p className="detail-notice info">
              <UserCircle size={15} />
              This is your own report. Matches against it show up on your dashboard.
            </p>
          ) : canClaim && isLost ? (
            <p className="detail-notice info">
              <HeartHandshake size={15} />
              Someone is looking for this. There is nothing to claim on a lost-item report -- if you have
              picked it up, report it as found and matching will pair the two reports automatically.
            </p>
          ) : null}

          {item?.is_high_value ? (
            <p className="detail-notice">
              <Lock size={15} />
              Protected report. Full photos and the reporter&apos;s contact details stay hidden until an
              ownership challenge is passed.
            </p>
          ) : null}
        </div>
      </div>

      <footer className="modal-foot">
        <button type="button" className="modal-ghost" onClick={onClose}>
          Close
        </button>
        {claimable ? (
          <button
            type="button"
            className="modal-primary"
            disabled={!complete}
            onClick={() => complete && onClaim?.(complete)}
          >
            <ShieldCheck size={16} />
            {complete ? "Claim Match" : "Loading details..."}
          </button>
        ) : canClaim && isLost && !own ? (
          <Link href="/report/found" className="modal-primary" onClick={onClose}>
            <HeartHandshake size={16} /> I Found This
          </Link>
        ) : null}
      </footer>
    </Modal>
  )
}
