#!/bin/sh
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
# SIGINT triggers Python atexit more reliably than SIGTERM under uvicorn
kill -INT "$API_PID" 2>/dev/null || true
sleep 3
if kill -0 "$API_PID" 2>/dev/null; then
    kill -TERM "$API_PID" 2>/dev/null || true
fi
wait "$API_PID" 2>/dev/null || true

echo "[coverage] Coverage data files in $COV_DATA_DIR:"
ls -la "$COV_DATA_DIR"/ 2>&1 || true

# Объединяем параллельные файлы покрытия и генерируем отчёт из /app
cd /app

# Проверяем наличие файлов данных перед combine
COV_FILES=$(ls "$COV_DATA_DIR"/.coverage.* 2>/dev/null || true)
if [ -z "$COV_FILES" ]; then
    echo "[coverage] ERROR: No coverage data files found in $COV_DATA_DIR"
    echo "[coverage] Expected files matching: $COV_DATA_DIR/.coverage.*"
    exit 1
fi

echo "[coverage] Combining coverage data..."
python -m coverage combine --rcfile=/app/ab_test_platform/.coveragerc $COV_FILES

if [ ! -f /app/.coverage ]; then
    echo "[coverage] ERROR: coverage combine did not produce /app/.coverage"
    exit 1
fi

echo ""
echo "========================= Coverage Report ========================="
python -m coverage report --rcfile=/app/ab_test_platform/.coveragerc
echo "=================================================================="

python -m coverage html --rcfile=/app/ab_test_platform/.coveragerc -d /html
echo "[coverage] HTML report saved to coverage_html/index.html"