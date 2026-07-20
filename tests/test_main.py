"""
Tests for main application
"""
import pytest
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


def test_root():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["version"] == "1.0.0"


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_analyze_resume():
    """Test resume analysis endpoint"""
    request_data = {
        "resume_text": "Software Engineer with 5 years experience in Python and JavaScript"
    }
    response = client.post("/analyze-resume", json=request_data)
    assert response.status_code == 200
    assert "profile" in response.json()


def test_find_jobs():
    """Test job finding endpoint"""
    candidate_profile = {
        "skills": ["Python", "JavaScript", "AWS"],
        "years_experience": 5
    }
    request_data = {
        "candidate_profile": candidate_profile,
        "keywords": ["Python Developer", "Backend Engineer"],
        "top_n": 5
    }
    response = client.post("/find-jobs", json=request_data)
    assert response.status_code == 200
    assert "matches" in response.json()
