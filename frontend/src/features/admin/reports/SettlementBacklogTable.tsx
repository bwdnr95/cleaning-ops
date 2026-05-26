import type { SettlementBacklogRow } from '../../../api/reports';

interface Props {
  rows: SettlementBacklogRow[];
}

export function SettlementBacklogTable({ rows }: Props) {
  return (
    <table data-testid="settlement-backlog-table" className="table">
      <thead>
        <tr>
          <th>방문일</th>
          <th>서비스</th>
          <th>협력사</th>
          <th>매출</th>
          <th>정산 예정액</th>
          <th>상태</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.order_id}>
            <td>{row.scheduled_date ?? '-'}</td>
            <td>{row.service_name}</td>
            <td>{row.partner_name ?? '-'}</td>
            <td>{formatWon(row.total_amount)}</td>
            <td>{formatWon(row.expected_settlement_amount)}</td>
            <td>{row.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function formatWon(value: string | number) {
  return `${Number(value || 0).toLocaleString()}원`;
}
