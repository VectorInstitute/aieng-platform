import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import type { DailyEngagement } from '@/lib/types';

interface EngagementChartProps {
  data: DailyEngagement[];
}

interface ChartDataPoint {
  date: string;
  users: number;
}

function formatChartData(engagement: DailyEngagement[]): ChartDataPoint[] {
  return engagement.map(item => ({
    date: new Date(item.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    users: item.unique_users,
  }));
}

function calculateYAxisDomain(data: ChartDataPoint[]): [number, number] {
  if (data.length === 0) return [0, 10];

  const maxValue = Math.max(...data.map(d => d.users));

  // Add 20% padding to max value
  const paddedMax = Math.ceil(maxValue * 1.2);

  // Round up to nearest 5, 10, or nice number
  const roundToNice = (num: number): number => {
    if (num <= 10) return 10;
    if (num <= 20) return 20;
    if (num <= 50) return Math.ceil(num / 5) * 5;
    if (num <= 100) return Math.ceil(num / 10) * 10;
    return Math.ceil(num / 20) * 20;
  };

  return [0, roundToNice(paddedMax)];
}

function shouldShowXAxisLabel(index: number, totalPoints: number): boolean {
  // Show labels intelligently based on data density
  if (totalPoints <= 30) return index % 3 === 0; // Every 3rd day
  if (totalPoints <= 45) return index % 5 === 0; // Every 5th day
  return index % 7 === 0; // Every 7th day (weekly)
}

export function EngagementChart({ data }: EngagementChartProps) {
  const chartData = formatChartData(data);
  const yAxisDomain = calculateYAxisDomain(chartData);

  return (
    <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl border-2 border-slate-200 dark:border-slate-700 p-6">
      <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">User Engagement</h2>
      <details className="mb-4" open>
        <summary className="text-sm text-slate-600 dark:text-slate-400 cursor-pointer hover:text-slate-900 dark:hover:text-white transition-colors">
          How we calculate engaged users
        </summary>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400 pl-4">
          A user is considered &quot;engaged&quot; if they initiate a connection to their workspace via apps, web terminal, or SSH.
          The graph displays the daily count of unique users who engaged at least once.
        </p>
      </details>

      <div className="h-80 mt-6">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="colorUsers" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.8}/>
                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.1}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
            <XAxis
              dataKey="date"
              stroke="#64748b"
              style={{ fontSize: '11px' }}
              tickLine={false}
              interval="preserveStartEnd"
              tick={(props) => {
                const { x, y, payload, index } = props;
                if (index === 0 || index === chartData.length - 1 || shouldShowXAxisLabel(index, chartData.length)) {
                  return (
                    <text x={x} y={y + 10} fill="#64748b" fontSize="11px" textAnchor="middle">
                      {payload.value}
                    </text>
                  );
                }
                return null;
              }}
            />
            <YAxis
              stroke="#64748b"
              style={{ fontSize: '11px' }}
              tickLine={false}
              domain={yAxisDomain}
              allowDecimals={false}
              tickCount={6}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1e293b',
                border: 'none',
                borderRadius: '8px',
                color: '#fff',
                padding: '8px 12px'
              }}
              labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
            />
            <Area
              type="monotone"
              dataKey="users"
              stroke="#8b5cf6"
              strokeWidth={2}
              fill="url(#colorUsers)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
