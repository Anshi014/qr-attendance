pip install pandas
import pandas as pd
import os

# ---------- SETTINGS ----------
subjects = {
    "AI": [
        {"Roll No.": "001", "Name": "Anshika Bharti"},
        {"Roll No.": "002", "Name": "Aman Sharma"},
        {"Roll No.": "003", "Name": "Riya Mehta"}
    ],
    "Python": [
        {"Roll No.": "004", "Name": "Karan Batra"},
        {"Roll No.": "005", "Name": "Pooja Soni"},
        {"Roll No.": "006", "Name": "Nikhil Thakur"}
    ]
}
folder = "excelsheets"
# -------------------------------

# Create folder if it doesn't exist
os.makedirs(folder, exist_ok=True)

# Loop through each subject and generate its Excel file
for subject, student_list in subjects.items():
    df = pd.DataFrame(student_list)
    file_path = os.path.join(folder, f"{subject}.xlsx")
    df.to_excel(file_path, index=False)
    print(f"✅ Created: {file_path}")
