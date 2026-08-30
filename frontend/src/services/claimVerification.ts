/**
 * Ownership-challenge layer for "Claim Match".
 *
 * Everything here is a PLACEHOLDER that mimics the shape of the real service:
 * the questions are derived from the item's own details, and the answers are
 * graded by keyword overlap. When the AI question generator lands, only the
 * three exported functions below need to change -- the UI already talks to
 * them asynchronously, so swapping in real HTTP calls is a drop-in.
 */

export interface ChallengeQuestion {
  id: string
  prompt: string
  helper?: string
  type: "choice" | "text"
  options?: string[]
  /** Weight 0 means the question shows but never blocks a claim. */
  weight: number
  placeholder?: string
}

export interface VerificationResult {
  matched: boolean
  /** 0..1 share of the answerable weight the claimant got right. */
  score: number
  message: string
}

export interface OwnerContact {
  full_name: string
  email: string
  phone_number?: string
  role?: string
  karma_score?: number
  preferred_window?: string
  handover_note?: string
  /** True while the contact is demo data rather than a verified-claim payload. */
  is_placeholder?: boolean
}

export interface ChallengeItem {
  id: number
  title: string
  description?: string
  category: string
  campus_zone: string
  type: string
  incident_time?: string
  created_at?: string
  ocr_tokens?: string[]
  user_id?: number
}

/**
 * Only someone else's FOUND report can be claimed.
 *
 * A FOUND report is someone holding an item and looking for its owner, so the
 * person who lost it proves ownership and collects it. A LOST report is the
 * opposite -- a search notice from someone who has nothing to hand over, so
 * there is nothing to claim. If you have picked up the item described in a
 * LOST report, the right move is to file it as found, which puts it through
 * the matching pipeline instead.
 *
 * `viewerId` is the signed-in user. Left undefined (a signed-out visitor, or a
 * record that does not carry an owner) ownership simply is not checked -- the
 * type rule still applies.
 */
export const isClaimable = (
  item?: { type?: string; user_id?: number } | null,
  viewerId?: number | null,
): boolean => {
  if (item?.type !== "FOUND") return false
  if (viewerId != null && item.user_id != null && item.user_id === viewerId) return false
  return true
}

/** True when the report belongs to the viewer, so the UI can label it as theirs. */
export const isOwnReport = (item?: { user_id?: number } | null, viewerId?: number | null): boolean =>
  viewerId != null && item?.user_id != null && item.user_id === viewerId

// Answer keys never travel to the component tree, so they cannot be read off
// the rendered DOM or React props the way a question-embedded answer could.
const answerKeys = new Map<number, Record<string, string>>()

const COLOURS = [
  "Black", "White", "Silver", "Grey", "Blue", "Navy", "Red",
  "Green", "Yellow", "Orange", "Purple", "Pink", "Brown", "Beige", "Gold",
]

const STOPWORDS = new Set([
  "the", "and", "with", "that", "this", "have", "from", "your", "mine", "item",
  "items", "near", "when", "what", "where", "some", "very", "just", "also",
  "there", "here", "into", "onto", "about", "which", "were", "been",
  "lost", "found", "campus", "please", "thing", "stuff",
])

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

const tokenize = (value: string): string[] =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((word) => word.length >= 4 && !STOPWORDS.has(word))

// Seeded so a claimant cannot re-roll the option order by reopening the form.
function shuffle<T>(values: T[], seed: number): T[] {
  const copy = [...values]
  let state = Math.abs(seed) || 1
  for (let i = copy.length - 1; i > 0; i -= 1) {
    state = (state * 1103515245 + 12345) % 2147483648
    const j = state % (i + 1)
    const swap = copy[i]
    copy[i] = copy[j]
    copy[j] = swap
  }
  return copy
}

const detectColour = (haystack: string): string | null =>
  COLOURS.find((colour) => new RegExp(`\\b${colour.toLowerCase()}\\b`).test(haystack)) || null

const formatDay = (value: string, offsetDays = 0): string => {
  const date = new Date(value)
  date.setDate(date.getDate() + offsetDays)
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })
}

/**
 * Build the ownership questions for an item.
 * TODO: replace the body with the AI endpoint (e.g. POST /claims/challenge/generate)
 * once it exists. The returned shape is already what the UI renders.
 */
