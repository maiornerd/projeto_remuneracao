import os
import re

import os
import glob
html_file = None
for f in os.listdir('.'):
    if f.startswith('FormularioIndic') and f.endswith('.html') and 'v5' in f:
        html_file = f
        break
with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()
file_path = 'templates/formulario.html'

# 1. Inject global variable and fetch logic
script_start_idx = content.find('<script>') + len('<script>')
inject_code = """
        // --- INJECAO BACKEND ---
        window.opcoesGestor = [];
        
        // Remove old generic DOMContentLoaded
        document.addEventListener('DOMContentLoaded', function() {
            fetch('/api/opcoes')
                .then(r => r.json())
                .then(data => {
                    if(data.error) {
                        window.location.href = '/login';
                        return;
                    }
                    window.opcoesGestor = data;
                    atualizarOpcoesEmpresa();
                    loadData(); // mantem a lógica original para carregar a tabela
                })
                .catch(err => {
                    console.error('Erro ao buscar opções:', err);
                    loadData();
                });
        });

        function atualizarOpcoesEmpresa() {
            const selectEmpresa = document.getElementById('empresa');
            // Pegar empresas unicas
            const empresasMap = new Map();
            window.opcoesGestor.forEach(op => {
                if(!empresasMap.has(op.cod_empresa)) {
                    empresasMap.set(op.cod_empresa, op.nome_empresa);
                }
            });
            
            // Se nao existem opcoes (admin vazio, por exemplo), nao deleta as originais
            if(empresasMap.size === 0) return;
            
            const valorAtual = selectEmpresa.value;
            selectEmpresa.innerHTML = '<option value="">-- Selecione --</option>';
            empresasMap.forEach((nome, cod) => {
                const selected = (cod.toString() === valorAtual.toString()) ? 'selected' : '';
                selectEmpresa.innerHTML += `<option value="${cod}" ${selected}>${cod} - ${nome}</option>`;
            });
        }

        function getOpcoesHtml(tipo, valorAtual) {
            const selectEmpresa = document.getElementById('empresa');
            const codEmpresa = selectEmpresa ? selectEmpresa.value : null;
            
            if(!codEmpresa) return '<option value="">Selecione a Empresa primeiro</option>';
            
            const opcoesFiltradas = window.opcoesGestor.filter(op => op.cod_empresa.toString() === codEmpresa.toString());
            const itensUnicos = new Set();
            
            opcoesFiltradas.forEach(op => {
                if(tipo === 'setor') itensUnicos.add(op.nome_setor);
                if(tipo === 'cargo') itensUnicos.add(op.nome_funcao);
            });
            
            let html = '<option value="">-- Selecione --</option>';
            if(valorAtual && !itensUnicos.has(valorAtual)) {
                html += `<option value="${valorAtual}" selected>${valorAtual}</option>`;
            }
            
            Array.from(itensUnicos).sort().forEach(item => {
                const selected = (item === valorAtual) ? 'selected' : '';
                html += `<option value="${item}" ${selected}>${item}</option>`;
            });
            
            return html;
        }

        function atualizarLinhasAtuais() {
            const rows = document.querySelectorAll('#tableBody tr');
            rows.forEach(row => {
                const selSetorO = row.querySelector('[data-field="setorOrigem"]');
                const selCargoA = row.querySelector('[data-field="cargoAtual"]');
                const selSetorD = row.querySelector('[data-field="setorDestino"]');
                const selCargoP = row.querySelector('[data-field="cargoProposto"]');
                if(selSetorO && selSetorO.tagName === 'SELECT') selSetorO.innerHTML = getOpcoesHtml('setor', selSetorO.value);
                if(selCargoA && selCargoA.tagName === 'SELECT') selCargoA.innerHTML = getOpcoesHtml('cargo', selCargoA.value);
                if(selSetorD && selSetorD.tagName === 'SELECT') selSetorD.innerHTML = getOpcoesHtml('setor', selSetorD.value);
                if(selCargoP && selCargoP.tagName === 'SELECT') selCargoP.innerHTML = getOpcoesHtml('cargo', selCargoP.value);
            });
        }
        // -------------------------
"""
content = content[:script_start_idx] + inject_code + content[script_start_idx:]

# Remove o document.addEventListener original para evitar conflito
content = re.sub(r'document\.addEventListener\(\'DOMContentLoaded\', function\(\) \{\s*loadData\(\);\s*\}\);', '', content)

# 2. Modify addRow to use selects
content = re.sub(
    r'<input type=\"text\" class=\"cell-input\" data-field=\"setorOrigem\".*?>',
    r'<select class="cell-select" data-field="setorOrigem" onchange="saveData()" onkeydown="handleCellKeydown(event)">${getOpcoesHtml("setor", v("setorOrigem"))}</select>',
    content
)
content = re.sub(
    r'<input type=\"text\" class=\"cell-input\" data-field=\"cargoAtual\".*?>',
    r'<select class="cell-select" data-field="cargoAtual" onchange="saveData()" onkeydown="handleCellKeydown(event)">${getOpcoesHtml("cargo", v("cargoAtual"))}</select>',
    content
)
content = re.sub(
    r'<input type=\"text\" class=\"cell-input\" data-field=\"setorDestino\".*?>',
    r'<select class="cell-select" data-field="setorDestino" onchange="saveData()" onkeydown="handleCellKeydown(event)">${getOpcoesHtml("setor", v("setorDestino"))}</select>',
    content
)
content = re.sub(
    r'<input type=\"text\" class=\"cell-input\" data-field=\"cargoProposto\".*?>',
    r'<select class="cell-select" data-field="cargoProposto" onchange="saveData()" onkeydown="handleCellKeydown(event)">${getOpcoesHtml("cargo", v("cargoProposto"))}</select>',
    content
)

# 3. Change saveData to post
save_data_patch = """
            const dataToSave = {
                responsavel: responsavel,
                empresa: empresa,
                rows: rows
            };

            fetch('/api/salvar', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(dataToSave)
            })
            .then(r => r.json())
            .then(res => {
                if(res.success) {
                    showSaveIndicator();
                }
            });
            
            localStorage.setItem('tabelaIndicacoesData', JSON.stringify(dataToSave));
"""
content = re.sub(
    r'const dataToSave = \{[\s\S]*?\};\s*localStorage\.setItem\(\'tabelaIndicacoesData\', JSON\.stringify\(dataToSave\)\);\s*showSaveIndicator\(\);',
    save_data_patch,
    content
)

# Fix event listener on empresa
content = content.replace('id="empresa" onchange="saveData()"', 'id="empresa" onchange="atualizarLinhasAtuais(); saveData()"')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch aplicado com sucesso!")
