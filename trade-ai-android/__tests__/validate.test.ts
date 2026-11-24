import { validateResponse } from "../src/api/validate";
import analysis from "../docs/backend/v2_examples/analysis.json";
import { emptyPortfolio } from "../src/domain/safety";
test("malformed and fixture responses are rejected in live client", () => {
  expect(validateResponse("/analyze", "POST", {})).toBe(false);
  expect(validateResponse("/analyze", "POST", analysis)).toBe(false);
  expect(
    validateResponse("/analyze", "POST", { ...analysis, data_mode: "live" }),
  ).toBe(true);
  expect(validateResponse("/portfolios", "GET", [emptyPortfolio("AUTO")])).toBe(
    false,
  );
  expect(
    validateResponse("/portfolios", "GET", [
      { ...emptyPortfolio("AUTO"), data_mode: "live" },
    ]),
  ).toBe(true);
  expect(
    validateResponse("/portfolios", "GET", [
      { ...emptyPortfolio("AUTO"), data_mode: "live", cash_quote: 10000 },
    ]),
  ).toBe(false);
});
test("unknown routes fail closed", () =>
  expect(validateResponse("/invented", "GET", {})).toBe(false));
