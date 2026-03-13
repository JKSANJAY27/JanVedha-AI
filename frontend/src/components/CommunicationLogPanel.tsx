"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { trustApi } from "@/lib/api";

interface NotificationEntry {
  id: string;
  ticket_id: string;
  event_type: string;
  message_sent: string;
  language: string;
  delivered: boolean;
  timestamp: string;
  ward_id: number | null;
}

interface WardConfig {
  ward_id: number;
  preferred_language: string;
  proactive_notifications_enabled: boolean;
  ward_name: string;
}

interface Props {
  wardId: number;
}

const EVENT_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  ticket_acknowledged: {
    label: "Ticket Acknowledged",
    icon: "📨",
    color: "bg-blue-100 text-blue-800 border-blue-200",
  },
  technician_assigned: {
    label: "Technician Assigned",
    icon: "👷",
    color: "bg-violet-100 text-violet-800 border-violet-200",
  },
  work_started: {
    label: "Work Started",
    icon: "🔧",
    color: "bg-amber-100 text-amber-800 border-amber-200",
  },
  issue_resolved: {
    label: "Issue Resolved",
    icon: "✅",
    color: "bg-emerald-100 text-emerald-800 border-emerald-200",
  },
};

export default function CommunicationLogPanel({ wardId }: Props) {
  const [log, setLog] = useState<NotificationEntry[]>([]);
  const [config, setConfig] = useState<WardConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingConfig, setSavingConfig] = useState(false);
  const [eventFilter, setEventFilter] = useState("all");
  const [showConfig, setShowConfig] = useState(false);

  // Local edit state for config
  const [language, setLanguage] = useState("English");
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);

  useEffect(() => {
    Promise.all([
      trustApi.getNotificationLog(wardId, 200),
      trustApi.getWardConfig(wardId),
    ])
      .then(([logRes, cfgRes]) => {
        setLog(logRes.data);
        setConfig(cfgRes.data);
        setLanguage(cfgRes.data.preferred_language);
        setNotificationsEnabled(cfgRes.data.proactive_notifications_enabled);
      })
      .catch(() => toast.error("Failed to load communication log"))
      .finally(() => setLoading(false));
  }, [wardId]);

  const handleSaveConfig = async () => {
    setSavingConfig(true);
    try {
      await trustApi.updateWardConfig(wardId, {
        preferred_language: language,
        proactive_notifications_enabled: notificationsEnabled,
      });
      toast.success("Ward notification settings saved!");
      setShowConfig(false);
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setSavingConfig(false);
    }
  };

  const filtered = eventFilter === "all" ? log : log.filter(e => e.event_type === eventFilter);
  const deliveredCount = log.filter(e => e.delivered).length;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h3 className="font-extrabold text-gray-900 text-lg flex items-center gap-2">
            💬 Communication Log
          </h3>
          <p className="text-sm text-gray-500">
            {log.length} notifications sent · {deliveredCount} delivered via Telegram
          </p>
        </div>
        <button
          onClick={() => setShowConfig(v => !v)}
          id="ward-notif-config-btn"
          className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-4 py-2 rounded-xl transition-colors flex items-center gap-1.5"
        >
          ⚙️ Notification Settings
        </button>
      </div>

      {/* Config panel */}
      {showConfig && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-indigo-50 border-2 border-indigo-200 rounded-2xl p-5 space-y-4"
        >
          <h4 className="font-bold text-indigo-800">Ward Notification Configuration</h4>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-semibold text-gray-700 block mb-2">
                Preferred Language
              </label>
              <select
                value={language}
                onChange={e => setLanguage(e.target.value)}
                className="w-full border-2 border-indigo-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 bg-white"
                id="ward-language-select"
              >
                <option value="English">🇬🇧 English</option>
                <option value="Tamil">🇮🇳 Tamil</option>
                <option value="Hindi">🇮🇳 Hindi</option>
              </select>
            </div>

            <div className="flex items-center gap-3 pt-6">
              <button
                onClick={() => setNotificationsEnabled(v => !v)}
                id="toggle-notifications-btn"
                className={`relative w-12 h-6 rounded-full transition-colors flex-shrink-0 ${
                  notificationsEnabled ? "bg-indigo-500" : "bg-gray-300"
                }`}
              >
                <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                  notificationsEnabled ? "translate-x-7" : "translate-x-1"
                }`} />
              </button>
              <span className="text-sm font-semibold text-gray-700">
                Proactive notifications {notificationsEnabled ? "enabled" : "disabled"}
              </span>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleSaveConfig}
              disabled={savingConfig}
              className="px-5 py-2.5 bg-indigo-600 text-white text-sm font-bold rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              {savingConfig ? "Saving..." : "Save Settings"}
            </button>
            <button
              onClick={() => setShowConfig(false)}
              className="px-5 py-2.5 bg-white border border-gray-200 text-gray-600 text-sm font-semibold rounded-xl hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </motion.div>
      )}

      {/* Event type filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <p className="text-xs text-gray-500 font-medium">Filter:</p>
        {["all", ...Object.keys(EVENT_LABELS)].map(key => {
          const ev = EVENT_LABELS[key];
          return (
            <button
              key={key}
              onClick={() => setEventFilter(key)}
              className={`text-xs px-3 py-1.5 rounded-full border font-semibold transition-all ${
                eventFilter === key
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}
            >
              {ev ? `${ev.icon} ${ev.label}` : "All Events"}
            </button>
          );
        })}
      </div>

      {/* Log table */}
      {loading ? (
        <div className="text-center py-10">
          <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-500 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-400">Loading...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-2xl border border-gray-100">
          <p className="text-3xl mb-2">📭</p>
          <p className="text-gray-500 font-medium">No notifications found</p>
          <p className="text-sm text-gray-400">Notifications are sent automatically at each ticket lifecycle stage.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-gray-200 shadow-sm">
          <table className="min-w-full divide-y divide-gray-100 text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs font-semibold uppercase tracking-wide">
              <tr>
                <th className="px-4 py-3 text-left">Event</th>
                <th className="px-4 py-3 text-left">Ticket</th>
                <th className="px-4 py-3 text-left">Message Preview</th>
                <th className="px-4 py-3 text-left">Language</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50 bg-white">
              {filtered.slice(0, 50).map((entry, i) => {
                const ev = EVENT_LABELS[entry.event_type] || {
                  label: entry.event_type,
                  icon: "📬",
                  color: "bg-gray-100 text-gray-600 border-gray-200",
                };
                return (
                  <motion.tr
                    key={entry.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.02 }}
                    className="hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full border ${ev.color}`}>
                        {ev.icon} {ev.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-blue-600 font-bold">
                      {entry.ticket_id.slice(-8)}
                    </td>
                    <td className="px-4 py-3 text-gray-600 max-w-[260px]">
                      <p className="line-clamp-2 text-xs leading-snug">{entry.message_sent}</p>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{entry.language}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                        entry.delivered
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-gray-100 text-gray-500"
                      }`}>
                        {entry.delivered ? "✓ Delivered" : "Not delivered"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                      {new Date(entry.timestamp).toLocaleString("en-IN", {
                        day: "numeric", month: "short",
                        hour: "2-digit", minute: "2-digit",
                      })}
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
          {filtered.length > 50 && (
            <p className="text-xs text-center py-3 text-gray-400 border-t border-gray-100">
              Showing 50 of {filtered.length} entries.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
