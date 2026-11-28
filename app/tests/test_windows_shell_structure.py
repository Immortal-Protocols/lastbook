"""Keep the Windows WebView2 host's runtime entry points intact on every platform."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class WindowsShellStructure(unittest.TestCase):
    def test_webview2_shell_keeps_its_host_lifecycle(self):
        source = (ROOT / 'app' / 'shell_windows.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        self.assertIn('Frame', classes)
        self.assertIn('Shell', classes)
        shell_methods = {
            node.name for node in classes['Shell'].body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertTrue(
            {'__init__', 'build', 'start_runtime', 'on_ready', 'on_request', 'on_nav', 'on_download'}
            <= shell_methods,
            f'Windows WebView2 host lifecycle is incomplete: {sorted(shell_methods)}',
        )
        self.assertIn('CoreWebView2Environment.CreateAsync', source)
        self.assertIn('WebResourceRequested', source)
