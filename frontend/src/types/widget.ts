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

export type Widget =
  | { type: 'table'; title: string; spec: TableSpec }
  | { type: 'chart'; title: string; spec: ChartSpec }
  | { type: 'flow'; title: string; spec: FlowSpec }
  | { type: 'map'; title: string; spec: MapSpec }