export async function generateChallengeQuestions(item: ChallengeItem): Promise<ChallengeQuestion[]> {
  await delay(650)

  const haystack = `${item.title} ${item.description || ""} ${(item.ocr_tokens || []).join(" ")}`.toLowerCase()
  const key: Record<string, string> = {}
  const questions: ChallengeQuestion[] = []

  const colour = detectColour(haystack)
  if (colour) {
    const distractors = shuffle(COLOURS.filter((entry) => entry !== colour), item.id).slice(0, 3)
    key.colour = colour
    questions.push({
      id: "colour",
      prompt: "What is the main colour of the item?",
      helper: "Pick the shade you would describe it as at a glance.",
      type: "choice",
      options: shuffle([colour, ...distractors], item.id + 7),
      weight: 1,
    })
  }

  const when = item.incident_time || item.created_at
  if (when && !Number.isNaN(new Date(when).getTime())) {
    const correct = formatDay(when)
    key.when = correct
    questions.push({
      id: "when",
      prompt: "Roughly when did you last have the item?",
      helper: "The reporter logged a date -- yours should line up.",
      type: "choice",
      options: shuffle(
        [correct, formatDay(when, -3), formatDay(when, 2), formatDay(when, 5)],
        item.id + 13,
      ),
      weight: 1,
    })
  }

  questions.push({
    id: "marks",
    prompt: "Describe a detail only the owner would know.",
    helper: "A sticker, engraving, scratch, case, strap, or wallpaper -- anything specific.",
    type: "text",
    placeholder: "e.g. a small dent on the bottom-left corner and a blue college sticker",
    weight: 1.4,
  })

  questions.push({
    id: "contents",
    prompt: "What was in, on, or attached to it when you lost it?",
    helper: "Cards, keyrings, cables, notes -- whatever was with the item.",
    type: "text",
    placeholder: "e.g. library card and a small brass keyring",
    weight: 1.2,
  })

  questions.push({
    id: "extra",
    prompt: "Anything else that helps confirm it is yours?",
    helper: "Optional. The reporter sees this before handing the item over.",
    type: "text",
    placeholder: "Optional -- add any extra context",
    weight: 0,
  })

  answerKeys.set(item.id, key)
  return questions
}

/**
 * Grade the claimant's answers.
 * TODO: replace with the AI grader -- it should return the same
 * {matched, score, message} triple so the UI needs no change.
 */
export async function verifyChallengeAnswers(
  item: ChallengeItem,
  questions: ChallengeQuestion[],
  answers: Record<string, string>,
): Promise<VerificationResult> {
  await delay(1100)

  const key = answerKeys.get(item.id) || {}
  const evidence = new Set(
    tokenize(`${item.title} ${item.description || ""} ${(item.ocr_tokens || []).join(" ")}`),
  )

  let earned = 0
  let available = 0

  for (const question of questions) {
    if (question.weight <= 0) continue
    available += question.weight

    const given = (answers[question.id] || "").trim()
    if (!given) continue

    if (question.type === "choice") {
      if (key[question.id] && given === key[question.id]) earned += question.weight
      continue
    }

    // Free text scores on overlap with what the reporter wrote about the item.
    const overlap = tokenize(given).filter((word) => evidence.has(word)).length
    if (overlap >= 2) earned += question.weight
    else if (overlap === 1) earned += question.weight * 0.6
  }

  const score = available > 0 ? earned / available : 0
  const matched = score >= 0.6

  return {
    matched,
    score,
    message: matched
      ? "Your answers line up with the reported details."
      : score >= 0.35
        ? "Some answers matched, but not enough to confirm ownership. Add more specific detail and try again."
        : "Those answers do not match the reported details. Check you are claiming the right item.",
  }
}

/**
 * Contact details of the person who reported the item, released only after a
 * challenge passes.
 * TODO: replace with a real endpoint that gates this on a verified claim --
 * what comes back below is demo data, not a real person.
 */
export async function fetchOwnerContact(item: ChallengeItem): Promise<OwnerContact> {
  await delay(450)

  const seed = item.user_id || item.id
  const names = ["Aarav Sharma", "Priya Nair", "Rohan Mehta", "Ishita Verma", "Kabir Singh", "Ananya Rao"]
  const windows = ["10:00 - 13:00", "13:00 - 16:00", "16:00 - 19:00"]
  const name = names[seed % names.length]

  return {
    full_name: name,
    email: `${name.toLowerCase().replace(/\s+/g, ".")}@campus.edu`,
    phone_number: `+91 9${String(80000000 + seed * 7919).slice(0, 9)}`,
    role: seed % 5 === 0 ? "STAFF" : "STUDENT",
    karma_score: 100 + (seed % 9) * 25,
    preferred_window: windows[seed % windows.length],
    handover_note: `Meet at the ${item.campus_zone} help desk and carry your student ID.`,
    is_placeholder: true,
  }
}
