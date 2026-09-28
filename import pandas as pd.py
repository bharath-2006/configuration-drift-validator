import pandas as pd

df = pd.read_csv('practice.csv')

print(df.head())
print(df.info())
print(df.tail())
print(df.shape)