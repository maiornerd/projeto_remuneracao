import sqlite3, os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.db')
print("DB:", db_path)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Descobrir quais status existem
statuses = conn.execute("SELECT DISTINCT status FROM indicacoes_item").fetchall()
print("=== Status existentes ===")
for s in statuses:
    print(repr(s['status']))

# Contar quantos são "Em análise"
row = conn.execute("SELECT COUNT(*) as qtd FROM indicacoes_item WHERE status = 'Em análise'").fetchone()
pendentes = row['qtd']
print(f"\nPendentes Em análise: {pendentes}")

# Inserir/atualizar notificação para Masters
masters = ['1-082959', '1-082361', '1-079254']
msg = f"Você tem {pendentes} Novas Indicações aguardando análise! Acesse: Visualizar Indicações."

if pendentes > 0:
    for m in masters:
        existe = conn.execute(
            "SELECT id FROM notificacoes WHERE matricula = ? AND mensagem LIKE 'Você tem % Novas Indicações aguardando análise!%'", (m,)
        ).fetchone()
        if existe:
            conn.execute("UPDATE notificacoes SET mensagem = ?, lida = 0, data_criacao = CURRENT_TIMESTAMP WHERE id = ?", (msg, existe['id']))
            print(f"  Atualizado para {m}")
        else:
            conn.execute("INSERT INTO notificacoes (matricula, mensagem, lida) VALUES (?, ?, 0)", (m, msg))
            print(f"  Inserido para {m}")
    conn.commit()
else:
    print("Nenhum pendente encontrado - limpando notificações do tipo 'aguardando análise'")
    for m in masters:
        conn.execute(
            "DELETE FROM notificacoes WHERE matricula = ? AND mensagem LIKE 'Você tem % Novas Indicações aguardando análise!%'", (m,)
        )
    conn.commit()

# Verificar resultado
all_notifs = conn.execute("SELECT * FROM notificacoes").fetchall()
print(f"\n=== Notificações no DB: {len(all_notifs)} ===")
for n in all_notifs:
    print(f"  ID={n['id']} mat={n['matricula']} lida={n['lida']} msg={n['mensagem'][:60]}")

conn.close()
print("\nFINISHED!")
