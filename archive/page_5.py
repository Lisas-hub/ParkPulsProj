#FÖRSÖK VISUALISERA GOOGLE SHEETS
#INSTRUKTIONER: https://docs.streamlit.io/develop/tutorials/databases/private-gsheet

# .streamlit/secrets.toml
[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/1OwMi2rcUWdvUCCwSzqbBSWzoW9DYQEer4KGCJfbzMhw/edit?gid=1348847931#gid=1348847931"

# From your JSON key file
type = "service_account"
project_id = "starlit-myth-462509-k4"
private_key_id = "34510126a0065100864f9bc901789f6a2a600aaa"
private_key = r"-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDR9l8RqG9XGocG\ngDw+gjYUcLL0xw/AQSTF+8xUQWVVjoenq/oF9ZxC3eSCkmoba9xegArnPA8r3IaJ\nZuzZUnxGrIo/T1V+MgZg+Eeg9qxEfm++AdPYtr7FMcTdh5UuycbnPyXMhzz+KhqB\nIYoPa70UaxeGkHkw5uv8ABwDpqkv+aP8IU5zqeZ8awZ4TgqOyKPMgYiTVVWki2KW\nPLnpmav1Ft6qEMaIyDucSPFvTHHbo/BRyvK5R7J7s6yMUAGV9B0ZQTH3yzjwNq4s\n26plgIW0q5TpnPqLlIfAoURV8G4uF4tqKDHJhHTtD6qP+u40pCj/AzH1xofWQEER\nYCBudGprAgMBAAECggEAKicp+AwWamjnge0d6zjOLbVgoFcUuPb7MIp4f9PvScmH\nP6j91dN1L1GILpTBm8bAY/KV/c2niBlKo2xYEduHGtNKICLH2cGmWTKPgufzNv8h\nZQbN5tztmP6AdS9iypV1Cvk5GAJwwuBmGNXId4ccW2ySuQ/pXOGHsDy/YxZDMl+x\nnbfh43hSxxDP2ye7L4v7AwtJJBn6Ned7hKawUDyrXOYPUYQGxuMC7jqLA+Z/XxDR\n8KnIbD/+yM3Zbs0+rgO6efTUvOVY/plBn8neAdUdbAi8gvk8WuaoJMDo26xLWt1Q\nrZ/JeaWoPAN4zrudHwpQiRwBJbA+dxK7ZgLFUvp5eQKBgQDwrg6RFx50aQLBPhhb\nFgJnWdTv+6Xoj8Dwzq1p3n9QngscRizCX0fkGmAGQB+GwYH56xcmfs8J2qkrn1yN\nZwn7lmmlqEaHX0YYujh8t+nybDcz34fvq8L9iG7Ro+h/9IMr5Mj/c7uHh7vvtQK2\nzhK834pVmjLvyFsu0J81MhWY8wKBgQDfU8OoBT+lzaTcGCizheeBeD4jLxgWMzyR\njK4fc7YsQ3Rkgr37kGHT5gE3GGG/V85qc0bUWdPDdDDlhd3WgwR3L0AiF7wRtkCs\nJxtskU5AEHcXpSL6Cqvhfme1UCvO1p6+Hr0y/PkEPobRD6Ff8fdLqT5PmGZiM7bu\nOW9DSCBGqQKBgCwxqdcWia8SgUD+p/ZBylsz8ZfHe6WCkAknykwAYRxqiNu+PwXJ\n/SdzeGJtb9yMt9MuSef1rQrALgQmlRYZ74lVCz0x8xF0eyibOTgdhUXQfSp3RzzJ\nK1rmrIKuOEkWmud6cTYHCE5QrD/N2xu6J1KrMXmagPPqtGOaR0G7Wp/lAoGBAMkL\naVm6z999T2prvUhPxWdCTf3yiWaC3YXR9XaO/nK+jutk3462HbtalcF5i5VrgIFI\nIX1NGFweH16gsmJINB7vRHbskvwG7BWOZxvHe4Ak0nFQ0jnynWU0HDyXXbiocOOK\nXJyoK6xsdYWC4q2y8AMG6vdQpOrGz2mJ/uW86oFxAoGAatTpDcm6ilSJ4YnSzduJ\n9kkHXhUJ1cpvQUNP341FVVBouvmVu4BrMwBhCG0yOeYB99vnrBmtoYv6fVsRJHlb\nSX4w1FdeSeFgMYyyRsQza9KWsy8FzCYqKRvu5HZx/5XSltrQlzkRZ9Sr6Zl3P0Tr\nO7qCkZlKu/emVVz4ONla+qo=\n-----END PRIVATE KEY-----\n"
client_email = "service-acc@starlit-myth-462509-k4.iam.gserviceaccount.com"
client_id = "100036519033467578175"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/service-acc%40starlit-myth-462509-k4.iam.gserviceaccount.com"

from streamlit_gsheets import GSheetsConnection

# Create a connection object.
conn = st.connection("gsheets", type=GSheetsConnection)

df = conn.read()

# Print results.
for row in df.itertuples():
    st.write(f"{row.name} has a :{row.pet}:")