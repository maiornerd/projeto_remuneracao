import re
import os

# 1. Update app.py
with open("app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

# Add MASTERS list
if "MASTERS = ['1-082959', '1-082361', '1-079254']" not in app_code:
    app_code = app_code.replace("app.secret_key = 'chave_super_secreta_demillus'", 
                                "app.secret_key = 'chave_super_secreta_demillus'\nMASTERS = ['1-082959', '1-082361', '1-079254']")

# Update Login
app_code = app_code.replace("session['matricula'] = user['matricula']\n            session['nome'] = user['nome']",
                            "session['matricula'] = user['matricula']\n            session['nome'] = user['nome']\n            session['is_master'] = user['matricula'] in MASTERS")

# Redefine Index to be Dashboard
app_code = app_code.replace("return render_template('formulario.html', nome_gestor=session.get('nome'))",
                            "return render_template('dashboard.html', nome_gestor=session.get('nome'), is_master=session.get('is_master'))")

# Add /tabela, /visualizar, /headcount, /relatorio routes
new_routes = """
@app.route('/tabela')
def tabela():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    return render_template('formulario.html', nome_gestor=session.get('nome'), is_master=session.get('is_master'))

@app.route('/visualizar')
def visualizar():
    if 'matricula' not in session: return redirect(url_for('login'))
    return render_template('em_construcao.html', voltar_url=url_for('index'), titulo="Visualizar Indicações")

@app.route('/headcount')
def headcount():
    if 'matricula' not in session: return redirect(url_for('login'))
    return render_template('em_construcao.html', voltar_url=url_for('index'), titulo="Headcount do Ano")

@app.route('/relatorio')
def relatorio():
    if 'matricula' not in session: return redirect(url_for('login'))
    if not session.get('is_master'): return redirect(url_for('index'))
    return render_template('em_construcao.html', voltar_url=url_for('index'), titulo="Gerar Relatório Final")
"""
if "@app.route('/tabela')" not in app_code:
    app_code = app_code.replace("@app.route('/login', methods=['GET', 'POST'])", new_routes + "\n@app.route('/login', methods=['GET', 'POST'])")

# Update /api/opcoes for Master
old_opcoes = """    matricula = request.args.get('matricula', session['matricula'])
    conn = get_db_connection()
    opcoes = conn.execute('SELECT * FROM opcoes_gestor WHERE matricula = ? ORDER BY nome_empresa, nome_setor, nome_funcao', (matricula,)).fetchall()
    conn.close()"""

new_opcoes = """    matricula = request.args.get('matricula')
    conn = get_db_connection()
    
    if session.get('is_master') and not matricula:
        # Master vê todas as opções do sistema se não especificar um destino
        opcoes = conn.execute('SELECT DISTINCT cod_empresa, nome_empresa, cod_setor, nome_setor, cod_funcao, nome_funcao FROM opcoes_gestor ORDER BY nome_empresa, nome_setor, nome_funcao').fetchall()
    else:
        alvo = matricula if matricula else session['matricula']
        opcoes = conn.execute('SELECT * FROM opcoes_gestor WHERE matricula = ? ORDER BY nome_empresa, nome_setor, nome_funcao', (alvo,)).fetchall()
        
    conn.close()"""
app_code = app_code.replace(old_opcoes, new_opcoes)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_code)


# 2. Update templates/formulario.html (Add Voltar button and Jinja2 condition for Master)
with open("templates/formulario.html", "r", encoding="utf-8") as f:
    form_html = f.read()

# Make "Nome do Responsavel" field unlocked if Master? The image says "Tem permissão total para editar...". 
# Usually, keeping it filled is better. We just need to add the Voltar button.
voltar_btn = """            <a href="/" class="btn btn-secondary" style="position: absolute; top: 20px; left: 30px; text-decoration: none; padding: 8px 15px; font-size: 14px; background: #6c757d; color: white; border-radius: 4px;">
                <span>⬅️</span> Voltar ao Menu
            </a>"""

if "Voltar ao Menu" not in form_html:
    form_html = form_html.replace('<h1>Tabela de Indicações para o Comitê</h1>', voltar_btn + '\n            <h1>Tabela de Indicações para o Comitê</h1>')

with open("templates/formulario.html", "w", encoding="utf-8") as f:
    f.write(form_html)


