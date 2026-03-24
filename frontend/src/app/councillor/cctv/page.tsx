"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";
import AlertCard from "@/components/cctv/AlertCard";
import CameraMap from "@/components/cctv/CameraMap";
import VerificationModal from "@/components/cctv/VerificationModal";
import UploadAnalyzeModal from "@/components/cctv/UploadAnalyzeModal";

export default function CouncillorCCTVPage() {
    const { user, isCouncillor } = useAuth();
    const router = useRouter();

    const [alerts, setAlerts] = useState<any[]>([]);
    const [cameras, setCameras] = useState<any[]>([]);
    const [counts, setCounts] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    
    // UI states
    const [filterStatus, setFilterStatus] = useState<string>('pending_verification');
    const [filterCamera, setFilterCamera] = useState<string>('');
    const [isMapOpen, setIsMapOpen] = useState(false);
    const [isUploadOpen, setIsUploadOpen] = useState(false);
    
    const [selectedAlert, setSelectedAlert] = useState<any>(null);
    const [isVerifyModalOpen, setIsVerifyModalOpen] = useState(false);

    const loadData = useCallback(async () => {
        if (!user?.ward_id) return;
        try {
            const [alertsRes, camerasRes, countsRes] = await Promise.all([
                fetch(`http://localhost:8000/api/cctv/alerts?ward_id=${user.ward_id}&limit=50`),
                fetch(`http://localhost:8000/api/cctv/cameras?ward_id=${user.ward_id}`),
                fetch(`http://localhost:8000/api/cctv/alerts/counts?ward_id=${user.ward_id}`)
            ]);

            const alertsData = await alertsRes.json();
            const camerasData = await camerasRes.json();
            const countsData = await countsRes.json();

            setAlerts(alertsData);
            setCameras(camerasData);
            setCounts(countsData);
        } catch (err) {
            toast.error("Failed to load CCTV data");
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [user]);

    useEffect(() => {
        if (!user) return;
        if (!isCouncillor) {
            router.push("/officer/dashboard");
            return;
        }
        loadData();
    }, [user, isCouncillor, router, loadData]);

    const handleVerify = async (action: string, data: any) => {
        if (!selectedAlert) return false;
        try {
            const res = await fetch(`http://localhost:8000/api/cctv/alerts/${selectedAlert.alert_id}/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...data, ward_id: user?.ward_id })
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail?.message || err.detail || 'Verification failed');
            }
            await loadData();
            return true;
        } catch (error: any) {
            console.error(error);
            toast.error(error.message);
            return false;
        }
    };

    const handleMarkResolved = async (alertId: string) => {
        try {
            const res = await fetch(`http://localhost:8000/api/cctv/alerts/${alertId}/mark-resolved`, {
                method: 'POST',
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail?.message || err.detail || 'Failed to mark as resolved');
            }
            toast.success("Alert marked as resolved");
            await loadData();
        } catch (error: any) {
            console.error(error);
            toast.error(error.message);
        }
    };

    const handleUploadSuccess = (newAlert: any) => {
        toast.success("Footage analyzed successfully");
        if (newAlert.status === 'pending_verification') {
            setFilterStatus('pending_verification');
        }
        loadData();
    };

    const filteredAlerts = alerts.filter(a => {
        if (filterStatus && a.status !== filterStatus) return false;
        if (filterCamera && a.camera_id !== filterCamera) return false;
        return true;
    });

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="w-10 h-10 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 pb-12">
            <div className="bg-gradient-to-r from-gray-900 to-slate-800 text-white px-6 py-8">
                <div className="max-w-7xl mx-auto flex justify-between items-end">
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                             <span className="bg-blue-600 text-white text-xs font-bold px-2.5 py-1 rounded border border-blue-500 shadow-sm flex items-center">
                               <span className="w-1.5 h-1.5 bg-white rounded-full mr-1.5 animate-pulse"></span>
                               LIVE AI
                             </span>
                             <p className="text-gray-300 text-sm">Ward {user?.ward_id} Surveillance</p>
                        </div>
                        <h1 className="text-3xl font-bold tracking-tight">CCTV Civic Sentinel</h1>
                        <p className="text-gray-400 mt-2 max-w-2xl text-sm">Automated detection of infrastructure issues, waterlogging, and waste violations using Gemini AI vision models.</p>
                    </div>
                    <div className="flex gap-3">
                        <button 
                            onClick={() => setIsMapOpen(true)}
                            className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded-lg font-medium text-sm transition-colors border border-slate-600"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path></svg>
                            Camera Map
                        </button>
                        <button 
                            onClick={() => setIsUploadOpen(true)}
                            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded-lg font-medium text-sm transition-colors shadow-sm"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path></svg>
                            Analyze Clip
                        </button>
                    </div>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 sm:px-6 mt-6">
                
                {/* Stats Row */}
                {counts && (
                    <div className="grid grid-cols-4 gap-4 mb-8">
                        <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
                            <p className="text-xs text-gray-500 uppercase font-semibold">Pending Review</p>
                            <div className="flex items-end justify-between mt-1">
                                <p className="text-2xl font-bold text-gray-900">{counts.pending_verification}</p>
                                {counts.pending_verification > 0 && <span className="bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded font-bold animate-pulse">Action required</span>}
                            </div>
                        </div>
                        <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
                            <p className="text-xs text-gray-500 uppercase font-semibold">Flagged for Team</p>
                            <p className="text-2xl font-bold text-purple-700 mt-1">{counts.flagged_for_discussion}</p>
                        </div>
                        <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
                            <p className="text-xs text-gray-500 uppercase font-semibold">Tickets Raised (Today)</p>
                            <p className="text-2xl font-bold text-green-700 mt-1">{counts.ticket_raised_today}</p>
                        </div>
                        <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
                            <p className="text-xs text-gray-500 uppercase font-semibold">Total Detections (Week)</p>
                            <p className="text-2xl font-bold text-gray-700 mt-1">{counts.total_alerts_this_week}</p>
                        </div>
                    </div>
                )}

                {/* Filters */}
                <div className="flex items-center justify-between mb-6 bg-white p-3 rounded-lg border shadow-sm">
                    <div className="flex gap-2">
                        {['pending_verification', 'flagged_for_discussion', 'ticket_raised', 'dismissed', ''].map(s => {
                            const labels: any = {
                                'pending_verification': 'Needs Review',
                                'flagged_for_discussion': 'Flagged',
                                'ticket_raised': 'Ticketed',
                                'dismissed': 'Dismissed',
                                '': 'All'
                            };
                            return (
                                <button
                                    key={s}
                                    onClick={() => setFilterStatus(s)}
                                    className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                                        filterStatus === s 
                                            ? 'bg-blue-100 text-blue-800' 
                                            : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
                                    }`}
                                >
                                    {labels[s]}
                                    {s === 'pending_verification' && counts?.pending_verification > 0 && filterStatus !== s && (
                                        <span className="ml-1.5 bg-red-500 text-white text-[10px] px-1.5 py-0.5 rounded-full">{counts.pending_verification}</span>
                                    )}
                                </button>
                            );
                        })}
                    </div>
                    <div>
                        {filterCamera && (
                            <button 
                                onClick={() => setFilterCamera('')}
                                className="text-xs text-blue-600 hover:underline mr-4"
                            >
                                Clear camera filter (Showing {filterCamera})
                            </button>
                        )}
                        <span className="text-sm text-gray-500">{filteredAlerts.length} footage items</span>
                    </div>
                </div>

                {/* Grid */}
                {filteredAlerts.length === 0 ? (
                    <div className="text-center py-20 bg-white rounded-xl border border-dashed border-gray-300">
                        <svg className="mx-auto h-12 w-12 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
                        <h3 className="text-lg font-medium text-gray-900">No footage found</h3>
                        <p className="mt-1 text-gray-500 text-sm">No CCTV alerts match the current filters.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                        {filteredAlerts.map(alert => (
                            <AlertCard 
                                key={alert.alert_id} 
                                alert={alert} 
                                onReview={() => {
                                    setSelectedAlert(alert);
                                    setIsVerifyModalOpen(true);
                                }}
                                onMarkResolved={alert.status === 'ticket_raised' ? () => handleMarkResolved(alert.alert_id) : undefined}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* Modals and Overlays */}
            <CameraMap 
                isOpen={isMapOpen} 
                onClose={() => setIsMapOpen(false)} 
                cameras={cameras} 
                alerts={alerts}
                onSelectCamera={(id) => {
                    setFilterCamera(id);
                    setIsMapOpen(false);
                }} 
            />
            
            <UploadAnalyzeModal 
                isOpen={isUploadOpen} 
                onClose={() => setIsUploadOpen(false)} 
                cameras={cameras} 
                wardId={user?.ward_id?.toString() || ""} 
                userId={user?.id?.toString() || ""} 
                onUploadSuccess={handleUploadSuccess} 
            />
            
            <VerificationModal 
                isOpen={isVerifyModalOpen} 
                onClose={() => setIsVerifyModalOpen(false)} 
                alert={selectedAlert} 
                onVerify={handleVerify} 
            />
        </div>
    );
}
