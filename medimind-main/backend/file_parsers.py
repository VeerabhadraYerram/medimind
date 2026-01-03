"""
File parsers for different medical file formats.
Converts HL7, EHR, and other formats into readable text for LLM analysis.
"""

import re
import json
from typing import Dict, Optional
from pathlib import Path


def parse_hl7(content: str) -> str:
    """
    Parse HL7 (Health Level 7) format files.
    HL7 messages are pipe-delimited with segments like MSH, PID, OBX, etc.
    """
    lines = content.strip().split('\n')
    parsed_segments = []
    
    # HL7 Segment definitions for common fields
    segment_meaning = {
        'MSH': 'Message Header',
        'PID': 'Patient Identification',
        'PV1': 'Patient Visit',
        'OBX': 'Observation/Result',
        'ORC': 'Common Order',
        'OBR': 'Observation Request',
        'NTE': 'Notes and Comments',
        'AL1': 'Patient Allergy Information',
        'DG1': 'Diagnosis',
        'PR1': 'Procedures',
        'RXA': 'Pharmacy/Treatment Administration',
        'RXR': 'Pharmacy/Treatment Route',
        'RXO': 'Pharmacy/Treatment Order',
        'SPM': 'Specimen',
        'NK1': 'Next of Kin',
        'IN1': 'Insurance',
        'ACC': 'Accident',
        'UB1': 'UB82',
        'UB2': 'UB92 Data',
    }
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Split by pipe delimiter
        fields = line.split('|')
        if len(fields) < 2:
            continue
            
        segment_type = fields[0]
        segment_desc = segment_meaning.get(segment_type, segment_type)
        
        parsed_segments.append(f"\n[{segment_desc} ({segment_type})]")
        
        # Parse common segments with their fields
        if segment_type == 'MSH':
            if len(fields) > 9:
                parsed_segments.append(f"  Sending Application: {fields[2] if len(fields) > 2 else 'N/A'}")
                parsed_segments.append(f"  Receiving Application: {fields[4] if len(fields) > 4 else 'N/A'}")
                parsed_segments.append(f"  Message Type: {fields[8] if len(fields) > 8 else 'N/A'}")
                parsed_segments.append(f"  Message Control ID: {fields[9] if len(fields) > 9 else 'N/A'}")
                
        elif segment_type == 'PID':
            if len(fields) > 3:
                # PID.3 - Patient ID
                patient_id = fields[3] if len(fields) > 3 else ''
                # PID.5 - Patient Name
                patient_name = fields[5] if len(fields) > 5 else ''
                # PID.7 - Date of Birth
                dob = fields[7] if len(fields) > 7 else ''
                # PID.8 - Sex
                sex = fields[8] if len(fields) > 8 else ''
                # PID.11 - Patient Address
                address = fields[11] if len(fields) > 11 else ''
                
                parsed_segments.append(f"  Patient ID: {patient_id}")
                parsed_segments.append(f"  Patient Name: {patient_name}")
                parsed_segments.append(f"  Date of Birth: {dob}")
                parsed_segments.append(f"  Sex: {sex}")
                parsed_segments.append(f"  Address: {address}")
                
        elif segment_type == 'OBX':
            if len(fields) > 5:
                # OBX.3 - Observation Identifier
                obs_id = fields[3] if len(fields) > 3 else ''
                # OBX.5 - Observation Value
                obs_value = fields[5] if len(fields) > 5 else ''
                # OBX.6 - Units
                units = fields[6] if len(fields) > 6 else ''
                # OBX.8 - Abnormal Flags
                abnormal = fields[8] if len(fields) > 8 else ''
                # OBX.11 - Observation Result Status
                status = fields[11] if len(fields) > 11 else ''
                
                parsed_segments.append(f"  Observation: {obs_id}")
                parsed_segments.append(f"  Value: {obs_value} {units}")
                if abnormal:
                    parsed_segments.append(f"  Abnormal Flag: {abnormal}")
                if status:
                    parsed_segments.append(f"  Status: {status}")
                    
        elif segment_type == 'DG1':
            if len(fields) > 3:
                # DG1.3 - Diagnosis Code
                diag_code = fields[3] if len(fields) > 3 else ''
                # DG1.4 - Diagnosis Description
                diag_desc = fields[4] if len(fields) > 4 else ''
                parsed_segments.append(f"  Diagnosis Code: {diag_code}")
                parsed_segments.append(f"  Diagnosis Description: {diag_desc}")
                
        elif segment_type == 'NTE':
            if len(fields) > 3:
                # NTE.3 - Comment
                comment = fields[3] if len(fields) > 3 else ''
                parsed_segments.append(f"  Note: {comment}")
        else:
            # For other segments, show key fields
            key_fields = ' | '.join(fields[1:6])  # Show first few fields
            if key_fields.strip():
                parsed_segments.append(f"  Data: {key_fields}")
    
    return '\n'.join(parsed_segments) if parsed_segments else content


def parse_ehr_json(content: str) -> str:
    """
    Parse EHR (Electronic Health Records) in JSON format.
    Common formats: FHIR, CCDA, or custom JSON structures.
    """
    try:
        data = json.loads(content)
        return _extract_ehr_data(data)
    except json.JSONDecodeError:
        return content  # Return original if not valid JSON


