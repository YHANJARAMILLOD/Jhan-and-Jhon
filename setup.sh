#!/bin/bash

echo "Creando entorno virtual..."
python3 -m venv .venv

echo "Activando entorno virtual..."
source .venv/bin/activate

echo "Actualizando pip..."
python -m pip install --upgrade pip

echo "Instalando dependencias..."
pip install -r requirements.txt

echo ""
echo "=================================="
echo "Setup completado correctamente"
echo "=================================="

