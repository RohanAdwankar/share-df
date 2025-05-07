<p align="center">
<img width="420" alt="image" class="center" src="https://github.com/user-attachments/assets/9e2b699d-9b31-4e9e-8f0b-87c1f5420920">
</p>

# share-df

Share and Edit Pandas/Polars Dataframes with a Link!

## Features

- ✅ Convert any DataFrame into a collaborative, Google Sheets-like experience
- ✅ Easy to use: just one function call
- ✅ Authentication via Google login
- ✅ Works with both pandas and polars DataFrames
- ✅ Interactive editing, sorting, filtering
- ✅ Collaborative editing with multiple users
- ✅ Realtime data updates
- ✅ End-to-end encryption for cloud sharing
- ✅ Versioning support for cloud-hosted dataframes

## Installation

```bash
pip install share-df
```

## Quick Start

### Basic Usage

```python
import pandas as pd
from share_df import pandaBear

df = pd.read_csv('your_data.csv')
df = pandaBear(df)  # Opens interactive editor and returns edited DataFrame
```

### Polars Support

```python
import polars as pl
from share_df import pandaBear

df = pl.read_csv('your_data.csv')
df = pandaBear(df)  # Works with Polars too!
```

### DataFrame Accessor Method

```python
import pandas as pd

df = pd.read_csv('your_data.csv')
df.pandaBear()  # Updates the DataFrame in-place
```

## Advanced Usage

### Collaboration Mode

Share your DataFrame with others in real-time:

```python
df = pandaBear(df, collaborative=True, share_with="your.friend@gmail.com")
```

Multiple recipients:

```python
df = pandaBear(df, collaborative=True, share_with=["friend1@gmail.com", "friend2@gmail.com"])
```

### Cloud Hosting

Share your DataFrame through secure cloud hosting with end-to-end encryption:

```python
df = pandaBear(df, use_cloud=True, share_with=["friend@gmail.com"])
```

This will:
- Upload your DataFrame to AWS S3 with encryption
- Generate a secure access URL to share
- Track versions as changes are made
- Control access with AWS Cognito authentication
- Provide cost metering and usage stats

#### Cloud Hosting Requirements

To use cloud hosting, you need AWS credentials:

1. Create a `.env` file in your project directory with:
   ```
   AWS_ACCESS_KEY_ID=your_access_key_here
   AWS_SECRET_ACCESS_KEY=your_secret_key_here
   AWS_REGION=us-east-1  # Optional, defaults to us-east-1
   AWS_S3_BUCKET=your-bucket-name  # Optional, defaults to sharedf-data
   ```

2. Or set these as environment variables in your shell

#### Retrieving Cloud Dataframes

To retrieve a specific version of a cloud-hosted DataFrame:

```python
from share_df import retrieve_cloud_dataframe, list_cloud_versions

# List all versions of a dataframe
versions = list_cloud_versions(session_id="session-id-from-url", df_id="df-id-from-url")
print(versions)

# Get the latest version
df = retrieve_cloud_dataframe(
    session_id="session-id-from-url", 
    df_id="df-id-from-url", 
    encryption_key="encryption-key-from-url"
)

# Get a specific version
df = retrieve_cloud_dataframe(
    session_id="session-id-from-url", 
    df_id="df-id-from-url", 
    encryption_key="encryption-key-from-url",
    version="1.2"  # Specific version to retrieve
)
```

## Options Reference

The `pandaBear` function accepts these parameters:

```python
def pandaBear(df, 
             use_iframe=False, 
             collaborative=True, 
             share_with=None, 
             log_level="CRITICAL", 
             local=False, 
             strict_dtype=True,
             use_cloud=False,
             df_name=None,
             df_description="")
```

- `df`: The pandas or polars DataFrame to edit
- `use_iframe`: Display in an iframe (Google Colab only)
- `collaborative`: Enable real-time collaboration features
- `share_with`: Email(s) to share the editor with
- `log_level`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `local`: Run in local mode without ngrok
- `strict_dtype`: Enforce strict data type checking
- `use_cloud`: Use cloud-based hosting with end-to-end encryption
- `df_name`: Name for the dataframe (cloud mode only)
- `df_description`: Description for the dataframe (cloud mode only)

## Authentication

For non-cloud mode:
- Uses ngrok with Google OAuth authentication
- Requires an ngrok account (free tier works for basic usage)
- Set `NGROK_AUTHTOKEN` in your `.env` file

For cloud mode:
- Uses AWS Cognito for authentication
- Uses end-to-end encryption for data security
- Credentials are passed securely in the URL