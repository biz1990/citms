import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Html5QrcodeScanner } from 'html5-qrcode';
import { 
  Card, CardContent, CardHeader, CardTitle, CardDescription 
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  Scan, 
  Wifi, 
  WifiOff, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle,
  History,
  Search,
  Database,
  ArrowRight,
  ShieldAlert,
  Check,
  X
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';
import { initDB, saveOfflineDevices, getOfflineDevices, OfflineDevice } from '@/lib/db';
import { format } from 'date-fns';
import { toast } from 'sonner';

interface Conflict {
  device_id: string;
  local_data: any;
  server_data: any;
}

const PhysicalInventoryPage: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [isScanning, setIsScanning] = useState(false);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [scannedResult, setScannedResult] = useState<string | null>(null);
  const [offlineData, setOfflineData] = useState<OfflineDevice[]>([]);
  const [pendingSync, setPendingSync] = useState<any[]>([]);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const scannerRef = useRef<Html5QrcodeScanner | null>(null);

  // Sync Status
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Load Offline Data
  const loadOffline = async () => {
    const data = await getOfflineDevices();
    setOfflineData(data);
    
    const db = await initDB();
    const pending = await db.getAll('pending_sync');
    setPendingSync(pending);
  };

  useEffect(() => {
    loadOffline();
  }, []);

  // Fetch Online Devices (to sync)
  const { data: onlineDevices, isLoading } = useQuery({
    queryKey: ['devices-sync'],
    queryFn: async () => {
      const response = await apiClient.get('/devices');
      await saveOfflineDevices(response.data);
      return response.data;
    },
    enabled: isOnline,
  });

  // Start/Stop Scanner
  useEffect(() => {
    if (isScanning) {
      scannerRef.current = new Html5QrcodeScanner(
        "qr-reader", 
        { fps: 10, qrbox: { width: 250, height: 250 } },
        /* verbose= */ false
      );
      scannerRef.current.render(onScanSuccess, onScanFailure);
    } else {
      scannerRef.current?.clear();
    }
    return () => {
      scannerRef.current?.clear();
    };
  }, [isScanning]);

  const onScanSuccess = (decodedText: string) => {
    setScannedResult(decodedText);
    setIsScanning(false);
    handleInventoryCheck(decodedText);
  };

  const onScanFailure = (error: any) => {
    // console.warn(`Code scan error = ${error}`);
  };

  const handleInventoryCheck = async (deviceId: string) => {
    const checkInData = {
      device_id: deviceId,
      checked_at: new Date().toISOString(),
      location: 'Warehouse A',
      status: 'VERIFIED'
    };

    if (isOnline) {
      try {
        await apiClient.post(`/devices/${deviceId}/check-in`, checkInData);
        queryClient.invalidateQueries({ queryKey: ['devices-sync'] });
        toast.success(`Device ${deviceId} verified online`);
      } catch (error) {
        console.error('Failed to sync check-in', error);
        toast.error('Failed to sync check-in');
      }
    } else {
      const db = await initDB();
      await db.add('pending_sync', {
        ...checkInData,
        status: 'VERIFIED_OFFLINE'
      });
      loadOffline();
      toast.info(`Device ${deviceId} saved for offline sync`);
    }
  };

  const syncData = async () => {
    if (!isOnline || pendingSync.length === 0) return;
    
    const db = await initDB();
    const newConflicts: Conflict[] = [];
    
    for (const item of pendingSync) {
      try {
        // Check for conflict: Get current server state
        const serverRes = await apiClient.get(`/devices/${item.device_id}`);
        const serverData = serverRes.data;
        
        // If server was updated AFTER our offline scan, it's a conflict
        if (serverData.last_seen && new Date(serverData.last_seen) > new Date(item.checked_at)) {
          newConflicts.push({
            device_id: item.device_id,
            local_data: item,
            server_data: serverData
          });
          continue;
        }

        // No conflict, proceed with sync
        await apiClient.post(`/devices/${item.device_id}/check-in`, item);
        await db.delete('pending_sync', item.id);
      } catch (error) {
        console.error(`Failed to sync ${item.device_id}`, error);
      }
    }

    setConflicts(newConflicts);
    loadOffline();
    
    if (newConflicts.length > 0) {
      toast.warning(`${newConflicts.length} conflicts detected during sync`);
    } else {
      toast.success('All items synced successfully');
    }
  };

  const resolveConflict = async (deviceId: string, choice: 'local' | 'server') => {
    const db = await initDB();
    const conflict = conflicts.find(c => c.device_id === deviceId);
    if (!conflict) return;

    if (choice === 'local') {
      // Force overwrite server with local data
      await apiClient.post(`/devices/${deviceId}/check-in`, conflict.local_data);
    }
    
    // Remove from pending sync and conflicts
    const pendingItem = pendingSync.find(p => p.device_id === deviceId);
    if (pendingItem) await db.delete('pending_sync', pendingItem.id);
    
    setConflicts(prev => prev.filter(c => c.device_id !== deviceId));
    loadOffline();
    toast.success(`Conflict resolved using ${choice} data`);
  };

  return (
    <div className="container mx-auto p-6 space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            {t('inventory.physical.title')}
            {isOnline ? (
              <Badge className="bg-green-600 hover:bg-green-700 flex items-center gap-1">
                <Wifi className="h-3 w-3" /> {t('common.status.online')}
              </Badge>
            ) : (
              <Badge variant="destructive" className="flex items-center gap-1">
                <WifiOff className="h-3 w-3" /> {t('common.status.offline')}
              </Badge>
            )}
          </h1>
          <p className="text-muted-foreground">{t('inventory.physical.description')}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={syncData} disabled={!isOnline || pendingSync.length === 0}>
            <RefreshCw className="h-4 w-4 mr-2" /> Sync Data ({pendingSync.length})
          </Button>
          <Button onClick={() => setIsScanning(!isScanning)}>
            <Scan className="h-4 w-4 mr-2" /> {isScanning ? 'Stop Scanning' : 'Start Scanning'}
          </Button>
        </div>
      </div>

      {/* Conflict Resolution UI */}
      {conflicts.length > 0 && (
        <div className="space-y-4 animate-in slide-in-from-top-4">
          <div className="flex items-center gap-2 text-orange-500 font-bold">
            <ShieldAlert className="h-5 w-5" />
            <h2>Sync Conflicts Detected</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {conflicts.map(conflict => (
              <Card key={conflict.device_id} className="border-orange-500/50 bg-orange-500/5">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Conflict for Device: {conflict.device_id}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div className="p-3 border rounded-lg bg-background">
                      <p className="font-bold mb-1">Local (Offline Scan)</p>
                      <p className="text-muted-foreground">Checked: {format(new Date(conflict.local_data.checked_at), 'HH:mm:ss')}</p>
                      <p className="text-muted-foreground">Status: {conflict.local_data.status}</p>
                    </div>
                    <div className="p-3 border rounded-lg bg-background">
                      <p className="font-bold mb-1">Server (Latest)</p>
                      <p className="text-muted-foreground">Last Seen: {format(new Date(conflict.server_data.last_seen), 'HH:mm:ss')}</p>
                      <p className="text-muted-foreground">Status: {conflict.server_data.status}</p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" className="flex-1" onClick={() => resolveConflict(conflict.device_id, 'local')}>
                      <Check className="h-3 w-3 mr-1" /> Use Local
                    </Button>
                    <Button size="sm" variant="outline" className="flex-1" onClick={() => resolveConflict(conflict.device_id, 'server')}>
                      <X className="h-3 w-3 mr-1" /> Use Server
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Scanner UI */}
      {isScanning && (
        <Card className="max-w-md mx-auto overflow-hidden border-2 border-primary/50 shadow-2xl">
          <CardHeader className="bg-primary/10">
            <CardTitle className="text-center text-sm">Align QR/Barcode within the frame</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div id="qr-reader" className="w-full" />
          </CardContent>
        </Card>
      )}

      {/* Offline Data View */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5 text-primary" />
              Offline Asset Cache
            </CardTitle>
            <CardDescription>Cached data for offline verification</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr className="text-left">
                    <th className="p-3 font-medium">Hostname</th>
                    <th className="p-3 font-medium">Serial</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">Last Sync</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {offlineData.map((device) => (
                    <tr key={device.id} className="hover:bg-muted/30 transition-colors">
                      <td className="p-3 font-medium">{device.hostname}</td>
                      <td className="p-3 font-mono text-xs">{device.serial_number}</td>
                      <td className="p-3">
                        <Badge variant={device.status === 'ONLINE' ? 'default' : 'secondary'}>
                          {device.status}
                        </Badge>
                      </td>
                      <td className="p-3 text-xs text-muted-foreground">
                        {format(device.synced_at, 'HH:mm:ss')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Sync Queue */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <History className="h-5 w-5 text-primary" />
              Pending Sync
            </CardTitle>
            <CardDescription>Scans performed while offline</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {pendingSync.map((item, i) => (
              <div key={i} className="flex items-center justify-between p-3 border rounded-lg bg-muted/20">
                <div className="flex items-center gap-3">
                  <Scan className="h-4 w-4 text-primary" />
                  <div>
                    <p className="text-xs font-bold">{item.device_id}</p>
                    <p className="text-[10px] text-muted-foreground">{format(new Date(item.checked_at), 'HH:mm:ss')}</p>
                  </div>
                </div>
                <Badge variant="outline" className="text-[10px]">PENDING</Badge>
              </div>
            ))}
            {pendingSync.length === 0 && (
              <div className="text-center py-8 text-muted-foreground italic border-2 border-dashed rounded-lg">
                <RefreshCw className="h-8 w-8 mx-auto mb-2 opacity-20" />
                <p className="text-xs">No pending sync items.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default PhysicalInventoryPage;
