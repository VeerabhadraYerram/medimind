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
        admission_keywords = ['admission', 'admitted', 'hospitalization', 'admit']
        procedure_keywords = ['procedure', 'surgery', 'operation', 'surgical', 'performed']
        lab_keywords = ['lab', 'laboratory', 'test', 'result', 'obx', 'observation']
        visit_keywords = ['visit', 'appointment', 'encounter', 'consultation']
        
        current_date = None
        for i, line in enumerate(lines):
            # Find dates
            date_matches = re.findall(date_pattern, line, re.IGNORECASE)
            if date_matches:
                # Try to parse date
                date_str = date_matches[0][0] or date_matches[0][1]
                try:
                    # Try different date formats
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                        try:
                            current_date = datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
                            break
                        except:
                            continue
                except:
                    pass
            
            line_lower = line.lower()
            
            # Check for admissions
            if any(kw in line_lower for kw in admission_keywords):
                event_text = line.strip()
                events.append({
                    "type": "admission",
                    "date": current_date or "Not specified",
                    "description": event_text,
                    "source_file": source_file,
                    "source_text": event_text
                })
            
            # Check for procedures
            if any(kw in line_lower for kw in procedure_keywords):
                event_text = line.strip()
                events.append({
                    "type": "procedure",
                    "date": current_date or "Not specified",
                    "description": event_text,
                    "source_file": source_file,
                    "source_text": event_text
                })
            
            # Check for lab tests
            if any(kw in line_lower for kw in lab_keywords) and ('result' in line_lower or 'value' in line_lower):
                event_text = line.strip()
                events.append({
                    "type": "lab",
                    "date": current_date or "Not specified",
                    "description": event_text,
                    "source_file": source_file,
                    "source_text": event_text
                })
            
            # Check for visits
            if any(kw in line_lower for kw in visit_keywords):
                event_text = line.strip()
                events.append({
                    "type": "visit",
                    "date": current_date or "Not specified",
                    "description": event_text,
                    "source_file": source_file,
                    "source_text": event_text
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
        
        # Also look for structured lab data in parsed content
        lines = content.split('\n')
        for line in lines:
            line_lower = line.lower()
            if any(kw in line_lower for kw in ['observation', 'test', 'lab result', 'value:']):
                # Try to extract lab name and value
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        test_name = parts[0].strip()
                        value_part = parts[1].strip()
                        
                        # Extract numeric value
                        value_match = re.search(r'(\d+\.?\d*)', value_part)
                        value = value_match.group(1) if value_match else value_part
                        
                        # Check for abnormal indicators
                        abnormal = any(x in value_part.upper() for x in ['HIGH', 'LOW', 'ABNORMAL', 'CRITICAL'])
                        
                        labs.append({
                            "test_name": test_name,
                            "value": value,
                            "units": "",
                            "reference_range": "Not specified",
                            "is_abnormal": abnormal,
                            "source_file": source_file,
                            "source_text": line
                        })
        
        return labs
    
    def _extract_medications(self, content: str, source_file: str) -> List[Dict]:
        """Extract medications with start/end dates if mentioned."""
        medications = []
        
        # Look for RXA segments in HL7 (Pharmacy/Treatment Administration)
        rxa_pattern = r'RXA\|.*?\|.*?\|.*?\|(.*?)\|'
        rxa_matches = re.findall(rxa_pattern, content)
        
        # Also look for medication keywords
        med_keywords = ['medication', 'medication:', 'drug', 'prescription', 'rx', 'rxo', 'rxa']
        
        lines = content.split('\n')
        current_date = None
        
        for line in lines:
            line_lower = line.lower()
            
            # Look for dates
            date_pattern = r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})'
            date_match = re.search(date_pattern, line)
            if date_match:
                try:
                    current_date = datetime.strptime(date_match.group(1), '%Y-%m-%d').strftime('%Y-%m-%d')
                except:
                    pass
            
            # Check for medication mentions
            if any(kw in line_lower for kw in med_keywords):
                # Extract medication name
                med_name = ""
                if ':' in line:
                    parts = line.split(':', 1)
                    med_name = parts[1].strip() if len(parts) > 1 else line.strip()
                else:
                    med_name = line.strip()
                
                # Look for start/end dates in nearby lines
                start_date = current_date or "Not specified"
                end_date = "Not specified"
                
                medications.append({
                    "name": med_name,
                    "start_date": start_date,
                    "end_date": end_date,
                    "source_file": source_file,
                    "source_text": line
                })
        
        return medications
    
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


