import pandas as pd

df = pd.read_csv(
    r"C:\Users\USER\Desktop\serious\freelance\oneapp\database\total andrew_8.1mln_bounces_cleaned.txt",
    sep="jhjujhj",
)

df.iloc[7000000:7500000, :].to_csv("ffd.csv", index=False)
