# Fly.io Deployment Guide

Deploy the Phish Setlist Maker API to Fly.io for **under $10/month** (likely $0-5/month with free tier).

## Prerequisites

1. **Fly.io account**: Sign up at https://fly.io/
2. **flyctl CLI**: Install it
   ```bash
   # macOS
   brew install flyctl
   
   # Or use install script
   curl -L https://fly.io/install.sh | sh
   ```
3. **Login to Fly.io**
   ```bash
   flyctl auth login
   ```

## Cost Breakdown (Free Tier)

Fly.io provides generous free allowances:
- ✅ **3 shared-cpu VMs** (256MB RAM each) - FREE
- ✅ **3GB persistent storage** - FREE  
- ✅ **160GB bandwidth/month** - FREE

**Expected cost: $0-5/month** for this app on free tier!

If you exceed free tier:
- Additional shared-cpu-1x: ~$2/month
- 1GB Postgres storage: ~$0.15/month

## Quick Deploy (5 minutes)

### Step 1: Create Postgres Database

```bash
cd /Users/smarshall/Development/phish-setlist-maker

# Create a Postgres cluster (uses free tier)
flyctl postgres create \
  --name phish-setlist-db \
  --region iad \
  --initial-cluster-size 1 \
  --vm-size shared-cpu-1x \
  --volume-size 1

# This creates a DATABASE_URL secret automatically
```

### Step 2: Launch the App

```bash
# Initialize Fly app (creates fly.toml if needed)
flyctl launch \
  --name phish-setlist-maker \
  --region iad \
  --no-deploy

# Attach database (sets DATABASE_URL secret)
flyctl postgres attach phish-setlist-db

# Deploy!
flyctl deploy
```

That's it! Your app is live at: `https://phish-setlist-maker.fly.dev`

## Manual Setup (if needed)

If you want more control:

```bash
# 1. Create app
flyctl apps create phish-setlist-maker

# 2. Create Postgres
flyctl postgres create --name phish-setlist-db --region iad

# 3. Attach database
flyctl postgres attach phish-setlist-db -a phish-setlist-maker

# 4. Deploy
flyctl deploy
```

## Import Your Data

After deployment, import your existing database:

```bash
# Get database connection string
flyctl postgres connect -a phish-setlist-db

# Or connect from local machine
flyctl proxy 5432 -a phish-setlist-db

# In another terminal, import your dump
psql "postgres://postgres:PASSWORD@localhost:5432/phish_setlist_maker" < your_dump.sql
```

## Configuration

### Environment Variables

Set additional env vars if needed:

```bash
flyctl secrets set LOG_LEVEL=info
flyctl secrets set SOME_API_KEY=xxx
```

Database URL is auto-set when you attach Postgres.

### Scale Configuration

The default `fly.toml` is optimized for free tier:
- **auto_stop_machines**: App sleeps when idle (saves money!)
- **auto_start_machines**: Wakes up on request (~1s cold start)
- **min_machines_running = 0**: No always-on machines
- **256MB RAM**: Fits in free tier

For production traffic, upgrade:

```bash
# Always keep 1 machine running (no cold starts)
flyctl scale count 1 --yes

# Increase memory if needed
flyctl scale memory 512

# Add more regions for redundancy
flyctl regions add ord lax
```

## Monitoring

```bash
# View live logs (streaming)
flyctl logs -a phish-setlist-maker

# View recent logs (no tail)
flyctl logs -a phish-setlist-maker --no-tail

# Check status
flyctl status -a phish-setlist-maker

# SSH into machine
flyctl ssh console -a phish-setlist-maker

# Monitor metrics
flyctl dashboard metrics -a phish-setlist-maker
```

## Testing

```bash
# Get your app URL
flyctl info

# Test endpoints
curl https://phish-setlist-maker.fly.dev/health
curl https://phish-setlist-maker.fly.dev/generate
curl https://phish-setlist-maker.fly.dev/docs
```

## Cost Optimization Tips

1. **Use auto-stop/start** (default in fly.toml) - Sleeps when idle
2. **Single region** - Avoid multi-region unless needed
3. **Shared CPU** - Plenty fast for this app
4. **256MB RAM** - Works fine for most requests
5. **1GB Postgres volume** - Your DB is small

## Troubleshooting

### App won't start

```bash
# Check logs
flyctl logs

# Check if DB is attached
flyctl secrets list
# Should see DATABASE_URL
```

### Database connection issues

```bash
# Verify DB is running
flyctl postgres list

# Check connection from app
flyctl ssh console
env | grep DATABASE_URL
```

### Out of memory

```bash
# Increase to 512MB
flyctl scale memory 512
```

### Slow cold starts

```bash
# Keep 1 machine always running
flyctl scale count 1
# This uses ~$2/month
```

## Updating the App

```bash
# Make code changes, then:
flyctl deploy

# Auto-deployed with zero downtime!
```

## Custom Domain (Optional)

```bash
# Add your domain
flyctl certs add yourdomain.com

# Add DNS records (shown in command output)
# A record: your-app-name.fly.dev
# AAAA record: (IPv6 shown in output)
```

## Cleanup/Uninstall

```bash
# Delete app
flyctl apps destroy phish-setlist-maker

# Delete database
flyctl apps destroy phish-setlist-db
```

## Comparison with AWS

| Feature | Fly.io | AWS App Runner |
|---------|--------|----------------|
| Free tier | ✅ 3 VMs + Postgres | ❌ None |
| Monthly cost | $0-5 | $20-25 |
| Setup time | 5 min | 20 min |
| Cold starts | ~1s (if auto-stop) | ~5s |
| Custom domains | Free | Free |

## Next Steps

- [ ] Import your production database
- [ ] Set up GitHub Actions for CI/CD
- [ ] Add custom domain
- [ ] Monitor usage in Fly.io dashboard
- [ ] Set up alerts for errors

## Support

- Docs: https://fly.io/docs
- Community: https://community.fly.io
- Pricing: https://fly.io/docs/about/pricing
