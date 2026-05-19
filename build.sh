#!/bin/bash
# Script de construcción completo para Aethelgard Mini App
# Ejecutar: bash build.sh

set -e
echo "🏗️  Construyendo Aethelgard Mini App..."

echo "📦 Instalando dependencias Python..."
pip install -r backend/requirements.txt

echo "⚛️  Construyendo frontend React..."
cd frontend
npm install
npm run build
cd ..

echo "📁 Copiando build al backend..."
cp -r frontend/dist backend/dist

echo "✅ Build completado. Listo para desplegar en Render."
echo "👉 Ejecuta: python backend/main.py"
