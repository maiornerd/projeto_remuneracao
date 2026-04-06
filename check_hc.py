import pandas as pd
import shutil
import traceback

print("Copiando arquivo...")
try:
    shutil.copy2('HEADCOUNT 2026.xlsx', 'HEADCOUNT_TEST.xlsx')
    print("Arquivo copiado.")
    df = pd.read_excel('HEADCOUNT_TEST.xlsx', header=1)
    
    with open('output_hc.txt', 'w', encoding='utf-8') as f:
        f.write("COLUMNS:\n")
        for i, col in enumerate(df.columns):
            f.write(f"{i}: {col}\n")
        f.write("\nFIRST DATAFRAME ROW:\n")
        for i, val in enumerate(df.iloc[0]):
            f.write(f"{i}: {val}\n")
            
    print("Concluido e escrito em output_hc.txt!")
except Exception as e:
    with open('output_hc.txt', 'w', encoding='utf-8') as f:
        f.write(traceback.format_exc())
    print("Erro capturado e escrito em output_hc.txt")
