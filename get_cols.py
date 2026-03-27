import pandas as pd
import sys

try:
    df1 = pd.read_excel('HEADCOUNT 2026.xlsx', header=0)
    print("=== HEADER=0 ===")
    for i, col in enumerate(df1.columns):
        print(f"[{i}] {col}")
    print("Row 0:", list(df1.iloc[0].values)[:15])
    print("Row 1:", list(df1.iloc[1].values)[:15])
    
    df2 = pd.read_excel('HEADCOUNT 2026.xlsx', header=1)
    print("\n=== HEADER=1 ===")
    for i, col in enumerate(df2.columns):
        print(f"[{i}] {col}")
except Exception as e:
    print("Erro:", str(e))
