import React from 'react';

import {
  createAdminBroker,
  deleteAdminBroker,
  getAdminBroker,
  listAdminBrokers,
  listBrokerSettlements,
  revertBrokerOrders,
  settleBrokerOrders,
  updateAdminBroker,
  type BrokerSettlementItem,
  type BrokerSettlementListResponse,
} from '../../../api/admin';
import { useApiResource } from '../../../api/useApiResource';
import { Icon } from '../../../components/common/ui';
import { formatPhone } from '../../../domain/phone';

type SettlementFilter = 'unpaid' | 'paid' | 'all';

const won = (value) => `${Math.round(Number(value) || 0).toLocaleString('ko-KR')}원`;

function emptyToNull(value) {
  const trimmed = String(value ?? '').trim();
  return trimmed === '' ? null : trimmed;
}

function brokerErrorMessage(err) {
  const detail = String(err?.detail || err?.message || '');
  if (detail.includes('broker_in_use')) {
    return '이 중개사로 등록된 주문이 있어 삭제할 수 없습니다. 비활성으로 변경하세요.';
  }
  if (detail.includes('broker_inactive')) {
    return '비활성 중개사입니다. 활성화 후 정산할 수 있습니다.';
  }
  if (detail.includes('settlement_order_broker_mismatch')) {
    return '다른 중개사의 주문은 정산할 수 없습니다.';
  }
  if (detail.includes('invalid_settlement_order')) {
    return '정산할 수 없는 주문입니다(중개 수수료 미입력 또는 상태 확인).';
  }
  return '처리 중 오류가 발생했습니다.';
}

function defaultBrokerForm(overrides = {}) {
  return {
    name: '',
    manager_name: '',
    phone: '',
    manager_phone: '',
    memo: '',
    is_active: true,
    ...overrides,
  };
}

