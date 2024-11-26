
## Instantly Share and Modify Dataframes With a Web Interface From Anywhere with One Line

https://github.com/user-attachments/assets/fd8e9ea4-b0d5-4d61-abfc-cd584ba7af44

## Vision
This package enables cross-collaboration between nontechnical and technical contributors by allowing developers to generate a URL for free with one line of code that they can then send to nontechnical contributors enabling them to modify the dataframe with a web app. Then, they can send it back to the developer, directly generating the modified dataframe maintaining code continuity, and removing the burden of file transfer and conversion to other file formats.

## Technical Contributor Features
- pip install share-df ✅
- one function call to generate link to send, accessible anywhere ✅ 
- changes made by client are recieved back as a dataframe for seamless development ✅
  
## Nontechnical Contributor Features
- Easy Google OAuth login ✅ 
- Seamless UI to modify the dataframe ✅
    * Change column names
    * Drag around columns
    * Change all values
    * Rename columns
    * Add new columns and rows
- Send the results back with the click of a button ✅
  
## Future Functionality
- True Asynchronicity with ipyparallel
- Code Recreation (instead of overwriting the df just solve the code needed)

## Notes
- The package is not working on Google Collab currently, but is working for local scripting or notebooks
- The package requires using a .env that is supplied with an ngrok auth token. This is free and takes less than a minute [here](https://dashboard.ngrok.com/)!

## Examples
```
    df = pd.DataFrame({
        'Name': ['John', 'Alice', 'Bob', 'Carol'],
        'Age': [25, 30, 35, 28],
        'City': ['New York', 'London', 'Paris', 'Tokyo'],
        'Salary': [50000, 60000, 75000, 65000]
    })
    df2 = pandaBear(df)
    print(df2)
```
