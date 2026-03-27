import sqlite3
import pandas as pd
import json

def init_db():
    print("Lendo base_dados.xlsx...")
    df = pd.read_excel('base_dados.xlsx', sheet_name='Planilha2')
    
    # Renomeando as colunas pelos índices para ignorar problemas de acentuação/encoding
    df.columns = [
        "COD_EMPRESA_TXT", "COD_EMPRESA", "NOME_EMPRESA", "EMPRESA_HC", "COD_SETOR_HC",
        "COD_SETOR", "MATRICULA_GESTOR", "NOME_GESTOR", "ATIVIDADE_HC", "NOME_SETOR",
        "DESC_AREA", "MACRO_AREA", "COD_FUNCAO", "DESC_FUNCAO"
    ]
    
    # Filtrar apenas as linhas que possuem um gestor definido
    df = df.dropna(subset=['MATRICULA_GESTOR'])
    
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    
    # Criar tabela de usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            matricula TEXT PRIMARY KEY,
            nome TEXT,
            senha TEXT
        )
    ''')
    
    # Criar tabela de acessos denormalizada para facilitar as buscas no Flask
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opcoes_gestor (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT,
            cod_empresa INTEGER,
            nome_empresa TEXT,
            cod_setor INTEGER,
            nome_setor TEXT,
            cod_funcao TEXT,
            nome_funcao TEXT
        )
    ''')
    
    # Criar tabela de indicações nativa antiga
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS indicacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT,
            dados_json TEXT,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Criar tabela de itens granulares
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
    
    # Limpar dados antigos caso o script seja rodado novamente
    cursor.execute('DELETE FROM usuarios')
    cursor.execute('DELETE FROM opcoes_gestor')
    
    # Inserir usuários únicos (definindo a senha padrão igual à matrícula)
    usuarios_unicos = df[['MATRICULA_GESTOR', 'NOME_GESTOR']].drop_duplicates()
    for _, row in usuarios_unicos.iterrows():
        matricula = str(row['MATRICULA_GESTOR']).strip()
        nome = str(row['NOME_GESTOR']).strip()
        senha = matricula 
        cursor.execute('INSERT INTO usuarios (matricula, nome, senha) VALUES (?, ?, ?)', (matricula, nome, senha))
    
    # Inserir as opções (setores e cargos) atrelados a cada matrícula
    count = 0
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT INTO opcoes_gestor (matricula, cod_empresa, nome_empresa, cod_setor, nome_setor, cod_funcao, nome_funcao)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(row['MATRICULA_GESTOR']).strip(),
            row['COD_EMPRESA'] if pd.notnull(row['COD_EMPRESA']) else 0,
            str(row['NOME_EMPRESA']).strip(),
            row['COD_SETOR'] if pd.notnull(row['COD_SETOR']) else 0,
            str(row['NOME_SETOR']).strip(),
            str(row['COD_FUNCAO']).strip(),
            str(row['DESC_FUNCAO']).strip()
        ))
        count += 1
        
    # Inserir usuários Master obrigatórios caso não existam na base Excel
    masters_obrigatorios = [
        ('1-082959', 'Gustavo Henrique Eiras Hülse', '1-082959'),
        ('1-082361', 'Alan da Silva do Carmo', '1-082361'),
        ('1-079254', 'Cristiane Covatti', '1-079254')
    ]
    for m in masters_obrigatorios:
        cursor.execute("INSERT OR IGNORE INTO usuarios (matricula, nome, senha) VALUES (?, ?, ?)", m)
        
    conn.commit()
    conn.close()
    print(f"Banco de dados 'app.db' criado! Foram inseridos {len(usuarios_unicos)} usuários e {count} opções de cargos/setores.")

if __name__ == '__main__':
    init_db()
