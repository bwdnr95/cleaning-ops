import React from 'react';

import {
  createAdminPartner,
  createPartnerCategory,
  deleteAdminPartner,
  deletePartnerCategory,
  getAdminPartner,
  listAdminPartners,
  listPartnerCategories,
  resetAdminPartnerPassword,
  updateAdminPartner,
  updatePartnerCategory,
} from '../../../api/admin';
import { PaginationBar, paginateItems } from '../../../components/common/Pagination';
import { useApiResource } from '../../../api/useApiResource';
import { Badge, Icon, StatusBadge } from '../../../components/common/ui';
import { formatPhone } from '../../../domain/phone';
import { formatAppDateTime, parseDateValue } from '../../../domain/time';

const ALL_CATEGORY_FILTER = 'all';
const UNCLASSIFIED_CATEGORY_FILTER = 'unclassified';

export function PartnersPage() {
  const loadPartners = React.useCallback(() => listAdminPartners({ includeInactive: true }), []);
  const loadCategories = React.useCallback(() => listPartnerCategories({ includeInactive: true }), []);
  const partnersResource = useApiResource(loadPartners);
  const categoriesResource = useApiResource(loadCategories);
  const partners = React.useMemo(() => partnersResource.data || [], [partnersResource.data]);
  const categories = React.useMemo(() => categoriesResource.data || [], [categoriesResource.data]);
  const [categoryFilter, setCategoryFilter] = React.useState(ALL_CATEGORY_FILTER);
  const [partnersPage, setPartnersPage] = React.useState(1);
  const [partnersPageSize, setPartnersPageSize] = React.useState(20);
  const [selectedCategoryId, setSelectedCategoryId] = React.useState('');
  const [categoryForm, setCategoryForm] = React.useState(defaultCategoryForm());
  const [selectedId, setSelectedId] = React.useState(null);
  const [detail, setDetail] = React.useState(null);
  const [form, setForm] = React.useState(defaultPartnerForm());
  const [createForm, setCreateForm] = React.useState(defaultPartnerForm({ is_active: true }));
  const [detailLoading, setDetailLoading] = React.useState(false);
  const [isCreating, setIsCreating] = React.useState(false);
  const [isSaving, setIsSaving] = React.useState(false);
  const [isSavingCategory, setIsSavingCategory] = React.useState(false);
  const [isResetting, setIsResetting] = React.useState(false);
  const [resetPassword, setResetPassword] = React.useState('');
  const [resetLoginPhone, setResetLoginPhone] = React.useState('');
  const [notice, setNotice] = React.useState('');
  const [error, setError] = React.useState('');

  const filteredPartners = React.useMemo(
    () => filterPartnersByCategory(partners, categoryFilter),
    [categoryFilter, partners],
  );
  const pagedPartners = React.useMemo(
    () => paginateItems(filteredPartners, partnersPage, partnersPageSize),
    [filteredPartners, partnersPage, partnersPageSize],
  );
  const selectedCategory = categories.find((category) => category.id === selectedCategoryId) || null;

  React.useEffect(() => {
    if (categories.length > 0 && !selectedCategoryId) {
      setSelectedCategoryId(categories[0].id);
    }
  }, [categories, selectedCategoryId]);

  React.useEffect(() => {
    setCategoryForm(selectedCategory ? toCategoryForm(selectedCategory) : defaultCategoryForm());
  }, [selectedCategory]);

  React.useEffect(() => {
    if (filteredPartners.length === 0) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || (!filteredPartners.some((partner) => partner.id === selectedId) && detail?.id !== selectedId)) {
      setSelectedId(filteredPartners[0].id);
    }
  }, [detail?.id, filteredPartners, selectedId]);

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

  const handleCategoryFilter = (nextFilter) => {
    setCategoryFilter(nextFilter);
    setPartnersPage(1);
    const nextPartners = filterPartnersByCategory(partners, nextFilter);
    setSelectedId(nextPartners[0]?.id || null);
    if (nextFilter !== ALL_CATEGORY_FILTER) {
      setCreateForm((current) => ({
        ...current,
        partner_category_id: nextFilter === UNCLASSIFIED_CATEGORY_FILTER ? '' : nextFilter,
      }));
    }
  };

  const handleCreateCategory = async () => {
    setError('');
    setNotice('');
    setIsSavingCategory(true);
    try {
      const created = await createPartnerCategory({
        name: '새 대분류',
        description: null,
        is_active: true,
        sort_order: categories.length * 10 + 10,
      });
      setSelectedCategoryId(created.id);
      setCategoryFilter(created.id);
      setCreateForm((current) => ({ ...current, partner_category_id: created.id }));
      setNotice('협력사 대분류를 등록했습니다.');
      categoriesResource.reload();
    } catch (requestError) {
      setError(partnerErrorMessage(requestError, '대분류 등록에 실패했습니다.'));
    } finally {
      setIsSavingCategory(false);
    }
  };

  const handleSaveCategory = async (event) => {
    event.preventDefault();
    if (!selectedCategory) {
      return;
    }

    setError('');
    setNotice('');
    setIsSavingCategory(true);
    try {
      const updated = await updatePartnerCategory(selectedCategory.id, toCategoryPayload(categoryForm));
      setSelectedCategoryId(updated.id);
      setNotice('협력사 대분류를 저장했습니다.');
      categoriesResource.reload();
      partnersResource.reload();
    } catch (requestError) {
      setError(partnerErrorMessage(requestError, '대분류 저장에 실패했습니다.'));
    } finally {
      setIsSavingCategory(false);
    }
  };

  const handleToggleCategory = async () => {
    if (!selectedCategory) {
      return;
    }

    setError('');
    setNotice('');
    setIsSavingCategory(true);
    try {
      await updatePartnerCategory(selectedCategory.id, { is_active: !selectedCategory.is_active });
      setNotice(selectedCategory.is_active ? '대분류를 비활성화했습니다.' : '대분류를 활성화했습니다.');
      categoriesResource.reload();
    } catch (requestError) {
      setError(partnerErrorMessage(requestError, '대분류 상태 변경에 실패했습니다.'));
    } finally {
      setIsSavingCategory(false);
    }
  };

  const handleDeleteCategory = async () => {
    if (!selectedCategory) {
      return;
    }
    if (!window.confirm(`'${selectedCategory.name}' 대분류를 삭제하고 매핑된 협력사를 미분류로 이동할까요?`)) {
      return;
    }

    setError('');
    setNotice('');
    setIsSavingCategory(true);
    try {
      await deletePartnerCategory(selectedCategory.id);
      if (categoryFilter === selectedCategory.id) {
        setCategoryFilter(UNCLASSIFIED_CATEGORY_FILTER);
      }
      setSelectedCategoryId('');
      setNotice('대분류를 삭제하고 매핑된 협력사를 미분류로 이동했습니다.');
      categoriesResource.reload();
      partnersResource.reload();
    } catch (requestError) {
      setError(partnerErrorMessage(requestError, '대분류 삭제에 실패했습니다.'));
    } finally {
      setIsSavingCategory(false);
    }
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    setError('');
    setNotice('');
    setIsCreating(true);
    try {
      const created = await createAdminPartner(toPartnerPayload(createForm, { includeLogin: true }));
      setCreateForm(defaultPartnerForm({ is_active: true, partner_category_id: created.partner_category_id || '' }));
      setSelectedId(created.id);
      setDetail(created);
      setForm(toPartnerForm(created));
      setCategoryFilter(created.partner_category_id || UNCLASSIFIED_CATEGORY_FILTER);
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
      setCategoryFilter(updated.partner_category_id || UNCLASSIFIED_CATEGORY_FILTER);
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
        <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <SectionHeader
            icon="list"
            title="협력사 대분류"
            right={(
              <button data-testid="partner-category-create" className="btn btn--ghost btn--sm" onClick={handleCreateCategory} disabled={isSavingCategory}>
                <Icon name="plus" size={12} /> 새 대분류
              </button>
            )}
          />
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 430px', gap: 0 }}>
            <div style={{ padding: 14, borderRight: '1px solid var(--divider)', display: 'flex', flexWrap: 'wrap', gap: 8, alignContent: 'flex-start' }}>
              <CategoryFilterButton
                testId="partner-category-filter-all"
                label="전체"
                count={partners.length}
                active={categoryFilter === ALL_CATEGORY_FILTER}
                onClick={() => handleCategoryFilter(ALL_CATEGORY_FILTER)}
              />
              <CategoryFilterButton
                testId="partner-category-filter-unclassified"
                label="미분류"
                count={countPartnersByCategory(partners, null)}
                active={categoryFilter === UNCLASSIFIED_CATEGORY_FILTER}
                onClick={() => handleCategoryFilter(UNCLASSIFIED_CATEGORY_FILTER)}
              />
              {categories.map((category) => (
                <CategoryFilterButton
                  key={category.id}
                  testId={`partner-category-filter-${category.id}`}
                  label={category.name}
                  count={countPartnersByCategory(partners, category.id)}
                  active={categoryFilter === category.id}
                  muted={category.is_active === false}
                  onClick={() => handleCategoryFilter(category.id)}
                />
              ))}
              {categoriesResource.isLoading && <span style={{ fontSize: 12, color: 'var(--text-tertiary)', alignSelf: 'center' }}>대분류를 불러오는 중입니다.</span>}
              {!categoriesResource.isLoading && categoriesResource.error && <span style={{ fontSize: 12, color: 'var(--danger-fg)', alignSelf: 'center' }}>대분류를 불러오지 못했습니다.</span>}
            </div>
            <form onSubmit={handleSaveCategory} style={{ padding: 14, display: 'grid', gridTemplateColumns: '1fr 80px auto', gap: 8, alignItems: 'end' }}>
              {selectedCategory ? (
                <>
                  <FormField testId="partner-category-name" label="대분류명" value={categoryForm.name} onChange={(value) => setCategoryForm({ ...categoryForm, name: value })} required />
                  <FormField testId="partner-category-sort-order" label="정렬" type="number" value={categoryForm.sort_order} onChange={(value) => setCategoryForm({ ...categoryForm, sort_order: value })} />
                  <button data-testid="partner-category-save" className="btn btn--primary btn--sm" disabled={isSavingCategory || !categoryForm.name.trim()}>
                    <Icon name="check" size={12} /> 저장
                  </button>
                  <div style={{ gridColumn: '1 / -1', display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 8, alignItems: 'end' }}>
                    <FormField testId="partner-category-description" label="설명" value={categoryForm.description} onChange={(value) => setCategoryForm({ ...categoryForm, description: value })} />
                    <button type="button" data-testid="partner-category-toggle" className="btn btn--secondary btn--sm" disabled={isSavingCategory} onClick={handleToggleCategory}>
                      <Icon name={selectedCategory.is_active ? 'x' : 'check'} size={12} />
                      {selectedCategory.is_active ? '비활성화' : '활성화'}
                    </button>
                    <button type="button" data-testid="partner-category-delete" className="btn btn--danger btn--sm" disabled={isSavingCategory} onClick={handleDeleteCategory}>
                      <Icon name="x" size={12} /> 삭제
                    </button>
                  </div>
                </>
              ) : (
                <div style={{ gridColumn: '1 / -1' }}>
                  <StateLine text="대분류를 만들거나 선택하세요. 매핑이 없는 협력사는 미분류로 조회됩니다." />
                </div>
              )}
            </form>
          </div>
        </section>

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
            {!partnersResource.isLoading && !partnersResource.error && partners.length > 0 && filteredPartners.length === 0 && <StateLine text="선택한 대분류에 협력사가 없습니다." />}

            {!partnersResource.isLoading && !partnersResource.error && filteredPartners.length > 0 && (
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
                    {pagedPartners.map((partner) => {
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
                            <div style={{ marginTop: 4 }}>
                              <Badge tone={partner.partner_category_id ? 'info' : 'neutral'}>{partner.partner_category_name || '미분류'}</Badge>
                            </div>
                            <div style={{ color: 'var(--text-tertiary)', marginTop: 2 }}>{partner.manager_name || '-'} · {formatPhone(partner.phone)}</div>
                          </Td>
                          <Td>
                            <span className="mono" style={{ color: 'var(--text-secondary)' }}>{partner.active_job_count}</span>
                            <span style={{ color: 'var(--text-tertiary)' }}> / {partner.scheduled_job_count}</span>
                          </Td>
                          <Td>
                            {partner.login_phone ? (
                              <span className="mono" style={{ color: partner.user_is_active ? 'var(--text-secondary)' : 'var(--text-tertiary)' }}>
                                {formatPhone(partner.login_phone)}
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
            {!partnersResource.isLoading && !partnersResource.error && filteredPartners.length > 0 && (
              <PaginationBar
                testId="partners-pagination"
                totalItems={filteredPartners.length}
                page={partnersPage}
                pageSize={partnersPageSize}
                onPageChange={setPartnersPage}
                onPageSizeChange={setPartnersPageSize}
                itemLabel="개"
              />
            )}
          </section>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <SectionHeader icon="plus" title="새 협력사 등록" />
              <form onSubmit={handleCreate} style={{ padding: 14, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
                <FormField testId="partner-create-name" label="협력사명" value={createForm.name} onChange={(value) => setCreateForm({ ...createForm, name: value })} required />
                <FormField label="담당자" value={createForm.manager_name} onChange={(value) => setCreateForm({ ...createForm, manager_name: value })} />
                <CategorySelect
                  testId="partner-create-category"
                  label="대분류"
                  categories={categories}
                  value={createForm.partner_category_id}
                  onChange={(value) => setCreateForm({ ...createForm, partner_category_id: value })}
                />
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
                      <CategorySelect
                        testId="partner-detail-category"
                        label="대분류"
                        categories={categories}
                        value={form.partner_category_id}
                        onChange={(value) => setForm({ ...form, partner_category_id: value })}
                      />
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
                      <div style={labelStyle}>대분류</div>
                      <KV label="분류" value={detail.partner_category_name || '미분류'} />
                    </div>

                    <div>
                      <div style={labelStyle}>계정</div>
                      <KV label="로그인" value={detail.login_phone ? formatPhone(detail.login_phone) : '미연결'} />
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

function CategorySelect({ label, categories, value, onChange, testId = undefined }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
      <span style={labelStyle}>{label}</span>
      <select
        className="input"
        data-testid={testId}
        value={value || ''}
        onChange={(event) => onChange(event.target.value)}
        style={{ height: 32, fontSize: 12 }}
      >
        <option value="">미분류</option>
        {categories.map((category) => (
          <option key={category.id} value={category.id}>
            {category.name}{category.is_active === false ? ' (비활성)' : ''}
          </option>
        ))}
      </select>
    </label>
  );
}

function CategoryFilterButton({ label, count, active, onClick, testId, muted = false }) {
  return (
    <button
      type="button"
      data-testid={testId}
      aria-pressed={active}
      onClick={onClick}
      style={{
        minHeight: 34,
        padding: '7px 10px',
        borderRadius: 6,
        border: active ? '1px solid var(--brand)' : '1px solid var(--border)',
        background: active ? 'var(--brand-bg)' : 'var(--surface)',
        color: muted ? 'var(--text-tertiary)' : 'var(--text)',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
        cursor: 'pointer',
        fontSize: 12,
        fontWeight: active ? 700 : 600,
      }}
    >
      <span>{label}</span>
      <span className="mono" style={{ color: active ? 'var(--brand)' : 'var(--text-tertiary)', fontWeight: 700 }}>{count}</span>
    </button>
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

function filterPartnersByCategory(partners, categoryFilter) {
  if (categoryFilter === ALL_CATEGORY_FILTER) {
    return partners;
  }
  if (categoryFilter === UNCLASSIFIED_CATEGORY_FILTER) {
    return partners.filter((partner) => !partner.partner_category_id);
  }
  return partners.filter((partner) => partner.partner_category_id === categoryFilter);
}

function countPartnersByCategory(partners, categoryId) {
  return partners.filter((partner) => (categoryId ? partner.partner_category_id === categoryId : !partner.partner_category_id)).length;
}

function defaultCategoryForm(overrides = {}) {
  return {
    name: '',
    description: '',
    sort_order: '0',
    ...overrides,
  };
}

function toCategoryForm(category) {
  return defaultCategoryForm({
    name: category.name || '',
    description: category.description || '',
    sort_order: String(category.sort_order || 0),
  });
}

function toCategoryPayload(form) {
  return {
    name: form.name.trim(),
    description: optionalText(form.description),
    sort_order: Number(form.sort_order || 0),
  };
}

function defaultPartnerForm(overrides = {}) {
  return {
    name: '',
    partner_category_id: '',
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
    partner_category_id: partner.partner_category_id || '',
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
    partner_category_id: form.partner_category_id || null,
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
    partner_category_not_found: '협력사 대분류를 찾을 수 없습니다.',
  };
  return messages[error?.message] || fallback;
}

function formatDate(value) {
  if (!value) {
    return '미정';
  }
  const date = parseDateValue(value);
  if (!date) {
    return value;
  }
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function formatDateTime(value) {
  return formatAppDateTime(value);
}

const labelStyle = {
  fontSize: 11,
  color: 'var(--text-tertiary)',
  fontWeight: 600,
};
