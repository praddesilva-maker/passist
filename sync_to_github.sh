#!/bin/bash

# Script to sync the passist project to GitHub
echo "Syncing passist project to GitHub..."

# Navigate to project directory
cd /home/praddesilva/ProjectTeams/personal-assistant

# Initialize git repository (if not already initialized)
if [ ! -d ".git" ]; then
    echo "Initializing Git repository..."
    git init
fi

# Set up the default branch name if needed
git config --global init.defaultBranch main

# Add all files to git
echo "Adding all files to git..."
git add .

# Commit all files with initial commit message
echo "Creating initial commit..."
git commit -m "Initial commit - Synced from local development environment"

# Add remote origin (GitHub repository)
echo "Setting up remote repository..."
git remote add origin https://github.com/praddesilva-maker/passist.git

# Push to GitHub main branch
echo "Pushing to GitHub..."
git push -u origin main

echo "Sync complete!"