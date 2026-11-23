'use client'

import { useEffect, useState } from 'react'
import { getUkVatAdjustment } from '@/lib/api'
import { reportingWeekUsesUkVatAdjustment, UK_VAT_NOTE } from '@/lib/uk-vat-window'

export default function UkVatAdjustmentNote({ week }: { week: string }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!week || !reportingWeekUsesUkVatAdjustment(week)) {
      setVisible(false)
      return
    }
    let cancelled = false
    getUkVatAdjustment()
      .then((summary) => {
        if (!cancelled) setVisible(summary.enabled !== false)
      })
      .catch(() => {
        if (!cancelled) setVisible(true)
      })
    return () => {
      cancelled = true
    }
  }, [week])

  if (!visible) return null
  return (
    <p className="mx-4 text-xs text-muted-foreground" data-testid="uk-vat-adjustment-note">
      {UK_VAT_NOTE}
    </p>
  )
}
