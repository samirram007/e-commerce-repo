import path from "node:path";
import { fileURLToPath } from "node:url";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

const projectRoot = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, projectRoot, "VITE_");

  return {
    plugins: [
      tanstackRouter({
        target: "react",
        autoCodeSplitting: true,
        routesDirectory: "./src/routes",
        generatedRouteTree: "./src/routeTree.gen.ts",
      }),
      react(),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        "@": path.resolve(projectRoot, "src"),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          // Pin IPv4: uvicorn binds 127.0.0.1 only, but `localhost` resolves
          // to ::1 first on some machines, which makes the proxy 502.
          target: env.VITE_API_PROXY ?? "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
