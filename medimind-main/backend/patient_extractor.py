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
        
        # Extract Age - More comprehensive patterns with better validation
        # Use word boundaries to avoid matching "Page" as "age"
        age_patterns = [
            r'\bage[:\s]+(\d+)',  # Word boundary before "age"
            r'(\d+)\s*years?\s*old',
            r'\bage[:\s]+(\d+)\s*years?',
            r'\bage[:\s]*(\d+)\s*[yY]',
            r'\bage\/sex[:\s]+(\d+)\s*\/\s*\w+',  # Age/Sex format
        ]
        for pattern in age_patterns:
            matches = re.finditer(pattern, content_lower)
            for match in matches:
                try:
                    age = int(match.group(1))
                    # Exclude very small numbers (likely not ages) and ensure reasonable range
                    # Also check context - age should not be part of a date or other number
                    context_before = content_lower[max(0, match.start()-10):match.start()]
                    context_after = content_lower[match.end():min(len(content_lower), match.end()+10)]
                    
                    # Skip if it looks like part of a date, ID, lab value, or other number sequence
                    context_combined = context_before + context_after
                    skip_indicators = ['/', '-', ':', 'id', 'no.', 'number', 'g/dl', 'mg/dl', 'ng/ml', 
                                      'pg/ml', 'u/l', 'fl', '%', '10^', 'range', 'normal', 'reference']
                    if any(x in context_combined for x in skip_indicators):
                        continue
                    
                    # Check if it's clearly an age mention (has "years", "yrs", "old" nearby or in same line)
                    line_with_match = content_lower[max(0, content_lower.rfind('\n', 0, match.start())):match.end()+50]
                    is_clear_age = any(term in line_with_match for term in ['years', 'yrs', 'year old', 'age', 'aged'])
                    
                    # Only accept ages between 2 and 120 (exclude 0, 1 as likely errors)
                    # If it's not a clear age mention, require it to be in a reasonable context
                    if 2 <= age <= 120:
                        if is_clear_age or ('patient' in context_before.lower() or 'demographic' in context_before.lower()):
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
        
        # Extract Vital Signs - with better context validation
        vital_patterns = {
            "blood_pressure": r'(?:blood pressure|bp)[:\s]+(\d+)\s*/\s*(\d+)',
            "heart_rate": r'(?:heart rate|hr|pulse)[:\s]+(\d+)',
            "temperature": r'(?:temperature|temp)[:\s]+(\d+\.?\d*)',
            "respiratory_rate": r'(?:respiratory rate|rr)[:\s]+(\d+)',
            "oxygen_saturation": r'(?:oxygen|spo2|o2 sat)[:\s]+(\d+\.?\d*)',
        }
        
        for vital_name, pattern in vital_patterns.items():
            matches = list(re.finditer(pattern, content_lower))
            for match in matches:
                # Check context to avoid false positives from lab values
                context_before = content_lower[max(0, match.start()-20):match.start()]
                context_after = content_lower[match.end():min(len(content_lower), match.end()+20)]
                
                # Skip if it looks like a lab value (has units like g/dL, mg/dL, etc. nearby)
                if any(unit in context_after for unit in ['g/dl', 'mg/dl', 'ng/ml', 'pg/ml', 'u/l', 'fl', '%', '10^']):
                    continue
                
                # Skip if it's part of a reference range
                if '-' in context_after[:10] or 'range' in context_before.lower():
                    continue
                
                if vital_name == "blood_pressure":
                    data["vital_signs"][vital_name] = f"{match.group(1)}/{match.group(2)}"
                    break
                else:
                    value = float(match.group(1)) if '.' in match.group(1) else int(match.group(1))
                    # Validate reasonable ranges
                    if vital_name == "heart_rate" and (value < 30 or value > 200):
                        continue
                    elif vital_name == "temperature" and (value < 90 or value > 110):
                        continue
                    elif vital_name == "respiratory_rate" and (value < 8 or value > 40):
                        continue
                    elif vital_name == "oxygen_saturation" and (value < 70 or value > 100):
                        continue
                    data["vital_signs"][vital_name] = value
                    break
        
        # If key patient data is missing, use LLM to extract from document
        # This is especially useful for PDFs where data might be in headers/footers or unstructured
        # Only use LLM if we truly don't have the data (not false positives)
        has_real_data = (
            (data["name"] and len(data["name"]) > 2) or
            (data["age"] and 2 <= data["age"] <= 120) or
            data["gender"]
        )
        if not has_real_data:
            try:
                llm_data = self._extract_with_llm(content, source_file)
                # Merge LLM results (only if regex didn't find it)
                for key in ["name", "age", "date_of_birth", "gender", "patient_id", "address", "phone", "email"]:
                    if not data.get(key) and llm_data.get(key):
                        data[key] = llm_data[key]
                # Merge vital signs
                if llm_data.get("vital_signs"):
                    data["vital_signs"].update(llm_data["vital_signs"])
            except Exception as e:
                print(f"LLM extraction failed: {e}")
        
        return data
    
    def _extract_with_llm(self, content: str, source_file: str) -> Dict[str, Any]:
        """Use LLM to extract patient data when regex patterns fail."""
        # Get first 3000 characters and last 1000 characters (headers/footers often there)
        content_sample = content[:3000] + "\n\n...\n\n" + content[-1000:] if len(content) > 4000 else content
        
        prompt = f"""Extract patient demographic information from this medical document. 
Return ONLY the information explicitly stated in the document. If information is not found, return null for that field.

Document content (sample):
{content_sample}

Extract the following information in JSON format:
{{
    "name": "patient name if found, else null",
    "age": "age in years as integer if found, else null",
    "date_of_birth": "date of birth in YYYY-MM-DD format if found, else null",
    "gender": "Male or Female if found, else null",
    "patient_id": "patient ID if found, else null",
    "address": "address if found, else null",
    "phone": "phone number if found, else null",
    "email": "email if found, else null",
    "vital_signs": {{
        "blood_pressure": "systolic/diastolic if found, else null",
        "heart_rate": "heart rate as integer if found, else null",
        "temperature": "temperature as float if found, else null",
        "respiratory_rate": "respiratory rate as integer if found, else null",
        "oxygen_saturation": "oxygen saturation as float if found, else null"
    }}
}}

IMPORTANT:
- Only extract information that is EXPLICITLY stated in the document
- Do NOT infer or guess any information
- Return null for fields that are not found
- For age, return only the number (integer), not text like "years old"
- For dates, use YYYY-MM-DD format
- Return valid JSON only, no additional text

JSON:"""

        try:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                return {}
            
            llm = ChatGroq(
                model="llama-3.1-8b-instant",
                api_key=api_key,
                temperature=0
            )
            
            response = llm.invoke([HumanMessage(content=prompt)]).content.strip()
            
            # Extract JSON from response (might have markdown code blocks)
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            llm_data = json.loads(response)
            
            # Validate and clean data
            result = {
                "name": None,
                "age": None,
                "date_of_birth": None,
                "gender": None,
                "patient_id": None,
                "address": None,
                "phone": None,
                "email": None,
                "vital_signs": {}
            }
            
            # Validate name (letters and spaces only)
            if llm_data.get("name") and isinstance(llm_data["name"], str):
                name = llm_data["name"].strip()
                if re.match(r'^[A-Za-z\s\.]+$', name) and len(name) > 2:
                    result["name"] = name
            
            # Validate age (integer between 0-150)
            if llm_data.get("age"):
                try:
                    age = int(llm_data["age"]) if isinstance(llm_data["age"], (int, str)) else None
                    if age and 0 < age <= 150:
                        result["age"] = age
                except:
                    pass
            
            # Validate date of birth
            if llm_data.get("date_of_birth") and isinstance(llm_data["date_of_birth"], str):
                dob = llm_data["date_of_birth"].strip()
                if re.match(r'^\d{4}-\d{2}-\d{2}$', dob):
                    result["date_of_birth"] = dob
            
            # Validate gender
            if llm_data.get("gender") and isinstance(llm_data["gender"], str):
                gender = llm_data["gender"].strip().title()
                if gender in ["Male", "Female"]:
                    result["gender"] = gender
            
            # Other fields
            for field in ["patient_id", "address", "phone", "email"]:
                if llm_data.get(field) and isinstance(llm_data[field], str) and llm_data[field].strip().lower() not in ["null", "none", "not found"]:
                    result[field] = llm_data[field].strip()
            
            # Vital signs
            if llm_data.get("vital_signs") and isinstance(llm_data["vital_signs"], dict):
                for vital, value in llm_data["vital_signs"].items():
                    if value and str(value).lower() not in ["null", "none", "not found"]:
                        result["vital_signs"][vital] = value
            
            return result
            
        except Exception as e:
            print(f"Error in LLM extraction: {e}")
            return {}

