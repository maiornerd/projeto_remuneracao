import os
import shutil
import pandas as pd
import sqlite3

# 1. IMPORT HEADCOUNT DATA
print("1. Seedando Banco de Dados com 'HEADCOUNT 2026.xlsx'...")
try:
    if not os.path.exists("temp_hc.xlsx"):
        shutil.copy2('HEADCOUNT 2026.xlsx', 'temp_hc.xlsx')
    df = pd.read_excel('temp_hc.xlsx', header=1)
    df = df.dropna(subset=[df.columns[0]])
    
    conn = sqlite3.connect('app.db')
    conn.execute('DROP TABLE IF EXISTS headcount')
    conn.execute('''
        CREATE TABLE headcount (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cod_empresa TEXT,
            nome_empresa TEXT,
            empresa_hc TEXT,
            cod_setor TEXT,
            matricula_gestor TEXT,
            gestor TEXT,
            atividade_hc TEXT,
            nome_setor TEXT,
            macro_area TEXT,
            cod_funcao TEXT,
            desc_funcao TEXT,
            qtd_01 INTEGER DEFAULT 0,
            qtd_02 INTEGER DEFAULT 0,
            qtd_03 INTEGER DEFAULT 0,
            qtd_04 INTEGER DEFAULT 0,
            qtd_05 INTEGER DEFAULT 0,
            qtd_06 INTEGER DEFAULT 0,
            qtd_07 INTEGER DEFAULT 0,
            qtd_08 INTEGER DEFAULT 0,
            qtd_09 INTEGER DEFAULT 0,
            qtd_10 INTEGER DEFAULT 0,
            qtd_11 INTEGER DEFAULT 0,
            qtd_12 INTEGER DEFAULT 0
        )
    ''')
    for _, row in df.iterrows():
        cod = str(row.iloc[0]).strip()
        if 'TOTAL' in cod.upper() or 'SUBTOTAL' in cod.upper() or len(cod) == 0 or cod == 'nan':
            continue
        try:
            matr = str(row.iloc[4]).strip()
            if matr == "nan": matr = ""
            conn.execute('''
                INSERT INTO headcount (
                    cod_empresa, nome_empresa, empresa_hc, cod_setor, matricula_gestor, gestor,
                    atividade_hc, nome_setor, macro_area, cod_funcao, desc_funcao,
                    qtd_01, qtd_02, qtd_03, qtd_04, qtd_05, qtd_06,
                    qtd_07, qtd_08, qtd_09, qtd_10, qtd_11, qtd_12
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                str(row.iloc[0]), str(row.iloc[1]), str(row.iloc[2]), str(row.iloc[3]), matr, str(row.iloc[5]),
                str(row.iloc[6]), str(row.iloc[7]), str(row.iloc[8]), str(row.iloc[9]), str(row.iloc[10]),
                int(row.iloc[11]) if pd.notna(row.iloc[11]) else 0,
                int(row.iloc[12]) if pd.notna(row.iloc[12]) else 0,
                int(row.iloc[13]) if pd.notna(row.iloc[13]) else 0,
                int(row.iloc[14]) if pd.notna(row.iloc[14]) else 0,
                int(row.iloc[15]) if pd.notna(row.iloc[15]) else 0,
                int(row.iloc[16]) if pd.notna(row.iloc[16]) else 0,
                int(row.iloc[17]) if pd.notna(row.iloc[17]) else 0,
                int(row.iloc[18]) if pd.notna(row.iloc[18]) else 0,
                int(row.iloc[19]) if pd.notna(row.iloc[19]) else 0,
                int(row.iloc[20]) if pd.notna(row.iloc[20]) else 0,
                int(row.iloc[21]) if pd.notna(row.iloc[21]) else 0,
                int(row.iloc[22]) if len(row) > 22 and pd.notna(row.iloc[22]) else 0
            ))
        except Exception as e:
            pass
    conn.commit()
    conn.close()
    print("Banco de dados 'headcount' populado com sucesso!")
except Exception as e:
    print("Falha no seed HC:", e)


# 2. UPDATE APP.PY
print("2. Atualizando app.py com as novas rotas do HC...")
app_path = "app.py"
with open(app_path, "r", encoding="utf-8") as f:
    app_content = f.read()

nova_rota_headcount = """
@app.route('/headcount')
def headcount():
    if 'matricula' not in session:
        return redirect(url_for('ver_tabela'))
        
    is_master = session.get('is_master', False)
    matricula = session.get('matricula')
    
    conn = get_db_connection()
    if is_master:
        lista_hc = conn.execute('SELECT * FROM headcount').fetchall()
    else:
        # Apenas as linhas onde o gestor == matricula 
        # Cuidado que na base, a matricula_gestor pode ter sido gravada diferente.
        # Vamos comparar como um texto.
        lista_hc = conn.execute('SELECT * FROM headcount WHERE matricula_gestor = ?', (matricula,)).fetchall()
        
    conn.close()
    
    # Converter para lista de dicts
    hcs = [dict(ix) for ix in lista_hc]
    
    return render_template('headcount.html', hcs=hcs, is_master=is_master, nome=session.get('nome'))

@app.route('/api/salvar_headcount', methods=['POST'])
def salvar_headcount():
    if 'matricula' not in session or not session.get('is_master'):
        return jsonify({'error': 'Não autorizado'}), 403
        
    payload = request.get_json()
    updates = payload.get('updates', [])
    
    conn = get_db_connection()
    for upd in updates:
        hc_id = upd.get('id')
        try:
            # Dynamic update over the months
            for i in range(1, 13):
                month_key = f"qtd_{i:02d}"
                if month_key in upd:
                    val = int(upd[month_key])
                    conn.execute(f"UPDATE headcount SET {month_key} = ? WHERE id = ?", (val, hc_id))
        except Exception as e:
            return jsonify({'error': str(e)}), 400
            
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Vagas atualizadas com sucesso!'})

"""

# Inserir antes de if __name__ == '__main__':
if '@app.route(\'/headcount\')' not in app_content:
    if "if __name__ == '__main__':" in app_content:
        app_content = app_content.replace(
            "if __name__ == '__main__':",
            f"{nova_rota_headcount}\nif __name__ == '__main__':"
        )
    else:
        app_content += f"\n{nova_rota_headcount}"
        
    with open(app_path, "w", encoding="utf-8") as f:
        f.write(app_content)
    print("Rotas HC adicionadas no app.py")
else:
    print("Rotas HC já existiam no app.py.")


# 3. WRITE HEADCOUNT TEMPLATE
print("3. Criando templates/headcount.html...")
html_content = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Headcount - Vagas Disponíveis</title>
    <style>
        :root {
            --primary-blue: #1e3a5f;
            --secondary-blue: #3A6EA5;
            --light-bg: #f4f7f6;
            --white: #ffffff;
            --border-color: #dee2e6;
            --success: #28a745;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Verdana, sans-serif; }

        body { 
            background-color: var(--light-bg); 
            color: #333; 
            display: flex;
            flex-direction: column;
            height: 100vh;
        }

        .navbar {
            background-color: var(--primary-blue);
            color: var(--white);
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .btn {
            background: var(--secondary-blue);
            color: var(--white);
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
            font-size: 13px;
        }
        .btn:hover { background: #2c5282; }
        .btn-success { background: var(--success); }
        .btn-success:hover { background: #218838; }

        .container {
            flex: 1;
            padding: 15px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .filters {
            display: flex;
            gap: 15px;
            margin-bottom: 15px;
            flex-wrap: wrap;
            background: var(--white);
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .filter-group {
            display: flex;
            flex-direction: column;
        }
        
        .filter-group label {
            font-size: 11px;
            font-weight: bold;
            color: var(--primary-blue);
            margin-bottom: 2px;
        }

        .filter-select {
            padding: 5px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            font-size: 12px;
            min-width: 150px;
        }

        .table-wrapper {
            flex: 1;
            overflow: auto;
            background: var(--white);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        table {
            border-collapse: collapse;
            font-size: 11px;
            white-space: nowrap;
        }

        th, td {
            padding: 6px 8px;
            border: 1px solid var(--border-color);
            text-align: center;
        }
        
        /* Master specific align left for non-numbers */
        td.text-col { text-align: left; }

        thead th {
            background-color: #5b9bd5; /* Cor similar ao print Excel */
            color: white;
            position: sticky;
            top: 0;
            z-index: 2;
        }

        /* Congelar a primeira linha extra do cabeçalho */
        thead tr.header-months th {
            top: 0;
        }
        thead tr.header-desc th {
            top: 26px; /* Offset the previous row */
        }
        
        .t-bg { background-color: #DCE6F1; } /* Tons de Azul Claro para Totais */

        /* Destacar as colunas dos meses */
        .col-mes {
            width: 45px;
        }
        
        .input-qtd {
            width: 40px;
            padding: 2px;
            text-align: center;
            border: 1px solid var(--border-color);
            font-size: 11px;
            border-radius: 2px;
        }
        
        .input-qtd:focus {
            outline: rgb(0, 120, 215) solid 1px;
        }

    </style>
</head>
<body>
    <nav class="navbar">
        <h2>Dashboard - Headcount 2026 (Usuário: {{ nome|default("Visitante") }})</h2>
        <div>
            {% if is_master %}
            <button class="btn btn-success" onclick="salvarHC()">💾 Salvar Alterações</button>
            {% endif %}
            <a href="/" class="btn" style="margin-left: 10px;">⬅️ Voltar Menu</a>
        </div>
    </nav>

    <div class="container">
        <!-- FILTROS DROPDOWN -->
        <div class="filters">
            {% if is_master %}
            <div class="filter-group">
                <label>Nome da Empresa</label>
                <select id="flt_empresa" class="filter-select" onchange="runFilters()"><option value="">TODOS</option></select>
            </div>
            <div class="filter-group">
                <label>Nome do Gestor</label>
                <select id="flt_gestor" class="filter-select" onchange="runFilters()"><option value="">TODOS</option></select>
            </div>
            {% endif %}
            <div class="filter-group">
                <label>Nome do Setor</label>
                <select id="flt_setor" class="filter-select" onchange="runFilters()"><option value="">TODOS</option></select>
            </div>
            <div class="filter-group">
                <label>Macro Área</label>
                <select id="flt_macro" class="filter-select" onchange="runFilters()"><option value="">TODOS</option></select>
            </div>
            <div class="filter-group">
                <label>Nome da Função</label>
                <select id="flt_funcao" class="filter-select" onchange="runFilters()"><option value="">TODOS</option></select>
            </div>
        </div>

        <!-- TABELA -->
        <div class="table-wrapper">
            <table id="hcTable">
                <thead>
                    <tr class="header-months">
                        {% if is_master %}
                        <th colspan="11"></th>
                        {% else %}
                        <th colspan="4"></th>
                        {% endif %}
                        <th class="t-bg">jan/26</th>
                        <th class="t-bg">fev/26</th>
                        <th class="t-bg">mar/26</th>
                        <th class="t-bg">abr/26</th>
                        <th class="t-bg">mai/26</th>
                        <th class="t-bg">jun/26</th>
                        <th class="t-bg">jul/26</th>
                        <th class="t-bg">ago/26</th>
                        <th class="t-bg">set/26</th>
                        <th class="t-bg">out/26</th>
                        <th class="t-bg">nov/26</th>
                        <th class="t-bg">dez/26</th>
                    </tr>
                    <tr class="header-desc">
                        {% if is_master %}
                        <th>CÓD. EMPRESA</th>
                        <th>NOME EMPRESA</th>
                        <th>EMPRESA (HC)</th>
                        <th>Cód. Setor</th>
                        <th>Matrícula Gestor</th>
                        <th>GESTOR</th>
                        <th>Atividade (HC)</th>
                        {% endif %}
                        <th>Nome Setor</th>
                        <th>MACRO ÁREA (RHBRC)</th>
                        <th>Cód Função</th>
                        <th>Descrição da Função</th>
                        
                        <!-- Month Headers -->
                        <th>Qtd 01/26</th>
                        <th>Qtd 02/26</th>
                        <th>Qtd 03/26</th>
                        <th>Qtd 04/26</th>
                        <th>Qtd 05/26</th>
                        <th>Qtd 06/26</th>
                        <th>Qtd 07/26</th>
                        <th>Qtd 08/26</th>
                        <th>Qtd 09/26</th>
                        <th>Qtd 10/26</th>
                        <th>Qtd 11/26</th>
                        <th>Qtd 12/26</th>
                    </tr>
                </thead>
                <tbody id="hcBody">
                    {% for h in hcs %}
                    <tr class="hc-row" data-id="{{ h.id }}">
                        <!-- Dados do Registro Identificadores Ocultos -->
                        <td style="display:none;" class="df-empresa">{{ h.nome_empresa }}</td>
                        <td style="display:none;" class="df-gestor">{{ h.gestor }}</td>
                        <td style="display:none;" class="df-setor">{{ h.nome_setor }}</td>
                        <td style="display:none;" class="df-macro">{{ h.macro_area }}</td>
                        <td style="display:none;" class="df-funcao">{{ h.desc_funcao }}</td>
                        
                        {% if is_master %}
                        <td>{{ h.cod_empresa }}</td>
                        <td class="text-col">{{ h.nome_empresa }}</td>
                        <td class="text-col">{{ h.empresa_hc }}</td>
                        <td>{{ h.cod_setor }}</td>
                        <td>{{ h.matricula_gestor }}</td>
                        <td class="text-col">{{ h.gestor }}</td>
                        <td class="text-col">{{ h.atividade_hc }}</td>
                        {% endif %}
                        <td class="text-col">{{ h.nome_setor }}</td>
                        <td class="text-col">{{ h.macro_area }}</td>
                        <td>{{ h.cod_funcao }}</td>
                        <td class="text-col">{{ h.desc_funcao }}</td>

                        <!-- Qtd Meses -->
                        {% for pt in [h.qtd_01, h.qtd_02, h.qtd_03, h.qtd_04, h.qtd_05, h.qtd_06, h.qtd_07, h.qtd_08, h.qtd_09, h.qtd_10, h.qtd_11, h.qtd_12] %}
                            <td class="col-mes">
                                {% if is_master %}
                                <input type="number" class="input-qtd" min="0" data-idx="{{ loop.index }}" value="{{ pt }}" onchange="markDirty(this)">
                                {% else %}
                                {{ pt }}
                                {% endif %}
                            </td>
                        {% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        // 1. POPULATE DROPDOWNS UNIQUELY
        function populateDropdown(selectId, className) {
            const selectEl = document.getElementById(selectId);
            if(!selectEl) return;
            
            const trs = document.querySelectorAll('.hc-row');
            const uniqueValues = new Set();
            
            trs.forEach(tr => {
                const textNode = tr.querySelector('.' + className);
                if(textNode) {
                    const txt = textNode.textContent.trim();
                    if(txt) uniqueValues.add(txt);
                }
            });
            
            Array.from(uniqueValues).sort().forEach(val => {
                const opt = document.createElement('option');
                opt.value = opt.textContent = val;
                selectEl.appendChild(opt);
            });
        }

        window.onload = function() {
            if(document.getElementById('flt_empresa')) populateDropdown('flt_empresa', 'df-empresa');
            if(document.getElementById('flt_gestor')) populateDropdown('flt_gestor', 'df-gestor');
            populateDropdown('flt_setor', 'df-setor');
            populateDropdown('flt_macro', 'df-macro');
            populateDropdown('flt_funcao', 'df-funcao');
        };

        // 2. FILTERING LOGIC
        function runFilters() {
            const fEmp = document.getElementById('flt_empresa') ? document.getElementById('flt_empresa').value : '';
            const fGest = document.getElementById('flt_gestor') ? document.getElementById('flt_gestor').value : '';
            const fSetor = document.getElementById('flt_setor').value;
            const fMacro = document.getElementById('flt_macro').value;
            const fFunc = document.getElementById('flt_funcao').value;

            document.querySelectorAll('.hc-row').forEach(row => {
                const matchEmp = !fEmp || row.querySelector('.df-empresa').textContent === fEmp;
                const matchGest = !fGest || row.querySelector('.df-gestor').textContent === fGest;
                const matchSetor = !fSetor || row.querySelector('.df-setor').textContent === fSetor;
                const matchMacro = !fMacro || row.querySelector('.df-macro').textContent === fMacro;
                const matchFunc = !fFunc || row.querySelector('.df-funcao').textContent === fFunc;

                if(matchEmp && matchGest && matchSetor && matchMacro && matchFunc) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        }

        // 3. MASTER SAVING
        function markDirty(input) {
            input.closest('.hc-row').classList.add('dirty');
        }

        function salvarHC() {
            const dirtyRows = document.querySelectorAll('.hc-row.dirty');
            const updates = [];
            
            dirtyRows.forEach(row => {
                const id = row.getAttribute('data-id');
                const rowUpdate = { id: id };
                
                const inputs = row.querySelectorAll('.input-qtd');
                inputs.forEach(ip => {
                    const monthId = parseInt(ip.getAttribute('data-idx'));
                    const key = 'qtd_' + (monthId < 10 ? '0' + monthId : monthId);
                    rowUpdate[key] = ip.value;
                });
                
                updates.push(rowUpdate);
            });

            if(updates.length === 0) {
                alert("Nenhuma modificação foi feita.");
                return;
            }

            fetch('/api/salvar_headcount', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({updates: updates})
            })
            .then(r => r.json())
            .then(data => {
                if(data.success) {
                    alert('As atualizações de vagas foram salvas!');
                    dirtyRows.forEach(r => r.classList.remove('dirty'));
                } else {
                    alert('Erro: ' + data.error);
                }
            })
            .catch(e => alert("Erro ao salvar: " + e));
        }
    </script>
</body>
</html>
"""

os.makedirs("templates", exist_ok=True)
with open("templates/headcount.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Processo concluído: Seed Finalizado, Back e Front construídos!")
