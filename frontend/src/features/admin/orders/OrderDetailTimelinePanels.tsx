import { StatusBadge } from '../../../components/common/ui';
import { orderWorkflowStatusValue } from '../../../domain/orderStatus';
import { formatDateTime, formatWon, timelineEventLabel } from './OrderDetailFormat';
import type { OrderDetailSiblingLine, OrderDetailTimelineEvent } from './OrderDetailModel';
import { EmptyLine, PanelTitle } from './OrderDetailPrimitives';

export function SiblingLinesPanel({
  siblings,
  onOpenOrder,
}: {
  readonly siblings: readonly OrderDetailSiblingLine[];
  readonly onOpenOrder?: (orderId: string) => void;
}) {
  return (
    <div className="card" style={{ padding: 14 }}>
      <PanelTitle>이 그룹의 다른 라인</PanelTitle>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {siblings.map((sibling) => (
          <button
            key={sibling.id}
            type="button"
            data-testid={`order-sibling-${sibling.id}`}
            onClick={() => onOpenOrder?.(sibling.id)}
            style={{
              display: 'block',
              width: '100%',
              border: '1px solid var(--divider)',
              borderRadius: 6,
              background: 'var(--surface)',
              padding: 8,
              textAlign: 'left',
              cursor: 'pointer',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12.5, fontWeight: 600 }}>
                {sibling.service_name}
              </span>
              <StatusBadge status={orderWorkflowStatusValue(sibling.status, sibling.payment_status)} dot={false}/>
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {sibling.team_name || '미배정'} · {formatWon(sibling.total_amount)}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

export function TimelinePanel({ timeline }: { readonly timeline: readonly OrderDetailTimelineEvent[] }) {
  return (
    <div className="card" style={{ padding: 14 }}>
      <PanelTitle>타임라인</PanelTitle>
      {timeline.length === 0 ? (
        <EmptyLine text="타임라인 기록이 없습니다." />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {timeline.map((event, index) => (
            <div key={event.id} style={{ display: 'flex', gap: 10, paddingBottom: index === timeline.length - 1 ? 0 : 12 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: index === timeline.length - 1 ? 'var(--brand)' : 'var(--border-strong)', marginTop: 4, flexShrink: 0 }}/>
              <div style={{ flex: 1, fontSize: 11.5 }}>
                <div style={{ color: 'var(--text-tertiary)', fontSize: 10.5, marginBottom: 1 }}>{formatDateTime(event.created_at)}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
                  <span style={{ color: 'var(--text)', fontWeight: 500 }}>{event.title}</span>
                  {event.event_metadata?.author_role === 'partner' && (
                    <span style={{ fontSize: 9.5, fontWeight: 700, color: 'var(--brand)', background: 'var(--brand-bg)', padding: '0 5px', borderRadius: 8 }}>협력사</span>
                  )}
                </div>
                <div style={{ color: 'var(--text-tertiary)', marginTop: 1 }}>{timelineEventLabel(event.event_type)}</div>
                {event.description && (
                  <div className="multiline-text" style={{ marginTop: 3, color: 'var(--text-secondary)', fontSize: 11.5, lineHeight: 1.45, whiteSpace: 'pre-wrap' }}>
                    {event.description}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
