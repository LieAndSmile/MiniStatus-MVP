#!/bin/bash
# Simple API test script for MiniStatus

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  MiniStatus API Test Script"
echo "=========================================="
echo ""

# Get server IP (default to localhost)
SERVER_IP="${1:-127.0.0.1}"
PORT="${2:-5000}"
BASE_URL="http://${SERVER_IP}:${PORT}"

echo "Testing API at: ${BASE_URL}"
echo ""

# Get API key from .env file
if [ -f .env ]; then
    API_KEY=$(grep "^API_KEY=" .env | cut -d '=' -f2 | tr -d '"' | tr -d "'")
    if [ -z "$API_KEY" ]; then
        echo -e "${RED}Error: API_KEY not found in .env file${NC}"
        echo "Please check your .env file and make sure API_KEY is set."
        exit 1
    fi
else
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please make sure you're running this from the MiniStatus directory."
    exit 1
fi

echo -e "${YELLOW}Using API Key: ${API_KEY}${NC}"
echo ""

# Test 1: Report a service status
echo "Test 1: Reporting service status..."
echo "-----------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "${BASE_URL}/api/report" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"name":"test-service","status":"up","description":"Test service from API"}')

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Success!${NC}"
    echo "Response: $BODY"
else
    echo -e "${RED}✗ Failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $BODY"
fi
echo ""

# Test 2: Report another service with different status
echo "Test 2: Reporting another service..."
echo "-----------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "${BASE_URL}/api/report" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"name":"test-service-2","status":"down","description":"Another test service"}')

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Success!${NC}"
    echo "Response: $BODY"
else
    echo -e "${RED}✗ Failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $BODY"
fi
echo ""

# Test 3: Test with wrong API key (should fail)
echo "Test 3: Testing with wrong API key (should fail)..."
echo "-----------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "${BASE_URL}/api/report" \
  -H "X-API-Key: wrong-key-12345" \
  -H "Content-Type: application/json" \
  -d '{"name":"test","status":"up"}')

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')

if [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "403" ]; then
    echo -e "${GREEN}✓ Correctly rejected invalid API key!${NC}"
    echo "Response: $BODY"
else
    echo -e "${YELLOW}⚠ Unexpected response (HTTP $HTTP_CODE)${NC}"
    echo "Response: $BODY"
fi
echo ""

echo "=========================================="
echo "  Tests Complete!"
echo "=========================================="
echo ""
echo "Check your admin dashboard to see if the test services appeared:"
echo "  ${BASE_URL}/admin/dashboard"
echo ""

