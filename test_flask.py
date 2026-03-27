from app import app
import json

app.testing = True
client = app.test_client()

with client.session_transaction() as sess:
    sess['matricula'] = '1-049896'
    sess['nome'] = 'Teste'

response = client.post('/api/salvar', json={
    'responsavelDestino': '1-082959 - Gustavo Henrique Eiras Hülse',
    'rows': [{'matriculaCompleta': '1-1234', 'nome': 'A', 'setorDestino': 'B', 'cargoAtual': 'C', 'cargoProposto': 'D'}]
})

print("STATUS CODe:", response.status_code)
print("RESPONSE BODY:", response.get_data(as_text=True)[:1000])
