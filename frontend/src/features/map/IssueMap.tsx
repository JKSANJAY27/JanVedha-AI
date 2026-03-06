"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import { PRIORITY_COLORS, PRIORITY_EMOJI, CHENNAI_CENTER } from "@/lib/constants";

interface MapIssue {
    id: string;
    ticket_code: string;
    description: string;
    dept_id: string;
    priority_label: string;
    priority_score: number;
    status: string;
    lat?: number;
    lng?: number;
    created_at: string;
}

interface IssueMapProps {
    issues: MapIssue[];
    onIssueClick: (issue: MapIssue) => void;
}

function getMarkerIcon(priority: string) {
    return L.divIcon({
        html: `<div style="
      font-size: 24px;
      filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
      line-height: 1;
      cursor: pointer;
    ">${PRIORITY_EMOJI[priority] ?? "📍"}</div>`,
        className: "custom-marker",
        iconSize: [32, 32],
        iconAnchor: [16, 28],
        popupAnchor: [0, -30],
    });
}

export default function IssueMap({ issues, onIssueClick }: IssueMapProps) {
    const mapContainerRef = useRef<HTMLDivElement>(null);
    const mapRef = useRef<L.Map | null>(null);
    const markersRef = useRef<L.Marker[]>([]);
    const initialFitDone = useRef(false);

    // Initialize map once
    useEffect(() => {
        if (!mapContainerRef.current || mapRef.current) return;

        const map = L.map(mapContainerRef.current, {
            center: CHENNAI_CENTER,
            zoom: 12,
        });

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "© OpenStreetMap contributors",
        }).addTo(map);

        mapRef.current = map;

        return () => {
            map.remove();
            mapRef.current = null;
        };
    }, []);

    // Update markers when issues change
    useEffect(() => {
        const map = mapRef.current;
        if (!map) return;

        // Remove old markers
        markersRef.current.forEach((m) => m.remove());
        markersRef.current = [];

        issues.forEach((issue) => {
            if (!issue.lat || !issue.lng) return;

            const marker = L.marker([issue.lat, issue.lng], {
                icon: getMarkerIcon(issue.priority_label),
            });

            marker.bindPopup(
                `<div style="min-width:200px;font-family:system-ui">
          <p style="font-family:monospace;font-weight:700;color:#1d4ed8;margin:0 0 4px">${issue.ticket_code}</p>
          <p style="font-size:12px;color:#374151;margin:0 0 6px;line-height:1.4">${issue.description?.slice(0, 100)}${issue.description?.length > 100 ? "…" : ""}</p>
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            <span style="background:${PRIORITY_COLORS[issue.priority_label]};color:white;font-size:10px;padding:2px 8px;border-radius:9999px;font-weight:600">${issue.priority_label}</span>
            <span style="background:#e5e7eb;color:#374151;font-size:10px;padding:2px 8px;border-radius:9999px">${issue.status}</span>
          </div>
        </div>`,
                { maxWidth: 260 }
            );

            marker.on("click", () => onIssueClick(issue));
            marker.addTo(map);
            markersRef.current.push(marker);
        });

        // Fit bounds only once after the initial markers are plotted
        if (markersRef.current.length > 0 && !initialFitDone.current) {
            const group = L.featureGroup(markersRef.current);
            map.fitBounds(group.getBounds().pad(0.15));
            initialFitDone.current = true;
        }
    }, [issues, onIssueClick]);

    return (
        <div
            ref={mapContainerRef}
            style={{ width: "100%", height: "100%", minHeight: "400px" }}
        />
    );
}
