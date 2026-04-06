import sqlite3

def migrate():
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    
    print("Criando tabela 'efetivo'...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS efetivo (
            matricula TEXT PRIMARY KEY,
            nome TEXT,
            cargo TEXT,
            secao_codigo TEXT,
            secao_nome TEXT,
            gestor_nome TEXT,
            macro_area TEXT,
            area_divisao TEXT,
            coligada_codigo TEXT,
            coligada_nome TEXT,
            data_admissao TEXT,
            situacao TEXT,
            extra_json TEXT
        )
    ''')
    
    # Aproveitar para garantir que a tabela usuarios tem a coluna email
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")
        print("Coluna 'email' adicionada à tabela 'usuarios'.")
    except sqlite3.OperationalError:
        print("Coluna 'email' já existe na tabela 'usuarios'.")

    # Garante que a tabela usuarios tem as colunas tipo, gestor_matricula, senha_resetada
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN tipo TEXT DEFAULT 'simples'")
        print("Coluna 'tipo' adicionada à tabela 'usuarios'.")
    except sqlite3.OperationalError: pass

    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN gestor_matricula TEXT")
        print("Coluna 'gestor_matricula' adicionada à tabela 'usuarios'.")
    except sqlite3.OperationalError: pass

    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN senha_resetada INTEGER DEFAULT 0")
        print("Coluna 'senha_resetada' adicionada à tabela 'usuarios'.")
    except sqlite3.OperationalError: pass
    
    # Tabela indicacoes_item - setor_origem
    try:
        cursor.execute("ALTER TABLE indicacoes_item ADD COLUMN setor_origem TEXT")
        print("Coluna 'setor_origem' adicionada à tabela 'indicacoes_item'.")
    except sqlite3.OperationalError: pass

    conn.commit()
    conn.close()
    print("Migração concluída com sucesso!")

if __name__ == '__main__':
    migrate()
