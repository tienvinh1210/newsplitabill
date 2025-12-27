# Deploying to Vercel

This guide will help you deploy your SplitDaBill app to Vercel so it runs permanently in the cloud.

## Prerequisites

1. A GitHub account (or GitLab/Bitbucket)
2. A Vercel account (free tier works) - sign up at [vercel.com](https://vercel.com)
3. A Postgres database (we'll use Supabase - free tier available)

## Step 1: Set Up Postgres Database

### Option A: Supabase (Recommended - Free)

1. Go to [supabase.com](https://supabase.com) and sign up
2. Create a new project
3. Go to **Settings** → **Database**
4. Copy the **Connection string** (URI format)
   - It looks like: `postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres`
5. **Create the table** - Go to **SQL Editor** and run:
   ```sql
   CREATE TABLE IF NOT EXISTS sessions (
       id TEXT PRIMARY KEY,
       state JSONB NOT NULL,
       updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
   );
   ```

### Option B: Vercel Postgres

1. In your Vercel project dashboard, go to **Storage** → **Create Database** → **Postgres**
2. Copy the connection string from the dashboard
3. The table will be created automatically on first use (or run the SQL above)

## Step 2: Push Code to GitHub

1. Initialize git (if not already):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. Create a new repository on GitHub

3. Push your code:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```

## Step 3: Deploy to Vercel

1. Go to [vercel.com](https://vercel.com) and sign in
2. Click **Add New Project**
3. Import your GitHub repository
4. Vercel will auto-detect it's a Python project
5. **Important**: Add environment variable:
   - Go to **Settings** → **Environment Variables**
   - Add: `DATABASE_URL` = your Postgres connection string from Step 1
6. Click **Deploy**

## Step 4: Verify Deployment

1. After deployment, Vercel will give you a URL like: `https://your-project.vercel.app`
2. Visit the URL - you should see the home page
3. Click "Create New Bill Link" - it should work!

## Troubleshooting

- **Database connection errors**: Make sure `DATABASE_URL` is set correctly in Vercel environment variables
- **Table not found**: Run the SQL CREATE TABLE command in your database
- **Import errors**: Make sure all dependencies are in `requirements.txt`

## Your App is Now Live! 🎉

Your app will run 24/7 on Vercel's servers, even when your computer is off. Share the Vercel URL with friends!

