#!/bin/bash

echo "Starting Controller Server on port 8081..."
python3 controller_server.py &
CONTROLLER_PID=$!

echo "Starting Web Server on port 3700..."
python3 -m http.server 3700 &
WEB_PID=$!

echo "=================================================="
echo "Bridge is running!"
echo "Open your browser to: http://localhost:3700"
echo "=================================================="
echo "Press Ctrl+C to stop all servers."

# Trap Ctrl+C to kill background processes
trap "kill $CONTROLLER_PID $WEB_PID; exit" INT

# Keep script running
wait
