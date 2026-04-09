import React from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/client';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, CheckCircle2, ShieldAlert } from 'lucide-react';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';

interface DeviceSoftwareTabProps {
  deviceId: string;
}

const DeviceSoftwareTab: React.FC<DeviceSoftwareTabProps> = ({ deviceId }) => {
  const { data: software, isLoading } = useQuery({
    queryKey: ['device-software', deviceId],
    queryFn: async () => {
      const response = await apiClient.get(`/devices/${deviceId}/software`);
      return response.data;
    },
  });

  if (isLoading) return <div className="p-8 text-center">Loading software inventory...</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <ShieldAlert className="h-5 w-5 text-primary" />
          Software Inventory & Compliance
        </h3>
        <div className="flex gap-4 text-sm">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-red-500/20 border border-red-500 rounded-sm" />
            <span>Violation/Blacklist</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-green-500/20 border border-green-500 rounded-sm" />
            <span>Compliant</span>
          </div>
        </div>
      </div>

      <div className="border rounded-lg overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead>Software Name</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Vendor</TableHead>
              <TableHead>Install Date</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {software?.map((item: any) => {
              const isViolation = item.is_blocked || item.license_violation;
              
              return (
                <TableRow 
                  key={item.id}
                  className={cn(
                    "transition-colors",
                    isViolation ? "bg-red-500/10 hover:bg-red-500/20" : "hover:bg-muted/50"
                  )}
                >
                  <TableCell className="font-medium">
                    <div className="flex flex-col">
                      <span>{item.name}</span>
                      {item.is_blacklisted && (
                        <span className="text-[10px] text-red-500 font-bold uppercase tracking-wider">
                          Blacklisted
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>{item.version || 'N/A'}</TableCell>
                  <TableCell>{item.vendor || 'N/A'}</TableCell>
                  <TableCell>
                    {item.installed_at ? format(new Date(item.installed_at), 'PPP') : 'N/A'}
                  </TableCell>
                  <TableCell>
                    {isViolation ? (
                      <Badge variant="destructive" className="flex w-fit items-center gap-1">
                        <AlertCircle className="h-3 w-3" /> Non-Compliant
                      </Badge>
                    ) : (
                      <Badge variant="default" className="flex w-fit items-center gap-1 bg-green-600 hover:bg-green-700">
                        <CheckCircle2 className="h-3 w-3" /> Compliant
                      </Badge>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
            {software?.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                  No software installations found for this device.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};

export default DeviceSoftwareTab;
