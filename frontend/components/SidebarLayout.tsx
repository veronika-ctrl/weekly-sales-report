'use client'

import { usePathname } from 'next/navigation'
import Link from 'next/link'
import { useState } from 'react'
import { IconChartBar, IconFileChart, IconTrendingUp, IconSettings, IconChevronDown, IconChevronRight, IconMenu2, IconX } from '@tabler/icons-react'

export default function SidebarLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [isWeeklyReportsOpen, setIsWeeklyReportsOpen] = useState(true)
  const [isSalesReportsOpen, setIsSalesReportsOpen] = useState(true)
  const [isAdditionalB2cOpen, setIsAdditionalB2cOpen] = useState(true)
  const [isMarketingOpen, setIsMarketingOpen] = useState(true)
  const [isProductsOpen, setIsProductsOpen] = useState(true)
  const [isCountriesOpen, setIsCountriesOpen] = useState(true)
  const [isBudgetOpen, setIsBudgetOpen] = useState(true)

  const isActive = (path: string) => pathname === path

  const getPageTitle = () => {
    const titles: Record<string, { title: string; subtitle: string }> = {
      '/summary': { title: 'Summary', subtitle: 'Overview of weekly metrics' },
      '/summary-mtd': { title: 'Online Summary', subtitle: 'MTD actuals, budget, YTD and YoY' },
      '/top-markets': { title: 'Top Markets', subtitle: 'Sales performance by country' },
      '/online-kpis': { title: 'Online KPIs', subtitle: 'Key performance indicators for online sales' },
      '/contribution': { title: 'Contribution', subtitle: 'New vs returning customer contribution' },
      '/gender-sales': { title: 'Gender Sales', subtitle: 'Sales breakdown by gender' },
      '/men-category-sales': { title: 'Men Category Sales', subtitle: 'Sales by men product categories' },
      '/women-category-sales': { title: 'Women Category Sales', subtitle: 'Sales by women product categories' },
      '/category-sales': { title: 'Category Sales', subtitle: 'Sales by category with YoY growth' },
      '/products-new': { title: 'Products New', subtitle: 'Top products for new and returning customers' },
      '/products-gender': { title: 'Top selling products', subtitle: 'Top products by gender' },
      '/sessions-per-country': { title: 'Sessions per Country', subtitle: '(‘000)' },
      '/conversion-per-country': { title: 'Conversion per Country', subtitle: 'Conversion rates by country' },
      '/new-customers-per-country': { title: 'New Customers per Country', subtitle: 'New customer acquisition by country' },
      '/returning-customers-per-country': { title: 'Returning Customers per Country', subtitle: 'Returning customers by country' },
      '/aov-new-customers-per-country': { title: 'AOV New Customers per Country', subtitle: '(SEK)' },
      '/aov-returning-customers-per-country': { title: 'AOV Returning Customers per Country', subtitle: '(SEK)' },
      '/marketing-spend-per-country': { title: 'Marketing Spend per Country', subtitle: '(SEK \'000)' },
      '/ncac-per-country': { title: 'nCAC per Country', subtitle: '(SEK)' },
      '/contribution-new-per-country': { title: 'Contribution New Customer per Country', subtitle: '(SEK)' },
      '/contribution-new-total-per-country': { title: 'Contribution New Total per Country', subtitle: '(SEK \'000)' },
      '/contribution-returning-per-country': { title: 'Contribution Returning Customer per Country', subtitle: '(SEK)' },
      '/contribution-returning-total-per-country': { title: 'Contribution Returning Total per Country', subtitle: '(SEK \'000)' },
      '/total-contribution-per-country': { title: 'Total Contribution per Country', subtitle: '(SEK \'000)' },
      '/budget': { title: 'Budget', subtitle: 'Budget vs actual performance' },
      '/budget/general': { title: 'Budget • General', subtitle: 'Monthly overview' },
      '/budget/markets': { title: 'Budget • Markets', subtitle: 'Budget by market' },
      '/audience-total': { title: 'Audience Total', subtitle: 'Total AOV, customers, return rate, COS, CAC' },
      '/products/summary': { title: 'Products Summary', subtitle: 'Overview of product performance' },
      '/products/product': { title: 'Products', subtitle: 'Product sales by category' },
      '/products/discounts': { title: 'Discounts', subtitle: 'Discount sales analysis' },
      '/products/discount-level': { title: 'Discount Level', subtitle: 'Discount level trend by market with YoY' },
      '/products/customer': { title: 'Customer Quality', subtitle: 'Customer discount behavior analysis' },
      '/countries/sweden': { title: 'Sweden', subtitle: 'Country-specific KPIs' },
      '/countries/uk': { title: 'United Kingdom', subtitle: 'Country-specific KPIs' },
      '/countries/usa': { title: 'USA', subtitle: 'Country-specific KPIs' },
      '/countries/germany': { title: 'Germany', subtitle: 'Country-specific KPIs' },
      '/countries/france': { title: 'France', subtitle: 'Country-specific KPIs' },
      '/countries/canada': { title: 'Canada', subtitle: 'Country-specific KPIs' },
      '/countries/australia': { title: 'Australia', subtitle: 'Country-specific KPIs' },
      '/countries/switzerland': { title: 'Switzerland', subtitle: 'Country-specific KPIs' },
      '/countries/uae': { title: 'UAE', subtitle: 'Country-specific KPIs' },
      '/countries/row': { title: 'ROW', subtitle: 'Rest of World KPIs' },
      '/settings': { title: 'Settings', subtitle: 'Configure data sources and file uploads' },
    }
    
    if (pathname?.startsWith('/audience/') && pathname !== '/audience-total') {
      const slug = (pathname.replace('/audience/', '') || '').toLowerCase().replace(/\s+/g, '-')
      const displayNames: Record<string, string> = {
        uk: 'UK', usa: 'USA', uae: 'UAE', row: 'ROW',
        sweden: 'Sweden', germany: 'Germany', france: 'France', canada: 'Canada',
        australia: 'Australia', switzerland: 'Switzerland',
        'united-kingdom': 'United Kingdom', 'united-states': 'United States',
      }
      const display = displayNames[slug] ?? slug.split('-').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
      return { title: `Audience • ${display}`, subtitle: 'Total AOV, customers, return rate, COS, CAC by market' }
    }
    return titles[pathname] || { title: 'Weekly Report', subtitle: 'Generate professional reports with data validation' }
  }

  const { title, subtitle } = getPageTitle()

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className={`${isCollapsed ? 'w-16' : 'w-64'} transition-all duration-300 flex-shrink-0 border-r bg-gray-50`}>
        <div className="flex flex-col h-full">
          {/* Toggle Button */}
          <div className="flex items-center justify-between p-4 border-b">
            {!isCollapsed && <h2 className="text-lg font-semibold text-gray-900">Menu</h2>}
            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="p-2 rounded-md hover:bg-gray-200 transition-colors"
              aria-label="Toggle sidebar"
            >
              {isCollapsed ? <IconMenu2 className="h-5 w-5" /> : <IconX className="h-5 w-5" />}
            </button>
          </div>

          <div className="flex-1 overflow-y-auto py-4">
            <nav className="flex flex-col space-y-1">
              {/* Weekly Reports Dropdown */}
              <div>
                <button
                  onClick={() => setIsWeeklyReportsOpen(!isWeeklyReportsOpen)}
                  className={`w-full flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                    isActive('/summary') || isActive('/summary-mtd') || isActive('/top-markets') || isActive('/online-kpis') || 
                    isActive('/contribution') || isActive('/gender-sales') || isActive('/men-category-sales') || 
                    isActive('/women-category-sales') || isActive('/category-sales') || isActive('/products-new') || 
                    isActive('/products-gender') || isActive('/sessions-per-country') || isActive('/conversion-per-country') || 
                    isActive('/new-customers-per-country') || isActive('/returning-customers-per-country') || 
                    isActive('/aov-new-customers-per-country') || isActive('/aov-returning-customers-per-country') || 
                    isActive('/marketing-spend-per-country') || isActive('/ncac-per-country') || 
                    isActive('/contribution-new-per-country') || isActive('/contribution-new-total-per-country') || 
                    isActive('/contribution-returning-per-country') || isActive('/contribution-returning-total-per-country') || 
                    isActive('/total-contribution-per-country') || isActive('/products/summary') || 
                    isActive('/products/product') || isActive('/products/discounts') || isActive('/products/discount-level') || isActive('/products/customer') ||
                    isActive('/countries/sweden') || isActive('/countries/uk') || isActive('/countries/usa') ||
                    isActive('/countries/germany') || isActive('/countries/france') || isActive('/countries/canada') ||
                    isActive('/countries/australia') || isActive('/countries/switzerland') || isActive('/countries/uae') ||
                    isActive('/countries/row') || isActive('/audience-total') || pathname?.startsWith('/audience/')
                      ? 'bg-gray-200 text-gray-900'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <IconFileChart className="h-4 w-4 flex-shrink-0" />
                  {!isCollapsed && (
                    <>
                      <span className="flex-1 text-left">Weekly Reports</span>
                      {isWeeklyReportsOpen ? <IconChevronDown className="h-4 w-4" /> : <IconChevronRight className="h-4 w-4" />}
                    </>
                  )}
                </button>
                
                {(isCollapsed || isWeeklyReportsOpen) && (
                  <div className={`${!isCollapsed ? 'ml-4 mt-1' : ''} space-y-1`}>
                    {/* Sales Reports subgroup */}
                    <div>
                <button
                  onClick={() => setIsSalesReportsOpen(!isSalesReportsOpen)}
                  className={`w-full flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                    isActive('/summary') || isActive('/summary-mtd') || isActive('/top-markets') ||
                    isActive('/gender-sales') || isActive('/men-category-sales') ||
                    isActive('/women-category-sales') || isActive('/products-gender') ||
                    isActive('/audience-total') || pathname?.startsWith('/audience/')
                      ? 'bg-gray-200 text-gray-900'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <IconChartBar className="h-4 w-4 flex-shrink-0" />
                  {!isCollapsed && (
                    <>
                      <span className="flex-1 text-left">Sales Reports</span>
                      {isSalesReportsOpen ? <IconChevronDown className="h-4 w-4" /> : <IconChevronRight className="h-4 w-4" />}
                    </>
                  )}
                </button>

                {(isCollapsed || isSalesReportsOpen) && (
                  <div className={`${!isCollapsed ? 'ml-4 mt-1' : ''} space-y-1`}>
                    <Link
                      href="/summary"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/summary')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Summary</span>}
                    </Link>
                    <Link
                      href="/summary-mtd"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/summary-mtd')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Online Summary</span>}
                    </Link>
                    <Link
                      href="/gender-sales"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/gender-sales')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Gender Sales</span>}
                    </Link>
                    <Link
                      href="/men-category-sales"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/men-category-sales')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Men&apos;s Category Sales</span>}
                    </Link>
                    <Link
                      href="/women-category-sales"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/women-category-sales')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Women Category Sales</span>}
                    </Link>
                    <Link
                      href="/products-gender"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/products-gender')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Top selling products</span>}
                    </Link>

                    <Link
                      href="/top-markets"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/top-markets')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconFileChart className="h-4 w-4" />
                      {!isCollapsed && <span>Top Markets</span>}
                    </Link>

                    <div>
                      {!isCollapsed && (
                        <div
                          className={`w-full flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md ${
                            isActive('/audience-total') || pathname?.startsWith('/audience/')
                              ? 'bg-gray-200 text-gray-900'
                              : 'text-gray-600'
                          }`}
                        >
                          <IconChartBar className="h-4 w-4 flex-shrink-0" />
                          <span className="flex-1 text-left">Audience</span>
                        </div>
                      )}
                      <div className={`${!isCollapsed ? 'ml-4 mt-1' : ''} space-y-1`}>
                        <Link
                          href="/audience-total"
                          prefetch={true}
                          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                            isActive('/audience-total')
                              ? 'bg-gray-200 text-gray-900'
                              : 'text-gray-600 hover:bg-gray-100'
                          }`}
                        >
                          <IconChartBar className="h-4 w-4" />
                          {!isCollapsed && <span>Total</span>}
                        </Link>
                        <Link href="/audience/sweden" prefetch={true} className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${pathname === '/audience/sweden' ? 'bg-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}>
                          <IconChartBar className="h-4 w-4" />
                          {!isCollapsed && <span>Sweden</span>}
                        </Link>
                        <Link href="/audience/uk" prefetch={true} className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${pathname === '/audience/uk' ? 'bg-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}>
                          <IconChartBar className="h-4 w-4" />
                          {!isCollapsed && <span>UK</span>}
                        </Link>
                        <Link href="/audience/usa" prefetch={true} className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${pathname === '/audience/usa' ? 'bg-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}>
                          <IconChartBar className="h-4 w-4" />
                          {!isCollapsed && <span>USA</span>}
                        </Link>
                        <Link href="/audience/germany" prefetch={true} className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${pathname === '/audience/germany' ? 'bg-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}>
                          <IconChartBar className="h-4 w-4" />
                          {!isCollapsed && <span>Germany</span>}
                        </Link>
                        <Link href="/audience/france" prefetch={true} className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${pathname === '/audience/france' ? 'bg-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}>
                          <IconChartBar className="h-4 w-4" />
                          {!isCollapsed && <span>France</span>}
                        </Link>
                        <Link href="/audience/canada" prefetch={true} className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${pathname === '/audience/canada' ? 'bg-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}>
                          <IconChartBar className="h-4 w-4" />
                          {!isCollapsed && <span>Canada</span>}
                        </Link>
                        <Link href="/audience/australia" prefetch={true} className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${pathname === '/audience/australia' ? 'bg-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}>
                          <IconChartBar className="h-4 w-4" />
                          {!isCollapsed && <span>Australia</span>}
                        </Link>
                        <Link href="/audience/row" prefetch={true} className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${pathname === '/audience/row' ? 'bg-gray-200 text-gray-900' : 'text-gray-600 hover:bg-gray-100'}`}>
                          <IconChartBar className="h-4 w-4" />
                          {!isCollapsed && <span>ROW</span>}
                        </Link>
                      </div>
                    </div>
                  </div>
                )}
                    </div>

                    {/* Additional B2C reports */}
                    <div>
                <button
                  onClick={() => setIsAdditionalB2cOpen(!isAdditionalB2cOpen)}
                  className={`w-full flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                    isActive('/online-kpis') ||
                    isActive('/contribution') ||
                    isActive('/category-sales') ||
                    isActive('/products-new')
                      ? 'bg-gray-200 text-gray-900'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <IconTrendingUp className="h-4 w-4 flex-shrink-0" />
                  {!isCollapsed && (
                    <>
                      <span className="flex-1 text-left">Additional B2C reports</span>
                      {isAdditionalB2cOpen ? <IconChevronDown className="h-4 w-4" /> : <IconChevronRight className="h-4 w-4" />}
                    </>
                  )}
                </button>

                {(isCollapsed || isAdditionalB2cOpen) && (
                  <div className={`${!isCollapsed ? 'ml-4 mt-1' : ''} space-y-1`}>
                    <Link
                      href="/online-kpis"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/online-kpis')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconTrendingUp className="h-4 w-4" />
                      {!isCollapsed && <span>Online KPIs</span>}
                    </Link>
                    <Link
                      href="/contribution"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/contribution')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconTrendingUp className="h-4 w-4" />
                      {!isCollapsed && <span>Contribution</span>}
                    </Link>
                    <Link
                      href="/category-sales"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/category-sales')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Category Sales</span>}
                    </Link>
                    <Link
                      href="/products-new"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/products-new')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Products New</span>}
                    </Link>
                  </div>
                )}
                    </div>

                    {/* Markets Subgroup */}
                    <div>
                <button
                  onClick={() => setIsMarketingOpen(!isMarketingOpen)}
                  className={`w-full flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                    isActive('/sessions-per-country') || isActive('/conversion-per-country') || isActive('/new-customers-per-country') || isActive('/returning-customers-per-country') || isActive('/aov-new-customers-per-country') || isActive('/aov-returning-customers-per-country') || isActive('/marketing-spend-per-country') || isActive('/ncac-per-country') || isActive('/contribution-new-per-country') ||
                    isActive('/countries/sweden') || isActive('/countries/uk') || isActive('/countries/usa') ||
                    isActive('/countries/germany') || isActive('/countries/france') || isActive('/countries/canada') ||
                    isActive('/countries/australia') || isActive('/countries/switzerland') || isActive('/countries/uae') ||
                    isActive('/countries/row')
                      ? 'bg-gray-200 text-gray-900'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <IconTrendingUp className="h-4 w-4 flex-shrink-0" />
                  {!isCollapsed && (
                    <>
                      <span className="flex-1 text-left">Markets</span>
                      {isMarketingOpen ? <IconChevronDown className="h-4 w-4" /> : <IconChevronRight className="h-4 w-4" />}
                    </>
                  )}
                </button>
                
                {(isCollapsed || isMarketingOpen) && (
                  <div className={`${!isCollapsed ? 'ml-4 mt-1' : ''} space-y-1`}>
                    <Link
                      href="/sessions-per-country"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/sessions-per-country')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Sessions per Country</span>}
                    </Link>
                    <Link
                      href="/conversion-per-country"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/conversion-per-country')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Conversion per Country</span>}
                    </Link>
                    <Link
                      href="/new-customers-per-country"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/new-customers-per-country')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>New Customers</span>}
                    </Link>
                    <Link
                      href="/returning-customers-per-country"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/returning-customers-per-country')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Returning Customers</span>}
                    </Link>
                    <Link
                      href="/aov-new-customers-per-country"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/aov-new-customers-per-country')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>AOV New Customers</span>}
                    </Link>
                    <Link
                      href="/aov-returning-customers-per-country"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/aov-returning-customers-per-country')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>AOV Returning Customers</span>}
                    </Link>
                    <Link
                      href="/marketing-spend-per-country"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/marketing-spend-per-country')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Marketing Spend</span>}
                    </Link>
                    <Link
                      href="/ncac-per-country"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/ncac-per-country')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>nCAC</span>}
                    </Link>
                    <Link
                      href="/contribution-new-per-country"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/contribution-new-per-country')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Contribution New Customer</span>}
                    </Link>
                    <Link
                      href="/contribution-new-total-per-country"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/contribution-new-total-per-country')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Contribution New Total</span>}
                    </Link>
                    <Link
                      href="/contribution-returning-per-country"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/contribution-returning-per-country')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Contribution Returning Customer</span>}
                    </Link>
                    <Link
                      href="/contribution-returning-total-per-country"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/contribution-returning-total-per-country')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Contribution Returning Total</span>}
                    </Link>
                    <Link
                      href="/total-contribution-per-country"
                      prefetch={true}
                      className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive('/total-contribution-per-country')
                          ? 'bg-gray-200 text-gray-900'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      <IconChartBar className="h-4 w-4" />
                      {!isCollapsed && <span>Total Contribution</span>}
                    </Link>
                  </div>
                )}
                    </div>
                  </div>
                )}
              </div>

              {/* Products group */}
              <div>
                <button
                  type="button"
                  onClick={() => setIsProductsOpen(!isProductsOpen)}
                  className={`w-full flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                    isActive('/products/summary') || isActive('/products/product') ||
                    isActive('/products/discounts') || isActive('/products/discount-level') || isActive('/products/customer')
                      ? 'bg-gray-200 text-gray-900'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <IconFileChart className="h-4 w-4 flex-shrink-0" />
                  {!isCollapsed && (
                    <>
                      <span className="flex-1 text-left">Products</span>
                      {isProductsOpen ? <IconChevronDown className="h-4 w-4" /> : <IconChevronRight className="h-4 w-4" />}
                    </>
                  )}
                </button>
                {(isCollapsed || isProductsOpen) && (
                <div className={`${!isCollapsed ? 'ml-4 mt-1' : ''} space-y-1`}>
                  <Link
                    href="/products/summary"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/products/summary')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>Summary</span>}
                  </Link>
                  <Link
                    href="/products/product"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/products/product')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>Product</span>}
                  </Link>
                  <Link
                    href="/products/discounts"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/products/discounts')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>Discounts</span>}
                  </Link>
                  <Link
                    href="/products/discount-level"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/products/discount-level')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>Discount Level</span>}
                  </Link>
                  <Link
                    href="/products/customer"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/products/customer')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>Customer</span>}
                  </Link>
                </div>
                )}
              </div>

              {/* Countries group */}
              <div>
                <button
                  type="button"
                  onClick={() => setIsCountriesOpen(!isCountriesOpen)}
                  className={`w-full flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                    isActive('/countries/sweden') || isActive('/countries/uk') ||
                    isActive('/countries/usa') || isActive('/countries/germany') ||
                    isActive('/countries/france') || isActive('/countries/canada') ||
                    isActive('/countries/australia') || isActive('/countries/switzerland') ||
                    isActive('/countries/uae') || isActive('/countries/row')
                      ? 'bg-gray-200 text-gray-900'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <IconFileChart className="h-4 w-4 flex-shrink-0" />
                  {!isCollapsed && (
                    <>
                      <span className="flex-1 text-left">Countries</span>
                      {isCountriesOpen ? <IconChevronDown className="h-4 w-4" /> : <IconChevronRight className="h-4 w-4" />}
                    </>
                  )}
                </button>
                {(isCollapsed || isCountriesOpen) && (
                <div className={`${!isCollapsed ? 'ml-4 mt-1' : ''} space-y-1`}>
                  <Link
                    href="/countries/sweden"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/countries/sweden')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>Sweden</span>}
                  </Link>
                  <Link
                    href="/countries/uk"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/countries/uk')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>United Kingdom</span>}
                  </Link>
                  <Link
                    href="/countries/usa"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/countries/usa')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>USA</span>}
                  </Link>
                  <Link
                    href="/countries/germany"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/countries/germany')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>Germany</span>}
                  </Link>
                  <Link
                    href="/countries/france"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/countries/france')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>France</span>}
                  </Link>
                  <Link
                    href="/countries/canada"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/countries/canada')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>Canada</span>}
                  </Link>
                  <Link
                    href="/countries/australia"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/countries/australia')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>Australia</span>}
                  </Link>
                  <Link
                    href="/countries/switzerland"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/countries/switzerland')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>Switzerland</span>}
                  </Link>
                  <Link
                    href="/countries/uae"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/countries/uae')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>UAE</span>}
                  </Link>
                  <Link
                    href="/countries/row"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/countries/row')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>ROW</span>}
                  </Link>
                </div>
                )}
              </div>

              {/* Budget group */}
              <div>
                <button
                  type="button"
                  onClick={() => setIsBudgetOpen(!isBudgetOpen)}
                  className={`w-full flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                    isActive('/budget/general') || isActive('/budget/markets')
                      ? 'bg-gray-200 text-gray-900'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <IconFileChart className="h-4 w-4 flex-shrink-0" />
                  {!isCollapsed && (
                    <>
                      <span className="flex-1 text-left">Budget</span>
                      {isBudgetOpen ? <IconChevronDown className="h-4 w-4" /> : <IconChevronRight className="h-4 w-4" />}
                    </>
                  )}
                </button>
                {(isCollapsed || isBudgetOpen) && (
                <div className={`${!isCollapsed ? 'ml-4 mt-1' : ''} space-y-1`}>
                  <Link
                    href="/budget/general"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/budget/general')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>General</span>}
                  </Link>
                  <Link
                    href="/budget/markets"
                    prefetch={true}
                    className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive('/budget/markets')
                        ? 'bg-gray-200 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    <IconFileChart className="h-4 w-4" />
                    {!isCollapsed && <span>Markets</span>}
                  </Link>
                </div>
                )}
              </div>

              {/* Settings */}
              <Link
                href="/settings"
                prefetch={true}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                  isActive('/settings')
                    ? 'bg-gray-200 text-gray-900'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <IconSettings className="h-4 w-4" />
                {!isCollapsed && <span>Settings</span>}
              </Link>
            </nav>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        <header className="bg-white shadow-sm border-b">
          <div className="px-6 py-4">
            <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
            <p className="text-gray-600 mt-1">{subtitle}</p>
          </div>
        </header>
        <main className="flex-1 bg-gray-50 p-6">
          {children}
        </main>
      </div>
    </div>
  )
}

