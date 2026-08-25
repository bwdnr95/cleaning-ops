import React from 'react';

import type { AdminOrder } from '../../../api/admin';
import {
  getAdminOrder,
  listBrokers,
  listPartners,
  listServiceCatalog,
  sendOrderAsRequest,
} from '../../../api/admin';
import { useApiResource } from '../../../api/useApiResource';
import { createEmptyGroupForm, toDuplicateForm, toForm } from './OrderFormModel';
import {
  orderSaveErrorMessage,
  persistOrderForm,
  validateOrderForm,
} from './OrderFormPersistence';
import { FormState } from './OrderFormPrimitives';
import {
  addOrderLine,
  enforceAmountLock,
  hasPartnerPriceWarning,
  removeOrderLine,
  updateGroupField,
  updateLineField,
  updateMoneyField,
  updatePartner,
  updateReceiptType,
  updateServiceCategory,
  updateServiceItem,
  updateVisitDates,
} from './OrderFormState';
import {
  NO_AMOUNT_LOCK,
  type OrderFormAmountLock,
  type OrderFormGroupFieldChange,
  type OrderFormLineFieldChange,
  type OrderGroupForm,
  type OrderMoneyField,
} from './OrderFormTypes';
import {
  OrderFormView,
  type OrderFormMode,
  type OrderFormViewActions,
} from './OrderFormView';
import { useOrderFormDraft } from './useOrderFormDraft';

interface OrderFormPageProps {
  readonly mode?: OrderFormMode;
  readonly orderId?: string | null;
  readonly duplicateFromOrderId?: string | null;
  readonly onCancel?: () => void;
  readonly onSaved?: (order: AdminOrder) => void;
}

