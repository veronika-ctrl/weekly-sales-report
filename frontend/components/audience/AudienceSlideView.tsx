'use client'

import { Button } from '@/components/ui/button'
import { X } from 'lucide-react'

export function AudienceSlideView({
  title,
  open,
  onClose,
  children,
}: {
  title: string
  open: boolean
  onClose: () => void
  children: React.ReactNode
}) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-[100] bg-white flex flex-col">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-1.5 shrink-0">
        <h2 className="text-sm font-semibold text-gray-900 truncate">{title}</h2>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 w-7 p-0 shrink-0"
          onClick={onClose}
          aria-label="Close slide view"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 min-h-0">{children}</div>
    </div>
  )
}
