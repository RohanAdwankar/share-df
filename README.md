<p align="center">
<img width="420" alt="image" class="center" src="https://github.com/user-attachments/assets/9e2b699d-9b31-4e9e-8f0b-87c1f5420920">
</p>

## share-df: Instantly Share and Modify Dataframes With a Web Interface From Anywhere


<video src="https://github.com/user-attachments/assets/fd8e9ea4-b0d5-4d61-abfc-cd584ba7af44" controls="controls" muted="muted" style="max-width:100%;"></video>

## Goal                                 [![PyPI Latest Release](https://img.shields.io/pypi/v/share-df.svg)](https://pypi.org/project/share-df/)

This package enables cross-collaboration between nontechnical and technical contributors by allowing developers to generate a URL for free with one line of code that they can then send to nontechnical contributors enabling them to modify the dataframe with a web app. Then, they can send it back to the developer, directly generating the modified dataframe, maintaining code continuity, and removing the burden of file transfer and conversion to other file formats.

## Technical Contributor Features
- ```pip install share-df``` 
- one function call to generate link to send, accessible anywhere 
- changes made by client are recieved back as a dataframe for seamless development 
  
## Nontechnical Contributor Features
- Easy Google OAuth login 
- Seamless UI to modify the dataframe 
    * Change column names
    * Drag around columns
    * Change all values
    * Rename columns
    * Add new columns and rows
- Send the results back with the click of a button

## How to Run
1. ```pip install share-df```
2. If you do not already have one, generate an auth token for free in less than a minute with [ngrok](https://dashboard.ngrok.com/)
3. Create a .env file in your directory with NGROK_AUTHTOKEN=<insert your token>
4. import and call the function on any df!

## Example Code
```
import pandas as pd
from share_df import pandaBear

df = pd.DataFrame({
    'Name': ['John', 'Alice', 'Bob', 'Carol'],
    'City': ['New York', 'London', 'Paris', 'Tokyo'],
    'Salary': [50000, 60000, 75000, 65000]
})

df = pandaBear(df)
print(df)
```

## Google Collab
- This code works by creating a localhost and then tunneling traffic to make it accesible to other people.
- Thereby, since Google Collab code runs on a VM this is a interesting challenge to handle.
- As of 0.1.7 the package offers experimental support for creating a Google generated link for DFs but this link is not shareable and the behavior is currently unstable for editing the dataframe.

## Future Functionality
- True Asynchronicity with ipyparallel
- Code Recreation (instead of overwriting the df just solve the code needed)
- First-class Google Collab support
- Multiple authentificated users
