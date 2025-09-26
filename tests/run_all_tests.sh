. ./instance/envars.sh
python -m pytest tests/unit

python scripts/setup_initial_data.py
python -m pytest tests/integration

if systemctl is-active mailhog; then
  python scripts/setup_initial_data.py
  python -m pytest tests/e2e
else
  echo "Start mailhog service to run e2e tests"
fi

