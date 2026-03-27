import re

with open('templates/formulario.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Fix exportCSV
old_csv_download = """
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
"""
new_csv_download = """
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            setTimeout(() => {
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
            }, 100);
        }
"""
html = html.replace(old_csv_download, new_csv_download)

# Fix generatePDF and sendEmail PDF saving
# find both doc.save(`Indicacoes_Promocao_${date}.pdf`);
old_doc_save = "doc.save(`Indicacoes_Promocao_${date}.pdf`);"
new_doc_save = """
            const pdfBlob = doc.output('blob');
            const pdfUrl = URL.createObjectURL(pdfBlob);
            const pdfLink = document.createElement('a');
            pdfLink.href = pdfUrl;
            pdfLink.download = `Indicacoes_Promocao_${date}.pdf`;
            document.body.appendChild(pdfLink);
            pdfLink.click();
            setTimeout(() => {
                document.body.removeChild(pdfLink);
                URL.revokeObjectURL(pdfUrl);
            }, 100);
"""
html = html.replace(old_doc_save, new_doc_save)

# Fix sendEmail CSV download
old_email_csv = """
    csvLink.style.visibility = 'hidden';
    document.body.appendChild(csvLink);
    csvLink.click();
    document.body.removeChild(csvLink);

    // --- 5. MONTA E ABRE O THUNDERBIRD VIA MAILTO ---
"""
new_email_csv = """
    csvLink.style.visibility = 'hidden';
    document.body.appendChild(csvLink);
    csvLink.click();
    setTimeout(() => {
        document.body.removeChild(csvLink);
        URL.revokeObjectURL(csvUrl);
    }, 100);

    // --- 5. MONTA E ABRE O THUNDERBIRD VIA MAILTO ---
"""
html = html.replace(old_email_csv, new_email_csv)

with open('templates/formulario.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Downloads fixed.")
