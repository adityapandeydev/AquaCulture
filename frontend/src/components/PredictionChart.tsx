import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts"

const getDotColor = (risk: string) => {
  if (risk === "low") return "#84CC16"
  if (risk === "medium") return "#F59E0B"
  return "#EF4444"
}

export default function PredictionChart({ data, dataKey, color }: any) {
  return (
    <div className="bg-surface p-4 rounded-xl h-64">
      <h2 className="mb-2 text-sm text-textSecondary uppercase">
        {dataKey}
      </h2>

      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
            <XAxis dataKey="time" stroke="#9ca3af" />
            <YAxis stroke="#9ca3af" />
            <Tooltip
              contentStyle={{
                backgroundColor: "#111827",
                border: "1px solid #1f2937",
                borderRadius: "8px",
              }}
            />
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={2}
            dot={(props: any) => {
              const { cx, cy, payload } = props
              return (
                <circle
                  cx={cx}
                  cy={cy}
                  r={3}
                  fill={getDotColor(payload.risk)}
                />
              )
            }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}