"""
Enhanced patient data extractor - extracts ALL patient demographics and details
from uploaded files without hallucinations.
"""

import re
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import os
from dotenv import load_dotenv
from pathlib import Path

# Load API key for LLM-assisted extraction
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class PatientDataExtractor:
    """Extracts comprehensive patient information from medical documents."""
    
    def extract_patient_data(self, files_data: Dict[str, str]) -> Dict[str, Any]:
        """Extract all patient data from files."""
        patient_data = {
            "name": None,
            "age": None,
            "date_of_birth": None,
            "gender": None,
            "patient_id": None,
            "address": None,
            "phone": None,
            "email": None,
            "vital_signs": {},
            "all_found_data": []
        }
        
        for filename, content in files_data.items():
            file_data = self._extract_from_content(content, filename)
            if file_data:
                patient_data["all_found_data"].append(file_data)
            
            # Merge data (keep first non-null value)
            for key in ["name", "age", "date_of_birth", "gender", "patient_id", "address", "phone", "email"]:
                if file_data.get(key) and not patient_data.get(key):
                    patient_data[key] = file_data[key]
            
            # Merge vital signs
            if file_data.get("vital_signs"):
                patient_data["vital_signs"].update(file_data["vital_signs"])
        
        return patient_data
    
    def _extract_from_content(self, content: str, source_file: str) -> Dict[str, Any]:
        """Extract patient data from a single file's content."""
        data = {
            "name": None,
            "age": None,
            "date_of_birth": None,
            "gender": None,
            "patient_id": None,
            "address": None,
            "phone": None,
            "email": None,
            "vital_signs": {},
            "source_file": source_file
        }
        
        content_lower = content.lower()
        lines = content.split('\n')
        
        # Extract Patient Name - Improved patterns
        name_patterns = [
            r'patient name[:\s]+([A-Za-z\s,\.\^]+)',  # Handles HL7 format with ^
            r'patient name[:\s]+([A-Za-z]+[\s\^]+[A-Za-z]+)',  # First Last format
            r'name[:\s]+([A-Za-z]+[\s\^\.]+[A-Za-z]+)',  # Generic name pattern
            r'pid.*?patient name[:\s]+([A-Za-z\s\^]+)',  # HL7 parsed format
            r'\[Patient Identification.*?Patient Name: ([A-Za-z\s\^]+)',  # HL7 parsed bracket format
        ]
        
        # Search line by line for better matching - check more lines for PDFs
        search_lines = min(200, len(lines))  # Check up to 200 lines
        for i, line in enumerate(lines[:search_lines]):
            line_lower = line.lower()
            line_clean = line.strip()
            
            # Look for patient name patterns
            if 'patient name' in line_lower or ('name:' in line_lower and ('patient' in content_lower[:1000] or i < 20)):
                # Extract name after colon or on same/next line
                if ':' in line:
                    name_part = line.split(':', 1)[1].strip()
                    # Also check next line if current line is short
                    if len(name_part) < 5 and i + 1 < len(lines):
                        name_part += ' ' + lines[i + 1].strip()
                    
                    # Clean up format
                    name = re.sub(r'[\|\^\n\r]+', ' ', name_part).strip()
                    # Extract name parts
                    name_match = re.search(r'([A-Za-z]+(?:\s+[A-Za-z]+)+)', name)
                    if name_match:
                        name = name_match.group(1).strip()
                        if len(name) > 2 and re.search(r'[A-Za-z]', name):
                            data["name"] = name
                            break
            
            # Also try to find names at the start of documents (common in PDFs)
            if i < 30 and not data["name"]:
                # Look for lines that look like names (2-4 capitalized words)
                if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$', line_clean):
                    # Check if it's not a header or other text
                    if not any(word in line_lower for word in ['report', 'laboratory', 'hospital', 'clinic', 'page', 'date', 'time']):
                        if len(line_clean.split()) >= 2 and len(line_clean.split()) <= 4:
                            data["name"] = line_clean
                            break
        
        # If still not found, try regex patterns
        if not data["name"]:
            for pattern in name_patterns:
                match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                if match:
                    name = match.group(1).strip()
                    # Clean up: replace ^ with space, remove | and other separators
                    name = re.sub(r'[\|\^]+', ' ', name).strip()
                    # Extract only valid name parts
                    name_match = re.search(r'([A-Za-z]+(?:\s+[A-Za-z]+)+)', name)
                    if name_match:
                        name = name_match.group(1).strip()
                        if len(name) > 2 and re.search(r'[A-Za-z]', name):
                            data["name"] = name
                            break
        
        # Extract Age - More comprehensive patterns
        age_patterns = [
            r'age[:\s]+(\d+)',
            r'(\d+)\s*years?\s*old',
            r'age[:\s]+(\d+)\s*years?',
            r'age[:\s]*(\d+)\s*[yY]',
            r'age\/sex[:\s]+\d+\s*\/\s*\w+\s*,\s*(\d+)',  # Age/Sex format
        ]
        for pattern in age_patterns:
            matches = re.finditer(pattern, content_lower)
            for match in matches:
                try:
                    age = int(match.group(1))
                    if 0 < age <= 150:  # Reasonable age range (exclude 0 and 1 as likely errors)
                        data["age"] = age
                        break
                except:
                    continue
            if data["age"]:
                break
        
        # Extract Date of Birth
        dob_patterns = [
            r'date of birth[:\s]+(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'dob[:\s]+(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'birth date[:\s]+(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'pid\|.*?\|.*?\|.*?\|.*?\|.*?\|(\d{8})',  # HL7 format YYYYMMDD
        ]
        for pattern in dob_patterns:
            match = re.search(pattern, content_lower)
            if match:
                dob_str = match.group(1)
                try:
                    # Try different formats
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y%m%d']:
                        try:
                            dob = datetime.strptime(dob_str, fmt)
                            data["date_of_birth"] = dob.strftime('%Y-%m-%d')
                            break
                        except:
                            continue
                    if data["date_of_birth"]:
                        break
                except:
                    pass
        
        # Extract Gender - Improved patterns
        gender_patterns = [
            r'gender[:\s]+([MFmf]ale|M|F)',
            r'sex[:\s]+([MFmf]ale|M|F)',
            r'\[Patient Identification.*?Sex: ([MFmf]ale|M|F)',
            r'pid.*?sex[:\s]+([MFmf]ale|M|F)',
        ]
        for pattern in gender_patterns:
            match = re.search(pattern, content_lower)
            if match:
                gender = match.group(1).upper()
                if gender in ['M', 'F', 'MALE', 'FEMALE']:
                    data["gender"] = 'Male' if gender in ['M', 'MALE'] else 'Female'
                    break
        
        # Also search line by line
        if not data["gender"]:
            for line in lines[:50]:
                line_lower = line.lower()
                if ('gender' in line_lower or 'sex' in line_lower) and ':' in line:
                    gender_part = line.split(':', 1)[1].strip().upper()
                    if gender_part in ['M', 'F', 'MALE', 'FEMALE', 'MALE', 'FEMALE']:
                        data["gender"] = 'Male' if gender_part in ['M', 'MALE'] else 'Female'
                        break
        
        # Extract Patient ID - Improved patterns
        id_patterns = [
            r'patient id[:\s]+([A-Za-z0-9\-]+)',
            r'patient id[:\s]+([A-Za-z0-9\-]+)',
            r'\[Patient Identification.*?Patient ID: ([A-Za-z0-9\-]+)',  # HL7 parsed format
            r'pid.*?patient id[:\s]+([A-Za-z0-9\-]+)',
        ]
        for pattern in id_patterns:
            match = re.search(pattern, content_lower)
            if match:
                data["patient_id"] = match.group(1).strip()
                break
        
        # Also search line by line
        if not data["patient_id"]:
            for line in lines[:50]:
                line_lower = line.lower()
                if 'patient id' in line_lower and ':' in line:
                    id_part = line.split(':', 1)[1].strip()
                    id_match = re.search(r'([A-Za-z0-9\-]+)', id_part)
                    if id_match:
                        data["patient_id"] = id_match.group(1).strip()
                        break
        
        # Extract Address
        address_patterns = [
            r'address[:\s]+([A-Za-z0-9\s,\.\-]+)',
            r'pid\|.*?\|.*?\|.*?\|.*?\|.*?\|.*?\|.*?\|.*?\|.*?\|.*?\|.*?\|([A-Za-z0-9\s,\.\-]+)',
        ]
        for pattern in address_patterns:
            match = re.search(pattern, content_lower)
            if match:
                addr = match.group(1).strip()[:200]  # Limit length
                if len(addr) > 5:
                    data["address"] = addr
                    break
        
        # Extract Phone
        phone_pattern = r'phone[:\s]+([\d\s\-\(\)]+)'
        match = re.search(phone_pattern, content_lower)
        if match:
            data["phone"] = match.group(1).strip()
        
        # Extract Email
        email_pattern = r'email[:\s]+([A-Za-z0-9@\.\-]+)'
        match = re.search(email_pattern, content_lower)
        if match:
            data["email"] = match.group(1).strip()
        
        # Extract Vital Signs
        vital_patterns = {
            "blood_pressure": r'(?:blood pressure|bp)[:\s]+(\d+)\s*/\s*(\d+)',
            "heart_rate": r'(?:heart rate|hr|pulse)[:\s]+(\d+)',
            "temperature": r'(?:temperature|temp)[:\s]+(\d+\.?\d*)',
            "respiratory_rate": r'(?:respiratory rate|rr)[:\s]+(\d+)',
            "oxygen_saturation": r'(?:oxygen|spo2|o2 sat)[:\s]+(\d+\.?\d*)',
        }
        
        for vital_name, pattern in vital_patterns.items():
            match = re.search(pattern, content_lower)
            if match:
                if vital_name == "blood_pressure":
                    data["vital_signs"][vital_name] = f"{match.group(1)}/{match.group(2)}"
                else:
                    value = float(match.group(1)) if '.' in match.group(1) else int(match.group(1))
                    data["vital_signs"][vital_name] = value
        
        return data

