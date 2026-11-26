module.exports = {
  preset: "jest-expo",
  testMatch: ["**/__tests__/**/*.test.[jt]s?(x)"],
  collectCoverageFrom: ["src/domain/**/*.ts", "src/api/client.ts"],
  testPathIgnorePatterns: ["/node_modules/", "/android/"],
};
