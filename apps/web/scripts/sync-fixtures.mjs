// Copy shared contract examples into apps/web/mocks/fixtures so the web app
// builds self-contained (Vercel root = apps/web). Source of truth stays in
// contracts/examples; CI re-runs this and fails on any git diff.
//   npm run sync:fixtures
import { cpSync, mkdirSync, readdirSync, rmSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = join(here, "..", "..", "..", "contracts", "examples");
const target = join(here, "..", "mocks", "fixtures");

function jsonFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) return jsonFiles(full);
    return name.endsWith(".json") ? [full] : [];
  });
}

rmSync(target, { recursive: true, force: true });
for (const file of jsonFiles(source)) {
  const dest = join(target, relative(source, file));
  mkdirSync(dirname(dest), { recursive: true });
  cpSync(file, dest);
}
console.log(`Synced ${jsonFiles(source).length} contract examples into mocks/fixtures`);
