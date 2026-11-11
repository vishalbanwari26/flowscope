// A Vite plugin for Vitest: wrap every named function of the project's own files so it
// reports when it starts and ends. It works on the JavaScript that Vite has already made
// from TypeScript, and only inserts text on the same line, so line numbers do not move.
import { readFileSync } from "node:fs";

const FUNCTIONS = new Set(["FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"]);

function nameFor(node, hint) {
  if ((node.type === "FunctionDeclaration" || node.type === "FunctionExpression") && node.id) return node.id.name;
  return hint || null;                    // anonymous: it counts under the function around it
}

function keyName(key, computed) {
  if (computed || !key) return null;
  if (key.type === "Identifier") return key.name;
  if (key.type === "Literal") return String(key.value);
  if (key.type === "PrivateIdentifier") return "#" + key.name;
  return null;
}

export function instrument(code, mod, parseAst) {
  const ast = parseAst(code);
  const inserts = [];                     // [position, text]
  const enter = `const __fs=globalThis.__flowscope&&globalThis.__flowscope.enter(${JSON.stringify(mod)},`;
  const close = "}finally{if(__fs)globalThis.__flowscope.exit(__fs)}";

  function wrap(fn, name) {
    const body = fn.body;
    if (body.type === "BlockStatement") {
      inserts.push([body.start + 1, `${enter}${JSON.stringify(name)});try{`]);
      inserts.push([body.end - 1, close]);
    } else {
      const arrow = code.lastIndexOf("=>", body.start);
      inserts.push([arrow + 2, `{${enter}${JSON.stringify(name)});try{return `]);
      inserts.push([fn.end, `${close}}`]);
    }
  }

  function walk(node, parent, hint) {
    if (!node || typeof node.type !== "string") return;
    let childHint = null;
    switch (node.type) {
      case "VariableDeclarator":
        childHint = node.id.type === "Identifier" ? node.id.name : null;
        walk(node.init, node, childHint);
        return;
      case "Property":
      case "MethodDefinition":
      case "PropertyDefinition":
        walk(node.value, node, keyName(node.key, node.computed));
        return;
      case "AssignmentExpression":
        walk(node.right, node, node.left.type === "MemberExpression" && !node.left.computed
          ? node.left.property.name : (node.left.type === "Identifier" ? node.left.name : null));
        return;
    }
    if (FUNCTIONS.has(node.type)) {
      const name = nameFor(node, hint);
      if (name) wrap(node, name);
    }
    for (const key of Object.keys(node)) {
      if (key === "type" || key === "start" || key === "end") continue;
      const v = node[key];
      if (Array.isArray(v)) for (const c of v) walk(c, node, null);
      else if (v && typeof v === "object") walk(v, node, null);
    }
  }
  walk(ast, null, null);
  inserts.sort((a, b) => b[0] - a[0]);
  let out = code;
  for (const [pos, text] of inserts) out = out.slice(0, pos) + text + out.slice(pos);
  return out;
}

export function flowscopePlugin({ parseAst, modulesFile, runtimeFile }) {
  const names = JSON.parse(readFileSync(modulesFile, "utf8"));
  return {
    name: "flowscope",
    enforce: "post",
    config() {
      return { test: { globals: true, setupFiles: [runtimeFile] } };
    },
    transform(code, id) {
      const mod = names[id.split("?")[0]];
      if (!mod) return null;
      try { return { code: instrument(code, mod, parseAst), map: null }; } catch { return null; }
    },
  };
}
