import pandas as pd
import re

# ---- Set these values as required ----
csv_path = r"C:\Users\rahul\Downloads\FinalPF_with_Reverse (8).csv"  # Replace with your actual file name
output_path = r"R:\PYTHON\PF_MAKER\PF_GEN_18092025\OUTPUT_FOLDER\filtered_output.csv"
# ------------------------------------

def extract_strikes(desc):
    """
    Extract ATMCE and NONATMCE as integers from Description like:
    'NIFTY 04/11/2025 25200 CE|NIFTY 04/11/2025 24900 CE'
    Returns (ATM_CE, NONATM_CE), else (None, None)
    """
    try:
        parts = desc.strip().split('|')
        if len(parts) != 2: return (None, None)
        atm = int(re.findall(r'(\d+)\s+CE', parts[0])[0])
        non_atm = int(re.findall(r'(\d+)\s+CE', parts[1])[0])
        return atm, non_atm
    except Exception:
        return (None, None)

df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)

df_clean = df[df['Description'].str.strip() != ""]

def filter_row(row):
    atm, non_atm = extract_strikes(row['Description'])
    if atm is None or non_atm is None:
        return False
    return abs(atm - non_atm) > 99

filtered = df_clean[df_clean.apply(filter_row, axis=1)]

filtered.to_csv(output_path, index=False)
print(f"Filtered rows written to {output_path}")
