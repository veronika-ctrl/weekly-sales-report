import { Inter } from 'next/font/google'
import { Suspense } from 'react'
import './globals.css'
import SidebarLayout from '@/components/SidebarLayout'
import { DataCacheProvider } from '@/contexts/DataCacheContext'
import { ChartSettingsProvider } from '@/contexts/ChartSettingsContext'
import LayoutContent from '@/components/LayoutContent'

const inter = Inter({ subsets: ['latin'] })

export const metadata = {
  title: 'Weekly Report Generator',
  description: 'Generate professional weekly reports with data validation',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className} suppressHydrationWarning>
        <DataCacheProvider>
          <ChartSettingsProvider>
            {/*
              Required by Next.js when the tree uses useSearchParams (see LayoutContent).
              Fallback must NOT render {children} — that mis-wires the router and can show not-found on /settings.
            */}
            <Suspense
              fallback={
                <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-gray-50 px-4">
                  <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-300 border-t-gray-700" aria-hidden />
                  <p className="text-sm text-gray-600">Loading…</p>
                </div>
              }
            >
              <LayoutContent>
                <SidebarLayout>
                  {children}
                </SidebarLayout>
              </LayoutContent>
            </Suspense>
          </ChartSettingsProvider>
        </DataCacheProvider>
      </body>
    </html>
  )
}
