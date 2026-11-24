// Reuse exported-app QA fixtures and native-independent layout checks from Task 8.
process.env.VISUAL_TASK9 = "1";
process.env.WEB_EXPORT_DIR ||= "/tmp/trade9-web";
process.env.VISUAL_OUTPUT_DIR ||= "/tmp/trade9-visual";
require("./visual-task8.cjs");
