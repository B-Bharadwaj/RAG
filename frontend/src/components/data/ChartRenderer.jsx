import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from "recharts";

const COLORS = [
  "#e0e0ff", "#60a5fa", "#4ade80", "#fb923c", "#f472b6",
  "#a78bfa", "#34d399", "#fbbf24", "#818cf8"
];

const TOOLTIP_STYLE = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  fontSize: 12,
  color: "var(--text-primary)",
};

export default function ChartRenderer({ chartData }) {
  if (!chartData) return null;

  const {
    chart_type,
    data,
    x_column,
    y_column,
    title,
    labels,
    values,
  } = chartData;

  const type = (chart_type || "bar").toLowerCase();

  // Normalize data
  const normalized = (() => {
    if (Array.isArray(data)) return data;
    if (labels && values) return labels.map((l, i) => ({ name: l, value: values[i] }));
    return [];
  })();

  if (!normalized.length) {
    return (
      <div className="chart-box">
        <p className="text-muted text-sm" style={{ textAlign: "center", padding: 20 }}>
          No chart data available
        </p>
      </div>
    );
  }

  const xKey = x_column || "name" || Object.keys(normalized[0])[0];
  const yKey = y_column || "value" || Object.keys(normalized[0])[1];

  return (
    <div className="chart-box">
      {title && (
        <div style={{ fontWeight: 600, marginBottom: 16, fontSize: 14 }}>{title}</div>
      )}
      <ResponsiveContainer width="100%" height={300}>
        {type === "bar" ? (
          <BarChart data={normalized} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey={xKey} tick={{ fill: "var(--text-muted)", fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "var(--bg-hover)" }} />
            <Bar dataKey={yKey} fill="#e0e0ff" radius={[3, 3, 0, 0]} />
          </BarChart>
        ) : type === "line" ? (
          <LineChart data={normalized} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey={xKey} tick={{ fill: "var(--text-muted)", fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Line type="monotone" dataKey={yKey} stroke="#e0e0ff" strokeWidth={2} dot={{ r: 3, fill: "#e0e0ff" }} />
          </LineChart>
        ) : type === "pie" ? (
          <PieChart>
            <Pie
              data={normalized}
              dataKey={yKey || "value"}
              nameKey={xKey || "name"}
              cx="50%"
              cy="50%"
              outerRadius={120}
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              labelLine={false}
            >
              {normalized.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Legend wrapperStyle={{ fontSize: 11, color: "var(--text-muted)" }} />
          </PieChart>
        ) : type === "scatter" ? (
          <ScatterChart margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey={xKey} type="number" name={xKey} tick={{ fill: "var(--text-muted)", fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis dataKey={yKey} type="number" name={yKey} tick={{ fill: "var(--text-muted)", fontSize: 11 }} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ strokeDasharray: "3 3" }} />
            <Scatter data={normalized} fill="#e0e0ff" />
          </ScatterChart>
        ) : (
          // hist fallback → bar
          <BarChart data={normalized} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey={xKey} tick={{ fill: "var(--text-muted)", fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "var(--bg-hover)" }} />
            <Bar dataKey={yKey} fill="#60a5fa" radius={[3, 3, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
