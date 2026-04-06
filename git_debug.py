import subprocess
import os

def run_git(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
        return f"CMD: {cmd}\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}\nCODE: {result.returncode}\n{'-'*40}\n"
    except Exception as e:
        return f"CMD: {cmd}\nEXEC_ERROR: {e}\n{'-'*40}\n"

log_path = "git_ops_log.txt"
with open(log_path, "w", encoding="utf-8") as f:
    f.write(run_git("git config user.email 'maiornerd@example.com'"))
    f.write(run_git("git config user.name 'Maior Nerd'"))
    f.write(run_git("git remote add origin https://github.com/maiornerd/projeto_remuneracao.git || git remote set-url origin https://github.com/maiornerd/projeto_remuneracao.git"))
    f.write(run_git("git branch -M main"))
    f.write(run_git("git add ."))
    f.write(run_git("git commit -m 'Refactor completo: Removido Efetivo, Corrigida Persistencia de E-mail e Ajustes de UI'"))
    f.write(run_git("git status"))

print(f"Logs salvos em {log_path}")
