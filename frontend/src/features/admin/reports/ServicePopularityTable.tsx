import type { ServicePopularityRow } from '../../../api/reports';

interface Props {
  rows: ServicePopularityRow[];
}

export function ServicePopularityTable({ rows }: Props) {
  return (
    <table data-testid="service-popularity-table" className="table">
      <thead>
        <tr>
          <th>서비스</th>
          <th>작업 수</th>
          <th>매출</th>
          <th>매출 비중</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.service_item_id ?? row.service_name}>
            <td>{row.service_name}</td>
            <td>{row.job_count}</td>
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
