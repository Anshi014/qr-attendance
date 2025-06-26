#import pandas as pd
#from datetime import datetime
#import os

#def mark_attendance(subject, name, roll, session_id):
   # try:
        # Create folder if it doesn't exist
       # os.makedirs("excelsheets", exist_ok=True)

        # Build Excel file path
        #file_path = os.path.join("excelsheets", f"{subject}.xlsx")  # ✅ correct extension

        # Load sheet or create new one
        #f os.path.exists(file_path):
         #   df = pd.read_excel(file_path)
        ##   df = pd.DataFrame(columns=["Roll No", "Name"])

        # Ensure consistent column names
        #df.columns = [col.strip().lower() for col in df.columns]
       ##name_column = "name"

        # Normalize input
        #roll = str(roll).strip()
        #name = str(name).strip()

        # Check if student already exists
        #match = df[df[roll_column].astype(str).str.strip() == roll]

        # If not, add the student row first
        #if match.empty:
         #   new_row = {roll_column: roll, name_column: name}
          #  df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        # Add today's date column if missing
        #today = datetime.now().strftime("%d-%m-%Y")
        #if today not in df.columns:
         #   df[today] = ""

        # Mark 'P'
        #df.loc[df[roll_column].astype(str).str.strip() == roll, today] = "P"

        # Save file
        #df.to_excel(file_path, index=False, engine="openpyxl")
        #print("✅ Attendance saved:")
       # print(df.tail())

        #return f"✅ Attendance marked for {name} ({roll})"

    #except Exception as e:
     #   print("❌ Error saving attendance:", e)
      #  return "⚠️ Failed to mark attendance"
