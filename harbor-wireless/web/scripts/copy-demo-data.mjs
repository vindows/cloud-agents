#!/usr/bin/env node
/**
 * Copy harbor-wireless/data/*.json into public/demo-data/ so production
 * builds (vite preview, Cursor publish-app) serve the full synthetic set.
 * Dev still uses the Vite middleware; public/ is what ships in dist/.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "..");
const srcDir = path.resolve(webRoot, "../data");
const destDir = path.resolve(webRoot, "public/demo-data");

const FILES = ["tickets.json", "agents.json", "golden-set.json", "dataset-meta.json"];

function destReady() {
  return FILES.every((name) => fs.existsSync(path.join(destDir, name)));
}

if (!fs.existsSync(srcDir)) {
  if (destReady()) {
    console.log(
      `[copy-demo-data] source ${srcDir} missing; using committed public/demo-data/`,
    );
    process.exit(0);
  }
  console.error(`[copy-demo-data] missing source dir: ${srcDir}`);
  process.exit(1);
}

fs.mkdirSync(destDir, { recursive: true });

let bytes = 0;
for (const name of FILES) {
  const from = path.join(srcDir, name);
  const to = path.join(destDir, name);
  if (!fs.existsSync(from)) {
    if (fs.existsSync(to)) {
      console.warn(`[copy-demo-data] missing ${from}; keeping existing ${to}`);
      bytes += fs.statSync(to).size;
      continue;
    }
    console.error(`[copy-demo-data] missing file: ${from}`);
    process.exit(1);
  }
  fs.copyFileSync(from, to);
  bytes += fs.statSync(to).size;
  console.log(`[copy-demo-data] ${name} → public/demo-data/ (${fs.statSync(to).size} bytes)`);
}

console.log(`[copy-demo-data] done (${FILES.length} files, ${(bytes / (1024 * 1024)).toFixed(2)} MiB)`);
