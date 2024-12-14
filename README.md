<p align="center">
<img width="420" alt="image" class="center" src="https://github.com/user-attachments/assets/9e2b699d-9b31-4e9e-8f0b-87c1f5420920">
</p>

## share-df: Instantly Share and Modify Dataframes With a Web Interface From Anywhere
<p align="center">
<a href="https://pepy.tech/project/share-df"><img src="https://static.pepy.tech/badge/share-df" alt="PyPI Downloads"></a>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://pypi.org/project/share-df/"><img src="https://img.shields.io/pypi/v/share-df.svg" alt="PyPI Latest Release"></a>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
<a href="https://github.com/RohanAdwankar/share-df">Demos and Source Code</a>
</p>
<video src="https://github.com/user-attachments/assets/fd8e9ea4-b0d5-4d61-abfc-cd584ba7af44" controls="controls" muted="muted" style="max-width:100%;"></video>

## Goal      

This package enables cross-collaboration between nontechnical and technical contributors by allowing developers to generate a URL for free with one line of code that they can then send to nontechnical contributors enabling them to modify the dataframe with a web app. Then, they can send it back to the developer, directly generating the modified dataframe, maintaining code continuity, and removing the burden of file transfer and conversion to other file formats.

## Technical Contributor Features
- ```pip install share-df``` 
- one function call to generate a link to send, accessible anywhere 
- changes made by the client are received back as a dataframe for seamless development 
  
## Nontechnical Contributor Features
- Easy Google OAuth login 
- Seamless UI to modify the dataframe 
    * Change column names
    * Drag around columns
    * Change all values
    * Rename columns
    * Add new columns and rows
- Send the results back with the click of a button
- Work with large amounts of data quickly

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

## Handling Big Data

<video src="https://github.com/user-attachments/assets/7fdaac68-b77d-49b3-89ff-17af028ff5bf" controls="controls" muted="muted" style="max-width:100%;"></video>

- As per the demo, currently, the site takes 6 seconds to load a million rows.
- After loading, it can handle cell changes, row additions, column sorting, new columns, fast scrolling, and sending the data back frictionlessly.
- That being said given interest I can improve this experience.

## Google Colab
- This code works by creating a localhost and then tunneling traffic to make it accessible to other people.
- Thereby, since Google Colab code runs on a VM this is an interesting challenge to handle.
- As of 0.1.7 the package offers support for creating a Google-generated link for DFs but this link is not shareable.
- For Google Colab instead of using a .env I recommend putting your NGROK_AUTHTOKEN into the Google Colab secrets manager (key icon on the left side of the screen). That way your secrets also can be synced to other notebooks and you don't have to repeat the .env uploading each time.
- I initially aimed for full functionality (link sharing) with Google Colab however it seems impossible as Colab locks it to Colab session authentification.
- Google has also stated that they may deprecate their serve_kernel_port_as_window function in the future in which case it will be swapped to serve_kernel_port_as_iframe and the same functionality will remain except it will be in the IFrame.
- For now, there is an optional parameter that allows you to use the editor in IFrame mode.
- Check out a [demo notebook](https://colab.research.google.com/drive/1LUm6vmb-aWBqLk5h9mcLPadQFzAEXiDq?usp=sharing) here.

<video src="https://github.com/user-attachments/assets/373ec28c-d61e-467b-9b54-ff6225126396" controls="controls" muted="muted" style="max-width:100%;"></video>

## Future Features
- Better Dataframe handling (pagination, lazy loading, better frontend for big data)
- Better Security (input sanitization, CSRF protection, configurable endpoint rate limiting)
- Better UI (search, dark mode, export option)
- IFrame Usage Option in Google Colab
- True Asynchronicity with ipyparallel
- Code Recreation (instead of overwriting the df just solve the code needed)
- Multiple authenticated users
