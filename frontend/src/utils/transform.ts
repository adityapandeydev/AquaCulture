export const transformPredictions = (data: any[]) => {
  const chartData: any[] = []

  data.forEach((entry) => {
    const baseTime = new Date(entry.window_end)

    entry.water_forecast.forEach((water: any, i: number) => {
      const nitrogen = entry.nitrogen_forecast[i]
      const risk = entry.risk?.risk_states?.[i] || "low"

      chartData.push({
        time: new Date(baseTime.getTime() + (i + 1) * 3600000)
          .toISOString()
          .slice(11, 16),

        do: water[0],
        temperature: water[1],
        ammonia: nitrogen[0],
        nitrate: nitrogen[1],

        risk, // 🔥 NEW
      })
    })
  })

  return chartData
}

export const getLatestMetrics = (data: any[]) => {
  if (!data.length) return null

  const last = data[data.length - 1]

  return {
    do: last.do,
    temperature: last.temperature,
    ammonia: last.ammonia,
    nitrate: last.nitrate,
  }
}

export const getCurrentRisk = (data: any[]) => {
  if (!data.length) return "low"
  return data[0].risk
}