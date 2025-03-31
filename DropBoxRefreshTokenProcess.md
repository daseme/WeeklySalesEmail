DropBoxRefreshTokenProcess.md

# How to Obtain a Dropbox Refresh Token: A Step-by-Step Guide

This guide will walk you through every step to obtain a long-lived **refresh token** from Dropbox. A refresh token lets your app automatically get new short-lived access tokens, so you won’t have to re-authorize it every few hours.

---

## 1. Create a Dropbox App

1. **Log in to Dropbox Developers:**
   - Open your web browser and go to [Dropbox App Console](https://www.dropbox.com/developers/apps).
   - Sign in with your Dropbox account.

2. **Create a New App:**
   - Click on **"Create app"**.
   - Choose **"Scoped access"**.
   - Select the access type that fits your needs:
     - **App folder** – if you want your app to access a specific folder.
     - **Full Dropbox** – if you need access to the entire Dropbox account.
   - Give your app a unique name.
   - Click **"Create app"**.

3. **Configure App Permissions:**
   - In your app’s settings, scroll to the **"Permissions"** section.
   - Check the boxes for the permissions (scopes) your app needs, for example:
     - `files.content.read`
     - `files.content.write`
     - `files.metadata.read`
     - `files.metadata.write`
   - Save your changes.

4. **Note Your App Credentials:**
   - In the app settings, locate your **App Key** and **App Secret**. You will need these later.

---

## 2. Start the OAuth Flow to Get an Authorization Code

1. **Build the Authorization URL:**
   - Construct a URL in this format:
     ```
     https://www.dropbox.com/oauth2/authorize?client_id=YOUR_APP_KEY&response_type=code&token_access_type=offline
     ```
   - Replace `YOUR_APP_KEY` with the App Key you noted earlier.

2. **Visit the URL:**
   - Copy and paste the URL into your browser.
   - You will see Dropbox’s OAuth consent screen.

3. **Grant Permission:**
   - Click the **"Allow"** button on the consent screen.
   - After clicking, Dropbox will display an **authorization code**. **Copy** this code immediately—it is short-lived (usually valid for about an hour).

---

## 3. Exchange the Authorization Code for Tokens

1. **Prepare to Exchange the Code:**
   - You now need to send the authorization code to Dropbox’s token endpoint to get an access token and a refresh token.
   - You can use a tool like **cURL** or **Postman**. We’ll show the cURL method.

2. **Run the cURL Command:**
   - Open a terminal (Command Prompt, PowerShell, or your preferred terminal).
   - Run the following command (replace placeholders with your actual values):

     ```bash
     curl --location --request POST "https://api.dropbox.com/oauth2/token" \
          --user "YOUR_APP_KEY:YOUR_APP_SECRET" \
          --header "Content-Type: application/x-www-form-urlencoded" \
          --data-urlencode "grant_type=authorization_code" \
          --data-urlencode "code=PASTE_YOUR_AUTHORIZATION_CODE_HERE"
     ```

   - **Explanation:**
     - `--user "YOUR_APP_KEY:YOUR_APP_SECRET"` sends your app credentials using Basic Authentication.
     - `grant_type=authorization_code` tells Dropbox what kind of exchange you’re doing.
     - Replace `PASTE_YOUR_AUTHORIZATION_CODE_HERE` with the code you copied.

3. **Review the JSON Response:**
   - The response will be a JSON object similar to:

     ```json
     {
       "access_token": "sl.u.ABCD1234shortlived...",
       "token_type": "bearer",
       "expires_in": 14400,
       "refresh_token": "vIggGLbXjzUAAAAAAAAAAW8oa_09VhsK83W8GzwxWNiGl8cwMRABswEMNc2j5UYi",
       "scope": "...",
       "uid": "",
       "team_id": "dbtid:..."
     }
     ```

   - **Important:** The value under `"refresh_token"` is your long-lived token.

---

## 4. Store Your Refresh Token Securely

1. **Copy the Refresh Token:**
   - From the JSON response, copy the string next to `"refresh_token"`.

2. **Add It to Your Environment:**
   - If you’re using GitHub Actions, add it as a repository secret:
     - Go to your repository on GitHub.
     - Click **Settings** → **Secrets and variables** → **Actions**.
     - Click **"New repository secret"**.
     - Set **Name** to `DROPBOX_REFRESH_TOKEN`.
     - Paste your refresh token into the **Value** field.
     - Click **"Add secret"**.

3. **Keep It Safe:**
   - Do not share this token publicly. It allows your app to request new access tokens without further user interaction.

---

## Summary

- **Create a Dropbox app** and note your **App Key** and **App Secret**.
- **Construct the OAuth URL** with `response_type=code` and `token_access_type=offline`.
- **Authorize your app** and get an **authorization code**.
- **Exchange the code** for tokens using the Dropbox token endpoint.
- **Store the refresh token** securely (e.g., in GitHub Secrets).

Following these steps, you’ll have a refresh token that your app can use to get new access tokens automatically.
