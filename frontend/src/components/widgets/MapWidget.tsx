import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { MapSpec } from '../../types/widget'

export default function MapWidget({ spec }: { spec: MapSpec }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current) return
    const map = L.map(ref.current, { scrollWheelZoom: false })
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors',
    }).addTo(map)

    const group = L.featureGroup()
    spec.markers.forEach((m) => {
      // 기본 마커 아이콘은 번들러에서 이미지 경로가 깨지므로 원형 마커를 사용한다
      const marker = L.circleMarker([m.lat, m.lon], {
        radius: 8,
        color: '#1d4ed8',
        fillColor: '#60a5fa',
        fillOpacity: 0.9,
        weight: 2,
      })
      const box = document.createElement('div')
      const title = document.createElement('strong')
      title.textContent = m.label // textContent 로 넣어 HTML 주입 방지
      box.appendChild(title)
      if (m.description) {
        const d = document.createElement('div')
        d.textContent = m.description
        box.appendChild(d)
      }
      marker.bindPopup(box)
      marker.bindTooltip(m.label)
      group.addLayer(marker)
    })
    group.addTo(map)

    if (spec.center) {
      map.setView(spec.center, spec.zoom ?? 11)
    } else if (spec.markers.length === 1) {
      map.setView([spec.markers[0].lat, spec.markers[0].lon], spec.zoom ?? 13)
    } else {
      map.fitBounds(group.getBounds().pad(0.2))
    }
    return () => {
      map.remove()
    }
  }, [spec])

  return <div ref={ref} className="h-72 w-full rounded-lg overflow-hidden z-0" />
}
