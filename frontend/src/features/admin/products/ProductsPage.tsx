import React from 'react';

import {
  createServiceCategory,
  createServiceItem,
  deleteServiceCategory,
  deleteServiceItem,
  listServiceCatalog,
  updateServiceCategory,
  updateServiceItem,
} from '../../../api/admin';
import { PaginationBar, paginateItems } from '../../../components/common/Pagination';
import { useApiResource } from '../../../api/useApiResource';
import { Badge, Icon } from '../../../components/common/ui';

const SERVICE_UNITS = ['평', '건', '대', '세트', '칸', '기타'];

export function ProductsPage() {
  const loadCatalog = React.useCallback(() => listServiceCatalog({ includeInactive: true }), []);
  const catalogResource = useApiResource(loadCatalog);
  const categories = React.useMemo(() => catalogResource.data || [], [catalogResource.data]);
  const [selectedCategoryId, setSelectedCategoryId] = React.useState('');
  const [selectedItemId, setSelectedItemId] = React.useState('');
  const [categoryPage, setCategoryPage] = React.useState(1);
  const [categoryPageSize, setCategoryPageSize] = React.useState(10);
  const [itemPage, setItemPage] = React.useState(1);
  const [itemPageSize, setItemPageSize] = React.useState(10);
  const [categoryForm, setCategoryForm] = React.useState(defaultCategoryForm());
  const [itemForm, setItemForm] = React.useState(defaultItemForm());
  const [isSaving, setIsSaving] = React.useState(false);
  const [notice, setNotice] = React.useState('');
  const [error, setError] = React.useState('');

  const selectedCategory = categories.find((category) => category.id === selectedCategoryId) || categories[0] || null;
  const items = React.useMemo(() => selectedCategory?.items || [], [selectedCategory]);
  const pagedCategories = React.useMemo(
    () => paginateItems(categories, categoryPage, categoryPageSize),
    [categories, categoryPage, categoryPageSize],
  );
  const pagedItems = React.useMemo(
    () => paginateItems(items, itemPage, itemPageSize),
    [items, itemPage, itemPageSize],
  );
  const selectedItem = items.find((item) => item.id === selectedItemId) || null;
  const stats = toCatalogStats(categories);

  React.useEffect(() => {
    if (!selectedCategory && categories.length > 0) {
      setSelectedCategoryId(categories[0].id);
    }
  }, [categories, selectedCategory]);

  React.useEffect(() => {
    if (!selectedCategory) {
      return;
    }
    setCategoryForm(toCategoryForm(selectedCategory));
    setItemForm((current) => ({ ...current, category_id: selectedCategory.id }));
    setItemPage(1);
    if (selectedItemId && !selectedCategory.items.some((item) => item.id === selectedItemId)) {
      setSelectedItemId('');
    }
  }, [selectedCategory, selectedItemId]);

  React.useEffect(() => {
    if (selectedItem) {
      setItemForm(toItemForm(selectedItem));
    } else if (selectedCategory) {
      setItemForm(defaultItemForm({ category_id: selectedCategory.id }));
    }
  }, [selectedCategory, selectedItem]);

  const saveCategory = async (event) => {
    event.preventDefault();
    setIsSaving(true);
    setNotice('');
    setError('');
    try {
      if (selectedCategory) {
        const updated = await updateServiceCategory(selectedCategory.id, toCategoryPayload(categoryForm));
        setSelectedCategoryId(updated.id);
        setNotice('카테고리를 저장했습니다.');
      } else {
        const created = await createServiceCategory(toCategoryPayload(categoryForm));
        setSelectedCategoryId(created.id);
        setNotice('카테고리를 등록했습니다.');
      }
      catalogResource.reload();
    } catch (requestError) {
      setError(catalogErrorMessage(requestError, '카테고리 저장에 실패했습니다.'));
    } finally {
      setIsSaving(false);
    }
  };

  const createCategory = async () => {
    setIsSaving(true);
    setNotice('');
    setError('');
    try {
      const created = await createServiceCategory({
        name: '새 카테고리',
        description: null,
        is_active: true,
        sort_order: categories.length * 10 + 10,
      });
      setSelectedCategoryId(created.id);
      setSelectedItemId('');
      setNotice('새 카테고리를 등록했습니다.');
      catalogResource.reload();
    } catch (requestError) {
      setError(catalogErrorMessage(requestError, '카테고리 등록에 실패했습니다.'));
    } finally {
      setIsSaving(false);
    }
  };

  const toggleCategory = async () => {
    if (!selectedCategory) {
      return;
    }
    setIsSaving(true);
    setNotice('');
    setError('');
    try {
      await updateServiceCategory(selectedCategory.id, { is_active: !selectedCategory.is_active });
      setNotice(selectedCategory.is_active ? '카테고리를 비활성화했습니다.' : '카테고리를 활성화했습니다.');
      catalogResource.reload();
    } catch (requestError) {
      setError(catalogErrorMessage(requestError, '카테고리 상태 변경에 실패했습니다.'));
    } finally {
      setIsSaving(false);
    }
  };

  const deleteCategory = async () => {
    if (!selectedCategory) {
      return;
    }
    if (!window.confirm(`'${selectedCategory.name}' 카테고리를 삭제할까요?`)) {
      return;
    }

    setIsSaving(true);
    setNotice('');
    setError('');
    try {
      await deleteServiceCategory(selectedCategory.id);
      setSelectedCategoryId('');
      setSelectedItemId('');
      setNotice('카테고리를 삭제했습니다.');
      catalogResource.reload();
    } catch (requestError) {
      setError(catalogErrorMessage(requestError, '카테고리 삭제에 실패했습니다.'));
    } finally {
      setIsSaving(false);
    }
  };

  const saveItem = async (event) => {
    event.preventDefault();
    setIsSaving(true);
    setNotice('');
    setError('');
    try {
      if (selectedItem) {
        const updated = await updateServiceItem(selectedItem.id, toItemPayload(itemForm));
        setSelectedItemId(updated.id);
        setNotice('상품을 저장했습니다.');
      } else {
        const created = await createServiceItem(toItemPayload(itemForm));
        setSelectedItemId(created.id);
        setNotice('상품을 등록했습니다.');
      }
      catalogResource.reload();
    } catch (requestError) {
      setError(catalogErrorMessage(requestError, '상품 저장에 실패했습니다.'));
    } finally {
      setIsSaving(false);
    }
  };

  const toggleItem = async (item) => {
    setIsSaving(true);
    setNotice('');
    setError('');
    try {
      await updateServiceItem(item.id, { is_active: !item.is_active });
      setNotice(item.is_active ? '상품을 비활성화했습니다.' : '상품을 활성화했습니다.');
      catalogResource.reload();
    } catch (requestError) {
      setError(catalogErrorMessage(requestError, '상품 상태 변경에 실패했습니다.'));
    } finally {
      setIsSaving(false);
    }
  };

  const deleteItem = async (item) => {
    if (!window.confirm(`'${item.name}' 상품을 삭제할까요?`)) {
      return;
    }

    setIsSaving(true);
    setNotice('');
    setError('');
    try {
      await deleteServiceItem(item.id);
      if (selectedItemId === item.id) {
        setSelectedItemId('');
      }
      setNotice('상품을 삭제했습니다.');
      catalogResource.reload();
    } catch (requestError) {
      setError(catalogErrorMessage(requestError, '상품 삭제에 실패했습니다.'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div data-testid="admin-products-page" style={{ flex: 1, minHeight: 0, overflow: 'auto', background: 'var(--bg)' }}>
      <div className="page-shell" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
          <StatCard label="카테고리" value={categories.length} icon="package" />
          <StatCard label="활성 상품" value={stats.activeItems} icon="check" tone="success" />
          <StatCard label="비활성 상품" value={stats.inactiveItems} icon="lock" tone="neutral" />
          <StatCard label="평균 기준가" value={formatWon(stats.averagePrice)} icon="creditCard" tone="info" />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '300px minmax(0, 1fr)', gap: 12, alignItems: 'start' }}>
          <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <SectionHeader
              icon="package"
              title="카테고리"
              right={(
                <button data-testid="products-create-category" className="btn btn--ghost btn--sm" onClick={createCategory} disabled={isSaving}>
                  <Icon name="plus" size={12} />
                </button>
              )}
            />
            {catalogResource.isLoading && <StateLine text="상품 기준 데이터를 불러오는 중입니다." />}
            {!catalogResource.isLoading && catalogResource.error && <StateLine text="상품 기준 데이터를 불러오지 못했습니다." tone="danger" />}
            {!catalogResource.isLoading && !catalogResource.error && categories.length === 0 && <StateLine text="등록된 카테고리가 없습니다." />}
            <div className="scroll" style={{ maxHeight: 430, overflow: 'auto' }}>
              {pagedCategories.map((category) => {
                const isSelected = selectedCategory?.id === category.id;
                return (
                  <button
                    key={category.id}
                    type="button"
                    onClick={() => {
                      setSelectedCategoryId(category.id);
                      setSelectedItemId('');
                    }}
                    style={{
                      display: 'block',
                      width: '100%',
                      padding: '10px 12px',
                      border: 'none',
                      borderTop: '1px solid var(--divider)',
                      borderLeft: isSelected ? '2px solid var(--brand)' : '2px solid transparent',
                      background: isSelected ? 'var(--brand-bg)' : 'transparent',
                      textAlign: 'left',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ flex: 1, fontSize: 12.5, fontWeight: 600 }}>{category.name}</span>
                      <Badge tone={category.is_active ? 'success' : 'neutral'}>{category.is_active ? '활성' : '비활성'}</Badge>
                    </div>
                    <div style={{ marginTop: 4, color: 'var(--text-tertiary)', fontSize: 11.5 }}>
                      상품 {category.items.length}개 · 정렬 {category.sort_order}
                    </div>
                  </button>
                );
              })}
            </div>
            {!catalogResource.isLoading && !catalogResource.error && categories.length > 0 && (
              <PaginationBar
                testId="products-categories-pagination"
                totalItems={categories.length}
                page={categoryPage}
                pageSize={categoryPageSize}
                onPageChange={setCategoryPage}
                onPageSizeChange={setCategoryPageSize}
                itemLabel="개"
              />
            )}
          </section>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <SectionHeader
                icon="settings"
                title={selectedCategory ? '카테고리 설정' : '카테고리 설정'}
                right={selectedCategory && (
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button type="button" className="btn btn--secondary btn--sm" onClick={toggleCategory} disabled={isSaving}>
                      <Icon name={selectedCategory.is_active ? 'x' : 'check'} size={12} />
                      {selectedCategory.is_active ? '비활성화' : '활성화'}
                    </button>
                    <button
                      type="button"
                      className="btn btn--danger btn--sm"
                      onClick={deleteCategory}
                      disabled={isSaving || selectedCategory.items.length > 0}
                      title={selectedCategory.items.length > 0 ? '상품이 없는 카테고리만 삭제할 수 있습니다.' : '카테고리 삭제'}
                    >
                      <Icon name="x" size={12} /> 삭제
                    </button>
                  </div>
                )}
              />
              {selectedCategory ? (
                <form onSubmit={saveCategory} style={{ padding: 14, display: 'grid', gridTemplateColumns: '1fr 1fr 100px auto', gap: 10, alignItems: 'end' }}>
                  <FormField testId="products-category-name" label="카테고리명" value={categoryForm.name} onChange={(value) => setCategoryForm({ ...categoryForm, name: value })} required />
                  <FormField testId="products-category-description" label="설명" value={categoryForm.description} onChange={(value) => setCategoryForm({ ...categoryForm, description: value })} />
                  <FormField testId="products-category-sort-order" label="정렬" type="number" value={categoryForm.sort_order} onChange={(value) => setCategoryForm({ ...categoryForm, sort_order: value })} />
                  <button data-testid="products-save-category" className="btn btn--primary btn--sm" disabled={isSaving}>
                    <Icon name="check" size={12} /> 저장
                  </button>
                </form>
              ) : (
                <StateLine text="카테고리를 선택하거나 새로 등록하세요." />
              )}
            </section>

            <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <SectionHeader
                icon="list"
                title="상품"
                right={selectedCategory && (
                  <button type="button" className="btn btn--ghost btn--sm" onClick={() => setSelectedItemId('')}>
                    <Icon name="plus" size={12} /> 새 상품
                  </button>
                )}
              />
              {selectedCategory && items.length === 0 && <StateLine text="등록된 상품이 없습니다." />}
              {selectedCategory && items.length > 0 && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 72px 110px 110px 80px 172px', fontSize: 12, overflowX: 'auto' }}>
                  {['상품명', '단위', '기준가', '도급가(VAT 포함)', '상태', '관리'].map((header) => <GridHead key={header}>{header}</GridHead>)}
                  {pagedItems.map((item) => (
                    <React.Fragment key={item.id}>
                      <GridCell>
                        <button type="button" onClick={() => setSelectedItemId(item.id)} style={linkButtonStyle}>
                          {item.name}
                        </button>
                      </GridCell>
                      <GridCell>{item.unit}</GridCell>
                      <GridCell mono>{formatWon(item.base_price)}</GridCell>
                      <GridCell mono>{formatWon(item.partner_base_price)}</GridCell>
                      <GridCell>
                        <Badge tone={item.is_active ? 'success' : 'neutral'} dot>{item.is_active ? '활성' : '비활성'}</Badge>
                      </GridCell>
                      <GridCell>
                        <div style={{ display: 'flex', gap: 4 }}>
                          <button
                            type="button"
                            className="btn btn--secondary btn--sm"
                            aria-label={`${item.name} 수정`}
                            onClick={() => setSelectedItemId(item.id)}
                          >
                            수정
                          </button>
                          <button type="button" className="btn btn--ghost btn--sm" disabled={isSaving} onClick={() => toggleItem(item)}>
                            {item.is_active ? '끄기' : '켜기'}
                          </button>
                          <button
                            type="button"
                            className="btn btn--danger btn--sm"
                            aria-label={`${item.name} 삭제`}
                            disabled={isSaving}
                            onClick={() => deleteItem(item)}
                            style={{ padding: '0 7px' }}
                          >
                            삭제
                          </button>
                        </div>
                      </GridCell>
                    </React.Fragment>
                  ))}
                </div>
              )}
              {selectedCategory && items.length > 0 && (
                <PaginationBar
                  testId="products-items-pagination"
                  totalItems={items.length}
                  page={itemPage}
                  pageSize={itemPageSize}
                  onPageChange={setItemPage}
                  onPageSizeChange={setItemPageSize}
                  itemLabel="개"
                />
              )}
            </section>

            {selectedCategory && (
              <section className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <SectionHeader icon={selectedItem ? 'settings' : 'plus'} title={selectedItem ? `상품 수정 · ${selectedItem.name}` : '새 상품 등록'} />
                <form onSubmit={saveItem} style={{ padding: 14, display: 'grid', gridTemplateColumns: '1fr 92px 140px 140px 90px auto', gap: 10, alignItems: 'end' }}>
                  <FormField testId="products-item-name" label="상품명" value={itemForm.name} onChange={(value) => setItemForm({ ...itemForm, name: value })} required />
                  <label style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
                    <span style={labelStyle}>단위</span>
                    <select className="input" data-testid="products-item-unit" value={itemForm.unit} onChange={(event) => setItemForm({ ...itemForm, unit: event.target.value })}>
                      {SERVICE_UNITS.map((unit) => <option key={unit} value={unit}>{unit}</option>)}
                    </select>
                  </label>
                  <FormField testId="products-item-base-price" label="기준가" type="number" value={itemForm.base_price} onChange={(value) => setItemForm({ ...itemForm, base_price: value })} />
                  <FormField testId="products-item-partner-base-price" label="도급가 (VAT 포함)" type="number" value={itemForm.partner_base_price} onChange={(value) => setItemForm({ ...itemForm, partner_base_price: value })} />
                  <FormField testId="products-item-sort-order" label="정렬" type="number" value={itemForm.sort_order} onChange={(value) => setItemForm({ ...itemForm, sort_order: value })} />
                  <button data-testid="products-save-item" className="btn btn--primary btn--sm" disabled={isSaving || !itemForm.name.trim()}>
                    <Icon name="check" size={12} /> 저장
                  </button>
                  <div style={{ gridColumn: '1 / -1' }}>
                    <FormField testId="products-item-description" label="설명" value={itemForm.description} onChange={(value) => setItemForm({ ...itemForm, description: value })} />
                  </div>
                </form>
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

function FormField({ label, value, onChange, type = 'text', required = false, testId = undefined }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
      <span style={labelStyle}>{label}</span>
      <input
        className="input"
        data-testid={testId}
        type={type}
        value={value || ''}
        required={required}
        onChange={(event) => onChange(event.target.value)}
        style={{ height: 32, fontSize: 12 }}
      />
    </label>
  );
}

function GridHead({ children }) {
  return (
    <div style={{
      padding: '9px 12px',
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
      minHeight: 44,
      padding: '9px 12px',
      borderBottom: '1px solid var(--divider)',
      display: 'flex',
      alignItems: 'center',
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

function toCatalogStats(categories) {
  const items = categories.flatMap((category) => category.items || []);
  const activeItems = items.filter((item) => item.is_active).length;
  const inactiveItems = items.length - activeItems;
  const averagePrice = activeItems
    ? items.filter((item) => item.is_active).reduce((sum, item) => sum + Number(item.base_price || 0), 0) / activeItems
    : 0;
  return { activeItems, inactiveItems, averagePrice };
}

function defaultCategoryForm(overrides = {}) {
  return {
    name: '',
    description: '',
    sort_order: '0',
    ...overrides,
  };
}

function defaultItemForm(overrides = {}) {
  return {
    category_id: '',
    name: '',
    unit: '건',
    base_price: '0',
    partner_base_price: '0',
    description: '',
    sort_order: '0',
    is_active: true,
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

function toItemForm(item) {
  return defaultItemForm({
    category_id: item.category_id,
    name: item.name || '',
    unit: item.unit || '건',
    base_price: String(item.base_price || 0),
    partner_base_price: String(item.partner_base_price || 0),
    description: item.description || '',
    sort_order: String(item.sort_order || 0),
    is_active: item.is_active !== false,
  });
}

function toCategoryPayload(form) {
  return {
    name: form.name.trim(),
    description: emptyToNull(form.description),
    sort_order: Number(form.sort_order || 0),
  };
}

function toItemPayload(form) {
  return {
    category_id: form.category_id,
    name: form.name.trim(),
    unit: form.unit,
    base_price: Number(form.base_price || 0),
    partner_base_price: Number(form.partner_base_price || 0),
    description: emptyToNull(form.description),
    sort_order: Number(form.sort_order || 0),
    is_active: form.is_active !== false,
  };
}

function emptyToNull(value) {
  const text = String(value || '').trim();
  return text ? text : null;
}

function catalogErrorMessage(error, fallback) {
  const messages = {
    service_category_not_found: '카테고리를 찾을 수 없습니다.',
    service_category_not_available: '비활성 카테고리에는 활성 상품을 등록할 수 없습니다.',
    service_category_has_items: '상품이 남아 있는 카테고리는 삭제할 수 없습니다.',
    service_category_in_use: '이미 주문에 사용된 카테고리는 삭제할 수 없습니다. 비활성화를 사용해주세요.',
    service_item_not_found: '상품을 찾을 수 없습니다.',
    service_item_not_available: '비활성 상품은 주문에 사용할 수 없습니다.',
    service_item_in_use: '이미 주문에 사용된 상품은 삭제할 수 없습니다. 비활성화를 사용해주세요.',
  };
  return messages[error?.message] || fallback;
}

function formatWon(value) {
  const amount = Number(value || 0);
  return `₩${Math.round(amount).toLocaleString()}`;
}

const labelStyle = {
  fontSize: 11,
  color: 'var(--text-tertiary)',
  fontWeight: 600,
};

const linkButtonStyle = {
  border: 'none',
  background: 'transparent',
  padding: 0,
  color: 'var(--text)',
  font: 'inherit',
  fontWeight: 600,
  cursor: 'pointer',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};
