"""
Handle some discrepancies between the unittest version that ships with Python 2.7 and the newer 3.x
releases without having to deal with backports and such.

"""
import unittest


if not hasattr(unittest.TestCase, "assertRegex"):
    unittest.TestCase.assertRegex = unittest.TestCase.assertRegexpMatches

if not hasattr(unittest.TestCase, "assertNotRegex") and \
        hasattr(unittest.TestCase, "assertNotRegexpMatches"):
    unittest.TestCase.assertNotRegex = unittest.TestCase.assertNotRegexpMatches
