# Functionality
## On the Dev Side
- pip install
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
```
    df3 = pd.DataFrame({
        'Name': ['Joe', 'Roger', 'Exponent', 'Yay!'],
        'Age': [25, 30, 35, 28],
        'City': ['New York', 'London', 'Paris', 'Tokyo'],
        'Salary': [50000, 60000, 75000, 65000]
    })
    df3.pandaBear()
    print(df3)
```