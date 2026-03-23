/**
 * Augment Recharts CartesianChartProps so LineChart/AreaChart/BarChart etc.
 * accept isAnimationActive and animationDuration (used by shadcn/ui charts).
 * Included explicitly in tsconfig.json so Vercel picks it up.
 */
declare module 'recharts/types/util/types' {
  interface CartesianChartProps {
    isAnimationActive?: boolean
    animationDuration?: number
  }
}
