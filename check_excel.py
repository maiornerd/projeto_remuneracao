import pandas as pd
import json

file_path = 'base_dados.xlsx'
try:
    xl = pd.ExcelFile(file_path)
    res = {}
    for sheet_name in xl.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        res[sheet_name] = {
            'columns': list(df.columns),
            'head': df.head(3).to_dict('records')
        }
    print(json.dumps(res, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error reading excel: {e}")
