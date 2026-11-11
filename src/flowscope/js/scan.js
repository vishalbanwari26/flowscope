// List the public functions and class methods of JavaScript and TypeScript files, for `flow gaps`.
// node scan.js <project root> <json file with the list of files>
// It reads the code with @babel/parser or, when the project has no Babel, with TypeScript.
const fs = require("fs");
const path = require("path");
const { createRequire } = require("module");
const { pathToFileURL } = require("url");
const root = process.argv[2];
const files = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));

function tryRequire(name) {
  try { return require(require.resolve(name, { paths: [root] })); } catch { return null; }
}
const babel = tryRequire("@babel/parser");
const tsPkg = babel ? null : tryRequire("typescript");
const ts = tsPkg && tsPkg.createSourceFile ? tsPkg : null;    // TypeScript 7 has no JavaScript API

const isPublic = (name) => name && !name.startsWith("_") && !name.startsWith("#");

// Each reader returns { found: [{name, qual, line, size, exported}], exported: Set, usesEsExports }
function readWithBabel(text) {
  const FN = new Set(["FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"]);
  const ast = babel.parse(text, { sourceType: "unambiguous", errorRecovery: true,
    plugins: ["typescript", "jsx", "decorators-legacy", "classProperties"] });
  const found = [], exported = new Set();
  let usesEsExports = false;
  const add = (node, qual, name, isExported) => found.push({ name, qual, line: node.loc.start.line,
    size: node.loc.end.line - node.loc.start.line + 1, exported: isExported });
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
      collectCommonJs(node, exported, (n) => n.expression && n.expression.type === "AssignmentExpression" ? n.expression : null,
        (l) => l.type === "MemberExpression" ? { obj: l.object.name || "", prop: l.property.name || "" } : null,
        (r) => (r.type === "ObjectExpression" ? r.properties.map((p) => p.key && p.key.name) : r.type === "Identifier" ? [r.name] : []),
        node.type === "ExpressionStatement");
    }
  }
  return { found, exported, usesEsExports };
}

function collectCommonJs(node, exported, getAssign, getTarget, getNames, isStatement) {
  if (!isStatement) return;
  const a = getAssign(node);
  if (!a) return;
  const t = getTarget(a.left);
  if (!t) return;
  if (t.obj === "module" && t.prop === "exports") for (const n of getNames(a.right)) if (n) exported.add(n);
  if (t.obj === "exports") exported.add(t.prop);
}

function readWithTypescript(text, file) {
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
  const K = ts.SyntaxKind;
  const found = [], exported = new Set();
  let usesEsExports = false;
  const lineOf = (n) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1;
  const endLine = (n) => sf.getLineAndCharacterOfPosition(n.getEnd()).line + 1;
  const hasExport = (n) => (ts.getCombinedModifierFlags ? (ts.getCombinedModifierFlags(n) & ts.ModifierFlags.Export) !== 0 : false);
  const isFn = (n) => n && (n.kind === K.ArrowFunction || n.kind === K.FunctionExpression);
  const add = (node, qual, name, isExported) => found.push({ name, qual, line: lineOf(node),
    size: endLine(node) - lineOf(node) + 1, exported: isExported });
  const nameOf = (n) => n.name && (n.name.text || n.name.escapedText);
  const fromDecl = (d, isExported) => {
    if (d.kind === K.FunctionDeclaration && d.name) add(d, d.name.text, d.name.text, isExported);
    else if (d.kind === K.VariableStatement) {
      for (const v of d.declarationList.declarations)
        if (v.name.kind === K.Identifier && isFn(v.initializer)) add(v, v.name.text, v.name.text, isExported);
    } else if (d.kind === K.ClassDeclaration && d.name) {
      for (const m of d.members) {
        const k = m.name && (m.name.text || m.name.escapedText);
        if (!k || m.kind === K.Constructor) continue;
        if (m.kind === K.MethodDeclaration || (m.kind === K.PropertyDeclaration && isFn(m.initializer)))
          add(m, `${d.name.text}.${k}`, k, isExported);
      }
    }
  };
  for (const node of sf.statements) {
    if (node.kind === K.ExportDeclaration) {
      usesEsExports = true;
      if (node.exportClause && node.exportClause.elements)
        for (const e of node.exportClause.elements) exported.add((e.propertyName || e.name).text);
    } else if (node.kind === K.ExportAssignment) {
      usesEsExports = true;
    } else if (hasExport(node)) {
      usesEsExports = true;
      fromDecl(node, true);
    } else {
      fromDecl(node, false);
      if (node.kind === K.ExpressionStatement && node.expression.kind === K.BinaryExpression
          && node.expression.operatorToken.kind === K.EqualsToken) {
        const l = node.expression.left, r = node.expression.right;
        const text = l.kind === K.PropertyAccessExpression ? l.getText(sf) : "";
        if (text === "module.exports") {
          if (r.kind === K.ObjectLiteralExpression) for (const p of r.properties) if (p.name) exported.add(p.name.text);
          if (r.kind === K.Identifier) exported.add(r.text);
        }
        if (text.startsWith("exports.")) exported.add(text.slice(8));
      }
    }
  }
  return { found, exported, usesEsExports };
}

