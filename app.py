from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
import sqlite3
import json
import os
from dotenv import load_dotenv

# Load env variables early
load_dotenv()

from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from secure_fields import crypt_field, decrypt_field

app = Flask(__name__)
# Load secret key from environment
app.secret_key = os.environ.get('SECRET_KEY', 'default_dev_key_fallback')

app.config.update(
    SESSION_COOKIE_SECURE=False,         # Cookie trafega apenas via HTTPS
    SESSION_COOKIE_HTTPONLY=True,        # Proíbe injeções de leitura local no browser via document.cookie
    SESSION_COOKIE_SAMESITE='Lax',       # Previne submissões CSRF acidentais em sites de terceiros
    SECURE_BROWSER_XSS_FILTER=True       # Habilita filtros estritos nativos
)

# Apply CSRF Globally
csrf = CSRFProtect(app)

# Apply Security Headers (Force HTTPS desativado em desenvolvimento local/Waitress HTTP)
Talisman(app, content_security_policy=None, force_https=False, session_cookie_secure=False)

# Apply Rate Limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["1000 per day", "100 per hour"],
    storage_uri="memory://"
)

MASTERS_INICIAIS = ['1-082959', '1-082361', '1-079254']

def get_db_connection():
    import os
    db_dir = os.path.join(os.path.dirname(__file__), '..', 'secure_data')
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, 'app.db')
    conn = sqlite3.connect(db_path, timeout=20) # Aumentar timeout para evitar locks
    conn.row_factory = sqlite3.Row
    return conn

