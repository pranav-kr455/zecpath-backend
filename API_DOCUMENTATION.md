# ZecPath ATS Backend - Core API Usage Guide

This document outlines the production-ready REST API endpoints for the ZecPath Applicant Tracking System (ATS) Core Infrastructure module. All responses adhere to a standardized corporate JSON layout.

---

## 🔐 1. Identity & Access Module

### 📝 Public User Registration
Registers new profiles into the platform database matrix. Enforces secure password hashing.
* *URL Routing:* POST /api/auth/register/
* *Access Control:* Public (AllowAny)
* *Headers:* Content-Type: application/json
* *Payload Request Body:*
```json
{
    "email": "candidate@zecpath.com",
    "password": "SecurePassword123",
    "role": "CANDIDATE",
    "phone": "9876543210"
}



<!-- Day 52: CI/CD Deployment Pipeline Verified -->