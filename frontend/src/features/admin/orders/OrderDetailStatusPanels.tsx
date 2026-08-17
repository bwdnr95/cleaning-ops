import { MultiDatePicker } from '../../../components/common/MultiDatePicker';
import { Icon } from '../../../components/common/ui';
import { ORDER_STATUS_OPTIONS } from '../../../domain/orderStatus';
import type { AdminPartnerOption } from './OrderDetailModel';
import { PanelTitle } from './OrderDetailPrimitives';

export function StatusChangePanel({
  selectedStatus,
  isSaving,
  isStatusDirty,
  onSelectedStatusChange,
  onStatusSave,
}: {
  readonly selectedStatus: string;
  readonly isSaving: boolean;
  readonly isStatusDirty: boolean;
  readonly onSelectedStatusChange: (value: string) => void;
  readonly onStatusSave: () => void;
}) {
  return (
    <div className="card" style={{ padding: 14 }}>
      <PanelTitle dirty={isStatusDirty}>상태 변경</PanelTitle>
      <select data-testid="detail-status-select" className="input" value={selectedStatus} onChange={(event) => onSelectedStatusChange(event.target.value)} style={{ width: '100%', height: 34, marginBottom: 8 }}>
        {ORDER_STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <button data-testid="detail-status-save" className={`btn btn--block ${isStatusDirty ? 'btn--primary' : 'btn--secondary'}`} disabled={isSaving || !isStatusDirty} onClick={onStatusSave}>
        <Icon name="check" size={13}/> 상태 저장
      </button>
    </div>
  );
}

export function PartnerAssignPanel({
  partners,
  selectedPartnerId,
  isSaving,
  isPartnerDirty,
  onSelectedPartnerIdChange,
  onPartnerSave,
}: {
  readonly partners: readonly AdminPartnerOption[];
  readonly selectedPartnerId: string;
  readonly isSaving: boolean;
  readonly isPartnerDirty: boolean;
  readonly onSelectedPartnerIdChange: (value: string) => void;
  readonly onPartnerSave: () => void;
}) {
  return (
    <div className="card" style={{ padding: 14 }}>
      <PanelTitle dirty={isPartnerDirty}>협력사 배정</PanelTitle>
      <select className="input" value={selectedPartnerId} onChange={(event) => onSelectedPartnerIdChange(event.target.value)} style={{ width: '100%', height: 34, marginBottom: 8 }}>
        <option value="">미배정</option>
        {partners.map((partner) => (
          <option key={partner.id} value={partner.id}>{partner.name}</option>
        ))}
      </select>
      <button className={`btn btn--block ${isPartnerDirty ? 'btn--primary' : 'btn--secondary'}`} disabled={isSaving || !isPartnerDirty} onClick={onPartnerSave}>
        <Icon name="user" size={13}/> 배정 저장
      </button>
    </div>
  );
}

export function SchedulePanel({
  selectedVisitDates,
  selectedRequestedTime,
  isSaving,
  hasScheduleChanges,
  onSelectedVisitDatesChange,
  onSelectedRequestedTimeChange,
  onScheduleSave,
}: {
  readonly selectedVisitDates: readonly string[];
  readonly selectedRequestedTime: string;
  readonly isSaving: boolean;
  readonly hasScheduleChanges: boolean;
  readonly onSelectedVisitDatesChange: (value: string[]) => void;
  readonly onSelectedRequestedTimeChange: (value: string) => void;
  readonly onScheduleSave: () => void;
}) {
  return (
    <div className="card" style={{ padding: 14 }}>
      <PanelTitle dirty={hasScheduleChanges}>방문 일정</PanelTitle>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 8 }}>
        <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>방문 예정일</span>
        <MultiDatePicker
          testId="detail-visit-dates"
          value={selectedVisitDates}
          onChange={onSelectedVisitDatesChange}
        />
      </label>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 8 }}>
        <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>요청 시간</span>
        <input
          data-testid="detail-requested-time"
          className="input"
          value={selectedRequestedTime}
          onChange={(event) => onSelectedRequestedTimeChange(event.target.value)}
          placeholder="14:00 또는 오후 2-5시"
          style={{ width: '100%', height: 34 }}
        />
      </label>
      <button
        data-testid="detail-schedule-save"
        className={`btn btn--block ${hasScheduleChanges ? 'btn--primary' : 'btn--secondary'}`}
        disabled={isSaving || !hasScheduleChanges}
        onClick={onScheduleSave}
      >
        <Icon name="calendar" size={13}/> 일정 저장
      </button>
    </div>
  );
}
