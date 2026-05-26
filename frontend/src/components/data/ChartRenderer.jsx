import { useEffect, useRef } from "react";
import Chart from "chart.js/auto";

export default function ChartRenderer({ chart, height = 300 }) {
  const ref = useRef(null);
  const instance = useRef(null);

  useEffect(() => {
    if (!chart || !ref.current) return;

    if (instance.current) {
      instance.current.destroy();
      instance.current = null;
    }

    const type = chart.chart_type === "hist" ? "bar" : (chart.chart_type || "bar");

    const datasets = chart.datasets?.length
      ? chart.datasets
      : [{
        label: chart.title || "Value",
        data: chart.values || [],
        backgroundColor: "#454cc7",
        borderColor: "#454cc7",
        borderWidth: 2,
        borderRadius: 4,
      }];

    const chartConfig = {
      type,
      data: { labels: chart.labels || [], datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: datasets.length > 1,
            labels: { color: "#3a3a6a", font: { size: 12 } },
          },
          title: {
            display: !!chart.title,
            text: chart.title || "",
            color: "#070811",
            font: { size: 14, weight: "600" },
            padding: { bottom: 16 },
          },
        },
        scales: type !== "pie" && type !== "doughnut"
          ? {
            x: { ticks: { color: "#6b6b9a", font: { size: 11 } }, grid: { color: "#d4d4e8" } },
            y: { beginAtZero: true, ticks: { color: "#6b6b9a", font: { size: 11 } }, grid: { color: "#d4d4e8" } },
          }
          : {},
      },
    };

    // Histogram: raw values, bars touching like a real histogram
    if (chart.chart_type === "hist") {
      const vals = chart.values || [];

      // Bin the raw values into buckets
      const min = Math.floor(Math.min(...vals));
      const max = Math.ceil(Math.max(...vals));
      const binCount = Math.min(10, max - min);
      const binSize = (max - min) / binCount;

      const bins = Array(binCount).fill(0);
      vals.forEach((v) => {
        const idx = Math.min(Math.floor((v - min) / binSize), binCount - 1);
        bins[idx]++;
      });

      const binLabels = Array(binCount).fill(0).map((_, i) =>
        `${(min + i * binSize).toFixed(0)}–${(min + (i + 1) * binSize).toFixed(0)}`
      );

      chartConfig.data.labels = binLabels;
      chartConfig.data.datasets[0].data = bins;
      chartConfig.data.datasets[0].barPercentage = 1.0;
      chartConfig.data.datasets[0].categoryPercentage = 1.0;
      chartConfig.data.datasets[0].borderRadius = 0;
      chartConfig.options.scales.x = {
        ...chartConfig.options.scales.x,
        offset: false,
      };
    }

    instance.current = new Chart(ref.current, chartConfig);

    return () => {
      if (instance.current) {
        instance.current.destroy();
        instance.current = null;
      }
    };
  }, [chart]);

  if (!chart) return null;

  return (
    <div style={{
      background: "var(--bg-surface)",
      border: "1px solid var(--border)",
      borderRadius: "var(--radius-lg)",
      padding: 20,
      marginTop: 12,
    }}>
      <canvas ref={ref} style={{ maxHeight: height, width: "100%" }} />
    </div>
  );
}