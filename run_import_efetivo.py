import pandas as pd
import sqlite3
import sys
import os

sys.path.append(os.path.abspath('.'))
from app import init_db_schema

print("Inicializando DB...")
init_db_schema()

print("Lendo excel...")
df = pd.read_excel('efetivo.XLSX')

print("Filtrando e agrupando...")
if 'DATA DE DEMISSÃO' in df.columns:
    df = df[df['DATA DE DEMISSÃO'].isna()]

req = ['NOME COLIGADA', 'GESTOR', 'NOME C. CUSTO CONTÁBIL', 'NOME SETOR', 'FUNÇÃO ATUAL']
df[req] = df[req].fillna('N/A')
agg = df.groupby(req).size().reset_index(name='qtd')

print("Salvando no DB...", len(agg), "grupos gerados")
db_path = os.path.abspath(os.path.join('..', 'secure_data', 'app.db'))
c = sqlite3.connect(db_path)

c.execute('DELETE FROM efetivo_agg')
for _, r in agg.iterrows():
    c.execute('INSERT INTO efetivo_agg (nome_coligada,gestor,macro_area,setor,funcao,quantidade) VALUES (?,?,?,?,?,?)',
              (str(r['NOME COLIGADA']), str(r['GESTOR']), str(r['NOME C. CUSTO CONTÁBIL']), str(r['NOME SETOR']), str(r['FUNÇÃO ATUAL']), int(r['qtd'])))

c.commit()
c.close()
print('Feito com sucesso.')
