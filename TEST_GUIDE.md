# Testing Guide for QR Attendance System

## Setup

Install pytest if not already installed:
```bash
pip install pytest pytest-flask
```

## Running Tests

### Run all tests:
```bash
pytest test_app.py -v
```

### Run specific test class:
```bash
pytest test_app.py::TestLogin -v
```

### Run specific test:
```bash
pytest test_app.py::TestLogin::test_valid_login -v
```

## Test Coverage

### 1. **Login Tests** (`TestLogin`)
- ✅ Login page loads correctly
- ✅ Valid login with correct credentials
- ✅ Invalid login with wrong credentials

### 2. **Dashboard Tests** (`TestDashboard`)
- ✅ Dashboard requires authentication
- ✅ Dashboard loads after valid login

### 3. **QR Generation Tests** (`TestQRGeneration`)
- ✅ QR generation requires login
- ✅ QR files are created successfully

### 4. **Attendance Tests** (`TestAttendance`)
- ✅ Retrieve student name by roll number
- ✅ Handle invalid roll numbers

### 5. **Database Tests** (`TestDatabase`)
- ✅ Database initialization
- ✅ Mark attendance records
- ✅ Duplicate device detection
- ✅ Duplicate IP detection

### 6. **Export Tests** (`TestExport`)
- ✅ Export requires authentication

### 7. **Route Tests** (`TestRoutes`)
- ✅ Test server is running
- ✅ Logout functionality

## Manual Testing Checklist

### User Authentication
- [ ] Login with valid credentials (teacher1/pass123)
- [ ] Verify invalid credentials are rejected
- [ ] Verify session is created after login
- [ ] Logout clears the session

### QR Generation & Scanning
- [ ] Navigate to dashboard
- [ ] Click "Generate QR" for a subject
- [ ] QR code displays correctly
- [ ] Scan QR with mobile device
- [ ] Roll number input works

### Attendance Marking
- [ ] Submit attendance with valid roll
- [ ] Verify "Attendance marked" message
- [ ] Try duplicate device - should be rejected
- [ ] Try duplicate IP - should be rejected
- [ ] Invalid roll shows error

### Reports
- [ ] CR/Incharge can view full reports
- [ ] Reports generate Excel files
- [ ] Attendance status shows P (Present) and A (Absent)
- [ ] Percentage attendance calculates correctly

### Database
- [ ] Check `/debug_attendance` to see all records
- [ ] Verify student list loads correctly
- [ ] Check attendance table has proper records

## Test Output Example

```
test_app.py::TestLogin::test_login_page_loads PASSED
test_app.py::TestLogin::test_valid_login PASSED
test_app.py::TestDashboard::test_dashboard_requires_login PASSED
...
======================== X passed in Y.YYs ========================
```

## Troubleshooting

**Database issues:**
- Delete `attendance.db` before running fresh tests
- Ensure database is not locked

**Import errors:**
- Install all dependencies: `pip install flask pandas openpyxl qrcode pillow`

**Session issues:**
- Make sure Flask secret key is set correctly
- Clear session between tests
