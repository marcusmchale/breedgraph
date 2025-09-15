python -m pytest tests/unit
python -m pytest tests/integration

service mailhog start
python -m pytest tests/e2e