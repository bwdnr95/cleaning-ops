import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface Props {
  data: { period: string; revenue: number; completed_count: number }[];
}

export function RevenueChart({ data }: Props) {
  return (
    <div data-testid="reports-revenue-chart" style={{ width: '100%', height: 320 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="period" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(value) => Number(value).toLocaleString()} />
          <Tooltip formatter={(value) => Number(value).toLocaleString()} />
          <Line type="monotone" dataKey="revenue" stroke="var(--brand)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
