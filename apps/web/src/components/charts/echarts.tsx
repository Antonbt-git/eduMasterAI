import ReactEChartsCore from "echarts-for-react/lib/core";
import { BarChart, HeatmapChart, LineChart, PieChart } from "echarts/charts";
import { GridComponent, LegendComponent, MarkPointComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([LineChart, BarChart, PieChart, HeatmapChart, GridComponent, TooltipComponent, LegendComponent, VisualMapComponent, MarkPointComponent, CanvasRenderer]);

export const C = { ink: "#0D0A1E", electric: "#7C5CFF", cyan: "#FF5FD2", violet: "#FF9F43", teal: "#2DE2A6", mist: "#A99CC9", dim: "#B4A8D8", line: "#3B2E78", frost: "#F3EEFF", warn: "#FFB547" };

export const tooltip = {
  backgroundColor: "rgba(13,10,30,0.95)",
  borderColor: "rgba(255,95,210,0.4)",
  textStyle: { color: C.frost, fontFamily: "Inter", fontSize: 12 },
  extraCssText: "border-radius:10px;box-shadow:0 0 24px -6px rgba(124,92,255,.6)",
};

export function EChart({ option, height = 240, label }: { option: any; height?: number | string; label: string }) {
  return (
    <div role="img" aria-label={label}>
      <ReactEChartsCore echarts={echarts} option={option} style={{ height, width: "100%" }} notMerge lazyUpdate opts={{ renderer: "canvas" }} />
    </div>
  );
}
