const esbuild = require("esbuild");

const client = process.argv[2];
const clientCandidate = ["browser", "node"];

if (!client) {
  console.log("You must specify client target(browser/node)");
  process.exit(1);
}
if (!clientCandidate.includes(client)) {
  console.log("Invalid client");
  process.exit(1);
}

const CommonConfig = {
  entryPoints: [client + "/index.ts"],
  bundle: true,
  sourcemap: true,
  target: ["es6"],
};

esbuild
  .build({ ...CommonConfig, format: "cjs", outfile: `dist/${client}/index.cjs`, platform: client })
  .catch(() => process.exit(1));

esbuild
  .build({
    ...CommonConfig,
    format: "esm",
    outfile: `dist/${client}/index.mjs`,
    platform: client,
  })
  .catch(() => process.exit(1));
