import pandas as pd
from datetime import datetime
import os

subject = "Python"
name = "Pooja Soni"
roll = "5"
session_id = "test123"

# Ensure folder exists
os.makedirs("excelsheets", exist_ok=True)

file_path = os.path.join("excelsheets", "Python.xlsx")

# Load or create DataFrame
if os.path.exists(file_path):
    df = pd.read_excel(file_path)
else:
    df = pd.DataFrame(columns=["Roll No", "Name"])

# Normalize columns
df.columns = [col.strip().lower() for col in df.columns]
roll_column = "roll no"
name_column = "name"

# Check if roll exists
roll = str(roll).strip()
name = str(name).strip()
match = df[df[roll_column].astype(str).str.strip() == roll]

if match.empty:
    print("🆕 Adding new student")
    new_row = {roll_column: roll, name_column: name}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

# Add today's column
today = datetime.now().strftime("%d-%m-%Y")
if today not in df.columns:
    df[today] = ""

# Mark 'P'
df.loc[df[roll_column].astype(str).str.strip() == roll, today] = "P"

# Save
df.to_excel(file_path, index=False, engine="openpyxl")
print("✅ Excel updated successfully")
