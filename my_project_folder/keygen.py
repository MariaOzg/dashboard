import streamlit_authenticator as stauth
from streamlit_authenticator.utilities.hasher import Hasher

# Ваши пароли
passwords = [
    "pass1", 
    "pass2", 
    "pass3", 
    "pass4", 
    "pass5"
]

# НОВЫЙ СПОСОБ ГЕНЕРАЦИИ:
hashed_passwords = Hasher.hash_list(passwords)

print(hashed_passwords)