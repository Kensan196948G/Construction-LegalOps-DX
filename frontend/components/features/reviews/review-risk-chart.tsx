"use client";

import * as React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/components/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";

export interface RiskCategoryScore {
  /** カテゴリ名 (例: 価格条件 / 瑕疵担保 / 解除条項) */
  category: string;
  /** 0-100 のスコア (高いほどリスクが大きい) */
  score: number;
}

export interface ReviewRiskChartProps
  extends React.HTMLAttributes<HTMLDivElement> {
  data: RiskCategoryScore[];
  variant?: "radar" | "bar";
  title?: string;
  description?: string;
  height?: number;
}

export function ReviewRiskChart({
  data,
  variant = "radar",
  title = "リスクスコア",
  description,
  className,
  height = 320,
  ...props
}: ReviewRiskChartProps) {
  return (
    <Card className={cn(className)} {...props}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <AiDisclaimerBanner variant="inline" />
        <div style={{ width: "100%", height }}>
          <ResponsiveContainer width="100%" height="100%">
            {variant === "radar" ? (
              <RadarChart data={data} outerRadius="75%">
                <PolarGrid strokeOpacity={0.3} />
                <PolarAngleAxis dataKey="category" tick={{ fontSize: 12 }} />
                <PolarRadiusAxis
                  angle={30}
                  domain={[0, 100]}
                  tick={{ fontSize: 10 }}
                />
                <Tooltip />
                <Radar
                  name="リスクスコア"
                  dataKey="score"
                  stroke="#ef4444"
                  fill="#ef4444"
                  fillOpacity={0.35}
                />
              </RadarChart>
            ) : (
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.3} />
                <XAxis dataKey="category" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar
                  dataKey="score"
                  fill="#ef4444"
                  radius={[4, 4, 0, 0]}
                  name="リスクスコア"
                />
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

export default ReviewRiskChart;
