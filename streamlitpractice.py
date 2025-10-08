import streamlit as st

st.title("My First Streamlit App")
st.header("Introduction")
st.write("This is a simple app made using Streamlit.")

import pandas as pd
import numpy as np

df = pd.DataFrame(
    np.random.randn(10, 5),
    columns=['A', 'B', 'C', 'D', 'E']
)

st.dataframe(df)  # Interactive table
st.table(df)      # Static table
st.metric("Temperature", "25°C", "-1°C")  # KPI metric
name = st.text_input("Enter your name")
age = st.number_input("Enter your age", 0, 120)


option = st.selectbox("Choose an option", ["A", "B", "C"])
multi_option = st.multiselect("Select multiple options", ["X", "Y", "Z"])

value = st.slider("Pick a value", 0, 100, 50)
if st.button("Click Me"):
    st.write("Button clicked!")


import matplotlib.pyplot as plt

x = [1, 2, 3, 4]
y = [10, 20, 25, 30]

plt.plot(x, y)
st.pyplot(plt)
st.line_chart(df)    # Line chart
st.bar_chart(df)     # Bar chart
st.area_chart(df)    # Area chart

