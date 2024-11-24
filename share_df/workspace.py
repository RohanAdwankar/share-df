from share_df import create_share_server
import time
import os

def run_server():
    content = "<h2>Place Holder HTML</h2><p>This website could then be used for displaying the GUI!</p>"
    url = create_share_server(
        content=content,
        title="My Shared Content",
        duration_hours=1
    )
    print(f"Access your content at: {url}")

def run_ngrok(email):
    os.system(f"ngrok http http://localhost:8000 --oauth google --oauth-allow-email {email}")

run_server()
email = input("Which gmail do you want to share this with?")
run_ngrok(email=email)