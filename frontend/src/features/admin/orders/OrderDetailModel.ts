import type { AdminOrder } from '../../../api/admin';
import type { AdminMessageChannel, AdminMessageRecipient, AdminMessageType } from '../../../api/messages';

export interface AdminPartnerOption {
  readonly id: string;
  readonly name: string;
}

export interface OrderDetailPhoto {
  readonly id: string;
  readonly file_url: string;
  readonly file_name?: string | null;
  readonly photo_type: string;
  readonly photo_source?: string | null;
  readonly is_customer_visible: boolean;
}

export interface OrderDetailMessageLog {
  readonly id: string;
  readonly message_type: string;
  readonly recipient_name?: string | null;
  readonly provider?: string | null;
  readonly provider_group_id?: string | null;
  readonly provider_message_id?: string | null;
  readonly provider_error_code?: string | null;
  readonly provider_status_message?: string | null;
  readonly error_message?: string | null;
  readonly status?: string | null;
  readonly sent_at?: string | null;
  readonly created_at?: string | null;
}

export interface OrderDetailTimelineEvent {
  readonly id: string;
  readonly event_type: string;
  readonly title: string;
  readonly description?: string | null;
  readonly created_at?: string | null;
  readonly event_metadata?: {
    readonly author_role?: string | null;
  } | null;
}

export interface OrderDetailSiblingLine {
  readonly id: string;
  readonly service_name?: string | null;
  readonly status?: string | null;
  readonly payment_status?: string | null;
  readonly team_name?: string | null;
  readonly total_amount?: number | null;
}

export interface AdminOrderDetail extends AdminOrder {
  readonly source_channel?: string | null;
  readonly photos?: readonly OrderDetailPhoto[];
  readonly message_logs?: readonly OrderDetailMessageLog[];
  readonly timeline?: readonly OrderDetailTimelineEvent[];
  readonly sibling_lines?: readonly OrderDetailSiblingLine[];
}

export interface MessageActionDraft {
  readonly messageType: AdminMessageType;
  readonly recipientType: AdminMessageRecipient;
  readonly title: string;
  readonly successText: string;
  readonly initialChannel?: AdminMessageChannel;
}

export interface MessagePreviewData {
  readonly recipient_name?: string | null;
  readonly recipient_phone?: string | null;
  readonly warnings?: readonly string[];
  readonly kakao_variables?: Record<string, string | number | boolean | null>;
  readonly kakao_channel_id_configured?: boolean;
  readonly kakao_template_configured?: boolean;
  readonly fallback_sms_enabled?: boolean;
  readonly kakao_template_id?: string | null;
  readonly fallback_sms_content?: string | null;
  readonly content?: string | null;
  readonly can_send?: boolean;
}