def init_db_schema():
    conn = get_db_connection()
    # Tabelas base
    conn.execute('''
        CREATE TABLE IF NOT EXISTS indicacoes_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gestor_origem_mat TEXT, nome_gestor_origem TEXT, gestor_destino_mat TEXT, nome_gestor_destino TEXT,
            matricula_empregado TEXT, nome_empregado TEXT, setor_destino TEXT, cargo_atual TEXT, cargo_proposto TEXT,
            mes_ano TEXT, observacao TEXT DEFAULT '', status TEXT DEFAULT 'Em análise', setor_origem TEXT,
            dados_completos TEXT, data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS notificacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, matricula TEXT, mensagem TEXT, lida BOOLEAN DEFAULT 0,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT, indicacao_id INTEGER, matricula TEXT, nome TEXT, acao TEXT,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS efetivo_agg (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_coligada TEXT,
            gestor TEXT,
            macro_area TEXT,
            setor TEXT,
            funcao TEXT,
            quantidade INTEGER,
            data_importacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Migrações e Colunas Extras
    try: conn.execute('ALTER TABLE indicacoes_item ADD COLUMN setor_origem TEXT'); 
    except: pass
    try: conn.execute("ALTER TABLE usuarios ADD COLUMN tipo TEXT DEFAULT 'simples'"); 
    except: pass
    try: conn.execute("ALTER TABLE usuarios ADD COLUMN senha_resetada INTEGER DEFAULT 1"); 
    except: pass
    try: conn.execute("ALTER TABLE usuarios ADD COLUMN gestor_matricula TEXT DEFAULT ''"); 
    except: pass
    try: conn.execute("ALTER TABLE usuarios ADD COLUMN email TEXT DEFAULT ''"); 
    except: pass
    
    # Garantir Masters e Tipos
    conn.execute("UPDATE usuarios SET tipo = 'simples' WHERE tipo IS NULL OR tipo = ''")
    for m in MASTERS_INICIAIS:
        conn.execute("UPDATE usuarios SET tipo = 'master' WHERE matricula = ?", (m,))
    
    conn.commit()
    conn.close()

# Inicializar banco na carga do app
with app.app_context():
    init_db_schema()

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
                conn.execute("DELETE FROM notificacoes WHERE id = ?", (existe['id'],))

# SMTP Configuration (Configure with real credentials for production)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_SERVER = "smtp.gmail.com" # Ex: smtp.gmail.com
SMTP_PORT = 585
SMTP_USER = ""  # Seu e-mail
SMTP_PASS = ""  # Sua senha de app

def enviar_email_reset(destinatario, nome_usuario, nova_senha):
    if not SMTP_USER or not SMTP_PASS:
        print(f"SMTP não configurado. Simulação: E-mail de reset enviado para {destinatario} com senha {nova_senha}")
        return True
        
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = destinatario
        msg['Subject'] = "Redefinição de Senha - Sistema de Indicações DeMillus"
        
        corpo = f"""
        Olá {nome_usuario},
        
        Sua senha de acesso ao Sistema de Indicações foi redefinida pelo administrador.
        
        Sua nova senha temporária é: {nova_senha}
        
        Por favor, realize o login com esta senha. O sistema solicitará que você crie uma nova senha pessoal no seu primeiro acesso.
        
        Atenciosamente,
        Administração DeMillus
        """
        msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {str(e)}")
        return False

@app.route('/')
def index():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', nome=session.get('nome'), is_master=session.get('is_master', False), tipo=session.get('tipo', 'simples'), is_planejador=session.get('is_planejador', False))

@app.route('/graficos')
def graficos():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    # Simples e Planejador não tem acesso a gráficos
    if session.get('tipo', 'simples') in ('simples', 'planejador'):
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
        alvos = [matricula]
        if session.get('gestor_matricula'):
            alvos.append(session['gestor_matricula'])
        placeholders = ','.join(['?'] * len(alvos))
        
        ind_counts = conn.execute(f'''
            SELECT TRIM(status) as st, COUNT(*) as qtd 
            FROM indicacoes_item 
            WHERE gestor_origem_mat IN ({placeholders}) OR gestor_destino_mat IN ({placeholders})
            GROUP BY TRIM(status)
        ''', alvos + alvos).fetchall()
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
                         headcount_data=json.dumps(headcount_data) if headcount_data else "null",
                         is_planejador=session.get('is_planejador'))


@app.route('/movimentacoes')
def movimentacoes():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    
    # Planejador e Simples não têm acesso a movimentações
    if session.get('is_planejador') or session.get('tipo') == 'simples':
        return redirect(url_for('index'))

    is_master = session.get('is_master')
    matricula = session['matricula']
    
    conn = get_db_connection()
    
    # 1. Identificar setores sob gestão
    if is_master:
        setores_gestao = [r['nome_setor'] for r in conn.execute('SELECT DISTINCT nome_setor FROM opcoes_gestor').fetchall()]
    else:
        setores_gestao = [r['nome_setor'] for r in conn.execute('SELECT DISTINCT nome_setor FROM opcoes_gestor WHERE matricula = ?', (matricula,)).fetchall()]

    if not setores_gestao:
        conn.close()
        return render_template('movimentacoes.html', 
                             nome=session.get('nome'), 
                             is_master=is_master,
                             data=json.dumps({}),
                             resumo={'entradas': 0, 'saidas': 0, 'saldo': 0})

    # 2. Buscar movimentações aprovadas envolvendo esses setores
    placeholders = ','.join(['?'] * len(setores_gestao))
    query = f'''
        SELECT * FROM indicacoes_item 
        WHERE status = 'Aprovado' 
        AND (setor_origem IN ({placeholders}) OR setor_destino IN ({placeholders}))
    '''
    rows = conn.execute(query, setores_gestao + setores_gestao).fetchall()
    conn.close()

    # 3. Processar dados para o dashboard
    stats = {} # { setor: { entradas: X, saidas: Y } }
    total_entradas = 0
    total_saidas = 0
    detalhes = []

    for r in rows:
        row_dict = dict(r)
        s_orig = row_dict['setor_origem']
        s_dest = row_dict['setor_destino']
        
        # Contabilizar Saída
        if s_orig in setores_gestao:
            stats.setdefault(s_orig, {'entradas': 0, 'saidas': 0})['saidas'] += 1
            total_saidas += 1
            
        # Contabilizar Entrada
        if s_dest in setores_gestao:
            stats.setdefault(s_dest, {'entradas': 0, 'saidas': 0})['entradas'] += 1
            total_entradas += 1
        if 'observacao' in row_dict and row_dict['observacao']:
            row_dict['observacao'] = decrypt_field(row_dict['observacao'])
        
        detalhes.append(row_dict)

    return render_template('movimentacoes.html',
                         nome=session.get('nome'),
                         is_master=is_master,
                         data=json.dumps(stats),
                         resumo={
                             'entradas': total_entradas,
                             'saidas': total_saidas,
                             'saldo': total_entradas - total_saidas
                         },
                         detalhes=detalhes)


@app.route('/tabela')
def tabela():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    # Planejador não tem acesso à tabela de indicações
    if session.get('tipo', 'simples') == 'planejador':
        return redirect(url_for('index'))
    # Se tiver gestor_nome na sessão, usa ele; caso contrário, usa o nome do próprio usuário
    nome_para_exibir = session.get('gestor_nome') if session.get('gestor_nome') else session.get('nome')
    return render_template('formulario.html', nome_gestor=nome_para_exibir, is_master=session.get('is_master'))

@app.route('/visualizar')
def visualizar():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    # Planejador não tem acesso a visualizar indicações
    if session.get('tipo', 'simples') == 'planejador':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    if session.get('is_master'):
        rows = conn.execute('SELECT * FROM indicacoes_item ORDER BY data_criacao DESC').fetchall()
    else:
        alvos = [session['matricula']]
        if session.get('gestor_matricula'):
            alvos.append(session['gestor_matricula'])
        placeholders = ','.join(['?'] * len(alvos))
        
        rows = conn.execute(f'''
            SELECT * FROM indicacoes_item 
            WHERE gestor_origem_mat IN ({placeholders}) OR gestor_destino_mat IN ({placeholders}) 
            ORDER BY data_criacao DESC
        ''', alvos + alvos).fetchall()
    conn.close()
    
    indicacoes_list = []
    for r in rows:
        d = dict(r)
        if 'observacao' in d and d['observacao']:
            d['observacao'] = decrypt_field(d['observacao'])
        indicacoes_list.append(d)

    return render_template('visualizar.html', 
                           indicacoes=indicacoes_list, 
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
    is_planejador = session.get('is_planejador', False)
    # Planejador tem acesso total ao headcount (como Master)
    acesso_total_hc = is_master or is_planejador
    matricula = session.get('matricula')
    
    conn = get_db_connection()
    try:
        # Verifica se está vazia primeiro
        total = conn.execute('SELECT COUNT(*) as c FROM headcount').fetchone()['c']
        if total == 0:
            raise sqlite3.OperationalError("Table is empty, forcing seed")
            
        if acesso_total_hc:
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
            
            if acesso_total_hc:
                lista_hc = conn.execute('SELECT * FROM headcount').fetchall()
            else:
                lista_hc = conn.execute('SELECT * FROM headcount WHERE matricula_gestor = ?', (matricula,)).fetchall()
                
        except Exception as e:
            conn.close()
            return f"Erro fatal ao importar planilha headcount: {str(e)}"
            
    conn.close()
    
    hcs = [dict(ix) for ix in lista_hc]
    return render_template('headcount.html', hcs=hcs, is_master=acesso_total_hc, nome=session.get('nome'))

@app.route('/api/salvar_headcount', methods=['POST'])
def salvar_headcount():
    if 'matricula' not in session or (not session.get('is_master') and not session.get('is_planejador')):
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

@app.route('/api/upload_headcount', methods=['POST'])
def upload_headcount():
    if 'matricula' not in session or (not session.get('is_master') and not session.get('is_planejador')):
        return jsonify({'error': 'Não autorizado'}), 403
        
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
    try:
        import os, uuid
        import pandas as pd
        temp_filename = f"temp_upload_{uuid.uuid4().hex}.xlsx"
        file.save(temp_filename)
        
        # Identificando a linha de cabeçalho dinamicamente
        df_raw = pd.read_excel(temp_filename, header=None)
        header_idx = 0
        for i, rval in df_raw.iterrows():
            row_str = ' '.join([str(x).upper() for x in rval.values if pd.notna(x)])
            if 'EMPRESA' in row_str and 'SETOR' in row_str and 'GESTOR' in row_str:
                header_idx = i
                break
                
        df = pd.read_excel(temp_filename, header=header_idx)
        df = df.dropna(subset=[df.columns[0]])
        
        # Extrair colunas como lowercase para mapear posições
        cols = [str(c).lower().strip() for c in df.columns]
        
        def find_col(possible_names):
            for name in possible_names:
                for idx, col in enumerate(cols):
                    if name in col: return idx
            return -1

        indices = {
            'cod_emp': find_col(['cód. empresa', 'cod. empresa', 'empresa']),
            'nome_emp': find_col(['nome empresa']),
            'emp_hc': find_col(['empresa (hc)']),
            'cod_setor': find_col(['cód. setor', 'cod. setor', 'cod setor']),
            'mat_gestor': find_col(['matrícula gestor', 'matricula gestor', 'matricula do gestor']),
            'gestor': find_col(['gestor', 'nome gestor']),
            'ativ_hc': find_col(['atividade']),
            'nome_setor': find_col(['nome setor', 'setor']),
            'macro': find_col(['macro']),
            'cod_func': find_col(['cód. função', 'cód função', 'cod. função', 'cod função']),
            'desc_func': find_col(['descrição', 'descrição da função'])
        }
        
        # Fallback fixo para export
        if indices['macro'] == -1: indices['macro'] = 8
        if indices['cod_func'] == -1: indices['cod_func'] = 9
        if indices['desc_func'] == -1: indices['desc_func'] = 10
        
        qtd_cols = []
        for idx_c, c in enumerate(cols):
            if 'qtd' in c or '/26' in c or 'jan' in c or 'fev' in c:
                qtd_cols.append(idx_c)
        if len(qtd_cols) < 12:
            qtd_cols = list(range(len(cols)-12, len(cols)))
            
        conn = get_db_connection()
        conn.execute('DELETE FROM headcount')
        
        for i, row in df.iterrows():
            val_cod = str(row.iloc[indices['cod_emp']]).strip() if indices['cod_emp'] != -1 else ""
            if 'TOTAL' in val_cod.upper() or 'SUBTOTAL' in val_cod.upper() or len(val_cod) == 0 or val_cod == 'nan':
                continue
                
            matr_val = str(row.iloc[indices['mat_gestor']]).strip() if indices['mat_gestor'] != -1 else ""
            if matr_val == "nan": matr_val = ""
            if matr_val.endswith('.0'): matr_val = matr_val[:-2]
            
            def get_str(key):
                if indices[key] == -1: return ""
                v = str(row.iloc[indices[key]]).strip()
                return "" if v == "nan" else v
            
            qtd_vals = []
            for j in range(12):
                if j < len(qtd_cols):
                    v = row.iloc[qtd_cols[j]]
                    try:
                        qtd_vals.append(int(v) if pd.notna(v) and str(v).strip() != "" else 0)
                    except:
                        qtd_vals.append(0)
                else:
                    qtd_vals.append(0)
                    
            conn.execute('''
                INSERT INTO headcount (
                    cod_empresa, nome_empresa, empresa_hc, cod_setor, matricula_gestor, gestor,
                    atividade_hc, nome_setor, macro_area, cod_funcao, desc_funcao,
                    qtd_01, qtd_02, qtd_03, qtd_04, qtd_05, qtd_06,
                    qtd_07, qtd_08, qtd_09, qtd_10, qtd_11, qtd_12
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                val_cod, get_str('nome_emp'), get_str('emp_hc'), get_str('cod_setor'), matr_val, get_str('gestor'),
                get_str('ativ_hc'), get_str('nome_setor'), get_str('macro'), get_str('cod_func'), get_str('desc_func'),
                *qtd_vals
            ))
            
        conn.commit()
        conn.close()
        
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        return jsonify({'success': True, 'message': 'Base atualizada com sucesso!'})
        
    except Exception as e:
        return jsonify({'error': f'Falha ao processar arquivo: {str(e)}'}), 500

