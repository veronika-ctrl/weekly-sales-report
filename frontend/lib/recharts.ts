/**
 * Re-export Recharts with LineChart, AreaChart, BarChart extended to accept
 * isAnimationActive and animationDuration (not in @types/recharts CartesianChartProps).
 * Use this module instead of 'recharts' wherever you pass those props to charts.
 */
import React from 'react'
import {
  LineChart as RLineChart,
  AreaChart as RAreaChart,
  BarChart as RBarChart,
} from 'recharts'

type CartesianChartExtraProps = {
  isAnimationActive?: boolean
  animationDuration?: number
}

export const LineChart = RLineChart as React.ForwardRefExoticComponent<
  React.ComponentProps<typeof RLineChart> & CartesianChartExtraProps & React.RefAttributes<SVGSVGElement>
>
export const AreaChart = RAreaChart as React.ForwardRefExoticComponent<
  React.ComponentProps<typeof RAreaChart> & CartesianChartExtraProps & React.RefAttributes<SVGSVGElement>
>
export const BarChart = RBarChart as React.ForwardRefExoticComponent<
  React.ComponentProps<typeof RBarChart> & CartesianChartExtraProps & React.RefAttributes<SVGSVGElement>
>

export {
  CartesianGrid,
  LabelList,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  ReferenceArea,
  ReferenceLine,
} from 'recharts'
