import { useEffect, useRef } from "react";

export default function PlotlyChart({ plotlyJson }) {
  const divRef = useRef();

  useEffect(() => {
    if (!plotlyJson || !divRef.current) return;

    let parsed;
    try {
      parsed = typeof plotlyJson === "string" ? JSON.parse(plotlyJson) : plotlyJson;
    } catch (e) {
      console.error("Failed to parse plotly_json:", e);
      return;
    }

    // Dynamically import Plotly to avoid bundle size issues
    import("plotly.js-dist").then((Plotly) => {
      Plotly.newPlot(divRef.current, parsed.data, parsed.layout, {
        responsive: true,
        displayModeBar: false,
      });
    });

    return () => {
      import("plotly.js-dist").then((Plotly) => {
        if (divRef.current) Plotly.purge(divRef.current);
      });
    };
  }, [plotlyJson]);

  return (
    <div style={{
      marginTop: 12,
      background: "var(--bg-surface)",
      border: "1px solid var(--border)",
      borderRadius: "var(--radius-lg)",
      overflow: "hidden",
    }}>
      <div ref={divRef} style={{ width: "100%", minHeight: 350 }} />
    </div>
  );
}