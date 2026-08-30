"use client"

import { ReactNode, useEffect } from "react"
import { X } from "lucide-react"

interface ModalProps {
  open: boolean
  onClose: () => void
  labelledBy: string
  size?: "regular" | "wide"
  children: ReactNode
}

/**
 * Shared dialog shell: backdrop click and Escape close it, and the page behind
 * is frozen so the dialog does not scroll the feed underneath it.
 */
export default function Modal({ open, onClose, labelledBy, size = "regular", children }: ModalProps) {
  useEffect(() => {
    if (!open) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    window.addEventListener("keydown", onKeyDown)

    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener("keydown", onKeyDown)
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby={labelledBy}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className={`modal-panel ${size === "wide" ? "wide" : ""}`}>
        <button type="button" className="modal-close" onClick={onClose} aria-label="Close dialog">
          <X size={18} />
        </button>
        {children}
      </div>
    </div>
  )
}
