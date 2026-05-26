import type { PartnerPerformanceRow } from '../../../api/reports';

interface Props {
  rows: PartnerPerformanceRow[];
}

export function PartnerPerformanceTable({ rows }: Props) {
  return (
    <table data-testid="partner-performance-table" className="table">
      <thead>
        <tr>
          <th>협력사</th>
          <th>작업 수</th>
          <th>평균 단가</th>
          <th>정산 대기</th>
          <th>정산 예정액</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.partner_id}>
            <td>{row.partner_name}</td>
            <td>{row.job_count}</td>
            <td>{formatWon(row.avg_unit_price)}</td>
            <td>{row.pending_settlement_count}</td>
            <td>{formatWon(row.expected_settlement_amount)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function formatWon(value: string | number) {
  return `${Number(value || 0).toLocaleString()}원`;
}
