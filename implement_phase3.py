import os
import sqlite3
import re

# 1. Database Migration
print("Migrating Database...")
conn = sqlite3.connect('app.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS indicacoes_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gestor_origem_mat TEXT,
        nome_gestor_origem TEXT,
        gestor_destino_mat TEXT,
        nome_gestor_destino TEXT,
        matricula_empregado TEXT,
        nome_empregado TEXT,
        setor_destino TEXT,
        cargo_atual TEXT,
        cargo_proposto TEXT,
        mes_ano TEXT,
        observacao TEXT DEFAULT '',
        status TEXT DEFAULT 'Em análise',
        dados_completos TEXT,
        data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()
conn.close()

# 2. Update app.py
print("Updating app.py...")
with open("app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

# Replace the /visualizar route with actual logic
old_visualizar = """@app.route('/visualizar')
def visualizar():
    if 'matricula' not in session: return redirect(url_for('login'))
    return render_template('em_construcao.html', voltar_url=url_for('index'), titulo="Visualizar Indicações")"""

new_visualizar = """@app.route('/visualizar')
def visualizar():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if session.get('is_master'):
        rows = conn.execute('SELECT * FROM indicacoes_item ORDER BY data_criacao DESC').fetchall()
    else:
        # Puxa onde ele é origem ou destino
        rows = conn.execute('SELECT * FROM indicacoes_item WHERE gestor_origem_mat = ? OR gestor_destino_mat = ? ORDER BY data_criacao DESC', 
                            (session['matricula'], session['matricula'])).fetchall()
    conn.close()
    
    return render_template('visualizar.html', 
                           indicacoes=[dict(r) for r in rows], 
                           is_master=session.get('is_master'),
                           nome_gestor=session.get('nome'))"""

app_code = app_code.replace(old_visualizar, new_visualizar)

# Replace the /api/salvar route
old_salvar = """@app.route('/api/salvar', methods=['POST'])
def salvar_indicacoes():
    if 'matricula' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
        
    dados = request.get_json()
    if not dados:
        return jsonify({'error': 'Dados vazios'}), 400
        
    matricula = session['matricula']
    
    conn = get_db_connection()
    conn.execute('INSERT INTO indicacoes (matricula, dados_json) VALUES (?, ?)', 
                 (matricula, json.dumps(dados, ensure_ascii=False)))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Indicações salvas com sucesso!'})"""

new_salvar = """import datetime
import locale

@app.route('/api/salvar', methods=['POST'])
def salvar_indicacoes():
    if 'matricula' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
        
    dados = request.get_json()
    if not dados or 'rows' not in dados:
        return jsonify({'error': 'Dados vazios'}), 400
        
    matricula_origem = session['matricula']
    nome_origem = session.get('nome', '')
    
    # Calcular proximo mes
    hoje = datetime.date.today()
    mes_que_vem = (hoje.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
    # Mapeamento basico de meses para PT-BR caso locale falhe
    meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
    mes_ano_str = f"{meses_pt[mes_que_vem.month - 1]}/{mes_que_vem.year}"
    
    conn = get_db_connection()
    for row in dados['rows']:
        # Extrair dados para as colunas
        matr_emp = row.get('matriculaCompleta', '')
        nome_emp = row.get('nome', '')
        setor_dest = row.get('setorDestino', '')
        cargo_atual = row.get('cargoAtual', '')
        cargo_prop = row.get('cargoProposto', '')
        
        # Para Gestor Destino, vamos pegar a matricula pelo dropdown se pudermos, ou salvar o nome
        # Na interface, o responsavel destino é um select com "matricula - nome"
        resp_destino_val = dados.get('responsavelDestino', '')
        gestor_destino_mat = resp_destino_val.split(' - ')[0] if ' - ' in resp_destino_val else resp_destino_val
        nome_gestor_dest = resp_destino_val.split(' - ')[1] if ' - ' in resp_destino_val else resp_destino_val
        
        conn.execute('''
            INSERT INTO indicacoes_item 
            (gestor_origem_mat, nome_gestor_origem, gestor_destino_mat, nome_gestor_destino,
            matricula_empregado, nome_empregado, setor_destino, cargo_atual, cargo_proposto,
            mes_ano, status, observacao, dados_completos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Em análise', '', ?)
        ''', (
            matricula_origem, nome_origem, gestor_destino_mat, nome_gestor_dest,
            matr_emp, nome_emp, setor_dest, cargo_atual, cargo_prop, mes_ano_str,
            json.dumps(row, ensure_ascii=False)
        ))
        
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Indicações enviadas com sucesso para análise!'})
    
@app.route('/api/atualizar_status', methods=['POST'])
def atualizar_status():
    if 'matricula' not in session or not session.get('is_master'):
        return jsonify({'error': 'Não autorizado'}), 403
        
    payload = request.get_json()
    updates = payload.get('updates', [])
    
    conn = get_db_connection()
    for upd in updates:
        item_id = upd.get('id')
        status = upd.get('status')
        obs = upd.get('observacao', '')
        
        if item_id and status:
            conn.execute('UPDATE indicacoes_item SET status = ?, observacao = ? WHERE id = ?',
                         (status, obs, item_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Status atualizados com sucesso!'})"""

if "@app.route('/api/atualizar_status'" not in app_code:
    app_code = app_code.replace(old_salvar, new_salvar)
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(app_code)
    print("app.py updated.")

# 3. Create templates/visualizar.html
visualizar_html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Visualizar Indicações - Comitê</title>
    <style>
        :root {
            --primary-blue: #1e3a5f;
            --secondary-blue: #3A6EA5;
            --light-bg: #f4f7f6;
            --white: #ffffff;
            --gray: #6c757d;
            --border-color: #dee2e6;
            --success: #28a745;
            --warning: #ffc107;
            --danger: #dc3545;
            --info: #17a2b8;
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
        
        .btn {
            background: var(--secondary-blue);
            color: var(--white);
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
            font-size: 14px;
            transition: all 0.3s;
        }
        .btn:hover { background: #2c5282; }
        .btn-success { background: var(--success); }
        .btn-success:hover { background: #218838; }

        .container {
            width: 100%;
            padding: 20px 30px;
            flex: 1;
            overflow-x: auto;
        }

        .header-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .header-bar h2 { color: var(--primary-blue); font-size: 22px; }

        table {
            width: 100%;
            border-collapse: collapse;
            background: var(--white);
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            font-size: 13px;
            white-space: nowrap;
        }

        th, td {
            padding: 12px 15px;
            border: 1px solid var(--border-color);
            text-align: left;
        }

        th {
            background-color: var(--primary-blue);
            color: var(--white);
            font-weight: 600;
            position: sticky;
            top: 0;
        }

        tr:nth-child(even) { background-color: #f8f9fa; }
        tr:hover { background-color: #e9ecef; }

        .status-badge {
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            color: #fff;
            display: inline-block;
            text-align: center;
        }
        
        .status-badge[data-status="Em análise"] { background-color: var(--warning); color: #000; }
        .status-badge[data-status="Em Comitê"] { background-color: var(--info); }
        .status-badge[data-status="Aprovado"] { background-color: var(--success); }
        .status-badge[data-status="Reprovado"] { background-color: var(--danger); }

        .obs-input {
            width: 200px;
            padding: 6px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            background: #fffdf5;
            font-size: 12px;
        }

        .status-select {
            padding: 4px;
            border-radius: 4px;
            border: 1px solid var(--border-color);
            font-size: 12px;
        }
        
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--success);
            color: white;
            padding: 12px 20px;
            border-radius: 4px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            display: none;
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
        }
        
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        .empty-state {
            text-align: center;
            padding: 50px;
            color: var(--gray);
            background: var(--white);
            border-radius: 8px;
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <h1>Painel de Indicações - Comitê</h1>
        <div class="nav-right">
            <a href="/" class="btn">⬅️ Voltar ao Menu</a>
        </div>
    </nav>

    <div class="container">
        <div class="header-bar">
            <h2>📜 Acompanhamento de Indicações</h2>
            {% if is_master and indicacoes|length > 0 %}
            <button class="btn btn-success" onclick="salvarAlteracoes()">💾 Salvar Alterações (Master)</button>
            {% endif %}
        </div>

        {% if indicacoes|length == 0 %}
        <div class="empty-state">
            <h3>Nenhuma indicação encontrada.</h3>
            <p>As indicações enviadas aparecerão nesta tela para análise.</p>
        </div>
        {% else %}
        <table id="indicacoesTable">
            <thead>
                <tr>
                    <th>Gestor Atual</th>
                    <th>Gestor Novo</th>
                    <th>Matr.</th>
                    <th>Nome</th>
                    <th>Setor de Destino</th>
                    <th>Cargo Atual</th>
                    <th>Cargo Proposto</th>
                    <th>Mês/Ano Mov.</th>
                    <th>Motivos das Alterações</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {% for item in indicacoes %}
                <tr data-id="{{ item.id }}">
                    <td>{{ item.nome_gestor_origem }}</td>
                    <td>{{ item.nome_gestor_destino }}</td>
                    <td>{{ item.matricula_empregado }}</td>
                    <td>{{ item.nome_empregado }}</td>
                    <td>{{ item.setor_destino }}</td>
                    <td>{{ item.cargo_atual }}</td>
                    <td>{{ item.cargo_proposto }}</td>
                    <td>{{ item.mes_ano }}</td>
                    
                    <!-- MASTER EDIT -->
                    {% if is_master %}
                    <td>
                        <textarea class="obs-input edit-obs" rows="2">{{ item.observacao }}</textarea>
                    </td>
                    <td>
                        <select class="status-select edit-status">
                            <option value="Em análise" {% if item.status == 'Em análise' %}selected{% endif %}>Em análise</option>
                            <option value="Em Comitê" {% if item.status == 'Em Comitê' %}selected{% endif %}>Em Comitê</option>
                            <option value="Aprovado" {% if item.status == 'Aprovado' %}selected{% endif %}>Aprovado</option>
                            <option value="Reprovado" {% if item.status == 'Reprovado' %}selected{% endif %}>Reprovado</option>
                        </select>
                    </td>
                    <!-- SIMPLES VIEW -->
                    {% else %}
                    <td>
                        <div class="obs-input" style="background:#e9ecef;" readonly>{{ item.observacao if item.observacao else 'Sem observações' }}</div>
                    </td>
                    <td>
                        <span class="status-badge" data-status="{{ item.status }}">{{ item.status }}</span>
                    </td>
                    {% endif %}
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% endif %}
    </div>

    <div id="toast" class="toast">✔️ Salvo com sucesso!</div>

    <script>
        function salvarAlteracoes() {
            const rows = document.querySelectorAll('#indicacoesTable tbody tr');
            const updates = [];
            
            rows.forEach(row => {
                const id = row.getAttribute('data-id');
                const obsEl = row.querySelector('.edit-obs');
                const statusEl = row.querySelector('.edit-status');
                
                if(obsEl && statusEl) {
                    updates.push({
                        id: id,
                        observacao: obsEl.value.trim(),
                        status: statusEl.value
                    });
                }
            });
            
            if(updates.length === 0) return;
            
            fetch('/api/atualizar_status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ updates: updates })
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    const toast = document.getElementById('toast');
                    toast.style.display = 'block';
                    setTimeout(() => { toast.style.display = 'none'; }, 3000);
                } else {
                    alert('Erro ao salvar: ' + (data.error || 'Desconhecido'));
                }
            })
            .catch(err => {
                alert('Erro de rede ao salvar: ' + err);
            });
        }
    </script>
</body>
</html>"""
with open("templates/visualizar.html", "w", encoding="utf-8") as f:
    f.write(visualizar_html)

# 4. Update templates/formulario.html (Add "Enviar p/ Visualizar" Button & Logic)
with open("templates/formulario.html", "r", encoding="utf-8") as f:
    form_html = f.read()

btn_enviar = """<button class="action-btn save-btn" onclick="enviarParaVisualizacao()">
                    <span class="icon">🚀</span>
                    Enviar p/ Visualizar
                </button>"""

if "Enviar p/ Visualizar" not in form_html:
    # Insere o botão na action-bar
    form_html = form_html.replace('<!-- FIM ACTION BAR -->', btn_enviar + '\n            <!-- FIM ACTION BAR -->')

# Logica de salvar
js_enviar = """
        function enviarParaVisualizacao() {
            // VERIFICAÇÃO DE MATRÍCULAS COM LETRAS (SEGURANÇA EXTRA)
            const invalidMatriculas = checkNumericMatriculaBlock();
            if (invalidMatriculas.length > 0) {
                showCustomAlert('⚠️ ATENÇÃO', '❌ BLOQUEADO: O campo matrícula deve conter APENAS números.\\n\\nPENDÊNCIAS:\\n' + invalidMatriculas.join('\\n') + '\\n\\nPor favor, corrija as matrículas antes de prosseguir.');
                return;
            }

            const duplicateCheck = hasDuplicatedMatriculas();
            if (duplicateCheck.hasDuplicates) {
                showCustomAlert('⚠️ ATENÇÃO', '❌ BLOQUEADO: Existem matrículas duplicadas na tabela.\\n\\nMatrículas repetidas: ' + duplicateCheck.duplicatedValues.join(', ') + '\\n\\nPor favor, corrija as matrículas duplicadas antes de prosseguir.');
                return;
            }

            const leadershipErrors = checkLeadershipBlock();
            if (leadershipErrors.length > 0) {
                const listaNomes = leadershipErrors.join('\\n');
                showCustomAlert('⚠️ ATENÇÃO', '❌ BLOQUEADO: Existem problemas de Avaliação de R&S.\\n\\n' + listaNomes);
                return;
            }

            const trainingErrors = checkTrainingBlock();
            if (trainingErrors.length > 0) {
                const listaNomes = trainingErrors.join('\\n');
                showCustomAlert('⚠️ ATENÇÃO', '❌ BLOQUEADO: Problemas de Carta de Treinamento.\\n\\n' + listaNomes);
                return;
            }

            const missingDateErrors = checkMissingDatesBlock();
            if (missingDateErrors.length > 0) {
                const listaNomes = missingDateErrors.join('\\n');
                showCustomAlert('⚠️ ATENÇÃO', '❌ BLOQUEADO: Existem informações de data obrigatórias faltando.\\n\\n' + listaNomes);
                return;
            }

            const errors = validateRequiredFields();
            if (errors.length > 0) {
                showCustomAlert('⚠️ ATENÇÃO', 'Preencha os campos obrigatórios antes de enviar:\\n\\n• ' + errors.join('\\n• '));
                return;
            }

            // Coletar dados
            const responsavelDestinoEl = document.getElementById('responsavelDestino');
            const responsavelDestino = responsavelDestinoEl ? responsavelDestinoEl.options[responsavelDestinoEl.selectedIndex].text : '';
            
            const rowsData = [];
            const rows = document.querySelectorAll('#tableBody tr');
            
            let indicacoesEnviadas = 0;
            rows.forEach(row => {
                const matricula = row.querySelector('[data-field="matricula"]').value;
                if (!matricula) return;
                
                indicacoesEnviadas++;
                const rowData = {
                    matriculaCompleta: getMatriculaComEmpresa(matricula),
                    nome: row.querySelector('[data-field="nome"]').value,
                    setorDestino: row.querySelector('[data-field="setorDestino"]').value,
                    cargoAtual: row.querySelector('[data-field="cargoAtual"]').value,
                    cargoProposto: row.querySelector('[data-field="cargoProposto"]').value
                };
                rowsData.push(rowData);
            });
            
            if (rowsData.length === 0) {
                showCustomAlert('⚠️ ATENÇÃO', 'A tabela está vazia. Adicione pelo menos uma indicação válida.');
                return;
            }
            
            const payload = {
                responsavelDestino: responsavelDestino,
                rows: rowsData
            };
            
            // Enviar ao backend
            fetch('/api/salvar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    showCustomAlert('✅ Sucesso', `Foram enviadas ${indicacoesEnviadas} indicações para análise do Comitê.\\nRedirecionando para o painel de visualização...`);
                    setTimeout(() => {
                        window.location.href = '/visualizar';
                    }, 2500);
                } else {
                    showCustomAlert('❌ Erro', 'Ocorreu um erro ao enviar: ' + (data.error || 'Desconhecido'));
                }
            })
            .catch(err => {
                showCustomAlert('❌ Erro', 'Ocorreu um erro de conexão: ' + err);
            });
        }
"""
if "function enviarParaVisualizacao()" not in form_html:
    form_html = form_html.replace('function exportCSV() {', js_enviar + '\n        function exportCSV() {')

with open("templates/formulario.html", "w", encoding="utf-8") as f:
    f.write(form_html)

print("Phase 3 complete.")
