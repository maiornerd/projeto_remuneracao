import sqlite3
import json
import os

def test_aggregation_logic():
    db_path = 'app.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # 1. Garantir que a coluna existe (simulando get_db_connection)
    try:
        conn.execute('ALTER TABLE indicacoes_item ADD COLUMN setor_origem TEXT')
    except sqlite3.OperationalError:
        pass
    
    # 2. Inserir dados de teste (Aprovados)
    # Movimentação 1: Setor A -> Setor B
    conn.execute('''
        INSERT INTO indicacoes_item 
        (nome_empregado, setor_origem, setor_destino, status)
        VALUES ('Emp A', 'Setor Alpha', 'Setor Beta', 'Aprovado')
    ''')
    
    # Movimentação 2: Setor B -> Setor C
    conn.execute('''
        INSERT INTO indicacoes_item 
        (nome_empregado, setor_origem, setor_destino, status)
        VALUES ('Emp B', 'Setor Beta', 'Setor Gamma', 'Aprovado')
    ''')

    # Movimentação 3: Setor A -> Setor C
    conn.execute('''
        INSERT INTO indicacoes_item 
        (nome_empregado, setor_origem, setor_destino, status)
        VALUES ('Emp C', 'Setor Alpha', 'Setor Gamma', 'Aprovado')
    ''')
    
    # 3. Simular lógica da rota /movimentacoes para um gestor que cuida do "Setor Alpha" e "Setor Beta"
    setores_gestao = ['Setor Alpha', 'Setor Beta']
    
    placeholders = ','.join(['?'] * len(setores_gestao))
    query = f'''
        SELECT * FROM indicacoes_item 
        WHERE status = 'Aprovado' 
        AND (setor_origem IN ({placeholders}) OR setor_destino IN ({placeholders}))
    '''
    rows = conn.execute(query, setores_gestao + setores_gestao).fetchall()
    
    stats = {}
    total_entradas = 0
    total_saidas = 0
    
    for r in rows:
        row_dict = dict(r)
        s_orig = row_dict['setor_origem']
        s_dest = row_dict['setor_destino']
        
        if s_orig in setores_gestao:
            stats.setdefault(s_orig, {'entradas': 0, 'saidas': 0})['saidas'] += 1
            total_saidas += 1
            
        if s_dest in setores_gestao:
            stats.setdefault(s_dest, {'entradas': 0, 'saidas': 0})['entradas'] += 1
            total_entradas += 1

    print(json.dumps({
        'stats': stats,
        'total_entradas': total_entradas,
        'total_saidas': total_saidas,
        'saldo': total_entradas - total_saidas
    }, indent=2))
    
    # Limpeza (opcional, mas bom pra teste repetido)
    conn.execute("DELETE FROM indicacoes_item WHERE nome_empregado LIKE 'Emp %'")
    conn.commit()
    conn.close()

if __name__ == '__main__':
    test_aggregation_logic()
