export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: string;
  permissions: string[];
  department_id?: string;
  location_id?: string;
  preferences: {
    notifications_enabled?: boolean;
    theme?: 'light' | 'dark';
    [key: string]: any;
  };
}

export interface Ticket {
  id: string;
  title: string;
  description: string;
  status: 'OPEN' | 'IN_PROGRESS' | 'PENDING' | 'RESOLVED' | 'CLOSED' | 'CANCELLED';
  priority: 'LOW' | 'MEDIUM' | 'HIGH';
  category?: string;
  reporter_id: string;
  reporter_name?: string;
  assignee_id?: string;
  assignee_name?: string;
  sla_deadline?: string;
  is_sla_breached: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface Device {
  id: string;
  hostname: string;
  serial_number: string;
  status: string;
  device_type: string;
  last_seen?: string;
  version: number;
}

export interface InventoryResponse {
  device_id: string;
  status: string;
  processed_at: string;
  version: number;
  agent_token?: string;
}
