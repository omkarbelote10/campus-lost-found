"use client"

import { useEffect, useState } from "react"
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

export default function FeedPage() {
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    category: "",
    campus_zone: "",
    type: "",
  })

  useEffect(() => {
    const fetchItems = async () => {
      try {
        const response = await itemService.getFeed(0, 20, filters)
        setItems(response.data)
      } catch (error) {
        console.error("Failed to fetch items:", error)
      } finally {
        setLoading(false)
      }
    }

    fetchItems()
  }, [filters])

  return (
    <div className="space-y-8">
      <h1 className="text-4xl font-bold">Campus Item Feed</h1>

      {/* Filters */}
      <div className="bg-white p-6 rounded-lg shadow space-y-4">
        <h2 className="text-lg font-semibold">Filters</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium mb-2">Type</label>
            <select
              value={filters.type}
              onChange={(e) =>
                setFilters({ ...filters, type: e.target.value })
              }
              className="w-full border rounded px-3 py-2"
            >
              <option value="">All</option>
              <option value="LOST">Lost</option>
              <option value="FOUND">Found</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Category</label>
            <select
              value={filters.category}
              onChange={(e) =>
                setFilters({ ...filters, category: e.target.value })
              }
              className="w-full border rounded px-3 py-2"
            >
              <option value="">All</option>
              <option value="ELECTRONICS">Electronics</option>
              <option value="WALLETS_CARDS">Wallets & Cards</option>
              <option value="KEYS">Keys</option>
              <option value="CLOTHING">Clothing</option>
              <option value="DOCUMENTS">Documents</option>
              <option value="OTHER">Other</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">
              Campus Zone
            </label>
            <select
              value={filters.campus_zone}
              onChange={(e) =>
                setFilters({ ...filters, campus_zone: e.target.value })
              }
              className="w-full border rounded px-3 py-2"
            >
              <option value="">All Zones</option>
              <option value="Library Zone">Library Zone</option>
              <option value="Engineering Block">Engineering Block</option>
              <option value="Science Block">Science Block</option>
              <option value="Hostel">Hostel</option>
              <option value="Sports Complex">Sports Complex</option>
            </select>
          </div>
        </div>
      </div>

      {/* Items Grid */}
      {loading ? (
        <div className="text-center py-12">Loading items...</div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          No items found matching your filters
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {items.map((item) => (
            <div
              key={item.id}
              className="bg-white rounded-lg shadow hover:shadow-lg transition"
            >
              {/* Image with sensitive item blur */}
              <div className="relative bg-gray-200 h-48 overflow-hidden">
                {item.is_high_value && item.image_urls.length === 0 ? (
                  <div className="w-full h-full flex items-center justify-center backdrop-blur-md bg-gray-300">
                    <span className="text-gray-600 font-semibold">
                      Sensitive Item - Claim to View
                    </span>
                  </div>
                ) : item.image_urls.length > 0 ? (
                  <img
                    src={resolveMediaUrl(item.image_urls[0])}
                    alt={item.title}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <span className="text-gray-500">No Image</span>
                  </div>
                )}
              </div>

              {/* Content */}
              <div className="p-4 space-y-2">
                <div className="flex justify-between items-start">
                  <h3 className="font-bold text-lg">{item.title}</h3>
                  <span
                    className={`px-2 py-1 text-xs rounded ${
                      item.type === "LOST"
                        ? "bg-red-100 text-red-800"
                        : "bg-green-100 text-green-800"
                    }`}
                  >
                    {item.type}
                  </span>
                </div>

                <p className="text-sm text-gray-600">
                  Category: <span className="font-medium">{item.category}</span>
                </p>
                <p className="text-sm text-gray-600">
                  Zone:{" "}
                  <span className="font-medium">{item.campus_zone}</span>
                </p>

                <div className="pt-4 flex gap-2">
                  <button className="flex-1 bg-primary text-white py-2 rounded hover:bg-blue-600">
                    View Details
                  </button>
                  <button className="flex-1 border border-primary text-primary py-2 rounded hover:bg-blue-50">
                    Claim Match
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
