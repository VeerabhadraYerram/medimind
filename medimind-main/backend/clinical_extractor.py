"""
Clinical data extractor that extracts structured information from medical files.
Only extracts explicitly documented information - no inferences.
"""

import re
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from backend.file_parsers import detect_and_parse_file


class ClinicalDataExtractor:
    """Extracts structured clinical data from parsed medical documents."""
    
    def __init__(self):
        self.events = []
        self.labs = []
        self.medications = []
        self.red_flags = []
        self.sections = {}
        
    def extract_from_files(self, files_data: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract clinical data from multiple files.
        files_data: {filename: parsed_content}
        """
        all_events = []
        all_labs = []
        all_medications = []
        all_red_flags = []
        all_sections = {}
        
        for filename, content in files_data.items():
            # Extract data from each file
            file_events = self._extract_events(content, filename)
            file_labs = self._extract_labs(content, filename)
            file_medications = self._extract_medications(content, filename)
            file_red_flags = self._extract_red_flags(content, filename)
            file_sections = self._extract_sections(content, filename)
            
            all_events.extend(file_events)
            all_labs.extend(file_labs)
            all_medications.extend(file_medications)
            all_red_flags.extend(file_red_flags)
            all_sections[filename] = file_sections
        
        return {
            "events": sorted(all_events, key=lambda x: x.get('date', '')),
            "labs": all_labs,
            "medications": sorted(all_medications, key=lambda x: x.get('start_date', '')),
            "red_flags": all_red_flags,
            "sections": all_sections,
            "summary": {
                "total_events": len(all_events),
                "total_labs": len(all_labs),
                "abnormal_labs": len([l for l in all_labs if l.get('is_abnormal', False)]),
                "total_medications": len(all_medications),
                "total_red_flags": len(all_red_flags),
            }
        }
    
    def _extract_events(self, content: str, source_file: str) -> List[Dict]:
        """Extract admissions, procedures, labs, visits with dates."""
        events = []
        lines = content.split('\n')
        
        # Look for date patterns (YYYY-MM-DD, MM/DD/YYYY, etc.)
        date_pattern = r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})|(\d{1,2}[-/]\d{1,2}[-/]\d{4})'
        
        # Keywords for different event types
        admission_keywords = ['admission', 'admitted', 'hospitalization', 'admit', 'discharge']
        procedure_keywords = ['procedure', 'surgery', 'operation', 'surgical', 'performed', 'biopsy', 'endoscopy']
        lab_keywords = ['lab', 'laboratory', 'test', 'result', 'obx', 'observation', 'blood test', 'cbc', 'complete blood count']
        visit_keywords = ['visit', 'appointment', 'encounter', 'consultation', 'examination', 'exam']
        
        current_date = None
        for i, line in enumerate(lines):
            # Find dates
            date_matches = re.findall(date_pattern, line, re.IGNORECASE)
            if date_matches:
                # Try to parse date
                date_str = date_matches[0][0] or date_matches[0][1]
                try:
                    # Try different date formats
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y', '%Y.%m.%d']:
                        try:
                            current_date = datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
                            break
                        except:
                            continue
                except:
                    pass
            
            line_lower = line.lower()
            line_stripped = line.strip()
            
            # Skip empty lines and very short lines
            if not line_stripped or len(line_stripped) < 3:
                continue
            
            # Check for admissions
            if any(kw in line_lower for kw in admission_keywords):
                event_text = line_stripped
                events.append({
                    "type": "admission",
                    "date": current_date or "Not specified",
                    "description": event_text,
                    "source_file": source_file,
                    "source_text": event_text
                })
            
            # Check for procedures
            if any(kw in line_lower for kw in procedure_keywords):
                event_text = line_stripped
                events.append({
                    "type": "procedure",
                    "date": current_date or "Not specified",
                    "description": event_text,
                    "source_file": source_file,
                    "source_text": event_text
                })
            
            # Check for lab tests - more flexible matching
            if any(kw in line_lower for kw in lab_keywords):
                # Check if it's actually a lab result line (has numbers/values)
                has_value = bool(re.search(r'\d+\.?\d*', line))
                if has_value or 'result' in line_lower or 'test' in line_lower:
                    event_text = line_stripped
                    events.append({
                        "type": "lab",
                        "date": current_date or "Not specified",
                        "description": event_text,
                        "source_file": source_file,
                        "source_text": event_text
                    })
            
            # Check for visits
            if any(kw in line_lower for kw in visit_keywords):
                event_text = line_stripped
                events.append({
                    "type": "visit",
                    "date": current_date or "Not specified",
                    "description": event_text,
                    "source_file": source_file,
                    "source_text": event_text
                })
        
        # Also create a lab event if we find lab results (even if no explicit "lab" keyword)
        if 'page' in content.lower() and any(kw in content.lower() for kw in ['cbc', 'complete blood', 'haemoglobin', 'glucose', 'creatinine']):
            # Extract report date if available
            report_date = current_date or "Not specified"
            events.append({
                "type": "lab",
                "date": report_date,
                "description": "Laboratory test results",
                "source_file": source_file,
                "source_text": "Laboratory report"
            })
        
        return events
    
    def _extract_labs(self, content: str, source_file: str) -> List[Dict]:
        """Extract lab results with values and reference ranges."""
        labs = []
        
        # Look for OBX segments in HL7 format
        obx_pattern = r'OBX\|.*?\|.*?\|(.*?)\|(.*?)\|(.*?)\|'
        obx_matches = re.findall(obx_pattern, content)
        
        for match in obx_matches:
            if len(match) >= 3:
                test_name = match[0].strip() if match[0] else "Unknown"
                value = match[1].strip() if match[1] else ""
                units = match[2].strip() if match[2] else ""
                
                # Try to extract reference range and abnormal flags
                abnormal = False
                ref_range = ""
                
                # Look for abnormal flags
                if 'H' in content or 'HIGH' in content.upper() or 'L' in content or 'LOW' in content.upper():
                    abnormal = True
                
                # Look for reference range patterns
                ref_pattern = r'(\d+\.?\d*)\s*-\s*(\d+\.?\d*)'
                ref_match = re.search(ref_pattern, content)
                if ref_match:
                    ref_range = f"{ref_match.group(1)}-{ref_match.group(2)} {units}"
                
                labs.append({
                    "test_name": test_name,
                    "value": value,
                    "units": units,
                    "reference_range": ref_range or "Not specified",
                    "is_abnormal": abnormal,
                    "source_file": source_file,
                    "source_text": f"OBX|{match[0]}|{match[1]}|{match[2]}"
                })
        
        # Enhanced pattern matching for natural language lab reports (PDFs, text files)
        # Pattern 1: Test name, value with units, reference range on same line
        # Example: "Haemoglobin (Hb) 16.0 g/dL 13-17" or "Glucose Fasting 77 mg/dL 70-100"
        # Skip lines that start with "(Method:" as those are not test names
        lab_pattern1 = r'([A-Za-z][A-Za-z\s\(\)\-/]+?)\s+(\d+\.?\d*)\s+([a-zA-Z/%\^]+/?[a-zA-Z0-9]*)\s+(\d+\.?\d*\s*[-–]\s*\d+\.?\d*)'
        matches1 = re.finditer(lab_pattern1, content, re.MULTILINE)
        for match in matches1:
            test_name = match.group(1).strip()
            value = match.group(2).strip()
            units = match.group(3).strip()
            ref_range = match.group(4).strip()
            
            # Skip if test name looks like a method line
            if test_name.lower().startswith('(method:') or 'method:' in test_name.lower():
                continue
            
            # Clean test name - remove trailing method references
            test_name = re.sub(r'\s*\(Method:.*?\)\s*$', '', test_name, flags=re.IGNORECASE)
            test_name = ' '.join(test_name.split())  # Normalize whitespace
            
            # Check if value is outside reference range
            ref_parts = re.findall(r'(\d+\.?\d*)', ref_range)
            if len(ref_parts) >= 2:
                try:
                    val_float = float(value)
                    ref_min = float(ref_parts[0])
                    ref_max = float(ref_parts[1])
                    abnormal = val_float < ref_min or val_float > ref_max
                except:
                    abnormal = False
            else:
                abnormal = False
            
            labs.append({
                "test_name": test_name,
                "value": value,
                "units": units,
                "reference_range": ref_range,
                "is_abnormal": abnormal,
                "source_file": source_file,
                "source_text": match.group(0)
            })
        
        # Pattern 2: Test name on one line, method line (skip), value and range on next line
        # Example: "Haemoglobin (Hb)\n(Method: Cynmeth Method)\n16.0 g/dL 13-17"
        lines = content.split('\n')
        for i in range(len(lines) - 2):
            line = lines[i].strip()
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            line_after_next = lines[i + 2].strip() if i + 2 < len(lines) else ""
            
            # Skip method lines
            if line.lower().startswith('(method:') or 'method:' in line.lower():
                continue
            
            # Check if current line looks like a test name (contains common lab terms)
            test_keywords = ['haemoglobin', 'hemoglobin', 'hb', 'wbc', 'rbc', 'platelet', 'glucose', 
                          'creatinine', 'cholesterol', 'triglyceride', 'bilirubin', 'alt', 'ast', 
                          'alkaline', 'phosphatase', 'sodium', 'potassium', 'calcium', 'magnesium',
                          'neutrophil', 'lymphocyte', 'monocyte', 'eosinophil', 'basophil', 'mcv', 
                          'mch', 'mchc', 'rdw', 'hct', 'hematocrit', 'esr', 'sedimentation', 'mpv',
                          'pct', 'p-lcr', 'pdw', 'absolute', 'count', 'differential', 'morphology']
            
            line_lower = line.lower()
            # Check if line looks like a test name (not too long, not a method line, has keywords or starts with capital)
            is_test_name = (
                (any(kw in line_lower for kw in test_keywords) or (line and line[0].isupper())) and 
                len(line) < 100 and 
                not line.lower().startswith('(method:') and
                not line.lower().startswith('page') and
                not line.lower().startswith('***') and
                line and line.strip()
            )
            
            if is_test_name:
                # Determine which line has the value/range
                # If next line is a method line, check line after next
                # Otherwise check next line
                if next_line.lower().startswith('(method:') or 'method:' in next_line.lower():
                    check_line = line_after_next
                else:
                    check_line = next_line
                
                # Pattern: value units range (e.g., "16.0 g/dL 13-17" or "50 % 40-70")
                value_range_pattern = r'(\d+\.?\d*)\s+([a-zA-Z/%\^]+/?[a-zA-Z0-9]*)\s+(\d+\.?\d*\s*[-–]\s*\d+\.?\d*)'
                match = re.search(value_range_pattern, check_line)
                if match:
                    value = match.group(1)
                    units = match.group(2)
                    ref_range = match.group(3)
                    
                    # Check if abnormal
                    ref_parts = re.findall(r'(\d+\.?\d*)', ref_range)
                    if len(ref_parts) >= 2:
                        try:
                            val_float = float(value)
                            ref_min = float(ref_parts[0])
                            ref_max = float(ref_parts[1])
                            abnormal = val_float < ref_min or val_float > ref_max
                        except:
                            abnormal = False
                    else:
                        abnormal = False
                    
                    # Clean test name - remove extra whitespace, keep it concise
                    test_name = ' '.join(line.split())
                    # Remove leading/trailing spaces and normalize
                    test_name = test_name.strip()
                    
                    labs.append({
                        "test_name": test_name,
                        "value": value,
                        "units": units,
                        "reference_range": ref_range,
                        "is_abnormal": abnormal,
                        "source_file": source_file,
                        "source_text": f"{line}\n{check_line}"
                    })
        
        # Pattern 3: Colon-separated format "Test Name: value units (range)"
        colon_pattern = r'([A-Za-z][A-Za-z\s\(\)\-]+?):\s*(\d+\.?\d*)\s*([a-zA-Z/%\^]+/?[a-zA-Z0-9]*)?\s*(?:\(([^)]+)\)|(\d+\.?\d*\s*-\s*\d+\.?\d*))'
        matches3 = re.finditer(colon_pattern, content)
        for match in matches3:
            test_name = match.group(1).strip()
            value = match.group(2).strip()
            units = match.group(3).strip() if match.group(3) else ""
            ref_range = (match.group(4) or match.group(5) or "").strip()
            
            if ref_range:
                ref_parts = re.findall(r'(\d+\.?\d*)', ref_range)
                if len(ref_parts) >= 2:
                    try:
                        val_float = float(value)
                        ref_min = float(ref_parts[0])
                        ref_max = float(ref_parts[1])
                        abnormal = val_float < ref_min or val_float > ref_max
                    except:
                        abnormal = False
                else:
                    abnormal = False
            else:
                abnormal = False
            
            labs.append({
                "test_name": test_name,
                "value": value,
                "units": units,
                "reference_range": ref_range or "Not specified",
                "is_abnormal": abnormal,
                "source_file": source_file,
                "source_text": match.group(0)
            })
        
        # Clean and deduplicate labs
        seen = set()
        unique_labs = []
        invalid_patterns = [
            r'^\(?method:',
            r'method\)$',
            r'calculated\)$',
            r'impedence\)$',
            r'microscopy\)$',
            r'^page\s+\d+',
            r'^\*\*\*',
            r'^itdose',
        ]
        
        # Method names that should be removed from test names
        method_names = ['hexokinase', 'uricase', 'clia', 'direct', 'diazo', 'ifcc', 'kinetic', 
                       'pnpp-amp', 'bromocresol', 'bcg', 'cynmeth', 'calculated', 'impedence',
                       'microscopy', 'sarcosine', 'oxidase']
        
        for lab in labs:
            test_name = lab["test_name"].strip()
            
            # Remove trailing method references in parentheses
            test_name = re.sub(r'\s*\([^)]*(?:method|assay|technique)[^)]*\)\s*$', '', test_name, flags=re.IGNORECASE)
            # Remove trailing single method words in parentheses
            test_name = re.sub(r'\s*\(([^)]+)\)\s*$', lambda m: '' if any(mn in m.group(1).lower() for mn in method_names) else m.group(0), test_name, flags=re.IGNORECASE)
            # Remove trailing closing parentheses with method names
            test_name = re.sub(r'\s*([A-Za-z]+)\)\s*$', lambda m: '' if any(mn in m.group(1).lower() for mn in method_names) else test_name, test_name, flags=re.IGNORECASE)
            
            test_name = test_name.strip()
            
            # Skip if test name matches invalid patterns
            is_invalid = any(re.search(pattern, test_name, re.IGNORECASE) for pattern in invalid_patterns)
            if is_invalid or len(test_name) < 2:
                continue
            
            # Update test name in lab dict
            lab["test_name"] = test_name
            
            # Deduplicate (same test name and value)
            key = (test_name.lower(), lab["value"], lab["source_file"])
            if key not in seen:
                seen.add(key)
                unique_labs.append(lab)
        
        return unique_labs
    
    def _extract_medications(self, content: str, source_file: str) -> List[Dict]:
        """Extract medications with start/end dates if mentioned."""
        medications = []
        
        # Look for RXA segments in HL7 (Pharmacy/Treatment Administration)
        rxa_pattern = r'RXA\|.*?\|.*?\|.*?\|(.*?)\|'
        rxa_matches = re.findall(rxa_pattern, content)
        
        for match in rxa_matches:
            if match and match.strip():
                medications.append({
                    "name": match.strip(),
                    "start_date": "Not specified",
                    "end_date": "Not specified",
                    "source_file": source_file,
                    "source_text": f"RXA|{match}"
                })
        
        # Enhanced medication extraction for natural language
        med_keywords = ['medication', 'medications', 'medication:', 'drug', 'drugs', 'prescription', 
                       'prescribed', 'rx', 'rxo', 'rxa', 'taking', 'currently on', 'on medication',
                       'tablet', 'capsule', 'injection', 'dose', 'mg', 'ml']
        
        lines = content.split('\n')
        current_date = None
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            line_stripped = line.strip()
            
            # Look for dates
            date_pattern = r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})|(\d{1,2}[-/]\d{1,2}[-/]\d{4})'
            date_match = re.search(date_pattern, line)
            if date_match:
                date_str = date_match.group(1) or date_match.group(2)
                try:
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                        try:
                            current_date = datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
                            break
                        except:
                            continue
                except:
                    pass
            
            # Check for medication mentions
            if any(kw in line_lower for kw in med_keywords):
                # Extract medication name - look for common medication patterns
                med_name = ""
                
                # Pattern 1: "Medication: Name" or "Drug: Name"
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        med_name = parts[1].strip()
                    else:
                        med_name = line_stripped
                # Pattern 2: Line contains medication keywords and drug name
                elif any(char.isupper() for char in line) and len(line_stripped) < 200:
                    # Extract potential medication name (usually capitalized words)
                    words = line_stripped.split()
                    # Look for capitalized words that might be medication names
                    med_words = [w for w in words if w and (w[0].isupper() or w.isdigit())]
                    if med_words:
                        med_name = ' '.join(med_words[:5])  # Take first few words
                    else:
                        med_name = line_stripped
                else:
                    med_name = line_stripped
                
                # Clean up medication name
                if med_name:
                    # Remove common prefixes
                    med_name = re.sub(r'^(medication|drug|prescription|rx)[:\s]*', '', med_name, flags=re.IGNORECASE)
                    med_name = med_name.strip()
                    
                    if med_name and len(med_name) > 2:  # Valid medication name
                        # Look for start/end dates in nearby lines
                        start_date = current_date or "Not specified"
                        end_date = "Not specified"
                        
                        # Check next few lines for dates
                        for j in range(i + 1, min(i + 5, len(lines))):
                            next_line = lines[j]
                            date_match = re.search(date_pattern, next_line)
                            if date_match and start_date == "Not specified":
                                date_str = date_match.group(1) or date_match.group(2)
                                try:
                                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                                        try:
                                            start_date = datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
                                            break
                                        except:
                                            continue
                                except:
                                    pass
                        
                        medications.append({
                            "name": med_name,
                            "start_date": start_date,
                            "end_date": end_date,
                            "source_file": source_file,
                            "source_text": line_stripped
                        })
        
        # Remove duplicates
        seen = set()
        unique_meds = []
        for med in medications:
            key = (med["name"].lower(), med["source_file"])
            if key not in seen:
                seen.add(key)
                unique_meds.append(med)
        
        return unique_meds
    
    def _extract_red_flags(self, content: str, source_file: str) -> List[Dict]:
        """Extract red flags only if explicitly documented."""
        red_flags = []
        
        # Red flag keywords that must be explicitly mentioned
        red_flag_keywords = [
            'critical', 'critical:', 'urgent', 'urgent:',
            'alert', 'alert:', 'warning', 'warning:',
            'adverse', 'adverse event', 'adverse reaction',
            'allergy', 'allergy:', 'allergic reaction',
            'contraindication', 'contraindicated'
        ]
        
        lines = content.split('\n')
        for line in lines:
            line_lower = line.lower()
            
            # Only flag if explicitly mentioned
            for keyword in red_flag_keywords:
                if keyword in line_lower:
                    # Extract the flag text
                    flag_text = line.strip()
                    red_flags.append({
                        "type": keyword.split(':')[0].strip().title(),
                        "description": flag_text,
                        "severity": "high" if any(x in line_lower for x in ['critical', 'urgent']) else "medium",
                        "source_file": source_file,
                        "source_text": flag_text
                    })
                    break
        
        return red_flags
    
    def _extract_sections(self, content: str, source_file: str) -> Dict[str, str]:
        """Determine section completeness based on what's mentioned."""
        sections = {
            "demographics": "not_mentioned",
            "chief_complaint": "not_mentioned",
            "history_of_present_illness": "not_mentioned",
            "past_medical_history": "not_mentioned",
            "medications": "not_mentioned",
            "allergies": "not_mentioned",
            "vital_signs": "not_mentioned",
            "physical_examination": "not_mentioned",
            "laboratory_results": "not_mentioned",
            "assessment": "not_mentioned",
            "plan": "not_mentioned"
        }
        
        content_lower = content.lower()
        
        # Check for each section
        section_keywords = {
            "demographics": ["patient id", "patient name", "date of birth", "age", "sex", "gender", "pid"],
            "chief_complaint": ["chief complaint", "cc", "presenting complaint"],
            "history_of_present_illness": ["history of present illness", "hpi", "present illness"],
            "past_medical_history": ["past medical history", "pmh", "medical history", "past history"],
            "medications": ["medication", "medications", "drug", "rx", "prescription"],
            "allergies": ["allergy", "allergies", "allergic", "adverse reaction"],
            "vital_signs": ["vital", "vitals", "blood pressure", "bp", "temperature", "temp", "heart rate", "hr"],
            "physical_examination": ["physical exam", "physical examination", "pe", "examination"],
            "laboratory_results": ["lab", "laboratory", "test results", "obx", "laboratory results"],
            "assessment": ["assessment", "diagnosis", "diagnoses", "impression"],
            "plan": ["plan", "treatment plan", "management", "recommendations"]
        }
        
        for section, keywords in section_keywords.items():
            found_count = sum(1 for kw in keywords if kw in content_lower)
            if found_count >= 2:
                sections[section] = "present"
            elif found_count == 1:
                sections[section] = "partial"
        
        return sections


def extract_clinical_data(files_data: Dict[str, str]) -> Dict[str, Any]:
    """Main function to extract clinical data from files."""
    extractor = ClinicalDataExtractor()
    return extractor.extract_from_files(files_data)


