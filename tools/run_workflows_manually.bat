python3.12 -m coverage run %~dp0/../tools/run_all_tests.py
python3.12 -m coverage report
python3.12 -m coverage html
python3.12 -m pylint %~dp0/../src
python3.12 -m mypy %~dp0/../src --ignore-missing-imports --strict