// 중개사관리 — 협력사관리와 동형. 목록(소개 건수·미정산 수수료) + 상세(정보) + 정산 섹션
// (그 중개사가 소개한 주문의 중개 수수료를 미정산→정산완료로 처리).
export function BrokersPage() {
  const loadBrokers = React.useCallback(() => listAdminBrokers({ includeInactive: true }), []);
  const brokersResource = useApiResource(loadBrokers);
  const brokers = React.useMemo(() => brokersResource.data || [], [brokersResource.data]);

  const [selectedId, setSelectedId] = React.useState(null);
  const [detail, setDetail] = React.useState(null);
  const [detailLoading, setDetailLoading] = React.useState(false);
  const [form, setForm] = React.useState(defaultBrokerForm());
  const [createForm, setCreateForm] = React.useState(defaultBrokerForm());
  const [isCreating, setIsCreating] = React.useState(false);
  const [isSaving, setIsSaving] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [notice, setNotice] = React.useState('');
  const [error, setError] = React.useState('');
  const [query, setQuery] = React.useState('');

  // 정산 상태
  const [settleStatus, setSettleStatus] = React.useState<SettlementFilter>('unpaid');
  const [settlements, setSettlements] = React.useState<BrokerSettlementListResponse | null>(null);
  const [settleLoading, setSettleLoading] = React.useState(false);
  const [settleError, setSettleError] = React.useState(false);
  const [settleMemo, setSettleMemo] = React.useState('');
  const [isSettling, setIsSettling] = React.useState(false);

  const loadSettlements = React.useCallback(async (brokerId: string, status: SettlementFilter) => {
    setSettleLoading(true);
    setSettleError(false);
    try {
      setSettlements(await listBrokerSettlements(brokerId, { status }));
    } catch {
      // 실패를 삼켜 '없음'으로 오표시하지 않도록 에러 상태를 세운다(로딩/에러/빈 3종 분리).
      setSettlements(null);
      setSettleError(true);
    } finally {
      setSettleLoading(false);
    }
  }, []);

  const selectBroker = React.useCallback((brokerId) => {
    setSelectedId(brokerId);
    setDetailLoading(true);
    setError('');
    setNotice('');
    getAdminBroker(brokerId)
      .then((data) => {
        setDetail(data);
        setForm(defaultBrokerForm(data));
      })
      .catch(() => {
        setError('중개사 정보를 불러오지 못했습니다.');
        setSelectedId(null);
        setDetail(null);
      })
      .finally(() => setDetailLoading(false));
  }, []);

  // 선택/필터 변경 시 정산 목록 로드.
  React.useEffect(() => {
    if (!selectedId) {
      setSettlements(null);
      return;
    }
    void loadSettlements(selectedId, settleStatus);
  }, [selectedId, settleStatus, loadSettlements]);

  const refreshAfterSettle = () => {
    if (selectedId) {
      void loadSettlements(selectedId, settleStatus);
      selectBroker(selectedId);
    }
    brokersResource.reload();
  };

  const handleSettle = async (orderIds: string[]) => {
    if (!selectedId || orderIds.length === 0) {
      return;
    }
    setIsSettling(true);
    setError('');
    setNotice('');
    try {
      await settleBrokerOrders(selectedId, orderIds, settleMemo);
      setSettleMemo('');
      setNotice(`${orderIds.length}건 정산 처리했습니다.`);
      refreshAfterSettle();
    } catch (err) {
      setError(brokerErrorMessage(err));
    } finally {
      setIsSettling(false);
    }
  };

  const handleRevert = async (orderIds: string[]) => {
    if (!selectedId || orderIds.length === 0) {
      return;
    }
    setIsSettling(true);
    setError('');
    setNotice('');
    try {
      await revertBrokerOrders(selectedId, orderIds);
      setNotice('정산을 되돌렸습니다.');
      refreshAfterSettle();
    } catch (err) {
      setError(brokerErrorMessage(err));
    } finally {
      setIsSettling(false);
    }
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    if (!createForm.name.trim()) {
      setError('중개사명을 입력해주세요.');
      return;
    }
    setIsCreating(true);
    setError('');
    setNotice('');
    try {
      const created = await createAdminBroker({
        name: createForm.name.trim(),
        manager_name: emptyToNull(createForm.manager_name),
        phone: emptyToNull(createForm.phone),
        manager_phone: emptyToNull(createForm.manager_phone),
        memo: emptyToNull(createForm.memo),
        is_active: true,
      });
      setCreateForm(defaultBrokerForm());
      setNotice('중개사를 등록했습니다.');
      brokersResource.reload();
      if (created?.id) {
        selectBroker(created.id);
      }
    } catch (err) {
      setError(brokerErrorMessage(err));
    } finally {
      setIsCreating(false);
    }
  };

  const handleSave = async () => {
    if (!selectedId || !form.name.trim()) {
      setError('중개사명을 입력해주세요.');
      return;
    }
    setIsSaving(true);
    setError('');
    setNotice('');
    try {
      await updateAdminBroker(selectedId, {
        name: form.name.trim(),
        manager_name: emptyToNull(form.manager_name),
        phone: emptyToNull(form.phone),
        manager_phone: emptyToNull(form.manager_phone),
        memo: emptyToNull(form.memo),
        is_active: form.is_active,
      });
      setNotice('저장했습니다.');
      brokersResource.reload();
      selectBroker(selectedId);
    } catch (err) {
      setError(brokerErrorMessage(err));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedId) {
      return;
    }
    setIsDeleting(true);
    setError('');
    setNotice('');
    try {
      await deleteAdminBroker(selectedId);
      setNotice('중개사를 삭제했습니다.');
      setSelectedId(null);
      setDetail(null);
      brokersResource.reload();
    } catch (err) {
      setError(brokerErrorMessage(err));
    } finally {
      setIsDeleting(false);
    }
  };

  const filtered = React.useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) {
      return brokers;
    }
    return brokers.filter((broker) => String(broker.name || '').toLowerCase().includes(keyword));
  }, [brokers, query]);

  const settleableIds = React.useMemo(
    () => (settlements?.items || []).filter(isSettleable).map((item) => item.order_id),
    [settlements],
  );

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
      {(notice || error) && (
        <div style={{
          padding: 10,
          borderRadius: 6,
          fontSize: 12,
          background: error ? 'var(--danger-bg)' : 'var(--success-bg)',
          color: error ? 'var(--danger-fg)' : 'var(--success-fg)',
        }}>
          {error || notice}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)', gap: 12, alignItems: 'start' }}>
        {/* 목록 */}
        <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={headerRow}>
            <Icon name="star" size={14} color="var(--text-tertiary)" />
            <strong style={{ fontSize: 13 }}>중개사 목록</strong>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{brokers.length}곳</span>
            <div style={{ flex: 1 }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 8px', height: 28, border: '1px solid var(--border)', borderRadius: 7, background: 'var(--bg)' }}>
              <Icon name="search" size={12} color="var(--text-tertiary)" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="중개사 검색"
                aria-label="중개사 검색"
                style={{ border: 'none', outline: 'none', background: 'transparent', fontSize: 12, color: 'var(--text)', width: 120 }}
              />
            </div>
          </div>

          {brokersResource.isLoading ? (
            <div style={emptyBox}>불러오는 중…</div>
          ) : brokersResource.error ? (
            <div style={{ ...emptyBox, color: 'var(--danger-fg)' }}>
              목록을 불러오지 못했습니다.{' '}
              <button className="btn btn--ghost btn--sm" onClick={brokersResource.reload}>다시 시도</button>
            </div>
          ) : filtered.length === 0 ? (
            <div style={emptyBox}>{query ? '검색 결과가 없습니다.' : '등록된 중개사가 없습니다. 오른쪽에서 등록하세요.'}</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
                <thead>
                  <tr>
                    <th style={thLeft}>중개사명</th>
                    <th style={thLeft}>담당자</th>
                    <th style={thLeft}>연락처</th>
                    <th style={thRight}>소개 건수</th>
                    <th style={thRight}>미정산 수수료</th>
                    <th style={thCenter}>상태</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((broker) => (
                    <tr
                      key={broker.id}
                      data-testid={`broker-row-${broker.id}`}
                      onClick={() => selectBroker(broker.id)}
                      style={{ cursor: 'pointer', background: broker.id === selectedId ? 'var(--brand-bg)' : 'transparent' }}
                    >
                      <td style={tdLeft}><span style={{ fontWeight: 600 }}>{broker.name}</span></td>
                      <td style={tdLeft}>{broker.manager_name || '—'}</td>
                      <td style={tdLeft} className="mono">{broker.phone ? formatPhone(broker.phone) : '—'}</td>
                      <td style={tdRight}>{broker.order_count ?? 0}건</td>
                      <td style={tdRight}>
                        {won(broker.unpaid_broker_amount_total)}
                        {(broker.unpaid_broker_order_count ?? 0) > 0 && (
                          <span style={{ fontSize: 10.5, color: 'var(--text-tertiary)' }}> ({broker.unpaid_broker_order_count}건)</span>
                        )}
                      </td>
                      <td style={tdCenter}>
                        <span style={{ fontSize: 11, fontWeight: 600, color: broker.is_active ? 'var(--success-fg)' : 'var(--text-tertiary)' }}>
                          {broker.is_active ? '활성' : '비활성'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* 상세 정보 + 등록 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {selectedId && (
            <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div style={headerRow}>
                <Icon name="star" size={14} color="var(--text-tertiary)" />
                <strong style={{ fontSize: 13 }}>중개사 정보</strong>
                <div style={{ flex: 1 }} />
                <button className="btn btn--ghost btn--sm" onClick={() => { setSelectedId(null); setDetail(null); }}>닫기</button>
              </div>
              {detailLoading ? (
                <div style={emptyBox}>불러오는 중…</div>
              ) : (
                <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={formGrid}>
                    <FormRow label="중개사명" value={form.name} onChange={(value) => setForm({ ...form, name: value })} required />
                    <FormRow label="담당자" value={form.manager_name} onChange={(value) => setForm({ ...form, manager_name: value })} />
                    <FormRow label="대표 연락처" value={form.phone} onChange={(value) => setForm({ ...form, phone: value })} />
                    <FormRow label="담당자 연락처" value={form.manager_phone} onChange={(value) => setForm({ ...form, manager_phone: value })} />
                  </div>
                  <FormRow label="메모" value={form.memo} onChange={(value) => setForm({ ...form, memo: value })} multiline />
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5 }}>
                    <input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} /> 활성
                  </label>
                  <div style={{ display: 'flex', gap: 6, justifyContent: 'space-between' }}>
                    <button className="btn btn--ghost btn--sm" onClick={handleDelete} disabled={isDeleting} style={{ color: 'var(--danger-fg)' }}>
                      <Icon name="x" size={12} /> 삭제
                    </button>
                    <button data-testid="broker-detail-save" className="btn btn--primary btn--sm" onClick={handleSave} disabled={isSaving}>저장</button>
                  </div>
                </div>
              )}
            </section>
          )}

          <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={headerRow}>
              <Icon name="plus" size={14} color="var(--text-tertiary)" />
              <strong style={{ fontSize: 13 }}>새 중개사 등록</strong>
            </div>
            <form onSubmit={handleCreate} style={{ padding: 14, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
              <FormRow testId="broker-create-name" label="중개사명" value={createForm.name} onChange={(value) => setCreateForm({ ...createForm, name: value })} required />
              <FormRow label="담당자" value={createForm.manager_name} onChange={(value) => setCreateForm({ ...createForm, manager_name: value })} />
              <FormRow label="대표 연락처" value={createForm.phone} onChange={(value) => setCreateForm({ ...createForm, phone: value })} />
              <FormRow label="담당자 연락처" value={createForm.manager_phone} onChange={(value) => setCreateForm({ ...createForm, manager_phone: value })} />
              <div style={{ gridColumn: '1 / -1' }}>
                <FormRow label="메모" value={createForm.memo} onChange={(value) => setCreateForm({ ...createForm, memo: value })} multiline />
              </div>
              <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end' }}>
                <button data-testid="broker-create-submit" className="btn btn--primary btn--sm" disabled={isCreating}>
                  <Icon name="plus" size={12} /> 등록
                </button>
              </div>
            </form>
          </section>
        </div>
      </div>

      {/* 정산 섹션 (전체폭) — 선택한 중개사가 소개한 주문의 중개 수수료 정산 */}
      {selectedId && (
        <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={headerRow}>
            <Icon name="list" size={14} color="var(--text-tertiary)" />
            <strong style={{ fontSize: 13 }}>배정 주문 / 정산</strong>
            <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>
              미정산 {detail?.unpaid_broker_order_count ?? 0}건 · {won(detail?.unpaid_broker_amount_total)}
            </span>
            <div style={{ flex: 1 }} />
            <select
              className="input"
              data-testid="broker-settlement-status"
              value={settleStatus}
              onChange={(event) => setSettleStatus(event.target.value as SettlementFilter)}
              style={{ height: 28, width: 120 }}
            >
              <option value="unpaid">미정산</option>
              <option value="paid">정산완료</option>
              <option value="all">전체</option>
            </select>
          </div>

          {settleLoading ? (
            <div style={emptyBox}>정산 목록을 불러오는 중…</div>
          ) : settleError ? (
            <div style={{ ...emptyBox, color: 'var(--danger-fg)' }}>
              정산 목록을 불러오지 못했습니다.{' '}
              <button
                className="btn btn--ghost btn--sm"
                onClick={() => selectedId && void loadSettlements(selectedId, settleStatus)}
              >
                다시 시도
              </button>
            </div>
          ) : !settlements || settlements.items.length === 0 ? (
            <div style={emptyBox}>조건에 맞는 소개 주문이 없습니다.</div>
          ) : (
            <>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', minWidth: 820, borderCollapse: 'collapse', fontSize: 12.5 }}>
                  <thead>
                    <tr>
                      <th style={thLeft}>방문일</th>
                      <th style={thLeft}>서비스</th>
                      <th style={thLeft}>고객</th>
                      <th style={thRight}>소비자가</th>
                      <th style={thRight}>중개 수수료</th>
                      <th style={thCenter}>정산</th>
                      <th style={thCenter}>액션</th>
                    </tr>
                  </thead>
                  <tbody>
                    {settlements.items.map((job) => {
                      const isPaid = job.broker_payment_status === 'paid';
                      const isCancelled = job.status === '취소';
                      return (
                        <tr key={job.order_id} data-testid={`broker-settlement-row-${job.order_id}`}>
                          <td style={tdLeft} className="mono">{job.scheduled_date ?? '미정'}</td>
                          <td style={tdLeft}>
                            <div style={{ minWidth: 0 }}>
                              <div>{job.service_name}</div>
                              <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{settlementAddress(job)}</div>
                            </div>
                          </td>
                          <td style={tdLeft}>{job.customer_name}</td>
                          <td style={tdRight} className="mono">{won(job.consumer_price)}</td>
                          <td style={tdRight} className="mono">{won(job.broker_price)}</td>
                          <td style={tdCenter}>
                            {isCancelled ? (
                              <span style={{ color: 'var(--text-quaternary)', fontSize: 11.5, fontWeight: 600 }}>정산 제외</span>
                            ) : isPaid ? (
                              <span style={{ color: 'var(--success-fg)', fontSize: 11.5, fontWeight: 700 }}>정산완료</span>
                            ) : (
                              <span style={{ color: 'var(--warn-fg)', fontSize: 11.5, fontWeight: 700 }}>미정산</span>
                            )}
                          </td>
                          <td style={tdCenter}>
                            {isCancelled ? (
                              <span style={{ color: 'var(--text-quaternary)', fontSize: 11.5 }}>—</span>
                            ) : isPaid ? (
                              <button
                                type="button"
                                data-testid={`broker-settlement-revert-${job.order_id}`}
                                className="btn btn--secondary btn--sm"
                                disabled={isSettling}
                                onClick={() => void handleRevert([job.order_id])}
                              >
                                되돌리기
                              </button>
                            ) : (
                              <button
                                type="button"
                                data-testid={`broker-settlement-settle-${job.order_id}`}
                                className="btn btn--secondary btn--sm"
                                disabled={isSettling || !isSettleable(job)}
                                title={isSettleable(job) ? undefined : '중개 수수료를 입력한 미정산 건만 정산할 수 있습니다.'}
                                onClick={() => void handleSettle([job.order_id])}
                              >
                                정산
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div style={{ padding: 12, borderTop: '1px solid var(--divider)', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  표시 합계 · 수수료 {won(settlements.total_broker_price)} / 소비자가 {won(settlements.total_consumer_price)}
                </span>
                <div style={{ flex: 1 }} />
                <input
                  className="input"
                  placeholder="정산 메모(선택)"
                  value={settleMemo}
                  onChange={(event) => setSettleMemo(event.target.value)}
                  style={{ width: 180, height: 30 }}
                />
                <button
                  type="button"
                  data-testid="broker-settlement-settle-all"
                  className="btn btn--primary btn--sm"
                  disabled={isSettling || settleableIds.length === 0}
                  onClick={() => void handleSettle(settleableIds)}
                >
                  미정산 {settleableIds.length}건 정산
                </button>
              </div>
            </>
          )}
        </section>
      )}
    </div>
  );
}

function isSettleable(job: BrokerSettlementItem): boolean {
  // 취소 아님 + 미지급 + 중개 수수료가 입력됨(0 초과). 백엔드 정산 가드와 일치.
  return job.status !== '취소' && job.broker_payment_status !== 'paid' && (job.broker_price ?? 0) > 0;
}

function settlementAddress(job: BrokerSettlementItem): string {
  return [job.address_short, job.address_detail].filter(Boolean).join(' ') || '-';
}

const headerRow: React.CSSProperties = {
  height: 42,
  padding: '0 14px',
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  borderBottom: '1px solid var(--divider)',
};
const formGrid: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
  gap: 10,
};
const emptyBox: React.CSSProperties = {
  padding: '32px 14px',
  textAlign: 'center',
  fontSize: 12.5,
  color: 'var(--text-tertiary)',
};
const thLeft: React.CSSProperties = {
  textAlign: 'left',
  padding: '8px 12px',
  fontSize: 11,
  color: 'var(--text-tertiary)',
  fontWeight: 600,
  borderBottom: '1px solid var(--divider)',
  whiteSpace: 'nowrap',
};
const thRight: React.CSSProperties = { ...thLeft, textAlign: 'right' };
const thCenter: React.CSSProperties = { ...thLeft, textAlign: 'center' };
const tdLeft: React.CSSProperties = {
  padding: '8px 12px',
  borderBottom: '1px solid var(--divider)',
  verticalAlign: 'top',
};
const tdRight: React.CSSProperties = { ...tdLeft, textAlign: 'right', whiteSpace: 'nowrap' };
const tdCenter: React.CSSProperties = { ...tdLeft, textAlign: 'center', whiteSpace: 'nowrap' };

function FormRow({ label, value, onChange, required = false, multiline = false, testId = undefined }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
      <span style={{ color: 'var(--text-tertiary)', fontWeight: 600 }}>
        {label}{required && <span style={{ color: 'var(--danger-fg)' }}> *</span>}
      </span>
      {multiline ? (
        <textarea
          className="input"
          data-testid={testId}
          value={value || ''}
          onChange={(event) => onChange(event.target.value)}
          style={{ minHeight: 60, padding: 8, resize: 'vertical' }}
        />
      ) : (
        <input
          className="input"
          data-testid={testId}
          value={value || ''}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </label>
  );
}
