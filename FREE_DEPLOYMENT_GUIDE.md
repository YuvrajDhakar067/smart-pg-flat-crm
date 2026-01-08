# 🚀 Free Deployment Guide - Smart PG & Flat Management CRM

Deploy your app for **FREE** with automatic deployments when you push to GitHub!

---

## 📋 What You'll Get

| Service | Provider | Cost |
|---------|----------|------|
| Web Hosting | Render.com | **FREE** |
| PostgreSQL Database | Render.com | **FREE** (90 days) |
| SSL Certificate | Render.com | **FREE** |
| Auto-Deploy from GitHub | Render.com | **FREE** |

---

## 🛠️ Step-by-Step Deployment

### Step 1: Push Code to GitHub

```bash
# If you haven't initialized git yet
cd "/Users/yuvrajdhakar/Smart PG & Flat Management CRM"
git init

# Create .gitignore (if not exists)
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
ENV/

# Django
*.log
local_settings.py
db.sqlite3
media/
staticfiles/

# Environment
.env
*.env

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
EOF

# Add all files
git add .

# Commit
git commit -m "Initial commit - Smart PG CRM"

# Create repository on GitHub (go to github.com/new)
# Then push:
git remote add origin https://github.com/YOUR_USERNAME/smart-pg-crm.git
git branch -M main
git push -u origin main
```

### Step 2: Create Render Account

1. Go to **[render.com](https://render.com)**
2. Click **"Get Started for Free"**
3. Sign up with your **GitHub account** (recommended for easy connection)

### Step 3: Create PostgreSQL Database

1. In Render Dashboard, click **"New +"** → **"PostgreSQL"**
2. Fill in:
   - **Name:** `smartpg-db`
   - **Database:** `smart_pg`
   - **User:** `smartpg`
   - **Region:** Singapore (or closest to you)
   - **Plan:** **Free**
3. Click **"Create Database"**
4. **IMPORTANT:** Copy the **"Internal Database URL"** - you'll need it!

   It looks like: `postgres://smartpg:xxxx@dpg-xxx.singapore-postgres.render.com/smart_pg`

### Step 4: Deploy Web Service

1. Click **"New +"** → **"Web Service"**
2. Select **"Build and deploy from a Git repository"**
3. Connect your GitHub repository
4. Configure:

   | Field | Value |
   |-------|-------|
   | Name | `smartpg-web` |
   | Region | Same as database |
   | Branch | `main` |
   | Runtime | `Python 3` |
   | Build Command | `./build.sh` |
   | Start Command | `gunicorn smart_pg.wsgi:application` |
   | Plan | **Free** |

5. Click **"Advanced"** and add **Environment Variables**:

   | Key | Value |
   |-----|-------|
   | `DJANGO_SETTINGS_MODULE` | `smart_pg.settings_render` |
   | `DJANGO_SECRET_KEY` | Click "Generate" to create a secure key |
   | `DATABASE_URL` | Paste the Internal Database URL from Step 3 |
   | `PYTHON_VERSION` | `3.9.18` |

6. Click **"Create Web Service"**

### Step 5: Wait for Deployment

- Render will automatically:
  - Clone your repository
  - Install dependencies
  - Run migrations
  - Collect static files
  - Start the server

- This takes **3-5 minutes** for the first deploy

### Step 6: Create Admin User

After deployment succeeds:

1. Go to your web service in Render Dashboard
2. Click **"Shell"** tab
3. Run:

```bash
python manage.py createsuperuser
```

4. Enter your admin username, email, and password

### Step 7: Access Your App! 🎉

Your app is now live at:
```
https://smartpg-web.onrender.com
```

(Or whatever name you chose)

---

## 🔄 Auto-Deploy on GitHub Push

**It's already set up!** Every time you push to GitHub:

```bash
git add .
git commit -m "Your changes"
git push
```

Render automatically:
1. Detects the push
2. Pulls the latest code
3. Runs build.sh
4. Restarts the server

**No manual deployment needed!**

---

## ⚙️ Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DJANGO_SETTINGS_MODULE` | ✅ | `smart_pg.settings_render` |
| `DJANGO_SECRET_KEY` | ✅ | Click "Generate" in Render |
| `DATABASE_URL` | ✅ | From your PostgreSQL service |
| `PYTHON_VERSION` | ✅ | `3.9.18` |
| `DJANGO_ALLOWED_HOSTS` | ❌ | Auto-detected by Render |
| `DJANGO_DEBUG` | ❌ | Default: `False` |

---

## 🔧 Troubleshooting

### Build Failed?

1. Check the **Logs** tab in Render
2. Common issues:
   - Missing dependency in `requirements.txt`
   - Syntax error in Python files
   - Wrong Python version

### Database Connection Error?

1. Make sure `DATABASE_URL` is set correctly
2. Check if database is still in "Creating" status
3. Use the **Internal** URL, not External

### Static Files Not Loading?

Run manually via Shell:
```bash
python manage.py collectstatic --noinput
```

### 502 Bad Gateway?

1. Check if build completed successfully
2. Look at logs for errors
3. Make sure `gunicorn` is in requirements.txt

---

## 💡 Tips for Free Tier

### Free Tier Limitations

- **Web Service:** Spins down after 15 minutes of inactivity
  - First request after sleep takes ~30 seconds
  - Use a free uptime monitor like [UptimeRobot](https://uptimerobot.com) to keep it awake

- **Database:** Free for 90 days
  - After 90 days, upgrade to paid ($7/month) or create new database

### Keep Your App Awake (Free)

1. Go to [uptimerobot.com](https://uptimerobot.com)
2. Create free account
3. Add monitor:
   - **URL:** `https://your-app.onrender.com/health/`
   - **Interval:** 5 minutes
4. This pings your app every 5 minutes, keeping it awake!

---

## 🔐 Custom Domain (Optional)

1. In Render Dashboard → Your Web Service → **Settings**
2. Click **"Add Custom Domain"**
3. Add your domain (e.g., `app.yourdomain.com`)
4. Update your DNS:
   - Add CNAME record pointing to `your-app.onrender.com`
5. SSL certificate is automatically provisioned!

---

## 📊 Monitoring

### Health Check Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health/` | Basic check - is app running? |
| `/health/ready/` | Database connection check |
| `/health/deep/` | Full system status |

### View Logs

1. Render Dashboard → Your Service → **Logs**
2. Real-time logs with request IDs for debugging

---

## 🆘 Need Help?

1. **Render Docs:** [render.com/docs](https://render.com/docs)
2. **Django Docs:** [docs.djangoproject.com](https://docs.djangoproject.com)
3. **Community:** [community.render.com](https://community.render.com)

---

## ✅ Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] Render account created
- [ ] PostgreSQL database created
- [ ] Web service created
- [ ] Environment variables set
- [ ] Build successful
- [ ] Admin user created
- [ ] App accessible at URL
- [ ] (Optional) Custom domain configured
- [ ] (Optional) Uptime monitor set up

---

**Congratulations! Your Smart PG CRM is now live! 🎉**

