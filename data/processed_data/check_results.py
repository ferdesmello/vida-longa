import pandas as pd
import numpy as np
import os

path = os.path.dirname(os.path.abspath(__file__))
data_mortality = path + "/" + "mortality_total.csv"

df_mortality = pd.read_csv(data_mortality)
print(df_mortality.head())
print(df_mortality.info())
print(df_mortality.describe())

sum = df_mortality["deaths"].sum()
print("Total deaths:", sum)

data_cause = path + "/" + "mortality_by_cause.csv"

df_cause = pd.read_csv(data_cause)
print(df_cause.head())
print(df_cause.info())
print(df_cause.describe())

sum = df_cause["deaths"].sum()
print("Total deaths:", sum)