@app.route('/api/download_headcount', methods=['GET'])
def download_headcount():
    if 'matricula' not in session or (not session.get('is_master') and not session.get('is_planejador')):
        return jsonify({'error': 'Não autorizado'}), 403

    gestor = request.args.get('gestor', '').strip()

    conn = get_db_connection()
    import pandas as pd
    if gestor:
        df = pd.read_sql_query('SELECT * FROM headcount WHERE gestor = ?', conn, params=(gestor,))
    else:
        df = pd.read_sql_query('SELECT * FROM headcount', conn)
    conn.close()

    cols_map = {
        'cod_empresa': 'CÓD. EMPRESA',
        'nome_empresa': 'NOME EMPRESA',
        'empresa_hc': 'EMPRESA (HC)',
        'cod_setor': 'Cód. Setor',
        'matricula_gestor': 'Matrícula Gestor',
        'gestor': 'GESTOR',
        'atividade_hc': 'Atividade (HC)',
        'nome_setor': 'Nome Setor',
        'macro_area': 'MACRO ÁREA',
        'cod_funcao': 'Cód Função',
        'desc_funcao': 'Descrição da Função',
        'qtd_01': 'Qtd 01/26',
        'qtd_02': 'Qtd 02/26',
        'qtd_03': 'Qtd 03/26',
        'qtd_04': 'Qtd 04/26',
        'qtd_05': 'Qtd 05/26',
        'qtd_06': 'Qtd 06/26',
        'qtd_07': 'Qtd 07/26',
        'qtd_08': 'Qtd 08/26',
        'qtd_09': 'Qtd 09/26',
        'qtd_10': 'Qtd 10/26',
        'qtd_11': 'Qtd 11/26',
        'qtd_12': 'Qtd 12/26'
    }

    if df.empty:
        export_df = pd.DataFrame(columns=cols_map.values())
    else:
        # Preencher colunas faltantes no db se houver
        for c in cols_map.keys():
            if c not in df.columns: df[c] = ''
        export_df = df[list(cols_map.keys())].rename(columns=cols_map)

    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name='Headcount')
    output.seek(0)
    
    return send_file(output, download_name='Headcount_Atualizado.xlsx', as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# --- Efetivo Dashboard ---
@app.route('/efetivo')
def efetivo():
    if 'matricula' not in session:
        return redirect(url_for('login'))
    is_master = session.get('is_master', False)
    is_planejador = session.get('is_planejador', False)
    if session.get('tipo', 'simples') == 'simples':
        return redirect(url_for('index'))
    return render_template('efetivo.html', nome=session.get('nome'), is_master=is_master, is_planejador=is_planejador)

@app.route('/api/upload_efetivo', methods=['POST'])
def upload_efetivo():
    if not (session.get('is_master') or session.get('is_planejador')):
        return jsonify({'error': 'Não autorizado'}), 403
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Arquivo vazio'}), 400
    
    try:
        import pandas as pd
        df = pd.read_excel(file)
        # Manter apenas registros onde DATA DE DEMISSÃO é nulo (Ativos)
        if 'DATA DE DEMISSÃO' in df.columns:
            df = df[df['DATA DE DEMISSÃO'].isna()]
            
        required_cols = ['NOME COLIGADA', 'GESTOR', 'NOME C. CUSTO CONTÁBIL', 'NOME SETOR', 'FUNÇÃO ATUAL']
        for col in required_cols:
            if col not in df.columns:
                return jsonify({'error': f'Coluna obrigatória não encontrada: {col}'}), 400
                
        # Fill NA 
        df[required_cols] = df[required_cols].fillna('N/A')
        
        # Aggregate
        agg_df = df.groupby(required_cols).size().reset_index(name='quantidade')
        
        conn = get_db_connection()
        conn.execute('DELETE FROM efetivo_agg')
        
        for _, row in agg_df.iterrows():
            conn.execute('''
                INSERT INTO efetivo_agg (nome_coligada, gestor, macro_area, setor, funcao, quantidade)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (str(row['NOME COLIGADA']), str(row['GESTOR']), str(row['NOME C. CUSTO CONTÁBIL']), 
                  str(row['NOME SETOR']), str(row['FUNÇÃO ATUAL']), int(row['quantidade'])))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Base do Efetivo atualizada com sucesso!'})
    except Exception as e:
        return jsonify({'error': f'Falha ao processar arquivo: {str(e)}'}), 500

@app.route('/api/efetivo_filtros', methods=['GET'])
def efetivo_filtros():
    if 'matricula' not in session:
        return jsonify({'error': 'Não autorizado'}), 403
        
    conn = get_db_connection()
    try:
        query = 'SELECT DISTINCT nome_coligada, gestor, setor, macro_area, funcao FROM efetivo_agg WHERE 1=1'
        params = []
        is_master = session.get('is_master', False)
        is_planejador = session.get('is_planejador', False)
        
        if not (is_master or is_planejador):
            query += ' AND gestor = ?'
            nome_busca = session.get('gestor_nome') or session.get('nome')
            params.append(nome_busca)
            
        rows = conn.execute(query, params).fetchall()
        # Convert to list of dicts to be consumed by javascript cascade logic
        combos = [dict(r) for r in rows]
        
        filtros = {
            'combos': combos,
            'coligadas': sorted(list(set(r['nome_coligada'] for r in combos if r['nome_coligada']))),
            'gestores': sorted(list(set(r['gestor'] for r in combos if r['gestor']))),
            'setores': sorted(list(set(r['setor'] for r in combos if r['setor']))),
            'macro_areas': sorted(list(set(r['macro_area'] for r in combos if r['macro_area']))),
            'funcoes': sorted(list(set(r['funcao'] for r in combos if r['funcao'])))
        }
    except Exception as e:
        print(f"Error filtering: {e}")
        filtros = {'combos': [], 'coligadas': [], 'gestores': [], 'setores': [], 'macro_areas': [], 'funcoes': []}
    finally:
        conn.close()
        
    return jsonify(filtros)

@app.route('/api/efetivo_dados', methods=['POST'])
def efetivo_dados():
    if 'matricula' not in session:
        return jsonify({'error': 'Não autorizado'}), 403
        
    filters = request.json or {}
    
    query = 'SELECT gestor, setor, funcao, SUM(quantidade) as quantidade FROM efetivo_agg WHERE 1=1'
    params = []
    
    # Regra Gestor
    is_master = session.get('is_master', False)
    is_planejador = session.get('is_planejador', False)
    if not (is_master or is_planejador):
        query += ' AND gestor = ?'
        nome_busca = session.get('gestor_nome') or session.get('nome')
        params.append(nome_busca)
    else:
        if filters.get('gestores'):
            query += ' AND gestor IN ({})'.format(','.join(['?']*len(filters['gestores'])))
            params.extend(filters['gestores'])
            
    if filters.get('coligadas'):
        query += ' AND nome_coligada IN ({})'.format(','.join(['?']*len(filters['coligadas'])))
        params.extend(filters['coligadas'])
        
    if filters.get('macro_areas'):
        query += ' AND macro_area IN ({})'.format(','.join(['?']*len(filters['macro_areas'])))
        params.extend(filters['macro_areas'])
        
    if filters.get('funcoes'):
        query += ' AND funcao IN ({})'.format(','.join(['?']*len(filters['funcoes'])))
        params.extend(filters['funcoes'])
        
    query += ' GROUP BY gestor, setor, funcao ORDER BY quantidade DESC'
    
    conn = get_db_connection()
    try:
        rows = conn.execute(query, params).fetchall()
        data = [dict(r) for r in rows]
    except Exception as e:
        print(f"Error fetching: {e}")
        data = []
    finally:
        conn.close()
        
    return jsonify(data)

@app.route('/api/download_efetivo', methods=['POST'])
def download_efetivo():
    if 'matricula' not in session:
        return jsonify({'error': 'Não autorizado'}), 403
    
    filters = request.json or {}
    query = 'SELECT gestor as Gestor, setor as Setor, funcao as Cargo, SUM(quantidade) as Quantidade FROM efetivo_agg WHERE 1=1'
    params = []
    
    # Regra Gestor
    is_master = session.get('is_master', False)
    is_planejador = session.get('is_planejador', False)
    if not (is_master or is_planejador):
        query += ' AND gestor = ?'
        nome_busca = session.get('gestor_nome') or session.get('nome')
        params.append(nome_busca)
    else:
        if filters.get('gestores'):
            query += ' AND gestor IN ({})'.format(','.join(['?']*len(filters['gestores'])))
            params.extend(filters['gestores'])
            
    if filters.get('coligadas'):
        query += ' AND nome_coligada IN ({})'.format(','.join(['?']*len(filters['coligadas'])))
        params.extend(filters['coligadas'])
        
    if filters.get('setores'):
        query += ' AND setor IN ({})'.format(','.join(['?']*len(filters['setores'])))
        params.extend(filters['setores'])
        
    if filters.get('macro_areas'):
        query += ' AND macro_area IN ({})'.format(','.join(['?']*len(filters['macro_areas'])))
        params.extend(filters['macro_areas'])
        
    if filters.get('funcoes'):
        query += ' AND funcao IN ({})'.format(','.join(['?']*len(filters['funcoes'])))
        params.extend(filters['funcoes'])
        
    query += ' GROUP BY gestor, setor, funcao ORDER BY Quantidade DESC'
    
    conn = get_db_connection()
    import pandas as pd
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Efetivo')
    output.seek(0)
    
    return send_file(output, download_name='Efetivo_Agrupado.xlsx', as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/comparativo')
def comparativo():
    if 'matricula' not in session: return redirect(url_for('login'))
    tipo = session.get('tipo', 'simples')
    if tipo == 'simples':
        return redirect(url_for('index'))
    return render_template('comparativo.html', nome=session.get('nome', ''), is_master=session.get('is_master'), is_planejador=session.get('is_planejador'), tipo=tipo)

@app.route('/api/comparativo_dados', methods=['GET'])
def comparativo_dados():
    if 'matricula' not in session:
        return jsonify({'error': 'Não autorizado'}), 403
    tipo = session.get('tipo', 'simples')
    if tipo == 'simples':
        return jsonify({'error': 'Não autorizado'}), 403
        
    mes = request.args.get('mes')
    if not mes or not mes.isdigit() or not (1 <= int(mes) <= 12):
        return jsonify({'error': 'Mês inválido'}), 400
        
    mes_str = f"{int(mes):02d}"
    
    # Intermediário: filtra apenas pelo gestor logado
    gestor_filter = ''
    params = []
    if tipo == 'intermediario':
        gestor_filter = 'WHERE gestor = ?'
        params = [session.get('nome', '')]
    
    query = f'''
        WITH combined AS (
            SELECT gestor, nome_setor as setor, desc_funcao as funcao, qtd_{mes_str} as vagas, 0 as efetivo
            FROM headcount
            UNION ALL
            SELECT gestor, setor, funcao, 0 as vagas, quantidade as efetivo
            FROM efetivo_agg
        )
        SELECT gestor, setor, funcao, SUM(vagas) as orcado, SUM(efetivo) as realizado, SUM(vagas) - SUM(efetivo) as saldo
        FROM combined
        {gestor_filter}
        GROUP BY gestor, setor, funcao
        ORDER BY gestor, setor, funcao
    '''
    
    conn = get_db_connection()
    try:
        rows = conn.execute(query, params).fetchall()
        data = [dict(r) for r in rows]
    except Exception as e:
        print(f"Error fetching comparativo: {e}")
        data = []
    finally:
        conn.close()
        
    return jsonify(data)
@app.route('/relatorio')
def relatorio():
    if 'matricula' not in session: return redirect(url_for('login'))
    if not session.get('is_master'): return redirect(url_for('index'))
    # Planejador não tem acesso ao relatório
    if session.get('tipo', 'simples') == 'planejador': return redirect(url_for('index'))
    
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
@limiter.limit("10 per minute")
def login():
    if request.method == 'POST':
        matricula = request.form.get('matricula', '').strip()
        senha = request.form.get('senha', '').strip()
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM usuarios WHERE matricula = ?', (matricula,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['senha'], senha):
            session['matricula'] = user['matricula']
            session['nome'] = user['nome']
            tipo_usuario = user['tipo'] if user['tipo'] else ('master' if user['matricula'] in MASTERS_INICIAIS else 'simples')
            session['tipo'] = tipo_usuario
            session['is_master'] = (tipo_usuario == 'master')
            session['is_intermediario'] = (tipo_usuario == 'intermediario')
            session['is_planejador'] = (tipo_usuario == 'planejador')
            session['gestor_matricula'] = user['gestor_matricula'] if 'gestor_matricula' in user.keys() and user['gestor_matricula'] else ''
            
            # Buscar nome do gestor se houver gestor_matricula
            session['gestor_nome'] = ''
            if session['gestor_matricula']:
                conn = get_db_connection()
                g = conn.execute('SELECT nome FROM usuarios WHERE matricula = ?', (session['gestor_matricula'],)).fetchone()
                conn.close()
                if g:
                    session['gestor_nome'] = g['nome']
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
        conn.execute('UPDATE usuarios SET senha = ?, senha_resetada = 0 WHERE matricula = ?', (generate_password_hash(nova_senha), session['matricula']))
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
        
    matricula_origem = session.get('gestor_matricula') if session.get('gestor_matricula') else session['matricula']
    nome_origem = session.get('gestor_nome') if session.get('gestor_nome') else session.get('nome', '')
    
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
            matricula_empregado, nome_empregado, setor_origem, setor_destino, cargo_atual, cargo_proposto,
            mes_ano, status, observacao, dados_completos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Em análise', '', ?)
        ''', (
            matricula_origem, nome_origem, gestor_destino_mat, nome_gestor_dest,
            matr_emp, nome_emp, row.get('setorOrigem', ''), setor_dest, cargo_atual, cargo_prop, mes_ano_str,
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
        mes_ano = upd.get('mes_ano')
        
        if item_id and status:
            item = conn.execute("SELECT status as status_antigo, gestor_origem_mat, gestor_destino_mat, nome_empregado, cargo_proposto, mes_ano as mes_antigo FROM indicacoes_item WHERE id = ?", (item_id,)).fetchone()
            if item:
                status_antigo = item['status_antigo']
                mes_antigo = item['mes_antigo']
                if status in ['Aprovado', 'Reprovado']:
                    msg = f"A indicação de {item['nome_empregado']} para {item['cargo_proposto']} foi {status.upper()}."
                    gestores = set([item['gestor_origem_mat'], item['gestor_destino_mat']])
                    for gestor in gestores:
                        if gestor:
                            conn.execute("INSERT INTO notificacoes (matricula, mensagem) VALUES (?, ?)", (gestor, msg))
                
                acao_parts = []
                if status_antigo != status:
                    acao_parts.append(f'Alterou status de "{status_antigo}" para "{status}"')
                if mes_ano and mes_ano != mes_antigo:
                    acao_parts.append(f'Alterou Mês/Ano de "{mes_antigo}" para "{mes_ano}"')
                if obs:
                    acao_parts.append(f'Motivo: {obs}')
                acao_text = '. '.join(acao_parts) if acao_parts else f'Atualizou para "{status}"'
                conn.execute('INSERT INTO auditoria (indicacao_id, matricula, nome, acao) VALUES (?, ?, ?, ?)',
                             (item_id, session['matricula'], session.get('nome', ''), acao_text))
                             
            if mes_ano:
                conn.execute('UPDATE indicacoes_item SET status = ?, observacao = ?, mes_ano = ? WHERE id = ?',
                             (status, crypt_field(obs), mes_ano, item_id))
            else:
                conn.execute('UPDATE indicacoes_item SET status = ?, observacao = ? WHERE id = ?',
                             (status, crypt_field(obs), item_id))
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
    usuarios = conn.execute("SELECT u.matricula, u.nome, u.email, u.senha, COALESCE(u.tipo, 'simples') as tipo, COALESCE(u.gestor_matricula, '') as gestor_matricula, COALESCE(g.nome, '') as gestor_nome FROM usuarios u LEFT JOIN usuarios g ON u.gestor_matricula = g.matricula ORDER BY u.nome").fetchall()
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
    email = dados.get('email', '').strip()
    senha = dados.get('senha', '').strip()
    tipo = dados.get('tipo', 'simples')
    gestor_matricula = dados.get('gestor_matricula', '').strip()
    if not matricula or not nome or not senha:
        return jsonify({'error': 'Preencha todos os campos obrigatórios.'}), 400
    conn = get_db_connection()
    existe = conn.execute("SELECT matricula FROM usuarios WHERE matricula = ?", (matricula,)).fetchone()
    if existe:
        conn.close()
        return jsonify({'error': 'Matrícula já cadastrada no sistema.'}), 400
    conn.execute("INSERT INTO usuarios (matricula, nome, email, senha, tipo, gestor_matricula) VALUES (?, ?, ?, ?, ?, ?)", (matricula, nome, email, generate_password_hash(senha), tipo, gestor_matricula))
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
    if not matricula or novo_tipo not in ['master', 'intermediario', 'simples', 'planejador']:
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
    
    # Se não enviou senha, gerar uma aleatória de 6 caracteres
    import string, random
    nova_senha = dados.get('nova_senha', '').strip()
    if not nova_senha:
        nova_senha = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

    if not matricula:
        return jsonify({'error': 'Dados inválidos'}), 400
        
    conn = get_db_connection()
    user = conn.execute("SELECT nome, email FROM usuarios WHERE matricula = ?", (matricula,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'Usuário não encontrado'}), 404
        
    conn.execute("UPDATE usuarios SET senha = ?, senha_resetada = 1 WHERE matricula = ?", (generate_password_hash(nova_senha), matricula))
    conn.commit()
    conn.close()
    
    # Enviar e-mail se houver e-mail cadastrado
    info_email = ""
    if user['email']:
        enviado = enviar_email_reset(user['email'], user['nome'], nova_senha)
        info_email = " e e-mail de notificação enviado" if enviado else " (erro ao enviar e-mail)"
    
    return jsonify({
        'success': True, 
        'message': f'Senha resetada para "{nova_senha}"{info_email}!',
        'nova_senha': nova_senha,
        'email': user['email'],
        'nome': user['nome'],
        'matricula': matricula
    })


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

@app.route('/api/admin/alterar_email', methods=['POST'])
def alterar_email_usuario():
    if 'matricula' not in session or not session.get('is_master'):
        return jsonify({'error': 'Não autorizado'}), 403
    dados = request.get_json()
    matricula = dados.get('matricula')
    novo_email = dados.get('email', '').strip()
    if not matricula:
        return jsonify({'error': 'Dados inválidos'}), 400
    conn = get_db_connection()
    conn.execute("UPDATE usuarios SET email = ? WHERE matricula = ?", (novo_email, matricula))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'E-mail do usuário atualizado com sucesso!'})



if __name__ == '__main__':
    from waitress import serve
    import os
    port = int(os.environ.get('PORT', 5000))
    print(f"Servidor de Produção Waitress rodando na porta {port}...")
    serve(app, host='0.0.0.0', port=port)
