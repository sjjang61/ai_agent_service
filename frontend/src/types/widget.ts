export interface TableSpec {
  columns: string[]
  rows: (string | number)[][]
  caption?: string
}

export interface ChartSpec {
  chart_type: 'bar' | 'line' | 'pie'
  labels: string[]
  series: { name: string; values: number[] }[]
  unit?: string
}

export interface FlowSpec {
  mermaid: string
}

export interface MapSpec {
  markers: { lat: number; lon: number; label: string; description?: string }[]
  center?: [number, number]
  zoom?: number
}

export interface StatsSpec {
  items: { label: string; value: string; note?: string; tone?: 'default' | 'positive' | 'negative' | 'accent' }[]
  columns?: number
  caption?: string
}

export type ProcessIconName =
  | 'bot' | 'user' | 'users' | 'file' | 'check' | 'search' | 'database' | 'chart' | 'mail'
  | 'code' | 'clock' | 'settings' | 'globe' | 'shield' | 'star' | 'none'

export interface ProcessSpec {
  stages: {
    items: { title: string; description?: string; icon?: ProcessIconName; highlight?: boolean }[]
    kind?: 'step' | 'result'
  }[]
  caption?: string
}

export type Widget =
  | { type: 'table'; title: string; spec: TableSpec }
  | { type: 'chart'; title: string; spec: ChartSpec }
  | { type: 'flow'; title: string; spec: FlowSpec }
  | { type: 'map'; title: string; spec: MapSpec }

  | { type: 'stats'; title: string; spec: StatsSpec }
  | { type: 'process'; title: string; spec: ProcessSpec }
