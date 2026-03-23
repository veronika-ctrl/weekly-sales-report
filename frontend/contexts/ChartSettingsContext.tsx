'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface ChartSettingsContextType {
  animationsEnabled: boolean
  setAnimationsEnabled: (enabled: boolean) => void
  isPdfGeneration: boolean
  setIsPdfGeneration: (isGenerating: boolean) => void
}

const ChartSettingsContext = createContext<ChartSettingsContextType | undefined>(undefined)

export function ChartSettingsProvider({ children }: { children: ReactNode }) {
  const [animationsEnabled, setAnimationsEnabled] = useState(true)
  const [isPdfGeneration, setIsPdfGeneration] = useState(false)

  // Load from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('chart_animations_enabled')
    if (saved !== null) {
      setAnimationsEnabled(saved === 'true')
    }
  }, [])

  // Save to localStorage when changed
  useEffect(() => {
    localStorage.setItem('chart_animations_enabled', String(animationsEnabled))
  }, [animationsEnabled])

  const value: ChartSettingsContextType = {
    animationsEnabled,
    setAnimationsEnabled,
    isPdfGeneration,
    setIsPdfGeneration,
  }

  return <ChartSettingsContext.Provider value={value}>{children}</ChartSettingsContext.Provider>
}

export function useChartSettings() {
  const context = useContext(ChartSettingsContext)
  if (context === undefined) {
    throw new Error('useChartSettings must be used within ChartSettingsProvider')
  }
  return context
}

export function useChartAnimations() {
  const { animationsEnabled, isPdfGeneration } = useChartSettings()
  // Disable animations during PDF generation
  return animationsEnabled && !isPdfGeneration
}
