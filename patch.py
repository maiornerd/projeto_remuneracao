import os

base_dir = r"c:\Users\USER\OneDrive\Desktop\INDICAÇÕES\FORMULÁRIO FINAL\FINAL\templates"
files = ["dashboard.html", "visualizar.html", "formulario.html", "headcount.html", "relatorio.html", "graficos.html"]

script_tag = '<script src="{{ url_for(\'static\', filename=\'notificacoes.js\') }}"></script>'

for f in files:
    path = os.path.join(base_dir, f)
    with open(path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    if script_tag not in content:
        content = content.replace('</body>', f'    {script_tag}\n</body>')
        with open(path, 'w', encoding='utf-8') as file:
            file.write(content)
