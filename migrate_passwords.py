import sqlite3
import os
from werkzeug.security import generate_password_hash

def migrate_passwords():
    db_path = os.path.join(os.path.dirname(__file__), 'app.db')
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Assuming primary key of usuarios is not 'id' but might be 'matricula' if there is no 'id' 
    # Let's check schema. Actually app.py doesn't show schema of `usuarios`.
    # It shows "SELECT * FROM usuarios WHERE matricula = ?". Let's update by 'matricula'.
    try:
        users = conn.execute("SELECT matricula, senha FROM usuarios").fetchall()
    except sqlite3.OperationalError as e:
        print("Error fetching from usuarios: " + str(e))
        return

    updated = 0
    skipped = 0
    for user in users:
        senha = user['senha']
        matricula = user['matricula']
        
        # Check if already hashed
        if senha and (senha.startswith('scrypt:') or senha.startswith('pbkdf2:')):
            skipped += 1
            continue

        if senha:
            hashed = generate_password_hash(senha)
            conn.execute("UPDATE usuarios SET senha = ? WHERE matricula = ?", (hashed, matricula))
            updated += 1
        else:
            skipped += 1

    conn.commit()
    conn.close()
    print(f"Migration complete: {updated} users updated with hashed passwords, {skipped} users skipped.")

if __name__ == '__main__':
    migrate_passwords()
