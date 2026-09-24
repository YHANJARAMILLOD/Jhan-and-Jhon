@echo off

echo Creando entorno virtual...
python -m venv .venv

echo Activando entorno virtual...
call .venv\Scripts\activate

echo Actualizando pip...
python -m pip install --upgrade pip

echo Instalando dependencias...
pip install -r requirements.txt

echo Descargando modelos de Ollama...
ollama pull qwen3:8b
ollama pull bge-m3

echo.
echo ==================================
echo Setup completado correctamente
echo ==================================
pause
