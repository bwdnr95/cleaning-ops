import type { ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

export function ReportToolbarEnd({ children }: Props) {
  return <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>{children}</div>;
}
