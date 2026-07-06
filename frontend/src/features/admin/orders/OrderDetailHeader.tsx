import { Icon, StatusBadge } from '../../../components/common/ui';
import { formatService } from './OrderDetailFormat';
import type { AdminOrderDetail } from './OrderDetailModel';

interface OrderDetailHeaderProps {
  readonly order: AdminOrderDetail;
  readonly displayStatus: string;
  readonly hasUnsavedChanges: boolean;
  readonly isDeleting: boolean;
  readonly onBack: () => void;
  readonly onEdit: () => void;
  readonly onDuplicate?: () => void;
  readonly onRefresh: () => void;
  readonly onDelete: () => void;
  readonly onOpenCalendar: () => void;
  readonly onOpenRecurringContract?: (contractId: string) => void;
  readonly isCompact?: boolean;
}

export function OrderDetailHeader({
  order,
  displayStatus,
  hasUnsavedChanges,
  isDeleting,
  onBack,
  onEdit,
  onDuplicate,
  onRefresh,
  onDelete,
  onOpenCalendar,
  onOpenRecurringContract,
  isCompact = false,
}: OrderDetailHeaderProps) {
  return (
    <div style={{
      padding: isCompact ? '10px 12px' : '10px 20px',
      background: 'var(--surface)',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      flexWrap: isCompact ? 'wrap' : 'nowrap',
      gap: 10,
    }}>
      <button className="btn btn--ghost btn--sm" onClick={onBack} style={{ padding: '0 6px' }}>
        <Icon name="chevronLeft" size={13}/> 목록
      </button>
      <span style={{ width: 1, height: 16, background: 'var(--border)' }}/>
      <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600, flex: isCompact ? '1 1 180px' : '0 1 auto', minWidth: 0 }}>{formatService(order)}</h2>
      <StatusBadge status={displayStatus}/>
      {order.recurring_contract_id && (
        onOpenRecurringContract ? (
          <button
            type="button"
            data-testid="order-recurring-badge"
            title="정기청소 계약 보기"
            onClick={() => onOpenRecurringContract(order.recurring_contract_id || '')}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 4, cursor: 'pointer',
              fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 10,
              border: 'none', background: 'var(--brand-bg)', color: 'var(--brand)',
            }}
          >
            <Icon name="refresh" size={11}/> 정기 계약 보기
          </button>
        ) : (
          <span
            data-testid="order-recurring-badge"
            title="정기청소 계약에서 생성된 주문"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 10,
              background: 'var(--brand-bg)', color: 'var(--brand)',
            }}
          >
            <Icon name="refresh" size={11}/> 정기
          </span>
        )
      )}
      {hasUnsavedChanges && (
        <span data-testid="detail-unsaved-indicator" style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          fontSize: 11, fontWeight: 600, color: 'var(--warn-fg)',
          background: 'var(--warn-bg)', borderRadius: 5, padding: '2px 8px',
        }}>
          <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--warn-fg)' }}/>
          저장 안 한 변경
        </span>
      )}
      <div style={{ flex: isCompact ? '1 0 100%' : 1 }}/>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: isCompact ? 'flex-start' : 'flex-end', gap: 8, flexWrap: isCompact ? 'wrap' : 'nowrap', width: isCompact ? '100%' : 'auto' }}>
        <button className="btn btn--ghost btn--sm" onClick={onRefresh}>
          <Icon name="refresh" size={12}/> 새로고침
        </button>
        <button data-testid="order-detail-edit" className="btn btn--secondary btn--sm" onClick={onEdit}>
          수정
        </button>
        {onDuplicate && (
          <button data-testid="order-detail-duplicate" className="btn btn--ghost btn--sm" onClick={onDuplicate}>
            <Icon name="copy" size={12}/> 복제
          </button>
        )}
        <button className="btn btn--ghost btn--sm" onClick={onOpenCalendar}>
          <Icon name="calendar" size={12}/> 일정표
        </button>
        <button
          data-testid="order-detail-delete"
          className="btn btn--ghost btn--sm"
          style={{ color: 'var(--danger-fg)' }}
          onClick={onDelete}
          disabled={isDeleting}
        >
          <Icon name="x" size={12}/> {isDeleting ? '삭제 중' : '삭제'}
        </button>
      </div>
    </div>
  );
}
