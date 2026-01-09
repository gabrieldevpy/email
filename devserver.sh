#!/bin/sh
source .venv/bin/activate
# CORREÇÃO: Usar um valor padrão para a porta se a variável $PORT não estiver definida.
# Isso evita o erro quando o script é executado em um ambiente sem a variável $PORT.
FLASK_PORT=${PORT:-8080}
python -u -m flask --app app run --port=$FLASK_PORT --debug
