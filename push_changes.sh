#!/bin/bash
# Script to push changes to GitHub using SSH

cd "/Users/yuvrajdhakar/Smart PG & Flat Management CRM"

echo "=== Pushing changes to GitHub (SSH) ==="
echo ""

# Switch to SSH if not already
CURRENT_REMOTE=$(git remote get-url origin)
if [[ $CURRENT_REMOTE == https://* ]]; then
    echo "Switching remote URL to SSH..."
    git remote set-url origin git@github.com:YuvrajDhakar067/smart-pg-flat-crm.git
    echo "✅ Remote URL updated to SSH"
    echo ""
fi

# Test SSH connection
echo "Testing SSH connection to GitHub..."
ssh -T git@github.com 2>&1 | head -3
echo ""

# Check if there are commits to push
if git log origin/main..HEAD --oneline 2>/dev/null | grep -q .; then
    echo "Commits to push:"
    git log origin/main..HEAD --oneline
    echo ""
    echo "Attempting to push via SSH..."
    git push origin main
    echo ""
    if [ $? -eq 0 ]; then
        echo "✅ Successfully pushed to GitHub!"
        echo "Render.com will auto-deploy the changes."
    else
        echo "❌ Push failed. Please check:"
        echo "1. Your SSH key is added to GitHub (Settings > SSH and GPG keys)"
        echo "2. Your SSH key is loaded: ssh-add ~/.ssh/id_ed25519 (or your key path)"
        echo "3. Test connection: ssh -T git@github.com"
        echo ""
        echo "If SSH doesn't work, you can use HTTPS with a Personal Access Token:"
        echo "git remote set-url origin https://github.com/YuvrajDhakar067/smart-pg-flat-crm.git"
        echo "git push https://YOUR_TOKEN@github.com/YuvrajDhakar067/smart-pg-flat-crm.git main"
    fi
else
    echo "No commits to push. Everything is up to date."
fi
