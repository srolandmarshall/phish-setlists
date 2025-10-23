#!/bin/bash
set -e

echo "🎸 Phish Setlist Maker - Fly.io Deployment"
echo "=========================================="
echo ""

# Check if flyctl is installed
if ! command -v flyctl &> /dev/null; then
    echo "❌ flyctl is not installed"
    echo "Install it: brew install flyctl"
    exit 1
fi

# Check if logged in
if ! flyctl auth whoami &> /dev/null; then
    echo "🔑 Please login to Fly.io first:"
    flyctl auth login
fi

echo "✅ Ready to deploy!"
echo ""
echo "This will:"
echo "  1. Create a Postgres database (free tier)"
echo "  2. Deploy your FastAPI app (free tier)"
echo "  3. Cost: \$0-5/month"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
fi

# Create Postgres if it doesn't exist
echo ""
echo "📊 Creating Postgres database..."
if flyctl postgres list | grep -q "phish-setlist-db"; then
    echo "✅ Database already exists"
else
    flyctl postgres create \
        --name phish-setlist-db \
        --region iad \
        --initial-cluster-size 1 \
        --vm-size shared-cpu-1x \
        --volume-size 1
fi

# Launch or deploy app
echo ""
echo "🚀 Deploying app..."
if flyctl apps list | grep -q "phish-setlist-maker"; then
    flyctl deploy
else
    flyctl launch --name phish-setlist-maker --region iad --now
    flyctl postgres attach phish-setlist-db
fi

echo ""
echo "✨ Deployment complete!"
echo ""
echo "Your app is live at:"
flyctl status | grep "Hostname" || echo "Run: flyctl status"
echo ""
echo "Test it:"
echo "  curl https://phish-setlist-maker.fly.dev/health"
echo "  curl https://phish-setlist-maker.fly.dev/generate"
echo ""
echo "View logs:"
echo "  flyctl logs"
