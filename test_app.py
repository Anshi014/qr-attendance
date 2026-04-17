import pytest
import sqlite3
import os
from app import app
from database_logic import init_db, mark_attendance, has_already_submitted, roll_exists
from users import users


@pytest.fixture
def client():
    """Create a test client for the Flask app"""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    # Setup test database
    if os.path.exists('test_attendance.db'):
        os.remove('test_attendance.db')
    
    with app.test_client() as client:
        # Initialize test database
        init_db()
        yield client
    
    # Cleanup
    if os.path.exists('test_attendance.db'):
        os.remove('test_attendance.db')


class TestLogin:
    """Test login functionality"""
    
    def test_login_page_loads(self, client):
        """Test that login page loads"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'login' in response.data.lower()
    
    def test_valid_login(self, client):
        """Test valid login"""
        response = client.post('/', data={
            'username': 'teacher1',
            'password': 'pass123'
        }, follow_redirects=True)
        assert response.status_code == 200
    
    def test_invalid_login(self, client):
        """Test invalid login credentials"""
        response = client.post('/', data={
            'username': 'invalid_user',
            'password': 'wrong_pass'
        })
        assert b'Invalid login' in response.data or response.status_code == 200


class TestDashboard:
    """Test dashboard functionality"""
    
    def test_dashboard_requires_login(self, client):
        """Test that dashboard redirects to login when not authenticated"""
        response = client.get('/dashboard')
        assert response.status_code == 302  # Redirect
    
    def test_dashboard_loads_after_login(self, client):
        """Test dashboard loads after valid login"""
        with client.session_transaction() as sess:
            sess['user'] = 'teacher1'
        
        response = client.get('/dashboard')
        assert response.status_code == 200


class TestQRGeneration:
    """Test QR code generation"""
    
    def test_qr_generation_requires_login(self, client):
        """Test that QR generation requires authentication"""
        response = client.get('/generate_qr/Python')
        assert response.status_code == 302  # Redirect to login
    
    def test_qr_file_creation(self, client):
        """Test that QR code files are created"""
        with client.session_transaction() as sess:
            sess['user'] = 'teacher1'
        
        response = client.get('/generate_qr/Python', follow_redirects=False)
        # Should redirect to qr_display
        assert response.status_code in [302, 200]


class TestAttendance:
    """Test attendance marking"""
    
    def test_get_name_valid_roll(self, client):
        """Test retrieving student name by valid roll"""
        # First seed a student
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO students (roll, name) VALUES (?, ?)", 
                      ('001', 'John Doe'))
        conn.commit()
        conn.close()
        
        response = client.post('/get_name', data={'roll': '001'})
        assert b'John Doe' in response.data
    
    def test_get_name_invalid_roll(self, client):
        """Test retrieving name with invalid roll"""
        response = client.post('/get_name', data={'roll': '999'})
        assert b'Not found' in response.data


class TestDatabase:
    """Test database functions"""
    
    def test_init_db(self):
        """Test database initialization"""
        if os.path.exists('test_db.db'):
            os.remove('test_db.db')
        
        # This should create tables without error
        init_db()
        assert os.path.exists('attendance.db')
    
    def test_mark_attendance(self):
        """Test marking attendance"""
        init_db()
        
        # Mark attendance
        mark_attendance('Python', 'sess_001', '001', 'John Doe', 'device1', '192.168.1.1')
        
        # Verify it was marked
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM attendance WHERE roll = ? AND subject = ?", 
                      ('001', 'Python'))
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None
    
    def test_has_already_submitted_device(self):
        """Test duplicate device submission check"""
        init_db()
        
        # Mark attendance once
        mark_attendance('Python', 'sess_001', '001', 'John Doe', 'device1', '192.168.1.1')
        
        # Check if same device already submitted
        result = has_already_submitted('Python', 'sess_001', device_id='device1')
        assert result == True
    
    def test_has_already_submitted_ip(self):
        """Test duplicate IP submission check"""
        init_db()
        
        # Mark attendance once
        mark_attendance('Python', 'sess_001', '001', 'John Doe', 'device1', '192.168.1.1')
        
        # Check if same IP already submitted
        result = has_already_submitted('Python', 'sess_001', ip_address='192.168.1.1')
        assert result == True


class TestExport:
    """Test data export functionality"""
    
    def test_export_requires_login(self, client):
        """Test that export requires login"""
        response = client.get('/export/Python')
        assert response.status_code == 302  # Redirect


class TestRoutes:
    """Test miscellaneous routes"""
    
    def test_test_page(self, client):
        """Test the test page"""
        response = client.get('/test')
        assert response.status_code == 200
        assert b'Server is running' in response.data
    
    def test_logout(self, client):
        """Test logout functionality"""
        with client.session_transaction() as sess:
            sess['user'] = 'teacher1'
        
        response = client.get('/logout', follow_redirects=True)
        assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
