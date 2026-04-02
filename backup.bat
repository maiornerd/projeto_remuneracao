@echo off
git add . 
git commit -m "Backup antes da unificacao de botoes" > git_commit_log.txt 2>&1
git log -1 >> git_commit_log.txt 2>&1
type git_commit_log.txt
