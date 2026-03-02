# Duplicate Data Checker Tool

A Python-based client-server tool for detecting and managing duplicate data. The server provides a REST API for uploading data and checking duplicates, while the client provides an easy interface to interact with the server.

## Features

- **REST API Server** with Flask
- **Duplicate Detection** using MD5 hashing
- **File Upload Support** for text files
- **Statistics Tracking** of processed data
- **Interactive Client** with command-line interface
- **Data Persistence** in text format

## Files

- `serve.py` - Flask server that handles duplicate checking
- `client.py` - Client application to interact with the server
- `data.txt` - Storage file for non-duplicate data (created automatically)
- `requirements.txt` - Python dependencies
- `sample_data.txt` - Sample test data with duplicates

## Installation

1. Install required packages:
```cmd
pip install -r requirements.txt
```

## Usage

### 1. Start the Server

```cmd
python serve.py
```

The server will start on `http://localhost:5000` with the following endpoints:

- `GET /health` - Health check
- `POST /upload` - Upload JSON data
- `POST /upload-file` - Upload text file
- `GET /statistics` - Get current statistics
- `POST /clear` - Clear all data

### 2. Use the Client

#### Interactive Mode
```cmd
python client.py
```

#### Command Line Mode
```cmd
# Upload a file
python client.py upload-file sample_data.txt

# Get statistics
python client.py stats
```

### 3. API Usage Examples

#### Upload Data via JSON API
```bash
curl -X POST http://localhost:5000/upload \
  -H "Content-Type: application/json" \
  -d '{"data": ["apple", "banana", "apple", "cherry"]}'
```

#### Upload File via API
```bash
curl -X POST http://localhost:5000/upload-file \
  -F "file=@sample_data.txt"
```

#### Get Statistics
```bash
curl http://localhost:5000/statistics
```

## How It Works

1. **Server**: 
   - Receives data via REST API
   - Uses MD5 hashing to detect duplicates
   - Stores only non-duplicate data in `data.txt`
   - Returns statistics (success count, duplicate count)

2. **Client**:
   - Provides interactive interface
   - Supports uploading individual items or files
   - Shows formatted results and statistics

3. **Duplicate Detection**:
   - Each data item is hashed using MD5
   - Hashes are compared against existing data
   - Only new (non-duplicate) items are saved

## Example Output

```
DUPLICATE CHECK RESULTS
==================================================
Total processed: 15
New items saved: 10
Duplicates found: 5
Success rate: 66.7%
Message: Processed 15 items from file: 10 new, 5 duplicates
==================================================
```

## Testing

Use the provided `sample_data.txt` file to test the duplicate detection:

```cmd
# Start server
python serve.py

# In another terminal, upload sample data
python client.py upload-file sample_data.txt
```

The sample file contains fruits with duplicates (apple, banana appear multiple times).

## API Response Format

### Upload Response
```json
{
  "status": "success",
  "statistics": {
    "success": 10,
    "duplicates": 5,
    "total_processed": 15
  },
  "message": "Processed 15 items: 10 new, 5 duplicates"
}
```

### Statistics Response
```json
{
  "total_unique_items": 50,
  "data_file": "data.txt",
  "file_exists": true
}
```

## Error Handling

- Server validates input data format
- Client checks server connectivity
- Graceful error messages for common issues
- Automatic file creation for data storage

## Customization

- Change server port in `serve.py` (default: 5000)
- Modify data file name in `DATA_FILE` constant
- Adjust hash algorithm if needed (currently MD5)
- Add authentication if required
