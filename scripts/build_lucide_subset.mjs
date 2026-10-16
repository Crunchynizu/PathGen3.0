// Rebuilds static/vendor/lucide/lucide.min.js with only the icons PathGen uses.
// The full Lucide bundle is ~350 KB; every page loads this file, so phones
// download and parse only the ~100 icons we need.
//
// Run from pathgen3.0app/ after adding a new data-lucide icon (needs Node and
// internet once):
//   npm install --no-save --prefix .lucide-build lucide@0.487.0 esbuild@0.24.2
//   node scripts/build_lucide_subset.mjs
// tests/test_qa_smoke.py fails if a template or script uses an icon that is
// missing from the subset.
import { readdirSync, readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const buildDir = join(root, ".lucide-build");
const require = createRequire(join(buildDir, "package.json"));
const lucide = require("lucide");
const esbuild = require("esbuild");
const version = require("lucide/package.json").version;

const toPascal = (name) =>
  name.replace(/(\w)(\w*)(_|-|\s*)/g, (_, first, rest) => first.toUpperCase() + rest.toLowerCase());

function files(dir, ext) {
  return readdirSync(dir, { withFileTypes: true, recursive: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(ext))
    .map((entry) => join(entry.parentPath, entry.name));
}

const names = new Set();
for (const file of files(join(root, "templates"), ".html")) {
  for (const [, name] of readFileSync(file, "utf8").matchAll(/data-lucide="([a-z0-9-]+)"/g)) names.add(name);
}
// Scripts build icons from plain strings (e.g. button("...", "", "plus")), so
// keep every string literal that is a Lucide icon name.
for (const file of files(join(root, "static", "js"), ".js")) {
  for (const [, name] of readFileSync(file, "utf8").matchAll(/["'`]([a-z0-9-]+)["'`]/g)) {
    if (lucide.icons[toPascal(name)]) names.add(name);
  }
}

const missing = [...names].filter((name) => !lucide.icons[toPascal(name)]);
if (missing.length) throw new Error(`Not Lucide icons: ${missing.join(", ")}`);
const ids = [...new Set([...names].map(toPascal))].sort();

mkdirSync(buildDir, { recursive: true });
const entry = join(buildDir, "entry.js");
writeFileSync(
  entry,
  `import { createIcons as create, ${ids.join(", ")} } from "lucide";
const icons = { ${ids.join(", ")} };
window.lucide = { icons, createIcons: (options = {}) => create({ icons, ...options }) };
`,
);
const out = join(root, "static", "vendor", "lucide", "lucide.min.js");
await esbuild.build({
  entryPoints: [entry],
  bundle: true,
  minify: true,
  format: "iife",
  target: "es2018",
  outfile: out,
  legalComments: "none",
  banner: {
    js: `/* lucide v${version} (ISC) subset: ${ids.length} icons. Rebuild: scripts/build_lucide_subset.mjs */`,
  },
});
console.log(`Wrote ${out}: ${ids.length} icons, ${readFileSync(out).length} bytes`);
