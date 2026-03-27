import requests
import json

payload = {
    "responsavelDestino": "1-082959 - Gustavo Henrique Eiras Hülse",
    "rows": [
        {
            "matriculaCompleta": "1-12345",
            "nome": "Empregado Teste",
            "setorDestino": "Vendas",
            "cargoAtual": "Analista",
            "cargoProposto": "Coordenador"
        }
    ]
}

try:
    with requests.Session() as s:
        login_res = s.post('http://localhost:5000/login', data={'matricula': '1-049896', 'senha': '1-049896'})
        r = s.post('http://localhost:5000/api/salvar', json=payload)
        print("STATUS:", r.status_code)
        
        # If it's a 500 HTML error, extract the traceback or title
        if r.status_code == 500:
            import re
            match = re.search(r'<title>(.*?)</title>', r.text, re.IGNORECASE)
            if match:
                print("ERROR TITLE:", match.group(1))
            # get the traceback if werkzeug
            tb = re.search(r'<h2>([^<]+)</h2>', r.text)
            if tb:
                print("TRACE:", tb.group(1))
        else:
            print("RESPONSE:", r.text[:500])
except Exception as e:
    print("Connection failed:", e)
