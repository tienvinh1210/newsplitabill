# Making Your Vercel App Publicly Accessible

If your shared links require login, it's because Vercel has **Password Protection** or **Deployment Protection** enabled on your project.

## How to Disable Password Protection

1. **Go to Vercel Dashboard**
   - Visit [vercel.com](https://vercel.com)
   - Sign in to your account
   - Select your project

2. **Navigate to Settings**
   - Click on **Settings** in the project menu
   - Go to **Deployment Protection** (or **Security** → **Password Protection**)

3. **Disable Protection**
   - Find the **Password Protection** toggle
   - Turn it **OFF** or set it to **"No Protection"**
   - Save the changes

4. **Redeploy (if needed)**
   - Vercel may automatically redeploy, or you may need to trigger a new deployment
   - Go to **Deployments** tab and click **Redeploy** if necessary

## Alternative: Check Project Settings

If you don't see "Deployment Protection", check:
- **Settings** → **General** → Look for any protection/security settings
- **Settings** → **Security** → Password Protection
- **Settings** → **Access Control** → Make sure it's set to "Public"

## Verify It Works

After disabling protection:
1. Open your Vercel URL in an incognito/private browser window
2. You should be able to access it without logging in
3. Shared links should work for anyone

## Note

- Password protection is useful for staging/preview environments
- For production apps that need to be shared publicly, disable it
- Your app code doesn't have any authentication - this is purely a Vercel feature

