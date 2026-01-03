# Enhanced Multi-File Analysis Version

This enhanced version supports **multiple file uploads** and **cross-file analysis** with trend detection.

## Features

✅ **Multiple File Upload**: Upload multiple `.txt` files at once  
✅ **Cross-File Analysis**: Ask questions that analyze trends across all files  
✅ **File Management**: View and delete uploaded files  
✅ **Source Citation**: Answers include which files were analyzed  
✅ **Trend Detection**: Automatically identifies patterns and relationships between documents  

## How to Use

### 1. Start the Enhanced Backend

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run the enhanced backend
uvicorn backend.api_enhanced:app --reload --host 0.0.0.0 --port 8000
```

### 2. Update Frontend to Use Enhanced Version

**Option A: Replace the main App.jsx** (recommended for permanent use)
```powershell
# Backup original
Copy-Item frontend\src\App.jsx frontend\src\App.original.jsx

# Use enhanced version
Copy-Item frontend\src\AppEnhanced.jsx frontend\src\App.jsx
```

**Option B: Create a separate entry point** (to keep both versions)

Edit `frontend/src/main.jsx` to import `AppEnhanced` instead of `App`:
```javascript
import AppEnhanced from './AppEnhanced.jsx'
// ... rest of the file
```

### 3. Start Frontend

```powershell
cd frontend
npm run dev
```

## API Endpoints

The enhanced backend includes these additional endpoints:

- `GET /files` - List all uploaded files
- `POST /upload` - Upload multiple files (accepts `files` array)
- `DELETE /files/{filename}` - Delete a specific file
- `POST /ask` - Enhanced query with cross-file analysis

## Example Questions

Once you've uploaded multiple files, try asking:

- "What are the common trends across all documents?"
- "Compare the information in file1.txt and file2.txt"
- "What patterns do you see between all the files?"
- "Are there any contradictions between the documents?"
- "Summarize the key points from all files"

## Differences from Original

| Feature | Original | Enhanced |
|---------|----------|----------|
| File Upload | Single file | Multiple files |
| File List | Not shown | Displayed with delete option |
| Cross-File Analysis | Basic | Advanced with trend detection |
| Source Citation | Limited | Shows which files were analyzed |
| File Management | None | View and delete files |

## Switching Back to Original

If you want to use the original version:

```powershell
# Restore original App.jsx
Copy-Item frontend\src\App.original.jsx frontend\src\App.jsx

# Use original backend
uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
```