export function OrderFormPage({
  mode = 'create',
  orderId = null,
  duplicateFromOrderId = null,
  onCancel,
  onSaved,
}: OrderFormPageProps) {
  const isDuplicate = mode === 'create' && Boolean(duplicateFromOrderId);
  const partners = useApiResource(listPartners);
  const brokers = useApiResource(listBrokers);
  const serviceCatalog = useApiResource(listServiceCatalog);
  const [form, setForm] = React.useState<OrderGroupForm>(() => createEmptyGroupForm());
  const [isLoadingOrder, setIsLoadingOrder] = React.useState(mode === 'edit' || isDuplicate);
  const [isSaving, setIsSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState('');
  const [asOpen, setAsOpen] = React.useState(false);
  const [asMemo, setAsMemo] = React.useState('');
  const [asRequested, setAsRequested] = React.useState(false);
  const [asBusy, setAsBusy] = React.useState(false);
  const initialFormRef = React.useRef<OrderGroupForm | null>(null);
  const [amountLock, setAmountLock] = React.useState<OrderFormAmountLock>(NO_AMOUNT_LOCK);
  const amountLockRef = React.useRef<OrderFormAmountLock>(NO_AMOUNT_LOCK);
  const draft = useOrderFormDraft(form, { enabled: mode === 'create' && !isDuplicate });
  // 잠긴 금액 필드는 어떤 편집 경로로도 바뀌지 않게 상태 갱신마다 원본 값으로 되돌린다.
  const applyFormUpdate = React.useCallback(
    (updater: (current: OrderGroupForm) => OrderGroupForm) => {
      setForm((current) => enforceAmountLock(
        updater(current),
        amountLockRef.current,
        initialFormRef.current?.lines[0] || null,
      ));
    },
    [],
  );
  const activeServiceCategories = React.useMemo(
    () => (serviceCatalog.data || []).filter((category) => category.is_active),
    [serviceCatalog.data],
  );

  React.useEffect(() => {
    let isCurrent = true;
    const loadId = mode === 'edit' ? orderId : (isDuplicate ? duplicateFromOrderId : null);
    if (!loadId) {
      setForm(createEmptyGroupForm());
      initialFormRef.current = null;
      amountLockRef.current = NO_AMOUNT_LOCK;
      setAmountLock(NO_AMOUNT_LOCK);
      setIsLoadingOrder(false);
      return () => { isCurrent = false; };
    }

    setIsLoadingOrder(true);
    getAdminOrder(loadId)
      .then((order) => {
        if (!isCurrent) return;
        const loadedForm = isDuplicate ? toDuplicateForm(order) : toForm(order);
        setForm(loadedForm);
        initialFormRef.current = isDuplicate ? null : loadedForm;
        // 복제는 새 주문이라 계약 청구방식과 무관하다. 수정일 때만 금액을 잠근다.
        const nextLock: OrderFormAmountLock = isDuplicate ? NO_AMOUNT_LOCK : {
          customerAmount: order.recurring_billing_mode === 'monthly',
          partnerAmount: order.recurring_partner_billing_mode === 'monthly',
        };
        amountLockRef.current = nextLock;
        setAmountLock(nextLock);
        if (!isDuplicate) {
          setAsRequested(Boolean(order.as_requested));
          setAsMemo(order.as_memo || '');
          setAsOpen(Boolean(order.as_requested));
        }
      })
      .catch(() => {
        if (isCurrent) setError('주문 정보를 불러오지 못했습니다.');
      })
      .finally(() => {
        if (isCurrent) setIsLoadingOrder(false);
      });
    return () => { isCurrent = false; };
  }, [mode, orderId, isDuplicate, duplicateFromOrderId]);

  React.useEffect(() => {
    if (mode !== 'create' || isDuplicate) return;
    const restored = draft.loadDraft();
    if (!restored) return;
    if (form.customer_name === '' && form.customer_phone === '' && form.lines.every((line) => !line.scheduled_date)) {
      if (window.confirm('이전 작성 중이던 신규 주문 임시 저장 데이터가 있습니다. 불러올까요?')) {
        setForm(restored);
      } else {
        draft.clearDraft();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const handleCancel = React.useCallback(() => {
    draft.clearDraft();
    onCancel?.();
  }, [draft, onCancel]);

  const setGroupField = React.useCallback<OrderFormGroupFieldChange>((key, value) => {
    applyFormUpdate((current) => updateGroupField(current, key, value));
  }, [applyFormUpdate]);

  const setLineField = React.useCallback<OrderFormLineFieldChange>((lineIndex, key, value) => {
    applyFormUpdate((current) => updateLineField(current, lineIndex, key, value));
  }, [applyFormUpdate]);

  const handleMoneyChange = React.useCallback((lineIndex: number, key: OrderMoneyField, value: string) => {
    applyFormUpdate((current) => updateMoneyField(current, lineIndex, key, value));
  }, [applyFormUpdate]);

  const handleVisitDatesChange = React.useCallback((lineIndex: number, value: readonly string[]) => {
    applyFormUpdate((current) => updateVisitDates(current, lineIndex, value));
  }, [applyFormUpdate]);

  const handlePartnerChange = React.useCallback((lineIndex: number, partnerId: string) => {
    applyFormUpdate((current) => updatePartner(current, lineIndex, partnerId, partners.data || []));
  }, [applyFormUpdate, partners.data]);

  const handleServiceCategoryChange = React.useCallback((lineIndex: number, categoryId: string) => {
    applyFormUpdate((current) => updateServiceCategory(current, lineIndex, categoryId));
  }, [applyFormUpdate]);

  const handleServiceItemChange = React.useCallback((lineIndex: number, serviceItemId: string) => {
    applyFormUpdate((current) => updateServiceItem(current, lineIndex, serviceItemId, activeServiceCategories));
  }, [applyFormUpdate, activeServiceCategories]);

  const handleReceiptTypeChange = React.useCallback((lineIndex: number, receiptType: string) => {
    applyFormUpdate((current) => updateReceiptType(current, lineIndex, receiptType));
  }, [applyFormUpdate]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setNotice('');
    const validationError = validateOrderForm(form);
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsSaving(true);
    try {
      const saved = await persistOrderForm({
        mode,
        orderId,
        form,
        initialForm: initialFormRef.current,
        amountLock,
      });
      draft.clearDraft();
      onSaved?.(saved);
    } catch (requestError) {
      setError(orderSaveErrorMessage(requestError));
    } finally {
      setIsSaving(false);
    }
  };

  const handleSendAs = async () => {
    if (mode !== 'edit' || !orderId) return;
    if (asRequested) {
      setError('이미 협력사에 전달된 AS 요청입니다.');
      return;
    }
    const memo = asMemo.trim();
    if (!memo) {
      setError('AS 요청 내용을 입력해주세요.');
      return;
    }

    setAsBusy(true);
    setError(null);
    setNotice('');
    try {
      const updated = await sendOrderAsRequest(orderId, memo);
      setAsRequested(Boolean(updated.as_requested));
      setAsMemo(updated.as_memo || memo);
      setNotice('AS 요청을 등록했습니다. 수신자별 발송 결과는 메시지 로그에서 확인할 수 있습니다.');
    } catch (requestError) {
      const message = requestError instanceof Error && requestError.message
        ? requestError.message
        : 'AS 요청 전송에 실패했습니다.';
      setError(message === 'partner_not_found' || message === 'partner_inactive'
        ? '배정된 협력사가 보관 또는 비활성 상태여서 AS 요청을 전달할 수 없습니다. 활성 협력사를 다시 배정해주세요.'
        : message);
    } finally {
      setAsBusy(false);
    }
  };

  if (isLoadingOrder) {
    return <FormState text="주문 입력 정보를 불러오는 중입니다." onCancel={handleCancel} />;
  }

  const actions: OrderFormViewActions = {
    onCancel: handleCancel,
    onSubmit: handleSubmit,
    onGroupFieldChange: setGroupField,
    onLineFieldChange: setLineField,
    onVisitDatesChange: handleVisitDatesChange,
    onMoneyChange: handleMoneyChange,
    onPartnerChange: handlePartnerChange,
    onServiceCategoryChange: handleServiceCategoryChange,
    onServiceItemChange: handleServiceItemChange,
    onReceiptTypeChange: handleReceiptTypeChange,
    onAddLine: () => setForm(addOrderLine),
    onRemoveLine: (lineIndex) => setForm((current) => removeOrderLine(current, lineIndex)),
    onAsToggle: setAsOpen,
    onAsMemoChange: setAsMemo,
    onSendAs: handleSendAs,
  };

  return (
    <OrderFormView
      mode={mode}
      isDuplicate={isDuplicate}
      isSaving={isSaving}
      form={form}
      feedback={{ error, notice, hasPartnerPriceWarning: hasPartnerPriceWarning(form) }}
      asState={{ isOpen: asOpen, memo: asMemo, isRequested: asRequested, isBusy: asBusy }}
      resources={{ serviceCategories: activeServiceCategories, partners: partners.data || [], brokers: brokers.data || [] }}
      actions={actions}
      amountLock={amountLock}
    />
  );
}
