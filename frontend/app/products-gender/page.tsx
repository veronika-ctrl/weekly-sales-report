'use client'

import { useState } from 'react'
import ProductsGenderTable from '@/components/ProductsGenderTable'
import { Maximize2, X } from 'lucide-react'
import { useDataCache } from '@/contexts/DataCacheContext'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

type GenderTab = 'men' | 'women'

export default function ProductsGender() {
  const { baseWeek } = useDataCache()
  const [activeTab, setActiveTab] = useState<GenderTab>('men')
  const [slideView, setSlideView] = useState(false)

  const tableBlock = (gender: GenderTab) =>
    baseWeek ? <ProductsGenderTable baseWeek={baseWeek} genderFilter={gender} compact /> : null

  return (
    <div className="space-y-2">
      {baseWeek ? (
        <>
          <Tabs
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as GenderTab)}
            className="w-full max-w-4xl"
          >
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <TabsList className="h-8">
                <TabsTrigger value="men" className="text-xs px-3 py-1">
                  Products Men
                </TabsTrigger>
                <TabsTrigger value="women" className="text-xs px-3 py-1">
                  Products Women
                </TabsTrigger>
              </TabsList>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1.5"
                onClick={() => setSlideView(true)}
              >
                <Maximize2 className="h-3.5 w-3.5" />
                Slide view
              </Button>
            </div>
            <TabsContent value="men" className="mt-0">
              {tableBlock('men')}
            </TabsContent>
            <TabsContent value="women" className="mt-0">
              {tableBlock('women')}
            </TabsContent>
          </Tabs>

          {slideView && baseWeek && (
            <div className="fixed inset-0 z-[100] bg-white flex flex-col">
              <div className="flex items-center justify-between gap-2 border-b px-3 py-1.5 shrink-0">
                <Tabs
                  value={activeTab}
                  onValueChange={(v) => setActiveTab(v as GenderTab)}
                  className="flex-1"
                >
                  <TabsList className="h-7">
                    <TabsTrigger value="men" className="text-[11px] px-2.5 py-0.5">
                      Men
                    </TabsTrigger>
                    <TabsTrigger value="women" className="text-[11px] px-2.5 py-0.5">
                      Women
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 shrink-0"
                  onClick={() => setSlideView(false)}
                  aria-label="Close slide view"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex-1 overflow-hidden p-2 min-h-0">
                <div className="h-full max-w-4xl mx-auto">
                  {tableBlock(activeTab)}
                </div>
              </div>
            </div>
          )}
        </>
      ) : null}
    </div>
  )
}
