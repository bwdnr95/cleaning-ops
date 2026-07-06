import { Badge, Icon } from '../../../components/common/ui';

type WorkflowTone = 'brand' | 'info' | 'warn' | 'success' | 'danger' | 'purple' | 'neutral';

type OrderWorkflowGuideProps = {
  readonly workflowStatus: string;
  readonly displayStatus: string;
  readonly hasPartner: boolean;
  readonly hasSchedule: boolean;
  readonly hasUnsavedChanges: boolean;
  readonly isStatusDirty: boolean;
  readonly isPartnerDirty: boolean;
  readonly hasScheduleChanges: boolean;
  readonly isPaymentDirty: boolean;
  readonly hasCustomerVisiblePhotos: boolean;
  readonly hasSavedBalanceDue: boolean;
  readonly canSendBalanceDue: boolean;
  readonly isAsRequested: boolean;
};

type GuideContent = {
  readonly tone: WorkflowTone;
  readonly title: string;
  readonly description: string;
};

export function OrderWorkflowGuide(props: OrderWorkflowGuideProps) {
  const guide = workflowGuideContent(props);
  const blockers = workflowBlockers(props);
  const dirtyItems = dirtyLabels(props);

  return (
    <div data-testid="order-workflow-guide" className="card" style={{ padding: 14, borderColor: `var(--${guide.tone}-border, var(--border))` }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <span style={{
          width: 30,
          height: 30,
          borderRadius: 8,
          background: `var(--${guide.tone}-bg, var(--brand-bg))`,
          color: `var(--${guide.tone}-fg, var(--brand))`,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}>
          <Icon name="check" size={14}/>
        </span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <Badge tone={guide.tone}>{props.displayStatus}</Badge>
            {props.isAsRequested && <Badge tone="purple">AS 요청</Badge>}
          </div>
          <div style={{ marginTop: 8, fontSize: 13, fontWeight: 800, color: 'var(--text)' }}>{guide.title}</div>
          <div style={{ marginTop: 4, fontSize: 11.5, lineHeight: 1.5, color: 'var(--text-tertiary)' }}>{guide.description}</div>
        </div>
      </div>

      {dirtyItems.length > 0 && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--divider)', display: 'grid', gap: 5 }}>
          <div style={{ fontSize: 10.5, fontWeight: 800, color: 'var(--warn-fg)' }}>저장 필요</div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {dirtyItems.map((item) => <Badge key={item} tone="warn">{item}</Badge>)}
          </div>
        </div>
      )}

      {blockers.length > 0 && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--divider)', display: 'grid', gap: 6 }}>
          {blockers.map((blocker) => (
            <div key={blocker} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, color: 'var(--text-secondary)', fontSize: 11.5, lineHeight: 1.45 }}>
              <Icon name="chevronRight" size={12} color="var(--text-quaternary)" />
              <span>{blocker}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function workflowGuideContent(props: OrderWorkflowGuideProps): GuideContent {
  if (props.hasUnsavedChanges) {
    return {
      tone: 'warn',
      title: '먼저 변경사항을 저장하세요',
      description: '상태, 일정, 협력사, 결제 정보가 저장되어야 안내 발송과 다음 작업 판단이 정확합니다.',
    };
  }
  if (!props.hasPartner) {
    return {
      tone: 'warn',
      title: '협력사 배정이 필요합니다',
      description: '협력사를 지정한 뒤 배정 안내를 보내야 협력사가 작업 일정을 확인할 수 있습니다.',
    };
  }
  if (props.isAsRequested) {
    return {
      tone: 'purple',
      title: 'AS 확인이 진행 중입니다',
      description: '협력사 재작업 완료와 고객 재서명 이후 작업완료 및 잔금 안내 흐름으로 돌아갑니다.',
    };
  }
  if (hasCompletionPaymentConflict(props)) {
    return {
      tone: props.canSendBalanceDue ? 'warn' : 'neutral',
      title: props.canSendBalanceDue ? '최종 결제 확인이 필요합니다' : '완료 상태와 결제 상태를 확인하세요',
      description: props.canSendBalanceDue
        ? '상태는 최종 단계지만 미수 잔금이 남아 있어 고객 잔금 안내 발송 대상입니다.'
        : '서비스완료 상태와 결제 상태가 맞지 않습니다. 결제 정보를 먼저 확인하세요.',
    };
  }
  if (props.workflowStatus === '협력사확인중') {
    return {
      tone: 'info',
      title: '협력사 작업 일정 확인 대기',
      description: '협력사가 알림톡 링크에서 작업 일정 확인을 누르면 일정 및 작업 확정으로 넘어갑니다.',
    };
  }
  if (['일정확정', '전날안내필요', '전날안내완료', '작업예정'].includes(props.workflowStatus)) {
    return {
      tone: 'brand',
      title: '작업 전 안내를 관리하세요',
      description: '작업 전날 고객 안내와 현장 일정 확인이 누락되지 않는지 확인하는 단계입니다.',
    };
  }
  if (props.workflowStatus === '작업진행') {
    return {
      tone: 'info',
      title: '현장 작업 증빙 대기',
      description: '협력사가 비포/애프터 사진과 고객 서명을 완료하면 작업완료 상태로 전환됩니다.',
    };
  }
  if (props.workflowStatus === '고객전달필요') {
    return {
      tone: props.hasCustomerVisiblePhotos ? 'success' : 'warn',
      title: props.hasCustomerVisiblePhotos ? '고객 사진 링크를 발송하세요' : '고객 공개 사진을 먼저 확인하세요',
      description: props.hasCustomerVisiblePhotos
        ? '고객에게 공개된 사진이 있으므로 사진 링크 발송이 가능합니다.'
        : '사진 링크 발송 전 고객에게 공개된 사진이 1장 이상 필요합니다.',
    };
  }
  if (props.workflowStatus === '고객전달완료') {
    return {
      tone: props.hasSavedBalanceDue ? 'warn' : 'success',
      title: props.hasSavedBalanceDue ? '잔금 안내와 완납 확인이 필요합니다' : '최종 결제 상태를 확인하세요',
      description: props.hasSavedBalanceDue
        ? '미수 잔금이 남아 있어 고객 잔금 안내 발송 대상입니다.'
        : '완납 또는 잔금 없음 상태입니다. 최종결제완료 처리 여부를 확인하세요.',
    };
  }
  if (props.workflowStatus === '서비스완료') {
    return {
      tone: 'success',
      title: '서비스 완료 상태입니다',
      description: '고객 전달과 결제 확인이 끝난 주문입니다. 추가 요청은 AS 요청 처리로 관리하세요.',
    };
  }
  if (props.workflowStatus === '취소') {
    return {
      tone: 'danger',
      title: '취소된 주문입니다',
      description: '운영 기록은 보존되며, 안내 발송 전 취소 사유와 고객/협력사 커뮤니케이션을 확인하세요.',
    };
  }
  return {
    tone: 'neutral',
    title: '주문 정보를 확인하세요',
    description: '상태와 배정, 일정, 결제 조건을 확인한 뒤 다음 안내를 진행하세요.',
  };
}

function workflowBlockers(props: OrderWorkflowGuideProps): readonly string[] {
  const blockers: string[] = [];
  if (!props.hasPartner) blockers.push('협력사 배정 후 협력사 안내와 AS 요청을 보낼 수 있습니다.');
  if (!props.hasSchedule) blockers.push('방문 예정일이 없으면 전날 안내와 작업 진행 판단이 불안정합니다.');
  if (props.workflowStatus === '고객전달필요' && !props.hasCustomerVisiblePhotos) {
    blockers.push('고객에게 공개된 사진이 없어 사진 링크 발송이 잠겨 있습니다.');
  }
  if (
    props.workflowStatus === '고객전달완료'
    && !props.hasSavedBalanceDue
    && !props.hasUnsavedChanges
    && !props.isPaymentDirty
  ) {
    blockers.push('미수 잔금이 없으면 잔금 안내는 생략하고 최종결제완료만 확인하면 됩니다.');
  }
  if (hasCompletionPaymentConflict(props)) {
    blockers.push('결제 상태가 완납이 아니면 서비스완료 안내로 보지 않습니다.');
  }
  return blockers;
}

function hasCompletionPaymentConflict(props: OrderWorkflowGuideProps): boolean {
  return props.workflowStatus === '서비스완료' && props.displayStatus !== '서비스완료';
}

function dirtyLabels(props: OrderWorkflowGuideProps): readonly string[] {
  const labels: string[] = [];
  if (props.isStatusDirty) labels.push('상태');
  if (props.isPartnerDirty) labels.push('협력사');
  if (props.hasScheduleChanges) labels.push('일정');
  if (props.isPaymentDirty) labels.push('결제/정산');
  return labels;
}
