"""find_functions: đếm dòng và tham số của hàm có tên, không AST."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "tools"))

from funcs import count_params, find_functions, strip_code  # noqa: E402


def by_name(text, lang="dart"):
    return {f["name"]: f for f in find_functions(text, lang)}


class StripCodeTest(unittest.TestCase):
    def test_keeps_offsets_and_lines(self):
        src = "a();\n// bỏ ( đi\nb('chuỗi có ) ngoặc');\n"
        out = strip_code(src, "dart")
        self.assertEqual(len(out), len(src))
        self.assertEqual(out.count("\n"), src.count("\n"))
        self.assertNotIn("bỏ", out)
        self.assertNotIn("ngoặc", out)
        self.assertIn("b(", out)

    def test_block_comment_and_unterminated_string(self):
        self.assertNotIn("x", strip_code("/* x */\n", "dart"))
        self.assertIn("f(", strip_code("var s = 'chưa đóng\nf();\n", "dart"))


class CountParamsTest(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(count_params(""), 0)
        self.assertEqual(count_params("int a"), 1)
        self.assertEqual(count_params("int a, {String? b, int c = 1}"), 3)
        self.assertEqual(count_params("Map<String, int> m, List<int> l"), 2)
        self.assertEqual(count_params("void Function(int, int) cb, int x"), 2)
        self.assertEqual(count_params("this.a, this.b, [this.c]"), 3)


class FindFunctionsDartTest(unittest.TestCase):
    def test_method_body_and_arrow(self):
        src = """class A {
  int plus(int a, int b) {
    return a + b;
  }

  String name() => 'x';
}
"""
        fns = by_name(src)
        self.assertEqual(fns["plus"]["lines"], 3)
        self.assertEqual(fns["plus"]["params"], 2)
        self.assertEqual(fns["name"]["lines"], 1)
        self.assertEqual(fns["name"]["params"], 0)

    def test_constructor_is_marked(self):
        src = "class Foo {\n  const Foo({this.a, this.b, this.c});\n  final int a, b, c;\n}\n"
        foo = by_name(src)["Foo"]
        self.assertTrue(foo["ctor"])
        self.assertEqual(foo["params"], 3)

    def test_calls_and_closures_are_not_functions(self):
        src = """class W {
  Widget build(BuildContext context) {
    return Column(children: [
      Text('a'),
      Builder(builder: (c) => Text('b')),
    ]);
  }
}
"""
        self.assertEqual(sorted(by_name(src)), ["build"])

    def test_nested_named_function_counted(self):
        src = "void outer() {\n  int inner(int a) {\n    return a;\n  }\n  inner(1);\n}\n"
        self.assertEqual(sorted(by_name(src)), ["inner", "outer"])

    def test_annotation_with_args_not_a_function(self):
        src = "@Named('x')\n@LazySingleton(as: Repo)\nclass RepoImpl implements Repo {\n  void go() {}\n}\n"
        self.assertEqual(sorted(by_name(src)), ["go"])

    def test_initializer_list_body_measured(self):
        src = "class P {\n  P(int a) : b = a {\n    print(b);\n  }\n  int b;\n}\n"
        self.assertEqual(by_name(src)["P"]["lines"], 3)

    def test_if_and_for_not_functions(self):
        src = "void f() {\n  if (a) { g(); }\n  for (var x in y) { h(x); }\n  while (a) {}\n}\n"
        self.assertEqual(sorted(by_name(src)), ["f"])


class FindFunctionsOtherLangsTest(unittest.TestCase):
    def test_python_block_by_indent(self):
        src = "def a(x, y=1):\n    if x:\n        return y\n    return 0\n\n\ndef b():\n    pass\n"
        fns = by_name(src, "py")
        self.assertEqual(fns["a"]["lines"], 4)
        self.assertEqual(fns["a"]["params"], 2)
        self.assertEqual(fns["b"]["lines"], 2)

    def test_python_method_drops_self(self):
        src = "class C:\n    def m(self, a):\n        return a\n"
        self.assertEqual(by_name(src, "py")["m"]["params"], 1)

    def test_kotlin_requires_fun_keyword(self):
        src = "class C {\n    fun go(a: Int, b: Int): Int {\n        return a + b\n    }\n}\n\nval x = listOf(1).map { it }\n"
        fns = by_name(src, "kotlin")
        self.assertEqual(sorted(fns), ["go"])
        self.assertEqual(fns["go"]["params"], 2)

    def test_kotlin_expression_body(self):
        src = "fun sum(a: Int, b: Int) = a + b\n"
        self.assertEqual(by_name(src, "kotlin")["sum"]["lines"], 1)

    def test_swift_requires_func_keyword(self):
        src = "struct S {\n    func go(_ a: Int, b: Int) -> Int {\n        return a\n    }\n}\nlet v = arr.map { $0 }\n"
        fns = by_name(src, "swift")
        self.assertEqual(sorted(fns), ["go"])
        self.assertEqual(fns["go"]["params"], 2)

    def test_ts_function_and_method(self):
        src = "export function f(a: number, b: string) {\n  return a;\n}\nclass C {\n  m(x) { return x; }\n}\n"
        self.assertEqual(sorted(by_name(src, "ts")), ["f", "m"])

    def test_unterminated_file_does_not_hang(self):
        self.assertIsInstance(find_functions("void f(int a) {\n  g(", "dart"), list)


if __name__ == "__main__":
    unittest.main()
