import * as Sentry from '@sentry/react';

type SentryEnv = {
  VITE_SENTRY_DSN?: string;
  VITE_SENTRY_ENVIRONMENT?: string;
  VITE_SENTRY_RELEASE?: string;
  VITE_SENTRY_TRACES_SAMPLE_RATE?: string;
  VITE_SENTRY_REPLAYS_SAMPLE_RATE?: string;
  MODE?: string;
};

export function initSentry(): void {
  const env = import.meta.env as unknown as SentryEnv;
  const dsn = env.VITE_SENTRY_DSN?.trim();
  if (!dsn) {
    return;
  }

  Sentry.init({
    dsn,
    environment: env.VITE_SENTRY_ENVIRONMENT?.trim() || env.MODE || 'production',
    release: env.VITE_SENTRY_RELEASE?.trim() || undefined,
    tracesSampleRate: parseRate(env.VITE_SENTRY_TRACES_SAMPLE_RATE, 0.1),
    replaysSessionSampleRate: parseRate(env.VITE_SENTRY_REPLAYS_SAMPLE_RATE, 0),
    replaysOnErrorSampleRate: 1.0,
    integrations: [Sentry.browserTracingIntegration()],
  });
}

function parseRate(value: string | undefined, fallback: number): number {
  if (!value) return fallback;
  const n = Number(value);
  if (Number.isFinite(n) && n >= 0 && n <= 1) {
    return n;
  }
  return fallback;
}
