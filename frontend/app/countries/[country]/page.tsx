import { Suspense } from 'react'
import { notFound } from 'next/navigation'
import CountryKPIsClient from './CountryKPIsClient'

interface CountryPageProps {
  params: Promise<{ country: string }>
  searchParams: Promise<{ pdf?: string }>
}

export default async function CountryPage({ params, searchParams }: CountryPageProps) {
  const resolvedParams = await params
  const resolvedSearchParams = await searchParams
  const countryParam = decodeURIComponent(resolvedParams.country || '').trim()
  const isPdfMode = resolvedSearchParams?.pdf === '1' || resolvedSearchParams?.pdf === 'true'

  if (!countryParam) {
    notFound()
  }

  return (
    <Suspense fallback={<div className="p-6 text-sm text-gray-600">Loading {countryParam}…</div>}>
      <CountryKPIsClient countryLabel={countryParam} apiCountry={countryParam} isPdfMode={isPdfMode} />
    </Suspense>
  )
}

