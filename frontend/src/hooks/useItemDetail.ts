"use client"

import { useEffect, useState } from "react"
import { itemService } from "@/services/api"

export interface ItemDetail {
  id: number
  user_id: number
  title: string
  description: string
  category: string
  campus_zone: string
  type: string
  status: string
  is_high_value: boolean
  image_urls: string[]
  ocr_tokens: string[]
  incident_time: string
  created_at: string
  latitude?: number | null
  longitude?: number | null
}

/**
 * The feed and dashboard lists carry only a summary of each item, so both
 * dialogs pull the full record on open. `preview` keeps the header populated
 * while that request is in flight instead of flashing an empty panel.
 */
export function useItemDetail(itemId: number | null, preview?: Partial<ItemDetail> | null) {
  const [item, setItem] = useState<ItemDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    if (itemId === null) {
      setItem(null)
      setError("")
      return
    }

    let active = true
    setLoading(true)
    setError("")

    itemService
      .getItem(itemId)
      .then((response) => {
        if (active) setItem(response.data)
      })
      .catch(() => {
        if (active) setError("We could not load the full details for this item.")
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [itemId])

  const merged = item || (preview && itemId !== null ? ({ ...preview, id: itemId } as ItemDetail) : null)

  return { item: merged, complete: item, loading, error }
}
