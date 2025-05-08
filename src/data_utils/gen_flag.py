import pandas as pd

def add_flag_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds a "flag" column to a DataFrame.

    The "flag" is -1 if "Fuel" is "Solar" or "Wind",
    and 1 otherwise.

    Args:
        df: The input pandas DataFrame. Must contain a "Unit Type" column.

    Returns:
        The DataFrame with the added "flag" column.
    """
    conditions = (df["Fuel"] == "Solar") | (df["Fuel"] == "Wind")
    df["flag"] = pd.Series(1, index=df.index)
    df.loc[conditions, "flag"] = -1
    return df