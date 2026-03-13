"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { trustApi } from "@/lib/api";

interface NotificationEvent {
  event_type: string;
  label: string;
  message: string;
  timestamp: string;
  delivered: boolean;
}

interface Props {
  ticketCode: string;
}

const EVENT_ICONS: Record<string, string> = {
  ticket_acknowledged: "📨",
  technician_assigned: "👷",
  work_started: "🔧",
  issue_resolved: "✅",
};

export default function NotificationTimeline({ ticketCode }: Props) {
  const [events, setEvents] = useState<NotificationEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    trustApi.getTicketNotifications(ticketCode)
      .then(res => setEvents(res.data))
      .catch(() => {/* silently ignore — citizen view */ })
      .finally(() => setLoading(false));
  }, [ticketCode]);

  if (loading) return null;
  if (events.length === 0) return null;

  return (
    <div className="mt-4">
      <p className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
        <span>🔔</span> Notification History
      </p>
      <div className="space-y-3">
        {events.map((ev, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08 }}
            className="flex gap-3 items-start"
          >
            {/* Timeline dot */}
            <div className="flex flex-col items-center">
              <div className="w-8 h-8 rounded-full bg-indigo-100 border-2 border-indigo-200 flex items-center justify-center text-base flex-shrink-0">
                {EVENT_ICONS[ev.event_type] || "📬"}
              </div>
              {i < events.length - 1 && (
                <div className="w-0.5 flex-1 bg-indigo-100 mt-1 min-h-[16px]" />
              )}
            </div>
            {/* Content */}
            <div className="pb-3">
              <p className="text-sm font-semibold text-gray-800">{ev.label}</p>
              <p className="text-xs text-gray-500 mt-0.5">
                We notified you on{" "}
                <span className="font-medium">
                  {new Date(ev.timestamp).toLocaleDateString("en-IN", {
                    day: "numeric", month: "long", year: "numeric",
                  })}
                </span>
              </p>
              <p className="text-xs text-gray-400 mt-0.5 italic leading-snug">
                "{ev.message.length > 120 ? ev.message.slice(0, 120) + "…" : ev.message}"
              </p>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
