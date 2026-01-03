"""
Real-world medical standards and reference ranges for clinical data.
Used to enhance dashboard visualizations with standard medical norms.
"""

# Common Lab Reference Ranges (standard values)
LAB_REFERENCE_RANGES = {
    "hemoglobin": {"normal": "12.0-17.5", "units": "g/dL", "male": "13.5-17.5", "female": "12.0-15.5"},
    "hematocrit": {"normal": "36-52", "units": "%", "male": "40-52", "female": "36-48"},
    "rbc": {"normal": "4.5-6.0", "units": "million/µL", "male": "4.5-6.0", "female": "4.0-5.5"},
    "wbc": {"normal": "4,000-11,000", "units": "cells/µL"},
    "platelets": {"normal": "150,000-450,000", "units": "platelets/µL"},
    "glucose": {"normal": "70-100", "units": "mg/dL", "fasting": "70-100", "random": "<140"},
    "creatinine": {"normal": "0.6-1.2", "units": "mg/dL", "male": "0.7-1.3", "female": "0.6-1.1"},
    "bun": {"normal": "7-20", "units": "mg/dL"},
    "sodium": {"normal": "136-145", "units": "mEq/L"},
    "potassium": {"normal": "3.5-5.0", "units": "mEq/L"},
    "chloride": {"normal": "98-107", "units": "mEq/L"},
    "co2": {"normal": "22-28", "units": "mEq/L"},
    "calcium": {"normal": "8.5-10.5", "units": "mg/dL"},
    "total_protein": {"normal": "6.0-8.3", "units": "g/dL"},
    "albumin": {"normal": "3.5-5.0", "units": "g/dL"},
    "ast": {"normal": "10-40", "units": "U/L", "alt_name": "SGOT"},
    "alt": {"normal": "10-40", "units": "U/L", "alt_name": "SGPT"},
    "alkaline_phosphatase": {"normal": "44-147", "units": "U/L"},
    "total_bilirubin": {"normal": "0.3-1.2", "units": "mg/dL"},
    "direct_bilirubin": {"normal": "0.0-0.3", "units": "mg/dL"},
    "ldh": {"normal": "140-280", "units": "U/L"},
    "troponin": {"normal": "<0.04", "units": "ng/mL"},
    "ck_mb": {"normal": "<5", "units": "ng/mL"},
    "pt": {"normal": "11-13", "units": "seconds"},
    "inr": {"normal": "0.9-1.1", "units": ""},
    "aptt": {"normal": "25-35", "units": "seconds"},
    "tsh": {"normal": "0.4-4.0", "units": "mIU/L"},
    "t4": {"normal": "5.0-12.0", "units": "µg/dL"},
    "t3": {"normal": "100-200", "units": "ng/dL"},
    "cholesterol": {"normal": "<200", "units": "mg/dL"},
    "ldl": {"normal": "<100", "units": "mg/dL", "optimal": "<100"},
    "hdl": {"normal": ">40", "units": "mg/dL", "male": ">40", "female": ">50"},
    "triglycerides": {"normal": "<150", "units": "mg/dL"},
    "hba1c": {"normal": "<5.7", "units": "%", "prediabetes": "5.7-6.4", "diabetes": "≥6.5"},
    "psa": {"normal": "<4.0", "units": "ng/mL"},
}

# Vital Signs Normal Ranges
VITAL_SIGNS_NORMAL = {
    "blood_pressure_systolic": {"normal": "90-120", "units": "mmHg", "elevated": "120-129", "high_stage1": "130-139", "high_stage2": "≥140"},
    "blood_pressure_diastolic": {"normal": "60-80", "units": "mmHg", "elevated": "80-89", "high_stage1": "80-89", "high_stage2": "≥90"},
    "heart_rate": {"normal": "60-100", "units": "bpm", "adult_resting": "60-100"},
    "respiratory_rate": {"normal": "12-20", "units": "breaths/min"},
    "temperature": {"normal": "97.8-99.1", "units": "°F", "celsius": "36.5-37.3", "units_c": "°C"},
    "oxygen_saturation": {"normal": "95-100", "units": "%"},
    "bmi": {"normal": "18.5-24.9", "units": "kg/m²", "underweight": "<18.5", "overweight": "25-29.9", "obese": "≥30"},
}

# Common Lab Test Name Variations (for matching)
LAB_NAME_VARIATIONS = {
    "rbc": ["rbc", "red blood cell", "red blood cell count", "erythrocyte count"],
    "wbc": ["wbc", "white blood cell", "white blood cell count", "leukocyte count"],
    "hemoglobin": ["hemoglobin", "hgb", "hb"],
    "hematocrit": ["hematocrit", "hct"],
    "glucose": ["glucose", "blood glucose", "blood sugar", "glu"],
    "creatinine": ["creatinine", "creat", "scr"],
    "bun": ["bun", "blood urea nitrogen", "urea nitrogen"],
    "sodium": ["sodium", "na"],
    "potassium": ["potassium", "k"],
    "chloride": ["chloride", "cl"],
    "co2": ["co2", "carbon dioxide", "bicarbonate", "hco3"],
    "calcium": ["calcium", "ca"],
    "ast": ["ast", "sgot", "aspartate aminotransferase"],
    "alt": ["alt", "sgpt", "alanine aminotransferase"],
    "troponin": ["troponin", "troponin i", "troponin t"],
    "tsh": ["tsh", "thyroid stimulating hormone"],
    "hba1c": ["hba1c", "hemoglobin a1c", "glycated hemoglobin"],
}

def get_lab_reference_range(lab_name: str, gender: str = None) -> dict:
    """Get reference range for a lab test by name."""
    lab_lower = lab_name.lower().strip()
    
    # Try direct match first
    if lab_lower in LAB_REFERENCE_RANGES:
        ref = LAB_REFERENCE_RANGES[lab_lower].copy()
        if gender and gender.lower() in ["male", "m"] and "male" in ref:
            ref["normal"] = ref["male"]
        elif gender and gender.lower() in ["female", "f"] and "female" in ref:
            ref["normal"] = ref["female"]
        return ref
    
    # Try variations
    for key, variations in LAB_NAME_VARIATIONS.items():
        if any(var in lab_lower for var in variations):
            ref = LAB_REFERENCE_RANGES.get(key, {})
            if ref:
                ref = ref.copy()
                if gender and gender.lower() in ["male", "m"] and "male" in ref:
                    ref["normal"] = ref["male"]
                elif gender and gender.lower() in ["female", "f"] and "female" in ref:
                    ref["normal"] = ref["female"]
                return ref
    
    return {"normal": "Reference range not available", "units": ""}

def get_vital_reference_range(vital_name: str) -> dict:
    """Get reference range for a vital sign."""
    vital_lower = vital_name.lower().strip()
    
    # Map common names
    vital_map = {
        "bp": "blood_pressure_systolic",
        "blood pressure": "blood_pressure_systolic",
        "systolic": "blood_pressure_systolic",
        "diastolic": "blood_pressure_diastolic",
        "hr": "heart_rate",
        "heart rate": "heart_rate",
        "pulse": "heart_rate",
        "rr": "respiratory_rate",
        "respiratory rate": "respiratory_rate",
        "temp": "temperature",
        "temperature": "temperature",
        "spo2": "oxygen_saturation",
        "oxygen": "oxygen_saturation",
        "o2 sat": "oxygen_saturation",
    }
    
    key = vital_map.get(vital_lower, vital_lower.replace(" ", "_"))
    return VITAL_SIGNS_NORMAL.get(key, {"normal": "Reference range not available", "units": ""})


