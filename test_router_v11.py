"""Tests for dynamic tool mapping and discovery helpers."""
import unittest
from artcraft_unified_router import Router

class DummyChild:
    ready = True
    tools = [{"name": "list_commands", "description": "Enumerate commands",
              "inputSchema": {"type": "object", "properties": {}}}]
    name = "GridCraft"

class DiscoveryTests(unittest.TestCase):
    def test_namespaced_mapping(self):
        router = Router({"apps": {}, "primary_app": "SolidCraft"})
        router.apps["GridCraft"] = DummyChild()
        router.rebuild()
        self.assertIn("gridcraft__list_commands", router.mapping)
        self.assertNotIn("list_commands", router.mapping)

    def test_primary_alias(self):
        router = Router({"apps": {}, "primary_app": "GridCraft"})
        router.apps["GridCraft"] = DummyChild()
        router.rebuild()
        self.assertIn("list_commands", router.mapping)

    def test_catalog_exposes_namespaced_tool(self):
        router = Router({"apps": {}, "primary_app": "SolidCraft"})
        router.apps["GridCraft"] = DummyChild()
        router.rebuild()
        names = [tool["name"] for tool in router.list_tools()]
        self.assertIn("gridcraft__list_commands", names)

if __name__ == "__main__":
    unittest.main()
