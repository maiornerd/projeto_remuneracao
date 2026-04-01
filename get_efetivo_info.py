import pandas as pd
import json
import os

file_path = 'EFETIVO.xlsx'
try:
    if os.path.exists(file_path):
        df = pd.read_excel(file_path, nrows=5)
        res = {
            'columns': df.columns.tolist(),
            'rows': df.head(3).astype(str).to_dict(orient='records')
        }
        with open('efetivo_info.json', 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print("Success: efetivo_info.json created")
    else:
        print(f"Error: {file_path} not found")
except Exception as e:
    print(f"Error: {str(e)}")
