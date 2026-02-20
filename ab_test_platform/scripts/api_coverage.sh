#!/bin/bash
# Запускает API под coverage.py, ждёт окончания тестов, генерирует отчёт.

DONE_FILE="/coverage/pytest_done"
COV_DATA_DIR="/coverage"

# Игнорируем внешний SIGTERM — завершим работу сами после репорта
trap '' TERM INT

echo "[coverage] Starting API under coverage.py..."
python -m coverage run \
    --rcfile=/app/ab_test_platform/.coveragerc \
    --data-file="$COV_DATA_DIR/.coverage" \
    -m ab_test_platform.src.main &
API_PID=$!

# Ждём сигнального файла от test-runner
while [ ! -f "$DONE_FILE" ]; do
    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo "[coverage] API process died unexpectedly"
        exit 1
    fi
    sleep 1
done

echo "[coverage] Tests done signal received. Stopping API..."
kill -TERM "$API_PID" 2>/dev/null || true
wait "$API_PID" 2>/dev/null || true

# Объединяем параллельные файлы покрытия и генерируем отчёт из /app
cd /app
python -m coverage combine --rcfile=/app/ab_test_platform/.coveragerc "$COV_DATA_DIR"/.coverage* 2>/dev/null || true

echo ""
echo "========================= Coverage Report ========================="
python -m coverage report --rcfile=/app/ab_test_platform/.coveragerc
echo "=================================================================="

python -m coverage html --rcfile=/app/ab_test_platform/.coveragerc -d /html
echo "[coverage] HTML report saved to coverage_html/index.html"
