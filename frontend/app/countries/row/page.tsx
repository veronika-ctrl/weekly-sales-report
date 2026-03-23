import { Suspense } from 'react'
import CountryKPIsClient from '../[country]/CountryKPIsClient'

interface ROWKPIsPageProps {
  searchParams: Promise<{ pdf?: string }>
}

export default async function ROWKPIsPage({ searchParams }: ROWKPIsPageProps) {
  const resolvedSearchParams = await searchParams
  const isPdfMode = resolvedSearchParams?.pdf === '1' || resolvedSearchParams?.pdf === 'true'
  const country = 'ROW'

  return (
    <Suspense fallback={<div className="p-6 text-sm text-gray-600">Loading {country}…</div>}>
      <CountryKPIsClient countryLabel={country} apiCountry={country} isPdfMode={isPdfMode} />
    </Suspense>
  )
}

