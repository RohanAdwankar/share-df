from share_df import create_share_server
import time
import os
import ngrok

def run_server():
    content = "<h2>Place Holder HTML</h2><p>This website could then be used for displaying the GUI!</p>"
    return create_share_server(
        content=content,
        title="My Shared Content",
        duration_hours=1
    )

def run_ngrok(url, email):
    listener = ngrok.forward(url, authtoken_from_env=True, oauth_provider="google", oauth_allow_emails=email)
    print(f"Ingress established at: {listener.url()}");
    time.sleep(10)

url = run_server()
email = input("Which gmail do you want to share this with? ")
run_ngrok(url=url, email=email)