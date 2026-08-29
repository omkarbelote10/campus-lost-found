"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { itemService, isTokenValid } from "@/services/api"

// Must match the backend's allowed upload extensions (see utils/validators.py)
const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
const MAX_IMAGE_BYTES = 10 * 1024 * 1024

// datetime-local expects local wall-clock time; toISOString() would give UTC
const toLocalDateTimeInput = (date: Date) =>
  new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)

export default function ReportFoundPage() {
  const router = useRouter()
  const [formData, setFormData] = useState({
    title: "",
    description: "",
    category: "ELECTRONICS",
    campus_zone: "Library Zone",
    incident_time: "",
    is_high_value: false,
  })
  const [images, setImages] = useState<File[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragActive, setDragActive] = useState(false)
  const [previews, setPreviews] = useState<string[]>([])

  useEffect(() => {
    const nextPreviews = images.map((image) => URL.createObjectURL(image))
    setPreviews(nextPreviews)
    return () => nextPreviews.forEach((preview) => URL.revokeObjectURL(preview))
  }, [images])

  useEffect(() => {
    if (!isTokenValid()) {
      router.replace("/login?redirect=/report/found")
      return
    }
    setFormData((current) => ({
      ...current,
      incident_time: current.incident_time || toLocalDateTimeInput(new Date()),
    }))
  }, [router])

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const { name, value, type } = e.target
    setFormData({
      ...formData,
      [name]: type === "checkbox" ? (e.target as HTMLInputElement).checked : value,
    })
  }

  const addImages = (selectedFiles: File[]) => {
    const wrongType = selectedFiles.filter((file) => !ACCEPTED_IMAGE_TYPES.includes(file.type))
    const tooLarge = selectedFiles.filter(
      (file) => ACCEPTED_IMAGE_TYPES.includes(file.type) && file.size > MAX_IMAGE_BYTES,
    )
    if (wrongType.length) {
      setError("Only JPG, PNG, GIF or WEBP images are supported.")
    } else if (tooLarge.length) {
      setError("Images must be 10MB or smaller.")
    }
    const validFiles = selectedFiles.filter(
      (file) => ACCEPTED_IMAGE_TYPES.includes(file.type) && file.size <= MAX_IMAGE_BYTES,
    )
    setImages((current) => [...current, ...validFiles].slice(0, 3))
  }

  const handleImageDrop = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault()
    setDragActive(false)
    addImages(Array.from(e.dataTransfer.files))
  }

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    addImages(Array.from(e.target.files || []))
    e.target.value = ""
  }

  const removeImage = (index: number) =>
    setImages((current) => current.filter((_, fileIndex) => fileIndex !== index))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isTokenValid()) {
      router.push("/login?redirect=/report/found")
      return
    }
    setLoading(true)
    setError("")

    try {
      const form = new FormData()
      form.append("type", "FOUND")
      form.append("title", formData.title)
      form.append("description", formData.description)
      form.append("category", formData.category)
      form.append("campus_zone", formData.campus_zone)
      form.append("incident_time", formData.incident_time)
      form.append("is_high_value", String(formData.is_high_value))

      images.forEach((img) => form.append("images", img))

      await itemService.reportItem(form)
      router.push("/dashboard")
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (err.response?.status === 401) {
        // The response interceptor already cleared the session and is redirecting
        return
      }
      setError(
        Array.isArray(detail)
          ? detail.map((item: any) => `${item.loc?.slice(-1)[0] ?? "field"}: ${item.msg}`).join("; ")
          : detail || "Failed to report item",
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="report-page">
      <div className="report-heading">
        <div>
          <p className="eyebrow">Good deed</p>
          <h1 className="display-title">Report Found Item</h1>
        </div>
        <span className="report-close" aria-hidden="true">×</span>
      </div>

      {error && <div className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</div>}

      <form onSubmit={handleSubmit} className="report-form">
        <div>
          <label className="block text-sm font-medium mb-1">Title *</label>
          <input
            type="text"
            name="title"
            value={formData.title}
            onChange={handleChange}
            required
            className="w-full border rounded px-3 py-2"
            placeholder="e.g., Set of keys with blue tag"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Description *</label>
          <textarea
            name="description"
            value={formData.description}
            onChange={handleChange}
            required
            className="w-full border rounded px-3 py-2 h-24"
            placeholder="Describe what you found, but leave out one detail only the owner would know..."
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Category *</label>
            <select
              name="category"
              value={formData.category}
              onChange={handleChange}
              className="w-full border rounded px-3 py-2"
            >
              <option value="ELECTRONICS">Electronics</option>
              <option value="WALLETS_CARDS">Wallets &amp; Cards</option>
              <option value="KEYS">Keys</option>
              <option value="CLOTHING">Clothing</option>
              <option value="DOCUMENTS">Documents</option>
              <option value="OTHER">Other</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Campus Zone *</label>
            <select
              name="campus_zone"
              value={formData.campus_zone}
              onChange={handleChange}
              className="w-full border rounded px-3 py-2"
            >
              <option value="Library Zone">Library Zone</option>
              <option value="Engineering Block">Engineering Block</option>
              <option value="Science Block">Science Block</option>
              <option value="Hostel">Hostel</option>
              <option value="Sports Complex">Sports Complex</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">When did you find it? *</label>
          <input
            type="datetime-local"
            name="incident_time"
            value={formData.incident_time}
            onChange={handleChange}
            required
            className="w-full border rounded px-3 py-2"
          />
        </div>

        <div className="flex items-center">
          <input
            type="checkbox"
            name="is_high_value"
            checked={formData.is_high_value}
            onChange={handleChange}
            className="mr-2"
          />
          <label className="text-sm font-medium">
            High-value item (photos stay hidden until a claim is verified)
          </label>
        </div>

        <div className="image-upload-field">
          <div className="image-upload-header">
            <label>Add photos</label>
            <span>{images.length}/3 selected</span>
          </div>
          <input
            id="item-images"
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/jpeg,image/png,image/gif,image/webp"
            onChange={handleImageSelect}
            className="image-input"
          />
          <label
            htmlFor="item-images"
            className={`image-dropzone ${dragActive ? "is-dragging" : ""}`}
            onDragEnter={(event) => {
              event.preventDefault()
              setDragActive(true)
            }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleImageDrop}
          >
            <span className="upload-cloud">↑</span>
            <strong>Drop images here or <u>browse</u></strong>
            <small>PNG, JPG, GIF or WEBP · up to 3 images</small>
          </label>
          {previews.length > 0 && (
            <div className="image-preview-grid">
              {previews.map((preview, index) => (
                <div className="image-preview" key={preview}>
                  <img src={preview} alt={`Selected item photo ${index + 1}`} />
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation()
                      removeImage(index)
                    }}
                    aria-label={`Remove image ${index + 1}`}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-primary text-white py-2 rounded hover:bg-blue-600 disabled:opacity-50"
        >
          {loading ? "Submitting..." : "Report Found Item"}
        </button>
      </form>
    </div>
  )
}
