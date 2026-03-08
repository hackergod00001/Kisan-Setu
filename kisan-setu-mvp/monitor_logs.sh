#!/bin/bash

# Real-time log monitoring for Kisan-Setu Lambda functions
# Shows logs from all key Lambda functions

echo "🔍 Kisan-Setu Real-Time Log Monitor"
echo "===================================="
echo ""
echo "Monitoring Lambda functions..."
echo "Press Ctrl+C to stop"
echo ""

# Get region
REGION=${AWS_REGION:-ap-south-1}

# Function to tail logs with prefix
tail_logs() {
    local function_name=$1
    local prefix=$2
    
    aws logs tail "/aws/lambda/$function_name" \
        --follow \
        --region "$REGION" \
        --format short 2>&1 | \
        while IFS= read -r line; do
            echo "[$prefix] $line"
        done &
}

# Start tailing all Lambda functions
echo "📡 Starting log streams..."

# Router
tail_logs "KisanSetuMVPStack-MessageRouter8CD84FD1-h6L1m4kKPfOf" "ROUTER"

# Orchestrator
tail_logs "KisanSetuMVPStack-BedrockOrchestratorF1D5335E-8c6vEjDJfHEl" "ORCHESTRATOR"

# Document Processor
tail_logs "KisanSetuMVPStack-DocumentProcessor3D49A083-FA0T7uHrcrn3" "PROCESSOR"

# Voice Handler
tail_logs "KisanSetuMVPStack-VoiceHandlerE91162FD-Ld5zzqKxqxqx" "VOICE" 2>/dev/null || true

echo ""
echo "✅ Monitoring active. Send a WhatsApp message to see logs..."
echo ""

# Wait for all background processes
wait
