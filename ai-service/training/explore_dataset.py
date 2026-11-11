import pandas as pd

# Load the referral dataset
data = pd.read_csv("datasets/raw/referrals.csv")

# Display the first five records
print("\nFIRST FIVE REFERRALS")
print(data.head())

# Display dataset information
print("\nDATASET INFORMATION")
print(data.info())

# Display statistical information
print("\nSTATISTICAL SUMMARY")
print(data.describe())

# Check missing values
print("\nMISSING VALUES")
print(data.isnull().sum())

# Check the number of delayed and non-delayed referrals
print("\nDELAY DISTRIBUTION")
print(data["delayed"].value_counts())