import { defineConfig } from "vitest/config";
import path from "path";

// jsdom, though nothing here mounts a component. The modules under test are
// pure, but they live in files that transitively import the UI store, which
// reads localStorage and touches document.documentElement at module load. A
// DOM is the cheapest way past that; the tests still assert on rules rather
// than on markup.
export default defineConfig({
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
  },
});
