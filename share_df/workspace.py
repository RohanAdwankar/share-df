from share_df import create_share_server
import time

content = "<h2>Place Holder HTML</h2><p>This website could then be used for displaying the GUI!</p>"

# Create the server
url, username, password = create_share_server(
    content=content,
    title="My Shared Content",
    duration_hours= 1
)

print(f"Access your content at: {url}")
print(f"Username: {username}")
print(f"Password: {password}")

time.sleep(100)