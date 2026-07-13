import { apiRequest } from './client';

export interface AdminNotification {
  readonly id: string;
  readonly order_id: string;
  readonly event_type: string;
  readonly title: string;
  readonly description?: string | null;
  readonly created_at?: string | null;
  readonly service_name: string;
  readonly customer_name: string;
  readonly actor_label: string;
}

export function listAdminNotifications(): Promise<AdminNotification[]> {
  return apiRequest('/admin/notifications') as Promise<AdminNotification[]>;
}
