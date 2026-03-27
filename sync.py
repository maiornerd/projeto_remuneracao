from app import get_db_connection, atualizar_notificacao_master
conn = get_db_connection()
atualizar_notificacao_master(conn, False)
conn.commit()
print("ROWS: ", conn.execute("SELECT COUNT(*) FROM notificacoes").fetchone()[0])
conn.close()
print('DONE')
