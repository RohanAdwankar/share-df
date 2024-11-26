# Notes
- The package is not working on Google Collab currently, but is working for local scripting or notebooks
- The package requires using a .env that is supplied with an ngrok auth token. This is free and takes less than a minute [here](https://dashboard.ngrok.com/)!

# Functionality
## On the Dev Side
- pip install ✅
- one command to generate link to send ✅ 
- changes made by client are recieved back ✅
## On the Client Side
- OAuth for easy google based login ✅ 
- Seamless UI to modify the dataframe ✅
- Send the results back with the click of a button ✅  
## Future Functionality
- True Asynchronicity with ipyparallel
- Code Recreation (instead of overwriting the df just solve the code needed)

# Examples
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