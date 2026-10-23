"""Basic router unit tests. No ArtCraft installation required."""
import unittest
from artcraft_unified_router import Router, read_message
import io

class RouterTests(unittest.TestCase):
    def test_empty_catalog(self):
        router = Router({"apps": {}})
        self.assertEqual(len(router.list_tools()), 6)

    def test_status(self):
        router = Router({"apps": {}})
        self.assertIn("content", router.call_tool("artcraft_status", {}))

    def test_unknown_tool(self):
        router = Router({"apps": {}})
        with self.assertRaises(KeyError):
            router.call_tool("missing_tool", {})

    def test_json_line(self):
        packet = io.BytesIO(b'{"jsonrpc":"2.0","id":1}\n')
        self.assertEqual(read_message(packet)["id"], 1)

if __name__ == "__main__":
    unittest.main()