# 3. Create templates/dashboard.html
dash_html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Painel Principal - Avaliações e Indicações</title>
    <style>
        :root {
            --primary-blue: #1e3a5f;
            --secondary-blue: #3A6EA5;
            --light-bg: #f4f7f6;
            --white: #ffffff;
            --gray: #6c757d;
            --danger: #dc3545;
            --hover-blue: #2c5282;
            --card-shadow: 0 4px 6px rgba(0,0,0,0.1);
            --transition: all 0.3s ease;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }

        body { 
            background-color: var(--light-bg); 
            color: #333; 
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .navbar {
            background-color: var(--primary-blue);
            color: var(--white);
            padding: 15px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .navbar h1 { font-size: 20px; font-weight: 600; }
        .nav-right { display: flex; align-items: center; gap: 20px; }
        .user-info { font-size: 14px; opacity: 0.9; }
        .user-badge {
            background: #ffd700;
            color: #000;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            margin-left: 8px;
            text-transform: uppercase;
        }

        .logout-btn {
            color: var(--white);
            text-decoration: none;
            padding: 6px 12px;
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 4px;
            transition: var(--transition);
            font-size: 13px;
        }

        .logout-btn:hover { background: rgba(255,255,255,0.1); border-color: var(--white); }

        .container {
            max-width: 1200px;
            margin: 40px auto;
            padding: 0 20px;
            flex: 1;
        }

        .welcome-section {
            text-align: center;
            margin-bottom: 40px;
            animation: fadeInDown 0.6s ease-out;
        }

        .welcome-section h2 { color: var(--primary-blue); font-size: 28px; margin-bottom: 10px; }
        .welcome-section p { color: var(--gray); font-size: 16px; }

        .menu-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 25px;
            animation: fadeInUp 0.6s ease-out;
        }

        .menu-card {
            background: var(--white);
            border-radius: 10px;
            padding: 30px 20px;
            text-align: center;
            text-decoration: none;
            color: #333;
            box-shadow: var(--card-shadow);
            transition: var(--transition);
            border-top: 4px solid var(--secondary-blue);
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .menu-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 15px rgba(0,0,0,0.15);
            border-top-color: var(--primary-blue);
        }

        .menu-card.disabled {
            opacity: 0.6;
            filter: grayscale(100%);
            cursor: not-allowed;
            pointer-events: none;
        }

        .icon-circle {
            width: 70px;
            height: 70px;
            background: rgba(58, 110, 165, 0.1);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 32px;
            margin-bottom: 20px;
            color: var(--secondary-blue);
            transition: var(--transition);
        }

        .menu-card:hover .icon-circle {
            background: var(--secondary-blue);
            color: var(--white);
            transform: scale(1.05);
        }

        .menu-card h3 { font-size: 18px; margin-bottom: 10px; color: var(--primary-blue); }
        .menu-card p { font-size: 13px; color: var(--gray); line-height: 1.5; flex: 1; }

        .permission-text {
            display: block;
            margin-top: 15px;
            font-size: 11px;
            font-weight: 600;
            color: #28a745;
            background: rgba(40,167,69,0.1);
            padding: 4px 10px;
            border-radius: 20px;
        }
        .permission-text.master { color: #856404; background: #fff3cd; border: 1px solid #ffeeba; }

        @keyframes fadeInDown { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }

        .footer {
            text-align: center;
            padding: 20px;
            color: var(--gray);
            font-size: 12px;
            border-top: 1px solid #e9ecef;
            margin-top: auto;
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <h1>Avaliações e Indicações</h1>
        <div class="nav-right">
            <div class="user-info">
                Olá, <strong>{{ nome_gestor }}</strong>
                {% if is_master %}
                    <span class="user-badge">⚙️ Master</span>
                {% else %}
                    <span class="user-badge" style="background:#e9ecef; color:#495057;">👤 Usuário Simples</span>
                {% endif %}
            </div>
            <a href="{{ url_for('logout') }}" class="logout-btn">Sair</a>
        </div>
    </nav>

    <div class="container">
        <div class="welcome-section">
            <h2>Selecione uma opção do Menu</h2>
            <p>Selecione a área que deseja gerenciar hoje.</p>
        </div>

        <div class="menu-grid">
            <a href="{{ url_for('visualizar') }}" class="menu-card">
                <div class="icon-circle">👁️</div>
                <h3>Visualizar Indicações</h3>
                <p>Ver painel geral de indicações no sistema.</p>
                {% if is_master %}
                <span class="permission-text master">Permissão Total: Edição/Exclusão (Todas as Indicações)</span>
                {% else %}
                <span class="permission-text">Sua Responsabilidade: Visualização Restrita</span>
                {% endif %}
            </a>

            <a href="{{ url_for('tabela') }}" class="menu-card">
                <div class="icon-circle">📝</div>
                <h3>Tabela de Indicações</h3>
                <p>Preencher e incluir novas indicações para o Comitê.</p>
                {% if is_master %}
                <span class="permission-text master">Permissão Total: Inclusão (Todos Setores e Cargos)</span>
                {% else %}
                <span class="permission-text">Sua Responsabilidade: Inclusão Restrita</span>
                {% endif %}
            </a>

            <a href="{{ url_for('headcount') }}" class="menu-card">
                <div class="icon-circle">📊</div>
                <h3>Headcount do Ano</h3>
                <p>Acompanhar a evolução do quadro e vagas.</p>
                {% if is_master %}
                <span class="permission-text master">Permissão Total: Visualização (Todos)</span>
                {% else %}
                <span class="permission-text">Sua Responsabilidade: Visualização Parcial</span>
                {% endif %}
            </a>

            {% if is_master %}
            <a href="{{ url_for('relatorio') }}" class="menu-card">
                <div class="icon-circle">📑</div>
                <h3>Gerar Relatório Final</h3>
                <p>Módulo exclusivo de Consolidação Final.</p>
                <span class="permission-text master">Permissão Master Exclusiva</span>
            </a>
            {% endif %}
        </div>
    </div>

    <div class="footer">
        © 2026 DeMillus S.A. | Sistema de Indicações para o Comitê
    </div>
</body>
</html>"""
with open("templates/dashboard.html", "w", encoding="utf-8") as f:
    f.write(dash_html)


# 4. Create templates/em_construcao.html
const_html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Página em Construção</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; color: #333; text-align: center; padding-top: 100px; }
        .container { max-width: 600px; margin: auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1 { color: #1e3a5f; margin-bottom: 20px; }
        p { color: #6c757d; line-height: 1.6; margin-bottom: 30px; font-size: 16px; }
        .btn { background: #3A6EA5; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; font-size: 16px;}
        .btn:hover { background: #2c5282; }
        .icon { font-size: 60px; margin-bottom: 20px; color: #f39c12; }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">🚧</div>
        <h1>{{ titulo }}</h1>
        <p>Esta página ainda está em desenvolvimento. Ela foi criada temporariamente para acomodar a estrutura do novo menu.</p>
        <a href="{{ voltar_url }}" class="btn">Voltar ao Início</a>
    </div>
</body>
</html>"""
with open("templates/em_construcao.html", "w", encoding="utf-8") as f:
    f.write(const_html)

print("Phase 2 scaffolding created successfully.")
