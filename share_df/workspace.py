from share_df import create_share_server
import time
import os

def run_server():
    content = "<h2>Place Holder HTML</h2><p>This website could then be used for displaying the GUI!</p>"
    url, username, password = create_share_server(
        content=content,
        title="My Shared Content",
        duration_hours=1
    )
    print(f"Access your content at: {url}")
    print(f"Username: {username}")
    print(f"Password: {password}")

def run_ngrok():
    time.sleep(5)
    os.system("ngrok http http://localhost:8000")

run_server()
run_ngrok()