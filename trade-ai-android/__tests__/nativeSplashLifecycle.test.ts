const mockHide = jest.fn().mockResolvedValue(undefined),
  mockPrevent = jest.fn().mockResolvedValue(true),
  mockOptions = jest.fn();
jest.mock("expo-splash-screen", () => ({
  hideAsync: (...args: unknown[]) => mockHide(...args),
  preventAutoHideAsync: () => mockPrevent(),
  setOptions: (...args: unknown[]) => mockOptions(...args),
}));
jest.mock("react-native", () => ({ Platform: { OS: "android" } }));
afterEach(() => {
  jest.useRealTimers();
  jest.clearAllMocks();
});
function fresh() {
  let s!: typeof import("../src/startup");
  jest.isolateModules(() => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- A fresh module tests each native process cold start.
    s = require("../src/startup");
  });
  return s;
}
test("first branded layout releases native exactly once, no fixed display delay", async () => {
  jest.useFakeTimers();
  const s = fresh();
  s.prepareNativeSplash();
  s.prepareNativeSplash();
  expect(mockPrevent).toHaveBeenCalledTimes(1);
  expect(mockHide).not.toHaveBeenCalled();
  s.releaseNativeSplash();
  s.releaseNativeSplash();
  expect(mockHide).toHaveBeenCalledTimes(1);
  jest.advanceTimersByTime(6000);
  expect(mockHide).toHaveBeenCalledTimes(1);
});
test("missing first-layout callback cannot leave an infinite native splash", async () => {
  jest.useFakeTimers();
  const s = fresh();
  s.prepareNativeSplash();
  jest.advanceTimersByTime(5999);
  expect(mockHide).not.toHaveBeenCalled();
  jest.advanceTimersByTime(1);
  expect(mockHide).toHaveBeenCalledTimes(1);
});
