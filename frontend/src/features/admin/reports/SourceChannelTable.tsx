import type { SourceChannelRow } from '../../../api/reports';
import { sourceChannelLabel } from '../../../domain/sourceChannel';

interface Props {
  rows: SourceChannelRow[];
}

export function SourceChannelTable({ rows }: Props) {
  return (
    <table data-testid="source-channel-table" className="table">
      <thead>
        <tr>
          <th>유입경로</th>
          <th>주문 수</th>
          <th>완료 수</th>
          <th>매출</th>
          <th>매출 비중</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.source_channel}>
            <td>{sourceChannelLabel(row.source_channel)}</td>
            <td>{row.order_count}</td>
            <td>{row.completed_count}</td>
            <td>{formatWon(row.revenue)}</td>
            <td>{row.revenue_share_pct.toFixed(1)}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function formatWon(value: string | number) {
  return `${Number(value || 0).toLocaleString()}원`;
}
