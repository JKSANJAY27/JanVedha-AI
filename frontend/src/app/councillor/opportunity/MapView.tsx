"use client";
// MapView.tsx — Leaflet map for the Opportunity Spotter (client-only)

import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, Rectangle, Tooltip, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

interface Zone {
  cell_id: string;
  rank: number;
  opportunity_score: number;
  cell_center: { lat: number; lng: number };
  complaint_volume: number;
  dominant_category: string;
  infrastructure_recommendation: string;
  resolution_failure_rate: number;
  recurrence_score: number;
  bounds: { south: number; north: number; west: number; east: number };
}

interface MapViewProps {
  zones: Zone[];
  selectedZone: string | null;
  onZoneClick: (cellId: string) => void;
}

function zoneColor(score: number): string {
  if (score >= 80) return "#dc2626"; // red
  if (score >= 60) return "#d97706"; // amber
  return "#2563eb"; // blue
}

const ZONE_LABELS = ["A", "B", "C", "D", "E"];

// Fits map to all zones on load
function FitBounds({ zones }: { zones: Zone[] }) {
  const map = useMap();
  useEffect(() => {
    if (!zones.length) return;
    const lats = zones.flatMap((z) => [z.bounds.south, z.bounds.north]);
    const lngs = zones.flatMap((z) => [z.bounds.west, z.bounds.east]);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    try {
      map.fitBounds(
        [[minLat - 0.002, minLng - 0.002], [maxLat + 0.002, maxLng + 0.002]],
        { padding: [30, 30] }
      );
    } catch {
      // fallback
    }
  }, [zones, map]);
  return null;
}

export default function MapView({ zones, selectedZone, onZoneClick }: MapViewProps) {
  // Default center: Adyar, Chennai
  const defaultCenter: [number, number] = zones.length
    ? [
        zones.reduce((s, z) => s + z.cell_center.lat, 0) / zones.length,
        zones.reduce((s, z) => s + z.cell_center.lng, 0) / zones.length,
      ]
    : [12.97, 80.24];

  return (
    <div className="w-full h-full relative">
      <MapContainer
        center={defaultCenter}
        zoom={14}
        style={{ width: "100%", height: "100%" }}
        scrollWheelZoom
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />
        <FitBounds zones={zones} />

        {zones.map((zone, idx) => {
          const color = zoneColor(zone.opportunity_score);
          const isSelected = selectedZone === zone.cell_id;
          const label = ZONE_LABELS[idx] ?? `Z${idx + 1}`;

          return (
            <Rectangle
              key={zone.cell_id}
              bounds={[
                [zone.bounds.south, zone.bounds.west],
                [zone.bounds.north, zone.bounds.east],
              ]}
              pathOptions={{
                color: color,
                fillColor: color,
                fillOpacity: isSelected ? 0.65 : 0.35,
                weight: isSelected ? 3 : 2,
              }}
              eventHandlers={{
                click: () => onZoneClick(zone.cell_id),
              }}
            >
              <Tooltip direction="top" permanent={false} sticky>
                <div className="text-xs font-bold text-gray-800">
                  Zone {label} — Score {zone.opportunity_score}
                </div>
                <div className="text-xs text-gray-600">
                  {zone.infrastructure_recommendation}
                </div>
                <div className="text-[10px] text-gray-500 mt-0.5">
                  {zone.complaint_volume} complaints · {Math.round(zone.resolution_failure_rate * 100)}% unresolved
                </div>
              </Tooltip>
            </Rectangle>
          );
        })}
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-4 right-4 z-[1000] bg-white rounded-xl shadow-md p-3 border border-gray-100">
        <p className="text-[10px] font-bold text-gray-700 mb-2 uppercase tracking-wider">Legend</p>
        {[
          { color: "#dc2626", label: "Critical (80–100)" },
          { color: "#d97706", label: "High Priority (60–79)" },
          { color: "#2563eb", label: "Moderate (< 60)" },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-2 mb-1.5 last:mb-0">
            <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: color, opacity: 0.7 }} />
            <span className="text-[10px] text-gray-600">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
