import re

# -------------
# 1. Patch app.py
# -------------
with open('app.py', 'r', encoding='utf-8') as f:
    app_code = f.read()

# Add get_gestores route and change get_opcoes to accept args
app_code = app_code.replace("matricula = session['matricula']\n    conn =", 
"""matricula = request.args.get('matricula', session['matricula'])
    conn =""")

gestores_route = """
@app.route('/api/gestores')
def get_gestores():
    if 'matricula' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
    conn = get_db_connection()
    gestores = conn.execute('SELECT matricula, nome FROM usuarios ORDER BY nome').fetchall()
    conn.close()
    return jsonify([dict(g) for g in gestores])

@app.route('/api/opcoes')
"""
app_code = app_code.replace("@app.route('/api/opcoes')", gestores_route)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(app_code)

# -------------
# 2. Patch templates/formulario.html
# -------------
with open('templates/formulario.html', 'r', encoding='utf-8') as f:
    html = f.read()

# A. Change Nome do Responsavel input
html = re.sub(
    r'<input type="text" id="responsavel".*?>',
    r'<input type="text" id="responsavel" value="{{ nome_gestor }}" placeholder="Digite o nome do responsável" readonly style="background-color: #f0f0f0;">',
    html
)

# B. Add Responsavel de Destino field
new_field = """
                <div class="form-group">
                    <label for="responsavel_destino" class="required-field">Responsável de Destino</label>
                    <select id="responsavel_destino" onchange="carregarOpcoesDestino(); saveData()" required>
                        <option value="">-- Carregando gestores... --</option>
                    </select>
                </div>
"""
# Find where the first form-group closes and inject right after
html = re.sub(
    r'(<div class="form-group">\s*<label for="responsavel" class="required-field">Nome do Responsável</label>\s*<input[^>]+>\s*</div>)',
    r'\1\n' + new_field,
    html,
    flags=re.DOTALL
)

# C. Update grid-template-columns for form-row to 3 columns
html = re.sub(r'grid-template-columns: repeat\(2, 1fr\);', r'grid-template-columns: repeat(3, 1fr);', html)

# D. Inject JS logic for new features
js_injection = """
        window.opcoesDestino = [];
        
        // Fetch gestores on load
        document.addEventListener('DOMContentLoaded', function() {
            fetch('/api/gestores')
                .then(r => r.json())
                .then(data => {
                    const selectDestino = document.getElementById('responsavel_destino');
                    if(data.error) return;
                    selectDestino.innerHTML = '<option value="">-- Selecione o Gestor de Destino --</option>';
                    data.forEach(g => {
                        selectDestino.innerHTML += `<option value="${g.matricula}">${g.nome}</option>`;
                    });
                    
                    // Restore from localStorage se existir dados preenchidos
                    setTimeout(() => {
                        const savedData = localStorage.getItem('tabelaIndicacoesData');
                        if (savedData) {
                             const parsed = JSON.parse(savedData);
                             if(parsed.responsavel_destino) {
                                 selectDestino.value = parsed.responsavel_destino;
                                 carregarOpcoesDestino();
                             }
                        }
                    }, 500);
                });
        });

        function carregarOpcoesDestino() {
            const matDestino = document.getElementById('responsavel_destino').value;
            if(!matDestino) {
                window.opcoesDestino = [];
                atualizarLinhasAtuais();
                return;
            }
            fetch('/api/opcoes?matricula=' + matDestino)
                .then(r => r.json())
                .then(data => {
                    window.opcoesDestino = data;
                    atualizarLinhasAtuais(); // re-render inputs para usar info do destino
                });
        }
"""
html = html.replace("window.opcoesGestor = [];", "window.opcoesGestor = [];\n" + js_injection)

# Modify getOpcoesHtml to look at opcoesDestino for Destino fields
html = html.replace(
"""function getOpcoesHtml(tipo, valorAtual) {""",
"""function getOpcoesHtml(tipo, valorAtual, isDestino = false) {
            const baseOpcoes = isDestino ? window.opcoesDestino : window.opcoesGestor;
"""
)

html = re.sub(
    r'const opcoesFiltradas = window\.opcoesGestor\.filter',
    r'const opcoesFiltradas = baseOpcoes.filter',
    html
)

html = html.replace(
    """selSetorD.innerHTML = getOpcoesHtml('setor', selSetorD.value);""",
    """selSetorD.innerHTML = getOpcoesHtml('setor', selSetorD.value, true);"""
)
html = html.replace(
    """selCargoP.innerHTML = getOpcoesHtml('cargo', selCargoP.value);""",
    """selCargoP.innerHTML = getOpcoesHtml('cargo', selCargoP.value, true);"""
)
html = html.replace(
    """${getOpcoesHtml("setor", v("setorDestino"))}""",
    """${getOpcoesHtml("setor", v("setorDestino"), true)}"""
)
html = html.replace(
    """${getOpcoesHtml("cargo", v("cargoProposto"))}""",
    """${getOpcoesHtml("cargo", v("cargoProposto"), true)}"""
)

# E. Update saveData
html = html.replace(
"""const dataToSave = {
                responsavel: responsavel,
                empresa: empresa,""",
"""const responsavel_destino = document.getElementById('responsavel_destino') ? document.getElementById('responsavel_destino').value : '';
            const dataToSave = {
                responsavel: responsavel,
                responsavel_destino: responsavel_destino,
                empresa: empresa,"""
)


with open('templates/formulario.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Patch features success!")
