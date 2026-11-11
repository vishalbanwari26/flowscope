// List the public functions and class methods of JavaScript and TypeScript files, for `flow gaps`.
// node scan.js <project root> <json file with the list of files>
const fs = require("fs");
const root = process.argv[2];
const files = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const parser = require(require.resolve("@babel/parser", { paths: [root] }));

const out = [];
const FN = new Set(["FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"]);
const isPublic = (name) => name && !name.startsWith("_") && !name.startsWith("#");

for (const file of files) {
  let ast;
  try {
    ast = parser.parse(fs.readFileSync(file, "utf8"), {
      sourceType: "unambiguous", errorRecovery: true,
      plugins: ["typescript", "jsx", "decorators-legacy", "classProperties"],
    });
  } catch { continue; }
  const found = [];
  const exported = new Set();
  let usesEsExports = false;
  const add = (node, qual, name, isExported) =>
    found.push({ name, qual, line: node.loc.start.line, size: node.loc.end.line - node.loc.start.line + 1, exported: isExported });
  const fromDecl = (d, isExported) => {
    if (!d) return;
    if (d.type === "FunctionDeclaration" && d.id) add(d, d.id.name, d.id.name, isExported);
    else if (d.type === "VariableDeclaration") {
      for (const v of d.declarations)
        if (v.id.type === "Identifier" && v.init && FN.has(v.init.type)) add(v, v.id.name, v.id.name, isExported);
    } else if (d.type === "ClassDeclaration" && d.id) {
      for (const m of d.body.body) {
        const k = m.key && (m.key.name || m.key.value);
        if ((m.type === "ClassMethod" || m.type === "ClassProperty") && k && k !== "constructor")
          if (m.type === "ClassMethod" || (m.value && FN.has(m.value.type))) add(m, `${d.id.name}.${k}`, k, isExported);
      }
    }
  };
  for (const node of ast.program.body) {
    if (node.type === "ExportNamedDeclaration") {
      usesEsExports = true;
      if (node.declaration) fromDecl(node.declaration, true);
      for (const s of node.specifiers || []) if (s.local) exported.add(s.local.name);
    } else if (node.type === "ExportDefaultDeclaration") {
      usesEsExports = true;
      fromDecl(node.declaration, true);
    } else {
      fromDecl(node, false);
      if (node.type === "ExpressionStatement" && node.expression.type === "AssignmentExpression") {
        const l = node.expression.left, r = node.expression.right;
        const text = l.type === "MemberExpression" ? `${l.object.name || ""}.${l.property.name || ""}` : "";
        if (text === "module.exports" && r.type === "ObjectExpression")
          for (const p of r.properties) if (p.key) exported.add(p.key.name);
        if (text === "module.exports" && r.type === "Identifier") exported.add(r.name);
        if (text.startsWith("exports.") && l.property) exported.add(l.property.name);
      }
    }
  }
  for (const f of found) {
    const cjsPublic = !usesEsExports && (exported.size === 0 || exported.has(f.name) || exported.has(f.qual.split(".")[0]));
    if ((f.exported || exported.has(f.name) || exported.has(f.qual.split(".")[0]) || cjsPublic) && isPublic(f.name))
      out.push({ file, name: f.name, qual: f.qual, line: f.line, size: f.size, entry: f.name === "main" });
  }
}
process.stdout.write(JSON.stringify(out));
