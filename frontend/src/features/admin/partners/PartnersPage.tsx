import React from 'react';

import {
  createAdminPartner,
  deleteAdminPartner,
  getAdminPartner,
  listAdminPartners,
  resetAdminPartnerPassword,
  updateAdminPartner,
} from '../../../api/admin';
import { useApiResource } from '../../../api/useApiResource';
import { Badge, Icon, StatusBadge } from '../../../components/common/ui';

export function PartnersPage() {
  const loadPartners = React.useCallback(() => listAdminPartners({ includeInactive: true }), []);
  const partnersResource = useApiResource(loadPartners);
  const partners = React.useMemo(() => partnersResource.data || [], [partnersResource.data]);
  const [selectedId, setSelectedId] = React.useState(null);
  const [detail, setDetail] = React.useState(null);
  const [form, setForm] = React.useState(defaultPartnerForm());
  const [createForm, setCreateForm] = React.useState(defaultPartnerForm({ is_active: true }));
  const [detailLoading, setDetailLoading] = React.useState(false);
  const [isCreating, setIsCreating] = React.useState(false);
  const [isSaving, setIsSaving] = React.useState(false);
  const [isResetting, setIsResetting] = React.useState(false);
  const [resetPassword, setResetPassword] = React.useState('');
  const [resetLoginPhone, setResetLoginPhone] = React.useState('');
  const [notice, setNotice] = React.useState('');
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    if (partners.length === 0) {
      return;
    }
    if (!selectedId || (!partners.some((partner) => partner.id === selectedId) && detail?.id !== selectedId)) {
      setSelectedId(partners[0].id);
    }
  }, [detail?.id, partners, selectedId]);

  React.useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }

    let isCurrent = true;
    setDetailLoading(true);
    setError('');

    getAdminPartner(selectedId)
      .then((partner) => {
        if (!isCurrent) {
          return;
        }
        setDetail(partner);
        setForm(toPartnerForm(partner));
        setResetLoginPhone(partner.login_phone || partner.phone || '');
        setResetPassword('');
      })
      .catch(() => {
        if (isCurrent) {
          setError('협력사 상세 정보를 불러오지 못했습니다.');
        }
      })
      .finally(() => {
        if (isCurrent) {
          setDetailLoading(false);
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedId]);

  const stats = toPartnerStats(partners);

  const handleCreate = async (event) => {
    event.preventDefault();
    setError('');
    setNotice('');
    setIsCreating(true);
    try {
      const created = await createAdminPartner(toPartnerPayload(createForm, { includeLogin: true }));
      setCreateForm(defaultPartnerForm({ is_active: true }));
      setSelectedId(created.id);
      setDetail(created);
      setForm(toPartnerForm(created));
      setResetLoginPhone(created.login_phone || created.phone || '');
      setNotice('새 협력사를 등록했습니다.');
      partnersResource.reload();
    } catch (requestError) {
      setError(partnerErrorMessage(requestError, '협력사 등록에 실패했습니다.'));
    } finally {
      setIsCreating(false);
    }
  };

  const handleSave = async (event) => {
    event.preventDefault();
    if (!detail) {
      return;
    }

    setError('');
    setNotice('');
    setIsSaving(true);
    try {
      const updated = await updateAdminPartner(detail.id, toPartnerPayload(form));
      setDetail(updated);
      setForm(toPartnerForm(updated));
      setResetLoginPhone(updated.login_phone || updated.phone || '');
      setNotice('협력사 정보를 저장했습니다.');
      partnersResource.reload();
    } catch (requestError) {
      setError(partnerErrorMessage(requestError, '협력사 저장에 실패했습니다.'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleActive = async () => {
    if (!detail) {
      return;
    }

    setError('');
    setNotice('');
    setIsSaving(true);
    try {
      const updated = await updateAdminPartner(detail.id, { is_active: !detail.is_active });
      setDetail(updated);
      setForm(toPartnerForm(updated));
      setNotice(updated.is_active ? '협력사 계정을 활성화했습니다.' : '협력사 계정을 비활성화했습니다.');
      partnersResource.reload();
    } catch (requestError) {
      setError(partnerErrorMessage(requestError, '협력사 상태 변경에 실패했습니다.'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!detail) {
      return;
    }
    if (!window.confirm(`'${detail.name}' 협력사를 삭제할까요?`)) {
      return;
    }

    setError('');
    setNotice('');
    setIsSaving(true);
    try {
      await deleteAdminPartner(detail.id);
      setSelectedId(null);
      setDetail(null);
      setForm(defaultPartnerForm());
      setResetLoginPhone('');
      setNotice('협력사를 삭제했습니다.');
      partnersResource.reload();
    } catch (requestError) {
      setError(partnerErrorMessage(requestError, '협력사 삭제에 실패했습니다.'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetPassword = async () => {
    if (!detail) {
      return;
    }

    setError('');
    setNotice('');
    setIsResetting(true);
    try {
      const result = await resetAdminPartnerPassword(detail.id, toResetPayload(resetLoginPhone, resetPassword));
      setResetPassword('');
      setResetLoginPhone(result.login_phone);
      setDetail((current) => current ? {
        ...current,
        user_id: result.user_id,
        login_phone: result.login_phone,
        user_is_active: current.is_active,
      } : current);
      setNotice(`임시 비밀번호: ${result.temporary_password}`);
      partnersResource.reload();
    } catch (requestError) {
      setError(partnerErrorMessage(requestError, '비밀번호 재설정에 실패했습니다.'));
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div data-testid="admin-partners-page" style={{ flex: 1, minHeight: 0, overflow: 'auto', background: 'var(--bg)' }}>
      <div style={{ padding: 20, maxWidth: 1280, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
          <StatCard label="전체 협력사" value={partners.length} icon="truck" />
          <StatCard label="활성 협력사" value={stats.active} icon="check" tone="success" />
          <StatCard label="운영 중 작업" value={stats.activeJobs} icon="calendar" tone="info" />
          <StatCard label="계정 미연결" value={stats.missingLogin} icon="lock" tone="warn" />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(360px, 0.95fr) minmax(0, 1.45fr)', gap: 12, alignItems: 'start' }}>
          <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <SectionHeader
              icon="truck"
              title="협력사 목록"
              right={(
                <button className="btn btn--ghost btn--sm" onClick={partnersResource.reload}>
                  <Icon name="refresh" size={12} /> 새로고침
                </button>
              )}
            />

            {partnersResource.isLoading && <StateLine text="협력사 목록을 불러오는 중입니다." />}
            {!partnersResource.isLoading && partnersResource.error && <StateLine text="협력사 목록을 불러오지 못했습니다." tone="danger" />}
            {!partnersResource.isLoading && !partnersResource.error && partners.length === 0 && <StateLine text="등록된 협력사가 없습니다." />}

            {!partnersResource.isLoading && !partnersResource.error && partners.length > 0 && (
              <div className="scroll" style={{ maxHeight: 470, overflow: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr>
                      <Th>상태</Th>
                      <Th>협력사</Th>
                      <Th>작업</Th>
                      <Th>계정</Th>
                      <Th>관리</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {partners.map((partner) => {
                      const isSelected = partner.id === selectedId;
                      return (
                        <tr
                          key={partner.id}
                          onClick={() => setSelectedId(partner.id)}
                          style={{
                            cursor: 'pointer',
                            background: isSelected ? 'var(--brand-bg)' : 'transparent',
                            borderTop: '1px solid var(--divider)',
                          }}
                        >
                          <Td>
                            <Badge tone={partner.is_active ? 'success' : 'neutral'} dot>
                              {partner.is_active ? '활성' : '비활성'}
                            </Badge>
                          </Td>
                          <Td>
                            <div style={{ fontWeight: 600, color: 'var(--text)' }}>{partner.name}</div>
                            <div style={{ color: 'var(--text-tertiary)', marginTop: 2 }}>{partner.manager_name || '-'} · {maskPhone(partner.phone)}</div>
                          </Td>
                          <Td>
                            <span className="mono" style={{ color: 'var(--text-secondary)' }}>{partner.active_job_count}</span>
                            <span style={{ color: 'var(--text-tertiary)' }}> / {partner.scheduled_job_count}</span>
                          </Td>
                          <Td>
                            {partner.login_phone ? (
                              <span className="mono" style={{ color: partner.user_is_active ? 'var(--text-secondary)' : 'var(--text-tertiary)' }}>
                                {maskPhone(partner.login_phone)}
                              </span>
                            ) : (
                              <Badge tone="warn">없음</Badge>
                            )}
                          </Td>
                          <Td>
                            <button
                              type="button"
                              className="btn btn--secondary btn--sm"
                              aria-label={`${partner.name} 수정`}
                              onClick={(event) => {
                                event.stopPropagation();
                                setSelectedId(partner.id);
                              }}
                            >
                              수정
                            </button>
                          </Td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <SectionHeader icon="plus" title="새 협력사 등록" />
              <form onSubmit={handleCreate} style={{ padding: 14, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
                <FormField testId="partner-create-name" label="협력사명" value={createForm.name} onChange={(value) => setCreateForm({ ...createForm, name: value })} required />
                <FormField label="담당자" value={createForm.manager_name} onChange={(value) => setCreateForm({ ...createForm, manager_name: value })} />
                <FormField testId="partner-create-phone" label="대표 연락처" value={createForm.phone} onChange={(value) => setCreateForm({ ...createForm, phone: value })} required />
                <FormField label="로그인 연락처" value={createForm.login_phone} onChange={(value) => setCreateForm({ ...createForm, login_phone: value })} />
                <FormField label="초기 비밀번호" value={createForm.login_password} onChange={(value) => setCreateForm({ ...createForm, login_password: value })} type="password" />
                <FormField label="권역" value={createForm.service_areas} onChange={(value) => setCreateForm({ ...createForm, service_areas: value })} />
                <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end' }}>
                  <button data-testid="partner-create-submit" className="btn btn--primary btn--sm" disabled={isCreating}>
                    <Icon name="plus" size={12} /> 등록
                  </button>
                </div>
              </form>
            </section>

            <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <SectionHeader
                icon="user"
                title={detail ? detail.name : '협력사 상세'}
                right={detail && (
                  <Badge tone={detail.is_active ? 'success' : 'neutral'} dot>
                    {detail.is_active ? '활성' : '비활성'}
                  </Badge>
                )}
              />

              {detailLoading && <StateLine text="협력사 상세 정보를 불러오는 중입니다." />}
              {!detailLoading && !detail && <StateLine text="목록에서 협력사를 선택하세요." />}
              {!detailLoading && detail && (
                <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 300px', gap: 0 }}>
                  <form onSubmit={handleSave} style={{ padding: 14, borderRight: '1px solid var(--divider)', display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
                      <FormField testId="partner-detail-name" label="협력사명" value={form.name} onChange={(value) => setForm({ ...form, name: value })} required />
                      <FormField label="담당자" value={form.manager_name} onChange={(value) => setForm({ ...form, manager_name: value })} />
                      <FormField testId="partner-detail-phone" label="대표 연락처" value={form.phone} onChange={(value) => setForm({ ...form, phone: value })} required />
                      <FormField label="권역" value={form.service_areas} onChange={(value) => setForm({ ...form, service_areas: value })} />
                    </div>
                    <TextAreaField label="가능 서비스" value={form.available_services} onChange={(value) => setForm({ ...form, available_services: value })} />
                    <TextAreaField label="운영 메모" value={form.memo} onChange={(value) => setForm({ ...form, memo: value })} />

                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                      <button
                        type="button"
                        data-testid="partner-delete"
                        className="btn btn--danger btn--sm"
                        disabled={isSaving || Number(detail.scheduled_job_count || 0) > 0}
                        onClick={handleDelete}
                        title={Number(detail.scheduled_job_count || 0) > 0 ? '배정 작업이 없는 협력사만 삭제할 수 있습니다.' : '협력사 삭제'}
                      >
                        <Icon name="x" size={12} /> 삭제
                      </button>
                      <button type="button" data-testid="partner-toggle-active" className="btn btn--secondary btn--sm" disabled={isSaving} onClick={handleToggleActive}>
                        <Icon name={detail.is_active ? 'x' : 'check'} size={12} />
                        {detail.is_active ? '비활성화' : '활성화'}
                      </button>
                      <button data-testid="partner-save" className="btn btn--primary btn--sm" disabled={isSaving}>
                        <Icon name="check" size={12} /> 저장
                      </button>
                    </div>
                  </form>

                  <aside style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 14 }}>
                    <div>
                      <div style={labelStyle}>운영 지표</div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
                        <MiniMetric label="예정" value={detail.scheduled_job_count} />
                        <MiniMetric label="진행" value={detail.active_job_count} />
                        <MiniMetric label="완료" value={detail.completed_job_count} />
                      </div>
                    </div>

                    <div>
                      <div style={labelStyle}>계정</div>
                      <KV label="로그인" value={detail.login_phone ? maskPhone(detail.login_phone) : '미연결'} />
                      <KV label="상태" value={detail.user_is_active === false ? '비활성' : detail.login_phone ? '활성' : '-'} />
                      <KV label="최근 로그인" value={formatDateTime(detail.last_login_at)} />
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <FormField label="로그인 연락처" value={resetLoginPhone} onChange={setResetLoginPhone} />
                      <FormField label="새 비밀번호" value={resetPassword} onChange={setResetPassword} type="password" placeholder="비워두면 자동 생성" />
                      <button type="button" className="btn btn--secondary btn--sm" disabled={isResetting} onClick={handleResetPassword}>
                        <Icon name="lock" size={12} /> 비밀번호 재설정
                      </button>
                    </div>
                  </aside>
                </div>
              )}
            </section>

            {detail && (
              <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <SectionHeader icon="list" title="최근 배정 작업" />
                {detail.jobs.length === 0 ? (
                  <StateLine text="최근 배정된 작업이 없습니다." />
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: '100px 110px 1fr 90px', fontSize: 12 }}>
                    {['방문일', '상태', '작업', '고객'].map((header) => <GridHead key={header}>{header}</GridHead>)}
                    {detail.jobs.map((job) => (
                      <React.Fragment key={job.id}>
                        <GridCell mono>{formatDate(job.scheduled_date)} {job.requested_time || ''}</GridCell>
                        <GridCell><StatusBadge status={job.status} /></GridCell>
                        <GridCell>
                          <div style={{ minWidth: 0 }}>
                            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.service_name} {job.size_or_quantity || ''}</div>
                            <div style={{ marginTop: 2, color: 'var(--text-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.customer_address}</div>
                          </div>
                        </GridCell>
                        <GridCell>{job.customer_name}</GridCell>
                      </React.Fragment>
                    ))}
                  </div>
                )}
              </section>
            )}
          </div>
        </div>

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
      </div>
    </div>
  );
}

function SectionHeader({ icon, title, right = null }) {
  return (
    <div style={{
      height: 42,
      padding: '0 14px',
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      borderBottom: '1px solid var(--divider)',
    }}>
      <Icon name={icon} size={14} color="var(--text-tertiary)" />
      <strong style={{ fontSize: 13 }}>{title}</strong>
      <div style={{ flex: 1 }} />
      {right}
    </div>
  );
}

function StatCard({ label, value, icon, tone = 'neutral' }) {
  return (
    <div className="card" style={{ padding: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
      <span style={{
        width: 30,
        height: 30,
        borderRadius: 6,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: `var(--${tone}-bg, var(--neutral-bg))`,
        color: `var(--${tone}-fg, var(--neutral-fg))`,
      }}>
        <Icon name={icon} size={14} />
      </span>
      <div>
        <div style={{ fontSize: 20, fontWeight: 700, lineHeight: 1 }}>{value}</div>
        <div style={{ marginTop: 4, fontSize: 11.5, color: 'var(--text-tertiary)' }}>{label}</div>
      </div>
    </div>
  );
}

function FormField({ label, value, onChange, type = 'text', required = false, placeholder = '', testId = undefined }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
      <span style={labelStyle}>{label}</span>
      <input
        className="input"
        data-testid={testId}
        type={type}
        value={value || ''}
        required={required}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        style={{ height: 32, fontSize: 12 }}
      />
    </label>
  );
}

function TextAreaField({ label, value, onChange }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <span style={labelStyle}>{label}</span>
      <textarea
        className="input"
        value={value || ''}
        onChange={(event) => onChange(event.target.value)}
        rows={3}
        style={{ resize: 'vertical', minHeight: 62, padding: 8, fontSize: 12 }}
      />
    </label>
  );
}

function MiniMetric({ label, value }) {
  return (
    <div style={{ padding: 8, border: '1px solid var(--border)', borderRadius: 6 }}>
      <div className="mono" style={{ fontSize: 16, fontWeight: 700 }}>{value}</div>
      <div style={{ marginTop: 2, fontSize: 10.5, color: 'var(--text-tertiary)' }}>{label}</div>
    </div>
  );
}

function KV({ label, value }) {
  return (
    <div style={{ display: 'flex', gap: 8, minHeight: 22, alignItems: 'center', fontSize: 12 }}>
      <span style={{ width: 70, color: 'var(--text-tertiary)' }}>{label}</span>
      <span style={{ flex: 1, color: 'var(--text)' }}>{value || '-'}</span>
    </div>
  );
}

function Th({ children }) {
  return (
    <th style={{
      padding: '9px 10px',
      textAlign: 'left',
      color: 'var(--text-tertiary)',
      fontSize: 11,
      fontWeight: 600,
      background: 'var(--bg-subtle)',
      borderTop: '1px solid var(--divider)',
    }}>
      {children}
    </th>
  );
}

function Td({ children }) {
  return (
    <td style={{ padding: '10px', verticalAlign: 'middle', minWidth: 0 }}>
      {children}
    </td>
  );
}

function GridHead({ children }) {
  return (
    <div style={{
      padding: '9px 12px',
      borderTop: '1px solid var(--divider)',
      borderBottom: '1px solid var(--divider)',
      color: 'var(--text-tertiary)',
      fontSize: 11,
      fontWeight: 600,
      background: 'var(--bg-subtle)',
    }}>
      {children}
    </div>
  );
}

function GridCell({ children, mono = false }) {
  return (
    <div style={{
      minWidth: 0,
      minHeight: 46,
      padding: '9px 12px',
      borderBottom: '1px solid var(--divider)',
      display: 'flex',
      alignItems: 'center',
      color: 'var(--text)',
      fontFamily: mono ? 'var(--font-mono)' : 'inherit',
    }}>
      {children}
    </div>
  );
}

function StateLine({ text, tone = 'muted' }) {
  return (
    <div style={{
      padding: 18,
      fontSize: 12.5,
      color: tone === 'danger' ? 'var(--danger-fg)' : 'var(--text-tertiary)',
    }}>
      {text}
    </div>
  );
}

function toPartnerStats(partners) {
  return partners.reduce((stats, partner) => {
    stats.active += partner.is_active ? 1 : 0;
    stats.activeJobs += Number(partner.active_job_count || 0);
    stats.missingLogin += partner.login_phone ? 0 : 1;
    return stats;
  }, { active: 0, activeJobs: 0, missingLogin: 0 });
}

function defaultPartnerForm(overrides = {}) {
  return {
    name: '',
    manager_name: '',
    phone: '',
    service_areas: '',
    available_services: '',
    memo: '',
    is_active: true,
    login_phone: '',
    login_password: '',
    ...overrides,
  };
}

function toPartnerForm(partner) {
  return defaultPartnerForm({
    name: partner.name || '',
    manager_name: partner.manager_name || '',
    phone: partner.phone || '',
    service_areas: partner.service_areas || '',
    available_services: partner.available_services || '',
    memo: partner.memo || '',
    is_active: partner.is_active !== false,
    login_phone: partner.login_phone || '',
    login_password: '',
  });
}

function toPartnerPayload(form, { includeLogin = false } = {}) {
  const payload = {
    name: form.name.trim(),
    manager_name: optionalText(form.manager_name),
    phone: form.phone.trim(),
    service_areas: optionalText(form.service_areas),
    available_services: optionalText(form.available_services),
    memo: optionalText(form.memo),
    is_active: form.is_active !== false,
    login_phone: undefined,
    login_password: undefined,
  };

  if (includeLogin) {
    const loginPhone = optionalText(form.login_phone);
    const loginPassword = optionalText(form.login_password);
    if (loginPhone) {
      payload.login_phone = loginPhone;
    }
    if (loginPassword) {
      payload.login_password = loginPassword;
    }
  }

  return payload;
}

function toResetPayload(loginPhone, password) {
  const payload = {
    login_phone: undefined,
    password: undefined,
  };
  const normalizedLoginPhone = optionalText(loginPhone);
  const normalizedPassword = optionalText(password);
  if (normalizedLoginPhone) {
    payload.login_phone = normalizedLoginPhone;
  }
  if (normalizedPassword) {
    payload.password = normalizedPassword;
  }
  return payload;
}

function optionalText(value) {
  const text = String(value || '').trim();
  return text.length > 0 ? text : null;
}

function partnerErrorMessage(error, fallback) {
  const messages = {
    partner_not_found: '협력사를 찾을 수 없습니다.',
    partner_in_use: '이미 배정 이력이 있는 협력사는 삭제할 수 없습니다. 비활성화를 사용해주세요.',
  };
  return messages[error?.message] || fallback;
}

function maskPhone(phone) {
  if (!phone) {
    return '-';
  }
  const digits = phone.replace(/\D/g, '');
  if (digits.length < 8) {
    return phone;
  }
  return `${digits.slice(0, 3)}-${digits.slice(3, 5)}**-${digits.slice(-4)}`;
}

function formatDate(value) {
  if (!value) {
    return '미정';
  }
  const date = new Date(`${value}T00:00:00`);
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function formatDateTime(value) {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

const labelStyle = {
  fontSize: 11,
  color: 'var(--text-tertiary)',
  fontWeight: 600,
};
