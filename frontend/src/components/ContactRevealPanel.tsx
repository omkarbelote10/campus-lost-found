"use client"

import { BadgeCheck, Clock, Mail, MapPin, Package, Phone, Star, X } from "lucide-react"
import { ItemDetail } from "@/hooks/useItemDetail"
import { OwnerContact } from "@/services/claimVerification"
import { resolveMediaUrl } from "@/services/api"

interface ContactRevealPanelProps {
  item: ItemDetail
  contact: OwnerContact
  onDismiss: () => void
}

/**
 * Shown on the page itself once a challenge passes -- the dialog closes and
 * this takes its place so the contact stays visible while the claimant writes
 * it down or reaches out.
 */
export default function ContactRevealPanel({ item, contact, onDismiss }: ContactRevealPanelProps) {
  const thumbnail = item.image_urls?.[0]

  return (
    <section className="contact-panel" aria-live="polite">
      <button type="button" className="contact-dismiss" onClick={onDismiss} aria-label="Dismiss contact details">
        <X size={16} />
      </button>

      <header className="contact-head">
        <div className="contact-check">
          <BadgeCheck size={22} />
        </div>
        <div>
          <p className="eyebrow">Ownership verified</p>
          <h2>Here is who reported this item</h2>
          <p className="contact-lede">
            Your answers matched the reported details, so the contact information below has been released.
          </p>
        </div>
      </header>

      <div className="contact-grid">
        <article className="contact-person">
          <div className="contact-avatar">{contact.full_name.charAt(0).toUpperCase()}</div>
          <div className="contact-person-body">
            <h3>{contact.full_name}</h3>
            <div className="contact-pills">
              {contact.role ? <span className="role-pill">{contact.role}</span> : null}
              {typeof contact.karma_score === "number" ? (
                <span className="contact-karma">
                  <Star size={12} fill="currentColor" /> {contact.karma_score} karma
                </span>
              ) : null}
            </div>

            <ul className="contact-lines">
              <li>
                <Mail size={15} />
                <a href={`mailto:${contact.email}`}>{contact.email}</a>
              </li>
              {contact.phone_number ? (
                <li>
                  <Phone size={15} />
                  <a href={`tel:${contact.phone_number.replace(/\s+/g, "")}`}>{contact.phone_number}</a>
                </li>
              ) : null}
              {contact.preferred_window ? (
                <li>
                  <Clock size={15} />
                  Usually available {contact.preferred_window}
                </li>
              ) : null}
            </ul>
          </div>
        </article>

        <aside className="contact-item">
          <div className="contact-thumb">
            {thumbnail ? <img src={resolveMediaUrl(thumbnail)} alt={item.title} /> : <Package size={22} />}
          </div>
          <div>
            <small>Claim opened on</small>
            <h4>{item.title}</h4>
            <p>
              <MapPin size={12} /> {item.campus_zone}
            </p>
          </div>
        </aside>
      </div>

      {contact.handover_note ? <p className="contact-note">{contact.handover_note}</p> : null}

      {contact.is_placeholder ? (
        <p className="contact-placeholder-note">
          Demo contact details. These will come from the verified-claim API once it is wired up.
        </p>
      ) : null}
    </section>
  )
}
