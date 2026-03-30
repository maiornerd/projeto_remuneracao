from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import json

app = Flask(__name__)
app.secret_key = 'chave_super_secreta_demillus'
MASTERS_INICIAIS = ['1-082959', '1-082361', '1-079254']

def get_db_connection():
    import os
    db_path = os.path.join(os.path.dirname(__file__), 'app.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    conn.execute('''
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
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notificacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT,
            mensagem TEXT,
            lida BOOLEAN DEFAULT 0,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicacao_id INTEGER,
            matricula TEXT,
            nome TEXT,
            acao TEXT,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Adicionar coluna tipo se não existir
    try:
        conn.execute("ALTER TABLE usuarios ADD COLUMN tipo TEXT DEFAULT 'simples'")
        for m in MASTERS_INICIAIS:
            conn.execute("UPDATE usuarios SET tipo = 'master' WHERE matricula = ?", (m,))
    except:
        pass
    # Migrar valores antigos: garantir que tipo nunca é NULL
    conn.execute("UPDATE usuarios SET tipo = 'simples' WHERE tipo IS NULL OR tipo = ''")
    # Adicionar coluna senha_resetada se não existir
    try:
        conn.execute("ALTER TABLE usuarios ADD COLUMN senha_resetada INTEGER DEFAULT 1")
        # Existentes NÃO devem ser forçados a trocar - somente novos ou quando admin resetar
        conn.execute("UPDATE usuarios SET senha_resetada = 0")
    except:
        pass
    # Adicionar coluna gestor_matricula se não existir
    try:
        conn.execute("ALTER TABLE usuarios ADD COLUMN gestor_matricula TEXT DEFAULT ''")
    except:
        pass
    conn.commit()
    
    return conn

def atualizar_notificacao_master(conn, triggered_by_master=False):
    pendentes_row = conn.execute("SELECT COUNT(*) as qtd FROM indicacoes_item WHERE TRIM(status) = 'Em análise'").fetchone()
    if not pendentes_row: return
    pendentes = pendentes_row['qtd']
    
    msg = f"Você tem {pendentes} Novas Indicações aguardando análise! <br><br><a href='/visualizar' style='color:#3A6EA5; text-decoration:underline; font-weight:bold;'>Visualizar agora</a>"
    masters_rows = conn.execute("SELECT matricula FROM usuarios WHERE tipo = 'master'").fetchall()
    masters = [r['matricula'] for r in masters_rows]
    
    for m in masters:
        existe = conn.execute("SELECT id, lida FROM notificacoes WHERE matricula = ? AND mensagem LIKE 'Você tem % Novas Indicações aguardando análise!%'", (m,)).fetchone()
        if pendentes > 0:
            if existe:
                nova_lida = existe['lida'] if triggered_by_master else 0
                conn.execute("UPDATE notificacoes SET mensagem = ?, lida = ?, data_criacao = CURRENT_TIMESTAMP WHERE id = ?", (msg, nova_lida, existe['id']))
            else:
                lida = 1 if triggered_by_master else 0
                conn.execute("INSERT INTO notificacoes (matricula, mensagem, lida) VALUES (?, ?, ?)", (m, msg, lida))
        else:
            if existe:
                conn.execute("DELETE FROM notificacoes WHERE id = ?", (existe['id'],))

@app.route('/')
def index():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', nome=session.get('nome'), is_master=session.get('is_master', False), tipo=session.get('tipo', 'simples'))

@app.route('/graficos')
def graficos():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    # Simples não tem acesso a gráficos
    if session.get('tipo', 'simples') == 'simples':
        return redirect(url_for('index'))
        
    is_master = session.get('is_master', False)
    matricula = session.get('matricula')
    
    conn = get_db_connection()
    status_dict = {'Em análise': 0, 'Em Comitê': 0, 'Aprovado': 0, 'Reprovado': 0}
    
    if is_master:
        ind_counts = conn.execute('''
            SELECT TRIM(status) as st, COUNT(*) as qtd 
            FROM indicacoes_item 
            GROUP BY TRIM(status)
        ''').fetchall()
        
        # Calculate Headcount global usage
        raw_hcs = conn.execute('SELECT * FROM headcount').fetchall()
        total_vagas_ano = 0
        for hc in raw_hcs:
            for m in range(1, 13):
                total_vagas_ano += (hc[f'qtd_{m:02d}'] or 0)
                
        aprovados_query = conn.execute("SELECT COUNT(*) as aggregate_qtd FROM indicacoes_item WHERE TRIM(status) = 'Aprovado'").fetchone()
        total_aprovados = aprovados_query['aggregate_qtd'] if aprovados_query else 0
        
        headcount_data = {
            'livre': total_vagas_ano - total_aprovados,
            'utilizado': total_aprovados
        }
    else:
        ind_counts = conn.execute('''
            SELECT TRIM(status) as st, COUNT(*) as qtd 
            FROM indicacoes_item 
            WHERE gestor_origem_mat = ? OR gestor_destino_mat = ?
            GROUP BY TRIM(status)
        ''', (matricula, matricula)).fetchall()
        headcount_data = None
        
    conn.close()
    
    for row in ind_counts:
        key = row['st']
        if key in status_dict:
            status_dict[key] = row['qtd']
            
    return render_template('graficos.html', 
                         nome=session.get('nome'),
                         is_master=is_master,
                         status_counts=json.dumps(status_dict),
                         headcount_data=json.dumps(headcount_data) if headcount_data else "null")


@app.route('/tabela')
def tabela():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    return render_template('formulario.html', nome_gestor=session.get('nome'), is_master=session.get('is_master'))

@app.route('/visualizar')
def visualizar():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if session.get('is_master'):
        rows = conn.execute('SELECT * FROM indicacoes_item ORDER BY data_criacao DESC').fetchall()
    else:
        rows = conn.execute('SELECT * FROM indicacoes_item WHERE gestor_origem_mat = ? OR gestor_destino_mat = ? ORDER BY data_criacao DESC', 
                            (session['matricula'], session['matricula'])).fetchall()
    conn.close()
    
    return render_template('visualizar.html', 
                           indicacoes=[dict(r) for r in rows], 
                           is_master=session.get('is_master'),
                           nome_gestor=session.get('nome'))

@app.route('/headcount')
def headcount():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    # Simples não tem acesso ao headcount
    if session.get('tipo', 'simples') == 'simples':
        return redirect(url_for('index'))
        
    is_master = session.get('is_master', False)
    matricula = session.get('matricula')
    
    conn = get_db_connection()
    try:
        # Verifica se está vazia primeiro
        total = conn.execute('SELECT COUNT(*) as c FROM headcount').fetchone()['c']
        if total == 0:
            raise sqlite3.OperationalError("Table is empty, forcing seed")
            
        if is_master:
            lista_hc = conn.execute('SELECT * FROM headcount').fetchall()
        else:
            lista_hc = conn.execute('SELECT * FROM headcount WHERE matricula_gestor = ?', (matricula,)).fetchall()
    except sqlite3.OperationalError:
        import pandas as pd
        import shutil
        import os
        
        try:
            shutil.copy2('HEADCOUNT 2026.xlsx', 'temp_hc.xlsx')
            df = pd.read_excel('temp_hc.xlsx', header=0)
            df = df.dropna(subset=[df.columns[0]])
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS headcount (
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
                matr_val = str(row.iloc[4]).strip()
                if matr_val == "nan": matr_val = ""
                conn.execute('''
                    INSERT INTO headcount (
                        cod_empresa, nome_empresa, empresa_hc, cod_setor, matricula_gestor, gestor,
                        atividade_hc, nome_setor, macro_area, cod_funcao, desc_funcao,
                        qtd_01, qtd_02, qtd_03, qtd_04, qtd_05, qtd_06,
                        qtd_07, qtd_08, qtd_09, qtd_10, qtd_11, qtd_12
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (
                    str(row.iloc[0]), str(row.iloc[1]), str(row.iloc[2]), str(row.iloc[3]), matr_val, str(row.iloc[5]),
                    str(row.iloc[6]), str(row.iloc[7]), str(row.iloc[9]), str(row.iloc[10]), str(row.iloc[11]),
                    int(row.iloc[12]) if pd.notna(row.iloc[12]) else 0,
                    int(row.iloc[13]) if pd.notna(row.iloc[13]) else 0,
                    int(row.iloc[14]) if pd.notna(row.iloc[14]) else 0,
                    int(row.iloc[15]) if pd.notna(row.iloc[15]) else 0,
                    int(row.iloc[16]) if pd.notna(row.iloc[16]) else 0,
                    int(row.iloc[17]) if pd.notna(row.iloc[17]) else 0,
                    int(row.iloc[18]) if pd.notna(row.iloc[18]) else 0,
                    int(row.iloc[19]) if pd.notna(row.iloc[19]) else 0,
                    int(row.iloc[20]) if len(row) > 20 and pd.notna(row.iloc[20]) else 0,
                    int(row.iloc[21]) if len(row) > 21 and pd.notna(row.iloc[21]) else 0,
                    int(row.iloc[22]) if len(row) > 22 and pd.notna(row.iloc[22]) else 0,
                    int(row.iloc[23]) if len(row) > 23 and pd.notna(row.iloc[23]) else 0
                ))
            conn.commit()
            
            if is_master:
                lista_hc = conn.execute('SELECT * FROM headcount').fetchall()
            else:
                lista_hc = conn.execute('SELECT * FROM headcount WHERE matricula_gestor = ?', (matricula,)).fetchall()
                
        except Exception as e:
            conn.close()
            return f"Erro fatal ao importar planilha headcount: {str(e)}"
            
    conn.close()
    
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

@app.route('/relatorio')
def relatorio():
    if 'matricula' not in session: return redirect(url_for('login'))
    if not session.get('is_master'): return redirect(url_for('index'))
    
    conn = get_db_connection()
    raw_hcs = conn.execute('SELECT * FROM headcount').fetchall()
    
    # Busca todas as indicações Aprovadas
    base_inds = conn.execute("SELECT setor_destino, cargo_proposto, mes_ano FROM indicacoes_item WHERE TRIM(status) = 'Aprovado'").fetchall()
    conn.close()
    
    meses_map = {
        'JANEIRO': '01', 'FEVEREIRO': '02', 'MARÇO': '03', 'ABRIL': '04',
        'MAIO': '05', 'JUNHO': '06', 'JULHO': '07', 'AGOSTO': '08',
        'SETEMBRO': '09', 'OUTUBRO': '10', 'NOVEMBRO': '11', 'DEZEMBRO': '12'
    }
    
    aprovados = {}
    for ind in base_inds:
        mes_ano_raw = ind['mes_ano'] or ''
        mes_nome = mes_ano_raw.split('/')[0].strip().upper()
        mes = meses_map.get(mes_nome, '00')
        
        setor = (ind['setor_destino'] or '').strip().upper()
        cargo = (ind['cargo_proposto'] or '').strip().upper()
        key = (setor, cargo, mes)
        aprovados[key] = aprovados.get(key, 0) + 1
        
    relatorio_data = []
    for hc in raw_hcs:
        row_data = dict(hc)
        total_vagas = 0
        total_aprovados = 0
        
        hc_setor = (hc['nome_setor'] or '').strip().upper()
        hc_cargo = (hc['desc_funcao'] or '').strip().upper()
        
        for m in range(1, 13):
            mes_str = f"{m:02d}"
            vagas_mes = hc[f'qtd_{mes_str}'] or 0
            
            apr_mes = aprovados.get((hc_setor, hc_cargo, mes_str), 0)
            saldo_mes = vagas_mes - apr_mes
            
            row_data[f'apr_{mes_str}'] = apr_mes
            row_data[f'saldo_{mes_str}'] = saldo_mes
            
            total_vagas += vagas_mes
            total_aprovados += apr_mes
            
        row_data['total_vagas'] = total_vagas
        row_data['total_aprovados'] = total_aprovados
        row_data['total_saldo'] = total_vagas - total_aprovados
        
        relatorio_data.append(row_data)

    return render_template('relatorio.html', relatorio=relatorio_data, is_master=True, nome=session.get('nome'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        matricula = request.form.get('matricula', '').strip()
        senha = request.form.get('senha', '').strip()
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM usuarios WHERE matricula = ? AND senha = ?', (matricula, senha)).fetchone()
        conn.close()
        
        if user:
            session['matricula'] = user['matricula']
            session['nome'] = user['nome']
            tipo_usuario = user['tipo'] if user['tipo'] else ('master' if user['matricula'] in MASTERS_INICIAIS else 'simples')
            session['tipo'] = tipo_usuario
            session['is_master'] = (tipo_usuario == 'master')
            session['is_intermediario'] = (tipo_usuario == 'intermediario')
            session['gestor_matricula'] = user['gestor_matricula'] if 'gestor_matricula' in user.keys() and user['gestor_matricula'] else ''
            # Verificar se precisa trocar a senha (primeiro login ou reset pelo admin)
            if user['senha_resetada'] if 'senha_resetada' in user.keys() else False:
                session['forcar_troca_senha'] = True
                return redirect(url_for('alterar_senha'))
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Matrícula ou senha inválidos')
            
    return render_template('login.html')

@app.route('/alterar_senha', methods=['GET', 'POST'])
def alterar_senha():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        nova_senha = request.form.get('nova_senha', '').strip()
        confirmar = request.form.get('confirmar_senha', '').strip()
        if len(nova_senha) < 4:
            return render_template('alterar_senha.html', error='A senha deve ter no mínimo 4 caracteres.')
        if nova_senha != confirmar:
            return render_template('alterar_senha.html', error='As senhas não coincidem.')
        conn = get_db_connection()
        conn.execute('UPDATE usuarios SET senha = ?, senha_resetada = 0 WHERE matricula = ?', (nova_senha, session['matricula']))
        conn.commit()
        conn.close()
        session.pop('forcar_troca_senha', None)
        return redirect(url_for('index'))
    return render_template('alterar_senha.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/api/gestores')
def get_gestores():
    if 'matricula' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
    conn = get_db_connection()
    gestores = conn.execute('SELECT matricula, nome FROM usuarios ORDER BY nome').fetchall()
    conn.close()
    return jsonify([dict(g) for g in gestores])

@app.route('/api/opcoes')

def get_opcoes():
    if 'matricula' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
        
    matricula = request.args.get('matricula')
    conn = get_db_connection()
    
    if session.get('is_master') and not matricula:
        # Master vê todas as opções do sistema se não especificar um destino
        opcoes = conn.execute('SELECT DISTINCT cod_empresa, nome_empresa, cod_setor, nome_setor, cod_funcao, nome_funcao FROM opcoes_gestor ORDER BY nome_empresa, nome_setor, nome_funcao').fetchall()
    else:
        alvo = matricula if matricula else session['matricula']
        # Se o usuário tem um gestor vinculado, usar a matrícula do gestor para buscar opções
        if not matricula and session.get('gestor_matricula'):
            alvo = session['gestor_matricula']
        opcoes = conn.execute('SELECT * FROM opcoes_gestor WHERE matricula = ? ORDER BY nome_empresa, nome_setor, nome_funcao', (alvo,)).fetchall()
        
    conn.close()
    
    result = [dict(ix) for ix in opcoes]
    return jsonify(result)

import datetime

@app.route('/api/salvar', methods=['POST'])
def salvar_indicacoes():
    if 'matricula' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
        
    dados = request.get_json()
    if not dados or 'rows' not in dados:
        return jsonify({'error': 'Dados vazios'}), 400
        
    matricula_origem = session['matricula']
    nome_origem = session.get('nome', '')
    
    hoje = datetime.date.today()
    mes_que_vem = (hoje.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
    meses_pt = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
    mes_ano_str = f"{meses_pt[mes_que_vem.month - 1]}/{mes_que_vem.year}"
    
    conn = get_db_connection()
    for row in dados['rows']:
        matr_emp = row.get('matriculaCompleta', '')
        nome_emp = row.get('nome', '')
        setor_dest = row.get('setorDestino', '')
        cargo_atual = row.get('cargoAtual', '')
        cargo_prop = row.get('cargoProposto', '')
        
        resp_destino_val = dados.get('responsavelDestino', '')
        gestor_destino_mat = resp_destino_val.split(' - ')[0] if ' - ' in resp_destino_val else resp_destino_val
        nome_gestor_dest = resp_destino_val.split(' - ')[1] if ' - ' in resp_destino_val else resp_destino_val
        
        cursor = conn.execute('''
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
        novo_id = cursor.lastrowid
        conn.execute('INSERT INTO auditoria (indicacao_id, matricula, nome, acao) VALUES (?, ?, ?, ?)',
                     (novo_id, matricula_origem, nome_origem, f'Criou a indicação do empregado {nome_emp} para {cargo_prop}'))
        
    atualizar_notificacao_master(conn, triggered_by_master=False)
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
            item = conn.execute("SELECT status as status_antigo, gestor_origem_mat, gestor_destino_mat, nome_empregado, cargo_proposto FROM indicacoes_item WHERE id = ?", (item_id,)).fetchone()
            if item:
                status_antigo = item['status_antigo']
                if status in ['Aprovado', 'Reprovado']:
                    msg = f"A indicação de {item['nome_empregado']} para {item['cargo_proposto']} foi {status.upper()}."
                    gestores = set([item['gestor_origem_mat'], item['gestor_destino_mat']])
                    for gestor in gestores:
                        if gestor:
                            conn.execute("INSERT INTO notificacoes (matricula, mensagem) VALUES (?, ?)", (gestor, msg))
                
                acao_parts = []
                if status_antigo != status:
                    acao_parts.append(f'Alterou status de "{status_antigo}" para "{status}"')
                if obs:
                    acao_parts.append(f'Motivo: {obs}')
                acao_text = '. '.join(acao_parts) if acao_parts else f'Atualizou para "{status}"'
                conn.execute('INSERT INTO auditoria (indicacao_id, matricula, nome, acao) VALUES (?, ?, ?, ?)',
                             (item_id, session['matricula'], session.get('nome', ''), acao_text))
                             
            conn.execute('UPDATE indicacoes_item SET status = ?, observacao = ? WHERE id = ?',
                         (status, obs, item_id))
    atualizar_notificacao_master(conn, triggered_by_master=True)
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Status atualizados com sucesso!'})

@app.route('/api/auditoria/<int:indicacao_id>', methods=['GET'])
def get_auditoria(indicacao_id):
    if 'matricula' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
    conn = get_db_connection()
    logs = conn.execute('SELECT * FROM auditoria WHERE indicacao_id = ? ORDER BY data_hora ASC', (indicacao_id,)).fetchall()
    conn.close()
    return jsonify([dict(l) for l in logs])

@app.route('/api/notificacoes', methods=['GET'])
def get_notificacoes():
    if 'matricula' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
    conn = get_db_connection()
    # Para Masters, sincroniza automaticamente as notificações de pendentes
    if session.get('is_master'):
        atualizar_notificacao_master(conn, triggered_by_master=True)
        conn.commit()
    notifs = conn.execute('SELECT * FROM notificacoes WHERE matricula = ? ORDER BY data_criacao DESC LIMIT 20', (session['matricula'],)).fetchall()
    nao_lidas = conn.execute('SELECT COUNT(*) as qtd FROM notificacoes WHERE matricula = ? AND lida = 0', (session['matricula'],)).fetchone()['qtd']
    conn.close()
    return jsonify({
        'nao_lidas': nao_lidas,
        'notificacoes': [dict(n) for n in notifs]
    })

@app.route('/api/ler_notificacoes', methods=['POST'])
def ler_notificacoes():
    if 'matricula' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
    conn = get_db_connection()
    conn.execute('UPDATE notificacoes SET lida = 1 WHERE matricula = ? AND lida = 0', (session['matricula'],))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/excluir_indicacoes', methods=['POST'])
def excluir_indicacoes():
    if 'matricula' not in session or not session.get('is_master'):
        return jsonify({'error': 'Não autorizado'}), 403
        
    payload = request.get_json()
    ids = payload.get('ids', [])
    
    if not ids:
        return jsonify({'error': 'Nenhum ID fornecido'}), 400
        
    conn = get_db_connection()
    placeholders = ','.join(['?'] * len(ids))
    conn.execute(f'DELETE FROM indicacoes_item WHERE id IN ({placeholders})', tuple(ids))
    atualizar_notificacao_master(conn, triggered_by_master=True)
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Excluído com sucesso!'})

# ========== ADMIN: Gest\u00e3o de Usu\u00e1rios ==========
@app.route('/admin/usuarios')
def admin_usuarios():
    if 'matricula' not in session or not session.get('is_master'):
        return redirect(url_for('index'))
    conn = get_db_connection()
    usuarios = conn.execute("SELECT u.matricula, u.nome, u.senha, COALESCE(u.tipo, 'simples') as tipo, COALESCE(u.gestor_matricula, '') as gestor_matricula, COALESCE(g.nome, '') as gestor_nome FROM usuarios u LEFT JOIN usuarios g ON u.gestor_matricula = g.matricula ORDER BY u.nome").fetchall()
    # Lista de gestores distintos da tabela opcoes_gestor
    gestores = conn.execute("SELECT DISTINCT og.matricula, u.nome FROM opcoes_gestor og LEFT JOIN usuarios u ON og.matricula = u.matricula ORDER BY u.nome").fetchall()
    conn.close()
    return render_template('admin_usuarios.html', usuarios=usuarios, gestores=gestores, nome=session.get('nome'), is_master=True)

@app.route('/api/admin/criar_usuario', methods=['POST'])
def criar_usuario():
    if 'matricula' not in session or not session.get('is_master'):
        return jsonify({'error': 'N\u00e3o autorizado'}), 403
    dados = request.get_json()
    matricula = dados.get('matricula', '').strip()
    nome = dados.get('nome', '').strip()
    senha = dados.get('senha', '').strip()
    tipo = dados.get('tipo', 'simples')
    gestor_matricula = dados.get('gestor_matricula', '').strip()
    if not matricula or not nome or not senha:
        return jsonify({'error': 'Preencha todos os campos obrigat\u00f3rios.'}), 400
    conn = get_db_connection()
    existe = conn.execute("SELECT matricula FROM usuarios WHERE matricula = ?", (matricula,)).fetchone()
    if existe:
        conn.close()
        return jsonify({'error': 'Matr\u00edcula j\u00e1 cadastrada no sistema.'}), 400
    conn.execute("INSERT INTO usuarios (matricula, nome, senha, tipo, gestor_matricula) VALUES (?, ?, ?, ?, ?)", (matricula, nome, senha, tipo, gestor_matricula))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': f'Usu\u00e1rio {nome} criado com sucesso!'})

@app.route('/api/admin/alterar_tipo', methods=['POST'])
def alterar_tipo_usuario():
    if 'matricula' not in session or not session.get('is_master'):
        return jsonify({'error': 'N\u00e3o autorizado'}), 403
    dados = request.get_json()
    matricula = dados.get('matricula')
    novo_tipo = dados.get('tipo')
    if not matricula or novo_tipo not in ['master', 'intermediario', 'simples']:
        return jsonify({'error': 'Dados inv\u00e1lidos'}), 400
    conn = get_db_connection()
    conn.execute("UPDATE usuarios SET tipo = ? WHERE matricula = ?", (novo_tipo, matricula))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': f'Tipo do usu\u00e1rio alterado para {novo_tipo.upper()}!'})

@app.route('/api/admin/excluir_usuario', methods=['POST'])
def excluir_usuario():
    if 'matricula' not in session or not session.get('is_master'):
        return jsonify({'error': 'N\u00e3o autorizado'}), 403
    dados = request.get_json()
    matricula = dados.get('matricula')
    if matricula == session['matricula']:
        return jsonify({'error': 'Voc\u00ea n\u00e3o pode excluir a si mesmo!'}), 400
    conn = get_db_connection()
    conn.execute("DELETE FROM usuarios WHERE matricula = ?", (matricula,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Usu\u00e1rio exclu\u00eddo!'})

@app.route('/api/admin/resetar_senha', methods=['POST'])
def resetar_senha():
    if 'matricula' not in session or not session.get('is_master'):
        return jsonify({'error': 'Não autorizado'}), 403
    dados = request.get_json()
    matricula = dados.get('matricula')
    nova_senha = dados.get('nova_senha', '').strip()
    if not matricula or not nova_senha:
        return jsonify({'error': 'Dados inválidos'}), 400
    conn = get_db_connection()
    conn.execute("UPDATE usuarios SET senha = ?, senha_resetada = 1 WHERE matricula = ?", (nova_senha, matricula))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': f'Senha resetada! O usuário precisará alterar no próximo login.'})

@app.route('/api/admin/alterar_gestor', methods=['POST'])
def alterar_gestor_usuario():
    if 'matricula' not in session or not session.get('is_master'):
        return jsonify({'error': 'Não autorizado'}), 403
    dados = request.get_json()
    matricula = dados.get('matricula')
    gestor_matricula = dados.get('gestor_matricula', '')
    if not matricula:
        return jsonify({'error': 'Dados inválidos'}), 400
    conn = get_db_connection()
    conn.execute("UPDATE usuarios SET gestor_matricula = ? WHERE matricula = ?", (gestor_matricula, matricula))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Gestor do usuário atualizado com sucesso!'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
