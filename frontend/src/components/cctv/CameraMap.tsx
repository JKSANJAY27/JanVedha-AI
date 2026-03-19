import React, { useEffect } from 'react';
import dynamic from 'next/dynamic';

const MapContainer = dynamic(() => import('react-leaflet').then(m => m.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import('react-leaflet').then(m => m.TileLayer), { ssr: false });
const CircleMarker = dynamic(() => import('react-leaflet').then(m => m.CircleMarker), { ssr: false });
const Popup = dynamic(() => import('react-leaflet').then(m => m.Popup), { ssr: false });

interface CameraMapProps {
  isOpen: boolean;
  onClose: () => void;
  cameras: any[];
  onSelectCamera: (cameraId: string) => void;
  alerts: any[];
}

export default function CameraMap({ isOpen, onClose, cameras, onSelectCamera, alerts }: CameraMapProps) {
  if (!isOpen) return null;

  const getAlertCount = (cameraId: string) => {
    return alerts.filter(a => a.camera_id === cameraId && (a.status === 'pending_verification' || a.status === 'flagged_for_discussion')).length;
  };

  const getMarkerColor = (status: string) => {
    switch (status) {
      case 'active': return '#10B981'; // green-500
      case 'inactive': return '#9CA3AF'; // gray-400
      case 'maintenance': return '#F59E0B'; // amber-500
      default: return '#10B981';
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full md:w-[400px] bg-white shadow-2xl z-50 flex flex-col transform transition-transform border-l border-gray-200">
      <div className="px-4 py-3 flex justify-between items-center border-b">
        <div>
          <h2 className="text-base font-semibold">Ward Cameras</h2>
          <p className="text-xs text-gray-500">{cameras.length} cameras registered</p>
        </div>
        <button onClick={onClose} className="p-1 rounded-full hover:bg-gray-100 text-gray-500">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
        </button>
      </div>

      <div className="h-[400px] w-full bg-gray-100 relative">
        {(typeof window !== 'undefined') && (
          <MapContainer center={[12.9716, 80.2443]} zoom={14} className="h-full w-full" zoomControl={false}>
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; OpenStreetMap'
            />
            {cameras.map(cam => (
              <CircleMarker
                key={cam.camera_id}
                center={[cam.lat, cam.lng]}
                radius={8}
                pathOptions={{
                  color: 'white',
                  weight: 2,
                  fillColor: getMarkerColor(cam.status),
                  fillOpacity: 1
                }}
              >
                <Popup className="min-w-[200px]">
                  <div className="p-1">
                    <p className="font-bold text-sm">{cam.camera_id}</p>
                    <p className="text-xs text-gray-600 my-1">{cam.location_description}</p>
                    <div className="flex items-center space-x-2 my-2">
                       <span className={`text-[10px] px-2 py-0.5 rounded text-white ${cam.status === 'active' ? 'bg-green-500' : 'bg-gray-500'}`}>
                         {cam.status.toUpperCase()}
                       </span>
                    </div>
                    {getAlertCount(cam.camera_id) > 0 && (
                      <p className="text-xs font-medium text-amber-600 mb-2">Pending alerts: {getAlertCount(cam.camera_id)}</p>
                    )}
                    <button 
                      onClick={() => onSelectCamera(cam.camera_id)}
                      className="text-xs text-blue-600 font-medium hover:underline w-full text-left"
                    >
                      Filter alerts by this camera &rarr;
                    </button>
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Camera List</h3>
        <div className="space-y-2">
          {cameras.map(cam => (
            <div key={cam.camera_id} className="bg-white border rounded p-3 text-sm flex justify-between items-center hover:shadow-sm cursor-pointer" onClick={() => onSelectCamera(cam.camera_id)}>
               <div className="flex-1">
                 <div className="flex items-center">
                   <span className="font-semibold text-gray-800 mr-2">{cam.camera_id}</span>
                   {cam.status !== 'active' && <span className="text-[10px] bg-gray-200 text-gray-700 px-1.5 py-0.5 rounded">{cam.status}</span>}
                 </div>
                 <p className="text-xs text-gray-500 mt-0.5 max-w-[220px] truncate">{cam.location_description}</p>
               </div>
               {getAlertCount(cam.camera_id) > 0 && (
                 <div className="bg-red-100 text-red-800 text-xs font-bold px-2 py-1 rounded-full">
                   {getAlertCount(cam.camera_id)}
                 </div>
               )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
