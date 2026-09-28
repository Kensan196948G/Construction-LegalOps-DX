import { render, screen } from "@testing-library/react";

import { RisksOverview } from "../risks-overview";

/**
 * Regression: ヒートマップは 4×4 で描画されていたが、DB の CHECK 制約
 * （`ck_risk_probability` / `ck_risk_impact`）は low|medium|high の 3 値のみで、
 * 確率=4 の行と影響度=4 の列は構造的に常に 0 だった。さらに凡例の
 * 「重大 (13–16)」は到達可能な最大スコア 9 を超えており、法務ユーザーに
 * 「重大リスク 0 件」と誤読させるため 3×3 / バンド 3 段に合わせた。
 */
describe("RisksOverview heatmap", () => {
  const byLevel = [
    { level: "low" as const, count: 1 },
    { level: "medium" as const, count: 2 },
    { level: "high" as const, count: 3 },
    { level: "critical" as const, count: 0 },
  ];

  it("renders exactly 3x3 cells with domain-accurate labels", () => {
    const cells = [
      { probability: 1 as const, impact: 1 as const, count: 1 },
      { probability: 3 as const, impact: 3 as const, count: 9 },
    ];
    const { container } = render(
      <RisksOverview byLevel={byLevel} byCategory={[]} heatmapData={cells} />,
    );

    // 確率 3 段（高/中/低）× 影響度 3 段（小/中/大）
    for (const label of ["高", "中", "低", "小", "大"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    // ドメインに存在しない語・到達不能なバンドを描画しない
    expect(screen.queryByText("中高")).toBeNull();
    expect(screen.queryByText("低中")).toBeNull();
    expect(screen.queryByText(/重大 \(13/)).toBeNull();

    // 9 セル + 行ラベル 3 + 列ラベル 3。4×4 なら 16 セルになる。
    const grid = container.querySelector('[style*="grid-template-columns"]');
    expect(grid).not.toBeNull();
    expect(grid?.children.length).toBe(3 * (1 + 3) + 1 + 3);

    expect(screen.getByText("低 (1–3)")).toBeInTheDocument();
    expect(screen.getByText("中 (4–6)")).toBeInTheDocument();
    expect(screen.getByText("高 (7–9)")).toBeInTheDocument();
  });

  it("shows the count for a populated cell", () => {
    render(
      <RisksOverview
        byLevel={byLevel}
        byCategory={[]}
        heatmapData={[{ probability: 2, impact: 3, count: 7 }]}
      />,
    );
    expect(screen.getByText("7")).toBeInTheDocument();
  });
});
