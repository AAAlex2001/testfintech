#!/bin/bash
set -e

case "$1" in
    web)
        echo "START WEB"
        exec python src/main.py
        ;;
    *)
        exec "$@"
        ;;
esac
