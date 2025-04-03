#!/bin/bash
set -e

echo "⚙️ Installing Python + Node dependencies..."

# Backend dependencies
if [ -f /workspaces/bnc-webui/backend/requirements.txt ]; then
  pip install -r /workspaces/bnc-webui/backend/requirements.txt
else
  echo "📦 Skipped: backend/requirements.txt not found"
fi

# Frontend dependencies
if [ -f /workspaces/bnc-webui/frontend/package.json ]; then
  npm install --prefix /workspaces/bnc-webui/frontend
else
  echo "📦 Skipped: frontend/package.json not found"
fi

echo "🚀 Starting backend and frontend..."

# Start backend
(
  cd /workspaces/bnc-webui/backend
  echo "▶️ Starting FastAPI backend..."
  nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > /tmp/backend.log 2>&1 &
)

# Start frontend with logging
(
  cd /workspaces/bnc-webui/frontend
  echo "▶️ Starting React frontend..."

  {
    echo "ℹ️ Launching npm run dev..."
    npm run dev
  } > /tmp/frontend.log 2>&1 &
)
