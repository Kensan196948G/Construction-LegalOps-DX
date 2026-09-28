import { buildParams } from "@/lib/api/endpoints";

/**
 * Regression: backend の一覧系エンドポイントはページサイズを `size` で受ける
 * （`page_size` を受け付けるものは 0 件）。frontend は `page_size` を送っていた
 * ため、指定件数が無視され常に既定値（多くは 20 件）が返っていた。
 * `buildParams` の 1 箇所で写像する。
 */
describe("buildParams page_size -> size mapping", () => {
  it("maps page_size to the backend parameter name", () => {
    expect(buildParams({ page: 2, page_size: 50 })).toEqual({ page: 2, size: 50 });
  });

  it("keeps other parameters untouched", () => {
    expect(
      buildParams({ page: 1, page_size: 24, q: "工事", sort: "-created_at" }),
    ).toEqual({ page: 1, size: 24, q: "工事", sort: "-created_at" });
  });

  it("prefers an explicitly supplied size", () => {
    expect(buildParams({ page: 1, size: 10, page_size: 50 })).toEqual({ page: 1, size: 10 });
    expect(buildParams({ page: 1, page_size: 50, size: 10 })).toEqual({ page: 1, size: 10 });
  });

  it("drops values the backend would reject with 422", () => {
    // 以前は素通しで無視されていたため、不正値で 422 にしないことが重要
    for (const bad of [Number.NaN, Number.POSITIVE_INFINITY, 0, -1, 1.5]) {
      expect(buildParams({ page: 1, page_size: bad })).toEqual({ page: 1 });
    }
    expect(buildParams({ page_size: "abc" })).toBeUndefined();
  });

  it("clamps to the maximum page size (200)", () => {
    expect(buildParams({ page_size: 999 })).toEqual({ size: 200 });
    expect(buildParams({ page_size: 201 })).toEqual({ size: 200 });
    expect(buildParams({ page_size: 200 })).toEqual({ size: 200 });
    // 文字列で来るケース（URL クエリ由来）も数値化して扱う
    expect(buildParams({ page_size: "50" })).toEqual({ size: 50 });
  });

  it("still drops null / undefined / empty values", () => {
    expect(buildParams({ page: undefined, page_size: null, q: "" })).toBeUndefined();
    expect(buildParams()).toBeUndefined();
  });
});
