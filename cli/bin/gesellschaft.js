#!/usr/bin/env node
import { run } from "../src/main.js";

run(process.argv).catch((err) => {
  console.error("错误:", err && err.message ? err.message : err);
  process.exit(1);
});
