import pandas as pd
import sqlite3
import shutil
import traceback

try:
    print("Fazendo copia local para evitar lock...")
    shutil.copy2("HEADCOUNT 2026.xlsx", "temp_hc.xlsx")

    df = pd.read_excel("temp_hc.xlsx", header=1)

    # Drop any rows where 'CÓD. EMPRESA' is NaN (e.g. subtotals from top header)
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

    for i, row in df.iterrows():
        # Ignorar o Total/Subtotal que está flutuando se ainda existir
        if 'TOTAL' in str(row.iloc[0]).upper() or 'SUBTOTAL' in str(row.iloc[0]).upper():
            continue
            
        conn.execute('''
            INSERT INTO headcount (
                cod_empresa, nome_empresa, empresa_hc, cod_setor, matricula_gestor, gestor,
                atividade_hc, nome_setor, macro_area, cod_funcao, desc_funcao,
                qtd_01, qtd_02, qtd_03, qtd_04, qtd_05, qtd_06,
                qtd_07, qtd_08, qtd_09, qtd_10, qtd_11, qtd_12
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            str(row.iloc[0]), str(row.iloc[1]), str(row.iloc[2]), str(row.iloc[3]), str(row.iloc[4]).strip(), str(row.iloc[5]),
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
    conn.commit()
    conn.close()

    with open('import_success.txt', 'w') as f:
        f.write('Importado com sucesso!')
except Exception as e:
    with open('import_error.txt', 'w') as f:
        f.write(traceback.format_exc())
