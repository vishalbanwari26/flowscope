// Babel plugin: wrap every named function of the project's own files so it reports when
// it starts and ends. The Python hook does the same with sys.setprofile.
// FLOWSCOPE_MODULES names a JSON file that maps each project file to its module name;
// a file that is not in it (a library, a test) is left alone.
const fs = require("fs");

let names = null;
function moduleOf(file) {
  if (names === null) {
    try { names = JSON.parse(fs.readFileSync(process.env.FLOWSCOPE_MODULES, "utf8")); } catch { names = {}; }
  }
  return names[file];
}

module.exports = function flowscope(api) {
  const t = api.types;
  const template = api.template;
  const open = template.statement(
    `const __fs = globalThis.__flowscope && globalThis.__flowscope.enter(MOD, NAME);`);
  const close = template.statement(
    `try { BODY } finally { if (__fs) globalThis.__flowscope.exit(__fs); }`);

  function nameOf(p) {
    const n = p.node, parent = p.parent;
    if (n.id && n.id.name) return n.id.name;
    if (t.isClassMethod(n) || t.isObjectMethod(n) || t.isClassPrivateMethod(n)) {
      const k = n.key;
      if (t.isIdentifier(k)) return k.name;
      if (t.isStringLiteral(k)) return k.value;
      if (t.isPrivateName(k)) return "#" + k.id.name;
      return null;
    }
    if (t.isVariableDeclarator(parent) && t.isIdentifier(parent.id)) return parent.id.name;
    if ((t.isClassProperty(parent) || t.isObjectProperty(parent)) && t.isIdentifier(parent.key)) return parent.key.name;
    if (t.isAssignmentExpression(parent) && t.isMemberExpression(parent.left) && t.isIdentifier(parent.left.property))
      return parent.left.property.name;
    return null;                       // anonymous: it counts under the function around it
  }

  return {
    name: "flowscope",
    visitor: {
      Function(p, state) {
        const mod = moduleOf(state.filename);
        if (!mod || p.node.__flowscope) return;
        const name = nameOf(p);
        if (!name) return;
        p.node.__flowscope = true;
        if (!t.isBlockStatement(p.node.body)) p.node.body = t.blockStatement([t.returnStatement(p.node.body)]);
        const body = p.node.body;
        const directives = body.directives;
        body.directives = [];
        const inner = t.blockStatement(body.body);
        body.body = [open({ MOD: t.stringLiteral(mod), NAME: t.stringLiteral(name) }), close({ BODY: inner.body })];
        body.directives = directives;
      },
    },
  };
};
