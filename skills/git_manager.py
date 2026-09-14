#!/usr/bin/env python3
"""
Git Manager Module - Handles Git operations for version control
"""

import subprocess
import os
from typing import Dict, List, Optional, Tuple


class GitManagerError(Exception):
    """Base exception for Git manager errors"""
    pass


class GitManager:
    """Manages Git operations for version control"""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self._check_repo()
    
    def _check_repo(self):
        """Check if path is a valid Git repository"""
        if not os.path.exists(self.repo_path):
            raise GitManagerError(f"Repository path does not exist: {self.repo_path}")
        if not os.path.isdir(self.repo_path):
            raise GitManagerError(f"Repository path is not a directory: {self.repo_path}")
        result = self._run_git(['rev-parse', '--git-dir'], check=False)
        if result.returncode != 0:
            raise GitManagerError(f"Not a Git repository: {self.repo_path}")
    
    def _run_git(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a Git command"""
        result = subprocess.run(
            ['git'] + args,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=check
        )
        return result
    
    def init(self) -> bool:
        """Initialize a new Git repository"""
        try:
            result = self._run_git(['init'], check=False)
            if result.returncode == 0:
                self._add_and_commit('.', 'Initial commit')
            return result.returncode == 0
        except GitManagerError:
            return False
    
    def add(self, files: List[str] = None) -> bool:
        """Add files to Git staging"""
        try:
            if files:
                args = ['add'] + files
            else:
                args = ['add', '.']
            result = self._run_git(args)
            return result.returncode == 0
        except GitManagerError:
            return False
    
    def commit(self, message: str) -> bool:
        """Commit staged changes with a message"""
        try:
            result = self._run_git(['commit', '-m', message])
            return result.returncode == 0
        except GitManagerError:
            return False
    
    def _add_and_commit(self, path: str, message: str):
        """Add and commit all changes"""
        self.add([path])
        self.commit(message)
    
    def status(self) -> Dict[str, str]:
        """Get repository status"""
        try:
            result = self._run_git(['status'])
            return {
                'output': result.stdout,
                'error': result.stderr,
                'success': result.returncode == 0
            }
        except GitManagerError:
            return {'output': '', 'error': '', 'success': False}
    
    def log(self, limit: int = 10) -> List[Dict[str, str]]:
        """Get recent commit log"""
        try:
            result = self._run_git(['log', '-n', str(limit), '--pretty=format:%H|%an|%ae|%ad|%s'])
            entries = []
            for line in result.stdout.splitlines():
                parts = line.split('|')
                if len(parts) >= 5:
                    entries.append({
                        'hash': parts[0][:7],
                        'author': parts[1],
                        'email': parts[2],
                        'date': parts[3],
                        'message': parts[4]
                    })
            return entries
        except GitManagerError:
            return []
    
    def diff(self, branch: str = 'HEAD') -> Dict[str, str]:
        """Get diff between current and branch"""
        try:
            result = self._run_git(['diff', branch])
            return {
                'output': result.stdout,
                'error': result.stderr,
                'success': result.returncode == 0
            }
        except GitManagerError:
            return {'output': '', 'error': '', 'success': False}
    
    def show(self, commit_hash: str) -> Dict[str, str]:
        """Show file contents at a commit"""
        try:
            result = self._run_git(['show', commit_hash])
            return {
                'output': result.stdout,
                'error': result.stderr,
                'success': result.returncode == 0
            }
        except GitManagerError:
            return {'output': '', 'error': '', 'success': False}
    
    def branch(self) -> List[str]:
        """Get list of branches"""
        try:
            result = self._run_git(['branch'])
            branches = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            return branches
        except GitManagerError:
            return []
    
    def checkout(self, branch: str) -> bool:
        """Checkout a branch"""
        try:
            result = self._run_git(['checkout', branch])
            return result.returncode == 0
        except GitManagerError:
            return False
    
    def current_branch(self) -> Optional[str]:
        """Get current branch name"""
        try:
            result = self._run_git(['branch', '--show-current'])
            return result.stdout.strip() if result.stdout.strip() else None
        except GitManagerError:
            return None
    
    def pull(self, remote: str = 'origin', branch: str = None) -> bool:
        """Pull changes from remote"""
        try:
            args = ['pull']
            if branch:
                args.extend([remote, branch])
            result = self._run_git(args)
            return result.returncode == 0
        except GitManagerError:
            return False
    
    def push(self, remote: str = 'origin', branch: str = None) -> bool:
        """Push changes to remote"""
        try:
            args = ['push']
            if branch:
                args.extend([remote, branch])
            result = self._run_git(args)
            return result.returncode == 0
        except GitManagerError:
            return False
    
    def clone(self, url: str, to_path: str) -> bool:
        """Clone a repository from URL"""
        try:
            result = subprocess.run(
                ['git', 'clone', url, to_path],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False
