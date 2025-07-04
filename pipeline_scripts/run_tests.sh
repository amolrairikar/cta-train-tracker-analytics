#!/bin/bash

echo "Running unit tests..."
if ! pipenv run coverage run --source=lambdas -m unittest discover -s tests/unit -v; then
    echo "Unit tests failed!"
    exit 1
fi
mv .coverage .coverage.unit

echo "Running component tests..."
if ! pipenv run coverage run --source=lambdas -m unittest discover -s tests/component -v; then
    echo "Component tests failed!"
    exit 1
fi
mv .coverage .coverage.component

echo "Combining coverage data..."
pipenv run coverage combine .coverage.unit .coverage.component

echo "Generating coverage report..."
pipenv run coverage report --omit=lambdas/write_train_lines/retry_api_exceptions.py --fail-under=80

echo "Test execution complete!"