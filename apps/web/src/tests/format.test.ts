import { describe, expect, it } from "vitest";
import { ago, int, pct, STATUS_ES } from "../lib/format";

describe("formatos", () => {
  it("porcentajes y enteros en es-PE", () => {
    expect(pct(0.123)).toMatch(/^12[.,]3%$/);
    expect(pct(null)).toBe("—");
    expect(int(24593).replace(/\D/g, "")).toBe("24593");
    expect(int(null)).toBe("—");
  });
  it("tiempo relativo", () => {
    expect(ago(new Date().toISOString())).toBe("Hace un momento");
    expect(ago(new Date(Date.now() - 2 * 3600e3).toISOString())).toBe("Hace 2 h");
  });
  it("estados traducidos", () => {
    expect(STATUS_ES.training).toBe("Entrenando");
  });
});
