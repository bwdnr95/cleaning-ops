import React from 'react';

const STORAGE_KEY = 'cleaning_ops_draft_order_form_v1';
const TTL_MS = 30 * 60 * 1000;
const DEBOUNCE_MS = 1000;

const EXCLUDED_FORM_FIELDS = [
  'payment_memo',
  'evidence_memo',
] as const;
const EXCLUDED_LINE_FIELDS = [
  'total_amount',
  'deposit_amount',
  'balance_amount',
  'onsite_extra_amount',
  'partner_payment_amount',
  'partner_payment_status',
  'payment_memo',
  'evidence_memo',
] as const;

function sanitize<T extends Record<string, unknown>>(form: T): T {
  const cloned = { ...form } as Record<string, unknown>;
  for (const key of EXCLUDED_FORM_FIELDS) {
    if (key in cloned) delete cloned[key];
  }
  if (Array.isArray(cloned.lines)) {
    cloned.lines = (cloned.lines as Record<string, unknown>[]).map((line) => {
      const lineCopy = { ...line };
      for (const key of EXCLUDED_LINE_FIELDS) {
        if (key in lineCopy) delete lineCopy[key];
      }
      return lineCopy;
    });
  }
  return cloned as T;
}

function hasDraftSignal(form: Record<string, unknown>): boolean {
  if (typeof form.customer_name === 'string' && form.customer_name.trim()) {
    return true;
  }

  const firstLine = Array.isArray(form.lines) ? form.lines[0] : null;
  if (!firstLine || typeof firstLine !== 'object') {
    return false;
  }

  const ignoredLineKeys = new Set(['local_id', 'status', 'received_date']);
  return Object.entries(firstLine as Record<string, unknown>).some(([key, value]) => {
    if (ignoredLineKeys.has(key)) return false;
    if (typeof value === 'string') return value.trim() !== '';
    return value !== null && value !== undefined && value !== false;
  });
}

interface DraftEnvelope<T> {
  saved_at: number;
  payload: T;
}

export function useOrderFormDraft<T>(form: T, options: { enabled: boolean }) {
  const { enabled } = options;
  const timer = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => {
    if (!enabled) return;
    if (!hasDraftSignal(form as Record<string, unknown>)) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      try {
        const sanitized = sanitize(form as Record<string, unknown>) as T;
        const envelope: DraftEnvelope<T> = { saved_at: Date.now(), payload: sanitized };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(envelope));
      } catch {
        // localStorage quota exceeded. Drop the draft and keep the form usable.
      }
    }, DEBOUNCE_MS);

    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [form, enabled]);

  const loadDraft = React.useCallback((): T | null => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const envelope = JSON.parse(raw) as DraftEnvelope<T>;
      if (Date.now() - envelope.saved_at > TTL_MS) {
        localStorage.removeItem(STORAGE_KEY);
        return null;
      }
      return envelope.payload;
    } catch {
      return null;
    }
  }, []);

  const clearDraft = React.useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }, []);

  return React.useMemo(() => ({ loadDraft, clearDraft }), [clearDraft, loadDraft]);
}