def _extract_ehr_data(data: Dict, indent: int = 0) -> str:
    """Recursively extract meaningful data from EHR JSON structures."""
    lines = []
    indent_str = "  " * indent
    
    if isinstance(data, dict):
        for key, value in data.items():
            # Skip common metadata fields that aren't useful
            if key.lower() in ['id', 'meta', 'extension', 'text', 'resourceType']:
                continue
                
            if isinstance(value, (dict, list)):
                if key:
                    # Capitalize and format key names
                    formatted_key = ' '.join(word.capitalize() for word in key.replace('_', ' ').replace('-', ' ').split())
                    lines.append(f"{indent_str}{formatted_key}:")
                    lines.append(_extract_ehr_data(value, indent + 1))
            else:
                if value and str(value).strip():
                    formatted_key = ' '.join(word.capitalize() for word in key.replace('_', ' ').replace('-', ' ').split())
                    lines.append(f"{indent_str}{formatted_key}: {value}")
                    
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, (dict, list)):
                lines.append(_extract_ehr_data(item, indent))
            else:
                if item and str(item).strip():
                    lines.append(f"{indent_str}- {item}")
    else:
        if data and str(data).strip():
            lines.append(f"{indent_str}{data}")
    
    return '\n'.join(lines)


def parse_ehr_xml(content: str) -> str:
    """
    Parse EHR in XML format (CCDA, CDA, etc.).
    Extracts text content and structured data from XML.
    """
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(content)
        return _extract_xml_text(root)
    except Exception:
        # If XML parsing fails, try to extract text between tags
        text_content = re.sub(r'<[^>]+>', ' ', content)
        text_content = ' '.join(text_content.split())
        return text_content if text_content.strip() else content


def parse_pdf(content: bytes) -> str:
    """
    Parse PDF files and extract text content.
    Returns extracted text ready for LLM analysis.
    """
    try:
        from pypdf import PdfReader
        from io import BytesIO
        
        pdf_file = BytesIO(content)
        reader = PdfReader(pdf_file)
        
        text_pages = []
        for page_num, page in enumerate(reader.pages, 1):
            try:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_pages.append(f"[Page {page_num}]\n{page_text.strip()}")
            except Exception as e:
                # Skip pages that can't be extracted
                text_pages.append(f"[Page {page_num} - Could not extract text]")
                continue
        
        if text_pages:
            return "\n\n---\n\n".join(text_pages)
        else:
            return "[PDF file contains no extractable text]"
            
    except ImportError:
        return "[PDF parsing library not installed. Please install pypdf: pip install pypdf]"
    except Exception as e:
        return f"[Error parsing PDF: {str(e)}]"


def _extract_xml_text(element, indent: int = 0) -> str:
    """Extract readable text from XML elements."""
    lines = []
    indent_str = "  " * indent
    
    # Get element tag name (remove namespace)
    tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
    formatted_tag = ' '.join(word.capitalize() for word in tag.replace('_', ' ').split())
    
    # Get text content
    text = element.text.strip() if element.text and element.text.strip() else None
    
    # Get attributes
    attrs = element.attrib
    if attrs:
        attr_str = ', '.join(f"{k}={v}" for k, v in attrs.items() if v)
        if attr_str:
            lines.append(f"{indent_str}{formatted_tag} ({attr_str}):")
    elif text:
        lines.append(f"{indent_str}{formatted_tag}: {text}")
    else:
        lines.append(f"{indent_str}{formatted_tag}:")
    
    # Process children
    for child in element:
        lines.append(_extract_xml_text(child, indent + 1))
    
    # Tail text
    if element.tail and element.tail.strip():
        lines.append(f"{indent_str}{element.tail.strip()}")
    
    return '\n'.join(lines)


def detect_and_parse_file(filename: str, content: bytes) -> str:
    """
    Detect file type and parse accordingly.
    Returns parsed text content ready for LLM analysis.
    """
    # Detect file type by extension first
    ext = Path(filename).suffix.lower()
    
    # PDF files - handle as binary
    if ext == '.pdf':
        return parse_pdf(content)
    
    # Try to decode as text for other file types
    try:
        text_content = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text_content = content.decode('latin-1')
        except:
            return f"[Binary file - cannot parse: {filename}]"
    
    # HL7 files
    if ext in ['.hl7', '.hl7v2', '.hl7v3']:
        return parse_hl7(text_content)
    
    # EHR JSON files
    elif ext in ['.json', '.ehr', '.fhir']:
        # Check if it looks like JSON
        text_content_stripped = text_content.strip()
        if text_content_stripped.startswith('{') or text_content_stripped.startswith('['):
            return parse_ehr_json(text_content)
        return text_content
    
    # EHR XML files
    elif ext in ['.xml', '.ccda', '.cda']:
        return parse_ehr_xml(text_content)
    
    # Plain text files
    elif ext in ['.txt', '.text']:
        return text_content
    
    # Default: try to detect format by content
    else:
        # Check if it looks like HL7 (starts with MSH|)
        if text_content.strip().startswith('MSH|'):
            return parse_hl7(text_content)
        
        # Check if it looks like JSON
        text_content_stripped = text_content.strip()
        if text_content_stripped.startswith('{') or text_content_stripped.startswith('['):
            try:
                json.loads(text_content_stripped)
                return parse_ehr_json(text_content)
            except:
                pass
        
        # Check if it looks like XML
        if text_content_stripped.startswith('<'):
            return parse_ehr_xml(text_content)
        
        # Default: return as-is
        return text_content