// Last resort: Node strips the types (keeping every line where it was) and Vite parses the rest.
let parseAst = null;
function readWithStripping(text) {
  const { stripTypeScriptTypes } = require("node:module");
  const code = stripTypeScriptTypes(text, { mode: "strip" });
  const starts = [0];
  for (let i = 0; i < code.length; i++) if (code[i] === "\n") starts.push(i + 1);
  const lineAt = (pos) => { let lo = 0, hi = starts.length - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (starts[m] <= pos) lo = m; else hi = m - 1; } return lo + 1; };
  const FN = new Set(["FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"]);
  const found = [], exported = new Set();
  let usesEsExports = false;
  const add = (node, qual, name, isExported) => found.push({ name, qual, line: lineAt(node.start),
    size: lineAt(node.end) - lineAt(node.start) + 1, exported: isExported });
  const fromDecl = (d, isExported) => {
    if (!d) return;
    if (d.type === "FunctionDeclaration" && d.id) add(d, d.id.name, d.id.name, isExported);
    else if (d.type === "VariableDeclaration") {
      for (const v of d.declarations)
        if (v.id.type === "Identifier" && v.init && FN.has(v.init.type)) add(v, v.id.name, v.id.name, isExported);
    } else if (d.type === "ClassDeclaration" && d.id) {
      for (const m of d.body.body) {
        const k = m.key && (m.key.name || m.key.value);
        if (!k || m.kind === "constructor") continue;
        if (m.type === "MethodDefinition" || (m.type === "PropertyDefinition" && m.value && FN.has(m.value.type)))
          add(m, `${d.id.name}.${k}`, k, isExported);
      }
    }
  };
  for (const node of parseAst(code).body) {
    if (node.type === "ExportNamedDeclaration") {
      usesEsExports = true;
      if (node.declaration) fromDecl(node.declaration, true);
      for (const sp of node.specifiers || []) if (sp.local) exported.add(sp.local.name);
    } else if (node.type === "ExportDefaultDeclaration") {
      usesEsExports = true;
      fromDecl(node.declaration, true);
    } else {
      fromDecl(node, false);
      collectCommonJs(node, exported, (n) => n.expression && n.expression.type === "AssignmentExpression" ? n.expression : null,
        (l) => l.type === "MemberExpression" ? { obj: l.object.name || "", prop: l.property.name || "" } : null,
        (r) => (r.type === "ObjectExpression" ? r.properties.map((p) => p.key && p.key.name) : r.type === "Identifier" ? [r.name] : []),
        node.type === "ExpressionStatement");
    }
  }
  return { found, exported, usesEsExports };
}

async function main() {
  if (!babel && !ts) {
    try {
      const vite = createRequire(path.join(root, "package.json")).resolve("vite");
      parseAst = (await import(pathToFileURL(vite).href)).parseAst;
    } catch { /* no Vite either */ }
    if (!parseAst || typeof require("node:module").stripTypeScriptTypes !== "function") {
      process.stderr.write("Neither @babel/parser, typescript nor vite (with Node 22.13 or newer) is available in the project, so the source cannot be read.");
      process.exit(1);
    }
  }
  const out = [];
  for (const file of files) await one(file, out);
  process.stdout.write(JSON.stringify(out));
}

async function one(file, out) {
  let info;
  try {
    const text = fs.readFileSync(file, "utf8");
    info = babel ? readWithBabel(text) : ts ? readWithTypescript(text, file) : readWithStripping(text);
  } catch { return; }
  const { found, exported, usesEsExports } = info;
  for (const f of found) {
    const top = f.qual.split(".")[0];
    const cjsPublic = !usesEsExports && (exported.size === 0 || exported.has(f.name) || exported.has(top));
    if ((f.exported || exported.has(f.name) || exported.has(top) || cjsPublic) && isPublic(f.name))
      out.push({ file, name: f.name, qual: f.qual, line: f.line, size: f.size, entry: f.name === "main" });
  }
}

main();
