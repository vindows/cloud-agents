import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.resolve(__dirname, "../data");

/**
 * Dev-only: serve ../data at /demo-data.
 * Production uses files copied into public/demo-data/ (see scripts/copy-demo-data.mjs).
 */
function harborDataPlugin(): Plugin {
  return {
    name: "harbor-data",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url?.split("?")[0] ?? "";
        if (!url.startsWith("/demo-data/")) return next();
        const rel = decodeURIComponent(url.replace("/demo-data/", ""));
        const file = path.normalize(path.join(dataDir, rel));
        if (!file.startsWith(dataDir) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
          res.statusCode = 404;
          res.end("Not found");
          return;
        }
        res.setHeader("Content-Type", "application/json");
        fs.createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), harborDataPlugin()],
  server: {
    port: 5173,
    fs: { allow: [path.resolve(__dirname, "..")] },
  },
});
