import os
import sys
import unittest

if __name__ == "__main__":
    suite = unittest.TestSuite()

    path_to_tests = os.path.join(os.path.dirname(__file__), "../tests")
    tests = unittest.TestLoader().discover(path_to_tests)
    suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=3, buffer=True)
    result = runner.run(suite)

    sys.exit(not result.wasSuccessful())
