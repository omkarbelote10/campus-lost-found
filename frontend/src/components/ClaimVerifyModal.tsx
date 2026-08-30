"use client"

import { useEffect, useMemo, useState } from "react"
import { AlertCircle, Loader2, Lock, MapPin, Package, ShieldCheck, Sparkles, Tag } from "lucide-react"
import Modal from "@/components/Modal"
import { ItemDetail } from "@/hooks/useItemDetail"
import { useAuthStore } from "@/hooks/useStore"
import { resolveMediaUrl } from "@/services/api"
import {
  ChallengeQuestion,
  OwnerContact,
  fetchOwnerContact,
  generateChallengeQuestions,
  isClaimable,
  verifyChallengeAnswers,
} from "@/services/claimVerification"

const categoryLabels: Record<string, string> = {
  ELECTRONICS: "Electronics",
  WALLETS_CARDS: "Wallets & Cards",
  KEYS: "Keys",
  CLOTHING: "Clothing",
  DOCUMENTS: "Documents",
  OTHER: "Other",
}

interface ClaimVerifyModalProps {
  item: ItemDetail | null
  onClose: () => void
  onVerified: (item: ItemDetail, contact: OwnerContact) => void
}

export default function ClaimVerifyModal({ item, onClose, onVerified }: ClaimVerifyModalProps) {
  const viewerId: number | null = useAuthStore((state) => state.user?.id ?? null)
  const [questions, setQuestions] = useState<ChallengeQuestion[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [building, setBuilding] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [failure, setFailure] = useState("")
  const [attempts, setAttempts] = useState(0)

  useEffect(() => {
    // Never build a challenge for a report that cannot be claimed -- the
    // callers already filter, this keeps the rule true if one ever forgets.
    if (!item || !isClaimable(item, viewerId)) return

    let active = true
    setBuilding(true)
    setQuestions([])
    setAnswers({})
    setFailure("")
    setAttempts(0)

    generateChallengeQuestions(item)
      .then((generated) => {
        if (active) setQuestions(generated)
      })
      .catch(() => {
        if (active) setFailure("We could not build the verification questions. Close and try again.")
      })
      .finally(() => {
        if (active) setBuilding(false)
      })

    return () => {
      active = false
    }
  }, [item, viewerId])

  const required = useMemo(() => questions.filter((question) => question.weight > 0), [questions])
  const answeredCount = required.filter((question) => (answers[question.id] || "").trim()).length
  const ready = required.length > 0 && answeredCount === required.length

  if (!item || !isClaimable(item, viewerId)) return null

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!ready || submitting) return

    setSubmitting(true)
    setFailure("")

    try {
      const result = await verifyChallengeAnswers(item, questions, answers)
      if (!result.matched) {
        setAttempts((count) => count + 1)
        setFailure(result.message)
        return
      }
      const contact = await fetchOwnerContact(item)
      onVerified(item, contact)
    } catch {
      setFailure("Verification could not be completed. Please try again in a moment.")
    } finally {
      setSubmitting(false)
    }
  }

  const thumbnail = item.image_urls?.[0]

  return (
    <Modal open onClose={onClose} labelledBy="claim-verify-title">
      <form onSubmit={handleSubmit} className="claim-form">
        <header className="claim-head">
          <div className="claim-head-icon">
            <ShieldCheck size={20} />
          </div>
          <div>
            <h2 id="claim-verify-title">Verify that this is yours</h2>
            <p>Answer a few questions only the real owner could know. Contact details unlock on a match.</p>
          </div>
        </header>

        <div className="modal-scroll">
          <div className="claim-item">
            <div className="claim-thumb">
              {thumbnail ? (
                <img src={resolveMediaUrl(thumbnail)} alt={item.title} />
              ) : item.is_high_value ? (
                <Lock size={20} />
              ) : (
                <Package size={20} />
              )}
            </div>
            <div className="claim-item-body">
              <h3>{item.title}</h3>
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
              <p className="claim-item-description">{item.description}</p>
            </div>
          </div>

          <p className="claim-ai-note">
            <Sparkles size={14} />
            These questions are generated from the reported item&apos;s own details.
          </p>

          {failure ? (
            <p className="claim-failure">
              <AlertCircle size={16} />
              <span>
                {failure}
                {attempts > 1 ? <small>Attempt {attempts}. Be as specific as you can.</small> : null}
              </span>
            </p>
          ) : null}

          {building ? (
            <div className="claim-building">
              <Loader2 size={18} className="spin" />
              Preparing your verification questions...
            </div>
          ) : (
            <ol className="claim-questions">
              {questions.map((question, index) => (
                <li key={question.id} className="claim-question">
                  <div className="claim-question-head">
                    <span className="claim-index">{index + 1}</span>
                    <div>
                      <p className="claim-prompt">
                        {question.prompt}
                        {question.weight === 0 ? <em> Optional</em> : null}
                      </p>
                      {question.helper ? <small>{question.helper}</small> : null}
                    </div>
                  </div>

                  {question.type === "choice" ? (
                    <div className="claim-options">
                      {(question.options || []).map((option) => (
                        <label
                          key={option}
                          className={`claim-option ${answers[question.id] === option ? "selected" : ""}`}
                        >
                          <input
                            type="radio"
                            name={question.id}
                            value={option}
                            checked={answers[question.id] === option}
                            onChange={() => setAnswers({ ...answers, [question.id]: option })}
                          />
                          {option}
                        </label>
                      ))}
                    </div>
                  ) : (
                    <textarea
                      className="claim-textarea"
                      rows={3}
                      value={answers[question.id] || ""}
                      placeholder={question.placeholder}
                      onChange={(event) => setAnswers({ ...answers, [question.id]: event.target.value })}
                    />
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>

        <footer className="modal-foot">
          <span className="claim-progress">
            {building ? "Generating..." : `${answeredCount} of ${required.length} answered`}
          </span>
          <button type="button" className="modal-ghost" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button type="submit" className="modal-primary" disabled={!ready || submitting}>
            {submitting ? <Loader2 size={16} className="spin" /> : <ShieldCheck size={16} />}
            {submitting ? "Checking answers..." : "Submit answers"}
          </button>
        </footer>
      </form>
    </Modal>
  )
}
