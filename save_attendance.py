import pandas as pd
from datetime import datetime
import os

def mark_attendance(subject, name, roll, session_id):
    try:
        file_path = f"excelsheets/{subject}.xlsx"

        # Load the existing Excel sheet
        if not os.path.exists(file_path):
            return f"⚠️ Subject sheet not found: {subject}.xlsx"

        df = pd.read_excel(file_path)

        # Check if roll number exists in sheet
        matching_rows = df[df["Roll No."].astype(str)== str(roll)]

        if matching_rows.empty:
            return f"❌Roll number {roll} not found in sheet"   

        # Get today's date in 'DD-MM-YYYY' format
        today = datetime.now().strftime("%d-%m-%Y")

        # Add today's date column if it doesn't exist
        if today not in df.columns:
            df[today] = ""

        # Mark 'P' for matching roll number
        df.loc[df["Roll No."].astype(str) == str(roll), today] = "P"

        # Save the updated Excel file
        df.to_excel(file_path, index=False)

        return f"✅ Attendance marked for {name} (Roll {roll}) in {subject}."

    except Exception as e:
        return f"⚠️ Error while marking attendance: {str(e)}"
