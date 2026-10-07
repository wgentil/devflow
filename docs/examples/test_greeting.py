import unittest
from greeting import greet

class GreetingTests(unittest.TestCase):
    def test_name(self):
        self.assertEqual(greet("Ada"), "Hello, Ada")
