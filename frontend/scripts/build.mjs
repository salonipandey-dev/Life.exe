// Production build: esbuild (TS/JSX bundle) + Tailwind CSS v4 compile API.
//
// Vite and the Tailwind CLI were not installable in the build environment
// (see docs/adr/ADR-004), so this ~100-line script does what they would:
//   1. bundle src/main.tsx -> dist/assets/app.js (minified, sourcemap)
//   2. extract class candidates from src/**, compile src/styles/app.css -> dist/assets/app.css
//   3. copy index.html and public/ into dist/
// Usage: node scripts/build.mjs [--watch]
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dist = path.join(root, "dist");
const extraPaths = (process.env.LIFEEXE_NODE_PATH ?? "/opt/npm-tools/node_modules").split(path.delimiter);
const require = createRequire(path.join(root, "package.json"));
const resolve = (id) => require.resolve(id, { paths: [path.join(root, "node_modules"), ...extraPaths] });

const esbuild = require(resolve("esbuild"));
const { compile } = require(resolve("tailwindcss"));
const tailwindDir = path.dirname(resolve("tailwindcss/package.json"));

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)],
  );
}

/** Candidate extraction: every token that could be a utility class. Tailwind
 * discards tokens that are not valid utilities, so over-collecting is safe. */
function candidates() {
  const set = new Set();
  for (const file of walk(path.join(root, "src"))) {
    if (!/\.(tsx?|html)$/.test(file)) continue;
    const text = fs.readFileSync(file, "utf8");
    for (const raw of text.split(/[\s"'`{}<>]+/)) {
      // trim punctuation that belongs to the surrounding code, not the class
      const token = raw.replace(/^[(,;]+|[),;]+$/g, "");
      if (/^[a-z!@\-\[][a-zA-Z0-9:/\[\]._%#\-!&>=*+(),]*$/.test(token) && token.length < 100) set.add(token);
    }
  }
  return [...set];
}

async function buildCss() {
  const entry = path.join(root, "src/styles/app.css");
  const compiler = await compile(fs.readFileSync(entry, "utf8"), {
    base: path.dirname(entry),
    loadStylesheet: async (id, base) => {
      const file = id === "tailwindcss" ? path.join(tailwindDir, "index.css")
        : id.startsWith("tailwindcss/") ? path.join(tailwindDir, id.slice("tailwindcss/".length))
        : path.resolve(base, id);
      return { path: file, base: path.dirname(file), content: fs.readFileSync(file, "utf8") };
    },
  });
  const css = compiler.build(candidates());
  const { code } = await esbuild.transform(css, { loader: "css", minify: true });
  fs.writeFileSync(path.join(dist, "assets/app.css"), code);
  return code.length;
}

function copyStatic() {
  fs.copyFileSync(path.join(root, "index.html"), path.join(dist, "index.html"));
  fs.cpSync(path.join(root, "public"), dist, { recursive: true });
}

const jsOptions = {
  entryPoints: [path.join(root, "src/main.tsx")],
  outfile: path.join(dist, "assets/app.js"),
  bundle: true,
  minify: true,
  sourcemap: true,
  format: "esm",
  target: ["es2020", "chrome100", "safari15", "firefox100"],
  jsx: "automatic",
  nodePaths: [path.join(root, "node_modules"), ...extraPaths],
  define: { "process.env.NODE_ENV": '"production"' },
  logLevel: "warning",
};

fs.rmSync(dist, { recursive: true, force: true });
fs.mkdirSync(path.join(dist, "assets"), { recursive: true });
copyStatic();

if (process.argv.includes("--watch")) {
  const ctx = await esbuild.context({
    ...jsOptions,
    minify: false,
    plugins: [{ name: "css", setup: (b) => b.onEnd(() => buildCss().then(() => console.log("rebuilt"))) }],
  });
  await ctx.watch();
  console.log("watching src/ ...");
} else {
  const started = Date.now();
  const result = await esbuild.build({ ...jsOptions, metafile: true });
  const cssBytes = await buildCss();
  const jsBytes = Object.values(result.metafile.outputs).find((o) => o.entryPoint)?.bytes ?? 0;
  console.log(`built in ${Date.now() - started}ms  js ${(jsBytes / 1024).toFixed(1)} KiB  css ${(cssBytes / 1024).toFixed(1)} KiB`);
}
